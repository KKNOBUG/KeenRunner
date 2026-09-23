# -*- coding: utf-8 -*-
"""
压测场景入参契约(编排层)。

场景回答「打什么、怎么打」: 接口项组合(角色/权重/思考时间/事务/数据集策略) + 链路阶段 +
判定口径(SLA目标/基线策略/熔断/预热)。跨表引用一律以 *_code 为准, id 与名称仅作展示冗余,
保存时由 crud 层回查覆盖, 防止前端传来的名称与资产实际名称分叉。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_scene_schema.py
@DateTime: 2026/9/15 16:00
"""
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.applications.performance.schemas.perf_load_preset_schema import (
    PERF_CONCURRENT_USERS_MAX,
    PERF_RUN_DURATION_MAX,
    PERF_SPAWN_RATE_MAX,
    PERF_TARGET_RPS_MAX,
    PerfLoadPresetCreate,
    PerfLoadPresetUpdate,
)
from backend.enums import (
    PERF_WARMUP_DEFAULT_MAX,
    PerfApiRole,
    PerfAssertMode,
    PerfDatasetStrategy,
    PerfDelayMode,
    PerfLoadMode,
    PerfPhaseExecution,
    PerfRunMode,
    PerfTargetMetric,
    PerfTargetOp,
    PerfTargetScope,
    PerfTargetSeverity,
)
from backend.applications.performance.schemas.perf_api_schema import NON_LIST_DICT_TYPE

# 单场景接口项上限: 超过该规模意味着应拆分为多个场景(指标归因与快照体积都会失控)
PERF_SCENE_ITEMS_MAX = 30
# 权重与思考时间边界
PERF_WEIGHT_MAX = 1000
PERF_DELAY_MS_MAX = 600_000
# 预热剔除绝对上限(与默认派生上限一致, 再大就该改用例而不是调参数)
PERF_WARMUP_MAX = PERF_WARMUP_DEFAULT_MAX
# SLA 目标条数上限
PERF_TARGETS_MAX = 20


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class PerfSceneItemOverride(BaseModel):
    """
    场景内对接口定义的少量覆盖。

    只允许覆盖请求头与请求参数: method/url/报文等结构性字段一律去改接口定义,
    否则同一资产在不同场景会长出不同形态, 报告快照失去可比性。
    """

    request_header: NON_LIST_DICT_TYPE = Field(None, description="追加/覆盖的请求头(按key合并)")
    request_params: NON_LIST_DICT_TYPE = Field(None, description="追加/覆盖的请求参数(按key合并)")


class PerfSceneItem(BaseModel):
    """场景接口项元素(引用压测接口资产 + 施压用法)。"""

    seq: int = Field(..., ge=1, description="场景内序号(执行顺序与链路引用锚点)")
    api_code: str = Field(..., min_length=1, max_length=64, description="压测接口标识")
    api_id: Optional[int] = Field(None, ge=1, description="压测接口ID(展示冗余, 保存时回查覆盖)")
    api_name: Optional[str] = Field(None, max_length=255, description="压测接口名称(展示冗余, 保存时回查覆盖)")
    role: PerfApiRole = Field(default=PerfApiRole.MEASURED, description="指标口径角色(measured计入/prepare隔离/verify抽查)")
    weight: int = Field(default=1, ge=1, le=PERF_WEIGHT_MAX, description="加权权重(仅mixed模式生效)")
    delay_mode: PerfDelayMode = Field(default=PerfDelayMode.FIXED, description="思考时间模式")
    delay_ms: int = Field(default=0, ge=0, le=PERF_DELAY_MS_MAX, description="固定思考毫秒数(delay_mode=fixed)")
    delay_ms_min: Optional[int] = Field(None, ge=0, le=PERF_DELAY_MS_MAX, description="思考毫秒下限(delay_mode=uniform)")
    delay_ms_max: Optional[int] = Field(None, ge=0, le=PERF_DELAY_MS_MAX, description="思考毫秒上限(delay_mode=uniform)")
    transaction: Optional[str] = Field(None, max_length=128, description="归属事务名(空=不参与事务聚合)")
    ds_code: Optional[str] = Field(None, max_length=64, description="绑定的数据集标识(空=无参数化)")
    ds_name: Optional[str] = Field(None, max_length=255, description="数据集名称(展示冗余, 保存时回查覆盖)")
    dataset_strategy: PerfDatasetStrategy = Field(default=PerfDatasetStrategy.ROUND_ROBIN, description="参数化行分配策略")
    override: Optional[PerfSceneItemOverride] = Field(None, description="场景内少量覆盖(仅请求头/请求参数)")
    enabled: bool = Field(default=True, description="是否参与施压")

    @model_validator(mode="after")
    def _check_delay_shape(self):
        """区间随机思考时间必须上下限齐备且下限不大于上限。"""
        if self.role == PerfApiRole.MEASURED and self.delay_mode == PerfDelayMode.UNIFORM:
            if self.delay_ms_min is None or self.delay_ms_max is None:
                raise ValueError(f"序号{self.seq}的思考模式为uniform时必须提供[delay_ms_min]与[delay_ms_max]")
            if self.delay_ms_min > self.delay_ms_max:
                raise ValueError(f"序号{self.seq}的[delay_ms_min]不得大于[delay_ms_max]")
        return self


class PerfJourneyPhase(BaseModel):
    """业务链路单个阶段(只引用接口项序号, 不重复定义请求内容)。"""

    name: str = Field(..., min_length=1, max_length=128, description="阶段名称")
    execution: PerfPhaseExecution = Field(default=PerfPhaseExecution.SERIAL, description="阶段内执行方式")
    sync_before: bool = Field(default=False, description="阶段前是否设集合点(整点放闸语义)")
    max_parallel: int = Field(default=1, ge=1, le=64, description="阶段内最大并行度(并行与集合点放闸的规模)")
    item_refs: List[int] = Field(..., min_length=1, description="引用的接口项序号列表")


class PerfJourney(BaseModel):
    """业务链路定义: 一圈产出一个事务样本。"""

    stop_on_step_fail: bool = Field(default=True, description="圈内任一步失败是否立即结束本圈")
    delay_between_journeys_ms: int = Field(default=0, ge=0, le=PERF_DELAY_MS_MAX, description="两圈之间思考毫秒数")
    phases: List[PerfJourneyPhase] = Field(..., min_length=1, description="阶段列表(按序执行)")


class PerfBaselinePolicy(BaseModel):
    """相对基线的退化阈值(百分比); 未设置的项不参与退化判定。"""

    p95_degrade_pct: Optional[float] = Field(None, ge=0, le=100, description="P95允许退化百分比")
    qps_degrade_pct: Optional[float] = Field(None, ge=0, le=100, description="RPS允许退化百分比")
    error_rate_increase: Optional[float] = Field(None, ge=0, le=100, description="错误率允许上升百分点")


class PerfTargetItem(BaseModel):
    """SLA 绝对目标(逐条判定, 与熔断、基线退化三者职责分离)。"""

    scope: PerfTargetScope = Field(..., description="判定对象层级(global/api/transaction)")
    target: PerfTargetMetric = Field(..., description="判定指标(与报告字段名逐字一致)")
    api_code: Optional[str] = Field(None, max_length=64, description="接口标识(scope=api必填)")
    transaction: Optional[str] = Field(None, max_length=128, description="事务名(scope=transaction必填)")
    op: PerfTargetOp = Field(..., description="比较运算符")
    expect: float = Field(..., description="期望值")
    severity: PerfTargetSeverity = Field(default=PerfTargetSeverity.FAIL, description="未达成严重级")
    min_total_requests: Optional[int] = Field(None, ge=1, description="参与判定的最小样本量")
    min_duration_seconds: Optional[int] = Field(None, ge=1, description="参与判定的最小施压时长")

    @model_validator(mode="after")
    def _check_scope_target(self):
        """api/transaction 两级判定必须给出定位对象, 否则退化成不知在比什么的结论。"""
        if self.scope == PerfTargetScope.API and not _has_text(self.api_code):
            raise ValueError("scope=api的目标必须提供[api_code]")
        if self.scope == PerfTargetScope.TRANSACTION and not _has_text(self.transaction):
            raise ValueError("scope=transaction的目标必须提供[transaction]")
        return self


class PerfSceneBase(BaseModel):
    """场景公共字段。"""

    scene_project: int = Field(..., ge=1, description="场景所属应用")
    scene_name: str = Field(..., min_length=1, max_length=255, description="场景名称")
    scene_desc: Optional[str] = Field(None, max_length=2048, description="场景描述")
    run_mode: PerfRunMode = Field(default=PerfRunMode.SINGLE, description="施压语义(single/mixed/journey)")
    scene_items: List[PerfSceneItem] = Field(..., min_length=1, max_length=PERF_SCENE_ITEMS_MAX, description="接口项列表")
    journey: Optional[PerfJourney] = Field(None, description="业务链路定义(journey模式必填)")
    perf_targets: Optional[List[PerfTargetItem]] = Field(None, max_length=PERF_TARGETS_MAX, description="SLA目标列表")
    baseline_report_code: Optional[str] = Field(None, max_length=64, description="基线报告标识")
    baseline_policy: Optional[PerfBaselinePolicy] = Field(None, description="基线退化阈值")
    warmup_seconds: Optional[int] = Field(None, ge=0, le=PERF_WARMUP_MAX, description="预热剔除秒数(空=按ramp派生, 0=不剔除)")
    error_rate_threshold: Optional[float] = Field(None, ge=0, le=100, description="熔断错误率阈值(百分比, 0=不熔断)")
    assert_mode: PerfAssertMode = Field(default=PerfAssertMode.ALL, description="断言执行口径")
    sample_ratio: float = Field(default=100.0, gt=0, le=100, description="断言采样比例(百分比)")
    inject_perf_tag: bool = Field(default=True, description="是否注入x-perf-batch压测标记头")

    @field_validator("scene_items", mode="before")
    @classmethod
    def _normalize_items(cls, v: Any) -> Any:
        """接口项必须为数组(字典形态多为前端序列化退化, 早失败好过静默错序)。"""
        if isinstance(v, dict):
            return list(v.values())
        return v

    @model_validator(mode="after")
    def _check_scene_shape(self):
        """
        校验场景编排自洽性: 序号唯一、被测项存在、模式与结构匹配。

        single 模式多于一个被测项会静默变成加权抽样, 用户看到的「单接口指标」实际是混合流量,
        属于口径级错误, 必须在保存期拦住而不是留到报告页解释。
        """
        items = [item for item in self.scene_items if item.enabled]
        seq_list = [item.seq for item in self.scene_items]
        if len(seq_list) != len(set(seq_list)):
            raise ValueError("参数[scene_items]存在重复的[seq]")
        if not items:
            raise ValueError("场景至少需要1个启用状态的接口项")
        measured = [item for item in items if item.role == PerfApiRole.MEASURED]
        if not measured:
            raise ValueError("场景至少需要1个角色为measured的接口项(准备与抽查项不计业务指标)")
        if self.run_mode == PerfRunMode.SINGLE and len(measured) > 1:
            raise ValueError("单接口模式只允许1个measured项, 多接口混合请改用mixed模式")
        if self.run_mode == PerfRunMode.MIXED and len(measured) < 2:
            raise ValueError("混合流量模式需要至少2个measured项, 否则请改用单接口模式")
        if self.run_mode == PerfRunMode.JOURNEY:
            self._check_journey(items)
        if self.assert_mode == PerfAssertMode.SAMPLE_RATIO and not self.sample_ratio:
            raise ValueError("assert_mode=sample_ratio时必须设置[sample_ratio]")
        return self

    def _check_journey(self, items: List[PerfSceneItem]) -> None:
        """链路模式校验: 阶段必须存在、引用必须落到启用项、每个启用项都要归属某阶段。"""
        if not self.journey or not self.journey.phases:
            raise ValueError("业务链路模式必须提供[journey.phases]")
        enabled_seqs = {item.seq for item in items}
        referenced: set = set()
        for phase in (self.journey.phases or []):
            unknown = [seq for seq in phase.item_refs if seq not in enabled_seqs]
            if unknown:
                raise ValueError(f"链路阶段[{phase.name}]引用了不存在或未启用的接口项序号: {unknown}")
            referenced.update(phase.item_refs)
        orphan = sorted(enabled_seqs - referenced)
        if orphan:
            raise ValueError(f"接口项序号{orphan}未归属任何链路阶段, 链路模式下所有启用项必须参与成圈")

    @property
    def measured_item_count(self) -> int:
        """启用的被测项数量(供列表页与预检展示, 避免各处重复过滤)。"""
        return sum(
            1 for item in self.scene_items
            if item.enabled and item.role == PerfApiRole.MEASURED
        )


class PerfSceneCreate(PerfSceneBase):
    """新建场景入参。"""

    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class PerfSceneUpdate(PerfSceneBase):
    """更新场景入参(与场景编辑「一次提交全量结构」的交互一致: 整编排覆盖保存, 不做局部补丁)。"""

    scene_id: Optional[int] = Field(None, ge=1, description="场景ID")
    scene_code: Optional[str] = Field(None, max_length=64, description="场景标识代码")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """更新必须能定位到一个场景。"""
        if not self.scene_id and not _has_text(self.scene_code):
            raise ValueError("请提供参数[scene_id | scene_code]完成场景更新")
        return self


class PerfSceneSelect(BaseModel):
    """分页查询场景入参。"""

    scene_id: Optional[int] = Field(None, ge=1, description="场景ID")
    scene_code: Optional[str] = Field(None, max_length=64, description="场景标识代码")
    scene_project: Optional[int] = Field(None, ge=1, description="场景所属应用")
    scene_name: Optional[str] = Field(None, max_length=255, description="场景名称(模糊匹配)")
    run_mode: Optional[PerfRunMode] = Field(None, description="施压语义")
    api_code: Optional[str] = Field(None, max_length=64, description="引用的接口标识(查引用关系)")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfSceneLocate(BaseModel):
    """单场景定位入参(复制共用)。"""

    scene_id: Optional[int] = Field(None, ge=1, description="场景ID")
    scene_code: Optional[str] = Field(None, min_length=1, max_length=64, description="场景标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一个场景。"""
        if not self.scene_id and not _has_text(self.scene_code):
            raise ValueError("请提供参数[scene_id | scene_code]完成场景定位")
        return self


class PerfScenePrecheck(PerfSceneLocate):
    """场景预检入参(定位 + 可选施压环境; 接口地址为绝对地址时环境可留空)。"""

    env_name: Optional[str] = Field(None, max_length=128, description="预检环境名称")
    env_config_name: Optional[str] = Field(None, max_length=128, description="预检目标配置名称(APP节点)")


class PerfScenePinBaseline(PerfSceneLocate):
    """场景基线钉选入参(定位场景 + 指定基线报告; report_code留空=取消钉选)。"""

    report_code: Optional[str] = Field(None, max_length=64, description="基线报告标识代码(空=取消钉选)")


class PerfSceneWizardPresetCreate(BaseModel):
    """
    一体化保存中预设新增项(向导专用)。

    与独立 PerfLoadPresetCreate 的区别: scene_code/scene_id/scene_name/preset_project 均可缺省,
    由 save_wizard 服务层在场景落库后统一回写, 前端无需(也不应)提前猜测场景标识。
    """

    preset_name: str = Field(..., min_length=1, max_length=255, description="负载预设名称")
    preset_desc: Optional[str] = Field(None, max_length=2048, description="负载预设描述")
    preset_project: Optional[int] = Field(None, ge=1, description="负载预设所属应用(缺省随场景)")
    scene_code: Optional[str] = Field(None, max_length=64, description="压测场景标识代码(缺省由服务层回写)")
    scene_id: Optional[int] = Field(None, ge=1, description="压测场景ID(缺省由服务层回写)")
    scene_name: Optional[str] = Field(None, max_length=255, description="压测场景名称(缺省由服务层回写)")
    env_name: Optional[str] = Field(None, max_length=128, description="施压环境名称")
    env_config_name: Optional[str] = Field(None, max_length=128, description="施压目标配置名称(APP节点)")
    load_mode: PerfLoadMode = Field(default=PerfLoadMode.FIXED, description="施压模式(fixed/stepped/rps)")
    concurrent_users: int = Field(default=1, ge=1, le=PERF_CONCURRENT_USERS_MAX, description="并发用户数")
    spawn_rate: int = Field(default=1, ge=1, le=PERF_SPAWN_RATE_MAX, description="每秒启动用户数")
    run_duration: int = Field(default=60, ge=1, le=PERF_RUN_DURATION_MAX, description="持续时长(秒)")
    step_start_users: Optional[int] = Field(None, ge=1, description="阶梯起始并发(stepped专用)")
    step_increment: Optional[int] = Field(None, ge=1, description="阶梯每档递增并发(stepped专用)")
    step_duration: Optional[int] = Field(None, ge=1, description="阶梯每档持续秒数(stepped专用)")
    step_max_users: Optional[int] = Field(None, ge=1, description="阶梯峰值并发(stepped专用)")
    step_sustain_duration: Optional[int] = Field(None, ge=1, description="阶梯峰值持续秒数(stepped专用)")
    target_rps: Optional[float] = Field(None, gt=0, le=PERF_TARGET_RPS_MAX, description="目标吞吐RPS(rps专用)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class PerfSceneWizardPresetDelete(BaseModel):
    """一体化保存中预设软删项(仅定位字段 + _delete 标记)。"""

    preset_id: Optional[int] = Field(None, ge=1, description="负载预设ID")
    preset_code: Optional[str] = Field(None, max_length=64, description="负载预设标识代码")
    _delete: bool = True

    @model_validator(mode="after")
    def _require_locator(self):
        """软删必须能定位到一条负载预设。"""
        if not self.preset_id and not _has_text(self.preset_code):
            raise ValueError("请提供参数[preset_id | preset_code]完成预设软删定位")
        return self


class PerfSceneWizardPayload(BaseModel):
    """
    场景独立编辑页一体化保存入参(Tab 编辑页唯一提交入口)。

    结构 = { scene: PerfSceneCreate|PerfSceneUpdate, presets: List[PerfLoadPresetCreate|PerfLoadPresetUpdate|PerfSceneWizardPresetDelete] };
    服务层在事务内 upsert scene + diff upsert presets(新增/更新/软删)。
    """

    scene: Union[PerfSceneCreate, PerfSceneUpdate] = Field(..., description="场景实体(含 scene_id/scene_code 时为更新)")
    presets: List[Union[PerfLoadPresetUpdate, PerfSceneWizardPresetDelete, PerfSceneWizardPresetCreate]] = Field(
        default_factory=list, description="负载预设列表(含 preset_id/preset_code 为更新; 含 _delete=True 为软删; 其余为新增)"
    )


class PerfPresetBatchDuplicate(BaseModel):
    """拐点测试快捷操作: 基于已有预设批量派生多个并发档位。"""

    base_preset_id: Optional[int] = Field(None, ge=1, description="基准预设ID(并发档位以该预设为模板)")
    base_preset_code: Optional[str] = Field(None, max_length=64, description="基准预设标识代码")
    concurrent_users_list: List[int] = Field(..., min_length=1, description="待派生的并发用户数列表(如 [50,100,200])")
    name_template: Optional[str] = Field(None, max_length=255, description="预设名称模板(包含 {users} 占位符; 缺省=基准名称-并发数)")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到基准预设。"""
        if not self.base_preset_id and not _has_text(self.base_preset_code):
            raise ValueError("请提供参数[base_preset_id | base_preset_code]定位基准预设")
        if not self.concurrent_users_list or any(u < 1 for u in self.concurrent_users_list):
            raise ValueError("concurrent_users_list 必须为非空正整数列表")
        return self


class PerfSceneRunAllPresets(PerfSceneLocate):
    """一键批量下发场景下所有预设执行入参(定位场景即可)。"""

