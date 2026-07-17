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
    """解析任务中的用例执行配置：顶层字段优先，否则回退到 task_kwargs。"""
    cases_cfg = task_dict.get("cases_execute_config")
    if isinstance(cases_cfg, dict) and cases_cfg:
        return cases_cfg
    kwargs = task_dict.get("task_kwargs")
    if isinstance(kwargs, dict):
        nested = kwargs.get("cases_execute_config")
        if isinstance(nested, dict):
            return nested
    return cases_cfg if isinstance(cases_cfg, dict) else None


class AutoTestApiTaskCrud(ScaffoldCrud[AutoTestApiTaskInfo, AutoTestApiTaskCreate, AutoTestApiTaskUpdate]):
    """自动化测试任务的 CRUD 服务，负责任务的增删改查及调度开关。"""

    def __init__(self):
        """初始化 CRUD，绑定模型 AutoTestApiTaskInfo。"""
        super().__init__(model=AutoTestApiTaskInfo)

    @staticmethod
    def _apply_related_env_ids(task_dict: Dict[str, Any]) -> Dict[str, Any]:
        """根据 cases_execute_config / task_kwargs 同步汇总 related_cases_env_id。"""
        cases_cfg = resolve_cases_execute_config(task_dict)
        if cases_cfg is not None:
            task_dict["cases_execute_config"] = cases_cfg
            task_dict["related_cases_env_id"] = extract_related_cases_env_ids(cases_cfg)
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
            if "task_scheduler" in task_dict and task_dict["task_scheduler"] is not None:
                task_dict["task_scheduler"] = task_dict["task_scheduler"].value
            if "last_execute_state" in task_dict and task_dict["last_execute_state"] is not None:
                task_dict["last_execute_state"] = task_dict["last_execute_state"].value
            # 新增时同步写入更新人，便于列表「更新人员」展示
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
        if "task_scheduler" in update_dict and update_dict["task_scheduler"] is not None:
            update_dict["task_scheduler"] = update_dict["task_scheduler"].value
        if "last_execute_state" in update_dict and update_dict["last_execute_state"] is not None:
            update_dict["last_execute_state"] = update_dict["last_execute_state"].value
        # 汇总涉及环境：优先用本次提交的配置，否则回退到库中已有配置
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
        """设置任务是否启动调度。

        启用时：若为「执行 1 次」落库的 datetime 模式且仍保留 crontab，
        则按 crontab 重算下一次触发时间，避免旧 target 已被 last_execute_time 消费后永远不再触发。
        """
        from datetime import datetime

        instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        instance.task_enabled = enabled
        update_fields = ["task_enabled"]

        if enabled:
            scheduler = getattr(instance.task_scheduler, "value", None) or instance.task_scheduler
            scheduler_str = str(scheduler or "").strip().lower()
            crontab = (instance.task_crontabs_expr or "").strip()
            if scheduler_str == "datetime" and crontab:
                try:
                    from croniter import croniter
                    now = datetime.now()
                    next_dt = croniter(crontab, now).get_next(datetime)
                    instance.task_datetime_expr = next_dt.strftime("%Y-%m-%d %H:%M:%S")
                    update_fields.append("task_datetime_expr")
                    LOGGER.info(
                        f"启动任务时刷新一次性触发时间: task_id={task_id}, "
                        f"crontab={crontab}, next={instance.task_datetime_expr}"
                    )
                except Exception as e:
                    LOGGER.warning(
                        f"启动任务时刷新 datetime 触发点失败: task_id={task_id}, error={e}"
                    )

        await instance.save(update_fields=update_fields)
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
