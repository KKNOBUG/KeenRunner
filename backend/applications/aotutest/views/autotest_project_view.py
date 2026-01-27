# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_view
@DateTime: 2026/1/2 21:37
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_project_schema import (
    AutoTestApiProjectCreate,
    AutoTestApiProjectUpdate,
    AutoTestApiProjectSelect
)
from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse,
)

autotest_project = APIRouter()


@autotest_project.post("/create", summary="API自动化测试-新增应用")
async def create_project_info(project_in: AutoTestApiProjectCreate = Body(..., description="应用信息")):
    try:
        instance = await AUTOTEST_API_PROJECT_CRUD.create_project(project_in=project_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        LOGGER.info(f"新增应用成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_project.post("/delete", summary="API自动化测试-按id或code删除应用")
async def delete_project_info(
        project_id: Optional[int] = Query(..., description="应用ID"),
        project_code: Optional[str] = Query(..., description="应用标识代码"),
):
    try:
        instance = await AUTOTEST_API_PROJECT_CRUD.delete_project(project_id=project_id, project_code=project_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        LOGGER.info(f"按id或code删除应用成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_project.post("/update", summary="API自动化测试-按id或code更新应用")
async def update_project_info(project_in: AutoTestApiProjectUpdate = Body(..., description="应用信息")):
    try:
        instance = await AUTOTEST_API_PROJECT_CRUD.update_project(project_in=project_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        LOGGER.info(f"按id或code更新应用成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败, 异常描述: {e}")


@autotest_project.get("/get", summary="API自动化测试-按id或code查询应用")
async def get_project_info(
        project_id: Optional[int] = Query(..., description="应用ID"),
        project_code: Optional[str] = Query(..., description="应用标识代码"),
):
    try:
        if project_id:
            instance = await AUTOTEST_API_PROJECT_CRUD.get_by_id(project_id=project_id, on_error=True)
        else:
            instance = await AUTOTEST_API_PROJECT_CRUD.get_by_code(project_code=project_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        LOGGER.info(f"按id或code查询应用成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_project.post("/search", summary="API自动化测试-按条件查询应用")
async def search_project_info(project_in: AutoTestApiProjectSelect = Body(..., description="查询条件")):
    try:
        q = Q()
        if project_in.project_id:
            q &= Q(id=project_in.project_id)
        if project_in.project_code:
            q &= Q(project_code=project_in.project_code)
        if project_in.project_state:
            q &= Q(project_state__contains=project_in.project_state)
        if project_in.project_phase:
            q &= Q(project_phase__contains=project_in.project_phase)
        if project_in.project_dev_owners:
            q &= Q(project_dev_owners__contains=project_in.project_dev_owners)
        if project_in.project_test_owners:
            q &= Q(project_test_owners__contains=project_in.project_test_owners)
        if project_in.created_user:
            q &= Q(created_user__contains=project_in.created_user)
        if project_in.updated_user:
            q &= Q(updated_user__contains=project_in.updated_user)
        q &= Q(state=project_in.state)
        total, instances = await AUTOTEST_API_PROJECT_CRUD.select_projects(
            search=q,
            page=project_in.page,
            page_size=project_in.page_size,
            order=project_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "project_id"}
            )
            for obj in instances
        ]
        LOGGER.info(f"按条件查询应用成功, 结果明细: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")
