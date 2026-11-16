# -*- coding: utf-8 -*-
"""
性能域环境引用键换算。

压测接口资产与 `/perf/api/debug` 已直接引用 `(env_id, config_mode)`; 仅 `/perf/scene/*`
与 `/perf/load_preset/*` 按设计 D 级保留名称入参(14.5), 由本模块在服务层完成唯一一次
「名称 → 引用键」换算, 之后统一走 StepDebugService.resolve_env_config_by_mode,
执行链路不再存在按名称解析环境的路径。

换算只在预检/执行下发时各发生一次(按 project 缓存), 不进入虚拟用户循环, 不触发热路径查库。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : perf_env_binding.py
@DateTime: 2026/11/14 10:00
"""
from typing import Dict, Optional

from backend.applications.autotest.dependencies import get_autotest_api_services
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.enums import AutoTestConfigNodeType


async def resolve_env_bind_id(*, project_id: int, env_name: str, label: str) -> int:
    """
    按应用 + 环境名称解析环境绑定ID(仅 APP 节点)。

    :param project_id: 应用ID(krun_autotest_project.id)
    :param env_name: 环境名称(忽略大小写)
    :param label: 错误信息前缀
    :return: 环境绑定ID(krun_autotest_env_bind.id)
    :raises ParameterException: env_name 为空
    :raises NotFoundException: 应用下不存在该环境的 APP 绑定
    """
    name: str = (env_name or "").strip()
    if not name:
        raise ParameterException(message=f"{label}, 参数[env_name]不允许为空")

    services = await get_autotest_api_services()
    env_row = await services.env_curd.get_bind_by_env_name(
        project_id=int(project_id),
        env_name=name,
        env_type=AutoTestConfigNodeType.APP,
    )
    if not env_row:
        error_message: str = f"{label}, 应用[{project_id}]下环境[{name}]不存在或未挂载APP节点"
        LOGGER.error(error_message)
        raise NotFoundException(message=error_message)
    return int(env_row.id)


async def resolve_config_mode(*, env_id: int, config_name: str, label: str) -> str:
    """
    按环境绑定ID + 配置名称解析配置逻辑标识(config_mode)。

    :param env_id: 环境绑定ID(krun_autotest_env_bind.id)
    :param config_name: APP节点配置名称
    :param label: 错误信息前缀
    :return: 配置逻辑标识(config_mode), 同一逻辑配置在各环境实例上共享 mode
    :raises ParameterException: config_name 为空
    :raises NotFoundException: 环境绑定下不存在该配置或配置缺少逻辑标识
    """
    # 配置不存在或缺少 mode(未回填的存量行)都视为不可引用, 避免把空 mode 带进执行链路
    name: str = (config_name or "").strip()
    if not name:
        raise ParameterException(message=f"{label}, 参数[config_name]不允许为空")

    services = await get_autotest_api_services()
    config_row = await services.env_config_curd.get_by_conditions(
        only_one=True,
        on_error=False,
        state__not=1,
        env_bind_id=int(env_id),
        config_name=name,
    )
    mode: str = str(getattr(config_row, "config_mode", "") or "").strip() if config_row else ""
    if not mode:
        error_message: str = f"{label}, 环境绑定[{env_id}]下APP配置[{name}]不存在或缺少配置逻辑标识"
        LOGGER.error(error_message)
        raise NotFoundException(message=error_message)
    return mode


async def resolve_preset_env_binding(
        *,
        project_id: int,
        env_name: str,
        config_name: Optional[str],
        label: str,
) -> Dict[str, object]:
    """
    负载预设施压环境的引用键换算(环境绑定ID + 可选缺省配置 mode)。

    :param project_id: 预设所属应用ID
    :param env_name: 施压环境名称
    :param config_name: 缺省APP配置名称(可空)
    :param label: 错误信息前缀
    :return: {"env_id": int, "config_mode": str}(config_mode 未选择时为空串)
    """
    # 预设只保存环境名与缺省配置名(D 级契约不变), 下发前一次性换算为引用键;
    # 缺省配置名为空时只返回 env_id, 由接口自身 request_config_mode 决定解析目标
    env_id: int = await resolve_env_bind_id(project_id=project_id, env_name=env_name, label=label)
    default_mode: str = ""
    if (config_name or "").strip():
        default_mode = await resolve_config_mode(env_id=env_id, config_name=config_name, label=label)
    return {"env_id": env_id, "config_mode": default_mode}