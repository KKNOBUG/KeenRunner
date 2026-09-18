# -*- coding: utf-8 -*-
"""
数据作业入参契约。

作业是功能用例的一次参数化批量执行(prepare造数/verify校验/cleanup清理),
执行复用 autotest 的 Celery 链, 本契约只描述作业资产本身的增删查与执行下发。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_job_schema.py
@DateTime: 2026/9/17 16:50
"""
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import PerfJobType

# 执行轮数上限: 每轮一次完整功能执行(含报告落库), 轮数过大意味着把造数做成了长跑, 早失败提示
PERF_JOB_LOOP_TIMES_MAX = 1000
# 提取列数上限: 列数过多意味着数据集设计不合理(一行承载了多张表), 早失败提示
PERF_JOB_EXTRACT_FIELDS_MAX = 50


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


def ensure_extract_fields(fields: Optional[List[str]]) -> None:
    """
    校验提取列契约: 不得重复, 去除首尾空白。

    提取列是造数回写数据集的表头, 与执行明细的提取变量名/会话变量键匹配,
    重复列会导致回写行结构歧义, 保存期一次校验早失败。

    :param fields: 提取列名列表; None 表示本次未提交, 跳过校验
    :return: None
    :raises ValueError: 列名为空或重复
    """
    if fields is None:
        return
    cleaned: List[str] = [str(name).strip() for name in fields]
    if any(not name for name in cleaned):
        raise ValueError("参数[extract_fields]存在空列名")
    if len(cleaned) != len(set(cleaned)):
        raise ValueError("参数[extract_fields]存在重复列名")


class PerfJobBase(BaseModel):
    """作业公共字段(执行的脚本用例 + 执行轮次 + 提取列契约)。"""

    job_name: str = Field(..., min_length=1, max_length=255, description="作业名称")
    job_desc: Optional[str] = Field(None, max_length=2048, description="作业描述")
    job_type: PerfJobType = Field(..., description="作业类型(prepare造数/verify校验/cleanup清理)")
    quote_case_id: int = Field(..., ge=1, description="执行的脚本用例ID(公共脚本/用户脚本)")
    bind_api_id: Optional[int] = Field(None, ge=1, description="产出归属压测接口ID(prepare回写数据集归属)")
    bind_scene_id: Optional[int] = Field(None, ge=1, description="关联压测场景ID(施压链路联动)")
    loop_times: int = Field(default=1, ge=1, le=PERF_JOB_LOOP_TIMES_MAX, description="执行轮数(每轮产出一行数据)")
    dataset_name: Optional[str] = Field(None, max_length=255, description="功能参数化数据源名称(可选, 轮内喂参)")
    extract_fields: List[str] = Field(
        default_factory=list, max_length=PERF_JOB_EXTRACT_FIELDS_MAX,
        description="回写数据集的提取列名列表(prepare生效, 如orderId/token)",
    )

    @model_validator(mode="after")
    def _check_extract_fields(self):
        """提取列契约校验(委托 ensure_extract_fields, crud 合并存量后复核同一口径)。"""
        ensure_extract_fields(self.extract_fields)
        return self


class PerfJobCreate(PerfJobBase):
    """新建数据作业入参。"""

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")

    @model_validator(mode="after")
    def _require_prepare_bindings(self):
        """prepare作业的产出闭环双校验: 提取列与归属接口缺一不可。

        空提取列意味着造数没有可回写的数据; 缺归属接口则产出的数据集无法定位
        所属应用(job不挂应用, 数据集ds_project由归属接口派生), 场景也就无法按
        归属链消费该数据集。
        """
        if self.job_type != PerfJobType.PREPARE:
            return self
        if not self.extract_fields:
            raise ValueError("参数[extract_fields]不能为空, prepare作业需声明要提取回写的列")
        if not self.bind_api_id:
            raise ValueError("参数[bind_api_id]不能为空, prepare作业需声明产出归属的压测接口")
        return self


class PerfJobSelect(BaseModel):
    """分页查询数据作业入参。"""

    job_id: Optional[int] = Field(None, ge=1, description="作业ID")
    job_code: Optional[str] = Field(None, max_length=64, description="作业标识代码")
    job_name: Optional[str] = Field(None, max_length=255, description="作业名称(模糊匹配)")
    job_type: Optional[PerfJobType] = Field(None, description="作业类型")
    status: Optional[str] = Field(None, max_length=16, description="执行状态(pending/running/success/failed)")
    quote_case_id: Optional[int] = Field(None, ge=1, description="执行的脚本用例ID")
    bind_scene_id: Optional[int] = Field(None, ge=1, description="关联压测场景ID")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfJobLocate(BaseModel):
    """定位单个数据作业入参(detail/run共用)。"""

    job_id: Optional[int] = Field(None, ge=1, description="作业ID")
    job_code: Optional[str] = Field(None, max_length=64, description="作业标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一个作业。"""
        if not self.job_id and not _has_text(self.job_code):
            raise ValueError("请提供参数[job_id | job_code]完成作业操作")
        return self

