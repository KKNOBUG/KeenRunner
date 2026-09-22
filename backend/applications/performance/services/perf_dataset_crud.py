# -*- coding: utf-8 -*-
"""
压测参数化数据集CRUD。

写操作收敛在本入口: 新增/更新/删除全部经 PerfDatasetCrud, 视图层不直写模型。
本层两条硬约束:
1. dataset/dataset_names/dataframe/axis 恒由解析器(apply_dataframe_payload)派生, 不接受入参直传,
   保证落库结构与 autotest 数据源同一条解析链路;
2. 归属接口ID(bind_api_id)一律回查覆盖, 不信任前端传入。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_dataset_crud.py
@DateTime: 2026/9/15 17:10
"""
import traceback
from typing import Any, Dict, List, Optional

from tortoise.exceptions import DoesNotExist, IntegrityError

from backend.applications.autotest.services.autotest_data_source_service import apply_dataframe_payload
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_dataset_model import PerfDatasetModel
from backend.applications.performance.schemas.perf_dataset_schema import (
    PerfDatasetCreate,
    PerfDatasetUpdate,
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

# 列表接口返回列(dataset大字段除外; 矩阵与场景数据经 /perf/dataset/get 全量读取, 场景数由dataset_names派生)
DATASET_LIST_FIELDS = (
    "id", "ds_name", "ds_desc", "ds_code", "ds_project",
    "bind_api_id", "dataset_names", "ds_source",
    "file_name", "file_hash",
    "state", "created_time", "updated_time", "created_user", "updated_user",
)


class PerfDatasetCrud(ScaffoldCrud[PerfDatasetModel, PerfDatasetCreate, PerfDatasetUpdate]):

    def __init__(self):
        super().__init__(model=PerfDatasetModel)

    async def get_by_id(self, ds_id: int, on_error: bool = False, **kwargs) -> Optional[PerfDatasetModel]:
        """
        根据主键ID查询数据集。

        :param ds_id: 数据集主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 数据集实例或None
        """
        if not ds_id:
            error_message: str = "查询压测数据集信息失败, 参数[ds_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=ds_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询压测数据集信息失败, 记录[id={ds_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, ds_code: str, on_error: bool = False, **kwargs) -> Optional[PerfDatasetModel]:
        """
        根据数据集标识代码查询数据集。

        :param ds_code: 数据集标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 数据集实例或None
        """
        if not ds_code:
            error_message: str = "查询压测数据集信息失败, 参数[ds_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(ds_code=ds_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询压测数据集信息失败, 记录[code={ds_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def resolve_bind_api_id(*, bind_api_id: int) -> Dict[str, Any]:
        """
        解析归属压测接口, 返回绑定字段的落库值与自动生成的 ds_name。

        bind_api_id 必填(一个接口只能有一个数据源, 对齐 autotest 设计);
        接口名称全局唯一(无 api_project), 数据集通过 bind_api_id 直接关联接口。

        :param bind_api_id: 归属压测接口ID(必填)
        :return: {"bind_api_id": xx, "ds_name": "{api_name}_数据源"}
        """
        if not bind_api_id:
            error_message: str = "校验压测数据集失败, 参数[bind_api_id]不允许为空(一个接口只能有一个数据源)"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        api: Optional[PerfApiModel] = await PerfApiModel.filter(id=bind_api_id, state__not=1).first()
        if not api:
            error_message: str = f"校验压测数据集失败, 归属压测接口[id={bind_api_id}]不存在或已禁用"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        # ds_name 自动生成: {api_name}_数据源(对齐 autotest 设计, 不再作为用户输入项)
        auto_name: str = f"{api.api_name}_数据源"
        return {"bind_api_id": api.id, "ds_name": auto_name}

    @staticmethod
    async def _parse_matrix_payload(*, dataframe: Optional[List[Any]], axis: Optional[int]) -> Dict[str, Any]:
        """
        解析前端提交的二维矩阵为 dataset 落库字典(复用 autotest 数据源同一解析链路)。

        :param dataframe: 二维矩阵; None 表示本次不修改矩阵(仅更新场景明用)
        :param axis: 调用方声明的方向
        :return: {"dataset", "dataset_names", "dataframe", "axis"}解析结果字典
        :raises ParameterException: 矩阵无法识别方向或场景数据为空
        """
        try:
            return await apply_dataframe_payload(dataframe=dataframe, axis=axis)
        except ValueError as e:
            error_message: str = f"校验压测数据集失败, {e}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    @classmethod
    async def ensure_datasets_deletable(cls, ds_codes: List[str], action: str) -> None:
        """
        删除保护: 仍被启用场景引用的数据集禁止删除(一次场景扫描覆盖整批, 避免逐条重复遍历)。

        :param ds_codes: 待删除的数据集标识列表
        :param action: 动作描述(用于错误文案)
        :return: None
        """
        index: Dict[str, List[str]] = await PerfSceneCrud.collect_asset_references("ds_code")
        for ds_code in ds_codes:
            referenced: List[str] = index.get(ds_code) or []
            if referenced:
                error_message: str = (
                    f"{action}压测数据集信息失败, 数据集[code={ds_code}]仍被以下场景引用, 请先在场景中解除绑定: "
                    f"{referenced[:10]}"
                )
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    async def create_perf_dataset(self, ds_in: PerfDatasetCreate) -> PerfDatasetModel:
        """
        新增或更新数据集(按 bind_api_id upsert, 一个接口只能有一个数据源)。

        对齐 autotest 设计: 数据源是接口的附属资产, 不存在则创建, 已存在则更新。
        ds_name 由服务端自动生成(格式: {api_name}_数据源), 不再作为用户输入项。

        :param ds_in: 数据集创建schema
        :return: 创建或更新后的数据集实例
        """
        await self._ensure_project_exists(project_id=ds_in.ds_project)

        ds_dict: Dict[str, Any] = ds_in.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        # 矩阵解析是唯一 dataset 派生入口(空场景数据拒绝落库; 方向无法识别等非法矩阵转译为入参异常);
        # 解析结果含清洗后 dataframe/实际axis, 直接覆盖 model_dump 里的入参原值
        ds_dict.update(
            await self._parse_matrix_payload(dataframe=ds_in.dataframe, axis=ds_in.axis)
        )
        # 解析绑定关系并自动生成 ds_name(无 api_project 校验, 接口名称全局唯一)
        ds_dict.update(
            await self.resolve_bind_api_id(bind_api_id=ds_in.bind_api_id)
        )

        # 按 bind_api_id 查找已存在的数据集(一个接口只能有一个数据源)
        existing = await self.model.filter(bind_api_id=ds_in.bind_api_id, state__not=1).first()
        if not existing:
            try:
                return await self.create(obj_in=ds_dict)
            except IntegrityError as e:
                error_message: str = f"新增压测数据集信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        # 已存在则更新(保留 id, 覆盖其他字段)
        try:
            ds_dict["state"] = 0
            return await self.update(id=existing.id, obj_in=ds_dict)
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)压测数据集信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_perf_dataset(self, ds_in: PerfDatasetUpdate) -> PerfDatasetModel:
        """
        更新数据集(按 bind_api_id 定位, 一个接口只能有一个数据源)。

        不做 exclude_none: 改回手工录入后要清掉来源文件名/路径/哈希都是「提交 null
        即清空」的合法意图, 丢掉 null 会让旧的溯源信息常驻, 列表上的来源标识与真实录入方式分叉。
        dataframe 为 None 表示本次不修改矩阵数据, 已落库的场景数据保持不变。

        :param ds_in: 数据集更新schema
        :return: 更新后的数据集实例
        """
        bind_api_id: int = ds_in.bind_api_id
        # 按 bind_api_id 定位数据集(一个接口只能有一个数据源)
        instance = await self.model.filter(bind_api_id=bind_api_id, state__not=1).first()
        if not instance:
            error_message: str = f"更新压测数据集信息失败, 接口[id={bind_api_id}]尚未绑定数据源"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        ds_id: int = instance.id

        update_dict: Dict[str, Any] = ds_in.model_dump(
            mode="json", exclude_unset=True, exclude={"ds_id", "ds_code", "bind_api_id"}
        )
        ds_project: int = update_dict.get("ds_project", instance.ds_project)
        # 矩阵按键存在判定: 提交矩阵才重新解析派生(空场景数据拒绝落库; 非法矩阵转译为入参异常);
        # 解析结果含清洗后 dataframe/实际axis, 直接覆盖 model_dump 里的入参原值
        if "dataframe" in update_dict:
            update_dict.update(
                await self._parse_matrix_payload(dataframe=ds_in.dataframe, axis=ds_in.axis)
            )

        # ds_name 由服务端自动生成, 不接受前端传入(如果传入了也忽略)
        update_dict.pop("ds_name", None)

        # 非空列不接受 null(dataset/ds_name 等): 在解析与绑定回查之后的写入口拦截,
        # 避免拖到 DB 层才炸成定位不到字段的约束错误
        ensure_no_null_for_required_fields(PerfDatasetModel, update_dict, "更新压测数据集")
        try:
            return await self.update(id=ds_id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = f"更新压测数据集信息失败, 记录[id={ds_id}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新压测数据集信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def mark_job_trace(self, *, ds_id: int, job_id: int, job_code: str) -> None:
        """
        回填造数溯源列(source_type=job时由数据作业执行链调用)。

        溯源列不由 create schema 承载(避免API层伪造溯源), 由产出作业在回写后窄入口回填。

        :param ds_id: 数据集主键ID
        :param job_id: 产出作业ID
        :param job_code: 产出作业标识代码
        :return: None
        """
        await self.model.filter(id=ds_id).update(job_id=job_id, job_code=job_code)

    async def delete_perf_dataset(self, ds_id: Optional[int] = None, ds_code: Optional[str] = None) -> PerfDatasetModel:
        """
        软删除数据集(被场景引用时禁止)。

        :param ds_id: 数据集主键ID，与ds_code二选一
        :param ds_code: 数据集标识代码，与ds_id二选一
        :return: 软删除后的数据集实例
        """
        if not ds_id and not ds_code:
            error_message: str = "删除压测数据集信息失败, 参数[ds_id]或[ds_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if ds_id:
            instance = await self.get_by_id(ds_id=ds_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(ds_code=ds_code, on_error=True, state__not=1)
        await self.ensure_datasets_deletable(ds_codes=[instance.ds_code], action="删除")
        return await self.soft_delete(id=instance.id)

    async def list_enabled_for_api(self, api_id: int) -> List[Dict[str, Any]]:
        """
        查询某压测接口绑定的数据源(一个接口只能有一个数据源, 对齐 autotest 设计)。

        返回字典而非模型实例: 选择器只需轻量字段, 显式取列避免加载场景数据大字段。

        :param api_id: 压测接口主键ID
        :return: 数据集轻量字典列表(最多一条)
        """
        api = await PerfApiModel.filter(id=api_id, state__not=1).first()
        if not api:
            error_message: str = f"查询压测数据集信息失败, 压测接口[id={api_id}]不存在或已禁用"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        # 一个接口只能有一个数据源, 直接按 bind_api_id 查询
        return await self.model.filter(
            bind_api_id=api.id,
            state__not=1,
        ).order_by("-updated_time").values(*DATASET_LIST_FIELDS)

    @staticmethod
    async def _ensure_project_exists(project_id: int) -> None:
        """
        校验应用主数据存在(与压测接口/场景同一口径, 业务层验证不设外键)。

        :param project_id: 应用ID
        :return: None
        """
        from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud

        await AutoTestProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)
