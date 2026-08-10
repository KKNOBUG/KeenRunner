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

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_env_schema import (
    AutoTestApiEnvCreate,
    AutoTestApiEnvUpdate,
    AutoTestApiEnvSelect,
    AutoTestApiEnvDelete, AutoTestApiEnvListQuery, AutoTestApiEnvConfigQueryByProjectsIn
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse
)

autotest_env = APIRouter()


@autotest_env.post("/create", summary="新增环境", description="新增环境")
async def create_environment(
        env_in: AutoTestApiEnvCreate = Body(..., description="环境信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增环境。

    :param env_in: 环境入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_curd.create_env(env_in=env_in)
        data = await services.env_curd.serialize_env(instance)
        LOGGER.info(f"新增环境成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_env.delete("/delete", summary="删除环境", description="根据id或code删除环境信息")
async def delete_environment(
        env_id: Optional[int] = Query(None, description="环境ID"),
        env_code: Optional[str] = Query(None, description="环境标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除环境。

    :param env_id: 环境主键ID
    :param env_code: 环境业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_curd.delete_env(env_id=env_id, env_code=env_code)
        data = await services.env_curd.serialize_env(instance)
        LOGGER.info(f"根据id或code删除环境成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_env.post("/deletes", summary="批量删除环境", description="根据id或code列表删除环境信息")
async def delete_environments(
        env_in: AutoTestApiEnvDelete = Body(..., description="环境信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code列表删除环境。

    :param env_in: 环境入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        count = await services.env_curd.delete_envs(env_in=env_in)
        LOGGER.info(f"根据id或code列表删除环境成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code列表删除环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_env.post("/update", summary="更新环境", description="根据id或code更新环境信息")
async def update_environment(
        env_in: AutoTestApiEnvUpdate = Body(..., description="环境信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新环境。

    :param env_in: 环境入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.env_curd.update_env(env_in=env_in)
        data = await services.env_curd.serialize_env(instance)
        LOGGER.info(f"根据id或code更新环境成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_env.get("/get", summary="查询环境", description="根据id或code查询环境信息")
async def get_environment(
        env_id: Optional[int] = Query(None, description="环境ID"),
        env_code: Optional[str] = Query(None, description="环境标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询环境。

    :param env_id: 环境主键ID
    :param env_code: 环境业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if env_id:
            instance = await services.env_curd.get_by_id(env_id=env_id, on_error=True, state__not=1)
        else:
            instance = await services.env_curd.get_by_code(env_code=env_code, on_error=True, state__not=1)
        data = await services.env_curd.serialize_env(instance)
        LOGGER.info(f"根据id或code查询环境成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env.get("/get_names", summary="查询环境名称", description="查询去重后的环境名称列表")
async def get_environment_names(
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    查询环境名称(去重)。

    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        names: List[str] = await services.env_curd.list_env_names()
        LOGGER.info(f"查询环境名称(去重)成功, 结果明细: {names}")
        return SuccessResponse(message="查询成功", data=names, total=len(names))
    except Exception as e:
        LOGGER.error(f"查询环境名称(去重)环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env.post("/search", summary="查询环境列表", description="根据条件分页查询环境列表信息(Body)")
async def search_environments(
        env_in: AutoTestApiEnvSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询环境。

    :param env_in: 环境入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if env_in.env_id:
            q &= Q(id=env_in.env_id)
        if env_in.env_code:
            q &= Q(env_code=env_in.env_code)
        if env_in.env_name:
            dict_ids = await services.env_curd.get_dict_ids_by_name(env_in.env_name)
            if not dict_ids:
                return SuccessResponse(message="查询成功", data=[], total=0)
            q &= Q(env_id__in=dict_ids)
        if env_in.created_user:
            q &= Q(created_user__iexact=env_in.created_user)
        if env_in.updated_user:
            q &= Q(updated_user__iexact=env_in.updated_user)
        q &= Q(state=env_in.state)
        total, instances = await services.env_curd.select_envs(
            search=q,
            page=env_in.page,
            page_size=env_in.page_size,
            order=env_in.order
        )
        env_serializes: List[Dict[str, Any]] = await services.env_curd.serialize_envs(instances, with_audit=True)
        LOGGER.info(f"根据条件查询环境成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=env_serializes, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件查询环境失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_env.post("/query", summary="查询环境配置并分类", description="按id列表查询环境配置并分类返回")
async def classify_environment_configs(
        env_config_in: AutoTestApiEnvConfigQueryByProjectsIn = Body(..., description="应用ID列表"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按应用ID列表查询环境配置并分类返回。

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
        LOGGER.error(f"按应用列表查询环境配置并分类失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")


@autotest_env.post("/list", summary="查询环境列表", description="按节点类型/应用聚合环境名称")
async def list_environments(
        env_in: AutoTestApiEnvListQuery = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按节点类型/应用聚合环境名称。

    :param env_in: 可选应用ID列表
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        result_data = await services.env_curd.get_envs(env_in.project_id)
        return SuccessResponse(message="查询成功", data=result_data)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询环境列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@autotest_env.get("/page", summary="查询环境分页列表", description="按应用/环境/节点类型聚合后分页查询")
async def search_environments(
        project_id: Optional[int] = Query(None, description="应用ID", ge=1),
        env_name: Optional[str] = Query(None, description="环境名称"),
        env_type: Optional[int] = Query(None, description="节点类型"),
        ip: Optional[str] = Query(None, description="IP地址"),
        page: int = Query(1, description="页码", ge=1),
        page_size: int = Query(10, description="每页条数", ge=1, le=100),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    按应用/环境/节点类型聚合后分页查询。

    :param project_id: 应用主键ID
    :param env_name: 环境名称
    :param env_type: 节点类型
    :param ip: IP地址
    :param page: 页码
    :param page_size: 每页条数
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        total, data = await services.env_curd.get_env_search_list(
            project_id=project_id,
            env_name=env_name,
            env_type=env_type,
            ip=ip,
            page=page,
            page_size=page_size,
        )
        return SuccessResponse(data=data, total=total, message="查询成功")
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询环境分页列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 错误描述: {e}")


@autotest_env.get("/get_all_app", summary="查询全部应用", description="获取全部启用应用列表")
async def get_all_apps(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10000, ge=1, description="每页条数"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    获取全部启用应用列表。

    :param page: 页码
    :param page_size: 每页条数
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        data, total = await services.project_curd.get_all_project(page, page_size)
        LOGGER.info(f"获取所有应用成功, 结果明细: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"获取所有应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败, 异常描述: {e}")
