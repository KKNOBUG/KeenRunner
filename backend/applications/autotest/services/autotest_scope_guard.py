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
from backend.enums import PUBLIC_CASE_TYPES, ResourceTag
from backend.services.data_scope import DataScope

# 父资源所属资源族：与路由注册标签同源，父/子资源的范围才可独立配置
PROJECT_TAG = ResourceTag.PROJECT.value
ENV_TAG = ResourceTag.ENV.value
CASE_TAG = ResourceTag.CASE.value


async def load_readable_project(scope: Optional[DataScope], project_id: int) -> AutoTestProjectModel:
    """
    加载启用态应用并校验可读，供子资源挂载前校验父资源。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param project_id: 应用ID
    :return: 应用实例
    :raises NotFoundException: 应用不存在或已软删
    :raises NoPermissionException: 应用归属不在当前用户可见范围
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

    公共脚本/公共接口（case_type在PUBLIC_CASE_TYPES中）直接放行；归属优先owner_user，
    回落created_user（兼容无归属人字段的应用/环境等父资源）。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param tag: 父资源所属资源族标签
    :param parent: 父资源实例
    :param label: 父资源中文名，用于错误提示
    :return: None
    :raises NoPermissionException: 父资源归属不在当前用户可见范围
    """
    if scope is None:
        return
    # 公共脚本/公共接口对所有用户可见，不随数据范围收窄
    if getattr(parent, "case_type", None) in PUBLIC_CASE_TYPES:
        return
    parent_scope = await scope.for_tag(tag)
    # 有归属人字段的父资源（用例）以归属人为准，转让后创建人不再代表数据归属
    owner = getattr(parent, "owner_user", None) or getattr(parent, "created_user", None)
    await parent_scope.load_owners([owner])
    if not parent_scope.can_read(owner):
        error_message: str = f"数据权限校验失败, 无权使用{label}[id={getattr(parent, 'id', '')}]所属数据"
        LOGGER.error(error_message)
        raise NoPermissionException(message=error_message)


async def assert_case_writable(scope: Optional[DataScope], case: AutoTestCaseModel, action: str) -> None:
    """
    校验用例既可读又可写。

    步骤、数据源等子资源没有独立归属，读写范围必须按父用例资源族解析；
    用子资源自身标签判定会让角色对autotest.case的覆盖配置对子资源失效。
    公共用例类型读取放行，但写入仍按归属人收敛。

    :param scope: 当前请求数据权限上下文；None表示调用方为内部可信路径
    :param case: 归属用例
    :param action: 操作名，用于错误提示
    :return: None
    :raises NoPermissionException: 用例归属不在当前用户可见或可写范围
    """
    if scope is None:
        return
    case_scope = await scope.for_tag(CASE_TAG)
    await case_scope.load_owners([case.owner_user])
    # 公共脚本/公共接口对所有用户可见，读取不随数据范围收窄，但写入仍按归属收敛
    if case.case_type not in PUBLIC_CASE_TYPES and not case_scope.can_read(case.owner_user):
        error_message: str = f"数据权限校验失败, {action}失败, 用例[{case.case_name}]所属人[{case.owner_user}]不在当前用户可见范围"
        LOGGER.error(error_message)
        raise NoPermissionException(message=error_message)
    if not case_scope.can_write(case.owner_user):
        error_message: str = f"数据权限校验失败, {action}失败, 用例[{case.case_name}]所属人[{case.owner_user}]不在当前用户可写范围"
        LOGGER.error(error_message)
        raise NoPermissionException(message=error_message)


async def assert_cases_readable(scope: Optional[DataScope], case_ids: Iterable[Optional[int]]) -> None:
    """
    批量校验用例对当前用户可见，供任务挂载/执行等多用例入口统一做父资源校验。

    只校验实际查到的用例；read_depts为None（不限部门范围）时直接放行，不查库；
    公共用例类型逐条跳过。

    :param scope: 当前请求数据权限上下文；None表示调用方未启用校验
    :param case_ids: 待校验的用例ID集合
    :return: None
    :raises NoPermissionException: 任一用例归属不在当前用户可见范围
    """
    ids: set[int] = {int(case_id) for case_id in case_ids or [] if case_id}
    if scope is None or not ids:
        return
    case_scope = await scope.for_tag(CASE_TAG)
    if case_scope.read_depts is None:
        return
    rows = await AutoTestCaseModel.filter(id__in=ids, state__not=1).values_list(
        "id", "case_name", "case_type", "owner_user"
    )
    await case_scope.load_owners([owner_user for _, _, _, owner_user in rows])
    for case_id, case_name, case_type, owner_user in rows:
        if case_type in PUBLIC_CASE_TYPES:
            continue
        if not case_scope.can_read(owner_user):
            error_message: str = f"数据权限校验失败, 用例[{case_name}](id={case_id})所属人[{owner_user}]不在当前用户可见范围"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)
