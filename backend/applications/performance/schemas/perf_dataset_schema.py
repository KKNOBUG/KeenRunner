# -*- coding: utf-8 -*-
"""
压测参数化数据集入参契约。

数据结构与功能数据源(krun_autotest_data_source)同形: 前端提交二维矩阵(dataframe+axis),
dataset/dataset_names 由服务端经 autotest_data_source_parser 解析派生, 契约不收直传;
分配策略属于场景用法层, 不在本契约内。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_dataset_schema.py
@DateTime: 2026/9/15 15:50
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import PerfDatasetSource

# 场景数上限: 「场景」即unique策略下的虚拟用户独占单元, 与并发用户数上限(PERF_CONCURRENT_USERS_MAX)同一把尺子
PERF_DATASET_SCENES_MAX = 5000


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class PerfDatasetBase(BaseModel):
    """数据集公共字段(矩阵协议: dataframe为二维矩阵, 第0行/列承载场景名与分区标记)。"""

    ds_project: int = Field(..., ge=1, description="数据集所属应用")
    ds_name: str = Field(..., min_length=1, max_length=255, description="数据集名称")
    ds_desc: Optional[str] = Field(None, max_length=2048, description="数据集描述")
    bind_api_id: Optional[int] = Field(None, ge=1, description="归属压测接口ID(空=场景级自由数据)")
    dataframe: List[List[Any]] = Field(
        default_factory=list,
        description="数据二维矩阵(水平: 首行分区标记+字段名/首列场景名; 垂直: 首列分区标记+字段名/首行场景名)",
    )
    axis: int = Field(default=0, ge=0, le=1, description="数据矩阵(0:水平模式, 1:垂直模式)")
    ds_source: PerfDatasetSource = Field(default=PerfDatasetSource.MANUAL, description="数据来源")
    file_name: Optional[str] = Field(None, max_length=2048, description="来源文件名")
    file_path: Optional[str] = Field(None, max_length=2048, description="来源文件路径")
    file_hash: Optional[str] = Field(None, max_length=64, description="来源文件哈希")


class PerfDatasetCreate(PerfDatasetBase):
    """新建数据集入参(dataset/dataset_names由服务端解析矩阵派生)。"""

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @model_validator(mode="after")
    def _require_dataframe(self):
        """数据集必须携带非空矩阵(空矩阵在施压期只会产出假结果)。"""
        if not self.dataframe:
            raise ValueError("参数[dataframe]不能为空, 请先在线编辑数据矩阵或上传文件解析")
        return self


class PerfDatasetUpdate(PerfDatasetBase):
    """更新数据集入参(定位字段二选一, 其余字段可选)。"""

    ds_id: Optional[int] = Field(None, ge=1, description="数据集ID")
    ds_code: Optional[str] = Field(None, max_length=64, description="数据集标识代码")
    ds_project: Optional[int] = Field(None, ge=1, description="数据集所属应用")
    ds_name: Optional[str] = Field(None, min_length=1, max_length=255, description="数据集名称")
    ds_desc: Optional[str] = Field(None, max_length=2048, description="数据集描述")
    bind_api_id: Optional[int] = Field(None, ge=1, description="归属压测接口ID(提交null=解除归属)")
    dataframe: Optional[List[List[Any]]] = Field(None, description="数据二维矩阵(null=本次不修改矩阵数据)")
    axis: Optional[int] = Field(None, ge=0, le=1, description="数据矩阵(0:水平模式, 1:垂直模式)")
    ds_source: Optional[PerfDatasetSource] = Field(None, description="数据来源")
    file_name: Optional[str] = Field(None, max_length=2048, description="来源文件名")
    file_path: Optional[str] = Field(None, max_length=2048, description="来源文件路径")
    file_hash: Optional[str] = Field(None, max_length=64, description="来源文件哈希")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """更新必须能定位到一个数据集。"""
        if not self.ds_id and not _has_text(self.ds_code):
            raise ValueError("请提供参数[ds_id | ds_code]完成数据集更新")
        return self


class PerfDatasetParsedPreview(BaseModel):
    """上传解析结果回显(仅返回不落库, 由用户确认矩阵后随 create 提交 dataframe+axis 落库)。"""

    dataset: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="解析出的场景数据({场景名: 四分区})")
    dataset_names: List[str] = Field(default_factory=list, description="解析出的场景名称列表")
    dataframe: List[List[Any]] = Field(default_factory=list, description="解析出的原始二维矩阵")
    axis: int = Field(default=0, ge=0, le=1, description="矩阵方向(0:水平, 1:垂直)")
    file_name: str = Field(..., max_length=2048, description="存储文件名(清洗非法字符并加时间戳前缀, 可能与上传名不同)")
    file_path: str = Field(..., max_length=2048, description="存储文件路径")
    file_hash: Optional[str] = Field(None, max_length=64, description="文件哈希(读取失败时为空)")
