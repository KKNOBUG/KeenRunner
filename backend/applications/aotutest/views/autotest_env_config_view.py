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

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiConfigCreate,
    AutoTestApiConfigUpdate,
    AutoTestApiConfigSelect,
    AutoTestApiConfigDelete,
    AutoTestEnvConfigQueryByProjectsIn,
)
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
    NotFoundResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse
)
from backend.enums import AutoTestConfigNodeType

autotest_env_config = APIRouter()


@autotest_env_config.post("/create", summary="新增环境配置")
async def create_env_config(
        config_in: AutoTestApiConfigCreate = Body(..., description="环境配置"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增环境配置。

    :param config_in: 环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_config_curd.create_config(config_in=config_in)
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
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_env_config.delete("/delete", summary="删除环境配置", description="根据id或code删除环境配置信息")
async def delete_env_config(
        config_id: Optional[int] = Query(None, description="环境配置ID"),
        config_code: Optional[str] = Query(None, description="环境配置标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除环境配置。

    :param config_id: 环境配置主键ID
    :param config_code: 环境配置业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_config_curd.delete_config(config_id=config_id, config_code=config_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "config_id"}
        )
        LOGGER.info(f"根据id或code删除环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_env_config.post("/delete", summary="批量删除环境配置", description="根据id或code列表删除环境配置信息")
async def delete_env_configs(
        config_in: AutoTestApiConfigDelete = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code列表删除环境。

    :param config_in: 环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        count = await services.env_config_curd.delete_configs(config_in=config_in)
        LOGGER.info(f"根据id或code列表删除环境配置成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code列表删除环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_env_config.post("/update", summary="更新环境配置", description="根据id或code更新环境配置信息")
async def update_env_config(
        config_in: AutoTestApiConfigUpdate = Body(..., description="环境配置"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新环境配置。

    :param config_in: 环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_config_curd.update_config(config_in=config_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "config_id"}
        )
        LOGGER.info(f"根据id或code更新环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_env_config.get("/get", summary="查询环境配置", description="根据id或code查询环境配置信息")
async def get_env_config(
        config_id: Optional[int] = Query(None, description="环境配置ID"),
        config_code: Optional[str] = Query(None, description="环境配置标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询环境配置。

    :param config_id: 环境配置主键ID
    :param config_code: 环境配置业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if not config_id and not config_code:
            return ParameterResponse(message="查询环境配置失败, 参数[config_id]或[config_code]至少传一个")
        if config_id:
            instance = await services.env_config_curd.get_by_id(config_id=config_id, on_error=True, state__not=1)
        else:
            instance = await services.env_config_curd.get_by_code(config_code=config_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "config_id"}
        )
        LOGGER.info(f"根据id或code查询环境配置成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.post("/search", summary="查询环境配置列表", description="根据条件分页查询环境配置列表信息(Body)")
async def search_env_configs(
        config_in: AutoTestApiConfigSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询环境配置。

    :param config_in: 环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
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
        total, instances = await services.env_config_curd.select_config(
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
                await services.project_curd.model.filter(
                    id__in=unique_project_ids,
                    state__not=1
                ).values_list("id", "project_name")
            )
        env_ids = [obj.env_id for obj in instances]
        unique_env_ids = list(set(env_ids))
        env_name_map = {}
        if unique_env_ids:
            env_name_map = dict(
                await services.env_enum_curd.model.filter(
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
        LOGGER.info(f"根据条件查询环境配置成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件查询环境配置失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.post("/query", summary="查询环境配置分类", description="根据应用列表查询环境配置并分类")
async def query_env_configs_classified(
        config_in: AutoTestEnvConfigQueryByProjectsIn = Body(..., description="应用ID列表"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    返回结构：project_id -> env_id -> config_type(api/database/file) -> config_name ->
    {config_host, config_port, database_name}。
    """
    try:
        data = await services.env_config_curd.query_classified_by_project_ids(
            project_ids=config_in.project_ids,
        )
        total_configs: int = sum(
            len(names)
            for envs in data.values()
            for buckets in envs.values()
            for names in buckets.values()
        )
        LOGGER.info(
            f"根据应用列表查询环境配置并分类成功, project_ids={config_in.project_ids}, 配置条数: {total_configs}"
        )
        return SuccessResponse(message="查询成功", data=data, total=total_configs)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据应用列表查询环境配置并分类失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.get("/config_names", summary="查询配置名称", description="获取去重后的配置名称列表")
async def get_env_config_names(
        project_id: Optional[int] = Query(None, ge=1, description="应用ID，可选"),
        env_id: Optional[int] = Query(None, ge=1, description="环境ID，可选"),
        config_type: Optional[AutoTestConfigNodeType] = Query(None, description="配置类型，可选"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    获取去重后的配置名称列表。

    :param project_id: 应用主键ID
    :param env_id: 环境主键ID
    :param config_type: 配置类型
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        config_type_val = config_type.value if config_type is not None else None
        data = await services.env_config_curd.list_distinct_config_names(
            project_id=project_id,
            env_id=env_id,
            config_type=config_type_val,
        )
        LOGGER.info(
            f"获取去重配置名称列表成功, project_id={project_id}, env_id={env_id}, "
            f"config_type={config_type_val}, 数量={len(data)}"
        )
        return SuccessResponse(message="查询成功", data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"获取去重配置名称列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
