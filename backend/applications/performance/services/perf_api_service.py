# -*- coding: utf-8 -*-
"""
压测接口业务服务：功能资产导入通道、单接口调试与数据源矩阵模板推导。

本模块只承载「不落在单一表」的业务动作, 写操作仍收敛在 PerfApiCrud:
- 导入: 从公共接口/功能用例步骤单向拷贝出接口草稿(不落库), 用户确认名称后走 create 保存;
  之所以是拷贝而非引用, 是为了压测资产的可复现性不被功能用例的变更节奏牵连(设计 ADR-V2-4)。
- 调试: 对已保存接口发一次真实请求并回写 debug_state, 是施压前预检闸门的唯一结论来源;
  走施压引擎同款构造器(RequestBuilder), 保证「调试通过」与「施压发出」是同一个请求。
- 矩阵模板: 复用 autotest 数据源服务「按报文构建矩阵」能力(接口报文字段与步骤模型同构),
  为 DataSource 面板推导 HEAD/BODY 分区的 path key 字段行, 只读不落库。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_api_service.py
@DateTime: 2026/9/15 18:20
"""
import asyncio
import time
import traceback
from typing import Any, Dict, List, Optional

import orjson
import requests

from backend.applications.autotest.dependencies import get_autotest_api_services
from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.autotest.models.autotest_step_model import AutoTestStepModel
from backend.applications.autotest.services.autotest_data_source_service import (
    build_vertical_matrix_from_step,
    collect_step_report_original,
)
from backend.applications.autotest.services.autotest_step_debug_service import StepDebugService
from backend.applications.performance.locust_engine.request_executor import (
    RequestBuilder,
    apply_extract_variables,
    build_response_context,
    execute_assertions,
)
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_dataset_model import PerfDatasetModel
from backend.applications.performance.schemas.perf_api_schema import PerfApiDebug
from backend.applications.performance.services.perf_api_crud import (
    IMPORTABLE_API_FIELDS,
    PerfApiCrud,
)
from backend.applications.performance.services.perf_asset_utils import model_field_literal
from backend.common.url_utils import build_absolute_http_url, is_absolute_http_url
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.enums import AutoTestCaseType, AutoTestConfigNodeType, AutoTestStepType, PerfApiSource

# 调试单请求超时(秒): 连通性验证不允许无限等待
DEBUG_REQUEST_TIMEOUT = 10.0
# 调试响应体回显截断(字符): 防止超大响应拖垮接口
DEBUG_BODY_SNIPPET_LIMIT = 5000
# 调试响应体完整回显上限(字符): 编辑页 Response 面板展示用, 兼顾超大响应兜底
DEBUG_BODY_FULL_LIMIT = 200000
# 可导入为压测接口的步骤类型(与压测单元语义一致: 一个请求即一个施压单元)
IMPORTABLE_STEP_TYPES = (AutoTestStepType.HTTP.value, AutoTestStepType.TCP.value)


def build_step_definition(step: AutoTestStepModel) -> Dict[str, Any]:
    """
    功能步骤 → 请求定义字典(纯字段搬运, 枚举落字面量)。

    :param step: 功能步骤实例
    :return: 压测接口请求定义字典
    """
    definition: Dict[str, Any] = {field: model_field_literal(step, field) for field in IMPORTABLE_API_FIELDS}
    if definition.get("request_method"):
        definition["request_method"] = str(definition["request_method"]).upper()
    return definition


class PerfApiService:
    """压测接口业务服务：导入通道、单接口调试与数据源矩阵模板推导。"""

    @staticmethod
    async def import_from_case(*, case_id: int, step_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        从功能资产导入压测接口草稿(公共接口整体导入 / 用例按指定步骤导入), 只读不落库。

        公共接口(case_type=公共接口)本身就等价一个请求单元, 不传 step_ids 即导入其全部
        HTTP/TCP 步骤; 普通用例必须显式指定步骤, 避免把整条功能链路灌进压测资产。
        导入结果为草稿: 名称可改, 由用户确认后走 create 落库。

        :param case_id: 来源用例ID(krun_autotest_case.id)
        :param step_ids: 来源步骤ID列表, 公共接口可省略
        :return: 接口草稿列表, 单个元素结构:
            {"api_name", "api_desc", "api_source",
             "source_case_code", "source_step_code", **请求定义字段}
        """
        case: Optional[AutoTestCaseModel] = await AutoTestCaseModel.filter(
            id=case_id, state__not=1
        ).first()
        if not case:
            error_message: str = f"导入压测接口失败, 用例[id={case_id}]不存在或已删除"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        query_step_ids: Optional[List[int]] = list(step_ids or [])
        if not query_step_ids and case.case_type != AutoTestCaseType.PUBLIC_API:
            error_message: str = "导入压测接口失败, 非公共接口用例必须显式指定要导入的步骤ID列表"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        step_query = AutoTestStepModel.filter(
            case_id=case_id, state__not=1, step_type__in=IMPORTABLE_STEP_TYPES
        )
        if query_step_ids:
            step_query = step_query.filter(id__in=query_step_ids)
        steps: List[AutoTestStepModel] = await step_query.order_by("step_no", "id")
        if not steps:
            error_message: str = f"导入压测接口失败, 用例[{case.case_name}]下无可导入的HTTP/TCP步骤"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if query_step_ids:
            missing_ids: List[int] = [sid for sid in query_step_ids if sid not in {step.id for step in steps}]
            if missing_ids:
                error_message: str = (
                    f"导入压测接口失败, 步骤{missing_ids}不存在、已删除或不属于用例[{case.case_name}]"
                    f"(仅HTTP/TCP步骤可导入)"
                )
                LOGGER.error(error_message)
                raise NotFoundException(message=error_message)

        api_source: PerfApiSource = (
            PerfApiSource.PUBLIC_API if case.case_type == AutoTestCaseType.PUBLIC_API else PerfApiSource.HTTP_STEP
        )
        drafts: List[Dict[str, Any]] = []
        for step in steps:
            definition: Dict[str, Any] = build_step_definition(step)
            drafts.append({
                "api_name": step.step_name,
                "api_desc": step.step_desc,
                "api_source": api_source.value,
                "source_case_code": case.case_code,
                "source_step_code": step.step_code,
                **definition,
            })
        LOGGER.info(f"压测接口导入完成: case_id={case_id}, 草稿{len(drafts)}条, 来源={api_source.value}")
        return drafts

    @staticmethod
    async def _resolve_debug_url(api: PerfApiModel, *, env_name: Optional[str], env_config_name: Optional[str]) -> str:
        """
        调试地址组装: 绝对地址原样返回, 相对地址按施压环境 APP 配置补齐 host/port。

        口径与执行管线完全一致(同一 resolve_env_config + build_absolute_http_url), 配置名优先取
        接口自带的目标配置, 未配置时回退调试入参选择的任务级配置。

        :param api: 压测接口实例
        :param env_name: 调试环境名称
        :param env_config_name: 调试目标配置名称(APP节点)
        :return: 可直接发起请求的绝对地址
        """
        request_url: str = str(api.request_url or "").strip()
        if is_absolute_http_url(request_url):
            return request_url

        config_name: str = (api.request_config_name or env_config_name or "").strip()
        if not api.request_project_id or not (env_name or "").strip() or not config_name:
            error_message: str = (
                "压测接口调试失败, 请求地址为相对路径时必须提供目标应用、调试环境与APP配置名称"
                f"(当前: 应用={api.request_project_id}, 环境={env_name}, 配置={config_name or '未选择'})"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        services = await get_autotest_api_services()
        endpoint = await StepDebugService.resolve_env_config(
            services,
            project_id=api.request_project_id,
            env_name=(env_name or "").strip(),
            config_name=config_name,
            config_type=AutoTestConfigNodeType.APP,
            label="压测接口调试失败",
        )
        host: str = (endpoint.config_host or "").strip()
        if not host:
            error_message: str = f"压测接口调试失败, 目标环境下[{config_name}]配置不完整(缺少host)"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return build_absolute_http_url(host, endpoint.config_port, request_url)

    @staticmethod
    async def _load_debug_scene(
        api_id: int,
        enable_data_source: bool,
        scene_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """
        读取调试用的单场景参数化数据(对齐 autotest 设计: 一个接口绑定一个数据源)。

        施压与调试同口径: 仅消费 head/body 两分区(assert_* 分区不参与施压),
        路径替换与占位符渲染由 RequestBuilder 按引擎同款语义完成。

        :param api_id: 压测接口ID(用于定位绑定的数据源)
        :param enable_data_source: 是否启用数据源
        :param scene_name: 启用数据源时选择的场景名称
        :return: {"name", "head", "body"}单场景字典或None
        """
        if not enable_data_source:
            return None
        if not scene_name:
            error_message: str = "压测接口调试失败, 启用数据源时必须指定场景名称"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 按 bind_api_id 查找接口绑定的唯一数据源(对齐 autotest 设计)
        dataset: Optional[PerfDatasetModel] = await PerfDatasetModel.filter(
            bind_api_id=api_id, state__not=1
        ).first()
        if not dataset:
            error_message: str = f"压测接口调试失败, 接口[id={api_id}]尚未绑定数据源"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        scene_names: List[str] = dataset.dataset_names or []
        if scene_name not in scene_names:
            error_message: str = (
                f"压测接口调试失败, 数据源[{dataset.ds_name}]不包含场景[{scene_name}], "
                f"可用场景: {scene_names[:10]}"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        scene_data: Dict[str, Any] = (dataset.dataset or {}).get(scene_name) or {}
        return {
            "name": scene_name,
            "head": scene_data.get("head") or {},
            "body": scene_data.get("body") or {},
        }

    @classmethod
    async def debug_api(cls, debug_in: PerfApiDebug) -> Dict[str, Any]:
        """
        单接口调试：以一次真实请求验证已保存的接口定义, 并回写调试结论(不生成报告)。

        请求由施压引擎同款 RequestBuilder 构造(占位符渲染、body 装配、Cookie 拆分口径完全一致),
        先提取后断言的顺序也与施压循环一致; 传输层异常属有效调试结果(返回原因而非抛错),
        调试结论 success = 状态码 < 400 且全部断言通过 —— 无断言时不再默认通过, 否则 5xx 会被记成 success。

        :param debug_in: 调试入参(接口定位 + 环境 + 临时变量池 + 取数场景)
        :return: 调试结果字典, 结构:
            {"success": true, "request_url": "http://...", "status_code": 200,
             "elapsed_ms": 45.2, "response_body": "...截断回显...", "transport_error": null,
             "assertions": [断言快照列表], "extracts": [提取快照列表],
             "request_info": {"method", "url", "headers", "params", "body_type", "body"},
             "response_headers": {...}, "response_cookies": {...}, "response_size": 1024,
             "content_type": "application/json", "response_data": "完整响应体文本", "logs": []}
            """
        if debug_in.api_id:
            api = await PerfApiCrud().get_by_id(api_id=debug_in.api_id, on_error=True, state__not=1)
        else:
            api = await PerfApiCrud().get_by_code(api_code=debug_in.api_code, on_error=True, state__not=1)

        definition: Dict[str, Any] = build_step_definition(api)
        definition["request_url"] = await cls._resolve_debug_url(
            api, env_name=debug_in.env_name, env_config_name=debug_in.env_config_name,
        )
        assert_validators: List[Dict[str, Any]] = definition.get("assert_validators") or []
        extract_variables: List[Dict[str, Any]] = definition.get("extract_variables") or []
        debug_scene: Optional[Dict[str, Any]] = await cls._load_debug_scene(
            api_id=api.id,
            enable_data_source=debug_in.enable_data_source,
            scene_name=debug_in.scene_name,
        )

        builder = RequestBuilder(
            request_definition=definition,
            # 变量池装载口径与引擎一致: 会话变量打底, 接口定义变量后写覆盖(defined > session);
            # defined_variables 元素与 step 容器同构(key/value/desc), 空键不入池
            variable_pool={
                **{item.key: item.value for item in debug_in.session_variables or [] if item.key},
                **{item.get("key"): item.get("value") for item in (api.defined_variables or []) if item.get("key")},
            },
            dataset_scenes=[debug_scene] if debug_scene else None,
        )
        request_kwargs, merged_lookup = builder.build_request()
        debug_result: Dict[str, Any] = {
            "success": False,
            "request_url": request_kwargs.get("url"),
            "status_code": None,
            "elapsed_ms": None,
            "response_body": None,
            "transport_error": None,
            "assertions": [],
            "extracts": [],
            # 编辑页 Response 面板回显所需(命名对齐 autotest 调试契约, 既有字段保持兼容)
            "request_info": cls._build_request_info(request_kwargs, definition=definition),
            "response_headers": {},
            "response_cookies": {},
            "response_size": None,
            "content_type": None,
            "response_data": None,
            "logs": [],
        }
        try:
            started = time.perf_counter()
            with requests.Session() as session:
                # requests 是同步客户端, 禁止在事件循环内直接发送: 目标若是本服务自身端口,
                # 事件循环被占导致请求永远无人处理而必然 ReadTimeout(自指死锁), 其余并发
                # 请求也被同步卡住; 丢线程池发送保持事件循环可调度(构造口径与引擎一致不变)
                response = await asyncio.to_thread(
                    session.request, timeout=DEBUG_REQUEST_TIMEOUT, allow_redirects=False, **request_kwargs
                )
                debug_result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
                debug_result["status_code"] = response.status_code
                debug_result["response_body"] = (response.text or "")[:DEBUG_BODY_SNIPPET_LIMIT]
                debug_result["response_headers"] = dict(response.headers or {})
                debug_result["response_cookies"] = response.cookies.get_dict() if response.cookies else {}
                debug_result["response_size"] = len(response.content or b"")
                debug_result["content_type"] = response.headers.get("Content-Type") or ""
                debug_result["response_data"] = (response.text or "")[:DEBUG_BODY_FULL_LIMIT]
                # 断言与提取上下文在会话内构建, 确保响应内容已消费(顺序与施压引擎一致: 先提取后断言)
                response_context = build_response_context(response, request_kwargs, merged_lookup)
                debug_result["extracts"] = apply_extract_variables(extract_variables, response_context)
                debug_result["assertions"] = execute_assertions(
                    assert_validators=assert_validators,
                    response_context=response_context,
                )
        except requests.RequestException as e:
            debug_result["transport_error"] = f"{type(e).__name__}: {e}"
            LOGGER.warning(f"压测接口调试请求失败: url={request_kwargs.get('url')}, 错误: {e}")
            await PerfApiCrud().mark_debug_result(api_id=api.id, success=False)
            return debug_result

        debug_result["success"] = (
            debug_result["status_code"] is not None
            and debug_result["status_code"] < 400
            and all(item["success"] for item in debug_result["assertions"])
        )
        await PerfApiCrud().mark_debug_result(api_id=api.id, success=debug_result["success"])
        LOGGER.info(
            f"压测接口调试完成: api_code={api.api_code}, status={debug_result['status_code']}, "
            f"success={debug_result['success']}"
        )
        return debug_result

    @staticmethod
    async def build_matrix_template(*, api_id: Optional[int] = None, api_code: Optional[str] = None) -> Dict[str, Any]:
        """
        按接口报文推导数据源矩阵模板(只读不落库), 供 DataSource 面板预填 path key 字段行。

        复用 autotest 数据源服务的构建函数: 压测接口报文字段与 HTTP/TCP 步骤模型同构
        (request_header/request_args_type/request_body/request_text/request_params/
        request_form_data/request_form_urlencoded), 按请求体类型自动推导字段路径:
        请求头$.Key、JSON叶子JSONPath、XML叶子XPath、键值型$.Key(文件字段跳过);
        ASSERT_HEAD/ASSERT_BODY 仅保留分区标记行, 与施压引擎消费口径一致。

        :param api_id: 接口主键ID(与 api_code 二选一)
        :param api_code: 接口业务标识(与 api_id 二选一)
        :return: {"dataframe": [["", "场景1"], ["HEAD", ""], ["$.Token", ""], ["BODY", ""], ...], "axis": 1,
            "data_original": {"HEAD": {"$.Token": "x"}, "BODY": {"$.id": "1"}}}
            dataframe 首行为场景名行, HEAD/BODY 分区下按报文推导字段路径行, 单元格值留空;
            axis 恒为 1(垂直模式), 用户可在线转置为水平后再保存; data_original 为报文原始值映射,
            供「导入正交易场景」回填字段值(与 autotest 数据源 /build 契约一致)
        """
        if api_id:
            api = await PerfApiCrud().get_by_id(api_id=api_id, on_error=True, state__not=1)
        else:
            api = await PerfApiCrud().get_by_code(api_code=api_code, on_error=True, state__not=1)
        # data_original 与 autotest /build 同契约(HEAD/BODY分区->路径->原始值), 供正交易场景列回填原始值
        return {
            "dataframe": build_vertical_matrix_from_step(api),
            "axis": 1,
            "data_original": collect_step_report_original(api),
        }

    @staticmethod
    def _build_request_info(request_kwargs: Dict[str, Any], *, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        调试请求的回显信息(命名与结构对齐 autotest http_debugging 的 request_info 契约)。

        :param request_kwargs: RequestBuilder 渲染后的请求 kwargs
        :param definition: 接口请求定义(取请求体形态声明)
        :return: {"method", "url", "headers", "params", "body_type", "body"}
        """
        return {
            "method": request_kwargs.get("method"),
            "url": request_kwargs.get("url"),
            "headers": request_kwargs.get("headers") or {},
            "params": request_kwargs.get("params") or {},
            "body_type": definition.get("request_args_type") or "none",
            "body": PerfApiService._render_request_body_display(request_kwargs),
        }

    @staticmethod
    def _render_request_body_display(request_kwargs: Dict[str, Any]) -> str:
        """请求体展示文本: json/data/content 三载体统一转文本(files 不回显)。"""
        if request_kwargs.get("json") is not None:
            try:
                return orjson.dumps(request_kwargs["json"], option=orjson.OPT_INDENT_2).decode("utf-8")
            except (orjson.JSONDecodeError, TypeError):
                return str(request_kwargs["json"])
        data = request_kwargs.get("data")
        if data is not None:
            if isinstance(data, str):
                return data
            try:
                return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
            except (orjson.JSONDecodeError, TypeError):
                return str(data)
        content = request_kwargs.get("content")
        if content is not None:
            if isinstance(content, (bytes, bytearray)):
                return bytes(content).decode("utf-8", errors="replace")
            return str(content)
        return ""
