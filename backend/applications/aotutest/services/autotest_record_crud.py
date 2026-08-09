# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_record_crud
@DateTime: 2026/2/1 12:13
"""
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Union, List, Tuple

from tortoise.exceptions import FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiRecordInfo
from backend.applications.aotutest.schemas.autotest_record_schema import (
    AutoTestApiRecordCreate,
    AutoTestApiRecordUpdate,
    AutoTestApiRecordSelect,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException, NotFoundException


class AutoTestApiTaskRecordCrud(ScaffoldCrud[AutoTestApiRecordInfo, AutoTestApiRecordCreate, AutoTestApiRecordUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiRecordInfo)

    async def get_by_id(self, record_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiRecordInfo]:
        """
        根据主键ID查询执行记录。

        :param record_id: 执行记录主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 执行记录实例或None
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

    async def get_by_celery_id(self, celery_id: str, **kwargs) -> Optional[AutoTestApiRecordInfo]:
        """
        根据Celery任务ID查询执行记录。

        :param celery_id: Celery任务ID；为空时返回None
        :param kwargs: 额外过滤条件
        :return: 记录实例或None
        """
        if not celery_id:
            return None
        return await self.model.filter(celery_id=celery_id, **kwargs).first()

    async def create_record(self, data: Union[AutoTestApiRecordCreate, Dict[str, Any]]) -> AutoTestApiRecordInfo:
        """
        创建一条任务执行记录。

        :param data: 创建入参Schema或字段字典
        :return: 新建的记录实例
        """
        if isinstance(data, dict):
            record_in = AutoTestApiRecordCreate.model_validate(data)
        else:
            record_in = data
        return await self.create(record_in.create_dict())

    async def update_record(
            self,
            data: Union[AutoTestApiRecordUpdate, Dict[str, Any]],
            *,
            record_id: Optional[int] = None,
            celery_id: Optional[str] = None,
    ) -> AutoTestApiRecordInfo:
        """
        更新一条任务执行记录（按主键或celery_id定位）。

        :param data: 更新入参Schema或字段字典
        :param record_id: 执行记录主键
        :param celery_id: Celery任务ID；与 record_id 二选一
        :return: 更新后的记录实例
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
            record_in = AutoTestApiRecordUpdate.model_validate(data)
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
        self._fill_updated_user(update_dict)
        if not update_dict.get("updated_user"):
            username = str(record.created_user).strip() if record.created_user else None
            if username:
                update_dict["updated_user"] = username.upper()[:16]

        return await self.update(id=record.id, obj_in=update_dict)

    async def update_record_by_celery_id(
            self,
            celery_id: str,
            data: Union[AutoTestApiRecordUpdate, Dict[str, Any]],
    ) -> Optional[AutoTestApiRecordInfo]:
        """
        根据celery_id更新执行记录；仅写入模型已有字段，部分键允许置空。

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

    async def select_records(self, record_in: AutoTestApiRecordSelect) -> Tuple[int, List[AutoTestApiRecordInfo]]:
        """
        根据条件分页查询任务执行记录。

        :param record_in: 查询条件(含分页、排序与时间区间)
        :return: (总数, 记录列表)
        """
        try:
            q = Q()
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
                """将YYYY-MM-DD HH:MM:SS格式的字符串解析为datetime对象，失败返回None。"""
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
            error_message: str = f"查询任务执行记录异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
