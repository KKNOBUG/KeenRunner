# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : project_crud.py
@DateTime: 2025/2/2 13:37
"""
from typing import Optional, List

from backend.applications.project.models.project_model import Project
from backend.applications.project.schemas.project_schema import ProjectCreate, ProjectUpdate
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
        project_instance = await self.create(project_in)
        return project_instance

    async def delete_project(self, project_id: int) -> Project:
        project_instance = await self.get(project_id)
        project_instance.is_active = 0
        await project_instance.save()
        return project_instance

    async def update_project(self, project_in: ProjectUpdate) -> Project:
        project_id: int = project_in.id
        project_if: dict = {
            key: value for key, value in project_in.items()
            if value is not None
        }
        project_instance = await self.update(id=project_id, obj_in=project_if)
        project_data = await project_instance.to_dict()
        return project_data


PROJECT_CRUD = ProjectCrud()
