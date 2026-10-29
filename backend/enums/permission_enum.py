# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : permission_enum.py
@DateTime: 2026/10/27
"""
from backend.enums.base_enum_cls import StringEnum


class DataScopeEnum(StringEnum):
    """
    角色数据权限范围。

    - select_scope 控制可查询范围
    - update_scope 控制可修改范围
    - delete_scope 控制可删除范围

    角色可按资源标签逐项覆盖，可写/可删范围不得超过可见范围，多角色按最宽范围合并，超级管理员不受限制。
    """

    ALL = ("ALL", "全部数据")
    DEPT_AND_CHILD = ("DEPT_AND_CHILD", "本部门及下级部门")
    DEPT = ("DEPT", "本部门")
    SELF = ("SELF", "仅本人")
