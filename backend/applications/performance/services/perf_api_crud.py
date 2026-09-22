# -*- coding: utf-8 -*-
"""
压测接口资产CRUD。

写操作收敛在本入口: 新增/更新/复制/删除/调试结论回写全部经 PerfApiCrud, 视图层不直写模型。
删除保护与版本自增是本层两条硬约束: 被场景引用的资产不可删(否则历史场景执行期才炸),
定义变更必须升版本并作废调试结论(否则 debug_state 闸门给假绿灯)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_api_crud.py
@DateTime: 2026/9/15 16:20
"""
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.schemas.perf_api_schema import (
    PerfApiCreate,
    PerfApiUpdate,
)
from backend.applications.performance.services.perf_asset_utils import (
    build_copy_name,
    canonical_value,
    ensure_no_null_for_required_fields,
    model_field_literal,
)
from backend.applications.performance.services.perf_scene_crud import PerfSceneCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import PerfDebugState

# 定义类字段: 任一字段变更即视为接口定义变化, 需自增版本号并作废调试结论
API_DEFINITION_FIELDS = (
    "step_type", "request_url", "request_port", "request_method", "request_header", "request_params",
    "request_form_data", "request_form_urlencoded", "request_form_file", "request_text", "request_body",
    "request_args_type", "request_project_id", "request_config_name",
    "defined_variables", "extract_variables", "assert_validators",
)
# 可从功能步骤平移至压测接口的定义字段(请求块与 autotest 步骤同形, 全量平移)
IMPORTABLE_API_FIELDS = API_DEFINITION_FIELDS
# 元素是 pydantic 模型的容器字段: 必须从解析后的对象重转, 不能依赖父层 dump(会递归丢默认值键)
API_NESTED_CONTAINER_FIELDS = ("defined_variables", "extract_variables", "assert_validators")


class PerfApiCrud(ScaffoldCrud[PerfApiModel, PerfApiCreate, PerfApiUpdate]):

    def __init__(self):
        super().__init__(model=PerfApiModel)

    async def get_by_id(self, api_id: int, on_error: bool = False, **kwargs) -> Optional[PerfApiModel]:
        """
        根据主键ID查询压测接口。

        :param api_id: 接口主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 接口实例或None
        """
        if not api_id:
            error_message: str = "查询压测接口信息失败, 参数[api_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=api_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询压测接口信息失败, 记录[id={api_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, api_code: str, on_error: bool = False, **kwargs) -> Optional[PerfApiModel]:
        """
        根据接口标识代码查询压测接口。

        :param api_code: 接口标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 接口实例或None
        """
        if not api_code:
            error_message: str = "查询压测接口信息失败, 参数[api_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(api_code=api_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询压测接口信息失败, 记录[code={api_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    def dump_nested_containers(schema_in: BaseModel) -> Dict[str, Any]:
        """
        嵌套模型容器字段 → 纯JSON字典(仅包含本次已提交的字段)。

        父层 model_dump(exclude_unset) 会递归丢弃嵌套项未显式提交的默认值键, 同一份规则在新增
        与更新两条路径上会落成两种结构; 从解析后的模型重转一次可固定落库形态, 也使版本比较
        不受「客户端恰好传了哪几个键」影响。

        :param schema_in: 接口新增或更新schema
        :return: 容器字段名到纯JSON值的字典
        """
        dumped: Dict[str, Any] = {}
        for field in API_NESTED_CONTAINER_FIELDS:
            items = getattr(schema_in, field, None)
            if items is not None:
                dumped[field] = [item.model_dump(mode="json", exclude_none=True) for item in items]
        return dumped

    @classmethod
    def dump_definition(cls, api_in: PerfApiCreate, *, with_source: bool = True) -> Dict[str, Any]:
        """
        新增schema → 落库字典(纯JSON、剔除未提交字段与空值)。

        :param api_in: 接口创建schema
        :param with_source: 是否写入录入溯源字段(复制场景需丢弃)
        :return: 可直接写入模型的字典
        """
        api_dict: Dict[str, Any] = api_in.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        if not with_source:
            api_dict.pop("api_source", None)
            api_dict.pop("source_case_code", None)
            api_dict.pop("source_step_code", None)
        api_dict.update(cls.dump_nested_containers(api_in))
        return api_dict

    @classmethod
    async def ensure_apis_deletable(cls, api_codes: List[str], action: str) -> None:
        """
        删除保护: 仍被启用场景引用的压测接口禁止删除(一次场景扫描覆盖整批, 避免逐条重复遍历)。

        :param api_codes: 待删除的接口标识列表
        :param action: 动作描述(用于错误文案)
        :return: None
        """
        index: Dict[str, List[str]] = await PerfSceneCrud.collect_asset_references("api_code")
        for api_code in api_codes:
            referenced: List[str] = index.get(api_code) or []
            if referenced:
                error_message: str = (
                    f"{action}压测接口信息失败, 接口[code={api_code}]仍被以下场景引用, 请先在场景中移除: {referenced[:10]}"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    async def create_perf_api(self, api_in: PerfApiCreate) -> PerfApiModel:
        """
        新增压测接口；同名接口已存在(含禁用)则恢复并覆盖(接口名称全局唯一)。

        :param api_in: 接口创建schema
        :return: 创建或恢复后的接口实例
        """
        if api_in.request_project_id:
            await self._ensure_project_exists(project_id=api_in.request_project_id)

        api_dict: Dict[str, Any] = self.dump_definition(api_in)
        # 新建接口初始调试态显式落"从未调试", 避免该列NULL与never两种空态并存
        api_dict.setdefault("debug_state", PerfDebugState.NEVER)
        api_dict.setdefault("api_version", 1)

        # 接口名称全局唯一(对齐 AutoTestStepModel: 无 api_project)
        existing = await self.model.filter(api_name=api_in.api_name).first()
        if not existing:
            try:
                return await self.create(obj_in=api_dict)
            except IntegrityError as e:
                error_message: str = f"新增压测接口信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            api_dict["state"] = 0
            return await self.update(id=existing.id, obj_in=api_dict)
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)压测接口信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_perf_api(self, api_in: PerfApiUpdate) -> PerfApiModel:
        """
        更新压测接口(按 id 或 code 定位)；定义变更时自增版本号并作废调试结论。

        不做 exclude_none: 改回绝对地址后要清掉目标应用/APP配置名是「提交 null 即清空」的合法意图,
        丢掉 null 会让旧值静默残留并继续参与环境解析。

        :param api_in: 接口更新schema
        :return: 更新后的接口实例
        """
        api_id: Optional[int] = api_in.api_id
        api_code: Optional[str] = api_in.api_code
        if api_id:
            instance = await self.get_by_id(api_id=api_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(api_code=api_code, on_error=True, state__not=1)
            api_id = instance.id

        update_dict: Dict[str, Any] = api_in.model_dump(
            mode="json",
            exclude_unset=True,
            exclude={"api_id", "api_code"},
        )
        update_dict.update(self.dump_nested_containers(api_in))
        if api_in.request_project_id:
            await self._ensure_project_exists(project_id=api_in.request_project_id)

        changed_fields: List[str] = [field for field in API_DEFINITION_FIELDS if field in update_dict]
        # 规范化后比对: 键序与「缺键 vs null」的形态差异不算定义变更, 否则未改动的保存也会白升版本号
        definition_changed: bool = any(
            canonical_value(update_dict[field]) != canonical_value(model_field_literal(instance, field))
            for field in changed_fields
        )
        if definition_changed:
            # 版本+1 且调试结论作废: 报告快照按 api_version 判可比性, 闸门按 debug_state 放行
            update_dict["api_version"] = instance.api_version + 1
            update_dict["debug_state"] = PerfDebugState.NEVER
            update_dict["debug_time"] = None

        if "api_name" in update_dict:
            api_name: str = update_dict.get("api_name", instance.api_name)
            # 接口名称全局唯一(对齐 AutoTestStepModel: 无 api_project)
            existing = await self.model.filter(
                api_name=api_name, state__not=1
            ).exclude(id=api_id).first()
            if existing:
                error_message: str = f"压测接口[api_name={api_name}]已存在"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        # 非空列不接受 null(api_name 等): 按回查覆盖后的最终写入口拦截, 避免拖到 DB 约束错误
        ensure_no_null_for_required_fields(PerfApiModel, update_dict, "更新压测接口")
        try:
            return await self.update(id=api_id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = f"更新压测接口信息失败, 记录[id={api_id}]或[code={api_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新压测接口信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def copy_perf_api(self, *, api_id: Optional[int] = None, api_code: Optional[str] = None,
                            created_user: Optional[str] = None) -> PerfApiModel:
        """
        复制压测接口为新资产(名称追加副本后缀, 调试结论与溯源不继承)。

        :param api_id: 源接口ID(与api_code二选一)
        :param api_code: 源接口标识(与api_id二选一)
        :param created_user: 复制操作人
        :return: 新建的接口实例
        """
        if api_id:
            source = await self.get_by_id(api_id=api_id, on_error=True, state__not=1)
        else:
            source = await self.get_by_code(api_code=api_code, on_error=True, state__not=1)

        copy_dict: Dict[str, Any] = await source.to_dict(
            include_fields=list(API_DEFINITION_FIELDS) + ["api_desc"],
        )
        copy_dict.pop("id", None)
        copy_dict["api_name"] = build_copy_name(source.api_name)
        copy_dict["api_version"] = 1
        copy_dict["debug_state"] = PerfDebugState.NEVER
        copy_dict["debug_time"] = None
        copy_dict["created_user"] = created_user or source.created_user
        try:
            return await self.create(obj_in=copy_dict)
        except IntegrityError as e:
            error_message: str = f"复制压测接口信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def mark_debug_result(self, *, api_id: int, success: bool) -> PerfApiModel:
        """
        回写调试结论(调试入口的唯一落库动作, 其余调试细节不落库以免污染资产)。

        :param api_id: 接口ID
        :param success: 本次调试是否通过(HTTP 2xx 且断言全通过)
        :return: 更新后的接口实例
        """
        return await self.update(
            id=api_id,
            obj_in={
                "debug_state": PerfDebugState.SUCCESS if success else PerfDebugState.FAILED,
                "debug_time": datetime.now(),
            },
        )

    async def delete_perf_api(self, api_id: Optional[int] = None, api_code: Optional[str] = None) -> PerfApiModel:
        """
        软删除压测接口(被场景引用时禁止)。

        :param api_id: 接口主键ID，与api_code二选一
        :param api_code: 接口标识代码，与api_id二选一
        :return: 软删除后的接口实例
        """
        if not api_id and not api_code:
            error_message: str = "删除压测接口信息失败, 参数[api_id]或[api_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if api_id:
            instance = await self.get_by_id(api_id=api_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(api_code=api_code, on_error=True, state__not=1)
        await self.ensure_apis_deletable(api_codes=[instance.api_code], action="删除")
        return await self.soft_delete(id=instance.id)

    async def select_perf_apis(self, search: Q, page: int, page_size: int,
                               order: List[str]) -> Tuple[int, List[PerfApiModel]]:
        """
        根据条件分页查询压测接口列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询压测接口信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message)

    async def list_for_scene(self, *, api_name: Optional[str] = None,
                             step_type: Optional[str] = None) -> List[PerfApiModel]:
        """
        场景选择器查询(不分页, 仅启用态; 无 api_project 过滤, 接口名称全局唯一)。

        :param api_name: 名称模糊匹配
        :param step_type: 请求类型过滤
        :return: 接口实例列表
        """
        query: Q = Q(state=0)
        if api_name:
            query &= Q(api_name__contains=api_name)
        if step_type:
            query &= Q(step_type=step_type)
        return await self.model.filter(query).order_by("-updated_time")

    @staticmethod
    async def _ensure_project_exists(project_id: int) -> None:
        """
        校验应用主数据存在(与压测任务同一口径, 业务层验证不设外键)。

        :param project_id: 应用ID
        :return: None
        """
        from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud

        await AutoTestProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)

