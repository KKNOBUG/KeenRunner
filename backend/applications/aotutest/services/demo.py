# -*- coding: utf-8 -*-
"""
占位符解析示例：直接运行本文件，在 main 里看各场景输出。

用法：在项目根目录执行（已自动把项目根加入 sys.path）::

  python backend/applications/aotutest/tests/test_resolve_placeholders.py

需已安装 requirements.txt（import backend 会加载日志等依赖）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

# 保证能 import backend（项目根目录 = backend 的父目录）
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from backend.applications.aotutest.services.autotest_tool_service3 import AutoTestToolService
except ImportError as e:
    print("导入失败（需先安装项目依赖，例如: pip install -r requirements.txt）")
    print(e)
    sys.exit(1)


def _log(msg: str) -> None:
    print(f"  [log] {msg}")


def main() -> None:
    # 非核心引擎：变量来自 key/value 列表
    var_list: List[Dict[str, Any]] = [
        {"key": "a", "value": 1},
        {"key": "b", "value": 2},
        {"key": "c", "value": 3},
        {"key": "d", "value": 4},
        {"key": "e", "value": 5},
        {"key": "f", "value": 6},
        {"key": "g", "value": 7},
        {"key": "h", "value": 8},
        {"key": "i", "value": 9},
        {"key": "s", "value": "hello world"},
    ]

    def run_case(title: str, template: str) -> None:
        print(f"\n--- {title} ---")
        print(f"  模板: {template!r}")
        out = AutoTestToolService.resolve_placeholders(
            template,
            logger_object=_log,
            is_core_engine=False,
            finished_variables=var_list,
        )
        print(f"  结果: {out!r}")

    print("=== resolve_placeholders 场景演示（变量: a=2, b=3, c=5, s='hello'）===")

    # print("=== 基础运算 ===")
    run_case("单变量1", "${a }")
    run_case("单变量2", "${b} ")
    run_case("单变量3", " ${c} ")
    run_case("变量运算1", "${a}+${b}")
    run_case("变量运算2", "${b} - ${c}")
    run_case("变量运算3", "${c} * ${d} ")
    run_case("变量运算4", " ${d} / ${e} ")
    run_case("变量运算5", " ${d} + ${e} ")

    print("=== 复合运算 ===")
    run_case("复合运算1", "(${a} + 10) * ${b} / (${c} - 1)")
    run_case("复合运算2", "(${a} + ${b} + ${c}) * ${d} / (${e} - 1)")
    run_case("复合运算3", "(${a} + ${b} + ${c}) * ((${d} * ${e} * 3) / ${f}) / (${g} - ${e})")

    print("=== 字面运算 ===")
    run_case("与字面量", "${a} + 10")
    run_case("非数字拼接（不做整式求值）", "${s}-${b}")
    run_case("未定义变量（部分保留）", "ok=${a}, bad=${not_exist}")
    run_case("未定义变量（部分保留）", "${a} + ${not_exist}")

    # 无变量：纯 GenerateUtils 函数（generate_random_number(7,7) 恒为 7）
    print("\n--- 纯函数占位符（不依赖变量表）---")
    t = "${generate_random_number(min=7,max=7)}+${generate_random_number(min=3,max=3)}"
    print(f"  模板: {t!r}")
    out2 = AutoTestToolService.resolve_placeholders(
        t, logger_object=_log, is_core_engine=False, finished_variables=[]
    )
    print(f"  结果: {out2!r}")


if __name__ == "__main__":
    # main()
    # str1 = 12
    # print(f"[{str1!r}]")
    print(getattr(AutoTestToolService, None)(**{}))
