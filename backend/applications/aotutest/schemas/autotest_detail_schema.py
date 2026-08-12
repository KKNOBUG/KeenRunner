# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_schema
@DateTime: 2025/11/27 10:42
"""
from typing import Optional, List, Dict, Any, Type, Union

import orjson
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestStepType, HTTPMethod, AutoTestReqArgsType, AutoTestAssertionOperation

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class DataBaseOperates(BaseModel):
    """步骤执行明细中的单条数据库操作字段模型。"""

    index: int = Field(..., ge=0, description="数据库操作序号")
    name: str = Field(..., max_length=128, description="数据库操作名称")
    env_name: str = Field(..., max_length=128, description="数据库操作环境名称")
    expr: str = Field(..., max_length=4096, description="数据库操作SQL语句")
    project_id: int = Field(..., ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
    variable_name: List[str] = Field(..., description="存储变量名称")
    config_name: str = Field(..., max_length=128, description="所属环境配置名称")
    database_name: str = Field(..., max_length=128, description="所属数据库名称")
    desc: Optional[str] = Field(None, max_length=2048, description="数据库操作描述")


class RedisOperates(BaseModel):
    """步骤执行明细中的单条Redis操作字段模型。"""

    index: int = Field(..., ge=0, description="Redis操作序号")
    name: str = Field(..., max_length=128, description="Redis操作名称")
    env_name: str = Field(..., max_length=128, description="Redis操作环境名称")
    expr: str = Field(..., max_length=4096, description="Redis命令")
    project_id: int = Field(..., ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
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
            raise ValueError("条件比较符不能为空")
        return AutoTestAssertionOperation(str(v).strip()).value


class AutoTestApiDetailReqBase(BaseModel):
    """步骤执行明细请求字段基础模型。"""

    request_url: Optional[str] = Field(default=None, max_length=2048, description="实际发出的请求地址")
    request_port: Optional[str] = Field(default=None, max_length=16, description="实际发出的请求端口")
    request_method: Optional[HTTPMethod] = Field(default=None, max_length=16, description="实际发出的请求方法")
    request_args_type: Optional[AutoTestReqArgsType] = Field(default=None, description="实际发出的请求参数类型")
    request_project_id: Optional[int] = Field(default=None, ge=1, description="实际发出的请求应用ID")
    request_config_name: Optional[str] = Field(default=None, max_length=128, description="实际发出的请求环境配置名称")
    request_env_name: Optional[str] = Field(default=None, max_length=128, description="实际发出的请求环境名称")
    request_header: NON_DICT_TYPE = Field(default=None, description="实际发出的请求头")
    request_params: NON_DICT_TYPE = Field(default=None, description="实际发出的请求参数")
    request_form_data: NON_DICT_TYPE = Field(default=None, description="实际发出的表单数据")
    request_form_urlencoded: NON_DICT_TYPE = Field(default=None, description="实际发出的 urlencoded 键值对")
    request_form_file: NON_DICT_TYPE = Field(default=None, description="实际发出的表单文件项")
    request_body: NON_DICT_TYPE = Field(default=None, description="实际发出的请求体(JSON)")
    request_text: Optional[str] = Field(default=None, description="实际发出的请求体(Raw)")


class AutoTestApiDetailResBase(BaseModel):
    """步骤执行明细响应字段基础模型。"""

    response_cookie: NON_DICT_TYPE = Field(default=None, description="响应信息(cookies)")
    response_header: NON_DICT_TYPE = Field(default=None, description="响应信息(headers)")
    response_body: Union[NON_DICT_TYPE, NON_LIST_DICT_TYPE] = Field(default=None, description="响应信息(body)")
    response_text: Optional[str] = Field(default=None, description="响应信息(text)")
    response_elapsed: Optional[str] = Field(default=None, max_length=16, description="响应信息(elapsed)")


class AutoTestApiDetailVarBase(BaseModel):
    """步骤执行明细变量/断言/操作快照基础字段模型。"""

    conditions: Optional[ConditionsBase] = Field(default=None, description="本次执行条件/循环判断条件")
    session_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="会话变量(所有步骤的执行结果持续累积)")
    defined_variables: Optional[List[StepVariablesBase]] = Field(default=None, description="定义变量(用户自定义、引用函数的结果)")
    extract_variables: NON_LIST_DICT_TYPE = Field(default=None, description="提取变量(从请求控制器、上下文中提取、执行代码结果)")
    assert_validators: NON_LIST_DICT_TYPE = Field(default=None, description="断言规则(支持对数据对象进行不同表达式的断言验证)")
    database_operates: Optional[List[DataBaseOperates]] = Field(default=None, description="数据库请求操作列表")
    redis_operates: Optional[List[RedisOperates]] = Field(default=None, description="Redis请求操作列表")
    datagram_field_compare: NON_LIST_DICT_TYPE = Field(default=None, description="报文比对配置列表(快照)")
    datagram_field_ordered: Optional[int] = Field(default=None, ge=0, le=1, description="报文比对默认字段顺序控制(快照,0忽略顺序,1控制顺序)")
    step_exec_logger: Optional[str] = Field(default=None, description="步骤执行日志(多行文本)")
    step_exec_except: Optional[str] = Field(default=None, description="步骤错误描述")

    @field_validator("session_variables", "defined_variables", "extract_variables", "assert_validators", "datagram_field_compare", mode="before")
    @classmethod
    def _empty_list_to_none(cls, v: Any) -> Any:
        """
        session_variables/defined_variables/extract_variables/assert_validators/datagram_field_compare字段空数组时归一为null值。

        :param v: 原始值
        :return: 空数组时返回None，其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v

    @field_validator("step_exec_logger", mode="before")
    @classmethod
    def normalize_step_exec_logger(cls, v: Any) -> Optional[str]:
        """
        将step_exec_logger规范为多行文本或null。
        兼容引擎传入的 List[str]：过滤空项后以换行拼接。

        :param v: 原始日志字段（str / List[str] / null）
        :return: 规范化后的日志文本，全空则返回 None
        """
        if v is None:
            return None
        if isinstance(v, list):
            out = [str(x) for x in v if x is not None and str(x) != ""]
            return "\n".join(out) if out else None
        text = str(v).strip()
        return text or None

    @field_validator('database_operates', mode='before')
    @classmethod
    def normalize_database_operates(cls, v):
        """
        将单条 database_operates 对象包装为列表。

        :param v: 原始值（null/dict/list）
        :return: 列表形式或原值
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v or None
        return v

    @field_validator('redis_operates', mode='before')
    @classmethod
    def normalize_redis_operates(cls, v):
        """
        将单条redis_operates对象包装为列表。

        :param v: 原始值（null/dict/list）
        :return: 列表形式或原值
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v or None
        return v

    @model_validator(mode='before')
    @classmethod
    def normalize_json_fields(cls, v):
        """
        将嵌套模型/复杂字段转为可JSON序列化结构；失败时置空并写入step_exec_logger。

        :param v: 原始入参字典或其它类型
        :return: 规范化后的入参
        """
        if not isinstance(v, dict):
            return v
        executive_logger: List[str] = []
        conditions_value: Optional[ConditionsBase] = v.get("conditions")
        if conditions_value:
            try:
                v["conditions"] = conditions_value.model_dump()
            except Exception as e:
                v["conditions"] = None
                executive_logger.append(f"字段[conditions]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        session_variables_value: Optional[List[StepVariablesBase]] = v.get("session_variables")
        if session_variables_value:
            try:
                v["session_variables"] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in session_variables_value
                ]
            except Exception as e:
                v["session_variables"] = None
                executive_logger.append(f"字段[session_variables]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        defined_variables_value: Optional[List[StepVariablesBase]] = v.get("defined_variables")
        if defined_variables_value:
            try:
                v["defined_variables"] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in defined_variables_value
                ]
            except Exception as e:
                v["defined_variables"] = None
                executive_logger.append(f"字段[defined_variables]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        extract_variables_value: Optional[List[Dict[str, Any]]] = v.get("extract_variables")
        if extract_variables_value:
            try:
                v["extract_variables"] = orjson.loads(orjson.dumps(extract_variables_value))
            except Exception as e:
                v["extract_variables"] = None
                executive_logger.append(f"字段[extract_variables]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        assert_validators_value: Optional[List[Dict[str, Any]]] = v.get("assert_validators")
        if assert_validators_value:
            try:
                v["assert_validators"] = orjson.loads(orjson.dumps(assert_validators_value))
            except Exception as e:
                v["assert_validators"] = None
                executive_logger.append(f"字段[assert_validators]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        database_operates_value: Optional[List[Dict[str, Any]]] = v.get("database_operates")
        if database_operates_value:
            try:
                v["database_operates"] = orjson.loads(orjson.dumps(database_operates_value))
            except Exception as e:
                v["database_operates"] = None
                executive_logger.append(f"字段[database_operates]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        datagram_field_compare_value = v.get("datagram_field_compare")
        if datagram_field_compare_value:
            try:
                v["datagram_field_compare"] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in datagram_field_compare_value
                ]
            except Exception as e:
                v["datagram_field_compare"] = None
                executive_logger.append(f"字段[datagram_field_compare]标准化失败, 无法写入, 已置空, 错误描述: {e}")

        if executive_logger:
            base = v.get("step_exec_logger")
            extra = "\n".join(str(x) for x in executive_logger if x is not None and str(x) != "")
            if extra:
                if base is None or base == "":
                    v["step_exec_logger"] = extra
                elif isinstance(base, list):
                    base_list = [str(x) for x in base if x is not None and str(x) != ""]
                    v["step_exec_logger"] = "\n".join(base_list + [str(x) for x in executive_logger])
                else:
                    v["step_exec_logger"] = f"{base}\n{extra}"

        return v


class AutoTestApiDetailBase(AutoTestApiDetailReqBase, AutoTestApiDetailVarBase, AutoTestApiDetailResBase):
    """步骤执行明细公共字段。"""

    quote_case_id: Optional[int] = Field(default=None, ge=1, description="引用公共脚本ID")
    step_st_time: Optional[str] = Field(default=None, max_length=255, description="步骤执行开始时间")
    step_ed_time: Optional[str] = Field(default=None, max_length=255, description="步骤执行结束时间")
    step_elapsed: Optional[str] = Field(default=None, max_length=16, description="步骤执行消耗时间")
    num_cycles: Optional[int] = Field(default=None, le=100, description="循环执行次数(第几次)")

    code: Optional[str] = Field(default=None, description="本次执行使用的代码(Python)")
    wait: Optional[float] = Field(default=None, ge=0, description="本次执行等待时间")
    loop_mode: Optional[Any] = Field(default=None, description="本次执行循环模式")
    loop_maximums: Optional[int] = Field(default=None, ge=1, description="本次执行最大循环次数")
    loop_interval: Optional[float] = Field(default=None, ge=0, description="本次执行循环间隔")
    loop_iterable: Optional[str] = Field(default=None, max_length=512, description="本次执行循环对象来源")
    loop_on_error: Optional[Any] = Field(default=None, description="本次执行循环错误策略")
    loop_timeout: Optional[float] = Field(default=None, ge=0, description="本次执行条件循环超时")
    database_searched: Optional[bool] = Field(default=None, description="本次执行是否启用数据库查到即止")
    redis_searched: Optional[bool] = Field(default=None, description="本次执行是否启用Redis查到即止")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")

    # 参数化驱动：本步骤执行使用的数据集名称和该步骤的数据快照，记录在明细中
    dataset_name: Optional[str] = Field(default=None, max_length=255, description="本步骤执行对应的数据集名称")
    dataset_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="本步骤执行使用的数据快照")


class AutoTestApiDetailCreate(AutoTestApiDetailBase):
    """创建步骤执行明细入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    step_id: int = Field(..., ge=1, description="步骤ID")
    step_no: int = Field(..., ge=1, description="步骤序号")
    step_name: str = Field(..., max_length=255, description="步骤名称")
    step_code: str = Field(..., max_length=64, description="步骤标识代码")
    step_type: AutoTestStepType = Field(..., description="步骤类型")
    step_state: bool = Field(..., description="步骤执行状态")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class AutoTestApiDetailUpdate(AutoTestApiDetailBase):
    """更新步骤执行明细入参。"""

    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    detail_id: Optional[int] = Field(None, description="明细ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiDetailSelect(BaseModel):
    """分页查询步骤执行明细入参。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["step_st_time"], description="排序字段")

    case_id: Optional[int] = Field(None, description="用例ID")
    case_code: Optional[str] = Field(None, max_length=64, description="用例标识代码")
    quote_case_id: Optional[int] = Field(None, description="引用公共脚本ID")
    report_code: Optional[str] = Field(None, description="报告标识代码")

    step_id: Optional[int] = Field(None, description="步骤ID")
    step_no: Optional[int] = Field(None, description="步骤序号")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态(True:成功, False:失败)")

    detail_id: Optional[int] = Field(None, description="明细ID")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")
