# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : password.py
@DateTime: 2025/1/18 12:10
"""
import jwt
from passlib import pwd
from passlib.context import CryptContext

from backend import PROJECT_CONFIG
from backend.applications.base.schemas.tokens_schema import JWTPayload

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_password() -> str:
    return pwd.genword()


def create_access_token(*, data: JWTPayload):
    payload = data.model_dump().copy()
    encoded_jwt = jwt.encode(
        payload,
        PROJECT_CONFIG.AUTH_SECRET_KEY,
        algorithm=PROJECT_CONFIG.AUTH_JWT_ALGORITHM
    )
    return encoded_jwt
