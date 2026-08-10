# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_project_view
@DateTime: 2026/1/2 21:37
"""
import traceback
from typing import Optional, List

from fastapi import APIRouter, Body, Query, Depends
from tortoise import connections
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_project_schema import (
    AutoTestApiProjectCreate,
    AutoTestApiProjectUpdate,
    AutoTestApiProjectSelect,
    AutoTestApiProjectDelete,
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

autotest_project = APIRouter()


async def _fuzzy_json_list_ids(
        *,
        table: str,
        field: str,
        keywords: List[str],
        state: int,
) -> List[int]:
    """
    MySQL JSON列表字段模糊匹配：CAST为字符串后LIKE，命中列表内任一元素片段即返回id。

    :param table: 表名
    :param field: JSON列表字段名
    :param keywords: 关键字列表（已去空白）
    :param state: 状态过滤
    :return: 命中的主键id列表；无有效关键字时返回空列表
    """
    cleaned = [str(k).strip() for k in (keywords or []) if k is not None and str(k).strip()]
    if not cleaned:
        return []
    likes = " OR ".join([f"CAST(`{field}` AS CHAR) LIKE %s" for _ in cleaned])
    params = [f"%{k}%" for k in cleaned]
    sql = f"SELECT `id` FROM `{table}` WHERE ({likes}) AND `state`=%s"
    conn = connections.get("default")
    rows = await conn.execute_query_dict(sql, [*params, state])
    return [int(r["id"]) for r in rows]


@autotest_project.post("/create", summary="新增应用", description="新增应用信息")
async def create_project(
        project_in: AutoTestApiProjectCreate = Body(..., description="应用信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增应用。

    :param project_in: 应用入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.project_curd.create_project(project_in=project_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增应用失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_project.delete("/delete", summary="删除应用", description="根据id或code删除应用信息")
async def delete_project(
        project_id: Optional[int] = Query(None, description="应用ID"),
        project_code: Optional[str] = Query(None, description="应用标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除应用信息。

    :param project_id: 应用主键ID
    :param project_code: 应用业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.project_curd.delete_project(project_id=project_id, project_code=project_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除应用信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_project.post("/delete", summary="删除应用(批量)", description="根据id或code列表删除应用信息")
async def batch_delete_projects(
        project_in: AutoTestApiProjectDelete = Body(..., description="项目信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code列表删除应用信息。

    :param project_in: 应用入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        count = await services.project_curd.delete_projects(project_in=project_in)
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code列表删除应用信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_project.post("/update", summary="更新应用", description="根据id或code更新应用信息")
async def update_project(
        project_in: AutoTestApiProjectUpdate = Body(..., description="应用信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新应用信息。

    :param project_in: 应用入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.project_curd.update_project(project_in=project_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
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
        LOGGER.error(f"根据id或code更新应用信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_project.get("/get", summary="查询应用", description="根据id或code查询应用信息")
async def get_project(
        project_id: Optional[int] = Query(None, description="应用ID"),
        project_code: Optional[str] = Query(None, description="应用标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询应用信息。

    :param project_id: 应用主键ID
    :param project_code: 应用业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if project_id:
            instance = await services.project_curd.get_by_id(project_id=project_id, on_error=True, state__not=1)
        else:
            instance = await services.project_curd.get_by_code(project_code=project_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "project_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询应用信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_project.get("/get_names", summary="查询应用名称", description="查询去重后的应用名称列表")
async def get_project_names(
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    查询去重后的应用名称列表。

    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        names: List[str] = await services.project_curd.model.filter(state__not=1).distinct().values_list("project_name", flat=True)
        return SuccessResponse(message="查询成功", data=names, total=len(names))
    except Exception as e:
        LOGGER.error(f"查询去重后的应用名称列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_project.post("/search", summary="查询应用列表", description="根据条件分页查询应用列表信息(Body)")
async def search_projects(
        project_in: AutoTestApiProjectSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件分页查询应用列表信息。

    :param project_in: 应用入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if project_in.project_id:
            q &= Q(id=project_in.project_id)
        if project_in.project_name:
            q &= Q(project_name__contains=project_in.project_name)
        if project_in.project_state:
            q &= Q(project_state__contains=project_in.project_state)
        if project_in.project_phase:
            q &= Q(project_phase__contains=project_in.project_phase)
        # JSON列表负责人：任一元素模糊包含关键字即可；多关键字之间为OR，与其它条件AND
        if project_in.project_dev_owners:
            dev_ids = await _fuzzy_json_list_ids(
                table="krun_autotest_project",
                field="project_dev_owners",
                keywords=project_in.project_dev_owners,
                state=project_in.state,
            )
            q &= Q(id__in=dev_ids) if dev_ids else Q(id=-1)
        if project_in.project_test_owners:
            test_ids = await _fuzzy_json_list_ids(
                table="krun_autotest_project",
                field="project_test_owners",
                keywords=project_in.project_test_owners,
                state=project_in.state,
            )
            q &= Q(id__in=test_ids) if test_ids else Q(id=-1)
        if project_in.created_user:
            q &= Q(created_user=project_in.created_user)
        if project_in.updated_user:
            q &= Q(updated_user=project_in.updated_user)
        q &= Q(state=project_in.state)
        total, instances = await services.project_curd.select_projects(
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
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询应用列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
