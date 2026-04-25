# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_schema
@DateTime: 2025/11/27 10:42
"""
import json
from typing import Optional, List, Dict, Any, Type, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.applications.base.services.scaffold import UpperStr
from backend.enums import AutoTestStepType, HTTPMethod, AutoTestReqArgsType

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]


class DataBaseOperates(BaseModel):
    name: str = Field(..., max_length=128, description="数据库操作名称")
    expr: str = Field(..., max_length=4096, description="数据库操作SQL语句")
    project_id: int = Field(..., ge=1, description="所属应用ID")
    project_name: str = Field(..., max_length=128, description="所属应用名称")
    variable_name: List[str] = Field(..., description="存储变量名称")
    config_name: str = Field(..., max_length=128, description="所属环境配置名称")
    database_name: str = Field(..., max_length=128, description="所属数据库名称")
    desc: Optional[str] = Field(None, max_length=2048, description="数据库操作描述")


class AutoTestApiDetailReqBase(BaseModel):
    request_url: Optional[str] = Field(default=None, max_length=2048, description="实际发出的请求地址")
    request_port: Optional[str] = Field(default=None, max_length=16, description="实际发出的请求端口")
    request_method: Optional[HTTPMethod] = Field(default=None, max_length=16, description="实际发出的请求方法")
    request_args_type: Optional[AutoTestReqArgsType] = Field(default=None, description="实际发出的请求参数类型")
    request_project_id: Optional[int] = Field(default=None, ge=1, description="实际发出的请求应用ID")
    request_header: NON_DICT_TYPE = Field(default=None, description="实际发出的请求头")
    request_params: NON_DICT_TYPE = Field(default=None, description="实际发出的请求参数")
    request_form_data: NON_DICT_TYPE = Field(default=None, description="实际发出的表单数据")
    request_form_urlencoded: NON_DICT_TYPE = Field(default=None, description="实际发出的 urlencoded 键值对")
    request_form_file: NON_DICT_TYPE = Field(default=None, description="实际发出的表单文件项")
    request_body: NON_DICT_TYPE = Field(default=None, description="实际发出的请求体(JSON)")
    request_text: Optional[str] = Field(default=None, description="实际发出的请求体(Raw)")


class AutoTestApiDetailResBase(BaseModel):
    response_cookie: NON_DICT_TYPE = Field(default=None, description="响应信息(cookies)")
    response_header: NON_DICT_TYPE = Field(default=None, description="响应信息(headers)")
    response_body: Union[NON_DICT_TYPE, NON_LIST_DICT_TYPE] = Field(default=None, description="响应信息(body)")
    response_text: Optional[str] = Field(default=None, description="响应信息(text)")
    response_elapsed: Optional[str] = Field(default=None, max_length=16, description="响应信息(elapsed)")


class AutoTestApiDetailVarBase(BaseModel):
    session_variables: Optional[List[StepVariablesBase]] = Field(
        default=None, description="会话变量(包含提取变量，以及前后code设置的变量), 项为 key/value/desc"
    )
    defined_variables: Optional[List[StepVariablesBase]] = Field(
        default=None, description="定义变量(自定义变量，如编写指定值或引用随机函数), 项为 key/value/desc"
    )
    extract_variables: NON_LIST_DICT_TYPE = Field(
        default=None, description="提取结果(与步骤 extract 配置对应；使用 scope 表示 ALL/SOME)"
    )
    assert_validators: NON_LIST_DICT_TYPE = Field(default=None, description="断言规则(支持对各类数据对象进行不同表达式的断言验证)")
    database_operates: Optional[List[DataBaseOperates]] = Field(default=None, description="本次执行数据库操作明细快照(解析后的数据库请求操作列表)")
    step_exec_logger: Optional[str] = Field(default=None, description="步骤执行日志")
    step_exec_except: Optional[str] = Field(default=None, description="步骤错误描述")

    @field_validator('database_operates', mode='before')
    @classmethod
    def normalize_database_operates(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v
        return v

    @model_validator(mode='before')
    @classmethod
    def normalize_json_fields(cls, v):
        if not isinstance(v, dict):
            return v
        executive_logger: List[str] = []
        session_variables_value: Optional[List[Dict[str, Any]]] = v.get("session_variables")
        if session_variables_value:
            try:
                v["session_variables"] = json.loads(json.dumps(session_variables_value, ensure_ascii=False))
            except Exception as e:
                v["session_variables"] = None
                executive_logger.append(f"字段[session_variables]标准化失败, 已置空, 错误描述: {e}")

        defined_variables_value: Optional[List[Dict[str, Any]]] = v.get("defined_variables")
        if defined_variables_value:
            try:
                v["defined_variables"] = json.loads(json.dumps(defined_variables_value, ensure_ascii=False))
            except Exception as e:
                v["defined_variables"] = None
                executive_logger.append(f"字段[defined_variables]标准化失败, 已置空, 错误描述: {e}")

        extract_variables_value: Optional[List[Dict[str, Any]]] = v.get("extract_variables")
        if extract_variables_value:
            try:
                v["extract_variables"] = json.loads(json.dumps(extract_variables_value, ensure_ascii=False))
            except Exception as e:
                v["extract_variables"] = None
                executive_logger.append(f"字段[extract_variables]标准化失败, 已置空, 错误描述: {e}")

        assert_validators_value: Optional[List[Dict[str, Any]]] = v.get("assert_validators")
        if assert_validators_value:
            try:
                v["assert_validators"] = json.loads(json.dumps(assert_validators_value, ensure_ascii=False))
            except Exception as e:
                v["assert_validators"] = None
                executive_logger.append(f"字段[assert_validators]标准化失败, 已置空, 错误描述: {e}")

        database_operates_value: Optional[List[Dict[str, Any]]] = v.get("database_operates")
        if database_operates_value:
            try:
                v["database_operates"] = json.loads(json.dumps(database_operates_value, ensure_ascii=False))
            except Exception as e:
                v["database_operates"] = None
                executive_logger.append(f"字段[database_operates]标准化失败, 已置空, 错误描述: {e}")

        if executive_logger:
            step_exec_logger_est: Optional[str] = v.get("step_exec_logger")
            step_exec_logger_str: str = str(step_exec_logger_est) if step_exec_logger_est else ""
            add_executive_logger: str = "\n".join(executive_logger)
            v["step_exec_logger"] = step_exec_logger_str + ("\n" if step_exec_logger_str else "") + add_executive_logger

        return v


class AutoTestApiDetailBase(AutoTestApiDetailReqBase, AutoTestApiDetailVarBase, AutoTestApiDetailResBase):
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
    conditions: NON_DICT_TYPE = Field(default=None, description="本次执行条件/循环判断条件")
    database_searched: Optional[bool] = Field(default=None, description="本次执行是否启用数据库查到即止")
    state: Optional[int] = Field(default=0, description="状态(0:未删除, 1:删除, 2:执行成功, 3:执行失败)")

    # 参数化驱动：本步骤执行使用的数据集名称和该步骤的数据快照，记录在明细中
    dataset_name: Optional[str] = Field(default=None, max_length=255, description="本步骤执行对应的数据集名称(参数化)")
    dataset_snapshot: Optional[Dict[str, Any]] = Field(default=None, description="本步骤执行使用的数据快照(该步骤的 head/body/assert)")


class AutoTestApiDetailCreate(AutoTestApiDetailBase):
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
    case_id: int = Field(..., ge=1, description="用例ID")
    case_code: str = Field(..., max_length=64, description="用例标识代码")
    report_code: str = Field(..., max_length=64, description="报告标识代码")
    detail_id: Optional[int] = Field(None, description="明细ID")
    step_code: Optional[str] = Field(None, max_length=64, description="步骤标识代码")
    step_type: Optional[AutoTestStepType] = Field(None, description="步骤类型")
    step_state: Optional[bool] = Field(None, description="步骤执行状态")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")


class AutoTestApiDetailSelect(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: List[str] = Field(default=["step_st_time"], description="排序字段")

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
