# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_crud
@DateTime: 2026/1/31 12:42
"""
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import FieldError
from tortoise.expressions import Q, RawSQL

from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel
from backend.applications.autotest.schemas.autotest_task_schema import AutoTestApiTaskCreate, AutoTestApiTaskUpdate
from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud
from backend.applications.autotest.services.autotest_task_schedule import normalize_schedule
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.enums import AutoTestTaskPeriodicMode
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    ParameterException,
)


def extract_task_involve_envs(cases_execute_config: Any) -> List[str]:
    """
    累积各用例involve_envs并去重，生成task级涉及环境名称列表。

    :param cases_execute_config: 任务级用例执行配置字典
    :return: 排序后的环境名称列表
    """
    if not isinstance(cases_execute_config, dict):
        return []
    env_names: Set[str] = set()
    for case_key, case_cfg in cases_execute_config.items():
        # 跳过顶层全局键(env_mode/env_name)，仅累积case_id配置的involve_envs
        if case_key in ("env_mode", "env_name"):
            continue
        involve_envs = case_cfg.get("involve_envs") if isinstance(case_cfg, dict) else None
        if isinstance(involve_envs, list):
            env_names.update(str(x) for x in involve_envs if x not in (None, ""))
    return sorted(env_names)


def resolve_cases_execute_config(task_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    解析用例执行配置。

    :param task_dict: 任务字段字典
    :return: cases_execute_config字典或None
    """
    cases_cfg = task_dict.get("cases_execute_config")
    return cases_cfg if isinstance(cases_cfg, dict) else None


def normalize_task_kwargs(task_kwargs: Any) -> Optional[Dict[str, Any]]:
    """
    规范化task_kwargs：仅承载initial_variables及未知扩展键。

    :param task_kwargs: 原始task_kwargs
    :return: 清洗后的字典；输入None时返回None
    """
    if task_kwargs is None:
        return None
    if not isinstance(task_kwargs, dict):
        return {}
    return dict(task_kwargs)


class AutoTestTaskCrud(ScaffoldCrud[AutoTestTaskModel, AutoTestApiTaskCreate, AutoTestApiTaskUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestTaskModel)

    @staticmethod
    def _dump_enum_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将任务字典中的枚举字段(task_type等)转为原始值。

        :param data: 任务字段字典
        :return: 原地转换后的字典
        """
        for key in ("task_type", "task_execute_mode", "task_periodic_expr", "last_execute_state"):
            if key in data and data[key] is not None and hasattr(data[key], "value"):
                data[key] = data[key].value
        # cases_execute_config顶层env_mode枚举转值
        cases_cfg = data.get("cases_execute_config")
        if isinstance(cases_cfg, dict) and hasattr(cases_cfg.get("env_mode"), "value"):
            cases_cfg["env_mode"] = cases_cfg["env_mode"].value
        return data

    @staticmethod
    def _apply_task_fields(task_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用任务字段处理：
        1. 规范化task_kwargs
        2. 根据cases_execute_config累积task_involve_envs

        :param task_dict: 任务字段字典
        :return: 原地处理后的字典
        """
        if "task_kwargs" in task_dict:
            task_dict["task_kwargs"] = normalize_task_kwargs(task_dict.get("task_kwargs"))
        cases_cfg = resolve_cases_execute_config(task_dict)
        if cases_cfg is not None:
            task_dict["task_involve_envs"] = extract_task_involve_envs(cases_cfg)
        return task_dict

    async def get_by_id(self, task_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestTaskModel]:
        """
        根据主键ID查询任务。

        :param task_id: 任务主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 任务实例或None
        """
        if not task_id:
            error_message: str = "查询任务信息失败, 参数[task_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=task_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 记录[id={task_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, task_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestTaskModel]:
        """
        根据任务标识代码查询任务。

        :param task_code: 任务标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 任务实例或None
        """
        if not task_code:
            error_message: str = "查询任务信息失败, 参数[task_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(task_code=task_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 记录[code={task_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_task(self, task_in: AutoTestApiTaskCreate) -> AutoTestTaskModel:
        """
        创建应用；同名软删记录恢复并更新，活跃同名报错。

        :param task_in: 任务创建schema
        :return: 创建后的任务实例
        """
        task_name: str = task_in.task_name
        task_project: int = task_in.task_project

        # 业务层验证：检查应用是否存在
        await AutoTestProjectCrud().get_by_id(project_id=task_project, on_error=True, state__not=1)

        # 业务层验证：(task_name, task_project)数据库唯一
        existing_task = await self.model.filter(task_name=task_name, task_project=task_project).first()
        if existing_task and existing_task.state != 1:
            error_message: str = f"任务[task_name={task_name}, task_project={task_project}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            task_dict: Dict[str, Any] = task_in.model_dump(exclude_none=True, exclude_unset=True)
            task_dict = self._dump_enum_fields(task_dict)
            if "task_schedule_expr" in task_dict:
                task_dict["task_schedule_expr"] = normalize_schedule(
                    periodic=task_dict.get("task_periodic_expr"), schedule=task_dict.get("task_schedule_expr")
                )
            if task_dict.get("created_user") and not task_dict.get("updated_user"):
                task_dict["updated_user"] = task_dict["created_user"]
            task_dict = self._apply_task_fields(task_dict)
            if existing_task and existing_task.state == 1:
                LOGGER.info(f"复活软删任务: id={existing_task.id}, task_name={task_name}, task_project={task_project}")
                task_dict.update({
                    "state": 0,
                    "last_execute_time": None,
                    "last_execute_state": None,
                    "last_execute_user": None,
                })
                if "task_schedule_expr" not in task_dict:
                    task_dict["task_schedule_expr"] = None
                    task_dict.setdefault("task_periodic_expr", AutoTestTaskPeriodicMode.UNBOUNDED.value)
                instance = await self.update(id=existing_task.id, obj_in=task_dict)
            else:
                instance = await self.create(task_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增任务信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def copy_task(self, task_id: int, operate_user: Optional[str] = None) -> AutoTestTaskModel:
        """
        完全复刻任务记录生成新任务：业务配置原样复制，task_code重新生成、
        task_enabled默认停用(避免复制后立即产生双调度)、执行痕迹(last_execute_time/state/user)重置。

        :param task_id: 源任务主键ID
        :param operate_user: 当前操作人，作为新任务的created_user/updated_user
        :return: 复制生成的新任务实例
        """
        source = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        # 新名称=原名+微秒时间戳后缀：(task_name, task_project)唯一性由时间戳唯一性保证，无需查重；
        # 原名按后缀长度截断，确保不超task_name上限255
        suffix: str = datetime.now().strftime("%Y%m%d%H%M%S%f")
        new_task_name: str = f"{source.task_name[:255 - len(suffix) - 1]}_{suffix}"
        copy_in = AutoTestApiTaskCreate(
            task_name=new_task_name,
            task_desc=source.task_desc,
            task_type=source.task_type,
            task_project=source.task_project,
            task_execute_mode=source.task_execute_mode,
            task_case_ids=source.task_case_ids,
            task_kwargs=source.task_kwargs,
            dataset_enabled=source.dataset_enabled,
            cases_execute_config=source.cases_execute_config,
            task_schedule_expr=source.task_schedule_expr,
            task_periodic_expr=source.task_periodic_expr,
            task_notify=source.task_notify,
            task_notifier=source.task_notifier,
            created_user=operate_user,
        )
        return await self.create_task(task_in=copy_in)

    async def update_task(self, task_in: AutoTestApiTaskUpdate) -> AutoTestTaskModel:
        """
        更新任务，根据task_id或task_code定位并校验(task_name, task_project)唯一。

        :param task_in: 任务更新schema
        :return: 更新后的任务实例
        """
        task_id: Optional[int] = task_in.task_id
        task_code: Optional[str] = task_in.task_code
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)
            task_id = instance.id

        update_dict: Dict[str, Any] = task_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"task_id", "task_code"}
        )
        # 定时表达式允许显式清空：exclude_none会剔除前端传null的两键，
        # 按model_fields_set检测显式清空意图，还原为None以便覆盖旧定时；
        # 原有定时被清空时同步停用调度，避免残留“已启动但永不触发”的误导状态
        _schedule_keys = ("task_periodic_expr", "task_schedule_expr")
        _clearing_schedule = any(
            key in task_in.model_fields_set and getattr(task_in, key, None) is None
            for key in _schedule_keys
        )
        if _clearing_schedule and (instance.task_periodic_expr or instance.task_schedule_expr):
            update_dict["task_periodic_expr"] = None
            update_dict["task_schedule_expr"] = None
            update_dict["task_enabled"] = False
        update_dict = self._dump_enum_fields(update_dict)
        if "task_periodic_expr" in update_dict or "task_schedule_expr" in update_dict:
            # 时效与定时表达式联动校验：以合并后的时效校验合并后的定时，防止单改时效后存量定时失配
            update_dict["task_schedule_expr"] = normalize_schedule(
                periodic=update_dict.get("task_periodic_expr", instance.task_periodic_expr),
                schedule=update_dict.get("task_schedule_expr", instance.task_schedule_expr),
            )
        if "task_kwargs" in update_dict:
            update_dict["task_kwargs"] = normalize_task_kwargs(update_dict.get("task_kwargs"))
        # 提交了cases_execute_config时，同步累积task_involve_envs
        if "cases_execute_config" in update_dict:
            update_dict["task_involve_envs"] = extract_task_involve_envs(update_dict.get("cases_execute_config"))
        task_name = update_dict.get("task_name", instance.task_name)
        task_project = update_dict.get("task_project", instance.task_project)
        existing_task = await self.model.filter(
            task_name=task_name,
            task_project=task_project,
            state__not=1
        ).exclude(id=task_id).first()
        if existing_task:
            error_message: str = f"任务(task_name={task_name}, task_project={task_project})已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=task_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新任务信息失败, 记录[id={task_id}]或[code={task_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新任务信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_task(self, task_id: Optional[int] = None, task_code: Optional[str] = None) -> AutoTestTaskModel:
        """
        软删除任务并关闭调度。

        :param task_id: 任务主键ID，与task_code二选一
        :param task_code: 任务标识代码，与task_id二选一
        :return: 软删除后的任务实例
        """
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)

        instance = await self.soft_delete(id=instance.id)
        instance.task_enabled = False
        await instance.save(update_fields=["task_enabled"])
        return instance

    async def set_task_enabled(self, task_id: int, enabled: bool = True, updated_user: Optional[str] = None) -> AutoTestTaskModel:
        """
        设置任务是否启用调度(仅切换task_enabled，触发依赖task_schedule_expr)。

        :param task_id: 任务主键ID
        :param enabled: 是否启用
        :param updated_user: 操作人员账号(启停调度视为任务修改，刷新维护人；调度触发执行的执行人归因到该人)
        :return: 更新后的任务实例
        :raises ParameterException: 启用调度时任务尚无定时表达式
        """
        instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        # 无定时表达式的任务启用后永不触发，误导为“已启动”；启动前强制校验
        if enabled and not instance.task_schedule_expr:
            error_message: str = "任务未配置定时表达式，请先在编辑中配置定时后再启动"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance.task_enabled = enabled
        update_fields = ["task_enabled"]
        if updated_user:
            # 启停调度视为任务修改：刷新维护人，调度触发的执行人归因到最后操作者
            instance.updated_user = updated_user
            instance.updated_time = datetime.now()
            update_fields.extend(["updated_user", "updated_time"])
        await instance.save(update_fields=update_fields)
        return instance

    async def select_tasks(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestTaskModel]]:
        """
        根据条件分页查询任务列表；默认根据最后执行时间倒序，未执行过的排在后面。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            # 根据执行时间排序时：有执行记录优先（NULL 置后），再根据时间倒序
            if order == ["-last_execute_time"] or (
                    len(order) == 1 and order[0] == "-last_execute_time"
            ):
                query = self.model.filter(search)
                total = await query.count()
                instances = await (
                    query.annotate(
                        _exec_null=RawSQL("`last_execute_time` IS NULL")
                    )
                    .order_by("_exec_null", "-last_execute_time", "-id")
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                return total, list(instances)
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询任务信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
