# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : resource_policy.py
@DateTime: 2026/10/28
"""
from typing import Dict, Tuple

from backend.enums import DataScopeEnum

# 资源族标签前缀：路由以「一级目录:二级模块」注册，作为数据权限的资源锚点
RESOURCE_TAG_PREFIXES: Tuple[str, ...] = (
    "系统管理:",
    "应用管理:",
    "自动化测试:",
    "任务管理:",
    "便捷工具:",
    "性能测试:",
)

# 无法识别资源族的路由归入 legacy，回落角色全局范围
LEGACY_TAG: str = "legacy"

# 范围宽窄排序：用于多角色合并取最宽
SCOPE_RANK: Dict[DataScopeEnum, int] = {
    DataScopeEnum.ALL: 4,
    DataScopeEnum.DEPT_AND_CHILD: 3,
    DataScopeEnum.DEPT: 2,
    DataScopeEnum.SELF: 1,
}


def widest_scope(scopes) -> DataScopeEnum:
    """
    多角色范围合并取最宽；全部为空时回落仅本人。

    :param scopes: 范围枚举可迭代对象
    :return: 最宽范围
    """
    valid = [DataScopeEnum(scope) for scope in scopes if scope is not None]
    return max(valid, key=SCOPE_RANK.__getitem__) if valid else DataScopeEnum.SELF


def scope_covers(outer: DataScopeEnum, inner: DataScopeEnum) -> bool:
    """
    判断 outer 范围是否覆盖 inner 范围。

    :param outer: 外层范围(如可见范围)
    :param inner: 内层范围(如可写/可删范围)
    :return: 覆盖返回True
    """
    return SCOPE_RANK[DataScopeEnum(outer)] >= SCOPE_RANK[DataScopeEnum(inner)]