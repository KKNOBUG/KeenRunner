# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_task_crud
@DateTime: 2026/1/31 12:42
"""
import re
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.exceptions import FieldError
from tortoise.expressions import Q, RawSQL
from tortoise.timezone import now as tz_now

from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel
from backend.applications.autotest.schemas.autotest_task_schema import AutoTestTaskCreate, AutoTestTaskUpdate
from backend.applications.autotest.services.autotest_scope_guard import (
    assert_cases_readable,
    load_readable_project,
)
from backend.applications.autotest.services.autotest_task_schedule import normalize_schedule
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import AUTOTEST_TASK_TIME_LIMIT, LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    ParameterException,
    NoPermissionException,
)
from backend.enums import AutoTestTaskPeriodicMode, AutoTestTaskStatus
from backend.services import DataScope


def extract_task_involve_envs(cases_execute_config: Any) -> List[str]:
    """
    累积各用例involve_envs并去重，生成task级涉及环境名称列表。

    结果落库到task_involve_envs，供环境删除前反查“该环境是否仍被任务引用”。

    :param cases_execute_config: 任务级用例执行配置字典
    :return: 排序后的环境名称列表；非字典输入返回空列表
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


def extract_steps_execute_envs(cases_execute_config: Any) -> Dict[str, str]:
    """
    累积各用例steps_execute_config的步骤执行环境名称映射(任务级扁平映射)。

    跨用例key重复时后者覆盖前者：step_id格式key全局唯一不受影响，
    仅@@step_name格式key(或历史脏数据)存在极小概率冲突。
    视图层用它回显列表的steps_execute_env，环境删除前用它反查单步骤引用。

    :param cases_execute_config: 任务级用例执行配置字典
    :return: {步骤配置键(step_id|step_id_@@op_index): 环境名称}映射
    """
    if not isinstance(cases_execute_config, dict):
        return {}
    step_envs: Dict[str, str] = {}
    for case_key, case_cfg in cases_execute_config.items():
        # 跳过顶层全局键(env_mode/env_name)，仅累积case_id配置的步骤执行环境
        if case_key in ("env_mode", "env_name"):
            continue
        if not isinstance(case_cfg, dict):
            continue
        steps_cfg = case_cfg.get("steps_execute_config")
        if not isinstance(steps_cfg, dict):
            continue
        for step_key, step_cfg in steps_cfg.items():
            env_name = step_cfg.get("env_name") if isinstance(step_cfg, dict) else None
            if env_name not in (None, ""):
                step_envs[str(step_key)] = str(env_name)
    return step_envs


def resolve_cases_execute_config(task_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    解析用例执行配置。

    :param task_dict: 任务字段字典
    :return: cases_execute_config字典；缺省或非字典类型均返回None
    """
    cases_cfg = task_dict.get("cases_execute_config")
    return cases_cfg if isinstance(cases_cfg, dict) else None


def normalize_task_kwargs(task_kwargs: Any) -> Optional[Dict[str, Any]]:
    """
    规范化task_kwargs：仅承载initial_variables及未知扩展键。

    非字典输入一律降为空字典，避免脏值写进JSONField后执行期取键报错。

    :param task_kwargs: 原始task_kwargs
    :return: 清洗后的字典；输入None时返回None（区别于显式传空对象）
    """
    if task_kwargs is None:
        return None
    if not isinstance(task_kwargs, dict):
        return {}
    return dict(task_kwargs)


class AutoTestTaskCrud(ScaffoldCrud[AutoTestTaskModel, AutoTestTaskCreate, AutoTestTaskUpdate]):
    """
    任务CRUD：任务创建/软删复活、复制、更新、删除、启停调度与执行权抢占。

    唯一键为（task_name, task_project），含软删行判重（复活复用原记录）。
    归属口径：任务以 created_user 为归属人（无独立 owner_user），删除只校验删除范围。
    并发口径：执行入口统一经 claim_execution 原子抢占，避免多端点击/Beat重投重复执行。
    """

    def __init__(self):
        """绑定任务模型，供基类通用CRUD复用。"""
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

    # 运行态失效缓冲：Celery 硬时限 SIGKILL 后状态可能残留 RUNNING，超过「任务硬时限+缓冲」视为僵尸状态
    RUN_STATE_STALE_GRACE_SECONDS: int = 60

    @classmethod
    def stale_run_before(cls) -> datetime:
        """返回运行态失效时间点：早于该时刻的 RUNNING 不再阻塞下一次触发。"""
        # 库内 DatetimeField 读出为带时区值，基准时刻必须同口径，避免 naive/aware 比较报错；
        # 以批量任务自身硬时限为基准：全局 1h 硬时限短于长任务正常耗时，会误判为僵尸而重复执行
        return tz_now() - timedelta(seconds=AUTOTEST_TASK_TIME_LIMIT + cls.RUN_STATE_STALE_GRACE_SECONDS)

    async def is_execution_running(self, task_id: int) -> bool:
        """
        判断任务是否处于有效运行态。

        :param task_id: 任务主键ID
        :return: RUNNING 且未失效返回 True
        """
        task: Optional[AutoTestTaskModel] = await self.model.filter(id=task_id).first()
        if not task or task.last_execute_state != AutoTestTaskStatus.RUNNING:
            return False
        return bool(task.last_execute_time and task.last_execute_time >= self.stale_run_before())

    async def claim_execution(
            self,
            task_id: int,
            execute_user: Optional[str],
            started_at: Optional[datetime] = None
    ) -> bool:
        """
        原子抢占任务执行权：仅当任务不在有效运行态时才能置为 RUNNING。

        多端点击/Beat 重投会在同一条 UPDATE 上互斥，未抢到的消息不再执行，
        避免同一任务并发生成多份报告。

        :param task_id: 任务主键ID
        :param execute_user: 本次执行人
        :param started_at: 本次执行开始时间，缺省取当前时刻
        :return: 抢占成功返回 True
        """
        started_at = started_at or tz_now()
        claimed: int = await self.model.filter(id=task_id).filter(
            Q(last_execute_state__isnull=True)
            | ~Q(last_execute_state=AutoTestTaskStatus.RUNNING)
            | Q(last_execute_time__isnull=True)
            | Q(last_execute_time__lt=self.stale_run_before())
        ).update(
            last_execute_state=AutoTestTaskStatus.RUNNING,
            last_execute_time=started_at,
            last_execute_user=execute_user,
        )
        return claimed > 0

    async def get_by_id(self, task_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestTaskModel]:
        """
        根据主键ID查询任务。

        :param task_id: 任务主键ID，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件（如 state__not=1 排除软删）
        :return: 任务实例或None
        :raises ParameterException: task_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

        :param task_code: 任务标识代码，必填
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件（如 state__not=1 排除软删）
        :return: 任务实例或None
        :raises ParameterException: task_code 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def create_task(self, task_in: AutoTestTaskCreate, scope: DataScope) -> AutoTestTaskModel:
        """
        创建任务；同名软删记录在写权限内恢复并更新，活跃同名报错。

        :param task_in: 任务创建schema
        :param scope: 数据权限上下文，恢复软删任务时要求创建人允许当前用户写入
        :return: 创建后的任务实例
        :raises ParameterException: 定时表达式与时效不匹配（normalize_schedule 校验失败）
        :raises NotFoundException: 所属应用不存在或已软删
        :raises NoPermissionException: 所属应用不可读、挂载用例不可见，或软删任务创建人不可写
        :raises DataAlreadyExistsException: 同应用下同名启用态任务已存在
        :raises DataBaseStorageException: 落库失败（唯一索引冲突或关联数据无效）
        """
        task_name: str = task_in.task_name
        task_project: int = task_in.task_project

        # 业务层验证：应用必须存在且对当前用户可读(B级父资源校验)
        await load_readable_project(scope, task_project)
        # 任务挂载的用例必须对当前用户可见，避免借任务执行触达他人私有脚本
        await assert_cases_readable(scope, task_in.task_case_ids or [])

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
                    periodic=task_dict.get("task_periodic_expr"),
                    schedule=task_dict.get("task_schedule_expr"),
                )
            if task_dict.get("created_user") and not task_dict.get("updated_user"):
                task_dict["updated_user"] = task_dict["created_user"]
            task_dict = self._apply_task_fields(task_dict)
            if existing_task and existing_task.state == 1:
                # 软删恢复不得跨写范围接管他人任务，且不覆盖原创建人
                await scope.load_owners([existing_task.created_user])
                if not scope.can_write(existing_task.created_user):
                    error_message: str = f"新增任务信息失败, 任务[{task_name}]创建人[{existing_task.created_user}]不在当前用户可操作范围内, 无权操作"
                    LOGGER.error(error_message)
                    raise NoPermissionException(message=error_message)
                task_dict.pop("created_user", None)
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
            error_message: str = "新增任务信息失败，相同应用下任务名称可能重复，或关联应用、用例无效，请检查后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [task_name={task_name}, task_project={task_project}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def copy_task(
            self,
            task_id: int,
            scope: DataScope,
            operate_user: Optional[str] = None,
    ) -> AutoTestTaskModel:
        """
        完全复刻任务记录生成新任务：业务配置原样复制，task_code重新生成、
        task_enabled默认停用(避免复制后立即产生双调度)、执行痕迹(last_execute_time/state/user)重置。

        :param task_id: 源任务主键ID
        :param operate_user: 当前操作人，作为新任务的created_user/updated_user
        :param scope: 数据权限上下文，源任务须在当前用户可见范围内
        :return: 复制生成的新任务实例
        :raises NotFoundException: 源任务不存在或已软删
        :raises NoPermissionException: 源任务创建人不在当前用户可见范围
        :raises ParameterException: 复制结果定时表达式校验失败
        :raises DataBaseStorageException: 新任务落库失败
        """
        source = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        await scope.load_owners([source.created_user])
        if not scope.can_read(source.created_user):
            error_message: str = f"复制任务信息失败, 任务[{source.task_name}]创建人[{source.created_user}]不在当前用户可见范围"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
        # 新名称=基础名+微秒时间戳后缀：(task_name, task_project)唯一性由时间戳唯一性保证，无需查重；连续复制时先剥离上一轮时间戳后缀，名称恒为"源基础名_最新时间戳"，不再链式变长；
        suffix: str = datetime.now().strftime("%Y%m%d%H%M%S%f")
        base_name: str = re.compile(r"_\d{20}$").sub("", source.task_name)
        new_task_name: str = f"{base_name[:255 - len(suffix) - 1]}_{suffix}"
        copy_in = AutoTestTaskCreate(
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
        return await self.create_task(task_in=copy_in, scope=scope)

    async def update_task(self, task_in: AutoTestTaskUpdate, scope: DataScope) -> AutoTestTaskModel:
        """
        更新任务，根据task_id或task_code定位并校验(task_name, task_project)唯一。

        定时表达式显式置空时同步停用调度；时效/定时任一变更都会以合并后的值重新
        校验并生成最终 task_schedule_expr，避免只改时效导致存量定时失配。

        :param task_in: 任务更新schema
        :param scope: 数据权限上下文，仅允许修改归属人在当前用户可操作范围内的任务
        :return: 更新后的任务实例
        :raises ParameterException: 定时表达式校验失败
        :raises NotFoundException: 任务或目标应用不存在/已软删
        :raises NoPermissionException: 任务创建人不可写，或目标应用/用例不可见
        :raises DataAlreadyExistsException: 改后与应用内其他任务同名
        :raises DataBaseStorageException: 落库失败（并发删除或索引冲突）
        """
        task_id: Optional[int] = task_in.task_id
        task_code: Optional[str] = task_in.task_code
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)
            task_id = instance.id

        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message: str = f"更新任务信息失败, 任务[{instance.task_name}]创建人[{instance.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        update_dict: Dict[str, Any] = task_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"task_id", "task_code"}
        )
        # 定时表达式允许显式清空：回补显式null以覆盖旧定时；
        # 原有定时被清空时同步停用调度，避免残留“已启动但永不触发”的误导状态
        _schedule_keys = ("task_periodic_expr", "task_schedule_expr")
        self.explicit_restored_null_fields(
            payload=task_in,
            update_dict=update_dict,
            field_names=_schedule_keys
        )
        if any(
                key in update_dict and update_dict[key] is None
                for key in _schedule_keys
        ) and (instance.task_periodic_expr or instance.task_schedule_expr):
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
        # 项目横移需重新校验父资源可读，用例集合变更需校验用例归属
        await load_readable_project(scope, task_project)
        if "task_case_ids" in update_dict:
            await assert_cases_readable(scope, update_dict.get("task_case_ids") or [])
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
            error_message: str = "更新任务信息失败，目标任务不存在或已被删除，请刷新后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [task_id={task_id}, task_code={task_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = "更新任务信息失败，相同应用下任务名称可能重复，或关联应用、用例无效，请检查后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [task_id={task_id}, task_code={task_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def delete_task(
            self,
            scope: DataScope,
            task_id: Optional[int] = None,
            task_code: Optional[str] = None,
    ) -> AutoTestTaskModel:
        """
        软删除任务并关闭调度。

        先软删再单独回写task_enabled=False：两者分开可避免基类软删字段集不含task_enabled。

        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的任务
        :param task_id: 任务主键ID，与task_code二选一
        :param task_code: 任务标识代码，与task_id二选一
        :return: 软删除后的任务实例
        :raises ParameterException: 两个定位参数均未命中
        :raises NotFoundException: 任务不存在或已软删
        :raises NoPermissionException: 任务创建人不在当前用户可删除范围
        """
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)

        await scope.load_owners([instance.created_user])
        if not scope.can_delete(instance.created_user):
            error_message: str = f"删除任务信息失败, 任务[{instance.task_name}]创建人[{instance.created_user}]不在当前用户可删除范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        instance = await self.soft_delete(id=instance.id)
        instance.task_enabled = False
        await instance.save(update_fields=["task_enabled"])
        return instance

    async def set_task_enabled(
            self,
            task_id: int,
            scope: DataScope,
            enabled: bool = True,
            updated_user: Optional[str] = None,
    ) -> AutoTestTaskModel:
        """
        设置任务是否启用调度(仅切换task_enabled，触发依赖task_schedule_expr)。

        :param task_id: 任务主键ID
        :param scope: 数据权限上下文，仅允许启停归属人在当前用户可操作范围内的任务
        :param enabled: 是否启用
        :param updated_user: 操作人员账号(启停调度视为任务修改，刷新维护人；调度触发执行的执行人归因到该人)
        :return: 更新后的任务实例
        :raises NoPermissionException: 任务创建人不在当前用户可操作范围内
        :raises ParameterException: 启用调度时任务尚无定时表达式
        """
        instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message: str = f"启停任务调度失败, 任务[{instance.task_name}]创建人[{instance.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
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
            error_message: str = "查询任务信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
