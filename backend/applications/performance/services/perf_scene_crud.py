# -*- coding: utf-8 -*-
"""
压测场景CRUD与编排校验。

场景是「引用组合」而不是「拷贝快照」: 保存期只做引用有效性与口径自洽校验并把展示字段回查覆盖,
完整解析快照在施压管线里生成并落进报告(报告不回查场景)。因此本层必须保证存进来的引用是真的,
否则问题会推迟到执行期以「0请求数」或「假压测」的形式暴露。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_scene_crud.py
@DateTime: 2026/9/15 16:40
"""
import traceback
from typing import Any, Dict, List, Optional, Tuple

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_dataset_model import PerfDatasetModel
from backend.applications.performance.models.perf_report_model import PerfReportModel
from backend.applications.performance.models.perf_scene_model import PerfSceneModel
from backend.applications.performance.models.perf_load_preset_model import PerfLoadPresetModel
from backend.applications.performance.schemas.perf_scene_schema import (
    PerfSceneCreate,
    PerfSceneItem,
    PerfScenePinBaseline,
    PerfScenePrecheck,
    PerfSceneUpdate,
)
from backend.applications.performance.schemas.perf_api_schema import PerfApiDebug
from backend.applications.performance.services.perf_asset_utils import build_copy_name
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import PerfReportStatus

# 复制场景时平移的编排字段(不含标识与脚手架字段: scene_code 重新生成, 名称走副本命名)
SCENE_COPY_FIELDS = (
    "scene_project", "scene_desc", "run_mode", "scene_items", "journey", "perf_targets",
    "baseline_report_id", "baseline_report_code", "baseline_policy",
    "warmup_seconds", "error_rate_threshold", "assert_mode", "sample_ratio", "inject_perf_tag",
)


class PerfSceneCrud(ScaffoldCrud[PerfSceneModel, PerfSceneCreate, PerfSceneUpdate]):

    def __init__(self):
        super().__init__(model=PerfSceneModel)

    async def get_by_id(self, scene_id: int, on_error: bool = False, **kwargs) -> Optional[PerfSceneModel]:
        """
        根据主键ID查询压测场景。

        :param scene_id: 场景主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 场景实例或None
        """
        if not scene_id:
            error_message: str = "查询压测场景信息失败, 参数[scene_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=scene_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询压测场景信息失败, 记录[id={scene_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, scene_code: str, on_error: bool = False, **kwargs) -> Optional[PerfSceneModel]:
        """
        根据场景标识代码查询压测场景。

        :param scene_code: 场景标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 场景实例或None
        """
        if not scene_code:
            error_message: str = "查询压测场景信息失败, 参数[scene_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(scene_code=scene_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询压测场景信息失败, 记录[code={scene_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def collect_asset_references(field: str) -> Dict[str, List[str]]:
        """
        扫描启用场景, 建立「场景引用的资产标识 → 引用它的场景清单」索引。

        场景对接口/数据集是 JSON 容器引用(无外键), 只能按 scene_items 内容在业务层判定;
        不走 SQL 模糊匹配是因为其结果依赖 JSON 序列化分隔符, 格式一变即假阴性(删除保护失效
        的代价远大于一次全量扫描)。仅取必要列, 删除是低频写操作。

        :param field: scene_items 元素内的引用键(api_code / ds_code)
        :return: {资产标识: ["场景名称(code=xxx)", ...]}
        """
        index: Dict[str, List[str]] = {}
        async for scene in PerfSceneModel.filter(state__not=1).only("scene_code", "scene_name", "scene_items"):
            for item in (scene.scene_items or []):
                if not isinstance(item, dict):
                    continue
                ref_value: str = str(item.get(field) or "")
                if ref_value:
                    index.setdefault(ref_value, []).append(f"{scene.scene_name}(code={scene.scene_code})")
        return index

    @staticmethod
    async def list_scene_codes_referencing_api(api_code: str) -> List[str]:
        """
        按接口标识检索引用它的场景code列表(列表页按引用关系过滤)。

        与 collect_asset_references 同口径的容器扫描: 场景对接口是 JSON 容器引用(无外键),
        只能按 scene_items 内容在业务层判定; 场景表规模小且该过滤是低频检索, 全量扫描可接受。

        :param api_code: 压测接口标识代码
        :return: 引用该接口的场景code列表(保持表序)
        """
        scene_codes: List[str] = []
        async for scene in PerfSceneModel.filter(state__not=1).only("scene_code", "scene_items"):
            if any(
                isinstance(item, dict) and str(item.get("api_code") or "") == api_code
                for item in (scene.scene_items or [])
            ):
                scene_codes.append(scene.scene_code)
        return scene_codes

    @staticmethod
    async def validate_and_fill_items(items: List[PerfSceneItem]) -> List[Dict[str, Any]]:
        """
        校验接口项引用的资产有效性, 并回查覆盖展示字段。

        规则: 接口必须存在且启用; 数据集必须存在且启用; 声明了参数列契约的接口, 其契约列必须
        全部包含在绑定数据集的列里(缺列会让占位符静默渲染成空串, 压出的是假请求);
        api_id/api_name/ds_name 一律以库内值覆盖, 不信任前端传来的展示字段。

        :param items: 场景接口项schema列表
        :return: 可直接落库的接口项字典列表
        """
        api_codes: List[str] = sorted({item.api_code for item in items})
        ds_codes: List[str] = sorted({item.ds_code for item in items if item.ds_code})

        api_map: Dict[str, PerfApiModel] = {
            obj.api_code: obj for obj in await PerfApiModel.filter(api_code__in=api_codes, state__not=1)
        }
        missing_apis: List[str] = [code for code in api_codes if code not in api_map]
        if missing_apis:
            error_message: str = f"校验压测场景失败, 以下压测接口不存在或已禁用: {missing_apis}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        ds_map: Dict[str, PerfDatasetModel] = {
            obj.ds_code: obj for obj in await PerfDatasetModel.filter(ds_code__in=ds_codes, state__not=1)
        }
        missing_ds: List[str] = [code for code in ds_codes if code not in ds_map]
        if missing_ds:
            error_message: str = f"校验压测场景失败, 以下数据集不存在或已禁用: {missing_ds}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        dumped: List[Dict[str, Any]] = []
        for item in items:
            api: PerfApiModel = api_map[item.api_code]
            item_dict: Dict[str, Any] = item.model_dump(mode="json", exclude_none=True)
            item_dict["api_id"] = api.id
            item_dict["api_name"] = api.api_name
            if item.ds_code:
                dataset: PerfDatasetModel = ds_map[item.ds_code]
                item_dict["ds_name"] = dataset.ds_name
            else:
                item_dict.pop("ds_name", None)
            dumped.append(item_dict)
        return dumped

    async def create_perf_scene(self, scene_in: PerfSceneCreate) -> PerfSceneModel:
        """
        新增压测场景；同应用下同名场景已存在(含禁用)则恢复并覆盖。

        :param scene_in: 场景创建schema
        :return: 创建或恢复后的场景实例
        """
        await self._ensure_project_exists(project_id=scene_in.scene_project)
        scene_dict: Dict[str, Any] = scene_in.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        scene_dict["scene_items"] = await self.validate_and_fill_items(scene_in.scene_items)
        if scene_in.journey is not None:
            scene_dict["journey"] = scene_in.journey.model_dump(mode="json", exclude_none=True)
        if scene_in.perf_targets is not None:
            scene_dict["perf_targets"] = [
                target.model_dump(mode="json", exclude_none=True) for target in scene_in.perf_targets
            ]
        if scene_in.baseline_policy is not None:
            scene_dict["baseline_policy"] = scene_in.baseline_policy.model_dump(mode="json", exclude_none=True)
        scene_dict.update(await self.resolve_baseline(baseline_report_code=scene_in.baseline_report_code))

        existing = await self.model.filter(
            scene_project=scene_in.scene_project, scene_name=scene_in.scene_name
        ).first()
        if not existing:
            try:
                return await self.create(obj_in=scene_dict)
            except IntegrityError as e:
                error_message: str = f"新增压测场景信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            scene_dict["state"] = 0
            return await self.update(id=existing.id, obj_in=scene_dict)
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)压测场景信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_perf_scene(self, scene_in: PerfSceneUpdate) -> PerfSceneModel:
        """
        更新压测场景(与场景编辑交互一致: 整编排覆盖保存)。

        不做 exclude_none: 取消基线/去掉链路定义/清空SLA目标都是「提交 null 即清空」的合法意图,
        丢掉 null 会让旧值静默残留在库里, 用户看到的表单与落库结构从此分叉。

        :param scene_in: 场景更新schema
        :return: 更新后的场景实例
        """
        scene_id: Optional[int] = scene_in.scene_id
        scene_code: Optional[str] = scene_in.scene_code
        if scene_id:
            instance = await self.get_by_id(scene_id=scene_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(scene_code=scene_code, on_error=True, state__not=1)
            scene_id = instance.id

        update_dict: Dict[str, Any] = scene_in.model_dump(
            mode="json", exclude_unset=True, exclude={"scene_id", "scene_code"}
        )
        update_dict["scene_items"] = await self.validate_and_fill_items(scene_in.scene_items)
        # 容器字段重转一次并只剔 null: 父层 exclude_unset 会递归丢掉嵌套项的默认值(false/0 一并丢),
        # 重转保证新建与更新落库的结构一致, 引擎按固定键读取不会因默认值缺失而歧义
        if scene_in.journey is not None:
            update_dict["journey"] = scene_in.journey.model_dump(mode="json", exclude_none=True)
        if scene_in.perf_targets is not None:
            update_dict["perf_targets"] = [
                target.model_dump(mode="json", exclude_none=True) for target in scene_in.perf_targets
            ]
        if scene_in.baseline_policy is not None:
            update_dict["baseline_policy"] = scene_in.baseline_policy.model_dump(mode="json", exclude_none=True)
        if "baseline_report_code" in update_dict:
            update_dict.update(await self.resolve_baseline(baseline_report_code=scene_in.baseline_report_code))

        if "scene_name" in update_dict or "scene_project" in update_dict:
            scene_name: str = update_dict.get("scene_name", instance.scene_name)
            scene_project: int = update_dict.get("scene_project", instance.scene_project)
            existing = await self.model.filter(
                scene_name=scene_name, scene_project=scene_project, state__not=1
            ).exclude(id=scene_id).first()
            if existing:
                error_message: str = f"压测场景[scene_name={scene_name}, scene_project={scene_project}]已存在"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            return await self.update(id=scene_id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = f"更新压测场景信息失败, 记录[id={scene_id}]或[code={scene_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新压测场景信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def copy_perf_scene(self, *, scene_id: Optional[int] = None, scene_code: Optional[str] = None,
                              created_user: Optional[str] = None) -> PerfSceneModel:
        """
        复制压测场景为同应用下的新场景(编排全量平移, 名称追加副本后缀)。

        复制而不新建: 同一编排改判定/改权重/改并发是压测里最高频的劳动, 复用接口引用关系不变。
        基线不随复制继承(新场景的第一份记录还没跑出来, 沿用旧基线会得出错的退化结论), 置空由用户重钉。

        :param scene_id: 源场景ID(与scene_code二选一)
        :param scene_code: 源场景标识(与scene_id二选一)
        :param created_user: 复制操作人
        :return: 新建的场景实例
        """
        if scene_id:
            source = await self.get_by_id(scene_id=scene_id, on_error=True, state__not=1)
        else:
            source = await self.get_by_code(scene_code=scene_code, on_error=True, state__not=1)

        copy_dict: Dict[str, Any] = await source.to_dict(include_fields=list(SCENE_COPY_FIELDS))
        copy_dict.pop("id", None)
        copy_dict["scene_name"] = build_copy_name(source.scene_name)
        copy_dict["baseline_report_id"] = None
        copy_dict["baseline_report_code"] = None
        copy_dict["created_user"] = created_user or source.created_user
        try:
            return await self.create(obj_in=copy_dict)
        except IntegrityError as e:
            error_message: str = f"复制压测场景信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def pin_baseline(self, pin_in: PerfScenePinBaseline, updated_user: Optional[str] = None) -> PerfSceneModel:
        """
        钉选/取消钉选场景基线报告(执行时随报告创建固化为对比对象)。

        基线必须是同场景的completed报告: 跨场景与失败报告都没有「同口径稳态结论」
        可比, 钉上只会产出不可比噪声。取消钉选传空report_code, 两个定位字段一并清空。

        :param pin_in: 钉选入参(场景定位 + 基线报告标识; report_code留空=取消钉选)
        :param updated_user: 操作人
        :return: 更新后的场景实例
        """
        if pin_in.scene_id:
            scene = await self.get_by_id(scene_id=pin_in.scene_id, on_error=True, state__not=1)
        else:
            scene = await self.get_by_code(scene_code=pin_in.scene_code, on_error=True, state__not=1)

        baseline_code: str = (pin_in.report_code or "").strip()
        fields: Dict[str, Any] = {"baseline_report_id": None, "baseline_report_code": None}
        if baseline_code:
            report = await PerfReportModel.filter(report_code=baseline_code, state__not=1).first()
            if report is None:
                error_message: str = f"钉选基线失败, 报告[report_code={baseline_code}]不存在"
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)
            if report.status != PerfReportStatus.COMPLETED:
                error_message = f"钉选基线失败, 报告[{baseline_code}]未处于完成状态, 无稳定结论可作为基线"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            if report.scene_code != scene.scene_code:
                error_message = (
                    f"钉选基线失败, 报告[{baseline_code}]属于场景[{report.scene_code}], "
                    f"与当前场景[{scene.scene_code}]不一致, 只能钉选同场景报告"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            fields = {"baseline_report_id": report.id, "baseline_report_code": report.report_code}
        fields["updated_user"] = updated_user
        await PerfSceneModel.filter(id=scene.id).update(**fields)
        return await self.get_by_id(scene_id=scene.id, on_error=True)

    async def precheck_scene(self, precheck_in: PerfScenePrecheck) -> Dict[str, Any]:
        """
        场景预检: 对场景内启用接口逐个发1次真实请求, 回显连通性与业务结论。

        复用单接口调试链(debug_api): 请求构造/环境解析/占位符渲染口径与施压完全一致,
        结论同步回写接口的 debug_state —— 预检通过即满足施压闸门「引用接口均有调试
        通过结论」的要求。连通=传输层无异常; 业务通过=调试结论 success(状态码<400
        且断言全过), 两列分开回显便于区分「网络不通」与「业务不达标」。

        :param precheck_in: 预检入参(场景定位 + 可选施压环境)
        :return: 预检汇总与逐接口结果, 形如:
            {"scene_id": 1, "scene_code": "xx", "scene_name": "xx",
             "total": 3, "enabled_total": 3, "connected_count": 3, "success_count": 2,
             "items": [{"seq": 1, "api_id": 1, "api_code": "xx", "api_name": "xx",
                        "role": "measured", "enabled": true, "skipped": false,
                        "connected": true, "success": true, "status_code": 200,
                        "elapsed_ms": 45.2, "request_url": "http://...", "error": null}]}
        """
        if precheck_in.scene_id:
            scene = await self.get_by_id(scene_id=precheck_in.scene_id, on_error=True, state__not=1)
        else:
            scene = await self.get_by_code(scene_code=precheck_in.scene_code, on_error=True, state__not=1)

        # 延迟导入: 存量 api_crud→scene_crud 与 api_service→api_crud 已互指,
        # 模块级再引 api_service 会闭合成环, 故仅在预检链路内导入
        from backend.applications.performance.services.perf_api_service import PerfApiService

        items: List[Dict[str, Any]] = list(scene.scene_items or [])
        if not items:
            error_message: str = f"预检压测场景失败, 场景[{scene.scene_name}]没有任何接口项"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 批量预取引用接口存在性: 缺失项直接记错误, 不进调试链(避免逐条空查询)
        api_codes: List[str] = [item.get("api_code") for item in items if item.get("api_code")]
        api_map: Dict[str, PerfApiModel] = {
            obj.api_code: obj for obj in await PerfApiModel.filter(api_code__in=api_codes, state__not=1)
        }

        results: List[Dict[str, Any]] = []
        connected_count: int = 0
        success_count: int = 0
        for item in items:
            row: Dict[str, Any] = {
                "seq": item.get("seq"), "api_code": item.get("api_code"),
                "api_name": item.get("api_name"), "role": item.get("role"),
                "enabled": bool(item.get("enabled", True)), "skipped": False,
                "connected": False, "success": False, "status_code": None,
                "elapsed_ms": None, "request_url": None, "error": None,
            }
            if not row["enabled"]:
                row["skipped"] = True
                row["error"] = "已停用, 未参与预检"
                results.append(row)
                continue
            api: Optional[PerfApiModel] = api_map.get(item.get("api_code"))
            if api is None:
                row["skipped"] = True
                row["error"] = f"引用压测接口[{item.get('api_code')}]不存在或已禁用"
                results.append(row)
                continue
            row["api_id"] = api.id
            row["api_name"] = api.api_name
            debug_result: Dict[str, Any] = await PerfApiService.debug_api(PerfApiDebug(
                api_id=api.id,
                env_name=precheck_in.env_name,
                env_config_name=precheck_in.env_config_name,
            ))
            row["connected"] = not debug_result.get("transport_error")
            row["success"] = bool(debug_result.get("success"))
            row["status_code"] = debug_result.get("status_code")
            row["elapsed_ms"] = debug_result.get("elapsed_ms")
            row["request_url"] = debug_result.get("request_url")
            row["error"] = debug_result.get("transport_error") or None
            connected_count += int(row["connected"])
            success_count += int(row["success"])
            results.append(row)

        enabled_total: int = sum(1 for row in results if row["enabled"])
        return {
            "scene_id": scene.id, "scene_code": scene.scene_code, "scene_name": scene.scene_name,
            "total": len(items), "enabled_total": enabled_total,
            "connected_count": connected_count, "success_count": success_count,
            "items": results,
        }

    async def delete_perf_scene(self, scene_id: Optional[int] = None, scene_code: Optional[str] = None) -> PerfSceneModel:
        """
        软删除压测场景；被负载预设引用时禁止删除。

        :param scene_id: 场景主键ID，与scene_code二选一
        :param scene_code: 场景标识代码，与scene_id二选一
        :return: 软删除后的场景实例
        """
        if not scene_id and not scene_code:
            error_message: str = "删除压测场景信息失败, 参数[scene_id]或[scene_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if scene_id:
            instance = await self.get_by_id(scene_id=scene_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(scene_code=scene_code, on_error=True, state__not=1)
        await self.ensure_scenes_deletable(scene_codes=[instance.scene_code])
        return await self.soft_delete(id=instance.id)

    @staticmethod
    async def ensure_scenes_deletable(scene_codes: List[str]) -> None:
        """
        删除保护: 被负载预设引用的场景禁止删除(预设列为真实字段, 走索引精确查, 无需扫描容器)。

        :param scene_codes: 待删除的场景标识列表
        :return: None
        """
        referencing: List[PerfLoadPresetModel] = await PerfLoadPresetModel.filter(
            scene_code__in=scene_codes, state__not=1
        ).only("preset_code", "preset_name", "scene_code")
        if not referencing:
            return
        grouped: Dict[str, List[str]] = {}
        for preset in referencing:
            grouped.setdefault(preset.scene_code, []).append(f"{preset.preset_name}(code={preset.preset_code})")
        error_message: str = f"删除压测场景信息失败, 以下场景仍被负载预设引用, 请先删除或改绑预设: {grouped}"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)

    async def select_perf_scenes(self, search: Q, page: int, page_size: int,
                                 order: List[str]) -> Tuple[int, List[PerfSceneModel]]:
        """
        根据条件分页查询压测场景列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询压测场景信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message)

    @staticmethod
    async def resolve_baseline(baseline_report_code: Optional[str]) -> Dict[str, Any]:
        """
        解析基线报告, 返回两个基线归属字段的落库值。

        基线错配会让退化判定整段静默失效, 故保存期实查报告是否存在; id 与 code 必须同时落库:
        基线展示靠 code, 退化对比取数靠 id, 只存一个就会在报告页长出一个回查。

        :param baseline_report_code: 基线报告标识代码, 空表示不钉基线
        :return: {"baseline_report_id": xx, "baseline_report_code": xx}
        """
        clean_code: Optional[str] = str(baseline_report_code or "").strip() or None
        if not clean_code:
            return {"baseline_report_id": None, "baseline_report_code": None}

        from backend.applications.performance.models.perf_report_model import PerfReportModel

        report = await PerfReportModel.filter(report_code=clean_code, state__not=1).first()
        if not report:
            error_message: str = f"校验压测场景失败, 基线报告[code={clean_code}]不存在或已删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return {"baseline_report_id": report.id, "baseline_report_code": report.report_code}

    @staticmethod
    async def _ensure_project_exists(project_id: int) -> None:
        """
        校验应用主数据存在(与负载预设同一口径, 业务层验证不设外键)。

        :param project_id: 应用ID
        :return: None
        """
        from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud

        await AutoTestProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)

