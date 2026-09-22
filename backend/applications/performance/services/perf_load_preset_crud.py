# -*- coding: utf-8 -*-
"""
负载预设CRUD(调度层)。

负载预设只回答「打多狠、什么时候打」, 施压结构全部来自引用的场景; 因此本层唯一的编排校验是
「场景引用是否有效」, 并在保存时以库内值回查覆盖 scene_id/scene_name(不信任前端传来的展示字段)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_load_preset_crud.py
@DateTime: 2026/9/14 11:20
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_load_preset_model import PerfLoadPresetModel
from backend.applications.performance.schemas.perf_load_preset_schema import (
    PerfLoadPresetCreate,
    PerfLoadPresetUpdate,
)
from backend.applications.performance.services.perf_asset_utils import ensure_no_null_for_required_fields
from backend.applications.performance.services.perf_scene_crud import PerfSceneCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import PerfLoadMode, PerfPresetStatus

# stepped 阶梯模式必填字段清单(联动校验用)
STEPPED_REQUIRED_FIELDS = (
    "step_start_users", "step_increment", "step_duration", "step_max_users", "step_sustain_duration",
)


class PerfLoadPresetCrud(ScaffoldCrud[PerfLoadPresetModel, PerfLoadPresetCreate, PerfLoadPresetUpdate]):

    def __init__(self):
        super().__init__(model=PerfLoadPresetModel)

    async def get_by_id(self, preset_id: int, on_error: bool = False, **kwargs) -> Optional[PerfLoadPresetModel]:
        """
        根据主键ID查询负载预设。

        :param preset_id: 负载预设主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 负载预设实例或None
        """
        if not preset_id:
            error_message: str = "查询负载预设信息失败, 参数[preset_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=preset_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询负载预设信息失败, 记录[id={preset_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, preset_code: str, on_error: bool = False, **kwargs) -> Optional[PerfLoadPresetModel]:
        """
        根据负载预设标识代码查询负载预设。

        :param preset_code: 负载预设标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 负载预设实例或None
        """
        if not preset_code:
            error_message: str = "查询负载预设信息失败, 参数[preset_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(preset_code=preset_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询负载预设信息失败, 记录[code={preset_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def bind_scene(scene_code: str) -> Dict[str, Any]:
        """
        按场景标识回查启用场景, 返回三个场景归属字段的落库值。

        场景是负载预设唯一的施压结构来源, 引用失效会在执行期以「空场景 0 请求」形式暴露,
        故保存期必须实查; id/名称以库内值为准, 覆盖前端传入的展示冗余。

        :param scene_code: 压测场景标识代码
        :return: {"scene_id": xx, "scene_code": xx, "scene_name": xx}
        """
        scene = await PerfSceneCrud().get_by_code(scene_code=scene_code, on_error=True, state__not=1)
        return {"scene_id": scene.id, "scene_code": scene.scene_code, "scene_name": scene.scene_name}

    @staticmethod
    def validate_load_params(data: Dict[str, Any]) -> None:
        """
        校验施压参数联动约束(阶梯模式五个字段必填/吞吐模式目标RPS必填)。

        :param data: 负载预设字段字典(创建入参全量或更新入参与存量合并后的全量)
        :return: None
        """
        if data.get("load_mode") == PerfLoadMode.STEPPED:
            missing_fields = [field for field in STEPPED_REQUIRED_FIELDS if not data.get(field)]
            if missing_fields:
                error_message: str = (
                    f"校验负载预设失败, 阶梯模式[{PerfLoadMode.STEPPED.value}]下必填字段缺失: {missing_fields}"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
        if data.get("load_mode") == PerfLoadMode.RPS:
            target_rps = data.get("target_rps")
            if not target_rps or float(target_rps) <= 0:
                error_message = (
                    f"校验负载预设失败, 吞吐模式[{PerfLoadMode.RPS.value}]下目标RPS[target_rps]必填且需大于0"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    @staticmethod
    def ensure_preset_editable(instance: PerfLoadPresetModel, action: str) -> None:
        """
        校验负载预设当前允许执行指定变更动作(执行中/停止中禁止修改与删除)。

        :param instance: 负载预设实例
        :param action: 动作描述(用于错误文案, 如 "更新"/"删除")
        :return: None
        """
        locked_states = (PerfPresetStatus.QUEUED, PerfPresetStatus.RUNNING, PerfPresetStatus.STOPPING)
        if instance.last_execute_state in locked_states:
            error_message: str = (
                f"{action}负载预设信息失败, 记录[id={instance.id}]当前状态为[{instance.last_execute_state.value}], 禁止{action}"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def create_perf_preset(self, preset_in: PerfLoadPresetCreate) -> PerfLoadPresetModel:
        """
        创建负载预设；同应用下同名负载预设已存在(含禁用)则恢复并更新。

        :param preset_in: 负载预设创建schema
        :return: 创建或恢复后的负载预设实例
        """
        preset_project: int = preset_in.preset_project
        # 业务层验证：检查应用是否存在
        from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud
        await AutoTestProjectCrud().get_by_id(project_id=preset_project, on_error=True, state__not=1)

        preset_dict: Dict[str, Any] = preset_in.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        # 场景归属字段统一由 crud 回查覆盖(前端传什么都不信), 保证负载预设表 scene 三字段与场景实体一致
        preset_dict.update(await self.bind_scene(preset_in.scene_code))
        # 新建负载预设初始执行态显式落"仅配置未执行"(对齐 PerfPresetStatus 枚举文档), 避免该列落 NULL 产生双初始态漂移
        preset_dict.setdefault("last_execute_state", PerfPresetStatus.IDLE)
        self.validate_load_params(preset_dict)

        # 业务层验证：同应用下相同名称仅允许一条记录（含已禁用，命中则恢复启用）
        existing_preset = await self.model.filter(preset_project=preset_project, preset_name=preset_in.preset_name).first()
        if not existing_preset:
            try:
                instance: PerfLoadPresetModel = await self.create(obj_in=preset_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增负载预设信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            preset_dict["state"] = 0
            instance: PerfLoadPresetModel = await self.update(id=existing_preset.id, obj_in=preset_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)负载预设信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_perf_preset(self, preset_in: PerfLoadPresetUpdate) -> PerfLoadPresetModel:
        """
        更新负载预设，根据preset_id或preset_code定位；执行相关状态下禁止更新。

        不做 exclude_none: 阶梯模式改回固定并发要清掉五个阶梯字段、换环境后清掉旧环境名都是
        「提交 null 即清空」的合法意图, 保留旧值会让下一次切回 stepped 时用过时参数静默施压。

        :param preset_in: 负载预设更新schema
        :return: 更新后的负载预设实例
        """
        preset_id: Optional[int] = preset_in.preset_id
        preset_code: Optional[str] = preset_in.preset_code
        if preset_id:
            instance = await self.get_by_id(preset_id=preset_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(preset_code=preset_code, on_error=True, state__not=1)
            preset_id = instance.id
        self.ensure_preset_editable(instance=instance, action="更新")

        update_dict: Dict[str, Any] = preset_in.model_dump(
            mode="json",
            exclude_unset=True,
            exclude={"preset_id", "preset_code"}
        )
        # 按键存在而非值非空判定: 场景是负载预设唯一的施压结构来源, 置空必须在此拦截而不是静默保留旧场景
        if "scene_code" in update_dict:
            update_dict.update(await self.bind_scene(preset_in.scene_code))
        # 合并存量后统一校验(stepped/rps联动字段可分次提交), 避免局部更新绕过完整性约束
        merged_dict: Dict[str, Any] = {
            field: update_dict.get(field, getattr(instance, field))
            for field in ("load_mode", *STEPPED_REQUIRED_FIELDS, "target_rps")
        }
        self.validate_load_params(merged_dict)

        # 名称/应用变更时校验(preset_name, preset_project)唯一
        if "preset_name" in update_dict or "preset_project" in update_dict:
            preset_name: str = update_dict.get("preset_name", instance.preset_name)
            preset_project: int = update_dict.get("preset_project", instance.preset_project)
            existing_preset = await self.model.filter(
                preset_name=preset_name,
                preset_project=preset_project,
                state__not=1
            ).exclude(id=preset_id).first()
            if existing_preset:
                error_message: str = f"负载预设[preset_name={preset_name}, preset_project={preset_project}]已存在"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        # 非空列不接受 null(preset_name/load_mode/concurrent_users 等): 在场景回查覆盖后的写入口拦截,
        # 既不会误拒前端占位提交的 scene_id=null(已由 bind_scene 覆盖为真值), 也不拖到 DB 约束错误
        ensure_no_null_for_required_fields(PerfLoadPresetModel, update_dict, "更新负载预设")
        try:
            instance = await self.update(id=preset_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新负载预设信息失败, 记录[id={preset_id}]或[code={preset_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新负载预设信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_perf_preset(self, preset_id: Optional[int] = None, preset_code: Optional[str] = None) -> PerfLoadPresetModel:
        """
        软删除负载预设；执行相关状态下禁止删除。

        :param preset_id: 负载预设主键ID，与preset_code二选一
        :param preset_code: 负载预设标识代码，与preset_id二选一
        :return: 软删除后的负载预设实例
        """
        if not preset_id and not preset_code:
            error_message: str = "删除负载预设信息失败, 参数[preset_id]或[preset_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if preset_id:
            instance = await self.get_by_id(preset_id=preset_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(preset_code=preset_code, on_error=True, state__not=1)
        self.ensure_preset_editable(instance=instance, action="删除")

        return await self.soft_delete(id=instance.id)

    async def select_perf_presets(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[PerfLoadPresetModel]]:
        """
        根据条件分页查询负载预设列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询负载预设信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

