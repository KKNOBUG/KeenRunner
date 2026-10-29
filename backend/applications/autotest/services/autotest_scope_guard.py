# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_scope_guard.py
@DateTime: 2026/10/28
"""
from typing import Any, Iterable, Optional

from backend.applications.autotest.models.autotest_case_model import AutoTestCaseModel
from backend.applications.autotest.models.autotest_project_model import AutoTestProjectModel
from backend.configure import LOGGER
from backend.core.exceptions import NoPermissionException, NotFoundException
from backend.enums import PUBLIC_CASE_TYPES
from backend.services.data_scope import DataScope

# 父资源所属资源族标签：与路由注册标签一致，父/子资源的范围才可独立配置
PROJECT_TAG = "应用管理:项目"
ENV_TAG = "应用管理:环境"
CASE_TAG = "自动化测试:用例"


async def load_readable_project(scope: Optional[DataScope], project_id: int) -> AutoTestProjectModel:
    """
    加载启用态应用并校验可读，供子资源挂载前校验父资源。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param project_id: 应用ID
    :return: 应用实例
    """
    project = await AutoTestProjectModel.filter(id=int(project_id), state__not=1).first()
    if not project:
        error_message: str = f"查询应用信息失败, 记录[id={project_id}]不存在"
        LOGGER.error(error_message)
        raise NotFoundException(message=error_message)
    await assert_parent_readable(scope, PROJECT_TAG, project, "应用")
    return project


async def assert_parent_readable(scope: Optional[DataScope], tag: str, parent: Any, label: str) -> None:
    """
    校验父资源对当前用户可见（B级防护：父资源可读才允许挂载子资源）。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param tag: 父资源所属资源族标签
    :param parent: 父资源实例
    :param label: 父资源中文名，用于错误提示
    :return: None
    """
    if scope is None:
        return
    # 公共脚本/公共接口对所有用户可见，不随数据范围收窄
    if getattr(parent, "case_type", None) in PUBLIC_CASE_TYPES:
        return
    parent_scope = await scope.for_tag(tag)
    # 有归属人字段的父资源（用例）以归属人为准，转让后创建人不再代表数据归属
    owner = getattr(parent, "owner_user", None) or getattr(parent, "created_user", None)
    if not parent_scope.can_read(owner):
        error_message: str = f"数据权限校验失败, 无权使用{label}[id={getattr(parent, 'id', '')}]所属数据"
        LOGGER.error(error_message)
        raise NoPermissionException(message=error_message)


async def assert_cases_readable(scope: Optional[DataScope], case_ids: Iterable[Optional[int]]) -> None:
    """
    批量校验用例对当前用户可见，供任务挂载/执行等多用例入口统一做父资源校验。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param case_ids: 待校验的用例ID集合
    :return: None
    """
    ids: set[int] = {int(case_id) for case_id in case_ids or [] if case_id}
    if scope is None or not ids:
        return
    case_scope = await scope.for_tag(CASE_TAG)
    if case_scope.read_owners is None:
        return
    rows = await AutoTestCaseModel.filter(id__in=ids, state__not=1).values_list(
        "id", "case_name", "case_type", "owner_user"
    )
    for case_id, case_name, case_type, owner_user in rows:
        if case_type in PUBLIC_CASE_TYPES:
            continue
        if not case_scope.can_read(owner_user):
            error_message: str = f"数据权限校验失败, 用例[{case_name}](id={case_id})所属人[{owner_user}]不在当前用户可见范围"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
