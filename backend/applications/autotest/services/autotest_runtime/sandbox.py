# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : sandbox.py
@DateTime: 2025/12/28 16:15
"""
from __future__ import annotations

import base64
import builtins as _builtins_module
import calendar
import collections
import decimal
import fractions
import functools
import itertools
import json
import math
import operator
import random
import re
import statistics
import string
import time
import typing
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

_builtin_import = _builtins_module.__import__


class ReadonlyModuleProxy:
    """
    白名单模块只读代理。

    阻断用户代码改写/删除共享模块属性, 如json.dumps=None污染同进程后续执行；
    并按模块封禁字符串间接取属性的危险工厂, 如operator.attrgetter/methodcaller以字符串做属性访问, 可完全绕过AST对下划线属性的封禁，串起__base__/__subclasses__反射链逃逸沙箱）。
    """

    __slots__ = ("_target", "_blocked")

    def __init__(self, target: Any, blocked: frozenset = frozenset()) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_blocked", blocked)

    def __getattr__(self, item: str) -> Any:
        if item in self._blocked:
            raise AttributeError(f"代码请求(Python)步骤中禁止使用该模块能力: {item}")
        return getattr(self._target, item)

    def __setattr__(self, key: str, value: Any) -> None:
        raise AttributeError(f"代码请求(Python)步骤中禁止改写模块属性: {key}")

    def __delattr__(self, item: str) -> None:
        raise AttributeError(f"代码请求(Python)步骤中禁止删除模块属性: {item}")

    def __repr__(self) -> str:
        return repr(self._target)


class UserCodeSandbox:
    """
    代码请求(Python)步骤沙箱：策略常量与执行上下文工厂（无实例状态，请勿实例化）。

    防护策略总览（与引擎_validate_user_python_restricted/run_python_code协同）：
    1. 源码长度上限 MAX_CODE_LENGTH —— 防超大输入撑爆AST解析与编译；
    2. AST静态校验（引擎消费本类ALLOWED_IMPORT_ROOTS/FORBIDDEN_ATTRS/ALLOWED_PRIVATE_ATTRS）：
       import白名单、下划线属性封禁（namedtuple只读方法例外）、帧自省属性封禁、禁class/async def；
    3. 受限builtins SAFE_BUILTINS —— 剔除open/input/eval/exec/compile/getattr/setattr等危险内建；
    4. 白名单模块只读代理 MODULE_PROXIES —— 防改写共享模块属性；operator封attrgetter/methodcaller；
    5. 受限导入钩子 _restricted_import —— 仅放行白名单根模块及其惰性私有依赖，白名单返回代理；
    6. 执行上下文隔离 new_exec_context —— builtins逐次浅拷贝防写穿，剥离namespace的__builtins__注入；
    7. 启动自验 _startup_selftest —— 进程导入期经工厂构建的完整沙箱路径执行特性探针，拦截缺陷启动期暴露。
    """

    # 匹配裸占位符: ${xxx}
    RE_PLACEHOLDER = re.compile(r"\$\{([^}]+)}")
    # 匹配引号包裹的占位符: "${var}"
    RE_QUOTED_PLACEHOLDER = re.compile(r"(['\"])\$\{([^}]+)}\1")
    # 匹配引号内拼接: "prefix_${var}_suffix"
    RE_QUOTED_CONCAT = re.compile(r"(['\"])((?:(?!\1).)*?)\$\{([^}]+)}((?:(?!\1).)*?)\1")

    # 源码长度上限（步骤代码为数据整形片段，64K足够；防超大输入撑爆AST解析与编译）
    MAX_CODE_LENGTH = 64 * 1024
    # 自省逃逸属性族：非下划线命名但可触达帧/协程/追溯对象（如gi_frame串起f_back/f_globals帧链触达引擎全局）
    FORBIDDEN_ATTRS = frozenset({
        "gi_frame", "gi_code", "gi_yieldfrom",
        "cr_frame", "cr_code", "cr_await",
        "ag_frame", "ag_code", "ag_await",
        "f_back", "f_builtins", "f_code", "f_globals", "f_locals", "f_trace",
        "tb_frame", "tb_next", "cell_contents",
    })
    # 下划线属性封禁的白名单例外：collections.namedtuple实例的只读工具方法（数据整形常用且无自省能力）
    ALLOWED_PRIVATE_ATTRS = frozenset({"_replace", "_asdict", "_make", "_fields", "_field_defaults"})

    # 白名单模块（纯计算/数据整形标准库，无文件/网络/进程/数据库能力），经只读代理注入
    _WHITELIST_MODULES: Dict[str, Any] = {
        "json": json,
        "random": random,
        "typing": typing,
        # 时间日期
        "time": time,
        "calendar": calendar,
        # 容器、迭代、函数式
        "operator": operator,
        "itertools": itertools,
        "functools": functools,
        "collections": collections,
        # 数值&数学
        "math": math,
        "decimal": decimal,
        "fractions": fractions,
        "statistics": statistics,
        # 文本、编码、正则
        "re": re,
        "string": string,
        "base64": base64,
    }
    MODULE_PROXIES: Dict[str, ReadonlyModuleProxy] = {
        name: ReadonlyModuleProxy(mod, frozenset({"attrgetter", "methodcaller"}) if name == "operator" else frozenset())
        for name, mod in _WHITELIST_MODULES.items()
    }
    # import/from允许的根模块；timedelta为类预绑定而非模块（不存在timedelta模块），不参与import判定
    ALLOWED_IMPORT_ROOTS = frozenset(_WHITELIST_MODULES) | {"datetime"}
    # 白名单模块运行期惰性加载的私有实现模块：datetime.strptime被调用时才会触发import _strptime
    _LAZY_IMPORT_ROOTS = frozenset({"_strptime"})

    @staticmethod
    def _restricted_import(
            name: str,
            globals: Optional[Dict[str, Any]] = None,
            locals: Optional[Dict[str, Any]] = None,
            fromlist: Tuple[Any, ...] = (),
            level: int = 0,
    ) -> Any:
        """
        受限导入，仅加载白名单根模块及其惰性私有依赖，禁止相对导入。

        作为沙箱__builtins__.__import__钩子，用户代码及白名单模块运行期触发的一切import均经此拦截。
        :param name: 模块名
        :param globals: 全局命名空间
        :param locals: 局部命名空间
        :param fromlist: from ... import的子模块列表
        :param level: 相对导入层级，非0则拒绝
        :return: 导入的模块对象（白名单返回只读代理）
        """
        if level != 0:
            raise ImportError("代码请求(Python)步骤中不允许使用相对路径导入模块")

        root = name.partition(".")[0]
        if root not in UserCodeSandbox.ALLOWED_IMPORT_ROOTS and root not in UserCodeSandbox._LAZY_IMPORT_ROOTS:
            allowed = "、".join(sorted(UserCodeSandbox.ALLOWED_IMPORT_ROOTS))
            raise ImportError(f"代码请求(Python)步骤中不允许导入[{name!r}]模块, 仅允许: {allowed}")
        module = _builtin_import(name, globals, locals, fromlist, level)
        # 用户白名单模块返回只读代理；内部惰性依赖（如_strptime）供标准库内部使用，须返回真实模块
        return UserCodeSandbox.MODULE_PROXIES.get(root, module)

    # 沙箱builtins，进程内一次构建（执行期经new_exec_context逐次浅拷贝隔离，防用户代码写穿共享常量）。
    # 仅保留纯计算内建；刻意剔除open/input/eval/exec/compile/globals/locals/vars/dir/exit/quit/help，
    # 以及getattr/setattr/hasattr/delattr——后者可用字符串属性名绕过AST对双下划线属性访问的封禁
    SAFE_BUILTINS: Dict[str, Any] = {
        "__import__": _restricted_import.__func__,
        # 基础类型
        "bool": bool,
        "bytes": bytes,
        "bytearray": bytearray,
        "dict": dict,
        "float": float,
        "frozenset": frozenset,
        "int": int,
        "list": list,
        "set": set,
        "str": str,
        "tuple": tuple,
        # 常用异常：用户代码依赖raise/except做数据校验
        "Exception": Exception,
        "ArithmeticError": ArithmeticError,
        "AssertionError": AssertionError,
        "AttributeError": AttributeError,
        "IndexError": IndexError,
        "KeyError": KeyError,
        "LookupError": LookupError,
        "NameError": NameError,
        "NotImplementedError": NotImplementedError,
        "OverflowError": OverflowError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        "TypeError": TypeError,
        "TimeoutError": TimeoutError,
        "UnicodeDecodeError": UnicodeDecodeError,
        "UnicodeEncodeError": UnicodeEncodeError,
        "ValueError": ValueError,
        "ZeroDivisionError": ZeroDivisionError,
        # 数学运算
        "abs": abs,
        "divmod": divmod,
        "max": max,
        "min": min,
        "pow": pow,
        "round": round,
        "sum": sum,
        # 进制/编码转换
        "bin": bin,
        "chr": chr,
        "hex": hex,
        "oct": oct,
        "ord": ord,
        # 迭代/序列操作
        "all": all,
        "any": any,
        "enumerate": enumerate,
        "filter": filter,
        "iter": iter,
        "len": len,
        "map": map,
        "next": next,
        "range": range,
        "reversed": reversed,
        "sorted": sorted,
        "zip": zip,
        # 类型判断与值处理
        "callable": callable,
        "format": format,
        "hash": hash,
        "id": id,
        "isinstance": isinstance,
        "issubclass": issubclass,
        # "type": type,
        # 输出/调试
        # "print": print,
        # "repr": repr,
        # 白名单模块对象（只读代理）；datetime/timedelta预绑定为类（C类型属性天然不可变，无需代理）
        **MODULE_PROXIES,
        "datetime": datetime,
        "timedelta": timedelta,
    }

    @classmethod
    def new_exec_context(cls, namespace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        构建单次执行的隔离上下文，可直接传入exec。

        builtins逐次浅拷贝（防用户代码写穿共享常量）；namespace剥离__builtins__注入后并入同一字典——
        单命名空间使def函数的__globals__即该字典，函数体内可见namespace变量且支持递归
        （若globals/locals分离，函数__globals__仅含builtins，函数体引用namespace会NameError）。
        :param namespace: 执行时的局部命名空间（如变量字典），可选；不改动调用方字典
        :return: exec上下文字典
        """
        context: Dict[str, Any] = {"__builtins__": dict(cls.SAFE_BUILTINS)}
        if namespace:
            context.update({key: value for key, value in namespace.items() if key != "__builtins__"})
        return context

    @classmethod
    def _startup_selftest(cls) -> None:
        """
        启动期自验：经new_exec_context构建的完整沙箱环境（受限builtins+导入钩子）执行各白名单特性的代表性探针。

        将拦截缺陷从用户运行期提前到进程启动期暴露：白名单模块若在运行期惰性加载私有实现模块
        （如datetime.strptime调用时才触发import _strptime），自验失败会在启动报错中指名待加入
        _LAZY_IMPORT_ROOTS的根模块；同时兼作惰性模块预热与Python版本升级回归哨兵。
        新增白名单模块时必须在此追加代表性探针。
        :return: None
        """
        probe_context = cls.new_exec_context()
        exec(
            "result = datetime.strptime('2000-01-01', '%Y-%m-%d').year"
            " + json.loads('{\"a\": 1}')['a'] + random.randint(1, 1)"
            " + len(string.digits) + timedelta(days=1).days"
            " + int(math.sqrt(16.0)) + int(decimal.Decimal('2.5') * 2)"
            " + fractions.Fraction(1, 2).denominator + int(statistics.mean([1, 2]))"
            " + len(base64.b64encode(b'a')) + calendar.isleap(2024)"
            " + len(collections.Counter('aab')) + len(list(itertools.chain([1], [2])))"
            " + functools.reduce(lambda a, b: a + b, [1, 2, 3]) + operator.add(1, 1)"
            " + (1 if re.match(r'\\d+', '123') else 0)"
            " + (1 if typing.Dict is not None else 0) + (1 if time.time() > 0 else 0)",
            probe_context,
        )
        if probe_context["result"] != 2045:
            raise RuntimeError("代码请求(Python)沙箱启动自验失败: 白名单模块特性探测结果异常")


UserCodeSandbox._startup_selftest()
