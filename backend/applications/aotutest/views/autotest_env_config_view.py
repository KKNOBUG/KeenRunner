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
    AutoTestApiConfigSelect,
    AutoTestEnvConfigQueryByProjectsIn,
    APPEnvConfigCreate,
    FILEEnvConfigCreate,
    DBEnvConfigCreate,
    RedisEnvConfigCreate,
    RedisEnvConfigUpdate,
    APPEnvConfigUpdate,
    FILEEnvConfigUpdate,
    DBEnvConfigUpdate,
    EnvConfigDelete,
    TestDBConnectionRequest,
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataAlreadyExistsResponse
)
from backend.enums import AutoTestConfigNodeType

autotest_env_config = APIRouter()


@autotest_env_config.post("/app/create", summary="新增APP类型环境配置", description="新增APP类型环境配置信息")
async def create_app_config(
        config_in: APPEnvConfigCreate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增APP类型环境配置信息。

    :param config_in: APP环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.create_config(config_in)
        return SuccessResponse(message="新增APP配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增APP配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增APP配置失败, 错误描述: {e}")


@autotest_env_config.post("/file/create", summary="新增FILE类型环境配置", description="新增FILE类型环境配置信息")
async def create_file_config(
        config_in: FILEEnvConfigCreate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增FILE类型环境配置信息。

    :param config_in: FILE环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.create_config(config_in)
        return SuccessResponse(message="新增FILE配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增FILE配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增FILE配置失败, 错误描述: {e}")


@autotest_env_config.post("/database/create", summary="新增DB类型环境配置", description="新增DB类型环境配置信息")
async def create_db_config(
        config_in: DBEnvConfigCreate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增DB类型环境配置信息。

    :param config_in: DB环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.create_config(config_in)
        return SuccessResponse(message="新增DB配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增DB配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增DB配置失败, 错误描述: {e}")


@autotest_env_config.post("/redis/create", summary="新增REDIS类型环境配置", description="新增REDIS类型环境配置信息")
async def create_redis_config(
        config_in: RedisEnvConfigCreate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增REDIS类型环境配置信息。

    :param config_in: Redis环境配置入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.create_redis_config(config_in)
        return SuccessResponse(message="新增Redis配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增Redis配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增Redis配置失败, 错误描述: {e}")


@autotest_env_config.post("/redis/update", summary="更新REDIS类型环境配置", description="更新REDIS类型环境配置信息")
async def update_redis_config(
        config_in: RedisEnvConfigUpdate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新REDIS类型环境配置信息。

    :param config_in: Redis环境配置更新入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.update_redis_config(config_in)
        return SuccessResponse(message="修改Redis配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"修改Redis配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改Redis配置失败, 错误描述: {e}")


@autotest_env_config.post("/delete", summary="删除子表环境配置", description="删除指定子表环境配置信息")
async def delete_env_config(
        config_in: EnvConfigDelete = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    删除指定子表环境配置信息。

    :param config_in: 环境配置删除入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.delete_config(config_in)
        return SuccessResponse(message="删除配置成功", data=result, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除配置失败, 错误描述: {e}")


@autotest_env_config.post("/app/update", summary="更新APP类型环境配置", description="更新APP类型环境配置信息")
async def update_app_config(
        config_in: APPEnvConfigUpdate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新APP类型环境配置信息。

    :param config_in: APP环境配置更新入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.update_config(config_in)
        return SuccessResponse(message="修改APP配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"修改APP配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改APP配置失败, 错误描述: {e}")


@autotest_env_config.post("/file/update", summary="更新FILE类型环境配置", description="更新FILE类型环境配置信息")
async def update_file_config(
        config_in: FILEEnvConfigUpdate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新FILE类型环境配置信息。

    :param config_in: FILE环境配置更新入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.update_config(config_in)
        return SuccessResponse(message="修改FILE配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"修改FILE配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改FILE配置失败, 错误描述: {e}")


@autotest_env_config.post("/database/update", summary="更新DB类型环境配置", description="更新DB类型环境配置信息")
async def update_db_config(
        config_in: DBEnvConfigUpdate = Body(..., description="环境配置信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    更新DB类型环境配置信息。

    :param config_in: DB环境配置更新入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result = await services.env_config_curd.update_config(config_in)
        return SuccessResponse(message="修改DB配置成功", data=result, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"修改DB配置失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"修改DB配置失败, 错误描述: {e}")


@autotest_env_config.get("/get", summary="查询环境配置", description="根据id或code查询环境配置信息")
async def get_env_config(
        config_id: Optional[int] = Query(None, description="环境配置ID"),
        config_code: Optional[str] = Query(None, description="环境配置标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询环境配置信息。

    :param config_id: 环境配置主键ID
    :param config_code: 环境配置业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
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
            replace_fields={"id": "env_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询环境配置信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.post("/search", summary="查询环境配置列表", description="根据条件分页查询环境配置列表信息(Body)")
async def search_env_configs(
        config_in: AutoTestApiConfigSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件分页查询环境配置列表信息。

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
            q &= Q(created_user=config_in.created_user)
        if config_in.updated_user:
            q &= Q(updated_user=config_in.updated_user)
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
        env_name_map = await services.env_curd.get_env_name_map(unique_env_ids)
        report_instances = await asyncio.gather(*[
            obj.to_dict(
                exclude_fields={"state", "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "config_id"}
            )
            for obj in instances
        ])
        data = [
            {
                **item,
                "project_name": project_name_map.get(item["project_id"], ""),
                "env_name": env_name_map.get(item["env_id"], "")
            }
            for item in report_instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询环境配置列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.post("/query", summary="查询环境配置分类", description="根据应用列表查询环境配置并分类")
async def classify_env_configs(
        env_config_in: AutoTestEnvConfigQueryByProjectsIn = Body(..., description="应用ID列表"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据应用列表查询环境配置并分类。

    :param env_config_in: 含project_ids的查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data = await services.env_config_curd.query_classified_by_project_ids(
            project_ids=env_config_in.project_ids,
        )
        total_configs: int = sum(
            len(names)
            for envs in data.values()
            for buckets in envs.values()
            for names in buckets.values()
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
        return SuccessResponse(message="查询成功", data=data, total=len(data))
    except Exception as e:
        LOGGER.error(f"获取去重后的配置名称列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env_config.get("/list", summary="查询子表环境配置列表", description="按条件分页查询子表环境配置列表")
async def list_env_configs(
        env_info_id: Optional[int] = Query(None, description="应用ID"),
        env_name: Optional[str] = Query(None, description="环境"),
        env_type: Optional[AutoTestConfigNodeType] = Query(None, description="节点类型(api/file/database/redis)"),
        page: int = Query(1, description="页码", ge=1),
        page_size: int = Query(10, description="每页条数", ge=1, le=100),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按条件分页查询子表环境配置列表。

    :param env_info_id: 应用主键ID
    :param env_name: 环境名称
    :param env_type: 节点类型
    :param page: 页码
    :param page_size: 每页条数
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        total, data = await services.env_config_curd.get_config_list(
            env_info_id=env_info_id,
            env_name=env_name,
            env_type=env_type,
            page=page,
            page_size=page_size,
        )
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询子表环境配置列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 错误描述: {e}")


@autotest_env_config.post("/database/test_connection", summary="执行数据库连接测试", description="根据入参测试数据库连接是否可用")
async def test_db_connection(
        config_in: TestDBConnectionRequest = Body(..., description="连接测试入参"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据入参测试数据库连接是否可用。

    :param config_in: 数据库连接测试入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        return await services.env_config_curd.test_db_connection(
            config_id=config_in.id,
            project_id=config_in.project_id,
            env_name=config_in.env_name,
            config_name=config_in.config_name,
            db_name=config_in.db_name,
        )
    except Exception as e:
        LOGGER.error(f"测试数据库连接失败: {e}\n{traceback.format_exc()}")
        return {
            "code": "999999",
            "status": "failure",
            "message": f"测试数据库连接失败：{e}",
            "data": None,
        }
