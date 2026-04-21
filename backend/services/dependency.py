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
from backend.services import CTX_USER_ID


class AuthControl:
    @classmethod
    async def is_authed(cls, token: str = Header(..., description="token验证")) -> Optional["User"]:
        try:
            decode_data = jwt.decode(
                jwt=token,
                key=PROJECT_CONFIG.AUTH_SECRET_KEY,
                algorithms=PROJECT_CONFIG.AUTH_JWT_ALGORITHM
            )
            user_id = decode_data.get("user_id")
            user = await User.filter(id=user_id).first()
            if not user:
                raise HTTPException(status_code=401, detail="请求服务鉴权失败")
            CTX_USER_ID.set(int(user_id))
            return user
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="请求服务鉴权失败, 请携带有效 Token 进行访问")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="请求服务鉴权已过期, 请重新登录获取有效 Token 后进行访问")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{repr(e)}")


class PermissionControl:
    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        if current_user.is_superuser:
            return
        method = str(HTTPMethod(request.method))
        # 对结尾‘/’符号进行统一化，使白名单/路径匹配稳定。
        path = request.url.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        roles: List[Role] = await current_user.roles
        if not roles:
            raise HTTPException(status_code=403, detail="请求服务不被接受, 暂无任何角色策略")
        # role.routers 保存了该角色可访问的接口（method + path）
        routers = [await role.routers for role in roles]
        permission_apis = list(set((str(router.method), router.path) for router in sum(routers, [])))
        # method = "GET"
        if (method, path) not in permission_apis:
            raise HTTPException(status_code=403, detail=f"请求服务不被接受, Method:{method} Path:{path}")


DependAuth = Depends(AuthControl.is_authed)
DependPermission = Depends(PermissionControl.has_permission)
