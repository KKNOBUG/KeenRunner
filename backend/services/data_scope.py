# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : data_scope.py
@DateTime: 2026/10/27
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from fastapi import Depends, Request
from tortoise.expressions import Q, RawSQL, Subquery

from backend.applications.base.models.role_model import Role
from backend.applications.base.models.role_tag_model import RoleTags
from backend.applications.department.models.dept_model import DeptStruct
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.enums import BuiltinRoleCode, DataScopeEnum, ResourceTag
from backend.services.ctx import normalize_username
from backend.services.dependency import AuthControl, load_request_roles
from backend.services.resource_policy import LEGACY_TAG, widest_scope


@dataclass(frozen=True)
class DataScope:
    """
    请求级数据权限上下文。

    解析顺序为「角色标签覆盖 > 角色默认范围」，多角色对同一标签取最宽；
    超管与管理员角色固定全部数据，不受角色字段与标签覆盖影响。
    read/write/delete_depts 为 None 表示不限范围，否则为可归属的部门ID集合（空集表示仅本人）。
    可写范围与可删范围会被可见范围收敛，杜绝"能修改却看不见"的孤儿数据。
    部门范围按归属人当前部门动态解析，不落业务表快照。
    列表读过滤下推为用户表子查询，写/删判定只反查涉及的归属人部门，
    不再把部门成员展开为内存集合并拼超大 IN，避免大部门下 SQL 膨胀与执行计划退化。
    同一请求内由 _ScopeResolver 共享角色、标签覆盖与部门集合，切换父资源族不重复查库。
    """

    username: str
    read_depts: Optional[frozenset[int]]
    write_depts: Optional[frozenset[int]]
    delete_depts: Optional[frozenset[int]]
    is_system: bool = False
    tag: str = LEGACY_TAG

    _resolver: Optional["_ScopeResolver"] = field(default=None, repr=False, compare=False)
    # 请求级归属人→部门缓存：写/删判定只反查涉及的归属人，不展开整个部门
    _owner_depts: Dict[str, Optional[int]] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    async def from_user(
            cls,
            user: User,
            tag: str,
            roles: Optional[List[Role]] = None,
    ) -> "DataScope":
        """
        根据已认证用户与请求所属资源族构造数据权限上下文。

        :param user: 当前登录用户
        :param tag: 请求路由的资源族标签
        :param roles: 已解析的角色列表；请求链路传入可复用接口鉴权的查询结果
        :return: 数据权限上下文
        """
        username: str = normalize_username(user.username)
        if user.is_superuser:
            return cls(
                username=username,
                read_depts=None,
                write_depts=None,
                delete_depts=None,
                is_system=True,
                tag=tag,
            )
        resolver = _ScopeResolver(
            user=user,
            username=username,
            roles=list(roles) if roles is not None else list(await user.roles),
        )
        return await resolver.resolve(tag)

    async def for_tag(self, tag: str) -> "DataScope":
        """
        按指定资源族重新解析上下文，用于父资源归属校验。

        :param tag: 目标资源族标签
        :return: 目标资源族的上下文；系统上下文、同一标签或无解析器时返回自身
        """
        if self.is_system or self._resolver is None or tag == self.tag:
            return self
        return await self._resolver.resolve(tag)

    @staticmethod
    def _dept_owner_subquery(dept_ids: frozenset[int]) -> Subquery:
        """部门成员归属键子查询：与 normalize_username 同源，把成员展开下推给数据库。"""
        queryset = User.filter(dept_id__in=sorted(dept_ids), state__not=1).annotate(
            owner_key=RawSQL("LEFT(UPPER(TRIM(`username`)),16)")
        ).values("owner_key")
        return Subquery(queryset)

    def read_q(self, owner_field: str) -> Optional[Q]:
        """
        构造列表查询的归属过滤条件。

        :param owner_field: 归属字段名(用例为 owner_user，其余为 created_user)
        :return: Q条件；None表示不限范围
        """
        if self.read_depts is None:
            return None
        # 本人始终可见；部门成员由子查询展开，SQL长度与部门人数无关
        owner_q = Q(**{owner_field: self.username})
        if not self.read_depts:
            return owner_q
        return owner_q | Q(**{f"{owner_field}__in": self._dept_owner_subquery(self.read_depts)})

    async def load_owners(self, owners: Iterable[Optional[str]]) -> None:
        """
        预取判定涉及的归属人部门；只反查这些归属人，避免为写/删判定展开整个部门成员。

        :param owners: 待判定记录的归属账号(owner_user或created_user)，批量场景一次传入全集
        :return: None；结果写入请求级缓存，供 can_read/can_write/can_delete 同步读取
        """
        if self.is_system:
            return
        keys = {normalize_username(owner) for owner in owners}
        keys.discard("")
        pending = sorted(key for key in keys if key not in self._owner_depts)
        if not pending:
            return
        rows = await User.filter(state__not=1).annotate(
            owner_key=RawSQL("LEFT(UPPER(TRIM(`username`)),16)")
        ).filter(owner_key__in=pending).values("owner_key", "dept_id")
        for row in rows:
            self._owner_depts[row["owner_key"]] = row["dept_id"]
        for key in pending:
            # 用户不存在或已软删：仅本人可访问，其余归属一律视为不在范围内
            self._owner_depts.setdefault(key, None)

    def _allows(self, dept_ids: Optional[frozenset[int]], owner: Optional[str]) -> bool:
        """按部门集合判定归属人是否落在范围内；未预取的归属人按不在范围处理并告警。"""
        if dept_ids is None:
            return True
        key = normalize_username(owner)
        if key == self.username:
            return True
        if not dept_ids:
            return False
        if key not in self._owner_depts:
            LOGGER.error(f"归属人[{key}]未预取部门，按不在数据范围处理；请先调用 load_owners")
            return False
        return self._owner_depts[key] in dept_ids

    def can_read(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户查看。

        :param owner: 数据归属账号(owner_user或created_user)，需先经 load_owners 预取
        :return: 允许返回True
        """
        return self._allows(self.read_depts, owner)

    def can_write(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户修改。

        :param owner: 数据归属账号(owner_user或created_user)，需先经 load_owners 预取
        :return: 允许返回True
        """
        return self._allows(self.write_depts, owner)

    def can_delete(self, owner: Optional[str]) -> bool:
        """
        判断指定归属人的数据是否允许当前用户删除。

        可删范围独立于可写范围：可编辑他人数据不代表可删除他人数据。

        :param owner: 数据归属账号(owner_user或created_user)，需先经 load_owners 预取
        :return: 允许返回True
        """
        return self._allows(self.delete_depts, owner)

    @classmethod
    def system(cls) -> "DataScope":
        """
        系统内部流程(任务执行、引擎回写)的数据权限上下文，不受归属限制。

        :return: 读写删均不限范围的上下文
        """
        return cls(
            username="",
            read_depts=None,
            write_depts=None,
            delete_depts=None,
            is_system=True,
        )

    @staticmethod
    def _clamp_to_read(
            read_depts: Optional[frozenset[int]],
            write_depts: Optional[frozenset[int]],
            delete_depts: Optional[frozenset[int]],
    ) -> tuple[Optional[frozenset[int]], Optional[frozenset[int]]]:
        """写/删范围收敛到可见范围内，避免出现不可见的可写数据；本人由判定逻辑单独兜底。"""
        if read_depts is None:
            return write_depts, delete_depts
        clamped_write = read_depts if write_depts is None else frozenset(write_depts & read_depts)
        clamped_delete = read_depts if delete_depts is None else frozenset(delete_depts & read_depts)
        return clamped_write, clamped_delete

    @classmethod
    async def _resolve_depts(
            cls,
            user: User,
            scope: DataScopeEnum,
    ) -> Optional[frozenset[int]]:
        """把范围枚举解析为部门ID集合；ALL 返回 None 表示不限，空集表示仅本人。"""
        if scope == DataScopeEnum.ALL:
            return None
        if scope in (DataScopeEnum.DEPT, DataScopeEnum.DEPT_AND_CHILD):
            return frozenset(await cls._dept_ids(user.dept_id, scope))
        return frozenset()

    @classmethod
    async def _dept_ids(cls, dept_id: Optional[int], scope: DataScopeEnum) -> list[int]:
        """解析部门范围：DEPT 取本部门，DEPT_AND_CHILD 借闭包表展开下级。"""
        if not dept_id:
            return []
        if scope == DataScopeEnum.DEPT:
            return [dept_id]
        descendants = await DeptStruct.filter(ancestor=dept_id).values_list("descendant", flat=True)
        return list(descendants) or [dept_id]


@dataclass
class _ScopeResolver:
    """
    一次请求内共享的数据权限解析状态。

    角色、标签覆盖与部门集合只加载一次：接口鉴权已查过的角色直接复用，
    子资源切换到父资源族时不再重复查询角色表与标签覆盖表。
    """

    user: User
    username: str
    roles: List[Role]
    _overrides: Optional[Dict[str, Dict[int, RoleTags]]] = None
    _depts: Dict[DataScopeEnum, Optional[frozenset[int]]] = field(default_factory=dict)
    _scopes: Dict[str, DataScope] = field(default_factory=dict)

    async def resolve(self, tag: str) -> DataScope:
        """解析指定资源族的数据权限上下文，同一标签只解析一次。"""
        cached = self._scopes.get(tag)
        if cached is not None:
            return cached

        levels = await self._effective_levels(tag)
        # 读/写/删常配置成同一范围(如均为本部门)，按枚举去重只解析一次部门集合
        depts: Dict[DataScopeEnum, Optional[frozenset[int]]] = {}
        for level in levels:
            if level not in self._depts:
                self._depts[level] = await DataScope._resolve_depts(self.user, level)
            depts[level] = self._depts[level]
        read_depts, write_depts, delete_depts = (depts[level] for level in levels)
        write_depts, delete_depts = DataScope._clamp_to_read(read_depts, write_depts, delete_depts)
        scope = DataScope(
            username=self.username,
            read_depts=read_depts,
            write_depts=write_depts,
            delete_depts=delete_depts,
            tag=tag,
            _resolver=self,
        )
        self._scopes[tag] = scope
        return scope

    async def _effective_levels(self, tag: str) -> tuple[DataScopeEnum, DataScopeEnum, DataScopeEnum]:
        """按「标签覆盖 > 角色默认」逐字段解析范围，多角色取最宽。"""
        if not self.roles:
            return DataScopeEnum.SELF, DataScopeEnum.SELF, DataScopeEnum.SELF
        # 管理员角色与超管同权：固定全部数据，无视角色三字段与标签覆盖
        if BuiltinRoleCode.includes_admin(role.code for role in self.roles):
            return DataScopeEnum.ALL, DataScopeEnum.ALL, DataScopeEnum.ALL

        overrides = await self._tag_overrides(tag)
        read_levels: List[DataScopeEnum] = []
        write_levels: List[DataScopeEnum] = []
        delete_levels: List[DataScopeEnum] = []
        for role in self.roles:
            override = overrides.get(role.id)
            # 标签覆盖允许逐字段继承：显式值为空时回落到角色默认范围
            read_levels.append((override.select_scope if override else None) or role.select_scope)
            write_levels.append((override.update_scope if override else None) or role.update_scope)
            delete_levels.append((override.delete_scope if override else None) or role.delete_scope)
        return widest_scope(read_levels), widest_scope(write_levels), widest_scope(delete_levels)

    async def _tag_overrides(self, tag: str) -> Dict[int, RoleTags]:
        """取指定资源族的角色覆盖；首次调用一次性加载全部可配置标签，避免逐标签查库。"""
        if tag == LEGACY_TAG or not self.roles:
            return {}
        if self._overrides is None:
            scope_tags = [member.value for member in ResourceTag if member.scope_aware]
            rows = await RoleTags.filter(
                role_id__in=[role.id for role in self.roles],
                tag__in=scope_tags,
            )
            grouped: Dict[str, Dict[int, RoleTags]] = {}
            for row in rows:
                grouped.setdefault(row.tag, {})[row.role_id] = row
            self._overrides = grouped
        return self._overrides.get(tag, {})


async def get_tag_scope(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
) -> DataScope:
    """FastAPI依赖：按请求路由启动时绑定的资源族编码解析数据权限上下文。"""
    resource = getattr(request.scope.get("route"), "resource", None)
    tag: str = resource.value if resource is not None else LEGACY_TAG
    if current_user.is_superuser:
        return await DataScope.from_user(user=current_user, tag=tag)
    # 与接口鉴权共用请求级角色缓存，同一请求只查一次用户角色
    roles: List[Role] = await load_request_roles(request=request, user=current_user)
    return await DataScope.from_user(user=current_user, tag=tag, roles=roles)


DependTagScope = Depends(get_tag_scope)