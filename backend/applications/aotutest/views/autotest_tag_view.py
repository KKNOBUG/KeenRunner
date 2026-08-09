# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_view
@DateTime: 2026/1/17 16:06
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.aotutest.dependencies import AutoTestApiServices, get_autotest_api_services
from backend.applications.aotutest.schemas.autotest_tag_schema import (
    AutoTestApiTagCreate,
    AutoTestApiTagSelect,
    AutoTestApiTagUpdate,
    AutoTestApiTagDelete,
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

autotest_tag = APIRouter()


@autotest_tag.post("/create", summary="新增标签", description="新增标签信息")
async def create_tag(
        tag_in: AutoTestApiTagCreate = Body(..., description="标签信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    新增标签。

    :param tag_in: 标签入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.tag_curd.create_tag(tag_in=tag_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增标签失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_tag.delete("/delete", summary="删除标签", description="根据id或code删除标签信息")
async def delete_tag(
        tag_id: Optional[int] = Query(None, description="标签ID"),
        tag_code: Optional[str] = Query(None, description="标签标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code删除标签。

    :param tag_id: 标签主键ID
    :param tag_code: 标签业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.tag_curd.delete_tag(tag_id=tag_id, tag_code=tag_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除标签信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_tag.post("/delete", summary="删除标签(批量)", description="根据id或code列表删除标签信息")
async def batch_delete_tags(
        tag_in: AutoTestApiTagDelete = Body(..., description="标签信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code列表删除标签。

    :param tag_in: 标签入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        count = await services.tag_curd.delete_tags(tag_in=tag_in)
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code列表删除标签信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_tag.post("/update", summary="更新标签", description="根据id或code更新标签信息")
async def update_tag(
        tag_in: AutoTestApiTagUpdate = Body(..., description="标签信息"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code更新标签。

    :param tag_in: 标签入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.tag_curd.update_tag(tag_in=tag_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        return SuccessResponse(data=data, message="更新成功", total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新标签信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_tag.get("/get", summary="查询标签", description="根据id或code查询标签信息")
async def get_tag(
        tag_id: Optional[int] = Query(None, description="标签ID"),
        tag_code: Optional[str] = Query(None, description="标签标识代码"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据id或code查询标签。

    :param tag_id: 标签主键ID
    :param tag_code: 标签业务标识
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if tag_id:
            instance = await services.tag_curd.get_by_id(tag_id=tag_id, on_error=True, state__not=1)
        else:
            instance = await services.tag_curd.get_by_code(tag_code=tag_code, on_error=True, state__not=1)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询标签信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_tag.post("/search", summary="查询标签列表", description="根据条件分页查询标签列表信息(Body)")
async def search_tags(
        tag_in: AutoTestApiTagSelect = Body(..., description="查询条件"),
        services: AutoTestApiServices = Depends(get_autotest_api_services),
):
    """
    根据条件查询标签。

    :param tag_in: 标签入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if tag_in.tag_id:
            q &= Q(id=tag_in.tag_id)
        if tag_in.tag_code:
            q &= Q(tag_code=tag_in.tag_code)
        if tag_in.tag_mode:
            q &= Q(tag_mode__contains=tag_in.tag_mode)
        if tag_in.tag_project:
            q &= Q(tag_project=tag_in.tag_project)
        if tag_in.tag_name:
            q &= Q(tag_name__contains=tag_in.tag_name)
        if tag_in.created_user:
            q &= Q(created_user=tag_in.created_user)
        if tag_in.updated_user:
            q &= Q(updated_user=tag_in.updated_user)
        q &= Q(state=tag_in.state)
        total, instances = await services.tag_curd.select_tags(
            search=q,
            page=tag_in.page,
            page_size=tag_in.page_size,
            order=tag_in.order
        )
        data = [
            await obj.to_dict(
                exclude_fields={
                    "state",
                    "created_user", "created_time",
                    "updated_user", "updated_time",
                    "reserve_1", "reserve_2", "reserve_3"
                },
                replace_fields={"id": "tag_id"}
            ) for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询标签列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
