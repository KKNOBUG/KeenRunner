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
from backend.configure import LOGGER


class PermissionRule:
    """
    内置角色路由权限规则引擎。

    职责与约束：
    - 按 summary 前缀动词判定路由行为类型，权限初始化与「刷新路由」的自动补绑均依赖该判定，
      summary 写法不规范会导致角色权限漏绑或错绑
    - 内置三角色(Administrators/Users/Guests)的路由放行规则与补绑(只追加，不回收)
    - 无实例状态，常量与规则集中为类属性，调用方统一经 PermissionRule 入口访问
    """

    # ==================== 常量：内置角色码 ====================
    ROLE_CODE_ADMIN: str = "Administrators"
    ROLE_CODE_USER: str = "Users"
    ROLE_CODE_GUEST: str = "Guests"
    BUILTIN_ROLE_CODES: Tuple[str, ...] = (ROLE_CODE_ADMIN, ROLE_CODE_USER, ROLE_CODE_GUEST)

    # ==================== 常量：路由域前缀与个人白名单 ====================
    SYSTEM_PREFIX: str = "系统管理:"
    BUSINESS_PREFIXES: Tuple[str, ...] = ("应用管理:", "自动化测试:", "任务管理:", "便捷工具:")

    # 个人白名单（标准/宾客可绑）；另含不告警的公开接口 summary
    SELF_SERVICE_SUMMARIES: frozenset = frozenset({"更新用户密码(个人)", "用户登出"})
    SUMMARY_NO_WARN_EXACT: frozenset = SELF_SERVICE_SUMMARIES | frozenset({"生成访问令牌"})

    # ==================== 常量：动作类型 ====================
    ACTION_OPS: str = "ops"
    ACTION_READ: str = "read"
    ACTION_CREATE: str = "create"
    ACTION_UPDATE: str = "update"
    ACTION_DELETE: str = "delete"
    ACTION_UPLOAD: str = "upload"
    ACTION_EXECUTE: str = "execute"
    ACTION_UNKNOWN: str = "unknown"
    ACTION_DOWNLOAD: str = "download"

    # 判定优先级：靠前优先匹配
    _ACTION_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
        (("刷新",), ACTION_OPS),
        (("查询",), ACTION_READ),
        (("更新",), ACTION_UPDATE),
        (("新增",), ACTION_CREATE),
        (("导入", "上传"), ACTION_UPLOAD),
        (("导出", "下载"), ACTION_DOWNLOAD),
        (("删除", "批量删除",), ACTION_DELETE),
        (("执行", "调试", "启动", "停止"), ACTION_EXECUTE),
    )
    _ALL_SUMMARY_PREFIXES: Tuple[str, ...] = tuple(
        prefix for prefixes, _ in _ACTION_RULES for prefix in prefixes
    )

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

    @staticmethod
    def _startswith_any(text: str, prefixes: Sequence[str]) -> bool:
        return any(text.startswith(prefix) for prefix in prefixes)

    @classmethod
    def _tag_parts(cls, router: Router) -> List[str]:
        return [part.strip() for part in cls._norm_text(router.tags).split(",") if part.strip()]

    @classmethod
    def _is_system_router(cls, router: Router) -> bool:
        return any(part.startswith(cls.SYSTEM_PREFIX) for part in cls._tag_parts(router))

    @classmethod
    def _is_business_router(cls, router: Router) -> bool:
        return any(
            part.startswith(prefix)
            for part in cls._tag_parts(router)
            for prefix in cls.BUSINESS_PREFIXES
        )

    @classmethod
    def _summary_matches_convention(cls, summary: str) -> bool:
        if not summary:
            return False
        if summary in cls.SUMMARY_NO_WARN_EXACT:
            return True
        return cls._startswith_any(summary, cls._ALL_SUMMARY_PREFIXES)

    # ==================== 行为判定 ====================
    @classmethod
    def classify_router_action(cls, router: Router) -> str:
        """
        按 summary 前缀识别行为；DELETE 方法视为删除。

        summary 无法匹配时：GET 回落为查询，其余为 unknown。

        :param router: 路由记录
        :return: 动作类型(ACTION_* 常量之一)
        """
        summary = cls._norm_text(router.summary)
        method = cls._method_value(router)

        if method == "DELETE":
            return cls.ACTION_DELETE
        for prefixes, action in cls._ACTION_RULES:
            if cls._startswith_any(summary, prefixes):
                return action
        if method == "GET":
            return cls.ACTION_READ
        return cls.ACTION_UNKNOWN

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

        action = cls.classify_router_action(router)
        if action == cls.ACTION_OPS:
            return False
        if cls._norm_text(router.summary) in cls.SELF_SERVICE_SUMMARIES:
            return True

        business = cls._is_business_router(router)
        if role_code == cls.ROLE_CODE_USER:
            # 业务全开；系统及未知域仅读
            return True if business else action == cls.ACTION_READ
        if role_code == cls.ROLE_CODE_GUEST:
            # 业务仅查/增；系统及未知域仅读
            if business:
                return action in (cls.ACTION_READ, cls.ACTION_CREATE)
            return action == cls.ACTION_READ
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
        对 summary 不符合规范的路由打告警。

        :param routers: 路由记录集合
        :return: 告警条数
        """
        count: int = 0
        for router in routers:
            summary = cls._norm_text(router.summary)
            if cls._summary_matches_convention(summary):
                continue
            LOGGER.warning(
                "[权限规则]路由 summary 无法按规范分类, "
                f"method={cls._method_value(router)}, path={getattr(router, 'path', '')}, "
                f"summary={summary!r}, tags={cls._norm_text(router.tags)!r}, "
                f"fallback_action={cls.classify_router_action(router)}。"
                f"请按 README「API 接口 summary 编写规范」修正。"
            )
            count += 1
        if count:
            LOGGER.warning(f"[权限规则]共 {count} 条路由 summary 无法分类，请尽快修正以免权限漏绑/错绑")
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
    async def sync_role_permission_bindings(cls, routers: Optional[Sequence[Router]] = None, menus: Optional[Sequence[Menu]] = None) -> None:
        """
        刷新/同步统一入口：告警未分类 summary，并为内置三角色补绑路由与菜单（只追加）。

        角色不存在时跳过（首次初始化路由早于角色时安全）。

        :param routers: 待补绑的路由集合；None 时查询全表
        :param menus: 待补绑的菜单集合；None 时查询全表
        """
        all_routers: List[Router] = list(routers) if routers is not None else await Router.all()
        all_menus: List[Menu] = list(menus) if menus is not None else await Menu.all()

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
