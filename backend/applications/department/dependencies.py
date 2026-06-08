# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : dependencies.py
@DateTime: 2026/6/8 09:47
"""
from backend.applications.department.services.department_crud import DepartmentCrud


async def get_dept_crud() -> DepartmentCrud:
    """获取部门 CRUD 服务实例"""
    return DepartmentCrud()
