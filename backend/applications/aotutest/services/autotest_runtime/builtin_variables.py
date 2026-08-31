# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : builtin_variables.py
@DateTime: 2026/8/28 10:00
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set

from backend.applications.aotutest.schemas.autotest_step_schema import StepVariablesBase
from backend.configure.project_config import PROJECT_CONFIG


def strip_host_scheme(host: Optional[str]) -> Optional[str]:
    """
    去除host中可能携带的http(s)协议前缀与首尾空白。

    :param host: 原始主机地址
    :return: 干净的主机地址
    """
    if host is None:
        return None
    return str(host).strip().replace("http://", "").replace("https://", "")


def builtin_variable_entries(
        target_host: Optional[str] = None,
        target_port: Optional[str] = None,
        target_path: Optional[str] = None,
) -> List[Dict[str, Optional[str]]]:
    return [
        {"name": "SERVER_HOST", "desc": "Toolbox工具箱服务主机", "value": str(PROJECT_CONFIG.SERVER_HOST)},
        {"name": "SERVER_PORT", "desc": "Toolbox工具箱服务端口", "value": str(PROJECT_CONFIG.SERVER_PORT)},
        {"name": "TARGET_HOST", "desc": "目标应用主机", "value": strip_host_scheme(target_host)},
        {"name": "TARGET_PORT", "desc": "目标应用端口", "value": str(target_port).strip() if target_port is not None else None},
        {"name": "TARGET_PATH", "desc": "目标应用地址", "value": target_path},
    ]


def collect_builtin_step_variables(
        *,
        target_host: Optional[str] = None,
        target_port: Optional[str] = None,
        target_path: Optional[str] = None,
        existing_keys: Optional[Set[str]] = None,
        log: Optional[Callable[[str], None]] = None,
) -> List[StepVariablesBase]:
    """
    遍历注册表装配HTTP/TCP步骤的内置变量列表，注册项统一经过以下约定。

    约定：
        - 与用户已定义变量同名时跳过，内置变量永不覆盖用户主动定义的变量。
        - 值为None视为内置数据获取失败，不注入并记录日志由前端反馈；
          空字符串为合法值，如TCP步骤的TARGET_PATH。
        - 值统一转为字符串。

    :param target_host: 目标应用主机
    :param target_port: 目标应用端口
    :param target_path: 目标应用地址
    :param existing_keys: 用户已定义的变量key集合（局部变量 + 会话变量）
    :param log: 日志回调
    :return: 可注入变量池的StepVariablesBase列表
    """
    existing_keys = existing_keys or set()

    result: List[StepVariablesBase] = []
    for entry in builtin_variable_entries(target_host, target_port, target_path):
        name: str = entry["name"]
        if name in existing_keys:
            # 同名跳过：内置变量不允许覆盖用户主动定义的变量
            continue
        value = entry["value"]
        if value is None:
            if log:
                log(f"【内置变量】内置数据获取失败: \n\t变量名: {name}, 请检查执行配置是否完整")
            continue
        result.append(StepVariablesBase(key=name, value=str(value), desc="内置环境变量(运行时注入, 不落库)"))
    return result
