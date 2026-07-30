# -*- coding: utf-8 -*-
"""
条件分支多分支(branch_items)功能测试
运行: PYTHONPATH=. backend/.venv/bin/python backend/tests/test_condition_branch.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.applications.aotutest.schemas.autotest_step_schema import BranchItem, ConditionsBase


passed = 0
failed = 0


def assert_ok(desc, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS: {desc}")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {desc} -> {e}")


def assert_raises(desc, fn, expected_msg=None):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  FAIL: {desc} -> expected exception but none raised")
    except Exception as e:
        if expected_msg and expected_msg not in str(e):
            failed += 1
            print(f"  FAIL: {desc} -> wrong error: {e}")
        else:
            passed += 1
            print(f"  PASS: {desc}")


print("=" * 60)
print("1. BranchItem 基础校验")
print("=" * 60)

assert_ok("if 分支 + branch_conditions 合法", lambda: BranchItem(
    branch_type="if",
    branch_conditions=ConditionsBase(condition_expr="${code}", condition_compare="等于", condition_value="200"),
    branch_desc="成功",
))

assert_ok("elif 分支 + branch_conditions 合法", lambda: BranchItem(
    branch_type="elif",
    branch_conditions=ConditionsBase(condition_expr="${code}", condition_compare="等于", condition_value="401"),
))

assert_ok("else 分支 + branch_conditions=None 合法", lambda: BranchItem(
    branch_type="else",
    branch_conditions=None,
    branch_desc="兜底",
))

assert_raises("if 分支缺少 branch_conditions", lambda: BranchItem(branch_type="if", branch_conditions=None), "必须配置 branch_conditions")

assert_raises("elif 分支缺少 branch_conditions", lambda: BranchItem(branch_type="elif"), "必须配置 branch_conditions")

assert_raises("else 分支不允许有 branch_conditions", lambda: BranchItem(
    branch_type="else",
    branch_conditions=ConditionsBase(condition_expr="x", condition_compare="非空"),
), "不允许配置 branch_conditions")

assert_raises("非法 branch_type", lambda: BranchItem(branch_type="switch"), "必须为 if/elif/else")

print()
print("=" * 60)
print("2. ConditionsBase 比较符校验")
print("=" * 60)

assert_ok("合法比较符: 等于", lambda: ConditionsBase(condition_expr="a", condition_compare="等于"))
assert_ok("合法比较符: 非空", lambda: ConditionsBase(condition_expr="a", condition_compare="非空"))
assert_ok("合法比较符: 包含", lambda: ConditionsBase(condition_expr="a", condition_compare="包含", condition_value="x"))
assert_raises("非法比较符", lambda: ConditionsBase(condition_expr="a", condition_compare="约等于"), "")

print()
print("=" * 60)
print("3. 完整分支列表组合")
print("=" * 60)

assert_ok("单 if", lambda: [
    BranchItem(branch_type="if", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="非空")),
])

assert_ok("if + else", lambda: [
    BranchItem(branch_type="if", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="等于", condition_value="1")),
    BranchItem(branch_type="else", branch_conditions=None),
])

assert_ok("if + elif + else", lambda: [
    BranchItem(branch_type="if", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="等于", condition_value="1")),
    BranchItem(branch_type="elif", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="等于", condition_value="2")),
    BranchItem(branch_type="else", branch_conditions=None),
])

assert_ok("if + 15个elif (上限)", lambda: [
    BranchItem(branch_type="if", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="非空")),
] + [
    BranchItem(branch_type="elif", branch_conditions=ConditionsBase(condition_expr="${x}", condition_compare="等于", condition_value=str(i)))
    for i in range(15)
])

print()
print("=" * 60)
print("4. 序列化/反序列化（对齐 CRUD 落库格式: exclude branch_children）")
print("=" * 60)


def test_serialization():
    branch_items = [
        BranchItem(branch_type="if", branch_conditions=ConditionsBase(condition_expr="${code}", condition_compare="等于", condition_value="200"), branch_desc="成功"),
        BranchItem(branch_type="elif", branch_conditions=ConditionsBase(condition_expr="${code}", condition_compare="等于", condition_value="401"), branch_desc="过期"),
        BranchItem(branch_type="else", branch_conditions=None, branch_desc="兜底"),
    ]
    data = [b.model_dump(exclude={"branch_children"}) for b in branch_items]
    assert len(data) == 3
    assert data[0]["branch_type"] == "if"
    assert data[0]["branch_conditions"]["condition_expr"] == "${code}"
    assert data[1]["branch_type"] == "elif"
    assert data[2]["branch_type"] == "else"
    assert data[2]["branch_conditions"] is None
    restored = [BranchItem.model_validate(d) for d in data]
    assert restored[0].branch_conditions.condition_compare == "等于"
    assert restored[2].branch_conditions is None


assert_ok("branch_items 序列化/反序列化往返", test_serialization)

print()
print("=" * 60)
print(f"结果: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
