# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : router_crud.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.router_schema import RouterCreate, RouterUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class RouterCrud(ScaffoldCrud[Router, RouterCreate, RouterUpdate]):
    def __init__(self):
        super().__init__(model=Router)

    async def get_by_id(self, router_id: int) -> Optional[Router]:
        return await self.model.filter(id=router_id).first()

    async def get_by_path(self, path: str) -> Optional[List[Router]]:
        return await self.model.filter(path=path).all()

    async def get_by_method(self, method: str) -> Optional[List[Router]]:
        return await self.model.filter(method=method).all()

    async def get_by_summary(self, summary: str) -> Optional[List[Router]]:
        return await self.model.filter(summary=summary).all()

    async def get_by_tags(self, tags: str) -> Optional[List[Router]]:
        return await self.model.filter(tags=tags).all()

    async def create_router(self, router_in: RouterCreate) -> Router:
        path = router_in.path
        method = router_in.method
        instances = await self.model.filter(path=path, method=method).all()
        if instances:
            raise DataAlreadyExistsException(message=f"接口(path={path},method={method})信息已存在")

        instance = await self.create(router_in)
        return instance

    async def delete_router(self, router_id: int) -> Router:
        instance = await self.query(router_id)
        if not instance:
            raise NotFoundException(message=f"接口(id={router_id})信息不存在")

        await instance.delete()
        data = await instance.to_dict()
        return data

    async def update_router(self, router_in: RouterUpdate) -> Router:
        router_id: int = router_in.id
        router_if: dict = {
            key: value for key, value in router_in.dict().items()
            if value is not None
        }
        try:
            instance = await self.update(id=router_id, obj_in=router_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"接口(id={router_id})信息不存在")

        return instance

    async def refresh_router(self, app: FastAPI) -> Optional[List[Router]]:
        # 获取全部路由数据
        all_router_list = []
        for route in app.routes:
            # 只更新有鉴权的路由
            if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
                all_router_list.append((list(route.methods)[0], route.path_format))

        # 删除废弃路由数据
        for router in await self.model.all():
            if (router.method, router.path) not in all_router_list:
                await self.model.filter(method=router.method, path=router.path).delete()

        # 更新路由数据
        for route in app.routes:
            if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
                data = {
                    'path': route.path_format,
                    'method': list(route.methods)[0],
                    'summary': route.summary,
                    'tags': ','.join(list(route.tags)),
                    'description': route.description
                }
                instance = await self.model.filter(method=data["method"], path=data["path"]).first()
                if instance:
                    await instance.update_from_dict(data).save()
                else:
                    await self.model.create(**data)

        return await self.model.all()


ROUTER_CRUD = RouterCrud()
