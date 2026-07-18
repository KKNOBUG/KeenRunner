# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_crud
@DateTime: 2026/1/31 12:42
"""
import traceback
from typing import Optional, Dict, Any, List

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import FieldError
from tortoise.expressions import Q, RawSQL

from backend.applications.aotutest.models.autotest_model import AutoTestApiTaskInfo
from backend.applications.aotutest.schemas.autotest_task_schema import AutoTestApiTaskCreate, AutoTestApiTaskUpdate
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    ParameterException,
)


def extract_related_cases_env_ids(cases_execute_config: Any) -> List[int]:
    """从 cases_execute_config 汇总去重后的环境 ID 列表。

    优先取每个用例的 global_env_id；若步骤配置中带有 env_id 一并纳入。
    """
    if not isinstance(cases_execute_config, dict):
        return []
    env_ids: set = set()
    for case_cfg in cases_execute_config.values():
        if not isinstance(case_cfg, dict):
            continue
        global_env_id = case_cfg.get("global_env_id")
        if global_env_id is not None:
            try:
                env_ids.add(int(global_env_id))
            except (TypeError, ValueError):
                pass
        steps_cfg = case_cfg.get("steps_execute_config") or {}
        if not isinstance(steps_cfg, dict):
            continue
        for step_cfg in steps_cfg.values():
            if not isinstance(step_cfg, dict):
                continue
            step_env_id = step_cfg.get("env_id")
            if step_env_id is not None:
                try:
                    env_ids.add(int(step_env_id))
                except (TypeError, ValueError):
                    pass
    return sorted(env_ids)


def resolve_cases_execute_config(task_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析用例执行配置：顶层权威；兼容读取旧数据中 task_kwargs 嵌套副本。"""
    cases_cfg = task_dict.get("cases_execute_config")
    if isinstance(cases_cfg, dict) and cases_cfg:
        return cases_cfg
    kwargs = task_dict.get("task_kwargs")
    if isinstance(kwargs, dict):
        nested = kwargs.get("cases_execute_config")
        if isinstance(nested, dict):
            return nested
    return cases_cfg if isinstance(cases_cfg, dict) else None


def normalize_task_kwargs(task_kwargs: Any) -> Optional[Dict[str, Any]]:
    """压缩 task_kwargs：保留 case_ids / initial_variables 及未知扩展键，剔除 cases_execute_config。"""
    if task_kwargs is None:
        return None
    if not isinstance(task_kwargs, dict):
        return {}
    cleaned = {k: v for k, v in task_kwargs.items() if k != "cases_execute_config"}
    return cleaned


class AutoTestApiTaskCrud(ScaffoldCrud[AutoTestApiTaskInfo, AutoTestApiTaskCreate, AutoTestApiTaskUpdate]):
    """自动化测试任务的 CRUD 服务，负责任务的增删改查及调度开关。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiTaskInfo。"""
        super().__init__(model=AutoTestApiTaskInfo)

    @staticmethod
    def _dump_enum_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("task_type", "task_periodic_expr", "last_execute_state"):
            if key in data and data[key] is not None and hasattr(data[key], "value"):
                data[key] = data[key].value
        return data

    @staticmethod
    def _apply_related_env_ids(task_dict: Dict[str, Any]) -> Dict[str, Any]:
        """根据 cases_execute_config 汇总 related_cases_env_id，并规范化 task_kwargs。"""
        if "task_kwargs" in task_dict:
            task_dict["task_kwargs"] = normalize_task_kwargs(task_dict.get("task_kwargs"))
        cases_cfg = resolve_cases_execute_config(task_dict)
        if cases_cfg is not None:
            task_dict["cases_execute_config"] = cases_cfg
            task_dict["related_cases_env_id"] = extract_related_cases_env_ids(cases_cfg)
            # 若仅从旧嵌套读取到配置，写回顶层后从 kwargs 去掉嵌套
            kwargs = task_dict.get("task_kwargs")
            if isinstance(kwargs, dict) and "cases_execute_config" in kwargs:
                task_dict["task_kwargs"] = normalize_task_kwargs(kwargs)
        return task_dict

    async def get_by_id(self, task_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiTaskInfo]:
        """
        根据任务主键 ID 查询单条任务

        :param task_id: 任务主键 ID。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 任务实例或 None。
        :raises ParameterException: 当 task_id 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not task_id:
            error_message: str = "查询任务信息失败, 参数(task_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=task_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 任务(id={task_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, task_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiTaskInfo]:
        """
        根据任务标识代码查询单条任务

        :param task_code: 任务标识代码。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 任务实例或 None。
        :raises ParameterException: 当 task_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not task_code:
            error_message: str = "查询任务信息失败, 参数(task_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(task_code=task_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询任务信息失败, 任务(code={task_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_task(self, task_in: AutoTestApiTaskCreate) -> AutoTestApiTaskInfo:
        """创建任务，校验项目存在及 (task_name, task_project) 唯一。

        :param task_in: 任务创建 schema。
        :returns: 创建后的任务实例。
        :raises NotFoundException: 项目不存在时。
        :raises DataAlreadyExistsException: 同项目下任务名已存在时。
        :raises DataBaseStorageException: 违反数据库约束时。
        """
        task_name: str = task_in.task_name
        task_project: int = task_in.task_project

        # 业务层验证：检查应用是否存在
        await AutoTestApiProjectCrud().get_by_id(project_id=task_project, on_error=True, state__not=1)

        # 业务层验证：检查 (task_name, task_project) 唯一
        existing_task = await self.model.filter(task_name=task_name, task_project=task_project, state__not=1).first()
        if existing_task:
            error_message: str = f"任务(task_name={task_name}, task_project={task_project})已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            task_dict: Dict[str, Any] = task_in.model_dump(exclude_none=True, exclude_unset=True)
            task_dict = self._dump_enum_fields(task_dict)
            if task_dict.get("created_user") and not task_dict.get("updated_user"):
                task_dict["updated_user"] = task_dict["created_user"]
            task_dict = self._apply_related_env_ids(task_dict)
            instance = await self.create(task_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增任务信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_task(self, task_in: AutoTestApiTaskUpdate) -> AutoTestApiTaskInfo:
        """更新任务，支持按 task_id 或 task_code 定位，并校验 (task_name, task_project) 唯一。

        :param task_in: 任务更新 schema。
        :returns: 更新后的任务实例。
        :raises NotFoundException: 任务不存在时。
        :raises DataAlreadyExistsException: 同项目下任务名已存在时。
        :raises DataBaseStorageException: 违反约束时。
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
        update_dict = self._dump_enum_fields(update_dict)
        if "task_kwargs" in update_dict:
            update_dict["task_kwargs"] = normalize_task_kwargs(update_dict.get("task_kwargs"))
        merged_for_env = {
            "task_kwargs": update_dict.get("task_kwargs", instance.task_kwargs),
            "cases_execute_config": update_dict.get(
                "cases_execute_config", instance.cases_execute_config
            ),
        }
        cases_cfg = resolve_cases_execute_config(merged_for_env)
        if cases_cfg is not None:
            if "task_kwargs" in update_dict or "cases_execute_config" in update_dict:
                update_dict["cases_execute_config"] = cases_cfg
            update_dict["related_cases_env_id"] = extract_related_cases_env_ids(cases_cfg)
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
            error_message: str = f"更新任务信息失败, 任务(id={task_id}或code={task_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新任务信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_task(self, task_id: Optional[int] = None, task_code: Optional[str] = None) -> AutoTestApiTaskInfo:
        """软删除任务（state=1）并关闭调度（task_enabled=False）。

        :param task_id: 任务主键 ID，与 task_code 二选一。
        :param task_code: 任务标识代码，与 task_id 二选一。
        :returns: 软删除后的任务实例。
        :raises NotFoundException: 任务不存在时。
        """
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)

        instance.state = 1
        instance.task_enabled = False
        await instance.save()
        return instance

    async def set_task_enabled(self, task_id: int, enabled: bool = True) -> AutoTestApiTaskInfo:
        """设置任务是否启动调度（仅切换 task_enabled，触发完全依赖 crontab）。"""
        instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        instance.task_enabled = enabled
        await instance.save(update_fields=["task_enabled"])
        return instance

    async def select_tasks(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """分页查询任务列表。

        默认按最后执行时间倒序，未执行过的任务（last_execute_time 为空）排在后面。

        :param search: Tortoise Q 查询条件。
        :param page: 页码。
        :param page_size: 每页条数。
        :param order: 排序字段列表。
        :returns: 由 (总条数, 当前页记录列表) 组成的元组。
        :raises ParameterException: 查询条件非法导致 FieldError 时。
        """
        try:
            order = order or ["-last_execute_time"]
            # 按执行时间排序时：有执行记录优先（NULL 置后），再按时间倒序
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
