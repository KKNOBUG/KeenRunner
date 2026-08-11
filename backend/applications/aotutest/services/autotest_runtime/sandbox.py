# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : sandbox.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import builtins as _builtins_module
import json
import random
import re
import string
import time
import typing
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

# 1.匹配裸的占位符，如: ${xxx}（报文占位符与 Python 代码占位符共用）
_RE_PLACEHOLDER = re.compile(r"\$\{([^}]+)}")
# 2.匹配同一引号包裹的占位符，如: "${var}"
_RE_QUOTED_PLACEHOLDER = re.compile(r"(['\"])\$\{([^}]+)}\1")
# 3.匹配同一引号内的拼接，如: "prefix_${var}_suffix"
_RE_QUOTED_CONCAT = re.compile(r"(['\"])((?:(?!\1).)*?)\$\{([^}]+)}((?:(?!\1).)*?)\1")

# 用户 Python 步骤：允许的 import 根名 → 预注入 builtins（单一配置；扩展时只改此处）
# 注：datetime 预绑定为 datetime 类（兼容直接写 datetime.now()）；import datetime 仍得到标准库模块
_USER_CODE_EXTRA_BUILTINS: Dict[str, Any] = {
    "random": random,
    "time": time,
    "datetime": datetime,
    "timedelta": timedelta,
    "typing": typing,
    "string": string,
    "json": json,
}
_USER_CODE_ALLOWED_IMPORT_ROOTS = frozenset(_USER_CODE_EXTRA_BUILTINS.keys())
_builtin_import = _builtins_module.__import__


def _safe_user_code_import(
        name: str,
        globals: Optional[Dict[str, Any]] = None,
        locals: Optional[Dict[str, Any]] = None,
        fromlist: Tuple[Any, ...] = (),
        level: int = 0,
) -> Any:
    """
    供run_python_code的exec使用：__import__仅加载白名单根模块，禁止相对导入。

    :param name: 模块名
    :param globals: 全局命名空间
    :param locals: 局部命名空间
    :param fromlist: from ... import的子模块列表
    :param level: 相对导入层级，非0则拒绝
    :return: 导入的模块对象
    """
    if level != 0:
        raise ImportError("代码请求(Python)步骤中不允许使用相对路径导入模块")

    root = name.partition(".")[0]
    if root not in _USER_CODE_ALLOWED_IMPORT_ROOTS:
        allowed = "、".join(sorted(_USER_CODE_ALLOWED_IMPORT_ROOTS))
        raise ImportError(f"代码请求(Python)步骤中不允许导入[{name!r}]模块, 仅允许: {allowed}")
    return _builtin_import(name, globals, locals, fromlist, level)


# 对外公开别名（步骤引擎等应导入下列名称，勿依赖下划线私有符号）
RE_PLACEHOLDER = _RE_PLACEHOLDER
RE_QUOTED_PLACEHOLDER = _RE_QUOTED_PLACEHOLDER
RE_QUOTED_CONCAT = _RE_QUOTED_CONCAT
USER_CODE_EXTRA_BUILTINS = _USER_CODE_EXTRA_BUILTINS
USER_CODE_ALLOWED_IMPORT_ROOTS = _USER_CODE_ALLOWED_IMPORT_ROOTS
safe_user_code_import = _safe_user_code_import
