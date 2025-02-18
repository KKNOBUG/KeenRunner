# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_crud.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List

from tortoise.exceptions import DoesNotExist

from backend.applications.base.models.api_model import Api
from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.services.base_crud import BaseCrud


class ApiCrud(BaseCrud[Api, ApiCreate, ApiUpdate]):
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
        instances = self.model.filter(path=path, method=method).all()
        if instances:
            raise DataAlreadyExistsException(message=f"接口(path={path},method={method})信息已存在")

        instance = await self.create(api_in)
        return instance

    async def delete_api(self, api_id: int) -> Api:
        instance = await self.select(api_id)
        if not instance:
            raise NotFoundException(message=f"接口(id={api_id})信息不存在")

        instance.is_active = 1
        await instance.save()
        return instance

    async def update_api(self, api_in: ApiUpdate) -> Api:
        api_id: int = api_in.id
        api_if: dict = {
            key: value for key, value in api_in.items()
            if value is not None
        }
        try:
            instance = await self.update(id=api_id, obj_in=api_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"接口(id={api_id})信息不存在")

        data = await instance.to_dict()
        return data


API_CRUD = ApiCrud()
