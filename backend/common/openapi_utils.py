# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : openapi_utils.py
@DateTime: 2026/9/17 11:30
"""
import json as json_lib
from typing import Any, Dict, List, Optional

import yaml

# 单次导入草稿上限(大文档截断, 防止一次灌入过量资产)
MAX_IMPORT_DRAFTS = 100
# $ref 解析深度上限(防循环引用)
_MAX_REF_DEPTH = 8
# paths 下可转换的标准 HTTP 方法键
_HTTP_METHOD_KEYS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _load_document(text: str) -> Dict[str, Any]:
    """
    加载文档并识别格式: 先按 JSON 解析, 失败则按 YAML 解析。

    :param text: OpenAPI/Swagger 文档文本(json/yaml)
    :return: 文档字典
    :raises ValueError: 文本不可解析或解析结果不是对象
    """
    try:
        doc = json_lib.loads(text)
    except json_lib.JSONDecodeError:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ValueError(f"文档解析失败, 请确认是合法的 JSON 或 YAML: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError("文档为空或解析结果不是JSON对象, 请确认是 OpenAPI/Swagger 文档")
    return doc


def _resolve_ref(doc: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    """
    解析文档内 $ref 引用(仅支持文档内路径引用 #/...)。

    :param doc: 文档根对象
    :param ref: 引用路径(如 #/components/schemas/Order)
    :return: 引用目标节点, 解析失败返回 None
    """
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node: Any = doc
    for segment in ref[2:].split("/"):
        if not isinstance(node, dict):
            return None
        node = node.get(segment)
    return node if isinstance(node, dict) else None


def _schema_example(doc: Dict[str, Any], schema: Any, depth: int = 0) -> Any:
    """
    从 JSON Schema 推导示例值: example > default > enum[0] > 类型骨架(空串/0/false/递归结构)。

    :param doc: 文档根对象(供 $ref 解析)
    :param schema: schema 节点
    :param depth: 当前递归深度
    :return: 示例值; 无法推导时返回 None
    """
    if depth > _MAX_REF_DEPTH or not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        resolved = _resolve_ref(doc, schema["$ref"])
        return _schema_example(doc, resolved, depth + 1) if resolved else None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    schema_type = schema.get("type")
    if schema_type == "object":
        return {
            name: _schema_example(doc, sub, depth + 1)
            for name, sub in (schema.get("properties") or {}).items()
        }
    if schema_type == "array":
        item = _schema_example(doc, schema.get("items") or {}, depth + 1)
        return [item] if item is not None else []
    if schema_type in ("integer", "number"):
        return 0
    if schema_type == "boolean":
        return False
    return ""


def _param_value(doc: Dict[str, Any], param: Dict[str, Any], is_v2: bool) -> Any:
    """
    提取参数示例值: v3 取 param.schema 推导, v2 取参数自身字段推导。

    :param doc: 文档根对象
    :param param: 参数对象
    :param is_v2: 是否 Swagger 2.0 文档
    :return: 参数示例值
    """
    if is_v2:
        return _schema_example(doc, param)
    return _schema_example(doc, param.get("schema") or {})


def _build_draft(
        doc: Dict[str, Any],
        path: str,
        method: str,
        operation: Dict[str, Any],
        common_params: List[Dict[str, Any]],
        is_v2: bool,
) -> Dict[str, Any]:
    """
    单个操作 → 接口草稿(与 import_from_case 草稿同构, api_source=openapi)。

    路径模板中的 {param} 保留原样并以警告提示手工替换; query/header 参数进容器字段;
    请求体按 content 类型归位到 json/表单字段(与 PerfApiForm 编辑形态一一对应)。
    """
    warnings: List[str] = []
    header_rows: List[Dict[str, str]] = []
    query_rows: List[Dict[str, str]] = []
    form_rows: List[Dict[str, str]] = []
    urlencoded_rows: List[Dict[str, str]] = []
    request_body: Optional[Dict[str, Any]] = None
    request_text: Optional[str] = None
    args_type = "none"
    consumes = operation.get("consumes") or doc.get("consumes") or []

    parameters = list(common_params) + list(operation.get("parameters") or [])
    for param in parameters:
        if not isinstance(param, dict):
            continue
        location = param.get("in")
        name = str(param.get("name") or "")
        if not name:
            continue
        if location == "path":
            warnings.append(f"路径参数{{{name}}}需替换为${{{name}}}占位符或实际值后再施压")
            continue
        value = _param_value(doc, param, is_v2)
        row = {"key": name, "value": "" if value is None else str(value), "desc": str(param.get("description") or "")}
        if location == "query":
            query_rows.append(row)
        elif location == "header":
            header_rows.append(row)
        elif location == "formData" and is_v2:
            if str(param.get("type")) == "file":
                warnings.append(f"表单文件字段[{name}]不支持导入(压测不支持文件上传)")
                continue
            if any("multipart" in str(ct) for ct in consumes):
                form_rows.append(row)
                args_type = "form-data"
            else:
                urlencoded_rows.append(row)
                args_type = "x-www-form-urlencoded"
        elif location == "body" and is_v2:
            body_example = _schema_example(doc, param.get("schema") or {})
            if body_example is not None:
                request_body = body_example if isinstance(body_example, dict) else None
                request_text = None if isinstance(body_example, dict) else json_lib.dumps(body_example, ensure_ascii=False)
                args_type = "json" if isinstance(body_example, dict) else "raw"

    # v3 requestBody: 按 content 类型优先级归位(json > x-www-form-urlencoded > multipart)
    if not is_v2:
        request_body_content = ((operation.get("requestBody") or {}).get("content")) or {}
        json_media = request_body_content.get("application/json") or {}
        body_example = _schema_example(doc, json_media.get("schema") or {})
        if body_example is not None:
            request_body = body_example if isinstance(body_example, dict) else None
            request_text = None if isinstance(body_example, dict) else json_lib.dumps(body_example, ensure_ascii=False)
            args_type = "json" if isinstance(body_example, dict) else "raw"
        elif "x-www-form-urlencoded" in request_body_content:
            properties = ((request_body_content.get("x-www-form-urlencoded") or {}).get("schema") or {}).get("properties") or {}
            urlencoded_rows = [
                {"key": name, "value": "" if (val := _schema_example(doc, sub)) is None else str(val), "desc": ""}
                for name, sub in properties.items()
            ]
            args_type = "x-www-form-urlencoded" if urlencoded_rows else args_type
        elif "multipart/form-data" in request_body_content:
            properties = ((request_body_content.get("multipart/form-data") or {}).get("schema") or {}).get("properties") or {}
            for name, sub in properties.items():
                if isinstance(sub, dict) and (sub.get("format") == "binary" or sub.get("type") == "string" and sub.get("format") == "binary"):
                    warnings.append(f"表单文件字段[{name}]不支持导入(压测不支持文件上传)")
                    continue
                value = _schema_example(doc, sub)
                form_rows.append({"key": name, "value": "" if value is None else str(value), "desc": ""})
            if form_rows:
                args_type = "form-data"

    summary = str(operation.get("summary") or "").strip()
    operation_id = str(operation.get("operationId") or "").strip()
    api_name = summary or operation_id or f"{method} {path}"

    return {
        "api_name": api_name,
        "api_desc": str(operation.get("description") or "").strip() or None,
        "step_type": "HTTP请求",
        "request_method": method,
        "request_url": path,
        "request_header": header_rows or None,
        "request_params": query_rows or None,
        "request_form_data": form_rows or None,
        "request_form_urlencoded": urlencoded_rows or None,
        "request_args_type": args_type,
        "request_body": request_body,
        "request_text": request_text,
        "api_source": "openapi",
        "warnings": warnings,
    }


def parse_openapi_document(text: str) -> List[Dict[str, Any]]:
    """
    解析 OpenAPI 3.x / Swagger 2.0 文档为压测接口草稿列表(纯函数, 无IO无状态)。

    :param text: 文档文本(json/yaml)
    :return: 草稿列表(与 import_from_case 草稿同构, 额外携带 warnings; 不含 api_project, 由用户落库时补选)
    :raises ValueError: 文档格式不合法或无可导入操作
    """
    doc = _load_document(text)
    version = str(doc.get("openapi") or doc.get("swagger") or "")
    if not version:
        raise ValueError("文档缺少 openapi/swagger 版本字段, 请确认是 OpenAPI 或 Swagger 文档")
    is_v2 = version.startswith("2")

    paths = doc.get("paths") or {}
    drafts: List[Dict[str, Any]] = []
    truncated = False
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        common_params = [p for p in (path_item.get("parameters") or []) if isinstance(p, dict)]
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHOD_KEYS or not isinstance(operation, dict):
                continue
            drafts.append(_build_draft(doc, path, method.upper(), operation, common_params, is_v2))
            if len(drafts) >= MAX_IMPORT_DRAFTS:
                truncated = True
                break
        if truncated:
            break
    if not drafts:
        raise ValueError("文档中未解析到可导入的接口操作(paths为空或不含标准HTTP方法)")
    if truncated:
        drafts[-1].setdefault("warnings", []).append(f"文档接口数超过导入上限{MAX_IMPORT_DRAFTS}, 已截断")
    return drafts
