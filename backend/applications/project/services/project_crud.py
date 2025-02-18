# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_crud.py
@DateTime: 2025/2/2 13:37
"""
from typing import Optional, List

from tortoise.exceptions import DoesNotExist

from backend.applications.project.models.project_model import Project
from backend.applications.project.schemas.project_schema import ProjectCreate, ProjectUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.services.base_crud import BaseCrud


class ProjectCrud(BaseCrud[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self):
        super().__init__(model=Project)

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        return await self.model.filter(id=project_id).first()

    async def get_by_name(self, name: str) -> Optional[Project]:
        return await self.model.filter(name=name).first()

    async def get_by_initiator(self, initiator: str) -> Optional[List[Project]]:
        return await self.model.filter(initiator=initiator).all()

    async def get_by_created_user(self, created_user: str) -> Optional[List[Project]]:
        return await self.model.filter(created_user=created_user).all()

    async def create_project(self, project_in: ProjectCreate) -> Project:
        name = project_in.name
        initiator = project_in.initiator
        instances = self.model.filter(name=name, initiator=initiator).all()
        if instances:
            raise DataAlreadyExistsException(message=f"项目(name={name},initiator={initiator})信息已存在")

        instance = await self.create(project_in)
        return instance

    async def delete_project(self, project_id: int) -> Project:
        instance = await self.get(project_id)
        if not instance:
            raise NotFoundException(message=f"项目(id={project_id})信息不存在")

        instance.is_deleted = 1
        await instance.save()
        return instance

    async def update_project(self, project_in: ProjectUpdate) -> Project:
        project_id: int = project_in.id
        project_if: dict = {
            key: value for key, value in project_in.items()
            if value is not None
        }
        try:
            instance = await self.update(id=project_id, obj_in=project_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"项目(id={project_id})信息不存在")

        data = await instance.to_dict()
        return data


PROJECT_CRUD = ProjectCrud()
