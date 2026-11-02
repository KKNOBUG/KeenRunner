# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : permission_contract.py
@DateTime: 2026/10/30
"""
from typing import Iterator, List, Optional, Set

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from backend.common.permission_action import ACTION_UNKNOWN, derive_action
from backend.configure import LOGGER
from backend.enums import ResourceTag
from backend.services.dependency import AuthControl, PermissionControl, get_superuser

# ==================== 认证模式 ====================
AUTH_MODE_PERMISSION: str = "permission"
AUTH_MODE_SELF: str = "self"
AUTH_MODE_PUBLIC: str = "public"


def _dependency_func(dependency) -> object:
    """取依赖的原始函数对象，避免绑定方法每次访问产生新对象导致比较失效。"""
    return getattr(dependency, "__func__", dependency)


_PERMISSION_FUNC = _dependency_func(PermissionControl.has_permission)
_AUTH_FUNC = _dependency_func(AuthControl.is_authed)
_SUPERUSER_FUNC = _dependency_func(get_superuser)


def _route_method(route: APIRoute) -> str:
    """取业务方法，忽略 HEAD/OPTIONS 自动补充项。"""
    methods = [method for method in route.methods if method not in ("HEAD", "OPTIONS")]
    return methods[0] if methods else ""


def _route_dependency_funcs(route: APIRoute) -> Set[object]:
    """递归收集路由全部依赖（含 include_router、装饰器与视图参数三处声明）。"""

    def walk(dependant: Dependant) -> Iterator[object]:
        for sub in dependant.dependencies:
            if sub.call is not None:
                yield _dependency_func(sub.call)
            yield from walk(sub)

    return set(walk(route.dependant))


def _resolve_auth_mode(functions: Set[object]) -> str:
    """按路由级依赖识别认证模式：权限鉴权 / 仅认证 / 公开。"""
    if _PERMISSION_FUNC in functions:
        return AUTH_MODE_PERMISSION
    if _AUTH_FUNC in functions:
        return AUTH_MODE_SELF
    return AUTH_MODE_PUBLIC


def bind_route_contracts(app: FastAPI) -> None:
    """
    启动时把资源族、行为、认证模式绑定到路由对象。

    绑定结果供路由刷新、权限判定、数据范围与审计统一读取，
    后续任何消费方都不再解析 tags 或路径字符串。

    :param app: FastAPI 应用
    """
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        method: str = _route_method(route)
        route.resource = ResourceTag.of_tags(route.tags)
        route.action = derive_action(method, route.path)
        # 依赖树只遍历一次，认证模式与管理员专属标记共用结果
        functions: Set[object] = _route_dependency_funcs(route)
        route.auth_mode = _resolve_auth_mode(functions)
        # 管理员专属接口不参与角色自动绑定，内置非管理员角色一律不授权
        route.available_only_admin = _SUPERUSER_FUNC in functions


def validate_route_contracts(app: FastAPI) -> List[str]:
    """
    校验路由契约完整性。

    问题只记录 ERROR 日志、不阻断启动，方便开发期及时纠正；
    CI 可读取返回值，非空即判定失败。

    :param app: FastAPI 应用
    :return: 问题描述列表
    """
    issues: List[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if getattr(route, "auth_mode", AUTH_MODE_PUBLIC) != AUTH_MODE_PERMISSION:
            continue
        method: str = _route_method(route)
        resource: Optional[ResourceTag] = getattr(route, "resource", None)
        action: str = getattr(route, "action", ACTION_UNKNOWN)
        if resource is None:
            issues.append(f"资源族未登记 tags={route.tags} {method} {route.path}")
        if action == ACTION_UNKNOWN:
            issues.append(f"路径末段不符 缺少预定义词根 {method} {route.path}")

    for issue in issues:
        LOGGER.error(f"[权限契约] {issue}")
    if issues:
        LOGGER.error(f"[权限契约] 共 {len(issues)} 项待修正，启动继续；")
    return issues
