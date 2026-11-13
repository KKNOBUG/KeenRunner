# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_record_crud
@DateTime: 2026/2/1 12:13

任务执行记录（krun_autotest_record）的CRUD：异步中心与执行历史的统一记录表。

一行记录代表一次Celery任务（导入/导出/脚本生成/用例执行等），终态以 celery_status 为准；
task_summary 为结果快照，附件以 attachments 信封存放于其中，删除记录时需同步清理对应产物文件。
"""
import os
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Union, List, Tuple, Set

from tortoise.exceptions import FieldError
from tortoise.expressions import Q

from backend.applications.autotest.models.autotest_record_model import AutoTestRecordModel
from backend.applications.autotest.schemas.autotest_record_schema import (
    AutoTestRecordCreate,
    AutoTestRecordUpdate,
    AutoTestRecordSelect,
    AutoTestRecordBatchDelete,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.celery_scheduler.celery_task_contract import list_attachments_from_summary, resolve_storage_path
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException, NotFoundException, NoPermissionException
from backend.enums import AutoTestTaskStatus, AutoTestTaskType
from backend.services import DataScope, normalize_username

# 终态状态值集合：仅终态(成功/失败/部分成功)记录允许删除
_RECORD_FINAL_STATUS_VALUES = frozenset(
    s.value for s in (AutoTestTaskStatus.SUCCESS, AutoTestTaskStatus.FAILURE, AutoTestTaskStatus.PARTIAL_SUCCESS)
)


def _remove_artifact_files(record: AutoTestRecordModel) -> None:
    """
    物理清理执行记录的产物文件；单个文件失败仅告警，不阻断其余清理。

    附件从 task_summary 的 attachments 信封取 storage_key，再还原为本地磁盘路径；
    非法键/磁盘异常均只记日志，因此调用方应在记录已删除之后调用，避免“文件已清、记录未删”。

    :param record: 已提交删除的执行记录行（仅需 task_summary）
    :return: None
    """
    for attachment in list_attachments_from_summary(getattr(record, "task_summary", None)):
        storage_key = str(attachment.get("storage_key") or "").strip()
        if not storage_key:
            continue
        try:
            file_path = resolve_storage_path(storage_key)
            if os.path.isfile(file_path):
                os.remove(file_path)
        except ValueError:
            LOGGER.warning(f"清理产物文件失败, 非法storage_key[{storage_key}]\n{traceback.format_exc()}")
        except OSError:
            LOGGER.warning(f"清理产物文件失败, 文件[{storage_key}]\n{traceback.format_exc()}")


class AutoTestRecordCrud(ScaffoldCrud[AutoTestRecordModel, AutoTestRecordCreate, AutoTestRecordUpdate]):
    """
    任务执行记录CRUD：异步任务进度/结果回写、异步中心列表查询与带产物的删除。

    写入主要由 Celery 任务回调驱动（直写 service，不过对外写接口）；读列表按 created_user 做范围过滤。
    删除约束：仅终态（成功/失败/部分成功）可删，且记录为物理删除。
    """

    def __init__(self):
        """绑定执行记录模型，供基类通用CRUD复用。"""
        super().__init__(model=AutoTestRecordModel)

    async def get_by_id(self, record_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestRecordModel]:
        """
        根据主键ID查询执行记录。

        :param record_id: 执行记录主键ID，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 执行记录实例或None
        :raises ParameterException: record_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
        """
        if not record_id:
            error_message: str = "查询执行记录信息失败, 参数[record_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=record_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询执行记录信息失败, 记录[id={record_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_celery_id(self, celery_id: str, **kwargs) -> Optional[AutoTestRecordModel]:
        """
        根据Celery任务ID查询执行记录。

        celery_id 仅有普通索引（非唯一），命中多行时返回首条；仅供 Celery 回调定位记录。

        :param celery_id: Celery任务ID；为空时返回None
        :param kwargs: 额外过滤条件
        :return: 记录实例或None
        """
        if not celery_id:
            return None
        return await self.model.filter(celery_id=celery_id, **kwargs).first()

    async def create_record(self, data: Union[AutoTestRecordCreate, Dict[str, Any]]) -> AutoTestRecordModel:
        """
        创建一条任务执行记录。

        :param data: 创建入参Schema或字段字典
        :return: 新建的记录实例
        :raises ValidationError: dict 入参不符合 Schema 约束（Pydantic 校验异常）
        """
        if isinstance(data, dict):
            record_in = AutoTestRecordCreate.model_validate(data)
        else:
            record_in = data
        return await self.create(record_in.create_dict())

    async def update_record(
            self,
            data: Union[AutoTestRecordUpdate, Dict[str, Any]],
            *,
            record_id: Optional[int] = None,
            celery_id: Optional[str] = None,
    ) -> AutoTestRecordModel:
        """
        更新一条任务执行记录（按主键或celery_id定位）。

        只写模型已有字段；task_summary/task_error/batch_code 允许显式置空（其余字段的 None 一律忽略，
        防止部分更新把存量进度/结果抹掉）。无登录上下文（Celery回调）时 updated_user 回落创建人。

        :param data: 更新入参Schema或字段字典
        :param record_id: 执行记录主键
        :param celery_id: Celery任务ID；与 record_id 二选一
        :return: 更新后的记录实例
        :raises ParameterException: 两个定位参数同时为空
        :raises NotFoundException: 记录不存在或已软删
        """
        if not record_id and not celery_id:
            error_message: str = "更新执行记录失败, 参数[record_id]或[celery_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if record_id:
            record = await self.get_by_id(record_id=record_id, on_error=True, state__not=1)
        else:
            record = await self.get_by_celery_id(celery_id=celery_id, state__not=1)
            if not record:
                error_message: str = f"更新执行记录失败, 记录[celery_id={celery_id}]不存在"
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        if isinstance(data, dict):
            record_in = AutoTestRecordUpdate.model_validate(data)
            raw = data
        else:
            record_in = data
            raw = data.model_dump(exclude_unset=True)
        update_dict = record_in.update_dict()
        # task_summary/task_error/batch_code允许显式置空
        allow_none_keys = ("task_summary", "task_error", "batch_code")
        update_dict = {
            k: v for k, v in update_dict.items()
            if hasattr(record, k) and (v is not None or (k in allow_none_keys and k in raw))
        }
        # 有CTX时以登录用户为准；Celery等无上下文时保留入参，再回落到创建人员
        self.fill_updated_user(update_dict)
        if not update_dict.get("updated_user"):
            username = str(record.created_user).strip() if record.created_user else None
            if username:
                update_dict["updated_user"] = normalize_username(username)

        return await self.update(id=record.id, obj_in=update_dict)

    async def update_record_by_celery_id(
            self,
            celery_id: str,
            data: Union[AutoTestRecordUpdate, Dict[str, Any]],
    ) -> Optional[AutoTestRecordModel]:
        """
        根据celery_id更新执行记录；仅写入模型已有字段，部分键允许置空。

        与 update_record 的差异：记录不存在时返回 None 而不抛错，供 Celery 回调做幂等更新
        （任务可能因强制终止而尚未建记录）。

        :param celery_id: Celery任务ID
        :param data: 更新入参Schema或字段字典
        :return: 更新后的记录；不存在则返回None
        """
        record = await self.get_by_celery_id(celery_id=celery_id, state__not=1)
        if not record:
            return None
        try:
            return await self.update_record(data, celery_id=celery_id)
        except NotFoundException:
            return None

    async def select_records(self, record_in: AutoTestRecordSelect, scope: DataScope) -> Tuple[int, List[AutoTestRecordModel]]:
        """
        根据条件分页查询任务执行记录。

        未指定 task_type/task_type_in 时默认排除三类“执行类”任务（多用例/单用例/调度扫描），
        使异步中心只展示导入/导出/脚本生成等异步产物任务。

        :param record_in: 查询条件(含分页、排序与时间区间)
        :param scope: 数据权限上下文，按创建人过滤可见范围
        :return: (总数, 记录列表)
        :raises ParameterException: 查询/排序字段不被ORM支持
        """
        try:
            q = Q(state__not=1)
            owner_q = scope.read_q("created_user")
            if owner_q is not None:
                q &= owner_q
            if record_in.celery_id:
                q &= Q(celery_id=record_in.celery_id)
            if record_in.task_id is not None:
                q &= Q(task_id=record_in.task_id)
            if record_in.task_code:
                q &= Q(task_code=record_in.task_code)
            if record_in.task_name:
                q &= Q(task_name__contains=record_in.task_name)
            if record_in.task_type is not None:
                type_val = getattr(record_in.task_type, "value", record_in.task_type)
                q &= Q(task_type=type_val)
            if record_in.task_type_in:
                type_vals = [getattr(t, "value", t) for t in record_in.task_type_in]
                q &= Q(task_type__in=type_vals)
            elif record_in.task_type is None:
                # 默认排除仅用于异步中心缺省查询，显式单值类型不得再叠加相反条件
                q &= Q(task_type__not_in=[
                    AutoTestTaskType.MULTIPLE_CASE_EXECUTE,
                    AutoTestTaskType.SINGLE_CASE_EXECUTE,
                    AutoTestTaskType.SCHEDULE_SCANNER]
                )
            if record_in.created_user:
                q &= Q(created_user__contains=record_in.created_user)
            if record_in.task_project is not None:
                q &= Q(task_project=record_in.task_project)
            if record_in.trigger_type is not None:
                trigger_val = getattr(record_in.trigger_type, "value", record_in.trigger_type)
                q &= Q(trigger_type=trigger_val)
            if record_in.batch_code:
                q &= Q(batch_code=record_in.batch_code)
            if record_in.celery_status is not None:
                status_val = getattr(record_in.celery_status, "value", record_in.celery_status)
                q &= Q(celery_status=status_val)

            def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
                """将YYYY-MM-DD HH:MM:SS格式字符串解析为datetime，失败返回None；超长部分（如带小数秒）截断。"""
                if not raw:
                    return None
                try:
                    return datetime.strptime(raw.strip()[:19], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None

            start_begin = _parse_dt(record_in.celery_start_time_begin)
            if start_begin:
                q &= Q(celery_start_time__gte=start_begin)
            start_end = _parse_dt(record_in.celery_start_time_end)
            if start_end:
                q &= Q(celery_start_time__lte=start_end)
            end_begin = _parse_dt(record_in.celery_end_time_begin)
            if end_begin:
                q &= Q(celery_end_time__gte=end_begin)
            end_end = _parse_dt(record_in.celery_end_time_end)
            if end_end:
                q &= Q(celery_end_time__lte=end_end)

            total, instances = await self.list(
                page=record_in.page,
                page_size=record_in.page_size,
                search=q,
                order=record_in.order,
            )
            return total, list(instances)
        except FieldError as e:
            error_message: str = "查询任务执行记录失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def delete_record_with_artifacts(self, record_id: int, scope: DataScope) -> int:
        """
        删除终态执行记录并物理清理产物文件。

        仅终态(成功/失败/部分成功)且创建人为当前用户的记录允许删除；记录硬删后尽力清理task_summary
        信封中的产物文件，单个文件清理失败仅告警不影响删除结果。

        :param record_id: 执行记录主键
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的执行记录
        :return: 删除的记录数(0或1)
        :raises NotFoundException: 记录不存在
        :raises NoPermissionException: 记录创建人不在当前用户可删除范围内
        :raises ParameterException: 记录未到终态(等待执行/正在执行)不允许删除
        """
        record = await self.get_by_id(record_id=record_id, on_error=True, state__not=1)
        await scope.load_owners([record.created_user])
        if not scope.can_delete(record.created_user):
            error_message: str = f"删除执行记录失败, 记录[id={record_id}]创建人[{record.created_user}]不在当前用户可删除范围内"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        status_val = getattr(record.celery_status, "value", record.celery_status)
        if status_val not in _RECORD_FINAL_STATUS_VALUES:
            error_message: str = f"删除执行记录失败, 记录[id={record_id}]未到终态(当前状态: {status_val})"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        deleted = await self.model.filter(id=record.id).delete()
        # 记录已物理删除后再清理产物文件，避免清理成功而删除失败的中间态
        _remove_artifact_files(record=record)
        return deleted

    async def delete_records_with_artifacts(self, record_in: AutoTestRecordBatchDelete, scope: DataScope) -> int:
        """
        批量删除终态执行记录并物理清理产物文件；先全量校验，任一记录不满足条件则整批拒绝。

        :param record_in: 执行记录ID列表
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的执行记录
        :return: 实际删除的记录数
        :raises NotFoundException: 存在记录不存在
        :raises NoPermissionException: 存在记录创建人不在当前用户可删除范围内
        :raises ParameterException: 存在记录未到终态(等待执行/正在执行)不允许删除
        """
        unique_ids: List[int] = list(dict.fromkeys(int(rid) for rid in record_in.record_ids))
        targets: List[AutoTestRecordModel] = list(await self.model.filter(id__in=unique_ids, state__not=1))
        found_ids: Set[int] = {instance.id for instance in targets}
        missing_ids: List[int] = [rid for rid in unique_ids if rid not in found_ids]
        if missing_ids:
            error_message: str = f"批量删除执行记录失败, 记录[id={missing_ids}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        await scope.load_owners([instance.created_user for instance in targets])
        for instance in targets:
            if not scope.can_delete(instance.created_user):
                error_message: str = (
                    f"批量删除执行记录失败, 记录[id={instance.id}]创建人[{instance.created_user}]不在当前用户可删除范围内"
                )
                LOGGER.error(error_message)
                raise NoPermissionException(message=error_message)
            status_val = getattr(instance.celery_status, "value", instance.celery_status)
            if status_val not in _RECORD_FINAL_STATUS_VALUES:
                error_message: str = (
                    f"批量删除执行记录失败, 记录[id={instance.id}]未到终态(当前状态: {status_val})"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

        deleted = await self.model.filter(id__in=list(found_ids)).delete()
        # 记录已物理删除后再清理产物文件，避免清理成功而删除失败的中间态
        for instance in targets:
            _remove_artifact_files(record=instance)
        return deleted
