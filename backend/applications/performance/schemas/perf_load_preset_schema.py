# -*- coding: utf-8 -*-
"""
负载预设入参契约(调度层)。

负载预设只承载「打多狠、什么时候打」: 场景引用 + 负载参数。流量结构与判定口径一律来自场景,
本文件不再定义任何请求/断言/数据集结构(那属于 perf_api_schema 与 perf_scene_schema)。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_load_preset_schema.py
@DateTime: 2026/9/14 11:20
"""
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import PerfLoadMode

# 压测入参边界常量：施压规模与时长上限，防止误配拖垮施压机
PERF_CONCURRENT_USERS_MAX = 5000
PERF_SPAWN_RATE_MAX = 1000
# 时长上限8h: 全局broker visibility_timeout=36000约束单任务硬时限(超时会触发消息重投重复执行),
# 与autotest任务级time_limit=28800对齐, 不碰全局配置
PERF_RUN_DURATION_MAX = 28800
# 目标吞吐上限: 引擎pacing间隔=并发/目标RPS, 过大会使间隔趋零失去节流意义
PERF_TARGET_RPS_MAX = 1000000


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class PerfLoadPresetBase(BaseModel):
    """负载预设公共字段(负载模型)。"""

    preset_project: int = Field(..., ge=1, description="负载预设所属应用")
    preset_name: str = Field(..., min_length=1, max_length=255, description="负载预设名称")
    preset_desc: Optional[str] = Field(None, max_length=2048, description="负载预设描述")
    # 施压脚本来源: 跨表引用以 code 为准, id 与名称由 crud 回查覆盖
    scene_code: str = Field(..., min_length=1, max_length=64, description="压测场景标识代码")
    scene_id: Optional[int] = Field(None, ge=1, description="压测场景ID(展示冗余, 保存时回查覆盖)")
    scene_name: Optional[str] = Field(None, max_length=255, description="压测场景名称(展示冗余, 保存时回查覆盖)")
    # 施压目标环境(复用 autotest 环境三级链; 场景内接口全为绝对地址时可留空)
    env_name: Optional[str] = Field(None, max_length=128, description="施压环境名称")
    env_config_name: Optional[str] = Field(None, max_length=128, description="施压目标配置名称(APP节点)")
    # 施压参数
    load_mode: PerfLoadMode = Field(default=PerfLoadMode.FIXED, description="施压模式(fixed/stepped/rps)")
    concurrent_users: int = Field(default=1, ge=1, le=PERF_CONCURRENT_USERS_MAX, description="并发用户数")
    spawn_rate: int = Field(default=1, ge=1, le=PERF_SPAWN_RATE_MAX, description="每秒启动用户数")
    run_duration: int = Field(default=60, ge=1, le=PERF_RUN_DURATION_MAX, description="持续时长(秒)")
    # stepped 阶梯专用字段(load_mode=stepped 时必填, 联动校验在 crud 层合并校验)
    step_start_users: Optional[int] = Field(None, ge=1, description="阶梯起始并发(stepped专用)")
    step_increment: Optional[int] = Field(None, ge=1, description="阶梯每档递增并发(stepped专用)")
    step_duration: Optional[int] = Field(None, ge=1, description="阶梯每档持续秒数(stepped专用)")
    step_max_users: Optional[int] = Field(None, ge=1, description="阶梯峰值并发(stepped专用)")
    step_sustain_duration: Optional[int] = Field(None, ge=1, description="阶梯峰值持续秒数(stepped专用)")
    # rps 吞吐模式专用字段(load_mode=rps 时必填, 联动校验在 crud 层合并校验)
    target_rps: Optional[float] = Field(None, gt=0, le=PERF_TARGET_RPS_MAX, description="目标吞吐RPS(rps专用)")


class PerfLoadPresetCreate(PerfLoadPresetBase):
    """创建负载预设入参。"""

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class PerfLoadPresetUpdate(PerfLoadPresetBase):
    """更新负载预设入参(定位字段二选一, 负载字段整体覆盖)。"""

    preset_id: Optional[int] = Field(None, ge=1, description="负载预设ID")
    preset_code: Optional[str] = Field(None, max_length=64, description="负载预设标识代码")
    preset_project: Optional[int] = Field(None, ge=1, description="负载预设所属应用")
    preset_name: Optional[str] = Field(None, min_length=1, max_length=255, description="负载预设名称")
    scene_code: Optional[str] = Field(None, min_length=1, max_length=64, description="压测场景标识代码")
    load_mode: Optional[PerfLoadMode] = Field(None, description="施压模式(fixed/stepped/rps)")
    concurrent_users: Optional[int] = Field(None, ge=1, le=PERF_CONCURRENT_USERS_MAX, description="并发用户数")
    spawn_rate: Optional[int] = Field(None, ge=1, le=PERF_SPAWN_RATE_MAX, description="每秒启动用户数")
    run_duration: Optional[int] = Field(None, ge=1, le=PERF_RUN_DURATION_MAX, description="持续时长(秒)")
    step_start_users: Optional[int] = Field(None, ge=1, description="阶梯起始并发(stepped专用)")
    step_increment: Optional[int] = Field(None, ge=1, description="阶梯每档递增并发(stepped专用)")
    step_duration: Optional[int] = Field(None, ge=1, description="阶梯每档持续秒数(stepped专用)")
    step_max_users: Optional[int] = Field(None, ge=1, description="阶梯峰值并发(stepped专用)")
    step_sustain_duration: Optional[int] = Field(None, ge=1, description="阶梯峰值持续秒数(stepped专用)")
    target_rps: Optional[float] = Field(None, gt=0, le=PERF_TARGET_RPS_MAX, description="目标吞吐RPS(rps专用)")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """更新必须能定位到一条负载预设。"""
        if not self.preset_id and not _has_text(self.preset_code):
            raise ValueError("请提供参数[preset_id | preset_code]完成负载预设更新")
        return self


class PerfLoadPresetSelect(BaseModel):
    """分页查询负载预设入参。"""

    preset_id: Optional[int] = Field(None, ge=1, description="负载预设ID")
    preset_code: Optional[str] = Field(None, max_length=64, description="负载预设标识代码")
    preset_project: Optional[int] = Field(None, ge=1, description="负载预设所属应用")
    preset_name: Optional[str] = Field(None, max_length=255, description="负载预设名称(模糊匹配)")
    scene_id: Optional[int] = Field(None, ge=1, description="压测场景ID")
    scene_code: Optional[str] = Field(None, max_length=64, description="压测场景标识代码")
    load_mode: Optional[PerfLoadMode] = Field(None, description="施压模式")
    last_execute_state: Optional[str] = Field(None, max_length=32, description="最近执行状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfLoadPresetLocate(BaseModel):
    """执行/停止负载预设入参(id或code二选一定位)。"""

    preset_id: Optional[int] = Field(None, ge=1, description="负载预设ID")
    preset_code: Optional[str] = Field(None, min_length=1, max_length=64, description="负载预设标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一条负载预设。"""
        if not self.preset_id and not _has_text(self.preset_code):
            raise ValueError("请提供参数[preset_id | preset_code]完成负载预设定位")
        return self
