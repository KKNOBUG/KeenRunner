# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any, Type, Union

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
    AutoTestReportType,
)
from backend.enums import HTTPMethod

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class DataBaseOperates(BaseModel):
    """步骤定义中的单条数据库操作字段模型。"""

    name: str = Field(..., max_length=128, description="数据库操作名称")
    expr: str = Field(..., max_length=4096, description="数据库操作SQL语句")
    project_id: Optional[int] = Field(None, ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
    variable_name: str = Field(..., max_length=128, description="存储变量名称")
    config_name: str = Field(..., max_length=128, description="所属环境配置名称")
    database_name: str = Field(..., max_length=128, description="所属数据库名称")
    desc: Optional[str] = Field(None, max_length=2048, description="数据库操作描述")


class RedisOperates(BaseModel):
    """步骤定义中的单条 Redis 操作字段模型。"""

    name: str = Field(..., max_length=128, description="Redis操作名称")
    expr: str = Field(..., max_length=4096, description="Redis命令(支持多行)")
    project_id: Optional[int] = Field(None, ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
    variable_name: str = Field(..., max_length=128, description="存储变量名称")
    config_name: str = Field(..., max_length=128, description="所属环境配置名称")
    database_name: str = Field(..., max_length=128, description="Redis库编号")
    desc: Optional[str] = Field(None, max_length=2048, description="Redis操作描述")


class ConditionsBase(BaseModel):
    """条件/循环判断基础字段模型。"""

    condition_expr: str = Field(..., max_length=128, description="条件表达式")
    condition_compare: str = Field(..., max_length=128, description="条件比较符")
    condition_value: Optional[Any] = Field(None, description="条件比对值")
    condition_desc: Optional[str] = Field(None, max_length=2048, description="条件描述")

    @field_validator("condition_compare", mode="before")
    @classmethod
    def validate_condition_compare(cls, v: Any) -> str:
        """
        校验并规范化条件比较符为AutoTestAssertionOperation枚举值。

        :param v: 原始比较符
        :return: 规范化后的比较符字符串
        """
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("参数[condition_compare]不允许为空")
        return AutoTestAssertionOperation(str(v).strip()).value


class BranchItem(BaseModel):
    """条件分支中的单个分支定义（if/elif/else）。"""

    branch_type: str = Field(..., description="分支类型: if/elif/else")
    branch_conditions: Optional[ConditionsBase] = Field(None, description="分支条件(else时为null)")
    branch_desc: Optional[str] = Field(None, max_length=2048, description="分支描述")
    branch_children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="分支子步骤")

    @field_validator("branch_type", mode="before")
    @classmethod
    def validate_branch_type(cls, v: Any) -> str:
        if v.lower() not in ("if", "elif", "else"):
            raise ValueError(f"参数[branch_type]必须为[if|elif|else], 当前: {v!r}")
        return v.lower()

    @model_validator(mode="after")
    def validate_conditions_presence(self):
        if self.branch_type in ("if", "elif") and not self.branch_conditions:
            raise ValueError(f"参数[branch_type]为{self.branch_type}分支时必须配置[branch_conditions]")
        if self.branch_type == "else" and self.branch_conditions is not None:
            raise ValueError("参数[branch_type]为else分支时不允许配置[branch_conditions]")
        return self


class StepVariablesBase(BaseModel):
    """步骤变量键值对基础字段模型。"""

    key: str = Field(..., max_length=1024, description="会话变量(键)")
    value: Optional[Any] = Field(None, description="会话变量(值)")
    desc: Optional[str] = Field(None, max_length=2048, description="会话变量(描述)")


class StepsExecuteConfigBase(BaseModel):
    """步骤执行时环境配置覆盖基础字段模型。"""

    env_name: str = Field(..., max_length=128, description="环境名称")
    config_type: AutoTestConfigNodeType = Field(..., description="配置类型")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="配置主机")
    config_port: str = Field(..., max_length=8, description="配置端口")
    database_name: Optional[str] = Field(None, max_length=128, description="数据库名称")


class StepExtractVariableItem(BaseModel):
    """步骤定义中的单条提取规则；scope表示ALL/SOME，对应extract_from_source的range_type参数。"""
    name: str = Field(..., max_length=256, description="提取项名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: str = Field(..., max_length=4096, description="提取表达式")
    scope: Optional[str] = Field(None, max_length=32, description="ALL或SOME")
    index: Optional[int] = Field(None, description="多匹配时索引")


class StepAssertValidatorItem(BaseModel):
    """步骤定义中的单条断言，与 run_assert_validators 入参一致。"""

    name: str = Field(..., max_length=256, description="断言项名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: str = Field(..., max_length=4096, description="表达式")
    operation: str = Field(..., max_length=128, description="比较符")
    except_value: Any = Field(default=None, description="期待值")


class AutoTestApiStepReqBase(BaseModel):
    """步骤请求相关基础字段模型。"""

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
    tcp_frame_mode: Optional[str] = Field(None, max_length=64, description="TCP 帧模式，如length_prefix_json/raw")
    tcp_length_field_size: Optional[int] = Field(None, ge=1, le=32, description="长度前缀字段宽度")
    tcp_encoding: Optional[str] = Field(None, max_length=32, description="文本编码，如utf-8")
    tcp_connect_timeout: Optional[float] = Field(None, ge=0, description="连接超时（秒）")
    tcp_read_timeout: Optional[float] = Field(None, ge=0, description="读写超时（秒）")
    tcp_max_response_bytes: Optional[int] = Field(None, ge=1, description="最大读取字节数")
    tcp_response_type: Optional[str] = Field(None, max_length=16, description="响应解析：json|xml|text|bytes")

    @field_validator(
        "request_header", "request_params", "request_form_data", "request_form_urlencoded", "request_form_file",
        mode="before"
    )
    @classmethod
    def _empty_request_list_to_none(cls, v: Any) -> Any:
        """
        request_header/request_params/request_form_data/request_form_urlencoded/request_form_file字段空数组时归一为null值。

        :param v: 原始值
        :return: 空数组时返回None，其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v


class AutoTestApiStepDbBase(BaseModel):
    """步骤数据库操作基础字段模型。"""

    database_operates: Optional[List[DataBaseOperates]] = Field(None, description="数据库请求操作列表")
    database_searched: Optional[bool] = Field(None, description="数据库请求查到即止开关")

    @field_validator("database_operates", mode="before")
    @classmethod
    def normalize_database_operates(cls, v: Any) -> Any:
        """
        将database_operates规范为null或对象列表；单条dict包装为列表。

        :param v: 原始值
        :return: 规范化后的列表或None
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v or None
        raise ValueError(f"参数[database_operates]必须为null或对象列表，当前类型: {type(v).__name__}")


class AutoTestApiStepRedisBase(BaseModel):
    """步骤Redis操作基础字段模型。"""

    redis_operates: Optional[List[RedisOperates]] = Field(None, description="Redis请求操作列表")
    redis_searched: Optional[bool] = Field(None, description="Redis请求查到即止开关")

    @field_validator("redis_operates", mode="before")
    @classmethod
    def normalize_redis_operates(cls, v: Any) -> Any:
        """
        将redis_operates规范为null或对象列表；dict取其values作为列表。

        :param v: 原始值
        :return: 规范化后的列表或None
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return list(v.values()) if v else None
        if isinstance(v, list):
            return v or None
        raise ValueError(f"参数[redis_operates]必须为null或对象列表，当前类型: {type(v).__name__}")


class AutoTestApiStepVarBase(BaseModel):
    """步骤变量/提取/断言基础字段模型。"""

    session_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables: Optional[List[StepExtractVariableItem]] = Field(default=None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: Optional[List[StepAssertValidatorItem]] = Field(default=None, description="断言规则(支持对数据对象进行不同表达式的断言验证)")

    @field_validator("session_variables", mode="before")
    @classmethod
    def _session_variables_list_shape(cls, v: Any) -> Any:
        """
        校验session_variables为数组或null；空数组归一为null。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"参数[session_variables]必须为null或对象列表，当前类型: {type(v).__name__}")
        return v or None

    @field_validator("defined_variables", mode="before")
    @classmethod
    def _defined_variables_list_shape(cls, v: Any) -> Any:
        """
        校验defined_variables为数组或null；空数组归一为null。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"参数[defined_variables]必须为null或对象列表，当前类型: {type(v).__name__}")
        return v or None

    @field_validator("extract_variables", mode="before")
    @classmethod
    def _extract_variables_list_shape(cls, v: Any) -> Any:
        """
        校验 extract_variables 为数组或 null；空数组归一为 null。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"参数[extract_variables]必须为null或对象列表，当前类型: {type(v).__name__}")
        return v or None

    @field_validator("assert_validators", mode="before")
    @classmethod
    def _assert_validators_list_shape(cls, v: Any) -> Any:
        """
        校验assert_validators为数组或null；空数组归一为null。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"参数[assert_validators]必须为null或对象列表，当前类型: {type(v).__name__}")
        return v or None


class AutoTestApiStepBase(AutoTestApiStepReqBase, AutoTestApiStepDbBase, AutoTestApiStepRedisBase, AutoTestApiStepVarBase):
    """步骤公共字段（创建/更新/树节点共用）。"""

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
    step_is_skipped: Optional[bool] = Field(False, description="是否跳过执行(注释)，默认不跳过")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, ge=0, le=300, description="等待控制(正浮点数, 单位:秒)")
    loop_mode: Optional[AutoTestLoopMode] = Field(None, description="循环模式类型")
    loop_maximums: Optional[int] = Field(None, ge=1, le=100, description="最大循环次数(正整数)")
    loop_interval: Optional[float] = Field(None, ge=0, le=60, description="每次循环间隔时间(正浮点数)")
    loop_iterable: Optional[str] = Field(None, max_length=512, description="循环对象来源(变量名或可迭代对象)")
    loop_on_error: Optional[AutoTestLoopErrorStrategy] = Field(None, description="循环执行失败时的处理策略")
    loop_timeout: Optional[float] = Field(None, ge=0, le=3000, description="条件循环超时时间(正浮点数, 单位:秒, 0表示不超时)")
    data_source_id: Optional[int] = Field(None, ge=1, description="数据源ID")
    data_source_name: Optional[str] = Field(None, max_length=2048, description="数据源名称")
    data_source_desc: Optional[str] = Field(None, max_length=2048, description="数据源描述")
    conditions: Optional[ConditionsBase] = Field(None, description="判断条件(仅循环结构条件循环使用)")
    branch_items: Optional[List[BranchItem]] = Field(None, description="条件分支列表(仅条件分支步骤使用)")
    branch_index: Optional[int] = Field(None, ge=0, description="所属分支序号(后端推断, 前端无需传递)")

    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")

    @field_validator("conditions", mode="before")
    @classmethod
    def _conditions_must_be_object_or_none(cls, v: Any) -> Any:
        """
        校验conditions为对象、ConditionsBase实例或null。

        :param v: 原始值
        :return: 原值（合法时）
        """
        if v is None:
            return None
        if isinstance(v, ConditionsBase):
            return v
        if isinstance(v, dict):
            return v
        raise ValueError(f"参数[conditions]必须为null或对象列表，当前类型: {type(v).__name__}")

    @field_validator("branch_items", mode="before")
    @classmethod
    def _branch_items_must_be_list_or_none(cls, v: Any) -> Any:
        """
        校验branch_items为数组或null；空数组归一为null（条件分支至少存在一个分支）。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if isinstance(v, list):
            return v or None
        raise ValueError(f"参数[branch_items]必须为null或对象列表，当前类型: {type(v).__name__}")


class AutoTestApiStepChildren(BaseModel):
    """步骤子节点与引用步骤字段模型。"""

    children: Optional[List["AutoTestApiStepBase"]] = Field(None, description="子步骤")
    quote_steps: Optional[List["AutoTestApiStepBase"]] = Field(None, description="引用步骤")


class AutoTestApiStepCreate(AutoTestApiStepBase):
    """创建步骤入参。"""

    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_type: AutoTestStepType = Field(..., description="步骤所属类型")
    created_user: Optional[Union[UpperStr, str]] = Field(None, description="创建人员")


class AutoTestApiStepUpdate(AutoTestApiStepBase):
    """更新步骤入参。"""

    updated_user: Optional[Union[UpperStr, str]] = Field(None, description="更新人员")


class AutoTestApiStepSelect(BaseModel):
    """分页查询步骤入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["case_id", "step_no"], description="排序字段")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")

    case_id: Optional[int] = Field(None, description="用例ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本ID")
    created_user: Optional[Union[UpperStr, str]] = Field(None, description="创建人员")
    updated_user: Optional[Union[UpperStr, str]] = Field(None, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")


class AutoTestStepTreeUpdateItem(AutoTestApiStepBase):
    """步骤树更新单节点入参。"""

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
    """仓储层从DB构建步骤树后的对外结果：根步骤均为已校验模型。"""
    root_steps: List["AutoTestStepTreeUpdateItem"] = Field(default_factory=list)
    step_counter: StepTreeCounter
    case_only_when_no_steps: Optional[AutoTestApiCaseUpdate] = Field(default=None,
                                                                     description="无任何根步骤时，与历史接口中单节点仅含case的占位信息对应")


class AutoTestStepTreeUpdateList(BaseModel):
    """整棵步骤树更新入参。"""

    case: AutoTestApiCaseUpdate = Field(..., description="用例信息")
    steps: List[AutoTestStepTreeUpdateItem] = Field(..., description="步骤树数据")


class AutoTestHttpDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepReqBase):
    """HTTP 步骤调试入参。"""

    env_id: int = Field(..., ge=1, description="环境枚举ID")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_url: str = Field(..., max_length=2048, description="请求地址")
    request_method: HTTPMethod = Field(..., description="请求方法")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestTcpDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepReqBase):
    """TCP 步骤调试入参。"""

    env_id: int = Field(..., ge=1, description="环境枚举ID")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestPythonCodeDebugRequest(AutoTestApiStepVarBase):
    """Python 代码步骤调试入参。"""

    step_name: str = Field(..., max_length=255, description="步骤名称")
    code: str = Field(..., description="执行代码(Python)")


class AutoTestRedisDebugRequest(AutoTestApiStepVarBase, AutoTestApiStepRedisBase):
    """Redis 步骤调试入参。"""

    env_id: int = Field(..., ge=1, description="环境枚举ID")
    step_name: str = Field(..., max_length=255, description="步骤名称")

    @model_validator(mode="after")
    def validate_redis_debug_request(self):
        """
        校验 Redis 调试请求至少包含一条 redis_operates。

        :return: 当前模型实例
        """
        if not self.redis_operates:
            raise ValueError("参数[redis_operates]至少包含一条Redis操作配置")
        return self


class AutoTestCaseRunInfo(BaseModel):
    """执行/调试时传入引擎的用例上下文（与 ORM to_dict 的 case 摘要字段对齐）。"""
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_name: str = Field(..., max_length=255, description="用例名称")


class AutoTestStepTreeExecute(BaseModel):
    """步骤树执行/调试入参。"""

    case_id: int = Field(..., description="用例ID")
    execute_type: AutoTestReportType = Field(..., description="执行类型(复用AutoTestReportType枚举)")
    steps: Optional[List[AutoTestStepTreeUpdateItem]] = Field(None, description="步骤树数据(DEBUG_EXEC必填；ASYNC_EXEC/SCHEDULE_EXEC不填)")
    initial_variables: Optional[List[StepVariablesBase]] = Field(default_factory=list, description="初始变量池(列表项为key/value/desc)")
    # 脚本执行配置：key=步骤ID(step_id) 或 @@{step_name}（当步骤未落库时），value=配置明细；空 dict 表示该步骤无配置覆盖
    # { step_id 或 @@step_name: {env_name, config_type(api|database|file), config_name, config_host, config_port, database_name} }
    steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = Field(default_factory=dict, description="脚本执行配置作用环境")
    # 参数化驱动：ASYNC_EXEC/SCHEDULE_EXEC可传多条；DEBUG_EXEC仅可选一条
    selected_dataset_names: Optional[List[str]] = Field(None, description="选中的数据集名称(列表运行/定时模式可选多条；调试模式仅可选一条)")

    @model_validator(mode='after')
    def validate_execute_request(self):
        """
        根据execute_type校验steps是否必填或禁止传递。

        :return: 当前模型实例
        """
        if self.case_id is None:
            raise ValueError("参数[case_id]不允许为空")
        has_steps = bool(self.steps)
        et = self.execute_type
        if et == AutoTestReportType.DEBUG_EXEC:
            if not has_steps:
                raise ValueError("参数[execute_type]为DEBUG_EXEC时必须传递[steps]")
        elif et in (AutoTestReportType.ASYNC_EXEC, AutoTestReportType.SCHEDULE_EXEC):
            if has_steps:
                raise ValueError("参数[execute_type]非DEBUG_EXEC时无须传递[steps]")
        return self


class AutoTestBatchExecuteCases(BaseModel):
    """批量执行用例入参。"""

    env_name: Optional[str] = Field(None, description="执行环境名称")
    case_ids: List[int] = Field(..., min_length=1, description="用例ID列表")
    initial_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="初始变量池(列表项为key/value/desc)")


def step_variables_list_from_storage(raw: Any) -> List[StepVariablesBase]:
    """ORM/JSON 边界：将存库的变量列表转为StepVariablesBase列表。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"必须为null或对象列表，当前类型: {type(raw).__name__}")
    out: List[StepVariablesBase] = []
    for i, x in enumerate(raw):
        if isinstance(x, StepVariablesBase):
            out.append(x)
        elif isinstance(x, dict):
            out.append(StepVariablesBase.model_validate(x))
        else:
            raise ValueError(f"变量列表第{i + 1}项类型非法: {type(x).__name__}")
    return out


def step_tree_item_from_storage(data: Any) -> "AutoTestStepTreeUpdateItem":
    """
    将仓储层to_dict得到的单步JSON转为AutoTestStepTreeUpdateItem。
    已为目标模型时直接返回；递归处理children/quote_steps/branch_items。
    """
    if isinstance(data, AutoTestStepTreeUpdateItem):
        return data
    if not isinstance(data, dict):
        raise TypeError(f"步骤树节点必须为Dict序列化结构或AutoTestStepTreeUpdateItem对象，当前: {type(data).__name__}")
    payload = dict(data)
    children_raw = payload.get("children") or []
    quotes_raw = payload.get("quote_steps") or []
    if children_raw and not isinstance(children_raw, list):
        raise ValueError("参数[children]必须为null或对象列表")
    if quotes_raw and not isinstance(quotes_raw, list):
        raise ValueError("参数[quote_steps]必须为null或对象列表")
    payload["children"] = [step_tree_item_from_storage(c) for c in children_raw] if children_raw else []
    payload["quote_steps"] = [step_tree_item_from_storage(q) for q in quotes_raw] if quotes_raw else []
    branch_items_raw = payload.get("branch_items")
    if branch_items_raw and isinstance(branch_items_raw, list):
        for branch in branch_items_raw:
            if isinstance(branch, dict) and branch.get("branch_children"):
                branch["branch_children"] = [step_tree_item_from_storage(c) for c in branch["branch_children"]]
    return AutoTestStepTreeUpdateItem.model_validate(payload)


def prepare_step_tree_item_for_execution(step: AutoTestStepTreeUpdateItem) -> AutoTestStepTreeUpdateItem:
    """执行前在模型上去除case/quote_case数据，并递归子树（不做model_dump往返）。"""
    children = [prepare_step_tree_item_for_execution(c) for c in (step.children or [])]
    quotes = [prepare_step_tree_item_for_execution(q) for q in (step.quote_steps or [])]
    update: Dict[str, Any] = {
        "case": None,
        "quote_case": None,
        "children": children or None,
        "quote_steps": quotes or None,
    }
    if step.branch_items:
        prepared_branches = []
        for branch in step.branch_items:
            branch_children = [prepare_step_tree_item_for_execution(c) for c in (branch.branch_children or [])]
            prepared_branches.append(branch.model_copy(update={"branch_children": branch_children or None}))
        update["branch_items"] = prepared_branches
    return step.model_copy(update=update)


# 允许递归引用
AutoTestApiStepBase.model_rebuild()
BranchItem.model_rebuild()
AutoTestStepTreeUpdateItem.model_rebuild()
AutoTestCaseStepTreeLoadResult.model_rebuild()
