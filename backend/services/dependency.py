# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependency.py
@DateTime: 2025/2/19 13:03
"""
import hmac
from typing import List, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request
from tortoise.expressions import Q

from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.enums import BuiltinRoleCode
from backend.services import CTX_USER_ID, CTX_USERNAME

# 认证必需声明：缺任一关键声明即视为非法令牌，避免无过期时间的长效凭证绕过
REQUIRED_CLAIMS: tuple = ("exp", "user_id", "token_version")


class AuthControl:
    @classmethod
    async def is_authed(cls, request: Request, token: str = Header(..., description="token验证")) -> "User":
        """
        认证当前请求并写入用户上下文。

        同一请求内中间件、路由依赖、审计会重复调用，命中 request.state 缓存时不再查库；
        缓存命中仍需重建上下文变量（中间件与端点可能运行在不同任务）。
        """
        user = getattr(request.state, "current_user", None)
        if user is not None:
            CTX_USER_ID.set(int(user.id))
            CTX_USERNAME.set((user.username or "").strip())
            return user

        configured = PROJECT_CONFIG.AUTH_TEMPORARY_TOKEN
        # 常量时间比对，避免通过响应耗时逐字符探测；空值表示开发用临时令牌未启用
        is_temporary = bool(configured) and hmac.compare_digest(str(token), str(configured))
        try:
            # 临时令牌本质是预签发的长效 JWT，必须与其他令牌一样受 exp / token_version 约束
            decode_data = jwt.decode(
                jwt=configured if is_temporary else token,
                key=PROJECT_CONFIG.AUTH_SECRET_KEY,
                algorithms=PROJECT_CONFIG.AUTH_JWT_ALGORITHM,
                options={"require": list(REQUIRED_CLAIMS)},
            )
            user = await User.filter(id=int(decode_data["user_id"]), state__not=1).first()
            if not user:
                raise HTTPException(status_code=401, detail="请求服务鉴权失败, 用户状态异常, 请联系管理员后重试")

            if int(decode_data["token_version"]) != user.token_version:
                raise HTTPException(status_code=401, detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")

            request.state.current_user = user
            CTX_USER_ID.set(int(user.id))
            CTX_USERNAME.set((user.username or "").strip())
            return user
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            if is_temporary:
                raise HTTPException(status_code=401, detail="开发用临时令牌已过期, 请重新签发后再使用")
            raise HTTPException(status_code=401, detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")
        except jwt.InvalidTokenError:
            if is_temporary:
                LOGGER.error("开发用临时令牌配置非法, 无法按JWT解析, 请重新签发后再使用")
            raise HTTPException(status_code=401, detail="请求服务鉴权失败, 请携带有效 Token 进行访问")
        except Exception as e:
            # 内部异常不向调用方暴露细节，日志留痕后统一返回服务异常
            LOGGER.error(f"请求认证异常: {e!r}")
            raise HTTPException(status_code=500, detail="请求服务鉴权异常, 请稍后重试")


class PermissionControl:
    @staticmethod
    def _path_matches(template: str, path: str) -> bool:
        """
        路由模板与请求路径匹配：`{param}` 视为单段通配。

        :param template: krun_router 中登记的路由路径，可含 `{param}` 占位
        :param path: 实际请求路径
        :return: 匹配返回True
        """
        if template == path:
            return True
        if "{" not in template:
            return False
        template_parts = template.strip("/").split("/")
        path_parts = path.strip("/").split("/")
        if len(template_parts) != len(path_parts):
            return False
        for template_part, path_part in zip(template_parts, path_parts):
            if template_part.startswith("{") and template_part.endswith("}"):
                if not path_part:
                    return False
                continue
            if template_part != path_part:
                return False
        return True

    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        """
        校验当前用户角色是否绑定当前「方法+路径」接口权限。

        超管与管理员角色直接放行；其余用户一次查询角色接口并集，
        含占位符的路由模板按段匹配，避免带路径参数的接口对非超管永久 403。

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
        # 统一大写：库内 method 为 HTTPMethod 值，直接比较字符串可避免非标准方法构造枚举报错
        method = request.method.upper()
        # 对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。
        path = request.url.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        # 多角色接口一次查出并集，避免按角色逐条查询造成 N+1；
        # 只取本次方法且路径为「精确匹配或含占位模板」的记录，避免每次拉全量路由再逐个比对
        permission_paths = await Router.filter(
            role_routers__id__in=[role.id for role in roles]
        ).filter(
            Q(method=method) & (Q(path=path) | Q(path__contains="{"))
        ).values_list("path", flat=True)
        # 路由模板可含 {param} 占位，需按段匹配；否则含路径参数的接口对非超管永久 403
        if not any(cls._path_matches(router_path, path) for router_path in permission_paths):
            raise HTTPException(status_code=403, detail=f"请求服务不被接受, Method:{method} Path:{path}")


async def load_request_roles(request: Request, user: User) -> List[Role]:
    """
    取当前请求用户的角色列表，并缓存在 request.state 上。

    available_only_admin 接口同时挂鉴权与超管守卫，Tortoise 的关系查询不走实例缓存，
    不共享结果会重复查同一张关联表。
    """
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
