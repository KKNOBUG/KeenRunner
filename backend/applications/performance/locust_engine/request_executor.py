# -*- coding: utf-8 -*-
"""
施压请求构造与断言执行器(由 locust 子进程加载, 禁止 import backend 主包)。

占位符渲染、来源提取与断言比较语义对齐 autotest_runtime 的
placeholders/resolver、exchange/extractors、exchange/assert_compare;
数据源路径替换复刻见同目录 datagram_replace(语义对齐 autotest datagram 模块)。
引擎内独立实现(仅依赖标准库与orjson/jsonpath_ng), 一致性由对齐测试锁定,
调整任一侧时必须同步评估另一侧。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : request_executor.py
@DateTime: 2026/9/14 14:40
"""
from __future__ import annotations

import copy
import json
import operator
import random
import re
import time
import uuid
from itertools import cycle
from typing import Any, Callable, Dict, List, Optional, Tuple

import orjson
from jsonpath_ng import parse as jsonpath_parse

try:  # locust子进程按平铺模块导入(perf_locustfile已将本目录注入sys.path)
    from datagram_replace import PerfJsonDatagram, PerfXmlDatagram
except ImportError:  # backend进程按包路径导入
    from backend.applications.performance.locust_engine.datagram_replace import (
        PerfJsonDatagram,
        PerfXmlDatagram,
    )

# 断言操作符合法取值: 与 backend AutoTestAssertionOperation 枚举值逐字一致(引擎内不可import枚举)
ASSERTION_OPERATIONS: Tuple[str, ...] = (
    "等于", "不等于", "大于", "大于等于", "小于", "小于等于",
    "长度等于", "数组长度等于", "包含", "不包含", "属于集合", "不属于集合",
    "以...开始", "以...结束", "不为空", "为空",
)
# 请求参数类型取值: 与 AutoTestReqArgsType 枚举值一致
ARGS_TYPE_JSON = "json"
ARGS_TYPE_RAW = "raw"
ARGS_TYPE_XML = "xml"
ARGS_TYPE_NONE = "none"
ARGS_TYPE_PARAMS = "params"
ARGS_TYPE_FORM_DATA = "form-data"
ARGS_TYPE_X_WWW_FORM_URLENCODED = "x-www-form-urlencoded"
# XML 报文缺省内容类型(与 autotest assemble_http_body_payloads 补齐口径一致)
XML_DEFAULT_CONTENT_TYPE = "application/xml; charset=utf-8"

# 数据集场景分配策略取值: 与 PerfDatasetStrategy 枚举值一致; unique 为虚拟用户独占场景,
# 由施压入口在虚拟用户启动时分配场景下标后经 fixed_scene_index 注入, 构造器内只实现可重复取场景策略
DATASET_ROUND_ROBIN = "round_robin"
DATASET_RANDOM = "random"

# 变量占位符: ${name} 形式, 大小写敏感(与 autotest 占位符约定一致)
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
# 内置函数调用形态: ${__funcName(arg1,arg2)}, "__"前缀为引擎保留字(不参与数据集列推导)
BUILTIN_CALL_PATTERN = re.compile(r"^(__[A-Za-z][A-Za-z0-9_]*)\((.*)\)$", re.S)


# ============================ 内置函数注册表 ============================

def _builtin_timestamp() -> int:
    """当前秒级时间戳(整型)。"""
    return int(time.time())


def _builtin_uuid() -> str:
    """随机UUID(标准带横杠格式)。"""
    return str(uuid.uuid4())


def _builtin_random_int(min_value: Any, max_value: Any) -> int:
    """[min, max]闭区间随机整数(语义对齐 JMeter __Random)。"""
    return random.randint(int(min_value), int(max_value))


# 内置函数注册表: 名称 -> (实现, 参数签名, 说明)。
# 口径单点: 施压渲染与接口调试链路共用本注册表; PerfApiForm 参数化说明文案为前端镜像,
# 新增或调整函数时必须两侧同步。同名变量优先于内置函数(与内置变量同名不覆盖用户变量同语义)
BUILTIN_FUNCTIONS: Dict[str, Tuple[Callable[..., Any], str, str]] = {
    "__timestamp": (_builtin_timestamp, "__timestamp()", "当前秒级时间戳"),
    "__uuid": (_builtin_uuid, "__uuid()", "随机UUID"),
    "__randomInt": (_builtin_random_int, "__randomInt(min, max)", "闭区间随机整数"),
}


def _coerce_builtin_arg(text: str) -> Any:
    """内置函数参数字面量转换: 整数 > 浮点数 > 原样文本。"""
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _eval_builtin(name: str) -> Tuple[bool, Any]:
    """
    按内置函数注册表求值占位符名称。

    :param name: 占位符名称(如 __randomInt(1, 9))
    :return: (是否命中, 求值结果); 非函数形态/未知函数/参数不合法导致执行失败时未命中,
        由调用方按未命中变量告警并保留占位符原样
    """
    match = BUILTIN_CALL_PATTERN.match(name)
    if not match:
        return False, None
    entry = BUILTIN_FUNCTIONS.get(match.group(1))
    if entry is None:
        return False, None
    raw_args = match.group(2).strip()
    args: Tuple[Any, ...] = ()
    if raw_args:
        args = tuple(_coerce_builtin_arg(part.strip()) for part in raw_args.split(","))
    try:
        return True, entry[0](*args)
    except Exception:
        return False, None


# ============================ 占位符渲染 ============================

def render_placeholders(value: Any, lookup: Dict[str, Any]) -> Tuple[Any, List[str]]:
    """
    递归渲染 str/dict/list 中的 ${name} 占位符(大小写敏感)。

    整串恰为单个占位符且变量命中时保留变量原始类型(整型ID等不被字符串化,
    避免破坏JSON请求结构); 拼接场景以 str 替换; 未命中的占位符保留原样并
    收集变量名, 由调用方决定是否告警。
    "__"前缀的内置函数占位符(如 ${__uuid()})由注册表在渲染时求值,
    同名用户变量优先于内置函数。

    :param value: 待渲染的任意结构
    :param lookup: 变量池字典(初始变量池合并数据集行)
    :return: (渲染后的同构结构, 未命中占位符名列表)
    :example:
        >>> render_placeholders("/api/users/${uid}", {"uid": 1001})
        ('/api/users/1001', [])
    """
    missing: List[str] = []

    def render_text(content: str) -> Any:
        """渲染单条文本: 整串占位符保留变量原始类型, 拼接场景以str替换。"""
        if "${" not in content:
            return content
        whole_match = PLACEHOLDER_PATTERN.fullmatch(content.strip())
        if whole_match:
            name = whole_match.group(1)
            if name in lookup:
                return lookup[name]
            hit, result = _eval_builtin(name)
            if hit:
                return result
            missing.append(name)
            return content

        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in lookup:
                return str(lookup[name])
            hit, result = _eval_builtin(name)
            if hit:
                return str(result)
            missing.append(name)
            return match.group(0)

        return PLACEHOLDER_PATTERN.sub(substitute, content)

    if isinstance(value, str):
        return render_text(value), missing
    if isinstance(value, dict):
        rendered: Dict[str, Any] = {}
        for key, item in value.items():
            rendered[str(key)], inner_missing = render_placeholders(item, lookup)
            missing.extend(inner_missing)
        return rendered, missing
    if isinstance(value, list):
        items: List[Any] = []
        for item in value:
            rendered_item, inner_missing = render_placeholders(item, lookup)
            items.append(rendered_item)
            missing.extend(inner_missing)
        return items, missing
    return value, missing


# ============================ 来源提取 ============================

def parse_cookie_header(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """
    从请求头 Cookie 字段解析 name->value 字典(键名大小写不敏感匹配)。

    语义对齐 autotest_runtime/util_kv.parse_cookie_header: 值为dict时逐项转str,
    为文本时按分号分割解析; 无Cookie或非法输入返回空字典。

    :param headers: 请求头映射
    :return: Cookie名到值的字典
    """
    if not headers or not isinstance(headers, dict):
        return {}
    cookie_raw: Any = None
    for key, value in headers.items():
        if str(key).lower() == "cookie":
            cookie_raw = value
            break
    if cookie_raw is None:
        return {}
    if isinstance(cookie_raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in cookie_raw.items()}
    cookie_text = str(cookie_raw).strip()
    if not cookie_text:
        return {}
    parsed: Dict[str, str] = {}
    for part in cookie_text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        if name:
            parsed[name] = value.strip()
    return parsed


def resolve_json_path(data: Any, expr: Optional[str]) -> Any:
    """
    使用 JSONPath 从 data 取值(必须$开头; 单匹配返回值, 多匹配返回列表)。

    语义对齐 extractors._resolve_json_path。

    :param data: 待取值对象(dict/list或嵌套结构)
    :param expr: JSONPath表达式(如 $.data[0].id)
    :return: 提取到的值
    :raises ValueError: 表达式为空/非$开头/数据源为空/解析失败/未匹配
    """
    expr = str(expr).strip() if expr else ""
    if not expr:
        raise ValueError("【JSONPath表达式】必须是非空字符串")
    if not expr.startswith("$"):
        raise ValueError("【JSONPath表达式】必须以$.字符开头")
    if data is None:
        raise ValueError("【JSONPath表达式】数据源不允许为空")
    try:
        json_path_expr = jsonpath_parse(expr)
    except Exception as e:
        raise ValueError(f"【JSONPath表达式】执行失败, {e}") from e
    matches = json_path_expr.find(data)
    if not matches:
        raise ValueError("【JSONPath表达式】匹配失败, 请检查数据源是否包含表达式")
    values = [match.value for match in matches]
    return values[0] if len(values) == 1 else values


def extract_text_by_regex(text: Optional[str], expr: Optional[str]) -> str:
    """
    从纯文本按正则提取整个匹配串(group 0), 语义对齐 extractors._extract_text_payload
    的断言调用路径(断言定义无index字段, 固定取整个匹配)。

    :param text: 响应或请求正文
    :param expr: 正则表达式
    :return: 匹配到的字符串
    :raises ValueError: 正文为空/表达式为空/正则非法/未匹配
    """
    if not text:
        raise ValueError("【断言提取】内容为空")
    if not expr:
        raise ValueError("【断言提取】参数[expr]是必须的, 并且需要有效的正则表达式")
    try:
        match = re.search(expr, text, re.S)
    except re.error as e:
        raise ValueError(f"【断言提取】正则表达式执行失败, 错误描述: {e}") from e
    if not match:
        raise ValueError(f"【断言提取】正则表达式[{expr}]未匹配到内容")
    return match.group(0)


def extract_by_source(source: str, expr: Optional[str], response_context: Dict[str, Any]) -> Any:
    """
    从 source 指定来源提取断言取值(固定SOME模式, 与断言元素五字段结构一致)。

    键名与 extractors 注册表一致; XML两类来源不在 PERF_ASSERT_SOURCES 校验范围,
    引擎同样不支持, 未命中注册表时直接拒绝(无 autotest 的DB/Redis回退分支——
    压测为纯HTTP单请求语义)。

    :param source: 来源键(如 response json)
    :param expr: 提取表达式(JSONPath或正则)
    :param response_context: 断言上下文(response_text/response_json/response_headers/
        response_cookies/request_text/request_json/request_headers/request_form_data/session_variables)
    :return: 提取到的值
    :raises ValueError: 来源不支持或提取失败
    """
    source_key = (source or "").strip().lower()
    mapping_sources: Dict[str, str] = {
        "response headers": "response_headers",
        "request headers": "request_headers",
        "response cookie": "response_cookies",
        "request cookie": "request_cookies",
        "request form-data": "request_form_data",
    }
    if source_key in ("response json", "request json"):
        label = "响应" if source_key.startswith("response") else "请求"
        data = response_context.get("response_json" if source_key.startswith("response") else "request_json")
        if data is None:
            raise ValueError(f"【断言提取】{label}内容不是有效的JSON数据")
        return resolve_json_path(data=data, expr=expr)
    if source_key in ("response text", "request text"):
        label = "响应" if source_key.startswith("response") else "请求"
        text = response_context.get("response_text" if source_key.startswith("response") else "request_text")
        if not text:
            raise ValueError(f"【断言提取】{label}内容不是有效的Text数据")
        return extract_text_by_regex(text=text, expr=expr)
    if source_key in mapping_sources:
        data = response_context.get(mapping_sources[source_key])
        if not data:
            raise ValueError(f"【断言提取】数据源[{source}]为空")
        try:
            return resolve_json_path(data=data, expr=expr)
        except Exception as e:
            raise ValueError(str(e) or f"【断言提取】JSONPath匹配失败: {expr}") from e
    if source_key in ("session_variables", "变量池"):
        lookup = response_context.get("session_variables")
        if not isinstance(lookup, dict):
            raise ValueError("【断言提取】变量池未提供或类型不合法")
        return resolve_json_path(data=lookup, expr=expr)
    raise ValueError(f"【断言提取】数据源源类型 {source} 不被允许")


# ============================ 断言比较 ============================

class PerfAssertionComparator:
    """
    对实际值与期望值根据断言操作符执行比较。

    全部辅助方法与操作符行为从 autotest assert_compare.py 语义复刻,
    由对齐测试锁定(引擎子进程不可 import backend)。
    """

    @classmethod
    def _is_leading_zero_digit_string(cls, value: str) -> bool:
        """判断是否为带前导零的整数字符串(如响应码000000), 此类值保留字符串形态参与比较。"""
        if not value:
            return False
        if value.startswith("-") and len(value) > 1:
            body = value[1:]
            return body.isdigit() and len(body) > 1 and body.startswith("0")
        return value.isdigit() and len(value) > 1 and value.startswith("0")

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """
        标准化比较类型: 数字字符串转int/float, true/false/null文本转bool/None, 前导零串保留原串。

        null文本归一用于数据集字符串化存储后的兼容: 期望值"null"与响应null字段可判定相等。
        """
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if cls._is_leading_zero_digit_string(value):
                return value
            if value.isdigit() or (value.startswith("-") and len(value) > 1 and value[1:].isdigit()):
                return int(value)
            try:
                if "." in value:
                    return float(value)
            except ValueError:
                pass
            lowered = value.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            if lowered == "null":
                return None
        return value

    @classmethod
    def _coerce_number_for_ordering(cls, value: Any) -> Any:
        """大小比较专用数值化: 允许带前导零的数字串按数值参与比较; 无法转换返回原值。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return value
            if text.isdigit() or (text.startswith("-") and len(text) > 1 and text[1:].isdigit()):
                return int(text)
            try:
                if "." in text:
                    return float(text)
            except ValueError:
                pass
        return value

    @classmethod
    def _is_bool_vs_number(cls, left: Any, right: Any) -> bool:
        """判断是否一侧bool另一侧非bool数值(Python中True==1为真, 断言禁止此类宽松相等)。"""
        left_is_bool = isinstance(left, bool)
        right_is_bool = isinstance(right, bool)
        left_is_number = isinstance(left, (int, float)) and not left_is_bool
        right_is_number = isinstance(right, (int, float)) and not right_is_bool
        return (left_is_bool and right_is_number) or (right_is_bool and left_is_number)

    @classmethod
    def _type_aware_equals(cls, actual: Any, expected: Any) -> bool:
        """类型感知相等: 先直接比较, 不等则标准化后再比较, bool与数值一律不等。"""
        if cls._is_bool_vs_number(actual, expected):
            return False
        if actual == expected:
            return True
        norm_actual = cls._normalize_value(actual)
        norm_expected = cls._normalize_value(expected)
        if cls._is_bool_vs_number(norm_actual, norm_expected):
            return False
        return norm_actual == norm_expected

    @classmethod
    def _type_aware_compare(
            cls,
            actual: Any,
            expected: Any,
            comparator: Callable[[Any, Any], bool],
    ) -> bool:
        """类型感知大小比较: 优先按数值比较(含前导零数字串), 否则回落字符串比较。"""
        num_actual = cls._coerce_number_for_ordering(actual)
        num_expected = cls._coerce_number_for_ordering(expected)
        if (
                isinstance(num_actual, (int, float))
                and not isinstance(num_actual, bool)
                and isinstance(num_expected, (int, float))
                and not isinstance(num_expected, bool)
        ):
            return comparator(num_actual, num_expected)
        return comparator(str(actual), str(expected))

    @classmethod
    def _assertion_length_equal(cls, actual: Any, expected: Any) -> bool:
        """比较实际值长度是否等于期望长度, 无__len__的类型取str长度。"""
        normalized = cls._normalize_value(expected)
        if normalized is None or actual is None:
            return False
        try:
            actual_len = len(actual)
        except TypeError:
            actual_len = len(str(actual))
        return actual_len == int(normalized)

    @classmethod
    def _assertion_array_length_equal(cls, actual: Any, expected: Any) -> bool:
        """比较数组长度是否等于期望值; 仅list/tuple视为数组, 字符串与字典返回False。"""
        if not isinstance(actual, (list, tuple)):
            return False
        normalized = cls._normalize_value(expected)
        if normalized is None:
            return False
        try:
            return len(actual) == int(normalized)
        except (TypeError, ValueError):
            return False

    @classmethod
    def _assertion_is_empty(cls, actual: Any, expected: Any) -> bool:
        """判断实际值是否为空: None、空串、空容器均为空; expected忽略。"""
        del expected
        if actual is None:
            return True
        if isinstance(actual, str):
            return actual == ""
        if isinstance(actual, (list, dict, set, tuple)):
            return len(actual) == 0
        return False

    @classmethod
    def _assertion_not_empty(cls, actual: Any, expected: Any) -> bool:
        """判断实际值是否非空; expected忽略。"""
        del expected
        return not cls._assertion_is_empty(actual, None)

    @classmethod
    def _parse_set_literal(cls, text: str) -> List[Any]:
        """解析集合字面量内部文本: 统一逗号分割, 去可选引号, 再经标准化转类型。"""
        elements: List[Any] = []
        for part in text.replace("，", ",").split(","):
            token = part.strip()
            if not token:
                continue
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
                token = token[1:-1]
            elements.append(cls._normalize_value(token))
        return elements

    @classmethod
    def _coerce_to_collection(cls, expected: Any) -> List[Any]:
        """将期望值规范为成员判断用的列表, 支持原生容器及[]、{}、()包裹的字面量。"""
        if expected is None:
            raise ValueError("集合期望值不允许为[None | Null]")
        if isinstance(expected, (list, tuple, set, frozenset)):
            return list(expected)
        if isinstance(expected, dict):
            raise ValueError("集合期望值不支持Dict，请使用List/Set或[]、{}、()字面量")
        if not isinstance(expected, str):
            raise ValueError(
                "集合期望值必须使用[]、{}或()包裹，例如[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)"
            )
        text = expected.strip()
        if not text:
            raise ValueError("集合期望值不允许为空字符串")
        pairs = {"[": "]", "{": "}", "(": ")"}
        opener = text[0]
        closer = pairs.get(opener)
        if closer is None or len(text) < 2 or not text.endswith(closer):
            raise ValueError("集合期望值必须使用[]、{}或()包裹，例如[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)")
        inner = text[1:-1]
        if opener == "[":
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
            return cls._parse_set_literal(inner)
        if opener == "{":
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                raise ValueError("集合期望值不支持JSON对象，请使用[元素1, 元素2]、{元素1, 元素2}或(元素1, 元素2)写法")
            return cls._parse_set_literal(inner)
        return cls._parse_set_literal(inner)

    @classmethod
    def _assertion_in_set(cls, actual: Any, expected: Any) -> bool:
        """判断实际值是否属于期望集合(类型感知相等)。"""
        return any(cls._type_aware_equals(actual, item) for item in cls._coerce_to_collection(expected))

    @classmethod
    def compare_assertion(cls, actual: Any, operation: str, expected: Any) -> bool:
        """
        根据操作符对实际值与期望值做断言比较; operation 取值与 AutoTestAssertionOperation 一致。

        :param actual: 实际值
        :param operation: 操作符中文文案(如 "等于")
        :param expected: 期望值(部分操作符忽略)
        :return: 断言是否通过
        :raises ValueError: 操作符非法或比较过程异常
        """
        comparator = _ASSERTION_HANDLERS.get(operation)
        if comparator is None:
            raise ValueError(f"操作符[{operation!r}]不被允许")
        try:
            return comparator(actual, expected)
        except Exception as e:
            raise ValueError(f"比较失败: 实际值[{actual}] 操作符[{operation}] 预期值[{expected}] {e}") from e


# 操作符 -> 比较器映射(键与 AutoTestAssertionOperation 枚举值一致); 模块级构建一次, 避免热路径重建
_ASSERTION_HANDLERS: Dict[str, Callable[[Any, Any], bool]] = {
    "等于": PerfAssertionComparator._type_aware_equals,
    "不等于": lambda a, e: not PerfAssertionComparator._type_aware_equals(a, e),
    "大于": lambda a, e: PerfAssertionComparator._type_aware_compare(a, e, operator.gt),
    "大于等于": lambda a, e: PerfAssertionComparator._type_aware_compare(a, e, operator.ge),
    "小于": lambda a, e: PerfAssertionComparator._type_aware_compare(a, e, operator.lt),
    "小于等于": lambda a, e: PerfAssertionComparator._type_aware_compare(a, e, operator.le),
    "长度等于": PerfAssertionComparator._assertion_length_equal,
    "数组长度等于": PerfAssertionComparator._assertion_array_length_equal,
    "包含": lambda a, e: str(e) in str(a),
    "不包含": lambda a, e: str(e) not in str(a),
    "属于集合": PerfAssertionComparator._assertion_in_set,
    "不属于集合": lambda a, e: not PerfAssertionComparator._assertion_in_set(a, e),
    "以...开始": lambda a, e: str(a).startswith(str(e)),
    "以...结束": lambda a, e: str(a).endswith(str(e)),
    "不为空": PerfAssertionComparator._assertion_not_empty,
    "为空": PerfAssertionComparator._assertion_is_empty,
}


# ============================ 断言执行 ============================

def execute_assertions(
        assert_validators: Optional[List[Dict[str, Any]]],
        response_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    执行业务断言列表, 返回逐项快照(快照字段与 autotest details 断言追加字段对齐)。

    单项提取或比较异常不中断整体执行: 异常写入error且success为False,
    避免单条配置错误导致整轮压测断言静默丢失。

    :param assert_validators: 断言定义列表(name/expr/source/operation/except_value)
    :param response_context: 断言提取上下文(见 extract_by_source)
    :return: 快照列表, 元素结构:
        {"name": "状态码断言", "expr": "$.code", "source": "response json",
         "operation": "等于", "except_value": 0, "actual_value": 0,
         "success": True, "error": None}
    """
    snapshots: List[Dict[str, Any]] = []
    for validator in assert_validators or []:
        snapshot: Dict[str, Any] = {
            "name": (validator or {}).get("name"),
            "expr": (validator or {}).get("expr"),
            "source": (validator or {}).get("source"),
            "operation": (validator or {}).get("operation"),
            "except_value": (validator or {}).get("except_value"),
            "actual_value": None,
            "success": False,
            "error": None,
        }
        try:
            actual_value = extract_by_source(
                source=validator.get("source") or "",
                expr=validator.get("expr"),
                response_context=response_context,
            )
            snapshot["actual_value"] = actual_value
            snapshot["success"] = PerfAssertionComparator.compare_assertion(
                actual=actual_value,
                operation=validator.get("operation") or "",
                expected=validator.get("except_value"),
            )
        except Exception as e:
            snapshot["error"] = str(e)
        snapshots.append(snapshot)
    return snapshots


# ============================ 变量提取 ============================

# 来源键 → 响应上下文字段名(与 autotest EXTRACTORS 注册表键保持一致)
SOURCE_CONTEXT_KEYS: Dict[str, str] = {
    "response json": "response_json",
    "request json": "request_json",
    "response text": "response_text",
    "request text": "request_text",
    "response headers": "response_headers",
    "request headers": "request_headers",
    "response cookie": "response_cookies",
    "request cookie": "request_cookies",
    "request form-data": "request_form_data",
    "session_variables": "session_variables",
    "变量池": "session_variables",
}


def extract_value_by_source(
        source: str,
        expr: Optional[str],
        response_context: Dict[str, Any],
        range_type: Optional[str] = "SOME",
        index: Optional[Any] = None,
) -> Any:
    """
    变量提取口径的取值入口: ALL 返回整段数据源, SOME 按表达式取值并按 index 取多匹配项。

    语义对齐 autotest Extractors._extract_json_payload 的三字段组合(scope/index/expr):
    ALL 不参与表达式解析; SOME 复用 extract_by_source; index 仅在结果为列表时生效
    (与 autotest 一致, 单匹配结果不按下标取位)。

    :param source: 来源键(如 response json)
    :param expr: 提取表达式(JSONPath或正则); ALL 模式可空
    :param response_context: 提取上下文(见 build_response_context)
    :param range_type: ALL 或 SOME(缺省 SOME)
    :param index: 多匹配结果下标(越界抛 ValueError)
    :return: 提取到的值
    :raises ValueError: 来源不支持、提取失败或索引越界
    """
    source_key = (source or "").strip().lower()
    if (range_type or "SOME").strip().lower() == "all":
        context_key = SOURCE_CONTEXT_KEYS.get(source_key)
        if context_key is None:
            raise ValueError(f"【变量提取】数据源[{source}]不被允许")
        data = response_context.get(context_key)
        if not data:
            raise ValueError(f"【变量提取】数据源[{source}]为空")
        return data
    value = extract_by_source(source=source, expr=expr, response_context=response_context)
    if isinstance(value, list) and index is not None:
        try:
            index_int = int(index)
        except (ValueError, TypeError) as e:
            raise ValueError(f"【变量提取】参数[index]必须是整数类型, 错误描述: {e}") from e
        if index_int >= len(value):
            raise ValueError(f"【变量提取】数组越界, 索引[{index_int}]不可大于数组长度[{len(value)}]")
        return value[index_int]
    return value


def apply_extract_variables(
        extract_variables: Optional[List[Dict[str, Any]]],
        response_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    执行变量提取列表, 返回逐项快照(字段与 autotest details 提取追加字段对齐)。

    单项提取失败不中断整体: 失败项写入error且extract_value为None(不入变量池),
    避免一处配置错误把后续步骤的变量全部拖没。

    :param extract_variables: 提取定义列表(name/expr/source/scope/index)
    :param response_context: 提取上下文(见 build_response_context)
    :return: 快照列表, 元素结构:
        {"name": "token", "expr": "$.data.token", "source": "response json",
         "extract_value": "xxx", "success": True, "error": None}
    """
    snapshots: List[Dict[str, Any]] = []
    for item in extract_variables or []:
        definition = item or {}
        snapshot: Dict[str, Any] = {
            "name": definition.get("name"),
            "expr": definition.get("expr"),
            "source": definition.get("source"),
            "extract_value": None,
            "success": False,
            "error": None,
        }
        try:
            snapshot["extract_value"] = extract_value_by_source(
                source=definition.get("source") or "",
                expr=definition.get("expr"),
                response_context=response_context,
                range_type=definition.get("scope"),
                index=definition.get("index"),
            )
            snapshot["success"] = bool(snapshot["name"])
            if not snapshot["success"]:
                snapshot["error"] = "【变量提取】参数[name]不允许为空"
        except Exception as e:
            snapshot["error"] = str(e)
        snapshots.append(snapshot)
    return snapshots


# ============================ 请求构造 ============================

def build_request_url(request_url: str, request_port: Optional[str]) -> str:
    """
    组装压测请求URL, 拼接语义对齐 protocol_http.build_absolute_http_url:
    无协议时补http://; request_port有值且host段未含端口时追加端口;
    已是绝对地址时端口由URL自身表达, 不重复拼接。

    :param request_url: 请求地址(含host与路径)
    :param request_port: 请求端口(可空)
    :return: 绝对请求URL
    :example:
        >>> build_request_url("127.0.0.1/api/users", "8000")
        'http://127.0.0.1:8000/api/users'
    """
    url = (request_url or "").strip()
    if not url:
        return url
    if url.lower().startswith(("http://", "https://")):
        return url
    slash_index = url.find("/")
    if slash_index >= 0:
        host, path = url[:slash_index], url[slash_index:]
    else:
        host, path = url, ""
    port = str(request_port).strip() if request_port else ""
    if port and ":" not in host:
        host = f"{host}:{port}"
    return f"http://{host}{path}"


def _ensure_mapping(body: Any) -> Any:
    """请求体兼容dict与JSON字符串两种形态(JSONTextField读出可能为str)。"""
    if isinstance(body, str):
        try:
            return orjson.loads(body)
        except orjson.JSONDecodeError:
            return body
    return body


class RequestBuilder:
    """
    压测请求构造器: 管理数据集场景轮询、路径替换预渲染与变量池渲染。

    数据集场景即虚拟用户取数单元(round_robin循环/random随机; unique独占场景由
    施压入口分配场景下标后经 fixed_scene_index 注入)。场景的 head/body 路径映射
    在构造期一次性应用到请求模板, 与 autotest「先数据驱动替换、再占位符替换」
    顺序一致; 运行期仅做 ${} 占位符渲染, 施压热路径零 JSONPath 开销。
    """

    def __init__(
            self,
            request_definition: Dict[str, Any],
            dataset_scenes: Optional[List[Dict[str, Any]]] = None,
            variable_pool: Optional[Dict[str, Any]] = None,
            scene_strategy: str = DATASET_ROUND_ROBIN,
            fixed_scene_index: Optional[int] = None,
    ) -> None:
        """
        初始化请求构造器并预渲染各场景请求模板。

        :param request_definition: 请求定义(request_method/request_url/request_port/
            request_header/request_params/request_form_data/request_form_file/
            request_form_urlencoded/request_args_type/request_text/request_body)
        :param dataset_scenes: 数据集场景列表, 元素结构
            {"name": 场景名, "head": {报文路径: 值}, "body": {报文路径: 值}}
        :param variable_pool: 变量池字典(引用传递, 其他请求写回的变量下一圈即可见)
        :param scene_strategy: 场景取数策略(round_robin/random)
        :param fixed_scene_index: 固定场景下标(unique策略由施压入口分配后注入, 优先于场景策略)
        """
        self.request_definition = request_definition
        self.dataset_scenes: List[Dict[str, Any]] = [
            scene for scene in (dataset_scenes or []) if isinstance(scene, dict)
        ]
        self.scene_strategy = scene_strategy
        self.fixed_scene_index = fixed_scene_index
        self.scene_cycle = (
            cycle(range(len(self.dataset_scenes)))
            if self.dataset_scenes and scene_strategy == DATASET_ROUND_ROBIN
            else None
        )
        self.base_lookup = variable_pool
        # 装载期模板: 无数据集仅基础模板, 有数据集逐场景应用路径映射(每场景一份独立模板)
        self._base_template: Dict[str, Any] = self._build_template(scene=None)
        self._scene_templates: List[Dict[str, Any]] = [
            self._build_template(scene=scene) for scene in self.dataset_scenes
        ]

    def _next_scene_index(self) -> Optional[int]:
        """返回下一场景下标; 未配置数据集且无固定场景时返回None。"""
        if self.fixed_scene_index is not None:
            return self.fixed_scene_index
        if not self.dataset_scenes:
            return None
        if self.scene_strategy == DATASET_RANDOM:
            return random.randrange(len(self.dataset_scenes))
        return next(self.scene_cycle)

    def _active_template(self) -> Dict[str, Any]:
        """按场景策略取用模板: 无数据集走基础模板; 非法下标兜底回基础模板。"""
        index = self._next_scene_index()
        if index is None or index >= len(self._scene_templates):
            return self._base_template
        return self._scene_templates[index]

    @staticmethod
    def _render_kv_list(
            items: Optional[List[Dict[str, Any]]],
            lookup: Dict[str, Any],
    ) -> Dict[str, str]:
        """渲染键值对列表为{key: value}映射; value为None时置空串(请求头序列化语义)。"""
        rendered: Dict[str, str] = {}
        for item in items or []:
            key = (item or {}).get("key")
            if not key:
                continue
            value, _ = render_placeholders(item.get("value"), lookup)
            rendered[str(key)] = "" if value is None else str(value)
        return rendered

    def _build_template(self, scene: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构造请求模板: 渲染定义级键值容器后应用场景路径映射(scene为None即基础模板)。

        装配与路径替换语义对齐 autotest HTTP步骤执行链(先按参数类型组装报文容器,
        再数据驱动替换: XML走XPath、其余走JSONPath), 占位符留给运行期渲染;
        路径未命中由 datagram_replace 记日志跳过, 不影响模板可用性。

        :param scene: 数据集场景字典(None表示不应用路径映射)
        :return: 模板字典(headers/params/form_data/form_files/urlencoded/
            args_type/body_kwargs/xml_default_headers)
        """
        definition = self.request_definition
        template: Dict[str, Any] = {
            "headers": self._render_kv_list(definition.get("request_header"), {}),
            "params": self._render_kv_list(definition.get("request_params"), {}),
            "form_data": self._render_kv_list(definition.get("request_form_data"), {}),
            "form_files": self._render_kv_list(definition.get("request_form_file"), {}),
            "urlencoded": self._render_kv_list(definition.get("request_form_urlencoded"), {}),
            "args_type": "",
            "body_kwargs": {},
            "xml_default_headers": None,
        }
        args_type = str(definition.get("request_args_type") or "").strip().lower()
        if not args_type:
            # 未指定类型按 raw -> form-data -> urlencoded -> json 推断(与运行期口径一致)
            if definition.get("request_text"):
                args_type = ARGS_TYPE_RAW
            elif template["form_data"] or template["form_files"]:
                args_type = ARGS_TYPE_FORM_DATA
            elif template["urlencoded"]:
                args_type = ARGS_TYPE_X_WWW_FORM_URLENCODED
            elif definition.get("request_body"):
                args_type = ARGS_TYPE_JSON
            else:
                return template
        template["args_type"] = args_type
        head_map = (scene or {}).get("head") or {}
        body_map = (scene or {}).get("body") or {}
        if args_type == ARGS_TYPE_XML:
            # XML: head_map走请求头通道、body_map走XPath替换报文文本(对齐autotest HTTP XML分支)
            text = str(definition.get("request_text") or "")
            if scene:
                out = PerfJsonDatagram.replace_json_datagram(
                    head_map=head_map, body_map={}, request_headers=template["headers"],
                )
                template["headers"] = out["headers"] or {}
                text = PerfXmlDatagram.replace_xml_datagram(body_map=body_map, request_text=text) or ""
            if text:
                template["body_kwargs"] = {"data": text}
                if not any(
                        str((item or {}).get("key") or "").lower() == "content-type"
                        for item in definition.get("request_header") or []
                ):
                    template["xml_default_headers"] = {"Content-Type": XML_DEFAULT_CONTENT_TYPE}
            return template
        # 非XML: head/body统一走JSONPath替换(head可写请求头, body可写body/form/urlencoded通道;
        # raw纯文本报文容器为None, 其body_map未命中由替换器记日志跳过)
        body: Any = _ensure_mapping(definition.get("request_body")) if args_type == ARGS_TYPE_JSON else None
        if isinstance(body, (dict, list)):
            # 各模板的报文容器必须隔离: 场景替换是原地写值, 共享定义级dict会造成模板间互相污染
            body = copy.deepcopy(body)
        if scene:
            out = PerfJsonDatagram.replace_json_datagram(
                head_map=head_map, body_map=body_map,
                request_headers=template["headers"], request_body=body,
                form_data=template["form_data"] or None,
                urlencoded=template["urlencoded"] or None,
            )
            template["headers"] = out["headers"] or {}
            body = out["request_body"]
            template["form_data"] = out["form_data"] or {}
            template["urlencoded"] = out["urlencoded"] or {}
        if args_type == ARGS_TYPE_JSON:
            template["body_kwargs"] = {"json": body} if body is not None else {}
        elif args_type == ARGS_TYPE_RAW:
            text = str(definition.get("request_text") or "")
            template["body_kwargs"] = {"data": text} if text else {}
        return template

    def build_request(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        组装下一次请求参数(模板已含场景路径替换结果, 运行期仅渲染占位符)与变量池。

        :return: (请求kwargs字典, 本次请求的变量池lookup)
            请求kwargs可直接透传 locust client.request, 结构:
            {"method": "POST", "url": "http://host:8000/api/users",
             "headers": {"Content-Type": "application/json"}, "params": {"page": "1"},
             "cookies": {"token": "abc"}, "json": {"uid": 1001}}
        """
        template = self._active_template()
        lookup = self.base_lookup
        definition = self.request_definition
        headers, _ = render_placeholders(template["headers"], lookup)
        params, _ = render_placeholders(template["params"], lookup)
        rendered_url, _ = render_placeholders(definition.get("request_url") or "", lookup)
        body_kwargs = self._render_body_kwargs(template=template, lookup=lookup)
        # XML等场景缺省Content-Type由body_kwargs带出, 用户显式请求头优先覆盖
        default_headers: Dict[str, Any] = body_kwargs.pop("headers", None)
        merged_headers: Dict[str, Any] = {**(default_headers or {}), **headers}
        # Cookie从请求头拆出为独立cookies参数, 避免requests内部与显式cookies合并冲突
        cookies = parse_cookie_header(headers)
        request_kwargs: Dict[str, Any] = {
            "method": str(definition.get("request_method") or "GET").upper(),
            "url": build_request_url(str(rendered_url), definition.get("request_port")),
            "headers": merged_headers or None,
            "params": params or None,
            "cookies": cookies or None,
            **body_kwargs,
        }
        return request_kwargs, lookup

    def _render_body_kwargs(self, *, template: Dict[str, Any], lookup: Dict[str, Any]) -> Dict[str, Any]:
        """
        渲染模板报文段为 locust client kwargs(json/data/files), 装配语义对齐
        autotest protocol_http.assemble_http_body_payloads: 表单承载独立容器
        (文件项以内容直传, 不读施压机本地磁盘); 模板段已在装载期完成数据驱动
        替换, 此处仅渲染占位符并按参数类型打包。
        """
        args_type = template["args_type"]
        if not args_type:
            return {}
        if args_type == ARGS_TYPE_JSON:
            body, _ = render_placeholders(template["body_kwargs"].get("json"), lookup)
            return {"json": body} if body is not None else {}
        if args_type in (ARGS_TYPE_RAW, ARGS_TYPE_XML):
            text, _ = render_placeholders(template["body_kwargs"].get("data") or "", lookup)
            if not text:
                return {}
            body_kwargs: Dict[str, Any] = {"data": str(text)}
            if template["xml_default_headers"]:
                body_kwargs["headers"] = dict(template["xml_default_headers"])
            return body_kwargs
        if args_type == ARGS_TYPE_FORM_DATA:
            form_data, _ = render_placeholders(template["form_data"], lookup)
            form_files, _ = render_placeholders(template["form_files"], lookup)
            merged_form = {**form_data, **form_files}
            if not merged_form:
                return {}
            # 键值表单走files强制multipart编码(纯文本字段以None文件名提交)
            return {"files": {str(key): (None, "" if value is None else value) for key, value in merged_form.items()}}
        if args_type == ARGS_TYPE_X_WWW_FORM_URLENCODED:
            urlencoded, _ = render_placeholders(template["urlencoded"], lookup)
            return {"data": urlencoded} if urlencoded else {}
        return {}


def build_response_context(
        response: Any,
        request_kwargs: Dict[str, Any],
        session_lookup: Dict[str, Any],
) -> Dict[str, Any]:
    """
    从 requests 响应与请求参数构造断言提取上下文。

    响应JSON解析失败时response_json置None(来源为response json的断言将得到明确错误);
    request_cookies从请求头解析(与 extractors.extract_from_source 的解析时机一致);
    form_data由data字典与files键值合并(mapping类来源统一按JSONPath提取)。

    :param response: requests响应对象(locust catch_response上下文中的response)
    :param request_kwargs: 本次请求参数(RequestBuilder.build_request产物)
    :param session_lookup: 本次请求合并后的变量池
    :return: 断言提取上下文字典(见 extract_by_source)
    """
    try:
        response_json = orjson.loads(response.content or b"") if response.content else None
    except orjson.JSONDecodeError:
        response_json = None
    form_data: Optional[Dict[str, Any]] = None
    if isinstance(request_kwargs.get("data"), dict):
        form_data = dict(request_kwargs["data"])
    if isinstance(request_kwargs.get("files"), dict):
        file_items = {
            key: value[1] if isinstance(value, tuple) else value
            for key, value in request_kwargs["files"].items()
        }
        form_data = {**(form_data or {}), **file_items}
    return {
        "response_text": response.text,
        "response_json": response_json,
        "response_headers": dict(response.headers),
        "response_cookies": dict(response.cookies),
        "request_text": request_kwargs.get("data") if isinstance(request_kwargs.get("data"), str) else None,
        "request_json": request_kwargs.get("json"),
        "request_headers": request_kwargs.get("headers"),
        "request_cookies": parse_cookie_header(request_kwargs.get("headers")),
        "request_form_data": form_data,
        "session_variables": session_lookup,
    }
