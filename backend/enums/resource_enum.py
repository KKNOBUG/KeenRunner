# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : resource_enum.py
@DateTime: 2026/10/30
"""
from typing import Optional, Sequence

from base_enum_cls import StringEnum


class ResourceDomain(StringEnum):
    """
    资源域：权限体系的一级分类。

    系统域仅放行查询给内置业务角色，其余域按业务域全开。
    """

    SYSTEM = ("system", "系统管理")
    APPLICATION = ("application", "应用管理")
    AUTOTEST = ("autotest", "自动化测试")
    TASK = ("task", "任务管理")
    TOOLBOX = ("toolbox", "便捷工具")
    PERFORMANCE = ("perf", "性能测试")

    @property
    def is_business(self) -> bool:
        """性能测试等非系统域按业务域处理，内置用户/宾客角色拥有完整权限。"""
        return self is not ResourceDomain.SYSTEM


class ResourceTag(StringEnum):
    """
    资源族：路由标签与数据权限的唯一事实源。

    code 用于逻辑判定与持久化，desc(中文 label) 仅用于展示与路由 tags。
    scope_aware 标记该资源族是否接入行级数据权限（DataScope + 归属字段过滤）：
    只有接入的资源族才出现在「标签范围」配置中，杜绝配置了却不生效的空项。
    新增资源族只需在此登记一次，路由注册、权限判定、审计展示、前端全量生效。
    """

    # ==================== 系统管理 ====================
    USER = ("system.user", "系统管理:用户", ResourceDomain.SYSTEM)
    ROUTER = ("system.router", "系统管理:路由", ResourceDomain.SYSTEM)
    MENU = ("system.menu", "系统管理:菜单", ResourceDomain.SYSTEM)
    ROLE = ("system.role", "系统管理:角色", ResourceDomain.SYSTEM)
    AUDIT = ("system.audit", "系统管理:审计", ResourceDomain.SYSTEM)
    FILE = ("system.file", "系统管理:文件", ResourceDomain.SYSTEM)
    DEPT = ("system.dept", "系统管理:部门", ResourceDomain.SYSTEM)

    # ==================== 应用管理 ====================
    PROJECT = ("application.project", "应用管理:项目", ResourceDomain.APPLICATION, True)
    ENV = ("application.env", "应用管理:环境", ResourceDomain.APPLICATION, True)
    ENV_CONFIG = ("application.env_config", "应用管理:环境配置", ResourceDomain.APPLICATION, True)
    TAG = ("application.tag", "应用管理:标签", ResourceDomain.APPLICATION, True)

    # ==================== 自动化测试 ====================
    CASE = ("autotest.case", "自动化测试:用例", ResourceDomain.AUTOTEST, True)
    # 步骤无独立归属，范围跟随所属用例（视图统一 for_tag(autotest.case)），不单独配置
    STEP = ("autotest.step", "自动化测试:步骤", ResourceDomain.AUTOTEST)
    REPORT = ("autotest.report", "自动化测试:报告", ResourceDomain.AUTOTEST, True)
    DETAIL = ("autotest.detail", "自动化测试:明细", ResourceDomain.AUTOTEST, True)
    TOOL = ("autotest.tool", "自动化测试:工具", ResourceDomain.AUTOTEST)
    # 数据源无独立归属，范围跟随所属用例，不单独配置
    DATASET = ("autotest.dataset", "自动化测试:数据源", ResourceDomain.AUTOTEST)
    DEBUG = ("autotest.debug", "自动化测试:调试", ResourceDomain.AUTOTEST)

    # ==================== 任务管理 ====================
    TASK = ("task.task", "任务管理:任务", ResourceDomain.TASK, True)

    # ==================== 便捷工具 ====================
    TOOLBOX = ("toolbox.toolbox", "便捷工具:工具箱", ResourceDomain.TOOLBOX)
    HTTP_COMPARE = ("toolbox.http_compare", "便捷工具:报文比对", ResourceDomain.TOOLBOX)

    # ==================== 性能测试 ====================
    PERF_API = ("perf.api", "性能测试:接口", ResourceDomain.PERFORMANCE)
    PERF_DATASET = ("perf.dataset", "性能测试:数据集", ResourceDomain.PERFORMANCE)
    PERF_SCENE = ("perf.scene", "性能测试:场景", ResourceDomain.PERFORMANCE)
    PERF_PRESET = ("perf.preset", "性能测试:负载预设", ResourceDomain.PERFORMANCE)
    PERF_JOB = ("perf.job", "性能测试:作业", ResourceDomain.PERFORMANCE)
    PERF_REPORT = ("perf.report", "性能测试:报告", ResourceDomain.PERFORMANCE)
    PERF_COMPARE = ("perf.compare", "性能测试:对比", ResourceDomain.PERFORMANCE)
    PERF_DIAGNOSIS = ("perf.diagnosis", "性能测试:诊断", ResourceDomain.PERFORMANCE)

    def __new__(cls, code: str, label: str, domain: ResourceDomain, scope_aware: bool = False):
        obj = str.__new__(cls, code)
        obj._value_ = code
        obj.desc = label
        obj.domain = domain
        obj.scope_aware = scope_aware
        return obj

    @classmethod
    def from_code(cls, code: Optional[str]) -> Optional["ResourceTag"]:
        """按 code 查资源族，未知 code 返回 None。"""
        try:
            return cls(str(code or ""))
        except ValueError:
            return None

    @classmethod
    def of_tags(cls, tags: Sequence[str]) -> Optional["ResourceTag"]:
        """按路由 tags 精确匹配资源族，无法匹配返回 None（调用方负责记录告警）。"""
        by_label = {member.desc: member for member in cls}
        for raw in tags or ():
            label = str(raw or "").strip()
            if label in by_label:
                return by_label[label]
        return None

    @classmethod
    def label_of(cls, code: Optional[str]) -> str:
        """code 转展示 label；未知 code 原样返回，避免历史数据丢失可读性。"""
        member = cls.from_code(code)
        return member.desc if member else str(code or "")


if __name__ == '__main__':
    print(ResourceTag.USER)
    print(ResourceTag.USER.value)
    print(ResourceTag.from_code("system.user"))
    print(ResourceTag.of_tags(["系统管理:用户"]))
    print(ResourceTag.label_of("system.user"))
