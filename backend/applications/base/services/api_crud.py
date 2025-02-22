# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_crud.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.api_model import Api
from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class ApiCrud(ScaffoldCrud[Api, ApiCreate, ApiUpdate]):
    def __init__(self):
        super().__init__(model=Api)

    async def get_by_id(self, api_id: int) -> Optional[Api]:
        return await self.model.filter(id=api_id).first()

    async def get_by_path(self, path: str) -> Optional[List[Api]]:
        return await self.model.filter(path=path).all()

    async def get_by_method(self, method: str) -> Optional[List[Api]]:
        return await self.model.filter(method=method).all()

    async def get_by_summary(self, summary: str) -> Optional[List[Api]]:
        return await self.model.filter(summary=summary).all()

    async def get_by_tags(self, tags: str) -> Optional[List[Api]]:
        return await self.model.filter(tags=tags).all()

    async def create_api(self, api_in: ApiCreate) -> Api:
        path = api_in.path
        method = api_in.method
        instances = await self.model.filter(path=path, method=method).all()
        if instances:
            raise DataAlreadyExistsException(message=f"接口(path={path},method={method})信息已存在")

        instance = await self.create(api_in)
        return instance

    async def delete_api(self, api_id: int) -> Api:
        instance = await self.query(api_id)
        if not instance:
            raise NotFoundException(message=f"接口(id={api_id})信息不存在")

        await instance.delete()
        data = await instance.to_dict()
        return data

    async def update_api(self, api_in: ApiUpdate) -> Api:
        api_id: int = api_in.id
        api_if: dict = {
            key: value for key, value in api_in.dict().items()
            if value is not None
        }
        try:
            instance = await self.update(id=api_id, obj_in=api_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"接口(id={api_id})信息不存在")

        return instance

    async def refresh_api(self, app: FastAPI) -> Optional[List[Api]]:
        # 获取全部API数据
        all_api_list = []
        for route in app.routes:
            # 只更新有鉴权的API
            # if isinstance(route, APIRoute) and len(route.dependencies) > 0:
            if isinstance(route, APIRoute) and route.methods not in ("OPTIONS",) and route.path_format not in ('/',):
                all_api_list.append((list(route.methods)[0], route.path_format))

        # 删除废弃API数据
        for api in await self.model.all():
            if (api.method, api.path) not in all_api_list:
                await self.model.filter(method=api.method, path=api.path).delete()

        # 更新API数据
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


API_CRUD = ApiCrud()
