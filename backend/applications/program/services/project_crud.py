# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_crud.py
@DateTime: 2025/3/15 15:18
"""
from typing import Optional, List, Dict

from tortoise.exceptions import DoesNotExist

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.program.models.env_model import Environment
from backend.applications.program.models.project_model import Project
from backend.applications.program.schemas.env_schema import EnvCreate, EnvUpdate
from backend.applications.program.schemas.project_schema import ProjectCreate, ProjectUpdate
from backend.applications.user.models.user_model import User
from backend.applications.user.services.user_crud import USER_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class ProjectCrud(ScaffoldCrud[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self):
        super().__init__(model=Project)

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        return await self.model.filter(id=project_id).first()

    async def get_by_code(self, code: str) -> Optional[Project]:
        return await self.model.filter(code=code).first()

    async def get_by_name(self, name: str) -> Optional[Project]:
        return await self.model.filter(name=name).first()

    async def create_project(self, project_in: ProjectCreate) -> Project:
        code = project_in.code
        name = project_in.name
        dev_owner = project_in.dev_owner
        test_owner = project_in.test_owner
        environments = project_in.environments
        instances = await self.model.filter(code=code, name=name).all()
        if instances:
            raise DataAlreadyExistsException(message=f"项目(code={code},name={name})信息已存在")

        # 查询负责人
        owner_instances = await USER_CRUD.model.filter(id__in=[dev_owner, test_owner]).all()
        owner_dict: Dict[int, User] = {user.id: user for user in owner_instances}
        # 验证负责人
        dev_owner_instance: User = owner_dict.get(dev_owner)
        test_owner_instance: User = owner_dict.get(test_owner)
        if not dev_owner_instance or not test_owner_instance:
            raise NotFoundException(message=f"用户(id={dev_owner or test_owner}信息不存在)")
        # 关联负责人
        project_in.dev_owner = dev_owner_instance
        project_in.test_owner = test_owner_instance
        instance = await self.create(project_in)

        # 关联环境
        if environments:
            env_instances = []
            for env in environments:
                env.project_id = instance.id
                env_obj = Environment(**env.create_dict())
                env_instances.append(env_obj)
            await Environment.bulk_create(objects=env_instances)

        return instance

    async def delete_project(self, project_id: int) -> Project:
        instance = await self.query(project_id)
        if not instance:
            raise NotFoundException(message=f"项目(id={project_id})信息不存在")

        await instance.delete()
        return instance

    async def update_project(self, project_in: ProjectUpdate) -> Project:
        project_id: int = project_in.id
        dev_owner = project_in.dev_owner
        test_owner = project_in.test_owner
        project_if: dict = {
            key: value for key, value in project_in.dict().items()
            if value is not None
        }
        # 查询负责人
        owner_instances = await USER_CRUD.model.filter(id__in=[dev_owner, test_owner]).all()
        owner_dict: Dict[int, User] = {user.id: user for user in owner_instances}
        # 验证负责人
        dev_owner_instance: User = owner_dict.get(dev_owner)
        test_owner_instance: User = owner_dict.get(test_owner)
        if not dev_owner_instance or not test_owner_instance:
            raise NotFoundException(message=f"用户(id={dev_owner or test_owner}信息不存在)")
        # 关联负责人
        project_if["dev_owner"] = dev_owner_instance
        project_if["test_owner"] = test_owner_instance

        # 处理环境配置更新
        if project_in.environments:
            # 假设 Project 模型有一个方法来更新环境配置
            await self._update_environments(project_id, project_in.environments)

        try:
            instance = await self.update(id=project_id, obj_in=project_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"项目(id={project_id})信息不存在")

        return instance

    @classmethod
    async def _update_environments(cls, project_id: int, environments: List[EnvUpdate]):
        project = await Project.filter(id=project_id).first()
        if not project:
            raise NotFoundException(message=f"项目(id={project_id})信息不存在")

        # 获取项目现有的环境配置
        existing_envs = await Environment.filter(project=project).all()
        existing_env_ids = [env.id for env in existing_envs]

        # 存储新环境配置的名称，用于后续删除多余的环境配置
        new_env_names = []

        for env in environments:
            # 检查是否存在同名的环境配置
            existing_env = next((e for e in existing_envs if e.name == env.name), None)
            new_env_names.append(env.name)

            if existing_env:
                # 如果存在，更新该环境配置
                existing_env.host = env.host
                existing_env.port = env.port
                existing_env.description = env.description
                await existing_env.save()
            else:
                # 如果不存在，创建新的环境配置
                await Environment.create(
                    name=env.name,
                    host=env.host,
                    port=env.port,
                    description=env.description,
                    project=project
                )

        # 删除新配置中不存在的环境配置
        for env in existing_envs:
            if env.name not in new_env_names:
                await env.delete()


PROJECT_CRUD = ProjectCrud()
