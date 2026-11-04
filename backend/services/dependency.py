# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependency.py
@DateTime: 2025/2/19 13:03
"""
import re
from functools import lru_cache
from typing import List, Optional, Tuple, Dict

import jwt
from fastapi import Depends, Header, HTTPException, Request
from tortoise.expressions import Q

from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.enums import BuiltinRoleCode
from backend.services import CTX_USER_ID, CTX_USERNAME

# 认证必需声明：缺任一关键即视为非法令牌，避免无过期时间的长效凭证绕过
REQUIRED_CLAIMS: tuple = ("exp", "user_id", "token_version")


class AuthControl:
    @classmethod
    async def is_authed(cls, request: Request, token: str = Header(..., description="token验证")) -> "User":
        """
        认证当前请求并写入用户上下文。

        同一请求内中间件、路由依赖、审计会重复调用，命中request.state缓存时不再查库；
        缓存命中仍需重建上下文变量，中间件与端点可能运行在不同任务。
        """
        user = getattr(request.state, "current_user", None)
        if user is not None:
            CTX_USER_ID.set(int(user.id))
            CTX_USERNAME.set((user.username or "").strip())
            return user

        try:
            decode_data = jwt.decode(
                jwt=token,
                key=PROJECT_CONFIG.AUTH_SECRET_KEY,
                algorithms=PROJECT_CONFIG.AUTH_JWT_ALGORITHM,
                options={"require": list(REQUIRED_CLAIMS)},
            )
            user = await User.filter(id=int(decode_data["user_id"]), state__not=1).first()
            if not user:
                raise HTTPException(status_code=401, detail="请求服务鉴权失败, 用户状态异常, 请联系管理员后重试")
            if int(decode_data["token_version"]) != user.token_version:
                raise HTTPException(status_code=401, detail="请求服务鉴权过期, 请重新登录获取有效 Token 后进行访问")
            request.state.current_user = user
            CTX_USER_ID.set(int(user.id))
            CTX_USERNAME.set((user.username or "").strip())
            return user
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="请求服务鉴权过期, 请重新登录获取有效 Token 后进行访问")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="请求服务鉴权失败, 请携带有效 Token 进行访问")
        except Exception as e:
            LOGGER.error(f"请求服务鉴权异常, 请稍后重试: {e!r}")
            raise HTTPException(status_code=500, detail="请求服务鉴权异常, 请稍后重试")


class PermissionControl:

    @staticmethod
    @lru_cache(maxsize=1024)
    def _compile_router_path(router_path: str) -> Tuple[re.Pattern, List[str]]:
        """
        编译路由模板为正则表达式，提取参数名称列表，结果缓存；支持段内拼接占位符。

        :param router_path: 路由模板路径
        :return: (正则对象, 参数名列表)
        """
        parts = router_path.split("/")
        re_parts = []
        all_params = []
        for part in parts:
            params = re.findall(r"\{([^{}]+?)\}", part)
            all_params.extend(params)
            escaped = re.escape(part)
            pat_segment = re.sub(r"\\\{([^{}]+?)\\\}", r"([^/]+)", escaped)
            re_parts.append(pat_segment)
        full_pat_str = "^" + "/".join(re_parts) + "$"
        return re.compile(full_pat_str), all_params

    @classmethod
    def _matches_router_path(cls, router_path: str, actual_path: str) -> bool:
        """
        判断实际请求路径是否匹配路由模板。

        :param router_path: 路由模板路径
        :param actual_path: 真实请求路径
        :return: 匹配返回True，否则False
        """
        if router_path == actual_path:
            return True
        if "{" not in router_path:
            return False
        pat, _ = cls._compile_router_path(router_path=router_path)
        return bool(pat.fullmatch(actual_path))

    @classmethod
    def _extract_router_path_params(cls, router_path: str, actual_path: str) -> Dict[str, str]:
        """
        路径匹配成功后提取路由参数，匹配失败返回空字典。

        :param router_path: 路由模板路径
        :param actual_path: 真实请求路径
        :return: 参数字典
        """
        if not cls._matches_router_path(router_path, actual_path):
            return {}
        pat, param_names = cls._compile_router_path(router_path)
        m = pat.fullmatch(actual_path)
        if not m:
            return {}
        return dict(zip(param_names, m.groups()))

    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        """
        校验当前用户角色是否绑定当前「方法+路径」接口权限。

        超管与管理员角色直接放行；其余用户一次查询角色接口并集，含占位符的路由模板按段匹配，避免带路径参数的接口对非超管永久 403。

        :param request: 当前请求
        :param current_user: 已认证用户
        :return: None
        :raises HTTPException: 无角色或接口未授权时返回403
        """
        if current_user.is_superuser:
            return
        roles: List[Role] = await load_request_roles(request=request, user=current_user)
        if not roles:
            raise HTTPException(status_code=403, detail="请求服务不被接受, 暂无任何角色策略")

        # 管理员角色与超管同权：全量接口放行，不依赖菜单/路由绑定记录
        if BuiltinRoleCode.includes_admin(role.code for role in roles):
            return

        method = request.method.upper()
        path = request.url.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # 多角色接口一次查出并集，避免按角色逐条查询造成 N+1；
        permission_paths = await Router.filter(
            role_routers__id__in=[role.id for role in roles]
        ).filter(
            Q(method=method) & (Q(path=path) | Q(path__contains="{"))
        ).values_list("path", flat=True)
        if not any(cls._matches_router_path(router_path=router_path, actual_path=path) for router_path in permission_paths):
            raise HTTPException(status_code=403, detail=f"请求服务不被接受, Method:{method} Path:{path}")


async def load_request_roles(request: Request, user: User) -> List[Role]:
    """取当前请求用户的角色列表，并缓存在request.state上。"""
    roles: Optional[List[Role]] = getattr(request.state, "current_roles", None)
    if roles is None:
        roles = await user.roles
        request.state.current_roles = roles
    return roles


async def get_superuser(request: Request, current_user: User = Depends(AuthControl.is_authed)) -> User:
    """仅超管或管理员角色可调用的管理员专属接口守卫。"""
    if current_user.is_superuser:
        return current_user
    roles: List[Role] = await load_request_roles(request=request, user=current_user)
    if BuiltinRoleCode.includes_admin(role.code for role in roles):
        return current_user
    raise HTTPException(status_code=403, detail="请求服务不被接受, 仅超管或管理员角色可调用")


DependAuth = Depends(AuthControl.is_authed)
DependPermission = Depends(PermissionControl.has_permission)
DependSuperUser = Depends(get_superuser)
