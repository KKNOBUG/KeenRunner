# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tcp_test_view
@DateTime: 2026/7/21 10:00:00
"""
import traceback

from fastapi import APIRouter

from backend.applications.autotest.services.autotest_tcp_test_service import TcpTestServerService
from backend.configure import LOGGER
from backend.core.responses import SuccessResponse, FailureResponse

autotest_tcp_test = APIRouter()


# ---------------------------------------------------------------------------
# 路由（仅用于启动/停止/状态/获取示例，实际 TCP 通信不走 HTTP）
# ---------------------------------------------------------------------------

@autotest_tcp_test.post(
    path="/start",
    summary="启动TCP测试服务器",
    description="按内置端口组合统一启动TCP测试服务器（业务mock端口9091/9092 + 帧协议诊断端口9093~9099），监听地址固定为后端启动地址"
)
async def start_tcp_test_server():
    """
    按内置端口组合一键启动全部TCP测试端口。

    :return: 统一HTTP响应，data含frame各端口状态快照列表
    """
    try:
        frame_statuses = await TcpTestServerService.start()
        return SuccessResponse(message="启动成功", data={"frame": frame_statuses})
    except Exception as e:
        error_message = "启动TCP测试服务器失败"
        LOGGER.error(f"{error_message}，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=error_message)


@autotest_tcp_test.post("/stop", summary="停止TCP测试服务器", description="统一停止全部TCP测试端口（业务mock端口与帧协议诊断端口）")
async def stop_tcp_test_server():
    """
    统一停止全部TCP测试端口。

    :return: 统一HTTP响应，data含 frame 各端口状态快照列表
    """
    try:
        frame_statuses = await TcpTestServerService.stop()
        return SuccessResponse(message="停止成功", data={"frame": frame_statuses})
    except Exception as e:
        error_message = "停止TCP测试服务器失败"
        LOGGER.error(f"{error_message}，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=error_message)


@autotest_tcp_test.get(
    path="/status",
    summary="查询TCP测试服务器状态",
    description="统一查询全部TCP测试端口（业务mock端口与帧协议诊断端口）运行状态、连接计数与最近收发诊断快照"
)
async def get_tcp_test_server_status():
    """
    统一查询全部TCP测试端口的运行状态。

    :return: 统一HTTP响应，data含 frame 各端口状态快照列表
    """
    return SuccessResponse(message="查询成功", data={"frame": TcpTestServerService.status()})


@autotest_tcp_test.get("/sample/json", summary="查询JSON请求示例报文", description="获取JSON端口银行账户交易查询请求示例")
async def get_json_sample():
    """
    获取JSON端口的银行账户交易查询请求报文示例。

    :return: 统一HTTP响应
    """
    return SuccessResponse(message="查询成功", data=TcpTestServerService.json_request_sample())


@autotest_tcp_test.get("/sample/xml", summary="查询XML请求示例报文", description="获取XML端口贷款申请请求示例")
async def get_xml_sample():
    """
    获取XML端口的贷款申请请求报文示例。

    :return: 统一HTTP响应
    """
    return SuccessResponse(message="查询成功", data=TcpTestServerService.xml_request_sample())


@autotest_tcp_test.get("/sample/response/json", summary="查询JSON端口的XML响应", description="预览JSON端口对示例请求返回的XML响应")
async def get_json_response_preview():
    """
    预览JSON端口对示例请求返回的XML响应。

    :return: 统一HTTP响应
    """
    return SuccessResponse(message="查询成功", data=TcpTestServerService.json_response_preview())


@autotest_tcp_test.get("/sample/response/xml", summary="查询XML端口的XML响应", description="预览XML端口对示例请求返回的XML响应")
async def get_xml_response_preview():
    """
    预览XML端口对示例请求返回的XML响应。

    :return: 统一HTTP响应
    """
    return SuccessResponse(message="查询成功", data=TcpTestServerService.xml_response_preview())
