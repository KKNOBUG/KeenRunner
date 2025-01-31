# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_crud.py
@DateTime: 2025/1/31 17:36
"""
from typing import Optional, List, Dict, Union

from backend.applications.base.models.api_model import Api
from backend.applications.base.schemas.api_schema import ApiCreate, ApiUpdate
from backend.core.exceptions.base_exceptions import ParameterException
from backend.services.base_crud import BaseCrud


class ApiCrud(BaseCrud[Api, ApiCreate, ApiUpdate]):
    def __init__(self):
        super().__init__(model=Api)

    async def get_by_id(self, api_id: int) -> Optional[Api]:
        return await self.model.filter(id=api_id).first()

    async def get_by_path(self, path: Optional[str] = None, method: Optional[str] = None) -> Optional[List[Api]]:
        if not path and not method:
            raise ParameterException(message="path和method参数不可同时为空")

        where: Dict[str, Union[str, int]] = {}
        if path:
            where["path"] = path
        if method:
            where["method"] = method

        return await self.model.filter(**where).all()

    async def get_by_tags(self, tags: str) -> Optional[List[Api]]:
        return await self.model.filter(tags=tags).all()

    async def create_api(self, api_in: ApiCreate) -> Api:
        api_instance = await self.create(api_in)
        return api_instance

    async def delete_api(self, api_in: int) -> Api:
        api_instance = await self.get(api_in)
        api_instance.is_active = 0
        await api_instance.save()
        return api_instance

    async def update_api(self, api_in: ApiUpdate) -> Api:
        api_id: int = api_in.id
        api_if: dict = {
            key: value for key, value in api_in.items()
            if value is not None
        }
        api_instance = await self.update(id=api_id, obj_in=api_if)
        api_data = await api_instance.to_dict()
        return api_data


API_CRUD = ApiCrud()
