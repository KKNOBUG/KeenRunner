# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : app_middleware.py
@DateTime: 2025/1/17 22:29
"""
import time
from io import BytesIO
from typing import Dict, Any, Optional
from urllib.parse import unquote

import orjson
from fastapi import Request, Response
from starlette.datastructures import FormData

from backend.applications.base.models.audit_model import Audit
from backend.applications.user.models.user_model import User
from backend.common.permission_action import ACTION_UNKNOWN, AUDITED_ACTIONS, derive_action
from backend.configure import PROJECT_CONFIG, GLOBAL_CONFIG, LOGGER
from backend.enums import ResourceTag
from backend.services import AuthControl
from backend.services.resource_policy import LEGACY_TAG

# 审计脱敏：凭证类字段在入库前遮蔽，避免拥有审计读权限的角色（Users 系统域只读）取到他人登录态与密码
MASKED_HEADER_KEYS: frozenset = frozenset({
    "auth",
    "token",
    "secret",
    "authorization",
    "cookie",
    "proxy-authorization",
    "proxy-authenticate",
    "www-authenticate",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "x-refresh-token",
    "x-secret-key",
    "x-signature",
})
MASKED_FIELD_KEYWORDS: frozenset = frozenset({
    "pwd",
    "passwd",
    "password",
    "secret",
    "auth",
    "authorization",
    "token",
    "auth_token",
    "access_token",
    "refresh_token",
})
MASKED_VALUE: str = "******"
NON_JSON_CONTENT: str = "<NON-JSON CONTENT>"


def _mask_sensitive(payload: Any) -> Any:
    """递归遮蔽字典/列表中的凭证字段，保留原始结构以保留审计可读性。

    :param payload: 已解析的请求体、响应体或表单数据
    :returns: 脱敏后的同结构数据
    """
    if isinstance(payload, dict):
        return {
            key: (
                f"{value[:int(len(str(value)) / 3)]}{MASKED_VALUE}{value[-(int(len(str(value)) / 3)):]}"
                if any(word in str(key).lower() for word in MASKED_FIELD_KEYWORDS)
                else _mask_sensitive(value)
            )
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_mask_sensitive(item) for item in payload]
    return payload


def is_upload_request(request: Request) -> bool:
    """判断当前请求是否为文件上传请求（multipart/form-data 或路径含 upload）。

    :param request: FastAPI/Starlette 请求对象。
    :returns: 是上传请求返回 True，否则 False。
    """
    path: str = request.url.path.lower()
    content_type: str = request.headers.get("content-type", "")
    return "multipart/form-data" in content_type.lower() or path.startswith("upload") or path.endswith("upload")


def is_html_response(response: Response) -> bool:
    """判断响应是否为 HTML 或 XML 文本类型。

    :param response: 响应对象。
    :returns: Content-Type 含 text/html 或 application/xml 时返回 True。
    """
    content_type: str = response.headers.get("content-type", "")
    return "text/html" in content_type.lower() or "application/xml" in content_type.lower()


def is_image_response(response: Response) -> bool:
    """判断响应是否为图片类型。

    :param response: 响应对象。
    :returns: Content-Type 含 image 时返回 True。
    """
    content_type: str = response.headers.get("content-type", "")
    return "image" in content_type.lower()


def is_download_response(response: Response) -> bool:
    """判断响应是否为附件下载（Content-Disposition 含 attachment）。

    :param response: 响应对象。
    :returns: 为附件下载时返回 True。
    """
    content_disposition: str = response.headers.get("content-disposition", "")
    return "attachment" in content_disposition.lower()


def is_longtext_response(response: Response) -> bool:
    """判断响应体是否超过 102400 字节（用于决定是否截断审计日志中的响应体）。

    :param response: 响应对象。
    :returns: Content-Length 大于 102400 时返回 True。
    """
    content_length: int = response.headers.get("content-length", 0)
    return int(content_length) > 102400


async def logging_middleware(request: Request, call_next):
    """记录请求与响应摘要、耗时，并写入审计表；对上传/下载/大响应体做特殊处理。

    :param request: 当前请求。
    :param call_next: 下一层 ASGI 可调用对象。
    :returns: 下游返回的 Response。
    """
    # 接口服务时间
    start_time = time.time()
    request_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2, time.localtime(start_time))

    # 变量初始化
    request_body, response_body = b'', b''

    # 读取并保存原始请求体，重置请求流以便后续处理
    original_request_body: bytes = await request.body()
    request._body = original_request_body
    request._stream = BytesIO(original_request_body)

    # 判断是否为文件上传请求
    is_upload: bool = is_upload_request(request)
    if is_upload:
        form_data: Dict[str, Any] = {}
        original_form_data: FormData = await request.form()
        # 提取字段和文件信息
        for field_name, field_value in original_form_data.items():
            if hasattr(field_value, 'file'):
                form_data[field_name] = {
                    "filename": field_value.filename,
                    "content_type": field_value.content_type,
                    "size": field_value.size
                }
            else:
                form_data[field_name] = field_value

        # 重置流的位置到开头，确保后续处理能正确读取
        request_body = orjson.dumps(form_data)
        request._stream.seek(0)

    # 记录请求信息
    request_method: str = request.method
    request_router: str = request.url.path
    request_header: dict = {
        key: (MASKED_VALUE if key.lower() in MASKED_HEADER_KEYS else value)
        for key, value in request.headers.items()
    }
    if request_header.get("referer"):
        # referer 可能带百分号编码的中文路径，记录前还原便于检索；unquote 对非法编码不抛异常
        request_header["referer"] = unquote(request_header["referer"])
    request_client: str = request.client.host if request.client else "127.0.0.1"
    request_body: bytes = request_body if is_upload else original_request_body.decode("utf-8", errors="ignore")
    request_params: str = unquote(request.query_params.__str__())

    # 请求流传递并获取响应
    response = await call_next(request)

    # 按启动绑定的契约归类行为：审计记录写/删/执行/上传/下载类请求，查询直接透传；
    # 无法判定行为的路由默认审计（fail-closed），避免漏审
    route = request.scope.get("route")
    resource = getattr(route, "resource", None)
    request_tags = resource.value if resource is not None else LEGACY_TAG
    # 路由对象在 call_next 后才挂到 scope，摘要直接从路由读取，避免单独维护路径字典
    request_summary: str = getattr(route, "summary", None) or "未定义"
    action: str = getattr(route, "action", None) or derive_action(request_method, request_router)
    # 403 拒绝事件即使落在查询接口也必须留痕：拒绝信号由异常处理器写入共享 request.state，
    # 正常查询不消费响应体，只有拒绝请求进入下方审计管线（与写操作同口径记录业务参数）
    denied: bool = bool(getattr(request.state, "audit_denied", False))
    if action not in AUDITED_ACTIONS and action != ACTION_UNKNOWN and not denied:
        return response

    # 判断是否管控响应
    is_download: bool = is_download_response(response)
    is_html: bool = is_html_response(response)
    is_image: bool = is_image_response(response)
    is_longtext: bool = is_longtext_response(response)

    response_header: dict = dict(response.headers)

    # 路由排除（静态文件&OpenApi文档&审计自身查询）；拒绝事件响应体很小，
    # 即使是排除路由也要落审计，避免越权探测无痕
    excluded_route: bool = request_router.startswith("/static/") or request_router in (
        '/',
        '/base/audit/list',
        '/base/audit/search',
        PROJECT_CONFIG.APP_DOCS_URL,
        PROJECT_CONFIG.APP_REDOC_URL,
        PROJECT_CONFIG.APP_OPENAPI_URL,
    )
    if not excluded_route or denied:
        # 消费响应体
        if is_download:
            response_body: bytes = b"<FILE DOWNLOAD>"
        elif is_html:
            response_body: bytes = b"<HTML CONTENT>"
        elif is_image:
            response_body: bytes = b"<IMAGE CONTENT>"
        elif is_longtext:
            response_body: bytes = b"<LONGTEXT CONTENT>"
        else:
            body_chunks = []
            async for chunk in response.body_iterator:
                body_chunks.append(chunk)

            response_body: str = b"".join(body_chunks).decode("utf-8", errors="ignore")

            # 重置响应体
            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=response_header,
                media_type=response.media_type
            )

        # 接口服务结束时间
        end_time = time.time()
        response_time: str = time.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2, time.localtime(end_time))
        response_elapsed = f"{end_time - start_time:.2f}s"

        # JSON请求保留结构并递归脱敏；无法可靠解析的非JSON原文不落审计，避免口令/XML秘密绕过字段级脱敏
        body_text: str = request_body.decode("utf-8", errors="ignore") if isinstance(request_body, bytes) else (request_body or "")
        try:
            masked_body: str = orjson.dumps(_mask_sensitive(orjson.loads(body_text))).decode()
        except orjson.JSONDecodeError:
            masked_body = NON_JSON_CONTENT if body_text else ""

        # 记录日志
        audit_log: Dict[str, Any] = {
            "request_time": request_time,
            "request_tags": request_tags,
            "request_summary": request_summary,
            "request_method": request_method,
            "request_router": request_router,
            "request_client": request_client,
            "request_header": request_header,
            "request_params": masked_body or request_params,
            "response_time": response_time,
            "response_header": response_header,
            "response_elapsed": response_elapsed
        }
        if isinstance(response_body, str) and response_body:
            try:
                _response = orjson.loads(response_body)
            except orjson.JSONDecodeError:
                # 非JSON响应无法保证字段级脱敏，仅保留类型占位符，避免纯文本秘密进入审计与日志
                _response = {}
                masked_response_body = NON_JSON_CONTENT
            else:
                masked_response_body = orjson.dumps(_mask_sensitive(_response)).decode()
            audit_log["response_code"] = _response.get("code", "") if isinstance(_response, dict) else ""
            response_message = _response.get("message", "") if isinstance(_response, dict) else ""
            audit_log["response_message"] = str(response_message)[:512]
            audit_log["response_params"] = masked_response_body
            del _response

        request_message: str = (
            f"\n> > > > > > > > > > > > > > > > > > > >\n"
            f"请求时间：{audit_log.get('request_time')}\n"
            f"请求模块：{ResourceTag.label_of(request_tags)}\n"
            f"请求接口：{audit_log.get('request_summary')}\n"
            f"请求方式：{audit_log.get('request_method')}\n"
            f"请求路由：{audit_log.get('request_router')}\n"
            f"请求来源：{audit_log.get('request_client')}\n"
            f"请求头部：{audit_log.get('request_header')}\n"
            f"请求参数：{audit_log.get('request_params')}\n"
            f"响应头部：{audit_log.get('response_header')}\n"
            f"响应代码：{audit_log.get('response_code')}\n"
            f"响应消息：{audit_log.get('response_message')}\n"
            f"响应参数：{audit_log.get('response_params')}\n"
            f"响应时间：{audit_log.get('response_time')}\n"
            f"响应耗时：{audit_log.get('response_elapsed')}\n"
            f"< < < < < < < < < < < < < < < < < < < < "
        )
        LOGGER.info(request_message)

        try:
            # 获取用户信息
            user_obj: Optional[User] = None
            token = request.headers.get("token")
            if token:
                user_obj: User = await AuthControl.is_authed(request=request, token=token)
            audit_log["user_id"] = user_obj.id if user_obj else 0
            audit_log["username"] = user_obj.username if user_obj else ""
        except Exception as e:
            audit_log["user_id"] = 0
            audit_log["username"] = ""

        # 审计落库
        await Audit.create(**audit_log)

    return response
