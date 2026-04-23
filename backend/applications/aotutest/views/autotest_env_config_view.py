# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_env_config_view
@DateTime: 2026/4/16 15:54
"""
import asyncio
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiConfigCreate,
    AutoTestApiConfigUpdate,
    AutoTestApiConfigSelect,
    AutoTestApiConfigDelete
)
from backend.applications.aotutest.services.autotest_env_config_crud import AUTOTEST_API_ENV_CONFIG_CRUD
from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_ENUM_CRUD
from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    DataBaseStorageResponse
)

autotest_env_config = APIRouter()


@autotest_env_config.post("/create", summary="API自动化测试-新增环境配置")
async def create_env_config(config_in: AutoTestApiConfigCreate = Body(..., description="环境配置")):
    try:
        instance = await AUTOTEST_API_ENV_CONFIG_CRUD.create_config(config_in=config_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "config_id"}
        )
        LOGGER.info(f"新增环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="新增配置成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败, 异常描述: {e}")


@autotest_env_config.delete("/delete", summary="API自动化测试-按id或code删除环境配置")
async def delete_env_config(
        config_id: Optional[int] = Query(None, description="环境配置ID"),
        config_code: Optional[str] = Query(None, description="环境配置标识代码"),
):
    try:
        instance = await AUTOTEST_API_ENV_CONFIG_CRUD.delete_config(config_id=config_id, config_code=config_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "config_id"}
        )
        LOGGER.info(f"按id或code删除环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code删除环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_env_config.post("/delete", summary="API自动化测试-按id或code列表删除环境")
async def delete_env_config_batch(
        config_in: AutoTestApiConfigDelete = Body(..., description="环境配置信息"),
):
    try:
        count = await AUTOTEST_API_ENV_CONFIG_CRUD.delete_configs(config_in=config_in)
        LOGGER.info(f"按id或code列表删除环境配置成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception as e:
        LOGGER.error(f"按id或code列表删除环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败, 异常描述: {e}")


@autotest_env_config.post("/update", summary="API自动化测试-按id或code更新环境配置")
async def update_env_config(config_in: AutoTestApiConfigUpdate = Body(..., description="环境配置")):
    try:
        instance = await AUTOTEST_API_ENV_CONFIG_CRUD.update_config(config_in=config_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"按id或code更新环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except (DataAlreadyExistsException, DataBaseStorageException) as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code更新环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败, 异常描述: {e}")


@autotest_env_config.get("/get", summary="API自动化测试-按id或code查询环境配置")
async def get_env_info(
        config_id: Optional[int] = Query(None, description="环境配置ID"),
        config_code: Optional[str] = Query(None, description="环境配置标识代码"),
):
    try:
        if config_id:
            instance = await AUTOTEST_API_ENV_CONFIG_CRUD.get_by_id(config_id=config_id, on_error=True)
        else:
            instance = await AUTOTEST_API_ENV_CONFIG_CRUD.get_by_code(config_code=config_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "env_id"}
        )
        LOGGER.info(f"按id或code查询环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except (NotFoundException, ParameterException) as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按id或code查询环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_env_config.post("/search", summary="API自动化测试-按条件查询环境配置")
async def search_env_info(config_in: AutoTestApiConfigSelect = Body(..., description="查询条件")):
    try:
        q = Q()
        if config_in.config_id:
            q &= Q(id=config_in.config_id)
        if config_in.config_code:
            q &= Q(config_code=config_in.config_code)
        if config_in.env_id:
            q &= Q(env_id=config_in.env_id)
        if config_in.project_id:
            q &= Q(project_id=config_in.project_id)
        if config_in.config_name:
            q &= Q(config_name__contains=config_in.config_name)
        if config_in.config_type:
            q &= Q(config_type=config_in.config_type.value)
        if config_in.database_type:
            q &= Q(database_type=config_in.database_type.value)
        if config_in.created_user:
            q &= Q(created_user__iexact=config_in.created_user)
        if config_in.updated_user:
            q &= Q(updated_user__iexact=config_in.updated_user)
        q &= Q(state=config_in.state)
        total, instances = await AUTOTEST_API_ENV_CONFIG_CRUD.select_config(
            search=q,
            page=config_in.page,
            page_size=config_in.page_size,
            order=config_in.order
        )
        project_ids = [obj.project_id for obj in instances]
        unique_project_ids = list(set(project_ids))
        project_name_map = {}
        if unique_project_ids:
            project_name_map = dict(
                await AUTOTEST_API_PROJECT_CRUD.model.filter(
                    id__in=unique_project_ids,
                    state__not=1
                ).values_list("id", "project_name")
            )
        env_ids = [obj.env_id for obj in instances]
        unique_env_ids = list(set(env_ids))
        env_name_map = {}
        if unique_env_ids:
            env_name_map = dict(
                await AUTOTEST_API_ENV_ENUM_CRUD.model.filter(
                    id__in=unique_env_ids,
                    state__not=1
                ).values_list("id", "env_name")
            )
        # 并发执行所有 to_dict 操作（核心：用gather批量处理异步任务）
        report_instances = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "config_id"}
            )
            for obj in instances
        ])
        # 用列表推导式填充 case_name 并生成最终数据
        data = [
            {
                **item,
                "project_name": project_name_map.get(item["project_id"], ""),
                "env_name": env_name_map.get(item["env_id"], "")
            }
            for item in report_instances
        ]
        LOGGER.info(f"按条件查询环境配置成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按条件查询环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")
