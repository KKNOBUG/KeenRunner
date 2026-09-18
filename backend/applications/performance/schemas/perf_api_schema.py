# -*- coding: utf-8 -*-
"""
压测接口资产入参契约。

一个压测接口 = 一个可独立施压的 HTTP/TCP 请求 + 其断言 + 其变量提取, 是施压热路径的唯一合法单元。
请求块字段名与 krun_autotest_step 逐字对齐, 使「从公共接口/HTTP步骤导入」退化为纯字段搬运。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_api_schema.py
@DateTime: 2026/9/15 15:40
"""
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.applications.base.services.scaffold import UpperStr
from backend.enums import (
    AutoTestAssertionOperation,
    AutoTestReqArgsType,
    AutoTestStepType,
    HTTPMethod,
    PerfApiSource,
)

NON_DICT_TYPE: Type = Optional[Dict[str, Any]]
NON_LIST_DICT_TYPE: Type = Optional[List[Dict[str, Any]]]

# 可施压的请求类型: 引擎当前仅有 HTTP 客户端, TCP 施压待阶段二实现(保存放行、执行前闸门拦截)
PERF_API_STEP_TYPES = (AutoTestStepType.HTTP, AutoTestStepType.TCP)
# 断言/提取来源合法值: 必须与 locust_engine/request_executor.py 的 EXTRACTORS 注册表键逐字一致。
# 引擎能力边界是口径单点, 此处镜像声明只为入参早失败, 引擎新增来源须两侧同步
PERF_ASSERT_SOURCES = (
    "response json", "request json", "response text", "request text",
    "response headers", "request headers", "response cookie", "request cookie",
    "request form-data", "session_variables", "变量池",
)


def _has_text(value: Optional[str]) -> bool:
    """非空字符串判断。"""
    return bool((value or "").strip())


class RequestKvItem(BaseModel):
    """键值对配置项(请求头/请求参数/变量池通用)，与 step 容器字段元素结构一致。"""

    key: str = Field(..., min_length=1, max_length=255, description="键名")
    value: Optional[Any] = Field(None, description="键值")
    desc: Optional[str] = Field(None, max_length=2048, description="描述")


class AssertValidatorItem(BaseModel):
    """业务断言配置项(与 step 断言元素同构)；source 合法值按引擎注册表校验。"""

    name: str = Field(..., min_length=1, max_length=255, description="断言名称")
    expr: str = Field(..., min_length=1, max_length=1024, description="断言表达式")
    source: str = Field(..., min_length=1, max_length=64, description="断言来源(引擎EXTRACTORS注册表键, 如 response json)")
    operation: AutoTestAssertionOperation = Field(..., description="比较方式(复用断言操作符枚举)")
    except_value: Optional[Any] = Field(None, description="期望值")

    @field_validator("source", mode="before")
    @classmethod
    def _validate_source(cls, v: Any) -> str:
        """断言来源必须在引擎支持清单内(引擎无DB/Redis回退分支, 不支持即拒绝)。"""
        source = str(v or "").strip()
        if source not in PERF_ASSERT_SOURCES:
            raise ValueError(f"参数[source]不支持, 当前: {source!r}, 可选: {list(PERF_ASSERT_SOURCES)}")
        return source


class ExtractVariableItem(BaseModel):
    """变量提取配置项(与 step 提取元素同构)；提取结果写入场景级变量池供后续请求渲染。"""

    name: str = Field(..., min_length=1, max_length=255, description="变量名(占位符 ${name})")
    expr: Optional[str] = Field(None, max_length=1024, description="提取表达式(SOME必填, ALL可省略)")
    source: str = Field(..., min_length=1, max_length=64, description="提取来源(引擎EXTRACTORS注册表键)")
    scope: Optional[str] = Field(None, max_length=32, description="ALL或SOME")
    index: Optional[int] = Field(None, description="多匹配时索引")

    @field_validator("source", mode="before")
    @classmethod
    def _validate_source(cls, v: Any) -> str:
        """提取来源必须在引擎支持清单内。"""
        source = str(v or "").strip()
        if source not in PERF_ASSERT_SOURCES:
            raise ValueError(f"参数[source]不支持, 当前: {source!r}, 可选: {list(PERF_ASSERT_SOURCES)}")
        return source


class PerfApiRequestBlock(BaseModel):
    """
    请求定义公共块(与 krun_autotest_step 请求字段同构)。

    request_url 允许是相对路径: 施压目标 host/port 由执行管线按环境实时解析后补齐, 不落库。
    """

    step_type: AutoTestStepType = Field(default=AutoTestStepType.HTTP, description="请求类型(HTTP请求/TCP请求)")
    request_url: Optional[str] = Field(None, max_length=2048, description="请求地址(可相对路径, 含${}占位符)")
    request_port: Optional[str] = Field(None, max_length=16, description="请求端口")
    request_method: Optional[HTTPMethod] = Field(None, description="请求方法(GET/POST/PUT/DELETE等)")
    request_header: NON_LIST_DICT_TYPE = Field(None, description="请求头信息")
    request_params: NON_LIST_DICT_TYPE = Field(None, description="请求路径参数")
    request_form_data: NON_LIST_DICT_TYPE = Field(None, description="请求表单数据(form-data)")
    request_form_urlencoded: NON_LIST_DICT_TYPE = Field(None, description="请求键值对数据(x-www-form-urlencoded)")
    request_form_file: NON_LIST_DICT_TYPE = Field(None, description="请求文件路径")
    request_text: Optional[str] = Field(None, description="原始请求体文本(raw/xml)")
    request_body: NON_DICT_TYPE = Field(None, description="请求体数据(json)")
    request_args_type: Optional[AutoTestReqArgsType] = Field(None, description="请求参数类型")
    # 施压目标定位: 应用 + APP节点配置名, 与功能用例同一解析口径
    request_project_id: Optional[int] = Field(None, ge=1, description="请求目标应用ID")
    request_config_name: Optional[str] = Field(None, max_length=128, description="请求目标环境配置名称(APP节点)")

    @field_validator(
        "request_header", "request_params", "request_form_data",
        "request_form_urlencoded", "request_form_file",
        mode="before",
    )
    @classmethod
    def _empty_request_list_to_none(cls, v: Any) -> Any:
        """
        请求容器字段空数组时归一为null值(与步骤 schema 同口径, 避免 {} 与 [] 两种空态)。

        :param v: 原始值
        :return: 空数组返回None, 其余原样返回
        """
        if isinstance(v, list) and not v:
            return None
        return v


class PerfApiBase(PerfApiRequestBlock):
    """压测接口公共字段。"""

    api_project: int = Field(..., ge=1, description="接口所属应用")
    api_name: str = Field(..., min_length=1, max_length=255, description="接口名称")
    api_desc: Optional[str] = Field(None, max_length=2048, description="接口描述")
    extract_variables: Optional[List[ExtractVariableItem]] = Field(None, description="变量提取规则列表")
    assert_validators: Optional[List[AssertValidatorItem]] = Field(None, description="业务断言规则列表")

    @model_validator(mode="after")
    def _require_pressable_definition(self):
        """
        校验施压单元语义: 请求类型必须在可施压清单内, 且 HTTP 请求必须有方法与非相对化不了的地址。

        结构性缺失若不在保存期拦截, 会在施压期以「0 请求数」的假结果骗过判定, 排查成本极高。
        """
        if self.step_type not in PERF_API_STEP_TYPES:
            raise ValueError(f"参数[step_type]不支持施压, 当前: {self.step_type}, 可选: {[t.value for t in PERF_API_STEP_TYPES]}")
        if self.step_type == AutoTestStepType.HTTP:
            if not _has_text(self.request_url):
                raise ValueError("HTTP请求必须提供参数[request_url]")
            if self.request_method is None:
                raise ValueError("HTTP请求必须提供参数[request_method]")
        return self


class PerfApiCreate(PerfApiBase):
    """新增压测接口入参。"""

    # 录入溯源: 导入草稿回传后由用户确认保存, 一旦落库不再变更(功能用例后续改动不静默影响压测资产)
    api_source: PerfApiSource = Field(default=PerfApiSource.MANUAL, description="录入来源")
    source_case_code: Optional[str] = Field(None, max_length=64, description="来源用例标识(导入时写入)")
    source_step_code: Optional[str] = Field(None, max_length=64, description="来源步骤标识(导入时写入)")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")


class PerfApiUpdate(PerfApiRequestBlock):
    """更新压测接口入参(全部可选, 定位字段二选一)。"""

    api_id: Optional[int] = Field(None, ge=1, description="接口ID")
    api_code: Optional[str] = Field(None, max_length=64, description="接口标识代码")
    api_project: Optional[int] = Field(None, ge=1, description="接口所属应用")
    api_name: Optional[str] = Field(None, min_length=1, max_length=255, description="接口名称")
    api_desc: Optional[str] = Field(None, max_length=2048, description="接口描述")
    extract_variables: Optional[List[ExtractVariableItem]] = Field(None, description="变量提取规则列表")
    assert_validators: Optional[List[AssertValidatorItem]] = Field(None, description="业务断言规则列表")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")

    @model_validator(mode="after")
    def _require_locator(self):
        """更新必须能定位到一条接口。"""
        if not self.api_id and not _has_text(self.api_code):
            raise ValueError("请提供参数[api_id | api_code]完成压测接口更新")
        return self


class PerfApiSelect(BaseModel):
    """分页查询压测接口入参。"""

    api_id: Optional[int] = Field(None, ge=1, description="接口ID")
    api_code: Optional[str] = Field(None, max_length=64, description="接口标识代码")
    api_project: Optional[int] = Field(None, ge=1, description="接口所属应用")
    api_name: Optional[str] = Field(None, max_length=255, description="接口名称(模糊匹配)")
    step_type: Optional[AutoTestStepType] = Field(None, description="请求类型")
    request_project_id: Optional[int] = Field(None, ge=1, description="请求目标应用ID")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, le=100, description="每页数量")
    order: List[str] = Field(default_factory=lambda: ["-updated_time"], description="排序字段")
    created_user: Optional[UpperStr] = Field(None, max_length=16, description="创建人员")
    updated_user: Optional[UpperStr] = Field(None, max_length=16, description="更新人员")
    state: Optional[int] = Field(default=0, description="状态(0:启用, 1:禁用)")


class PerfApiSimpleSelect(BaseModel):
    """场景选择器查询入参(不分页, 只回精简字段, 避免全量拉取拖慢抽屉打开)。"""

    api_project: int = Field(..., ge=1, description="接口所属应用")
    api_name: Optional[str] = Field(None, max_length=255, description="接口名称(模糊匹配)")
    step_type: Optional[AutoTestStepType] = Field(None, description="请求类型")


class PerfApiLocate(BaseModel):
    """单接口定位入参(复制/调试共用, id或code二选一)。"""

    api_id: Optional[int] = Field(None, ge=1, description="接口ID")
    api_code: Optional[str] = Field(None, min_length=1, max_length=64, description="接口标识代码")

    @model_validator(mode="after")
    def _require_locator(self):
        """必须能定位到一条接口。"""
        if not self.api_id and not _has_text(self.api_code):
            raise ValueError("请提供参数[api_id | api_code]完成接口定位")
        return self


class PerfApiDebug(BaseModel):
    """
    压测接口调试入参(对已保存资产发一次真实请求, 回显状态码/耗时/响应片段/断言与提取结果)。

    调试结果回写 api.debug_state/debug_time, 是施压前预检闸门的依据; 未保存的表单请先保存再调试
    (调试结论必须挂在可追溯的资产版本上, 否则 debug_state 无处落)。
    """

    api_id: Optional[int] = Field(None, ge=1, description="接口ID")
    api_code: Optional[str] = Field(None, min_length=1, max_length=64, description="接口标识代码")
    # 施压目标环境(复用 autotest 环境三级链; 接口地址为绝对地址时可留空)
    env_name: Optional[str] = Field(None, max_length=128, description="调试环境名称")
    env_config_name: Optional[str] = Field(None, max_length=128, description="调试目标配置名称(APP节点)")
    session_variables: Optional[List[RequestKvItem]] = Field(None, description="临时变量池(渲染请求占位符, 不落库)")
    # 参数化取数: 数据集与接口无绑定列(数据集反向归属接口, 一个接口可挂多个数据集), 故调试时必须显式指定
    ds_code: Optional[str] = Field(None, max_length=64, description="调试取数数据集标识(空=不注入参数化数据)")
    scene_index: int = Field(default=0, ge=0, description="取该数据集的第几个场景做调试(0起, 按场景声明顺序)")

    @model_validator(mode="after")
    def _require_locator(self):
        """调试必须能定位到一条接口; 指定场景序号时必须同时指定数据集。"""
        if not self.api_id and not _has_text(self.api_code):
            raise ValueError("请提供参数[api_id | api_code]完成调试")
        if self.scene_index > 0 and not _has_text(self.ds_code):
            raise ValueError("参数[scene_index]仅在指定[ds_code]时有效, 请同时提供数据集标识")
        return self


class PerfApiImport(BaseModel):
    """
    从功能资产导入压测接口入参(单向拷贝 + 溯源留痕, 不落库, 返回草稿供用户改名后保存)。

    公共接口(case_type=公共接口)恰好等于一个 HTTP/TCP 步骤, 不传 step_ids 即整体导入;
    普通用例必须显式指定要转成压测接口的步骤, 避免把整条功能用例灌进压测资产。
    """

    case_id: int = Field(..., ge=1, description="来源用例ID(公共接口或用例)")
    step_ids: Optional[List[int]] = Field(None, description="来源步骤ID列表(公共接口可省略)")


class PerfApiCurlParse(BaseModel):
    """
    cURL 粘贴解析入参(解析为接口草稿不落库, 由用户在表单确认补全后保存)。

    解析为纯函数(common/curl_utils), 主机地址不落库: 施压目标由环境配置承接,
    草稿仅保留路径/端口/头/参数/数据体与解析警告。
    """

    curl_text: str = Field(
        ..., min_length=1, max_length=20000,
        description="cURL命令文本(支持bash/Windows续行与ANSI-C引用)",
    )


class PerfApiOpenapiParse(BaseModel):
    """
    OpenAPI/Swagger 批量解析入参(解析为接口草稿列表不落库, 由用户逐条确认补全后保存)。

    解析为纯函数(common/openapi_utils), 支持 OpenAPI 3.x 与 Swagger 2.0(json/yaml);
    单次导入上限由 MAX_IMPORT_DRAFTS 约束, 路径参数/文件表单等不适配项进入各条草稿的 warnings。
    """

    openapi_text: str = Field(
        ..., min_length=1, max_length=200000,
        description="OpenAPI/Swagger文档文本(json/yaml)",
    )

