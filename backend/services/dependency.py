# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependency.py
@DateTime: 2025/2/19 13:03
"""
from typing import Optional, List

import jwt
from fastapi import Depends, Header, HTTPException, Request

from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.user.models.user_model import User
from backend.configure import PROJECT_CONFIG
from backend.enums import BuiltinRoleCode, HTTPMethod
from backend.services import CTX_USER_ID, CTX_USERNAME


class AuthControl:
    @classmethod
    async def is_authed(cls, token: str = Header(..., description="token验证")) -> Optional["User"]:
        try:
            if token == PROJECT_CONFIG.AUTH_TEMPORARY_TOKEN:
                user_id: int = 1
                user = await User.filter(id=user_id, state__not=1).first()
            else:
                decode_data = jwt.decode(
                    jwt=token,
                    key=PROJECT_CONFIG.AUTH_SECRET_KEY,
                    algorithms=PROJECT_CONFIG.AUTH_JWT_ALGORITHM
                )
                user_id = decode_data.get("user_id")
                user = await User.filter(id=user_id, state__not=1).first()
                if not user:
                    raise HTTPException(status_code=401, detail="请求服务鉴权失败, 用户状态异常, 请联系管理员后重试")

                token_version = decode_data.get("token_version", 0)
                if token_version != user.token_version:
                    raise HTTPException(status_code=401, detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")

            CTX_USER_ID.set(int(user_id))
            CTX_USERNAME.set((user.username or "").strip())
            return user
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="请求服务鉴权失败, 请携带有效 Token 进行访问")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{repr(e)}")

    @classmethod
    async def is_authed_optional(cls, token: Optional[str] = Header(None, description="token验证(可选)")) -> Optional["User"]:
        """无token时放行且不写CTX；有token时校验并写入CTX_USERNAME，用于注册是公开接口：默认匿名可访问，管理员代建用户时可带token自动填充创建人。"""
        if token is None or not str(token).strip():
            return None
        return await cls.is_authed(token=str(token).strip())


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
        if current_user.is_superuser:
            return
        roles: List[Role] = await current_user.roles
        if not roles:
            raise HTTPException(status_code=403, detail="请求服务不被接受, 暂无任何角色策略")
        # 管理员角色与超管同权：全量接口放行，不依赖菜单/路由绑定记录
        if BuiltinRoleCode.includes_admin(role.code for role in roles):
            return
        # 使用枚举value，避免 str(HTTPMethod.POST)=="HTTPMethod.POST" 与库内 "POST" 匹配失败
        method = HTTPMethod(request.method).value
        # 对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。
        path = request.url.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        # 多角色接口一次查出并集，避免按角色逐条查询造成 N+1
        permission_apis = await Router.filter(
            role_routers__id__in=[role.id for role in roles]
        ).values_list("method", "path")
        # 路由模板可含 {param} 占位，需按段匹配；否则含路径参数的接口对非超管永久 403
        if not any(
                method == (router_method.value if hasattr(router_method, "value") else str(router_method))
                and cls._path_matches(router_path, path)
                for router_method, router_path in permission_apis
        ):
            raise HTTPException(status_code=403, detail=f"请求服务不被接受, Method:{method} Path:{path}")


async def get_superuser(current_user: User = Depends(AuthControl.is_authed)) -> User:
    """仅任务执行引擎、超管或管理员角色可调用的内部写接口守卫。"""
    if current_user.is_superuser:
        return current_user
    roles: List[Role] = await current_user.roles
    if BuiltinRoleCode.includes_admin(role.code for role in roles):
        return current_user
    raise HTTPException(status_code=403, detail="请求服务不被接受, 仅任务执行引擎或管理员可调用")


DependAuth = Depends(AuthControl.is_authed)
DependOptionalAuth = Depends(AuthControl.is_authed_optional)
DependPermission = Depends(PermissionControl.has_permission)
DependSuperUser = Depends(get_superuser)
