# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : router_crud.py
@DateTime: 2025/1/31 17:36
"""
import traceback
from typing import Any, Dict, Optional, List, Tuple

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.router_schema import RouterCreate, RouterSelect, RouterUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, NotFoundException, ParameterException

# 路由对外序列化口径: 主键统一为 router_id(前端列表/表单均按该字段取值)
ROUTER_REPLACE_FIELDS: Dict[str, str] = {"id": "router_id"}


class RouterCrud(ScaffoldCrud[Router, RouterCreate, RouterUpdate]):

    def __init__(self):
        super().__init__(model=Router)

    async def get_by_id(self, router_id: int, on_error: bool = True, **kwargs) -> Optional[Router]:
        """
        根据主键ID查询路由。

        :param router_id: 路由ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 路由实例或None
        """
        if not router_id:
            error_message: str = "查询路由信息失败, 参数[router_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.get_or_none(id=router_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询路由信息失败, 记录[id={router_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def serialize_router(instance: Router) -> Dict[str, Any]:
        """
        按路由对外口径序列化，主键对外为router_id。

        :param instance: 路由实例
        :return: 响应字典
        """
        return await instance.to_dict(replace_fields=ROUTER_REPLACE_FIELDS)

    async def select_routers(self, router_in: RouterSelect) -> Tuple[int, List[Router]]:
        """
        按条件分页查询路由列表。

        :param router_in: 路由查询入参
        :return: 记录总数与当前页路由列表
        """
        # path/summary/tags 为包含匹配，method 为枚举等值匹配，created_user/updated_user 为等值匹配
        search = Q()
        if router_in.path:
            search &= Q(path__contains=router_in.path)
        if router_in.method:
            method_value = router_in.method.value if hasattr(router_in.method, "value") else router_in.method
            search &= Q(method=method_value)
        if router_in.summary:
            search &= Q(summary__contains=router_in.summary)
        if router_in.tags:
            search &= Q(tags__contains=router_in.tags)
        if router_in.created_user:
            search &= Q(created_user=router_in.created_user)
        if router_in.updated_user:
            search &= Q(updated_user=router_in.updated_user)
        return await self.list(
            page=router_in.page,
            page_size=router_in.page_size,
            search=search,
            order=router_in.order,
        )

    async def list_permission_keys(self, is_admin: bool, role_ids: List[int]) -> List[str]:
        """
        查询用户可访问的接口权限键。

        :param is_admin: 是否为超管或管理员角色
        :param role_ids: 用户角色ID列表
        :return: 排序后的权限键列表，权限键为方法小写加路由路径
        """
        if is_admin:
            routers: List[Router] = await self.model.all()
        elif role_ids:
            # 多角色接口一次查出并去重，避免按角色逐条查询造成 N+1
            routers = await self.model.filter(role_routers__id__in=role_ids).distinct()
        else:
            routers = []
        return sorted({router.method.lower() + router.path for router in routers})

    async def create_router(self, router_in: RouterCreate) -> Router:
        """
        创建路由：校验path+method唯一性后落库。

        :param router_in: 新增路由入参
        :return: 新建的路由实例
        """
        path = router_in.path
        method = router_in.method
        instances = await self.get_by_conditions(only_one=False, on_error=False, path=path, method=method)
        if instances:
            error_message: str = f"新增路由信息失败, 记录[path={path}, method={method}]信息已存在"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.create(router_in)
        except IntegrityError as e:
            # 并发创建同 method+path：预校验会同时通过，靠唯一索引收敛为业务已存在
            error_message: str = f"新增路由信息失败, 记录[path={path}, method={method}]信息已存在"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e
        return instance

    async def delete_router(self, router_id: int, **kwargs) -> Router:
        """
        根据ID物理删除单个路由。

        :param router_id: 路由ID
        :param kwargs: 额外查询条件
        :return: 被删除的路由实例
        """
        instance = await self.get_by_id(router_id, on_error=True, **kwargs)
        await instance.delete()
        return instance

    async def update_router(self, router_in: RouterUpdate) -> Router:
        """
        根据路由ID更新路由字段。

        :param router_in: 更新入参
        :return: 更新后的路由实例
        """
        router_id: int = router_in.id
        router_if: dict = router_in.model_dump(exclude_none=True)
        try:
            instance = await self.update(id=router_id, obj_in=router_if)
        except IntegrityError as e:
            # 并发改名/改路径撞唯一索引与创建同口径，返回已存在而非服务异常
            error_message: str = f"更新路由信息失败, 记录[id={router_id}]与已有[path+method]冲突"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataAlreadyExistsException(message=error_message) from e

        return instance

    async def refresh_router(self, app: FastAPI, sync_role_bindings: bool = True) -> List[Router]:
        """
        根据FastAPI应用当前路由同步数据库：只收录需要 RBAC 的接口，
        删除废弃项并清理角色绑定，新增或更新现有项，最后按规则为内置角色补绑路由。

        :param app: FastAPI应用实例
        :param sync_role_bindings: 是否按权限规则补绑角色路由（不触碰角色菜单人工配置）
        :return: 同步后的全部路由列表
        """
        from backend.core.initializations.permission_contract import AUTH_MODE_PERMISSION

        # 只收录需要 RBAC 的路由；公开与仅认证接口不进入权限体系
        contracts = []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if getattr(route, "auth_mode", None) != AUTH_MODE_PERMISSION:
                continue
            methods = [method for method in route.methods if method not in ("OPTIONS", "HEAD")]
            if not methods or route.path_format == "/":
                continue
            contracts.append((methods[0], route.path_format, route))

        valid_keys = {(method, path) for method, path, _ in contracts}

        # 一次查回全量路由并按method+path建索引，废弃项与更新项批量处理，避免循环内查库
        existing_map: Dict[Tuple[str, str], Router] = {
            (router.method.value, router.path): router for router in await self.model.all()
        }
        obsolete_ids: List[int] = [
            router.id for key, router in existing_map.items() if key not in valid_keys
        ]

        updated_rows: List[Router] = []
        created_rows: List[Router] = []
        for method, path, route in contracts:
            data = {
                'path': path,
                'method': method,
                'summary': route.summary,
                'tags': ','.join(list(route.tags or [])),
                'description': route.description,
                'available_only_admin': bool(getattr(route, "available_only_admin", False))
            }
            target = existing_map.get((method, path))
            if target:
                for field, value in data.items():
                    setattr(target, field, value)
                updated_rows.append(target)
            else:
                created_rows.append(self.model(**data))

        # 同事务提交删除与写入：krun_role_routers 外键为级联删除，废弃路由的绑定行由数据库自动清理
        async with in_transaction() as conn:
            if obsolete_ids:
                await self.model.filter(id__in=obsolete_ids).using_db(conn).delete()
                for router_id in obsolete_ids:
                    LOGGER.info(f"[路由刷新]删除废弃路由[id={router_id}]")
            for target in updated_rows:
                await target.save(using_db=conn)
            for new_router in created_rows:
                await new_router.save(using_db=conn)

        routers = await self.model.all()
        if sync_role_bindings:
            from backend.applications.base.services.permission_rule import PermissionRule
            await PermissionRule.sync_role_permission_bindings(routers=routers)
        return routers
