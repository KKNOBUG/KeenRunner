# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : runnn
@DateTime: 2025/11/12 14:42
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到 Python 路径
# test_step_execution.py 位于: backend/applications/autotest/services/
# 需要添加 backend 目录到路径
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent.parent.parent  # 从 services -> autotest -> applications -> backend
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 尝试导入，如果失败则使用相对导入
try:
    from backend.applications.aotutest.services.autotest_step_engine import (
        AutoTestStepExecutionEngine,
        StepExecutionResult, AutoTestStepExecution
)
except ImportError:
    # 如果绝对导入失败，尝试相对导入
    from autotest_step_engine import (
        AutoTestStepExecutionEngine,
        StepExecutionResult
    )

# 用户提供的测试数据
TEST_DATA = {
    "code": "000000",
    "status": "success",
    "message": "获取步骤树成功",
    "data": [
        {
            "conditions": None,
            "created_user": None,
            "created_time": "2025-11-12 09:28:20",
            "case_id": 1,
            "request_form_file": None,
            "step_type": "循环结构",
            "request_params": None,
            "max_cycles": 3,
            "code": None,
            "request_text": None,
            "ext_variables": None,
            "step_no": 1,
            "step_desc": None,
            "pre_code": None,
            "wait": None,
            "step_name": "循环逻辑",
            "request_method": None,
            "request_header": None,
            "post_code": None,
            "updated_user": None,
            "request_port": None,
            "quote_case_id": None,
            "request_body": None,
            "updated_time": "2025-11-12 09:33:01",
            "pre_wait": None,
            "request_form_urlencoded": None,
            "validators": None,
            "request_url": None,
            "id": 1,
            "post_wait": None,
            "step_code": "2025111000000-1001",
            "state": -1,
            "parent_step_id": None,
            "request_form_data": None,
            "use_variables": None,
            "case": {
                "updated_time": "2025-11-10 15:52:15",
                "id": 1,
                "created_user": None,
                "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                "case_tags": "冒烟测试",
                "created_time": "2025-11-10 15:20:45",
                "case_version": 1,
                "updated_user": None,
                "state": -1,
                "case_project": 1,
                "case_code": "320200-567985AD756349EDA110E13F000005D3",
                "case_name": "企业网银-认证中心-用户登录-1001"
            },
            "children": [
                {
                    "conditions": None,
                    "created_user": None,
                    "created_time": "2025-11-12 09:32:45",
                    "case_id": 1,
                    "request_form_file": None,
                    "step_type": "执行代码(Python)",
                    "request_params": None,
                    "max_cycles": None,
                    "code": "def generate_var():import random return {f\"key{random.randint(1, 99)}\": f\"{random.randint(1, 99)}\"}",
                    "request_text": None,
                    "ext_variables": None,
                    "step_no": 2,
                    "step_desc": None,
                    "pre_code": None,
                    "wait": None,
                    "step_name": "执行代码-创建随机变量",
                    "request_method": None,
                    "request_header": None,
                    "post_code": None,
                    "updated_user": None,
                    "request_port": None,
                    "quote_case_id": None,
                    "request_body": None,
                    "updated_time": "2025-11-12 09:33:58",
                    "pre_wait": None,
                    "request_form_urlencoded": None,
                    "validators": None,
                    "request_url": None,
                    "id": 2,
                    "post_wait": None,
                    "step_code": "2025111000000-1002",
                    "state": -1,
                    "parent_step_id": 1,
                    "request_form_data": None,
                    "use_variables": None,
                    "case": {
                        "updated_time": "2025-11-10 15:52:15",
                        "id": 1,
                        "created_user": None,
                        "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                        "case_tags": "冒烟测试",
                        "created_time": "2025-11-10 15:20:45",
                        "case_version": 1,
                        "updated_user": None,
                        "state": -1,
                        "case_project": 1,
                        "case_code": "320200-567985AD756349EDA110E13F000005D3",
                        "case_name": "企业网银-认证中心-用户登录-1001"
                    },
                    "children": [],
                    "quote_steps": [],
                    "quote_case": None
                }
            ],
            "quote_steps": [],
            "quote_case": None
        },
        {
            "conditions": None,
            "created_user": None,
            "created_time": "2025-11-12 09:32:45",
            "case_id": 1,
            "request_form_file": None,
            "step_type": "HTTP/HTTPS协议网络请求",
            "request_params": None,
            "max_cycles": None,
            "code": None,
            "request_text": None,
            "ext_variables": {
                "expr": "$.data.token",
                "name": "token",
                "range": "SOME",
                "source": "Response Json"
            },
            "step_no": 3,
            "step_desc": None,
            "pre_code": None,
            "wait": None,
            "step_name": "登录ZERORUNNER系统",
            "request_method": "POST",
            "request_header": None,
            "post_code": None,
            "updated_user": None,
            "request_port": None,
            "quote_case_id": None,
            "request_body": {
                "password": "123456",
                "username": "${username}"
            },
            "updated_time": "2025-11-12 16:52:14",
            "pre_wait": None,
            "request_form_urlencoded": None,
            "validators": {
                "expr": "$.code",
                "name": "断言是否登录成功",
                "source": "Response Json",
                "operation": "等于",
                "except_value": 0
            },
            "request_url": "https://zerorunner.cn/api/user/login",
            "id": 3,
            "post_wait": None,
            "step_code": "2025111000000-1003",
            "state": -1,
            "parent_step_id": None,
            "request_form_data": None,
            "use_variables": {
                "username": "admin"
            },
            "case": {
                "updated_time": "2025-11-10 15:52:15",
                "id": 1,
                "created_user": None,
                "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                "case_tags": "冒烟测试",
                "created_time": "2025-11-10 15:20:45",
                "case_version": 1,
                "updated_user": None,
                "state": -1,
                "case_project": 1,
                "case_code": "320200-567985AD756349EDA110E13F000005D3",
                "case_name": "企业网银-认证中心-用户登录-1001"
            },
            "children": [],
            "quote_steps": [],
            "quote_case": None
        },
        {
            "conditions": "{\"value\": \"${token}\", \"operation\": \"非空\", \"except_value\": None, \"desc\": \"如果获取token成功\"}",
            "created_user": None,
            "created_time": "2025-11-12 10:12:08",
            "case_id": 1,
            "request_form_file": None,
            "step_type": "条件分支",
            "request_params": None,
            "max_cycles": None,
            "code": None,
            "request_text": None,
            "ext_variables": None,
            "step_no": 4,
            "step_desc": None,
            "pre_code": None,
            "wait": None,
            "step_name": "判断token是否获取成功",
            "request_method": None,
            "request_header": None,
            "post_code": None,
            "updated_user": None,
            "request_port": None,
            "quote_case_id": None,
            "request_body": None,
            "updated_time": "2025-11-12 16:52:11",
            "pre_wait": None,
            "request_form_urlencoded": None,
            "validators": None,
            "request_url": None,
            "id": 4,
            "post_wait": None,
            "step_code": "2025111000000-1004",
            "state": -1,
            "parent_step_id": None,
            "request_form_data": None,
            "use_variables": None,
            "case": {
                "updated_time": "2025-11-10 15:52:15",
                "id": 1,
                "created_user": None,
                "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                "case_tags": "冒烟测试",
                "created_time": "2025-11-10 15:20:45",
                "case_version": 1,
                "updated_user": None,
                "state": -1,
                "case_project": 1,
                "case_code": "320200-567985AD756349EDA110E13F000005D3",
                "case_name": "企业网银-认证中心-用户登录-1001"
            },
            "children": [
                {
                    "conditions": None,
                    "created_user": None,
                    "created_time": "2025-11-12 10:15:40",
                    "case_id": 1,
                    "request_form_file": None,
                    "step_type": "执行代码(Python)",
                    "request_params": None,
                    "max_cycles": None,
                    "code": "def generate_var():import random return {\"keykey\": f\"{random.randint(1, 99)}\"}",
                    "request_text": None,
                    "ext_variables": None,
                    "step_no": 5,
                    "step_desc": None,
                    "pre_code": None,
                    "wait": None,
                    "step_name": "执行代码-创建随机变量2",
                    "request_method": None,
                    "request_header": None,
                    "post_code": None,
                    "updated_user": None,
                    "request_port": None,
                    "quote_case_id": None,
                    "request_body": None,
                    "updated_time": "2025-11-12 10:15:40",
                    "pre_wait": None,
                    "request_form_urlencoded": None,
                    "validators": None,
                    "request_url": None,
                    "id": 5,
                    "post_wait": None,
                    "step_code": "2025111000000-1005",
                    "state": -1,
                    "parent_step_id": 4,
                    "request_form_data": None,
                    "use_variables": None,
                    "case": {
                        "updated_time": "2025-11-10 15:52:15",
                        "id": 1,
                        "created_user": None,
                        "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                        "case_tags": "冒烟测试",
                        "created_time": "2025-11-10 15:20:45",
                        "case_version": 1,
                        "updated_user": None,
                        "state": -1,
                        "case_project": 1,
                        "case_code": "320200-567985AD756349EDA110E13F000005D3",
                        "case_name": "企业网银-认证中心-用户登录-1001"
                    },
                    "children": [],
                    "quote_steps": [],
                    "quote_case": None
                },
                {
                    "conditions": None,
                    "created_user": None,
                    "created_time": "2025-11-12 10:16:51",
                    "case_id": 1,
                    "request_form_file": None,
                    "step_type": "等待控制",
                    "request_params": None,
                    "max_cycles": None,
                    "code": None,
                    "request_text": None,
                    "ext_variables": None,
                    "step_no": 6,
                    "step_desc": None,
                    "pre_code": None,
                    "wait": 2,
                    "step_name": "等待2秒",
                    "request_method": None,
                    "request_header": None,
                    "post_code": None,
                    "updated_user": None,
                    "request_port": None,
                    "quote_case_id": None,
                    "request_body": None,
                    "updated_time": "2025-11-12 10:16:51",
                    "pre_wait": None,
                    "request_form_urlencoded": None,
                    "validators": None,
                    "request_url": None,
                    "id": 6,
                    "post_wait": None,
                    "step_code": "2025111000000-1006",
                    "state": -1,
                    "parent_step_id": 4,
                    "request_form_data": None,
                    "use_variables": None,
                    "case": {
                        "updated_time": "2025-11-10 15:52:15",
                        "id": 1,
                        "created_user": None,
                        "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                        "case_tags": "冒烟测试",
                        "created_time": "2025-11-10 15:20:45",
                        "case_version": 1,
                        "updated_user": None,
                        "state": -1,
                        "case_project": 1,
                        "case_code": "320200-567985AD756349EDA110E13F000005D3",
                        "case_name": "企业网银-认证中心-用户登录-1001"
                    },
                    "children": [],
                    "quote_steps": [],
                    "quote_case": None
                },
                {
                    "conditions": None,
                    "created_user": None,
                    "created_time": "2025-11-12 10:20:58",
                    "case_id": 1,
                    "request_form_file": None,
                    "step_type": "HTTP/HTTPS协议网络请求",
                    "request_params": None,
                    "max_cycles": None,
                    "code": None,
                    "request_text": None,
                    "ext_variables": {
                        "expr": "$.data.rows",
                        "name": "rows",
                        "range": "SOME",
                        "source": "Response Json"
                    },
                    "step_no": 7,
                    "step_desc": None,
                    "pre_code": None,
                    "wait": None,
                    "step_name": "查询测试用例信息列表",
                    "request_method": "POST",
                    "request_header": {
                        "token": "${token}"
                    },
                    "post_code": None,
                    "updated_user": None,
                    "request_port": None,
                    "quote_case_id": None,
                    "request_body": {
                        "name": "",
                        "page": 1,
                        "pageSize": 50,
                        "created_by": None,
                        "created_by_name": ""
                    },
                    "updated_time": "2025-11-12 10:21:30",
                    "pre_wait": None,
                    "request_form_urlencoded": None,
                    "validators": {
                        "expr": "$.code",
                        "name": "断言请求成功",
                        "source": "Response Json",
                        "operation": "等于",
                        "except_value": 0
                    },
                    "request_url": "https://zerorunner.cn/api/testCase/list",
                    "id": 7,
                    "post_wait": None,
                    "step_code": "2025111000000-1007",
                    "state": -1,
                    "parent_step_id": 4,
                    "request_form_data": None,
                    "use_variables": None,
                    "case": {
                        "updated_time": "2025-11-10 15:52:15",
                        "id": 1,
                        "created_user": None,
                        "case_desc": "传递正确的用户名和密码测试登录接口，验证token有效性和用户信息是否正确",
                        "case_tags": "冒烟测试",
                        "created_time": "2025-11-10 15:20:45",
                        "case_version": 1,
                        "updated_user": None,
                        "state": -1,
                        "case_project": 1,
                        "case_code": "320200-567985AD756349EDA110E13F000005D3",
                        "case_name": "企业网银-认证中心-用户登录-1001"
                    },
                    "children": [],
                    "quote_steps": [],
                    "quote_case": None
                }
            ],
            "quote_steps": [],
            "quote_case": None
        }
    ],
    "total": None
}


def flatten_step_tree(steps: List[Dict[str, Any]], parent_id: int = None) -> List[Dict[str, Any]]:
    """
    将树形结构的步骤数据扁平化，同时保留children信息供执行器使用
    """
    result = []
    for step in steps:
        # 只处理根步骤（parent_step_id为None）
        if step.get("parent_step_id") == parent_id:
            step_copy = step.copy()
            # 保留children信息，执行器会使用
            result.append(step_copy)
    return result


def print_result(result: StepExecutionResult, indent: int = 0) -> None:
    """递归打印执行结果"""
    prefix = "  " * indent
    status = "✓" if result.success else "✗"
    print(f"{prefix}{status} [{result.step_no}] {result.step_name} ({result.step_type.value})")
    if result.message:
        print(f"{prefix}   消息: {result.message}")
    if result.error:
        print(f"{prefix}   错误: {result.error}")
    if result.elapsed:
        print(f"{prefix}   耗时: {result.elapsed:.3f}秒")
    if result.variables:
        print(f"{prefix}   变量: {json.dumps(result.variables, ensure_ascii=False, indent=2)}")
    if result.validators:
        print(f"{prefix}   断言: {json.dumps(result.validators, ensure_ascii=False, indent=2)}")
    if result.response:
        print(f"{prefix}   响应: {json.dumps(result.response, ensure_ascii=False, indent=2)[:200]}...")

    for child in result.children:
        print_result(child, indent + 1)


async def test_execution():
    """执行测试"""
    print("=" * 80)
    print("开始执行测试用例步骤")
    print("=" * 80)

    # 提取用例信息（从第一个步骤中获取）
    case_info = TEST_DATA["data"][0].get("case", {})
    case_info.pop("state")
    case_info.pop("case_desc")
    case_info.pop("created_time")
    case_info.pop("updated_time")
    case_info.pop("case_version")
    print(f"\n用例信息:", json.dumps(case_info, ensure_ascii=False, indent=2))
    case = {
        "id": case_info.get("id"),
        "case_code": case_info.get("case_code"),
        "case_name": case_info.get("case_name"),
    }

    # 提取根步骤（parent_step_id为None的步骤）
    root_steps = [step for step in TEST_DATA["data"] if step.get("parent_step_id") is None]

    print(f"\n用例信息:", case_info)
    print(f"  用例ID: {case['id']}")
    print(f"  用例代码: {case['case_code']}")
    print(f"  用例名称: {case['case_name']}")
    print(f"\n根步骤数量: {len(root_steps)}")

    # 创建执行引擎
    engine = AutoTestStepExecutionEngine()

    # 执行测试
    try:
        results, logs = await engine.execute_case(
            case=case,
            steps=root_steps,
            initial_variables={}  # 可以在这里设置初始变量
        )

        print("\n" + "=" * 80)
        print("执行结果")
        print("=" * 80)

        # 打印执行日志
        print("\n执行日志:")
        for log in logs:
            print(f"  {log}")

        # 打印执行结果
        print("\n步骤执行结果:")
        for result in results:
            print_result(result)

        # 统计信息
        total_steps = sum(1 for _ in _count_all_results(results))
        success_steps = sum(1 for r in _count_all_results(results) if r.success)
        failed_steps = total_steps - success_steps

        print("\n" + "=" * 80)
        print("执行统计")
        print("=" * 80)
        print(f"总步骤数: {total_steps}")
        print(f"成功步骤: {success_steps}")
        print(f"失败步骤: {failed_steps}")
        print(f"成功率: {success_steps / total_steps * 100:.2f}%" if total_steps > 0 else "N/A")

    except Exception as e:
        print(f"\n执行异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def _count_all_results(results: List[StepExecutionResult]) -> List[StepExecutionResult]:
    """递归收集所有结果"""
    all_results = []
    for result in results:
        all_results.append(result)
        all_results.extend(_count_all_results(result.children))
    return all_results


if __name__ == "__main__":
    # 运行测试
    # asyncio.run(test_execution())
    asyncio.run(AutoTestStepExecution(test_steps=TEST_DATA).execute())

