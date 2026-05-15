# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.applications.aotutest.schemas.autotest_case_schema import AutoTestApiCaseUpdate
from backend.applications.base.services.scaffold import UpperStr
from backend.enums import (
    AutoTestStepType,
    AutoTestLoopMode,
    AutoTestReqArgsType,
    AutoTestLoopErrorStrategy,
    AutoTestAssertionOperation,
    AutoTestConfigNodeType,
)
from backend.enums import HTTPMethod

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class DataBaseOperates(BaseModel):
    name: str = Field(..., max_length=128, description="数据库操作名称")
    expr: str = Field(..., max_length=4096, description="数据库操作SQL语句")
    project_id: Optional[int] = Field(None, ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
    variable_name: str = Field(..., max_length=128, description="存储变量名称")
    config_name: str = Field(..., max_length=128, description="所属环境配置名称")
    database_name: str = Field(..., max_length=128, description="所属数据库名称")
    desc: Optional[str] = Field(None, max_length=2048, description="数据库操作描述")


class ConditionsBase(BaseModel):
    condition_expr: str = Field(..., max_length=128, description="条件表达式")
    condition_compare: str = Field(..., max_length=128, description="条件比较符")
    condition_value: Optional[Any] = Field(None, description="条件比对值")
    condition_desc: Optional[str] = Field(None, max_length=2048, description="条件描述")

    @field_validator("condition_compare", mode="before")
    @classmethod
    def validate_condition_compare(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("条件比较符不能为空")
        return AutoTestAssertionOperation(str(v).strip()).value


class StepVariablesBase(BaseModel):
    key: str = Field(..., max_length=1024, description="会话变量(键)")
    value: Optional[Any] = Field(None, description="会话变量(值)")
    desc: Optional[str] = Field(None, max_length=2048, description="会话变量(描述)")


class StepsExecuteConfigBase(BaseModel):
    env_name: str = Field(..., max_length=128, description="环境名称")
    config_type: AutoTestConfigNodeType = Field(..., description="配置类型")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="配置主机")
    config_port: str = Field(..., max_length=8, description="配置端口")
    database_name: Optional[str] = Field(None, max_length=128, description="数据库名称")


class StepExtractVariableItem(BaseModel):
    """步骤定义中的单条提取规则；``scope`` 表示 ALL/SOME，对应 ``extract_from_source`` 的 range_type 参数。"""
    name: str = Field(..., max_length=256, description="提取项名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: str = Field(..., max_length=4096, description="提取表达式")
    scope: Optional[str] = Field(None, max_length=32, description="ALL 或 SOME 等，与 run_extract 一致")
    index: Optional[int] = Field(None, description="多匹配时索引")


class StepAssertValidatorItem(BaseModel):
    """步骤定义中的单条断言，与 run_assert_validators 入参一致。"""

    name: str = Field(..., max_length=256, description="断言项名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: str = Field(..., max_length=4096, description="表达式")
    operation: str = Field(..., max_length=128, description="比较符")
    except_value: Any = Field(default=None, description="期待值")


class AutoTestApiStepReqBase(BaseModel):
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, max_length=16, description="请求方法(GET/POST/PUT/DELETE等)")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_body: NON_DICT_TYPE = Field(None, description="请求体数据(Json格式)")
    request_header: NON_LIST_DICT_TYPE = Field(None, description="请求头信息")
    request_params: NON_LIST_DICT_TYPE = Field(None, description="请求路径参数")
    request_form_data: NON_LIST_DICT_TYPE = Field(None, description="请求表单数据")
    request_form_urlencoded: NON_LIST_DICT_TYPE = Field(None, description="请求键值对数据")
    request_form_file: NON_LIST_DICT_TYPE = Field(None, description="请求文件路径")
    request_project_id: Optional[int] = Field(None, ge=1, description="请求应用ID")
    request_args_type: Optional[AutoTestReqArgsType] = Field(None, description="请求参数类型")
    request_config_name: Optional[str] = Field(None, max_length=128, description="请求环境配置名称")
    # TCP 步骤扩展（与 TcpStepExecutor 约定一致；存库 JSON 可含下列键）
    tcp_frame_mode: Optional[str] = Field(None, max_length=64, description="TCP 帧模式，如 length_prefix_json / raw")
    tcp_length_field_size: Optional[int] = Field(None, ge=1, le=32, description="长度前缀字段宽度")
    tcp_encoding: Optional[str] = Field(None, max_length=32, description="文本编码，如 utf-8")
    tcp_connect_timeout: Optional[float] = Field(None, ge=0, description="连接超时（秒）")
    tcp_read_timeout: Optional[float] = Field(None, ge=0, description="读写超时（秒）")
    tcp_max_response_bytes: Optional[int] = Field(None, ge=1, description="最大读取字节数")
    tcp_response_type: Optional[str] = Field(None, max_length=16, description="响应解析：json|xml|text|bytes")


class AutoTestApiStepDbBase(BaseModel):
    database_operates: Optional[List[DataBaseOperates]] = Field(None, description="数据库请求操作列表")
    database_searched: Optional[bool] = Field(None, description="数据库请求查到即止开关")

    @field_validator("database_operates", mode="before")
    @classmethod
    def normalize_database_operates(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        raise ValueError(
            f"database_operates 必须为 null、单条对象或对象数组，当前类型: {type(v).__name__}"
        )


class AutoTestApiStepVarBase(BaseModel):
    session_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="会话变量(所有步骤持续累积), 列表项为 key / value / desc")
    defined_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="定义变量, 列表项为 key / value / desc")
    extract_variables: Optional[List[StepExtractVariableItem]] = Field(default=None, description="提取规则(步骤定义), 使用 scope 表示 ALL/SOME")
    assert_validators: Optional[List[StepAssertValidatorItem]] = Field(default=None, description="断言规则(步骤定义)")

    @field_validator("session_variables", mode="before")
    @classmethod
    def _session_variables_list_shape(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"session_variables 必须为数组或 null，当前类型: {type(v).__name__}")
        return v

    @field_validator("defined_variables", mode="before")
    @classmethod
    def _defined_variables_list_shape(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"defined_variables 必须为数组或 null，当前类型: {type(v).__name__}")
        return v

    @field_validator("extract_variables", mode="before")
    @classmethod
    def _extract_variables_list_shape(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"extract_variables 必须为数组或 null，当前类型: {type(v).__name__}")
        return v

    @field_validator("assert_validators", mode="before")
    @classmethod
    def _assert_validators_list_shape(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"assert_validators 必须为数组或 null，当前类型: {type(v).__name__}")
        return v


class AutoTestApiStepBase(AutoTestApiStepReqBase, AutoTestApiStepDbBase, AutoTestApiStepVarBase):
    model_config = ConfigDict(extra="ignore")

    step_id: Optional[int] = Field(None, description="步骤ID(更新必填, 新增不填)")
    step_no: Optional[int] = Field(None, ge=1, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码(更新必填, 新增不填)")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_desc: Optional[str] = Field(None, description="步骤描述")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤所属类型")

    case_id: Optional[int] = Field(None, description="步骤所属用例")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, ge=0, le=300, description="等待控制(正浮点数, 单位:秒)")
    loop_mode: Optional[AutoTestLoopMode] = Field(None, description="循环模式类型")
    loop_maximums: Optional[int] = Field(None, ge=1, le=100, description="最大循环次数(正整数)")
    loop_interval: Optional[float] = Field(None, ge=0, le=60, description="每次循环间隔时间(正浮点数)")
    loop_iterable: Optional[str] = Field(None, max_length=512, description="循环对象来源(变量名或可迭代对象)")
    loop_on_error: Optional[AutoTestLoopErrorStrategy] = Field(None, description="循环执行失败时的处理策略")
    loop_timeout: Optional[float] = Field(None, ge=0, le=3000, description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    data_source_name: Optional[str] = Field(None, max_length=2048, description="数据源名称")
    data_source_desc: Optional[str] = Field(None, max_length=2048, description="数据源描述")
    conditions: Optional[ConditionsBase] = Field(None, description="判断条件(循环结构或条件分支)")

    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")

    @field_validator("conditions", mode="before")
    @classmethod
    def _conditions_must_be_object_or_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, ConditionsBase):
            return v
        if isinstance(v, dict):
            return v
        raise ValueError(
            f"conditions 必须为对象或 null，当前类型: {type(v).__name__}"
        )


class AutoTestApiStepChildren(BaseModel):
    children: Optional[List["AutoTestApiStepBase"]] = Field(None, description="子步骤")
    quote_steps: Optional[List["AutoTestApiStepBase"]] = Field(None, description="引用步骤")


class AutoTestApiStepCreate(AutoTestApiStepBase):
    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_type: AutoTestStepType = Field(..., description="步骤所属类型")
    created_user: Optional[UpperStr] = Field(None, description="创建人员")


class AutoTestApiStepUpdate(AutoTestApiStepBase):
    updated_user: Optional[UpperStr] = Field(None, description="更新人员")


class AutoTestApiStepSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["case_id", "step_no"], description="排序字段")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")

    case_id: Optional[int] = Field(None, description="用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本ID")
    created_user: Optional[UpperStr] = Field(None, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")


class AutoTestStepTreeUpdateItem(AutoTestApiStepBase):
    case: NON_DICT_TYPE = Field(None, description="用例信息")
    children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="子步骤列表")
    quote_steps: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="引用步骤列表(与 children 同型；更新时忽略)")
    quote_case: Optional[Any] = Field(None, description="引用公共脚本信息(更新时忽略)")


class StepTreeCounter(BaseModel):
    """步骤树统计：与历史 get_by_case_id 末尾元数据字段一致。"""
    direct_steps: int = 0
    child_steps: int = 0
    quote_steps: int = 0
    total_steps: int = 0


class AutoTestCaseStepTreeLoadResult(BaseModel):
    """仓储层从 DB 构建步骤树后的对外结果：根步骤均为已校验模型。"""
    root_steps: List["AutoTestStepTreeUpdateItem"] = Field(default_factory=list)
    step_counter: StepTreeCounter
    case_only_when_no_steps: Optional[AutoTestApiCaseUpdate] = Field(
        default=None,
        description="无任何根步骤时，与历史接口中单节点仅含 case 的占位信息对应",
    )


class AutoTestStepTreeUpdateList(BaseModel):
    case: AutoTestApiCaseUpdate = Field(..., description="用例信息")
    steps: List[AutoTestStepTreeUpdateItem] = Field(..., description="步骤树数据")


class AutoTestHttpDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepReqBase):
    env_id: int = Field(..., ge=1, description="环境枚举ID")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_url: str = Field(..., max_length=2048, description="请求地址")
    request_method: HTTPMethod = Field(..., description="请求方法")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestTcpDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepReqBase):
    env_id: int = Field(..., ge=1, description="环境枚举ID")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestPythonCodeDebugRequest(AutoTestApiStepVarBase):
    step_name: str = Field(..., max_length=255, description="步骤名称")
    code: str = Field(..., description="执行代码(Python)")


class AutoTestCaseRunInfo(BaseModel):
    """执行/调试时传入引擎的用例上下文（与 ORM to_dict 的 case 摘要字段对齐）。"""
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_name: str = Field(..., max_length=255, description="用例名称")


class AutoTestStepTreeExecute(BaseModel):
    case_id: int = Field(..., description="用例ID(运行模式和调试模式都必填)")
    steps: Optional[List[AutoTestStepTreeUpdateItem]] = Field(None, description="步骤树数据(调试模式必填, 运行模式不填)")
    initial_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="初始变量池, 列表项为 key / value / desc")
    # 脚本执行配置：key=步骤ID(step_id) 或 @@{step_name}（当步骤未落库时），value=配置明细；空 dict 表示该步骤无配置覆盖
    # { step_id 或 @@step_name: {env_name, config_type(api|database|file), config_name, config_host, config_port, database_name} }
    steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = Field(default=None, description="脚本执行配置作用环境")
    # 参数化驱动：运行模式可传多条数据集名称，按条数循环执行；调试模式只能传一条
    selected_dataset_names: Optional[List[str]] = Field(None, description="选中的数据集名称列表。运行模式可选多条；调试模式仅可选一条")

    @model_validator(mode='after')
    def validate_mode(self):
        # case_id 是必填的（运行模式和调试模式都需要）
        # 运行模式：只传递 case_id，不传递 steps
        # 调试模式：传递 case_id 和 steps
        if self.case_id is None:
            raise ValueError("必须提供[case_id]参数（运行模式和调试模式都需要）")
        return self


class AutoTestBatchExecuteCases(BaseModel):
    env_name: Optional[str] = Field(None, description="执行环境名称")
    case_ids: List[int] = Field(..., min_length=1, description="用例ID列表")
    initial_variables: Optional[List[StepVariablesBase]] = Field(
        default=None, description="初始变量(会应用到所有用例), 列表项为 key / value / desc"
    )


def step_variables_list_from_storage(raw: Any) -> List[StepVariablesBase]:
    """ORM/JSON 边界：将存库的变量列表转为 ``StepVariablesBase`` 列表。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"变量列表必须为数组或 null，当前类型: {type(raw).__name__}")
    out: List[StepVariablesBase] = []
    for i, x in enumerate(raw):
        if isinstance(x, StepVariablesBase):
            out.append(x)
        elif isinstance(x, dict):
            out.append(StepVariablesBase.model_validate(x))
        else:
            raise ValueError(f"变量列表第 {i + 1} 项类型非法: {type(x).__name__}")
    return out


def step_tree_item_from_storage(data: Any) -> "AutoTestStepTreeUpdateItem":
    """
    唯一推荐入口：将仓储层 ``to_dict`` 得到的单步 JSON 转为 ``AutoTestStepTreeUpdateItem``。
    已为目标模型时直接返回；递归处理 ``children`` / ``quote_steps``。
    """
    if isinstance(data, AutoTestStepTreeUpdateItem):
        return data
    if not isinstance(data, dict):
        raise TypeError(f"步骤树节点必须为 dict 或 AutoTestStepTreeUpdateItem，当前: {type(data).__name__}")
    payload = dict(data)
    children_raw = payload.get("children") or []
    quotes_raw = payload.get("quote_steps") or []
    if children_raw and not isinstance(children_raw, list):
        raise ValueError("children 必须为数组或 null")
    if quotes_raw and not isinstance(quotes_raw, list):
        raise ValueError("quote_steps 必须为数组或 null")
    payload["children"] = [step_tree_item_from_storage(c) for c in children_raw] if children_raw else []
    payload["quote_steps"] = [step_tree_item_from_storage(q) for q in quotes_raw] if quotes_raw else []
    return AutoTestStepTreeUpdateItem.model_validate(payload)


def prepare_step_tree_item_for_execution(step: AutoTestStepTreeUpdateItem) -> AutoTestStepTreeUpdateItem:
    """执行前在模型上去除 case/quote_case，并递归子树（不做 model_dump 往返）。"""
    children = [prepare_step_tree_item_for_execution(c) for c in (step.children or [])]
    quotes = [prepare_step_tree_item_for_execution(q) for q in (step.quote_steps or [])]
    return step.model_copy(
        update={
            "case": None,
            "quote_case": None,
            "children": children or None,
            "quote_steps": quotes or None,
        }
    )


# 允许递归引用
AutoTestApiStepBase.model_rebuild()
AutoTestStepTreeUpdateItem.model_rebuild()
AutoTestCaseStepTreeLoadResult.model_rebuild()
