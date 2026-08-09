# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : dependency.py
@DateTime: 2025/2/19 13:03
"""
from typing import Optional, List

import jwt
from fastapi import Depends, Header, HTTPException, Request

from backend.applications.base.models.role_model import Role
from backend.applications.user.models.user_model import User
from backend.configure import PROJECT_CONFIG
from backend.enums import HTTPMethod
from backend.services import CTX_USER_ID, CTX_USERNAME


class AuthControl:
    @classmethod
    async def is_authed(cls, token: str = Header(..., description="token验证")) -> Optional["User"]:
        try:
            if token == PROJECT_CONFIG.AUTH_JWT_TEMPORARY_TOKEN:
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
    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        if current_user.is_superuser:
            return
        # 使用枚举value，避免 str(HTTPMethod.POST)=="HTTPMethod.POST" 与库内 "POST" 匹配失败
        method = HTTPMethod(request.method).value
        # 对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。
        path = request.url.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        roles: List[Role] = await current_user.roles
        if not roles:
            raise HTTPException(status_code=403, detail="请求服务不被接受, 暂无任何角色策略")
        # role.routers 保存了该角色可访问的接口（method + path）
        routers = [await role.routers for role in roles]
        permission_apis = list(
            set(
                (
                    (router.method.value if hasattr(router.method, "value") else str(router.method)),
                    router.path,
                )
                for router in sum(routers, [])
            )
        )
        if (method, path) not in permission_apis:
            raise HTTPException(status_code=403, detail=f"请求服务不被接受, Method:{method} Path:{path}")


DependAuth = Depends(AuthControl.is_authed)
DependOptionalAuth = Depends(AuthControl.is_authed_optional)
DependPermission = Depends(PermissionControl.has_permission)
