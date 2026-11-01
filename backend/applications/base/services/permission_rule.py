# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : permission_rule.py
@DateTime: 2026/8/9 15:41
"""
from typing import Iterable, List, Optional, Sequence, Tuple

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.common.permission_action import (
    ACTION_OPS,
    ACTION_READ,
    ACTION_UNKNOWN,
    derive_action,
)
from backend.configure import LOGGER
from backend.enums import BuiltinRoleCode, ResourceTag


class PermissionRule:
    """
    内置角色路由权限规则引擎。

    职责与约束：
    - 行为类型由路径末段动词判定，资源域由路由标签对应的资源族判定；
      两者均来自启动时绑定的契约，summary 不再参与权限判定
    - 内置三角色(Administrators/Users/Guests)的路由放行规则与补绑(只追加，不回收)；
      管理员角色运行期本就全量放行，补绑仅让其菜单/路由可见，不参与鉴权判定；
      例外：依赖 get_superuser 的管理员专属路由会从非管理员角色上回收；
    - 角色菜单是管理员的人工配置，只在显式传入 menus 时补绑，路由刷新不得覆盖
    - 无实例状态，常量与规则集中为类属性，调用方统一经 PermissionRule 入口访问
    """

    # ==================== 常量：内置角色码 ====================
    ROLE_CODE_ADMIN: str = BuiltinRoleCode.ADMIN.value
    ROLE_CODE_USER: str = BuiltinRoleCode.USER.value
    ROLE_CODE_GUEST: str = BuiltinRoleCode.GUEST.value
    BUILTIN_ROLE_CODES: Tuple[str, ...] = tuple(BuiltinRoleCode.get_values())

    # ==================== 内部工具(不对外暴露) ====================
    @staticmethod
    def _norm_text(value: Optional[str]) -> str:
        return (value or "").strip()

    @staticmethod
    def _method_value(router: Router) -> str:
        method = getattr(router, "method", None)
        if method is None:
            return ""
        if hasattr(method, "value"):
            return str(method.value).upper()
        return str(method).upper()

    @classmethod
    def _tag_parts(cls, router: Router) -> List[str]:
        return [part.strip() for part in cls._norm_text(router.tags).split(",") if part.strip()]

    @classmethod
    def _resource(cls, router: Router) -> Optional[ResourceTag]:
        """按路由标签匹配资源族，未登记返回 None（不参与自动绑定）。"""
        return ResourceTag.of_tags(cls._tag_parts(router))

    # ==================== 行为判定 ====================
    @classmethod
    def classify_router_action(cls, router: Router) -> str:
        """
        按 HTTP 方法与路径末段动词识别行为。

        DELETE 一律删除；GET 无动词回落查询；其余无动词为 unknown。

        :param router: 路由记录
        :return: 动作类型(ACTION_* 常量之一)
        """
        return derive_action(cls._method_value(router), router.path)

    # ==================== 角色放行规则 ====================
    @classmethod
    def role_allows_router(cls, role_code: str, router: Router) -> bool:
        """
        判断内置角色是否应按规则拥有该路由。

        :param role_code: 角色编码(BUILTIN_ROLE_CODES 之一)
        :param router: 路由记录
        :return: 放行返回True，拦截返回False
        """
        if role_code == cls.ROLE_CODE_ADMIN:
            return True

        # 管理员专属接口（依赖 get_superuser 守卫）不向内置非管理员角色开放
        if getattr(router, "available_only_admin", False):
            return False

        resource: Optional[ResourceTag] = cls._resource(router)
        if resource is None:
            return False
        action = cls.classify_router_action(router)
        if action == ACTION_OPS:
            return False

        if role_code == cls.ROLE_CODE_USER:
            # 业务全开；系统域仅读
            return True if resource.domain.is_business else action == ACTION_READ
        if role_code == cls.ROLE_CODE_GUEST:
            # autotest 共享策略：业务域全部放行(含执行/调试/上传/下载)，
            # 数据删除由 service 层按归属人收口，接口权限不再阻断共享操作
            if resource.domain.is_business:
                return True
            return action == ACTION_READ
        return False

    @classmethod
    def filter_routers_for_role(cls, role_code: str, routers: Iterable[Router]) -> List[Router]:
        """
        按角色放行规则过滤路由集合。

        :param role_code: 角色编码(BUILTIN_ROLE_CODES 之一)
        :param routers: 路由记录集合
        :return: 该角色放行的路由列表
        """
        return [router for router in routers if cls.role_allows_router(role_code, router)]

    # ==================== 对外服务入口 ====================
    @classmethod
    def warn_unclassified_routers(cls, routers: Iterable[Router]) -> int:
        """
        对资源族未登记或路径无法推导行为的路径打 ERROR 日志，不阻断启动。

        :param routers: 路由记录集合
        :return: 告警条数
        """
        count: int = 0
        for router in routers:
            method = cls._method_value(router)
            path = getattr(router, "path", "")
            tags = cls._norm_text(router.tags)
            if cls._resource(router) is None:
                LOGGER.error(
                    f"[权限规则]路由资源族未登记, method={method}, path={path}, tags={tags!r}。"
                    f"请按 backend/README.md「接口路径与行为规范」修正"
                )
                count += 1
            if cls.classify_router_action(router) == ACTION_UNKNOWN:
                LOGGER.error(
                    f"[权限规则]路由路径末段缺少已知动词, method={method}, path={path}, tags={tags!r}。"
                    f"请按 backend/README.md「接口路径与行为规范」修正"
                )
                count += 1
        if count:
            LOGGER.error(f"[权限规则]共 {count} 条路由契约异常，已按默认策略处理，请尽快修正")
        return count

    @staticmethod
    async def _append_missing_relations(role: Role, relation_name: str, candidates: Sequence, label: str) -> None:
        """向角色 M2M 追加尚未绑定的对象。"""
        relation = getattr(role, relation_name)
        existing = await relation.all()
        existing_ids = {item.id for item in existing}
        to_add = [item for item in candidates if item.id not in existing_ids]
        if not to_add:
            LOGGER.info(f"[权限规则]角色[{role.name}]无需补绑{label}")
            return
        await relation.add(*to_add)
        LOGGER.info(f"[权限规则]角色[{role.name}]补绑{label}成功, 新增{len(to_add)}个, 候选共{len(candidates)}个")

    @classmethod
    async def drop_available_only_admin_bindings(cls, routers: Sequence[Router]) -> None:
        """
        回收所有非管理员角色上的管理员专属路由绑定。

        这类接口由 get_superuser 硬校验，非管理员角色即使绑定也必然 403，
        留着只会让前端错误地展示可用入口。

        :param routers: 路由记录集合
        :return: None
        """
        available_only_admin_ids = {router.id for router in routers if getattr(router, "available_only_admin", False)}
        if not available_only_admin_ids:
            return
        roles = await Role.exclude(code=cls.ROLE_CODE_ADMIN).all()
        for role in roles:
            relation = getattr(role, "routers")
            to_remove = [item for item in await relation.all() if item.id in available_only_admin_ids]
            if not to_remove:
                continue
            await relation.remove(*to_remove)
            removed = ",".join(f"{item.method.value} {item.path}" for item in to_remove)
            LOGGER.info(f"[权限规则]角色[{role.name}]回收管理员专属路由{len(to_remove)}个: {removed}")

    @classmethod
    async def sync_role_permission_bindings(cls, routers: Optional[Sequence[Router]] = None, menus: Optional[Sequence[Menu]] = None) -> None:
        """
        刷新/同步统一入口：告警未分类 summary，并为内置三角色补绑路由（只追加，
        管理员专属路由例外地会从非管理员角色上回收）。

        菜单属于管理员在「权限」抽屉中的人工配置：只有显式传入 menus 时才补绑，
        路由刷新传 None 时不得读取全表回填，否则被回收的菜单会在 refresh 后复活。

        角色不存在时跳过（首次初始化路由早于角色时安全）。

        :param routers: 待补绑的路由集合；None 时查询全表
        :param menus: 待补绑的菜单集合；None 时不处理菜单
        """
        all_routers: List[Router] = list(routers) if routers is not None else await Router.all()
        all_menus: List[Menu] = list(menus) if menus is not None else []

        cls.warn_unclassified_routers(all_routers)

        if not all_routers and not all_menus:
            LOGGER.info("[权限规则]无路由/菜单可绑定，跳过")
            return

        for role_code in cls.BUILTIN_ROLE_CODES:
            role = await Role.get_or_none(code=role_code)
            if not role:
                LOGGER.info(f"[权限规则]角色[{role_code}]不存在，跳过补绑")
                continue
            if all_routers:
                allowed = cls.filter_routers_for_role(role_code, all_routers)
                await cls._append_missing_relations(role, "routers", allowed, "路由")
            if all_menus:
                await cls._append_missing_relations(role, "menus", all_menus, "菜单")

        if all_routers:
            await cls.drop_available_only_admin_bindings(all_routers)
