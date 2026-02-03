# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_view
@DateTime: 2026/1/2 21:21
"""
import traceback
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvSelect
)
from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_CRUD
from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException, DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse
)

autotest_env = APIRouter()


@autotest_env.post("/create", summary="API自动化测试-新增环境")
async def create_env_info(env_in: AutoTestApiEnvCreate = Body(..., description="环境信息")):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.create_env(env_in=env_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"新增环境成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_env.delete("/delete", summary="API自动化测试-按id或code删除环境")
async def delete_env_info(
        env_id: Optional[int] = Query(None, description="环境ID"),
        env_code: Optional[str] = Query(None, description="环境标识代码"),
):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.delete_env(env_id=env_id, env_code=env_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"按id或code删除环境成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_env.post("/update", summary="API自动化测试-按id或code更新环境")
async def update_env_info(env_in: AutoTestApiEnvUpdate = Body(..., description="环境信息")):
    try:
        instance = await AUTOTEST_API_ENV_CRUD.update_env(env_in=env_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"按id或code更新环境成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败, 异常描述: {e}")


@autotest_env.get("/get", summary="API自动化测试-按id或code查询环境")
async def get_env_info(
        env_id: Optional[int] = Query(None, description="环境ID"),
        env_code: Optional[str] = Query(None, description="环境标识代码"),
):
    try:
        if env_id:
            instance = await AUTOTEST_API_ENV_CRUD.get_by_id(env_id=env_id, on_error=True)
        else:
            instance = await AUTOTEST_API_ENV_CRUD.get_by_code(env_code=env_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"按id或code查询环境成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_env.get("/get", summary="API自动化测试-查询环境名称(去重)")
async def get_env_info():
    try:
        names: List[str] = await AUTOTEST_API_ENV_CRUD.model.filter(
            tate__not=1).distinct().values_list("env_name", flat=True)
        LOGGER.info(f"查询环境名称(去重)成功, 结果明细: {names}")
        return SuccessResponse(message="查询成功", data=names, total=len(names))
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询环境名称(去重)环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_env.post("/search", summary="API自动化测试-按条件查询环境")
async def search_env_info(env_in: AutoTestApiEnvSelect = Body(..., description="查询条件")):
    try:
        q = Q()
        if env_in.env_id:
            q &= Q(id=env_in.env_id)
        if env_in.env_code:
            q &= Q(env_code=env_in.env_code)
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
        env_serializes: List[Dict[str, Any]] = []
        for instance in instances:
            serialize: Dict[str, Any] = await instance.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "updated_user",
                    "created_time", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "env_id"}
            )
            project_id: int = serialize["project_id"]
            project_instance = await AUTOTEST_API_PROJECT_CRUD.model.filter(
                id=project_id,
            ).first().values("project_name")
            serialize["project_name"] = project_instance["project_name"]
            env_serializes.append(serialize)
        LOGGER.info(f"按条件查询环境成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=env_serializes, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")
