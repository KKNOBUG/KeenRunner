# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : permission_rule.py
@DateTime: 2026/8/9 15:41
"""
from typing import Iterable, List, Optional, Sequence, Tuple

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.configure import LOGGER

ROLE_CODE_ADMIN = "Administrators"
ROLE_CODE_USER = "Users"
ROLE_CODE_GUEST = "Guests"
BUILTIN_ROLE_CODES = (ROLE_CODE_ADMIN, ROLE_CODE_USER, ROLE_CODE_GUEST)

SYSTEM_PREFIX = "系统管理:"
BUSINESS_PREFIXES = ("应用管理:", "自动化测试:", "任务管理:", "便捷工具:")

# 个人白名单（标准/宾客可绑）；另含不告警的公开接口 summary
SELF_SERVICE_SUMMARIES = frozenset({"更新用户密码(个人)", "用户登出"})
SUMMARY_NO_WARN_EXACT = SELF_SERVICE_SUMMARIES | frozenset({"生成访问令牌"})

ACTION_READ = "read"
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_EXECUTE = "execute"
ACTION_IMPORT = "import"
ACTION_OPS = "ops"
ACTION_UNKNOWN = "unknown"

# 判定优先级：靠前优先匹配
_ACTION_RULES: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("批量删除", "删除", "清空"), ACTION_DELETE),
    (("刷新",), ACTION_OPS),
    (("执行", "调试", "启动", "停止"), ACTION_EXECUTE),
    (("导入", "上传"), ACTION_IMPORT),
    (("更新",), ACTION_UPDATE),
    (("新增",), ACTION_CREATE),
    (("查询", "导出", "下载"), ACTION_READ),
)
_ALL_SUMMARY_PREFIXES: Tuple[str, ...] = tuple(
    prefix for prefixes, _ in _ACTION_RULES for prefix in prefixes
)


def _norm_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _method_value(router: Router) -> str:
    method = getattr(router, "method", None)
    if method is None:
        return ""
    if hasattr(method, "value"):
        return str(method.value).upper()
    return str(method).upper()


def _startswith_any(text: str, prefixes: Sequence[str]) -> bool:
    return any(text.startswith(prefix) for prefix in prefixes)


def _tag_parts(router: Router) -> List[str]:
    return [part.strip() for part in _norm_text(router.tags).split(",") if part.strip()]


def _is_system_router(router: Router) -> bool:
    return any(part.startswith(SYSTEM_PREFIX) for part in _tag_parts(router))


def _is_business_router(router: Router) -> bool:
    return any(
        part.startswith(prefix)
        for part in _tag_parts(router)
        for prefix in BUSINESS_PREFIXES
    )


def _summary_matches_convention(summary: str) -> bool:
    if not summary:
        return False
    if summary in SUMMARY_NO_WARN_EXACT:
        return True
    return _startswith_any(summary, _ALL_SUMMARY_PREFIXES)


def classify_router_action(router: Router) -> str:
    """
    按 summary 前缀识别行为；DELETE 方法视为删除。
    summary 无法匹配时：GET 回落为查询，其余为 unknown。
    """
    summary = _norm_text(router.summary)
    method = _method_value(router)

    if method == "DELETE":
        return ACTION_DELETE
    for prefixes, action in _ACTION_RULES:
        if _startswith_any(summary, prefixes):
            return action
    if method == "GET":
        return ACTION_READ
    return ACTION_UNKNOWN


def role_allows_router(role_code: str, router: Router) -> bool:
    """判断内置角色是否应按规则拥有该路由。"""
    if role_code == ROLE_CODE_ADMIN:
        return True

    action = classify_router_action(router)
    if action == ACTION_OPS:
        return False
    if _norm_text(router.summary) in SELF_SERVICE_SUMMARIES:
        return True

    business = _is_business_router(router)
    if role_code == ROLE_CODE_USER:
        # 业务全开；系统及未知域仅读
        return True if business else action == ACTION_READ
    if role_code == ROLE_CODE_GUEST:
        # 业务仅查/增；系统及未知域仅读
        if business:
            return action in (ACTION_READ, ACTION_CREATE)
        return action == ACTION_READ
    return False


def filter_routers_for_role(role_code: str, routers: Iterable[Router]) -> List[Router]:
    return [router for router in routers if role_allows_router(role_code, router)]


def warn_unclassified_routers(routers: Iterable[Router]) -> int:
    """对 summary 不符合规范的路由打告警，返回告警条数。"""
    count = 0
    for router in routers:
        summary = _norm_text(router.summary)
        if _summary_matches_convention(summary):
            continue
        LOGGER.warning(
            "[权限规则]路由 summary 无法按规范分类, "
            f"method={_method_value(router)}, path={getattr(router, 'path', '')}, "
            f"summary={summary!r}, tags={_norm_text(router.tags)!r}, "
            f"fallback_action={classify_router_action(router)}。"
            f"请按 README「API 接口 summary 编写规范」修正。"
        )
        count += 1
    if count:
        LOGGER.warning(f"[权限规则]共 {count} 条路由 summary 无法分类，请尽快修正以免权限漏绑/错绑")
    return count


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


async def sync_role_permission_bindings(routers: Optional[Sequence[Router]] = None, menus: Optional[Sequence[Menu]] = None) -> None:
    """
    刷新/同步统一入口：告警未分类 summary，并为内置三角色补绑路由与菜单（只追加）。
    角色不存在时跳过（首次初始化路由早于角色时安全）。
    """
    all_routers: List[Router] = list(routers) if routers is not None else await Router.all()
    all_menus: List[Menu] = list(menus) if menus is not None else await Menu.all()

    warn_unclassified_routers(all_routers)

    if not all_routers and not all_menus:
        LOGGER.info("[权限规则]无路由/菜单可绑定，跳过")
        return

    for role_code in BUILTIN_ROLE_CODES:
        role = await Role.get_or_none(code=role_code)
        if not role:
            LOGGER.info(f"[权限规则]角色[{role_code}]不存在，跳过补绑")
            continue
        if all_routers:
            allowed = filter_routers_for_role(role_code, all_routers)
            await _append_missing_relations(role, "routers", allowed, "路由")
        if all_menus:
            await _append_missing_relations(role, "menus", all_menus, "菜单")
