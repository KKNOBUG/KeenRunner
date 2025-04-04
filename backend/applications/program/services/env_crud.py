# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : env_crud.py
@DateTime: 2025/4/2 19:40
"""
from typing import Optional, List, Dict

from tortoise.exceptions import DoesNotExist

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.program.models.env_model import Environment
from backend.applications.program.models.project_model import Project
from backend.applications.program.schemas.env_schema import EnvCreate, EnvUpdate
from backend.applications.program.services.project_crud import PROJECT_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class EnvCrud(ScaffoldCrud[Environment, EnvCreate, EnvUpdate]):
    def __init__(self):
        super().__init__(model=Environment)

    async def get_by_id(self, env_id: int) -> Optional[Environment]:
        return await self.model.filter(id=env_id).first()

    async def get_by_name(self, name: str) -> Optional[Environment]:
        return await self.model.filter(name=name).first()

    async def get_by_host(self, host: str) -> Optional[List[Environment]]:
        return await self.model.filter(host=host).first()

    async def get_by_port(self, port: int) -> Optional[List[Environment]]:
        return await self.model.filter(port=int).first()

    async def create_env(self, env_in: EnvCreate) -> Environment:
        name = env_in.name
        project_id = env_in.project_id

        # 1. 检查环境名称是否存在
        if await self.get_by_name(name=name):
            raise DataAlreadyExistsException(message=f"环境(name={name})已存在")

        # 2. 检查项目是否存在（补充await）
        if not await PROJECT_CRUD.get_by_id(project_id=project_id):
            raise NotFoundException(message=f"项目(id={project_id})不存在")

        # 3. 转换字段名以适配ORM外键（project -> project_id）
        # create_data = env_in.model_dump()
        # create_data["project_id"] = create_data.pop("project")

        # 4. 创建环境记录（确保使用await调用异步方法）
        instance = await ENV_CRUD.create(env_in)
        return instance

    async def delete_env(self, env_id: int) -> Environment:
        instance = await self.query(env_id)
        if not instance:
            raise NotFoundException(message=f"环境(id={env_id})信息不存在")

        await instance.delete()
        data = await instance.to_dict()
        return data

    async def update_env(self, env_in: EnvUpdate) -> Environment:
        env_id: int = env_in.id
        env_if: dict = {
            key: value for key, value in env_in.dict().items()
            if value is not None
        }
        try:
            instance = await self.update(id=env_id, obj_in=env_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"环境(id={env_in})信息不存在")

        return instance


ENV_CRUD = EnvCrud()
