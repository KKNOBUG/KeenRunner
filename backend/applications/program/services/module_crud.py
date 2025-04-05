# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : module_crud.py
@DateTime: 2025/4/5 12:39
"""
from typing import Optional, List, Dict

from tortoise.exceptions import DoesNotExist

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.program.models.module_model import Module
from backend.applications.program.schemas.module_schema import ModuleCreate, ModuleUpdate
from backend.applications.program.services.project_crud import PROJECT_CRUD
from backend.applications.user.models.user_model import User
from backend.applications.user.services.user_crud import USER_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class ModuleCrud(ScaffoldCrud[Module, ModuleCreate, ModuleUpdate]):
    def __init__(self):
        super().__init__(model=Module)

    async def get_by_id(self, module_id: int) -> Optional[Module]:
        return await self.model.filter(id=module_id).first()

    async def get_by_code(self, code: str) -> Optional[Module]:
        return await self.model.filter(code=code).first()

    async def get_by_name(self, name: str) -> Optional[Module]:
        return await self.model.filter(name=name).first()

    async def get_by_created_user(self, user: str) -> Optional[List[Module]]:
        return await self.model.filter(user=user).all()

    async def get_by_updated_user(self, user: str) -> Optional[List[Module]]:
        return await self.model.filter(user=user).all()

    async def get_by_dev_owner_id(self, dev_owner_id: int) -> Optional[List[Module]]:
        return await self.model.filter(dev_owner_id=dev_owner_id).all()

    async def get_by_test_owner_id(self, test_owner_id: int) -> Optional[List[Module]]:
        return await self.model.filter(test_owner_id=test_owner_id).all()

    async def get_by_project_id(self, project_id: int) -> Optional[List[Module]]:
        return await self.model.filter(project_id=project_id).all()

    async def create_module(self, module_in: ModuleCreate) -> Module:
        code = module_in.code
        name = module_in.name
        dev_owner_id = module_in.dev_owner
        test_owner_id = module_in.test_owner
        project_id = module_in.project
        instances = await self.model.filter(code=code, name=name).all()
        if instances:
            raise DataAlreadyExistsException(message=f"模块(code={code},name={name})信息已存在")

        # 查询负责人
        owner_instances = await USER_CRUD.model.filter(id__in=[dev_owner_id, test_owner_id]).all()
        owner_dict: Dict[int, User] = {user.id: user for user in owner_instances}
        # 验证负责人
        dev_owner_instance: User = owner_dict.get(dev_owner_id)
        test_owner_instance: User = owner_dict.get(test_owner_id)
        if not dev_owner_instance or not test_owner_instance:
            raise NotFoundException(message=f"用户(id={dev_owner_id or test_owner_id}信息不存在)")

        # 关联负责人
        module_in.dev_owner = dev_owner_instance
        module_in.test_owner = test_owner_instance

        # 查询项目
        project_instance = await PROJECT_CRUD.get_by_id(project_id=project_id)
        if not project_instance:
            raise NotFoundException(message=f"项目(id={project_id}信息不存在)")

        # 关联项目
        module_in.project = project_instance
        instance = await self.create(module_in)

        return instance

    async def delete_module(self, module_id: int) -> Module:
        instance = await self.query(module_id)
        if not instance:
            raise NotFoundException(message=f"模块(id={module_id})信息不存在")

        await instance.delete()
        return instance

    async def update_module(self, module_in: ModuleUpdate) -> Module:
        module_id = module_in.id

        # 查询负责人
        dev_owner_id = module_in.dev_owner
        test_owner_id = module_in.test_owner
        owner_instances = await USER_CRUD.model.filter(id__in=[dev_owner_id, test_owner_id]).all()
        owner_dict: Dict[int, User] = {user.id: user for user in owner_instances}

        # 验证负责人
        dev_owner_instance: User = owner_dict.get(dev_owner_id)
        test_owner_instance: User = owner_dict.get(test_owner_id)
        if not dev_owner_instance or not test_owner_instance:
            raise NotFoundException(message=f"用户(id={dev_owner_id or test_owner_id}信息不存在)")

        # 关联负责人
        module_if: dict = {
            key: value for key, value in module_in.dict().items()
            if value is not None
        }
        module_if["dev_owner"] = dev_owner_instance
        module_if["test_owner"] = test_owner_instance

        # 查询项目
        project_id = module_in.project
        if project_id:
            project_instance = await PROJECT_CRUD.get_by_id(project_id=project_id)
            if not project_instance:
                raise NotFoundException(message=f"项目(id={project_id}信息不存在)")
            # 关联项目
            module_if["project"] = project_instance

        try:
            instance = await self.update(id=module_id, obj_in=module_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"模块(id={module_id})信息不存在")

        return instance


MODULE_CRUD = ModuleCrud()
