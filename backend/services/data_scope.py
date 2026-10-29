# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : data_scope.py
@DateTime: 2026/10/27
"""
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, Request
from tortoise.expressions import Q

from backend.applications.base.models.role_tag_model import RoleTag
from backend.applications.department.models.dept_model import DeptStruct
from backend.applications.user.models.user_model import User
from backend.enums import BuiltinRoleCode, DataScopeEnum
from backend.services.dependency import AuthControl
from backend.services.resource_policy import LEGACY_TAG, RESOURCE_TAG_PREFIXES, widest_scope


@dataclass(frozen=True)
class DataScope:
    """
    请求级数据权限上下文。

    解析顺序为「角色标签覆盖 > 角色默认范围」，多角色对同一标签取最宽；
    超管与管理员角色固定全部数据，不受角色字段与标签覆盖影响。
    read/write/delete_owners 为 None 表示不限范围，否则为归属账号（大写16位截断）集合。
    可写范围与可删范围会被可见范围收敛，杜绝"能修改却看不见"的孤儿数据。
    部门范围按归属人当前部门动态解析，不落业务表快照。
    """

    username: str
    read_owners: Optional[frozenset[str]]
    write_owners: Optional[frozenset[str]]
    delete_owners: Optional[frozenset[str]]
    is_system: bool = False
    tag: str = LEGACY_TAG

    _user: Optional[User] = field(default=None, repr=False, compare=False)
    # 同一请求内按父资源族重解析的缓存：批量入口(如用例拼接树)逐条校验父资源时避免重复查库
    _tag_cache: dict[str, "DataScope"] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    async def from_user(
            cls,
            user: User,
            tag: str = LEGACY_TAG,
            _tag_cache: Optional[dict[str, "DataScope"]] = None,
    ) -> "DataScope":
        """
        根据已认证用户与请求所属资源族构造数据权限上下文。

        :param user: 当前登录用户
        :param tag: 请求路由的资源族标签
        :param _tag_cache: 父上下文共享的标签解析缓存，供 for_tag 复用
        :return: 数据权限上下文
        """
        username = cls._normalize(user.username)
        if user.is_superuser:
            return cls(
                username=username,
                read_owners=None,
                write_owners=None,
                delete_owners=None,
                is_system=True,
                tag=tag,
                _user=user,
                _tag_cache={} if _tag_cache is None else _tag_cache,
            )

        scopes = await cls.effective_scopes(user, tag)
        # 读/写/删常配置成同一范围(如均为本部门)，按枚举去重只解析一次部门成员
        owners: dict[DataScopeEnum, Optional[frozenset[str]]] = {}
        for scope in scopes:
            if scope not in owners:
                owners[scope] = await cls._resolve_owners(user, scope, username)
        read_owners, write_owners, delete_owners = (owners[scope] for scope in scopes)
        write_owners, delete_owners = cls._clamp_to_read(read_owners, write_owners, delete_owners)
        return cls(
            username=username,
            read_owners=read_owners,
            write_owners=write_owners,
            delete_owners=delete_owners,
            tag=tag,
            _user=user,
            _tag_cache={} if _tag_cache is None else _tag_cache,
        )

    async def for_tag(self, tag: str) -> "DataScope":
        """
        按指定资源族重新解析上下文，用于父资源归属校验。

        :param tag: 父资源所属资源族标签
        :return: 父资源族的上下文；系统上下文、同一标签或无法还原用户时返回自身，同标签重复解析复用缓存
        """
        if self.is_system or self._user is None or tag == self.tag:
            return self
        cached = self._tag_cache.get(tag)
        if cached is None:
            cached = await DataScope.from_user(self._user, tag=tag, _tag_cache=self._tag_cache)
            self._tag_cache[tag] = cached
        return cached

    @classmethod
    async def effective_scopes(cls, user: User, tag: str = LEGACY_TAG) -> tuple[DataScopeEnum, DataScopeEnum, DataScopeEnum]:
        """
        计算用户在指定资源族上的(可见, 写入, 删除)范围。

        :param user: 当前登录用户
        :param tag: 资源族标签
        :return: (select_scope, update_scope, delete_scope)
        """
        if user.is_superuser:
            return DataScopeEnum.ALL, DataScopeEnum.ALL, DataScopeEnum.ALL

        roles = await user.roles
        if not roles:
            return DataScopeEnum.SELF, DataScopeEnum.SELF, DataScopeEnum.SELF

        # 管理员角色与超管同权：固定全部数据，无视角色三字段与标签覆盖
        if BuiltinRoleCode.includes_admin(role.code for role in roles):
            return DataScopeEnum.ALL, DataScopeEnum.ALL, DataScopeEnum.ALL

        overrides = {}
        if tag and tag != LEGACY_TAG:
            overrides = {
                row.role_id: row
                for row in await RoleTag.filter(role_id__in=[role.id for role in roles], tag=tag)
            }

        read_scopes, write_scopes, delete_scopes = [], [], []
        for role in roles:
            override = overrides.get(role.id)
            # 标签覆盖允许逐字段继承：显式值为空时回落到角色默认范围
            read_scopes.append((override.select_scope if override else None) or role.select_scope)
            write_scopes.append((override.update_scope if override else None) or role.update_scope)
            delete_scopes.append((override.delete_scope if override else None) or role.delete_scope)
        return widest_scope(read_scopes), widest_scope(write_scopes), widest_scope(delete_scopes)

    def read_q(self, owner_field: str) -> Optional[Q]:
        """
        构造列表查询的归属过滤条件。

        :param owner_field: 归属字段名(用例为 owner_user，其余为 created_user)
        :return: Q条件；None表示不限范围
        """
        if self.read_owners is None:
            return None
        # 空集合用空串占位：归属账号非空，等价于恒不命中，且规避 MySQL 对 IN () 的语法限制
        return Q(**{f"{owner_field}__in": sorted(self.read_owners) or [""]})

    def can_read(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户查看。

        :param owner: 数据归属账号(owner_user或created_user)
        :return: 允许返回True
        """
        return self.read_owners is None or self._normalize(owner) in self.read_owners

    def can_write(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户修改。

        :param owner: 数据归属账号(owner_user或created_user)
        :return: 允许返回True
        """
        return self.write_owners is None or self._normalize(owner) in self.write_owners

    def can_delete(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户删除。

        可删范围独立于可写范围：可编辑他人数据不代表可删除他人数据。

        :param owner: 数据归属账号(owner_user或created_user)
        :return: 允许返回True
        """
        if self.is_system:
            return True
        return self.delete_owners is None or self._normalize(owner) in self.delete_owners

    @classmethod
    def system(cls) -> "DataScope":
        """
        系统内部流程(任务执行、引擎回写)的数据权限上下文，不受归属限制。

        :return: 读写删均不限范围的上下文
        """
        return cls(
            username="",
            read_owners=None,
            write_owners=None,
            delete_owners=None,
            is_system=True,
        )

    @staticmethod
    def _clamp_to_read(
            read_owners: Optional[frozenset[str]],
            write_owners: Optional[frozenset[str]],
            delete_owners: Optional[frozenset[str]],
    ) -> tuple[Optional[frozenset[str]], Optional[frozenset[str]]]:
        """写/删范围收敛到可见范围内，避免出现不可见的可写数据。"""
        if read_owners is None:
            return write_owners, delete_owners
        clamped_write = read_owners if write_owners is None else frozenset(write_owners & read_owners)
        clamped_delete = read_owners if delete_owners is None else frozenset(delete_owners & read_owners)
        return clamped_write, clamped_delete

    @staticmethod
    def _normalize(owner: Optional[str]) -> str:
        return str(owner or "").strip().upper()[:16]

    @classmethod
    async def _resolve_owners(
            cls,
            user: User,
            scope: DataScopeEnum,
            username: str,
    ) -> Optional[frozenset[str]]:
        """把范围枚举解析为归属人集合；ALL 返回 None 表示不限。"""
        if scope == DataScopeEnum.ALL:
            return None

        # 本人始终可写自己的数据，避免用户不在所属部门时被误拦截
        owners: set[str] = {username}
        if scope in (DataScopeEnum.DEPT, DataScopeEnum.DEPT_AND_CHILD):
            dept_ids = await cls._dept_ids(user.dept_id, scope)
            if dept_ids:
                names = await User.filter(dept_id__in=dept_ids, state__not=1).values_list("username", flat=True)
                owners.update(cls._normalize(name) for name in names if name)
        return frozenset(owners)

    @classmethod
    async def _dept_ids(cls, dept_id: Optional[int], scope: DataScopeEnum) -> list[int]:
        """解析部门范围：DEPT 取本部门，DEPT_AND_CHILD 借闭包表展开下级。"""
        if not dept_id:
            return []
        if scope == DataScopeEnum.DEPT:
            return [dept_id]
        descendants = await DeptStruct.filter(ancestor=dept_id).values_list("descendant", flat=True)
        return list(descendants) or [dept_id]


def resolve_request_tag(request: Request) -> str:
    """
    读取当前路由声明的资源族标签；未声明时归入 legacy。

    标签来自路由注册时的显式声明，不做 URL 前缀推断。

    :param request: 当前请求
    :return: 资源族标签或 legacy
    """
    route = request.scope.get("route")
    for tag in getattr(route, "tags", None) or []:
        text: str = str(tag or "").strip()
        if text.startswith(RESOURCE_TAG_PREFIXES):
            return text
    return LEGACY_TAG


async def get_data_scope(current_user: User = Depends(AuthControl.is_authed)) -> DataScope:
    """FastAPI依赖：按用户全局范围构造数据权限上下文。"""
    return await DataScope.from_user(current_user)


async def get_tag_scope(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
) -> DataScope:
    """FastAPI依赖：按请求路由的资源族标签解析数据权限上下文。"""
    return await DataScope.from_user(current_user, tag=resolve_request_tag(request))


DependDataScope = Depends(get_data_scope)
DependTagScope = Depends(get_tag_scope)