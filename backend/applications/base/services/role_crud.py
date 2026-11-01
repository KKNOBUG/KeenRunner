# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : role_crud.py
@DateTime: 2025/2/19 23:08
"""
import traceback
from typing import Dict, List, Optional, Set

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.transactions import in_transaction

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.role_tag_model import RoleTags
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.role_schema import RoleCreate, RoleUpdate, RoleRouterItem, RoleTagScopeItem
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException
from backend.enums import BuiltinRoleCode, DataScopeEnum, ResourceTag
from backend.services.resource_policy import scope_covers


class RoleCrud(ScaffoldCrud[Role, RoleCreate, RoleUpdate]):

    def __init__(self):
        super().__init__(model=Role)

    async def get_by_id(self, role_id: int, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据主键ID查询角色。

        :param role_id: 角色ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        """
        if not role_id:
            error_message: str = "查询角色信息失败, 参数[role_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=role_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[id={role_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, role_code: str, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据角色编码查询单条角色。

        :param role_code: 角色编码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        """
        if not role_code:
            error_message: str = "查询角色信息失败, 参数[role_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_by_conditions(only_one=True, on_error=False, code=role_code, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[code={role_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_name(self, role_name: str, on_error: bool = False, **kwargs) -> Optional[Role]:
        """
        根据角色名称查询单条角色。

        :param role_name: 角色名称
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 角色实例或None
        """
        if not role_name:
            error_message: str = "查询角色信息失败, 参数[role_name]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_by_conditions(only_one=True, on_error=False, name=role_name, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询角色信息失败, 记录[name={role_name}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def is_exist(self, name: str, **kwargs) -> bool:
        """
        判断指定名称的角色是否存在。

        :param name: 角色名称
        :param kwargs: 额外过滤条件
        :return: 存在返回True，否则False
        """
        return await self.model.filter(name=name, **kwargs).exists()

    async def create_role(self, role_in: RoleCreate) -> Role:
        """
        创建角色：校验code/name唯一性后落库。

        新角色不自动绑定菜单、接口与标签范围，权限须由管理员在「权限」抽屉中显式配置。

        :param role_in: 新增角色入参
        :return: 新建的角色实例
        """
        code = role_in.code
        name = role_in.name
        if await self.model.filter(code=code).exists():
            error_message: str = f"创建角色信息失败, 记录[code={code}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        if await self.model.filter(name=name).exists():
            error_message: str = f"创建角色信息失败, 记录[name={name}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        self._assert_scope_order(
            select_scope=role_in.select_scope,
            update_scope=role_in.update_scope,
            delete_scope=role_in.delete_scope,
        )
        try:
            instance = await self.create(role_in)
        except IntegrityError as e:
            # 并发建同名/同编码：预校验会同时通过，靠唯一索引收敛为业务已存在
            error_message: str = f"创建角色信息失败, 记录[code={code}, name={name}]信息已存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def update_role(self, role_in: RoleUpdate) -> Role:
        """
        根据角色ID更新角色基础字段（不含菜单/路由绑定）。

        :param role_in: 更新入参（含可选 updated_user；有登录上下文时由服务端覆盖）
        :return: 更新后的角色实例
        """
        role_id = role_in.id
        role_obj = await self.get_by_id(role_id=role_id, on_error=True)

        update_dict = role_in.update_dict()
        code = update_dict.get("code")
        name = update_dict.get("name")
        if code and code != role_obj.code and role_obj.code == BuiltinRoleCode.ADMIN.value:
            error_message: str = "更新角色信息失败, 管理员角色编码不允许修改"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if code and await self.model.filter(code=code).exclude(id=role_id).exists():
            error_message: str = f"更新角色信息失败, 记录[code={code}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        if name and await self.model.filter(name=name).exclude(id=role_id).exists():
            error_message: str = f"更新角色信息失败, 记录[name={name}]已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        self._assert_scope_order(
            select_scope=update_dict.get("select_scope") or role_obj.select_scope,
            update_scope=update_dict.get("update_scope") or role_obj.update_scope,
            delete_scope=update_dict.get("delete_scope") or role_obj.delete_scope,
        )
        try:
            instance = await self.update(id=role_id, obj_in=role_in)
        except DoesNotExist as e:
            error_message: str = f"更新角色信息失败, 记录[id={role_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            # 并发改名/改编码撞唯一索引与创建同口径，返回已存在而非服务异常
            error_message: str = f"更新角色信息失败, 记录[id={role_id}]的编码/名称与已有记录冲突"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def save_authorization(
            self,
            role: Role,
            menu_ids: List[int],
            router_infos: List[RoleRouterItem],
            tag_scopes: Optional[List[RoleTagScopeItem]] = None,
    ) -> None:
        """
        重置角色的菜单、接口与标签范围。

        三者同属一次授权：先批量校验全部入参，再在同一事务内重建；
        既避免循环查库，也避免菜单已清空、后续校验失败导致的部分更新。

        :param role: 角色实例
        :param menu_ids: 菜单ID列表
        :param router_infos: 接口绑定项列表
        :param tag_scopes: 标签范围覆盖列表；None表示本次不修改
        :return: None
        """
        if role is None:
            error_message: str = "更新角色权限失败, 参数[role]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        menus: List[Menu] = await self._load_menus(menu_ids)
        routers: List[Router] = await self._load_routers(router_infos)
        tag_rows: Optional[List[Dict]] = self._build_tag_scope_rows(role, tag_scopes) if tag_scopes is not None else None

        async with in_transaction() as conn:
            await role.menus.clear(using_db=conn)
            if menus:
                await role.menus.add(*menus, using_db=conn)
            await role.routers.clear(using_db=conn)
            if routers:
                await role.routers.add(*routers, using_db=conn)
            if tag_rows is not None:
                await RoleTags.filter(role_id=role.id).using_db(conn).delete()
                if tag_rows:
                    await RoleTags.bulk_create([RoleTags(**row) for row in tag_rows], using_db=conn)

    @staticmethod
    async def _load_menus(menu_ids: List[int]) -> List[Menu]:
        """批量加载菜单并校验全部存在。

        :param menu_ids: 菜单ID列表
        :return: 去重后的菜单实例列表
        """
        ids: List[int] = list(dict.fromkeys(int(menu_id) for menu_id in menu_ids or []))
        if not ids:
            return []
        menus: List[Menu] = await Menu.filter(id__in=ids)
        missing: List[int] = sorted(set(ids) - {menu.id for menu in menus})
        if missing:
            error_message: str = f"更新角色权限失败, 菜单[id={missing}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return menus

    @staticmethod
    async def _load_routers(router_infos: List[RoleRouterItem]) -> List[Router]:
        """批量加载接口并校验全部存在，管理员专属接口直接忽略。

        :param router_infos: 接口绑定项列表
        :return: 可授予角色的接口实例列表
        """
        pairs: List[tuple] = list(dict.fromkeys(
            ((item.path or "").strip(), (item.method or "").strip().upper()) for item in router_infos or []
        ))
        if not pairs:
            return []
        rows: List[Router] = await Router.filter(path__in=[path for path, _ in pairs])
        by_key: Dict[tuple, Router] = {(row.path, row.method): row for row in rows}
        missing: List[tuple] = [pair for pair in pairs if pair not in by_key]
        if missing:
            error_message: str = f"更新角色权限失败, 路由[path, method]={missing}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)

        granted: List[Router] = []
        for path, method in pairs:
            router_obj: Router = by_key[(path, method)]
            # 管理员专属接口仅管理员可调用，分配给其他角色必然 403，直接忽略
            if router_obj.available_only_admin:
                LOGGER.warning(f"更新角色权限: 路由[{method} {path}]为管理员专属, 已忽略该分配")
                continue
            granted.append(router_obj)
        return granted

    # ------------------------------ 标签范围 ------------------------------

    @staticmethod
    def _assert_scope_order(select_scope: DataScopeEnum, update_scope: DataScopeEnum, delete_scope: DataScopeEnum) -> None:
        """校验角色全局的可写/可删范围不宽于可见范围。"""
        for scope, label in ((update_scope, "可写"), (delete_scope, "可删")):
            if not scope_covers(select_scope, scope):
                error_message: str = f"保存角色信息失败, {label}范围[{scope.value}]不能大于可见范围[{select_scope.value}]"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)

    @staticmethod
    def list_resource_tags() -> List[str]:
        """
        返回接入行级数据权限的资源族编码，作为标签范围配置的可选项。

        标签直接来自资源族枚举而非路由表，新增资源族无需等待路由刷新即可配置；
        未接入 DataScope 的资源族不列出，避免配置了却不生效的空项。

        :return: 资源族编码列表
        """
        return [tag.value for tag in ResourceTag if tag.scope_aware]

    async def list_tag_scopes(self, role_id: int) -> List[Dict]:
        """
        查询角色的标签范围：显式覆盖值与未覆盖时生效的角色默认范围。

        :param role_id: 角色ID
        :return: 每项含资源族编码、展示名、显式覆盖值、角色默认值
        """
        role = await self.get_by_id(role_id=role_id, on_error=True)
        tags: List[str] = self.list_resource_tags()
        # 只读当前接入的资源族；表内不在枚举内的历史行不参与判定，下次保存时随重建一并清理
        overrides: Dict[str, RoleTags] = {
            row.tag: row for row in await RoleTags.filter(role_id=role_id, tag__in=tags)
        }
        return [
            {
                "tag": tag,
                "tag_label": ResourceTag.label_of(tag),
                "select_scope": overrides[tag].select_scope if tag in overrides else None,
                "update_scope": overrides[tag].update_scope if tag in overrides else None,
                "delete_scope": overrides[tag].delete_scope if tag in overrides else None,
                "default_select_scope": role.select_scope,
                "default_update_scope": role.update_scope,
                "default_delete_scope": role.delete_scope,
            }
            for tag in tags
        ]

    def _build_tag_scope_rows(self, role: Role, items: List[RoleTagScopeItem]) -> List[Dict]:
        """
        校验标签范围并生成待落库行，三字段均为空的标签不落库。

        显式可写/可删范围不得宽于当前生效的可见范围，否则拒绝保存。

        :param role: 角色实例，用于取默认范围
        :param items: 标签范围项列表
        :return: RoleTags 构造参数字典列表
        """
        valid_tags: Set[str] = set(self.list_resource_tags())
        rows: List[Dict] = []
        seen: Set[str] = set()
        for item in items or []:
            tag: str = (item.tag or "").strip()
            if tag not in valid_tags:
                error_message: str = f"保存角色标签范围失败, 标签[tag={tag}]未在资源族枚举中登记"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            if tag in seen:
                error_message: str = f"保存角色标签范围失败, 标签[tag={tag}]重复"
                LOGGER.error(error_message)
                raise ParameterException(message=error_message)
            seen.add(tag)
            self._assert_tag_scope_order(role, tag, item)
            if item.select_scope is None and item.update_scope is None and item.delete_scope is None:
                continue
            rows.append({
                "role_id": role.id,
                "tag": tag,
                "select_scope": item.select_scope,
                "update_scope": item.update_scope,
                "delete_scope": item.delete_scope,
            })
        return rows

    @staticmethod
    def _assert_tag_scope_order(role: Role, tag: str, item: RoleTagScopeItem) -> None:
        """
        校验可写/可删范围不宽于可见范围，保证不可写入不可读取的数据。

        未显式设置的字段按角色默认范围参与校验：否则保存后回读展示默认值、
        运行期却被可见范围收敛，配置与实际生效值不一致。
        """
        read_scope = item.select_scope or role.select_scope
        for field, label in (("update_scope", "可写"), ("delete_scope", "可删")):
            explicit = getattr(item, field)
            value = explicit or getattr(role, field)
            if scope_covers(read_scope, value):
                continue
            source = "" if explicit is not None else "默认"
            error_message: str = (
                f"保存角色标签范围失败, 标签[tag={tag}]的{label}范围[{source}{value.value}]"
                f"不能大于可见范围[{read_scope.value}], 请显式设置该标签的{label}范围"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def _assert_roles_not_referenced(self, targets: List[Role]) -> None:
        """
        校验角色未被未删除用户绑定。

        krun_user_role 外键为级联删除，删角色会静默清空用户权限，批量删除同样需前置拦截。

        :param targets: 待删除角色列表
        :raises ParameterException: 存在角色仍被用户绑定
        """
        if not targets:
            return
        role_map: Dict[int, Role] = {instance.id: instance for instance in targets}
        bound_role_ids: Set[int] = set()
        users = await User.filter(roles__id__in=list(role_map), state=0).prefetch_related("roles")
        for user in users:
            bound_role_ids.update(role.id for role in user.roles if role.id in role_map)
        if bound_role_ids:
            codes: List[str] = sorted(role_map[rid].code for rid in bound_role_ids)
            error_message: str = f"删除角色信息失败, 角色[code={codes}]已被用户绑定, 请先解除绑定后再删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

    async def delete_role(self, role_id: int, **kwargs) -> Role:
        """
        根据ID物理删除单个角色；管理员角色与仍被用户绑定的角色不允许删除。

        krun_user_role 的外键为级联删除，物理删除角色会顺带清掉绑定行并让在线用户
        静默失去权限，因此必须前置拦截；软删用户的绑定不算引用，随角色删除一并清理。

        :param role_id: 角色ID
        :param kwargs: 额外查询条件
        :return: 被删除的角色实例
        :raises ParameterException: 管理员角色或仍存在未删除用户绑定
        """
        instance = await self.get_by_id(role_id=role_id, on_error=True, **kwargs)
        if instance.code == BuiltinRoleCode.ADMIN.value:
            error_message: str = "删除角色信息失败, 管理员角色不允许删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        user_count: int = await User.filter(roles__id=instance.id, state=0).count()
        if user_count > 0:
            error_message: str = (
                f"删除角色信息失败, 角色[code={instance.code}]已被{user_count}个用户绑定, 请先解除绑定后再删除"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        await instance.delete()
        return instance

    async def delete_roles(self, role_ids: Optional[List[int]] = None, role_codes: Optional[List[str]] = None) -> List:
        """
        根据ID或code列表物理删除角色。

        角色表无 state 字段，批量删除与单删一致为物理删除；删除前逐条校验引用关系，
        存在未删除用户绑定时整体拒绝，避免用户静默失去权限。

        :param role_ids: 角色ID列表
        :param role_codes: 角色编码列表
        :return: 实际删除的角色ID或code列表
        :raises ParameterException: 存在管理员角色被绑定或仍被未删除用户引用
        """
        targets: List[Role] = []
        if role_ids:
            for rid in role_ids:
                instance = await self.get_by_id(role_id=int(rid))
                if not instance:
                    continue
                if instance.code == BuiltinRoleCode.ADMIN.value:
                    LOGGER.warning(f"[角色]管理员角色[id={rid}]不允许删除, 已跳过")
                    continue
                targets.append(instance)
        elif role_codes:
            for code in role_codes:
                instance = await self.get_by_code(role_code=code)
                if not instance:
                    continue
                if instance.code == BuiltinRoleCode.ADMIN.value:
                    LOGGER.warning(f"[角色]管理员角色[code={code}]不允许删除, 已跳过")
                    continue
                targets.append(instance)

        await self._assert_roles_not_referenced(targets)
        async with in_transaction() as conn:
            for instance in targets:
                await instance.delete(using_db=conn)
        if role_ids:
            return [instance.id for instance in targets]
        return [instance.code for instance in targets]
