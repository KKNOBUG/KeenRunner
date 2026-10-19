# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_schema.py
@DateTime: 2025/4/28
"""
import re
from typing import Optional, List, Dict, Any, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

from backend.applications.autotest.schemas.autotest_case_schema import AutoTestCaseUpdate
from backend.applications.autotest.schemas.autotest_datagram_diff_schema import DatagramFieldCompareItem
from backend.applications.base.services.scaffold import UpperStr
from backend.enums import (
    AutoTestStepType,
    AutoTestBranchType,
    AutoTestLoopMode,
    AutoTestReqArgsType,
    AutoTestLoopErrorStrategy,
    AutoTestAssertionOperation,
    AutoTestConfigNodeType,
    AutoTestTcpRadix,
    AutoTestTcpDatagramLength,
    AutoTestTcpConnectType,
    AutoTestTcpEndSymbol,
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
    """步骤定义中的单条Redis操作字段模型。"""

    name: str = Field(..., max_length=128, description="Redis操作名称")
    expr: str = Field(..., max_length=4096, description="Redis操作命令")
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

    @field_validator("condition_compare", mode="before")
    @classmethod
    def _validate_condition_compare(cls, v: Any) -> str:
        """
        校验并规范化条件比较符为AutoTestAssertionOperation枚举值。

        :param v: 原始比较符
        :return: 规范化后的比较符字符串
        """
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("参数[condition_compare]不允许为空")
        return AutoTestAssertionOperation(str(v).strip()).value


class BranchItem(BaseModel):
    """条件分支中的单个分支定义。"""

    branch_type: AutoTestBranchType = Field(..., description="分支类型")
    branch_conditions: Optional[ConditionsBase] = Field(None, description="分支条件")
    branch_desc: Optional[str] = Field(None, max_length=2048, description="分支描述")
    branch_children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="分支子步骤")

    @field_validator("branch_type", mode="before")
    @classmethod
    def _validate_branch_type(cls, v: Any) -> AutoTestBranchType:
        """
        校验并规范化branch_type为AutoTestBranchType枚举值。

        :param v: 原始值
        :return: 规范化后的AutoTestBranchType枚举值
        """
        if not isinstance(v, str) or not str(v).strip():
            raise ValueError(f"参数[branch_type]必须为[if|elif|else], 当前: {v!r}")
        try:
            return AutoTestBranchType(v.strip().lower())
        except ValueError:
            raise ValueError(f"参数[branch_type]必须为[if|elif|else], 当前: {v!r}")

    @model_validator(mode="after")
    def _validate_branch_conditions(self):
        if self.branch_type in (AutoTestBranchType.IF, AutoTestBranchType.ELIF) and not self.branch_conditions:
            raise ValueError(f"参数[branch_type]为[{self.branch_type}]时必须配置[branch_conditions]")
        if self.branch_type == AutoTestBranchType.ELSE and self.branch_conditions is not None:
            raise ValueError("参数[branch_type]为[else]时不允许配置[branch_conditions]")
        return self


class StepVariablesBase(BaseModel):
    """步骤变量键值对基础字段模型。"""

    key: str = Field(..., max_length=1024, description="会话变量(键)")
    value: Optional[Any] = Field(None, description="会话变量(值)")
    desc: Optional[str] = Field(None, max_length=2048, description="会话变量(描述)")

    @model_serializer(mode="plain")
    def _serialize_variables(self) -> Dict[str, Any]:
        # value=null是合法提取结果，外层dump带exclude_none时会递归过滤嵌套模型，导致明细快照丢失value键；用plain序列化器固化三键结构，使value=None不被剔除；
        return {"key": self.key, "value": self.value, "desc": self.desc}


class StepsExecuteConfigBase(BaseModel):
    """步骤执行时环境配置覆盖基础字段模型。"""

    env_name: str = Field(..., max_length=128, description="环境名称")
    config_type: AutoTestConfigNodeType = Field(..., description="配置类型")
    config_name: str = Field(..., max_length=128, description="配置名称")
    config_host: str = Field(..., max_length=128, description="配置主机")
    config_port: str = Field(..., max_length=8, description="配置端口")
    database_name: Optional[str] = Field(None, max_length=128, description="数据库名称")


class StepExtractVariableItem(BaseModel):
    """步骤定义中的单条提取规则。"""

    name: str = Field(..., max_length=256, description="提取项名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: Optional[str] = Field(None, max_length=4096, description="提取表达式")
    scope: Optional[str] = Field(None, max_length=32, description="ALL或SOME")
    index: Optional[int] = Field(None, description="多匹配时索引")


class StepAssertValidatorItem(BaseModel):
    """步骤定义中的单条断言。"""

    name: str = Field(..., max_length=256, description="断言名称")
    source: str = Field(..., max_length=128, description="数据源")
    expr: str = Field(..., max_length=4096, description="表达式")
    operation: str = Field(..., max_length=128, description="比较符")
    except_value: Any = Field(default=None, description="期待值")

    @field_validator("operation", mode="before")
    @classmethod
    def _validate_operation(cls, v: Any) -> str:
        """
        校验并规范化比较符为AutoTestAssertionOperation枚举值。

        :param v: 原始比较符
        :return: 规范化后的比较符字符串
        """
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("参数[operation]不允许为空")
        return AutoTestAssertionOperation(str(v).strip()).value


class AutoTestStepReqBase(BaseModel):
    """步骤请求相关基础字段模型。"""

    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, max_length=16, description="请求方法")
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

    # TCP请求帧配置（仅TCP步骤使用）；帧模式由字段组合推导：
    # 进制数≠不使用 → 长度前缀；进制数=不使用且任一结束符≠无 → 结束符；均未配置 → RAW
    tcp_radix: Optional[AutoTestTcpRadix] = Field(None, description="TCP报文头进制数")
    tcp_radix_length: Optional[int] = Field(None, ge=2, le=10, description="TCP长度位宽度")
    tcp_datagram_length: Optional[AutoTestTcpDatagramLength] = Field(None, description="TCP报文总长度")
    tcp_request_end_symbol: Optional[AutoTestTcpEndSymbol] = Field(None, description="TCP请求报文结束符")
    tcp_response_end_symbol: Optional[str] = Field(None, max_length=64, description="TCP响应报文结束符(自定义文本, 无或空=不使用)")
    tcp_connect_type: Optional[AutoTestTcpConnectType] = Field(None, description="TCP连接方式")
    tcp_encoding: Optional[str] = Field(None, max_length=32, description="TCP文本编码")
    tcp_hex_string: Optional[bool] = Field(None, description="TCP HEX报文开关")
    tcp_response_timeout: Optional[float] = Field(None, ge=0, description="TCP响应接收超时")

    @field_validator(
        "request_header",
        "request_params",
        "request_form_data",
        "request_form_urlencoded",
        "request_form_file",
        mode="before"
    )
    @classmethod
    def _validate_empty_request_fields(cls, v: Any) -> Any:
        """
        request_header/request_params/request_form_data/request_form_urlencoded/request_form_file字段空数组时归一为null值。

        :param v: 原始值
        :return: 空数组时返回None，其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v

    @model_validator(mode="after")
    def _normalize_tcp_frame_fields(self):
        """
        帧模式由tcp_radix字段确定互斥。

        进制数开启走长度前缀模式，结束符不适用，置为null值；
        进制数为空或不使用走结束符/RAW模式，长度位参数不适用，置为null值；

        :return: 当前模型实例
        """
        if self.tcp_radix in (None, AutoTestTcpRadix.NONE):
            self.tcp_radix_length = None
            self.tcp_datagram_length = None
        else:
            self.tcp_request_end_symbol = None
            self.tcp_response_end_symbol = None
        return self


class AutoTestStepDbBase(BaseModel):
    """步骤数据库操作基础字段模型。"""

    database_searched: Optional[bool] = Field(None, description="数据库请求查到即止开关")
    database_operates: Optional[List[DataBaseOperates]] = Field(None, description="数据库请求操作列表")

    @field_validator("database_operates", mode="before")
    @classmethod
    def _normalize_database_operates(cls, v: Any) -> Any:
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


class AutoTestStepRedisBase(BaseModel):
    """步骤Redis操作基础字段模型。"""

    redis_searched: Optional[bool] = Field(None, description="Redis请求查到即止开关")
    redis_operates: Optional[List[RedisOperates]] = Field(None, description="Redis请求操作列表")

    @field_validator("redis_operates", mode="before")
    @classmethod
    def _normalize_redis_operates(cls, v: Any) -> Any:
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


class AutoTestStepVarBase(BaseModel):
    """步骤变量/提取/断言基础字段模型。"""

    session_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables: Optional[List[StepExtractVariableItem]] = Field(default=None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: Optional[List[StepAssertValidatorItem]] = Field(default=None, description="断言规则(支持对数据对象进行不同表达式的断言验证)")

    @field_validator("defined_variables", "session_variables", "extract_variables", "assert_validators", mode="before")
    @classmethod
    def _validate_fields_shape(cls, v: Any) -> Any:
        """
        校验defined_variables、session_variables、extract_variables、assert_validators字段类型。

        :param v: 原始值
        :return: 合法且非空时返回原值，空数组时返回None值
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(
                f"参数[session_variables｜defined_variables｜extract_variables｜assert_validators]必须为列表或null，当前类型: {type(v).__name__}"
            )
        return v or None


class AutoTestStepBase(AutoTestStepReqBase, AutoTestStepDbBase, AutoTestStepRedisBase, AutoTestStepVarBase):
    """步骤公共字段。"""

    model_config = ConfigDict(extra="ignore")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, ge=1, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_name: Optional[str] = Field(None, max_length=255, description="步骤名称")
    step_desc: Optional[str] = Field(None, description="步骤描述")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤所属类型")

    case_id: Optional[int] = Field(None, description="步骤所属用例")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本/接口ID")
    parent_step_id: Optional[int] = Field(None, description="父级步骤ID")
    step_is_skipped: Optional[bool] = Field(False, description="是否跳过执行")

    code: Optional[str] = Field(None, description="执行代码(Python)")
    wait: Optional[float] = Field(None, ge=0, le=300, description="等待控制")

    loop_mode: Optional[AutoTestLoopMode] = Field(None, description="循环模式类型")
    loop_maximums: Optional[str] = Field(None, max_length=512, description="最大循环次数")
    loop_interval: Optional[float] = Field(None, ge=0, le=60, description="每次循环间隔时间")
    loop_iterable: Optional[str] = Field(None, max_length=512, description="循环对象来源")
    loop_on_error: Optional[AutoTestLoopErrorStrategy] = Field(None, description="循环执行失败时的处理策略")
    loop_timeout: Optional[float] = Field(None, ge=0, le=300, description="条件循环超时时间")
    loop_conditions: Optional[ConditionsBase] = Field(None, description="条件循环判断条件")
    # 循环变量名：允许用户自定义(嵌套循环时避免同名作用域冲突)，默认值由前端页面预填，后端以保存入库的为准
    loop_index: Optional[str] = Field(None, max_length=64, description="循环索引变量名")
    loop_key: Optional[str] = Field(None, max_length=64, description="循环键名变量名")
    loop_value: Optional[str] = Field(None, max_length=64, description="循环数据变量名")

    branch_items: Optional[List[BranchItem]] = Field(None, description="条件分支列表")
    branch_index: Optional[int] = Field(None, ge=0, description="所属分支序号")

    data_source_id: Optional[int] = Field(None, ge=1, description="数据源ID")
    data_source_name: Optional[str] = Field(None, max_length=2048, description="数据源名称")
    data_source_desc: Optional[str] = Field(None, max_length=2048, description="数据源描述")

    # 报文比对步骤：左右报文引用列表(每项自带datagram_field_ordered)
    datagram_field_compare: Optional[List[DatagramFieldCompareItem]] = Field(None, description="报文比对配置列表")

    state: Optional[int] = Field(default=0, description="状态")

    @field_validator("loop_maximums", mode="before")
    @classmethod
    def _normalize_loop_maximums(cls, v: Any) -> Any:
        """
        规范化loop_maximums：整数入参，统一存为字符串；字面量整数校验1-100，占位符交由执行期解析。

        :param v: 原始值（int/str/None）
        :return: 规范化后的字符串或None
        """
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("参数[loop_maximums]不允许为布尔值")
        if isinstance(v, int):
            if v < 1 or v > 100:
                raise ValueError("参数[loop_maximums]字面量必须为1-100的正整数")
            return str(v)
        if isinstance(v, float):
            if not v.is_integer() or v < 1 or v > 100:
                raise ValueError("参数[loop_maximums]字面量必须为1-100的正整数")
            return str(int(v))
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return None
            if text.isdigit():
                number = int(text)
                if number < 1 or number > 100:
                    raise ValueError("参数[loop_maximums]字面量必须为1-100的正整数")
                return text
            return text
        raise ValueError(f"参数[loop_maximums]必须为null、正整数或字符串，当前类型: {type(v).__name__}")

    @field_validator("loop_index", "loop_key", "loop_value", mode="before")
    @classmethod
    def _normalize_loop_var_name(cls, v: Any) -> Any:
        """
        规范化循环变量名：strip后为空存None(默认值由前端预填，后端以保存入库的为准)；
        变量名需可安全用于${name}占位符，禁止包含空白符、'${'、'}'。

        :param v: 原始值
        :return: 规范化后的变量名或None
        """
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError(f"参数[循环变量]必须为null或字符串，当前类型: {type(v).__name__}")
        text = v.strip()
        if not text:
            return None
        if len(text) > 64:
            raise ValueError("参数[循环变量]长度不允许超过64字符")
        if re.search(r"\s", text) or "${" in text or "}" in text:
            raise ValueError(f"参数[循环变量]不允许包含空白符、'${{'、'}}': \n\t当前值: {text!r}")
        return text

    @field_validator("loop_conditions", mode="before")
    @classmethod
    def _loop_conditions_must_be_object_or_none(cls, v: Any) -> Any:
        """
        校验loop_conditions为对象、ConditionsBase实例或null。

        :param v: 原始值
        :return: 原值（合法时）
        """
        if v is None:
            return None
        if isinstance(v, ConditionsBase):
            return v
        if isinstance(v, dict):
            return v
        raise ValueError(f"参数[loop_conditions]必须为null或对象，当前类型: {type(v).__name__}")

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

    @field_validator("datagram_field_compare", mode="before")
    @classmethod
    def _datagram_field_compare_list_shape(cls, v: Any) -> Any:
        """
        校验datagram_field_compare为数组或null；空数组归一为null。

        :param v: 原始值
        :return: 原值（合法且非空时），空数组返回None
        """
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError(f"参数[datagram_field_compare]必须为null或对象列表，当前类型: {type(v).__name__}")
        return v or None


class AutoTestStepChildren(BaseModel):
    """步骤子节点与引用步骤字段模型。"""

    children: Optional[List["AutoTestStepBase"]] = Field(None, description="子步骤")
    quote_steps: Optional[List["AutoTestStepBase"]] = Field(None, description="引用步骤")


class AutoTestStepCreate(AutoTestStepBase):
    """创建步骤入参。"""

    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_type: AutoTestStepType = Field(..., description="步骤所属类型")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestStepUpdate(AutoTestStepBase):
    """更新步骤入参。"""

    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestStepSelect(BaseModel):
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
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本/接口ID")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态")


class AutoTestStepTreeUpdateItem(AutoTestStepBase):
    """步骤树更新单节点入参。"""

    case: NON_DICT_TYPE = Field(None, description="用例信息")
    children: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="子步骤列表")
    quote_steps: Optional[List["AutoTestStepTreeUpdateItem"]] = Field(None, description="引用步骤列表")
    quote_case: Optional[Any] = Field(None, description="引用公共脚本/引用公共接口的用例信息")


class StepTreeCounter(BaseModel):
    """步骤树统计：与历史 get_case_tree 末尾元数据字段一致。"""
    direct_steps: int = 0
    child_steps: int = 0
    quote_steps: int = 0
    total_steps: int = 0


class AutoTestCaseStepTreeLoadResult(BaseModel):
    """仓储层从DB构建步骤树后的对外结果：根步骤均为已校验模型。"""
    root_steps: List["AutoTestStepTreeUpdateItem"] = Field(default_factory=list)
    step_counter: StepTreeCounter
    case_only_when_no_steps: Optional[AutoTestCaseUpdate] = Field(
        default=None,
        description="无任何根步骤时，与历史接口中单节点仅含case的占位信息对应"
    )


class AutoTestStepTreeUpdateList(BaseModel):
    """整棵步骤树更新入参。"""

    case: AutoTestCaseUpdate = Field(..., description="用例信息")
    steps: List[AutoTestStepTreeUpdateItem] = Field(..., description="步骤树数据")


class AutoTestHttpDebugRequest(AutoTestStepVarBase, AutoTestStepReqBase):
    """HTTP 步骤调试入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_url: str = Field(..., max_length=2048, description="请求地址")
    request_method: HTTPMethod = Field(..., description="请求方法")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestTcpDebugRequest(AutoTestStepVarBase, AutoTestStepReqBase):
    """TCP 步骤调试入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    request_text: Optional[str] = Field(None, description="请求体数据(Text格式)")
    request_project_id: int = Field(..., ge=1, description="请求应用ID")
    request_config_name: str = Field(..., max_length=128, description="请求环境配置名称")


class AutoTestPythonCodeDebugRequest(AutoTestStepVarBase):
    """Python代码步骤调试入参。"""

    step_name: str = Field(..., max_length=255, description="步骤名称")
    code: str = Field(..., description="执行代码(Python)")


class AutoTestRedisDebugRequest(AutoTestStepVarBase, AutoTestStepRedisBase):
    """Redis 步骤调试入参。"""

    env_name: str = Field(..., max_length=64, description="环境名称")
    step_name: str = Field(..., max_length=255, description="步骤名称")

    @model_validator(mode="after")
    def validate_redis_debug_request(self):
        """
        校验Redis调试请求至少包含一条redis_operates。

        :return: 当前模型实例
        """
        if not self.redis_operates:
            raise ValueError("参数[redis_operates]不允许为空, 请至少提供一条Redis操作配置")
        return self


class AutoTestCaseRunInfo(BaseModel):
    """执行/调试时传入引擎的用例上下文。"""
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    case_name: str = Field(..., max_length=255, description="用例名称")


class AutoTestStepTreeExecute(BaseModel):
    """步骤树执行/调试入参。"""

    case_id: int = Field(..., description="用例ID(运行模式和调试模式都必填)")
    steps: Optional[List[AutoTestStepTreeUpdateItem]] = Field(None, description="步骤树数据(调试模式必填, 运行模式不填)")
    initial_variables: Optional[List[StepVariablesBase]] = Field(None, description="会话变量(初始变量池)")
    steps_execute_config: Optional[Dict[str, StepsExecuteConfigBase]] = Field(default=None, description="脚本执行配置作用环境")
    selected_dataset_names: Optional[List[str]] = Field(None, description="选中的数据集名称列表，运行模式可选多条，调试模式仅可选1条")


class AutoTestBatchExecuteCases(BaseModel):
    """批量执行用例入参。"""

    env_name: Optional[str] = Field(None, description="执行环境名称")
    case_ids: List[int] = Field(..., min_length=1, description="用例ID列表")
    initial_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="会话变量(初始变量池)")


class AutoTestStepTreeSplice(BaseModel):
    """批量拼接多用例步骤树入参：case_ids与case_codes二选一，同时传递时以case_ids为准。"""

    case_ids: Optional[List[int]] = Field(None, min_length=1, description="用例ID列表")
    case_codes: Optional[List[str]] = Field(None, min_length=1, description="用例标识代码列表")


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
    TCP帧互斥脏数据由模型侧 _normalize_tcp_frame_fields 读取归一自愈，此处无需预处理。
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
AutoTestStepBase.model_rebuild()
BranchItem.model_rebuild()
AutoTestStepTreeUpdateItem.model_rebuild()
AutoTestCaseStepTreeLoadResult.model_rebuild()
