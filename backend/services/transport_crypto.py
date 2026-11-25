# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : transport_crypto.py
@DateTime: 2026/11/25 10:00

环境配置密码传输加密工具（RSA-2048 + PKCS1 v1.5）。

契约：config_password 以密文传输并原样落库，保存/查询链路零加解密；
保存期只做密文格式校验拒明文（assert_cipher_format），
执行期建连接池时解密还原明文（decrypt_password），
公钥经 /base/security/get_public_key 提供前端加密，刷库脚本用 encrypt_password。
私钥来自 .env 的 SECURITY_RSA_PRIVATE_KEY，与 AUTH_SECRET_KEY 完全隔离。
"""
import base64
import binascii
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.configure import PROJECT_CONFIG, LOGGER
from backend.core.exceptions import ParameterException

# RSA-2048 密文固定256字节，base64后固定344字符；PKCS1 v1.5 单块明文上限245字节
_CIPHER_BYTES: int = 256
_CIPHER_TEXT_LENGTH: int = 344
_MAX_PLAIN_BYTES: int = 245


@lru_cache(maxsize=1)
def _load_private_key() -> rsa.RSAPrivateKey:
    """加载并缓存私钥；位数锁定2048，避免换钥后密文长度超出存储列宽。"""
    pem_bytes = base64.b64decode(PROJECT_CONFIG.SECURITY_RSA_PRIVATE_KEY, validate=True)
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 2048:
        raise ValueError("配置[SECURITY_RSA_PRIVATE_KEY]必须为RSA-2048私钥")
    return key


def get_public_key_pem() -> str:
    """由私钥推导PEM公钥，供前端加密接口返回。"""
    return _load_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def encrypt_password(plain: str) -> str:
    """
    公钥加密密码为base64密文，供存量刷库脚本使用。

    :param plain: 密码明文
    :return: base64密文（344字符）
    :raises ValueError: 明文超过PKCS1 v1.5单块上限
    """
    data = plain.encode("utf-8")
    if len(data) > _MAX_PLAIN_BYTES:
        raise ValueError(f"密码明文超过{_MAX_PLAIN_BYTES}字节, 无法加密")
    cipher = _load_private_key().public_key().encrypt(data, padding.PKCS1v15())
    return base64.b64encode(cipher).decode("ascii")


def decrypt_password(cipher: str) -> str:
    """
    执行期解密密码密文，供数据库/Redis连接池建连使用。

    :param cipher: base64密文
    :return: 密码明文
    :raises ValueError: 密文非法、密钥不匹配或解密失败（连接池侧按建池失败处理）
    """
    try:
        raw = base64.b64decode(cipher, validate=True)
        plain = _load_private_key().decrypt(raw, padding.PKCS1v15())
        return plain.decode("utf-8")
    except Exception as e:
        # 密文与明文均不落日志，只记录错误类型便于定位
        LOGGER.error(f"密码密文解密失败, 错误类型: {type(e).__name__}")
        raise ValueError("密码密文解密失败, 请检查加密密钥与密文是否匹配") from e


def assert_cipher_format(value: str) -> None:
    """
    保存期密文格式校验（拒明文）：仅接受RSA-2048密文的base64形态。

    :param value: 入参密码值（非空时调用）
    :raises ParameterException: 非base64或长度不符合密文特征
    """
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raw = None
    if raw is None or len(value) != _CIPHER_TEXT_LENGTH or len(raw) != _CIPHER_BYTES:
        error_message: str = "参数[config_password]必须为RSA加密密文, 不接受明文传递"
        LOGGER.error(error_message)
        raise ParameterException(message=error_message)


if __name__ == '__main__':
    print("公钥：", get_public_key_pem())
    # 加密：返回344字符base64密文
    # dkGdrS9C+mmCennM+ctSNDCCSD0BmdEPnl7hQBanoUexLK/mVc6IPwSS6EWZKBDobtTszFWs/xeOAGn0do/6OhInd/ebHxCaKmpKr4NrWsQyOEJd+WHV432M+wE9fAcTH4ENDnYFAmiYjNcFZgrgT3K+5cU4/2yROrNjwVAWFb9KY+mNeV5Vl8oILWj4eL6/i5ejuDmtBDC6779AVAFXU51mc4xrAE1V4SCt51qHGIF1tZ7EW2ZzDXjbz92DwCmCc1wzAvS6ZZj+82DXWWkgfJok5lQ5NFyR8iWu2cQLrjItNn3e8+rXxp8byCXbnNo/mbWxjPh6T1wKs5822c+9gQ==
    cipher = encrypt_password("KFuser01@!")
    # 解密：还原明文
    plain = decrypt_password(cipher)
    print("加密：", cipher)
    print("解密：", plain)
