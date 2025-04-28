# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : runcode.py
@DateTime: 2025/2/23 12:04
"""
import asyncio
import subprocess
import traceback

from fastapi import HTTPException

from backend.core.exceptions.base_exceptions import ImportedException, SyntaxException, MaxTimeoutException, \
    ReqInvalidException
from backend.core.responses.http_response import BadReqResponse, RequestTimeoutResponse


def validate_python_code(code: str):
    """基础代码验证"""
    forbidden_patterns = [
        ('os.system', '禁止访问系统命令'),
        ('subprocess', '禁止创建子进程'),
        ('open(', '禁止文件操作'),
        ('import os', '禁止导入系统模块'),
        ('import subprocess', '禁止导入子进程模块')
    ]

    for pattern, msg in forbidden_patterns:
        if pattern in code:
            raise ImportedException(message=msg)


async def run_python_code(code: str, timeout: int = 60):
    try:
        # 执行前验证代码
        validate_python_code(code)

        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                'python3', '-c', code,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ),
            timeout=timeout
        )

        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip()
        error = stderr.decode().strip()

        # 处理常见错误类型
        if "SyntaxError" in error:
            error_lines = error.split('\n')
            simplified_error = '\n'.join(error_lines[-3:])
            raise SyntaxException(message=f"语法错误: {simplified_error}")

        return {"result": output, "error": error}
    except asyncio.TimeoutError:
        raise MaxTimeoutException(message="代码执行耗时不被允许（30秒限制）")
    except Exception as e:
        traceback_str = traceback.format_exc()
        raise ReqInvalidException(message=traceback_str)
