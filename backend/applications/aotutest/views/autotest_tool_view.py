# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tool_view
@DateTime: 2026/1/17 16:13
"""
import inspect
import traceback
from typing import Any, Dict, List

from fastapi import APIRouter

from backend.common.generate_utils import GenerateUtils
from backend.configure import LOGGER
from backend.core.responses import SuccessResponse, FailureResponse

autotest_tool = APIRouter()


def _build_func_list_with_desc(cls) -> List[Dict[str, Any]]:
    """
    获取类下所有公共方法信息
    支持：实例方法、@classmethod、@staticmethod
    返回结构：[{"name": "函数名(干净无类型参数)", "desc": "函数首行文档注释"}]
    规则：
        1. 仅收集非下划线开头公共方法
        2. 剔除 self/cls
        3. 剔除所有类型注解、返回值注解
        4. 保留参数默认值
        5. desc 取函数首行文档注释，无注释则为空

    :param cls: 目标类，通常为 GenerateUtils
    :return: [{"name": "func(a=1)", "desc": "..."}, ...]
    """
    result: List[Dict[str, Any]] = []

    for name, member in inspect.getmembers(cls):
        # 过滤私有方法
        if name.startswith("_"):
            continue

        # 匹配三种可调用方法：普通函数、类方法、静态方法
        if not any((
                inspect.isfunction(member),
                inspect.ismethod(member),
                inspect.isbuiltin(member)
        )):
            continue

        try:
            sig = inspect.signature(member)
            params = list(sig.parameters.values())

            # 剔除 self/cls
            if params and params[0].name in ("self", "cls"):
                params = params[1:]

            # 拼接纯参数（无类型注解）
            param_parts = []
            for p in params:
                if p.default is inspect.Parameter.empty:
                    param_parts.append(p.name)
                else:
                    param_parts.append(f"{p.name}={p.default!r}")

            result.append({
                "name": f"{name}({', '.join(param_parts)})",
                "desc": inspect.getdoc(member) or "",
            })
        except (ValueError, TypeError):
            continue

    return result


@autotest_tool.get("/get", summary="查询辅助函数")
async def get_func_info():
    """
    辅助函数查询。

    :return: 统一HTTP响应
    """
    try:
        func_list = _build_func_list_with_desc(GenerateUtils)
        LOGGER.info("辅助函数查询成功")
        return SuccessResponse(message="查询成功", data=func_list, total=len(func_list))
    except Exception as e:
        LOGGER.error(f"辅助函数查询失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
