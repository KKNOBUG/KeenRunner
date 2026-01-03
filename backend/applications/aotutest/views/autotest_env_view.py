# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_view
@DateTime: 2026/1/2 21:21
"""
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_CRUD
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvSelect
)
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException, DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    ParameterResponse,
    NotFoundResponse, DataBaseStorageResponse
)

autotest_env = APIRouter()


@autotest_env.post("/create", summary="API自动化测试-新增环境")
async def create_env_info(env_in: AutoTestApiEnvCreate = Body(..., description="环境信息")):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.create_env(env_in=env_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "env_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_env.post("/delete", summary="API自动化测试-按id或code删除环境")
async def delete_env_info(
        env_id: Optional[int] = Query(..., description="环境ID"),
        env_code: Optional[str] = Query(..., description="环境标识代码"),
):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.delete_env(env_id=env_id, env_code=env_code)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "env_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_env.post("/update", summary="API自动化测试-按id或code更新环境")
async def update_env_info(env_in: AutoTestApiEnvUpdate = Body(..., description="环境信息")):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.update_env(env_in=env_in)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "env_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"更新失败, 异常描述: {e}")


@autotest_env.get("/get", summary="API自动化测试-按id或code查询环境")
async def get_env_info(
        env_id: Optional[int] = Query(..., description="环境ID"),
        env_code: Optional[str] = Query(..., description="环境标识代码"),
):
    try:
        if env_id:
            instance = await AUTOTEST_API_ENV_CRUD.get_by_id(env_id=env_id, on_error=True)
        else:
            instance = await AUTOTEST_API_ENV_CRUD.get_by_code(env_code=env_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
            replace_fields={"id": "env_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_env.post("/search", summary="API自动化测试-按条件查询环境")
async def search_env_info(env_in: AutoTestApiEnvSelect = Body(..., description="查询条件")):
    try:
        q = Q()
        if env_in.env_id:
            q &= Q(id=env_in.env_id)
        if env_in.env_code:
            q &= Q(env_code__contains=env_in.env_code)
        if env_in.project_id:
            q &= Q(project_id=env_in.project_id)
        if env_in.env_name:
            q &= Q(env_name__contains=env_in.env_name)
        if env_in.env_host:
            q &= Q(env_host__contains=env_in.env_host)
        if env_in.created_user:
            q &= Q(created_user__iexact=env_in.created_user)
        if env_in.updated_user:
            q &= Q(updated_user__iexact=env_in.updated_user)
        q &= Q(state=env_in.state)
        total, instances = await AUTOTEST_API_ENV_CRUD.select_envs(
            search=q,
            page=env_in.page,
            page_size=env_in.page_size,
            order=env_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={"state", "created_user", "updated_user", "created_time", "updated_time"},
                replace_fields={"id": "env_id"}
            )
            for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败, 异常描述: {e}")
