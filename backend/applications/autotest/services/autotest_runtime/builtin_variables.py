# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : builtin_variables.py
@DateTime: 2026/8/28 10:00
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set

from backend.applications.autotest.schemas.autotest_step_schema import StepVariablesBase
from backend.configure.project_config import PROJECT_CONFIG


def strip_host_scheme(host: Optional[str]) -> Optional[str]:
    """
    清理主机地址：去掉首尾空白，并移除字符串中出现的 http:// 与 https://（按子串替换，不校验前缀位置）。

    :param host: 原始主机地址；None 原样返回
    :return: 清理后的主机地址
    """
    if host is None:
        return None
    return str(host).strip().replace("http://", "").replace("https://", "")


def builtin_variable_entries(
        target_host: Optional[str] = None,
        target_port: Optional[str] = None,
        target_path: Optional[str] = None,
) -> List[Dict[str, Optional[str]]]:
    """
    内置变量注册表：固定顺序给出 SERVER_*（平台配置）与 TARGET_*（调用方传入的执行配置）。

    仅描述注册项、不做注入与日志：值为 None 表示该项获取失败，由 collect_builtin_step_variables
    决定跳过并记录；TARGET_HOST 会剥离协议前缀，TARGET_PORT 统一转为字符串。

    :param target_host: 目标应用主机；None 表示未解析到执行配置
    :param target_port: 目标应用端口；None 表示未解析到执行配置
    :param target_path: 目标应用地址；HTTP 传 request_url 原值，TCP 传空字符串
    :return: [{"name": 变量名, "desc": 说明, "value": 字符串或 None}, ...]，顺序即注入顺序
    """
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
    :param existing_keys: 已定义变量的 key 集合（调用方按执行/调试口径提供：局部变量 + 会话变量或查找表键）
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
