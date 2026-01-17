# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_view
@DateTime: 2026/1/17 16:06
"""

from typing import Optional

from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.schemas.autotest_tag_schema import (
    AutoTestApiTagCreate,
    AutoTestApiTagSelect,
    AutoTestApiTagUpdate
)
from backend.applications.aotutest.services.autotest_tag_crud import AUTOTEST_API_TAG_CRUD
from backend.core.exceptions.base_exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse,
)

autotest_tag = APIRouter()


@autotest_tag.post("/create", summary="API自动化测试-新增标签")
async def create_tag_info(tag_in: AutoTestApiTagCreate = Body(..., description="标签信息")):
    try:
        instance = await AUTOTEST_API_TAG_CRUD.create_tag(tag_in=tag_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        LOGGER.info(f"新增标签成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataBaseStorageResponse as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsResponse as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_tag.delete("/delete", summary="API自动化测试-按id或code删除标签")
async def delete_tag_info(
        tag_id: Optional[int] = Query(None, description="标签ID"),
        tag_code: Optional[str] = Query(None, description="标签标识代码"),
):
    try:
        instance = await AUTOTEST_API_TAG_CRUD.delete_tag(tag_id=tag_id, tag_code=tag_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        LOGGER.info(f"按id或code删除标签成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_tag.post("/update", summary="API自动化测试-按id或code更新标签")
async def update_tag_info(tag_in: AutoTestApiTagUpdate = Body(..., description="标签信息")):
    try:
        instance = await AUTOTEST_API_TAG_CRUD.update_tag(tag_in=tag_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        LOGGER.info(f"按id或code更新标签成功, 结果明细: {data}")
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
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_tag.get("/get", summary="API自动化测试-按id或code查询标签")
async def get_tag_info(
        tag_id: Optional[int] = Query(None, description="标签ID"),
        tag_code: Optional[str] = Query(None, description="标签标识代码"),
):
    try:
        if tag_id:
            instance = await AUTOTEST_API_TAG_CRUD.get_by_id(tag_id=tag_id, on_error=True)
        else:
            instance = await AUTOTEST_API_TAG_CRUD.get_by_code(tag_code=tag_code, on_error=True)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "created_time",
                "updated_user", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "tag_id"}
        )
        LOGGER.info(f"按id或code查询标签成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_tag.post("/search", summary="API自动化测试-按条件查询标签")
async def search_tags_info(
        tag_in: AutoTestApiTagSelect = Body(..., description="查询条件")
):
    try:
        q = Q()
        if tag_in.tag_id:
            q &= Q(id=tag_in.tag_id)
        if tag_in.tag_code:
            q &= Q(tag_code__contains=tag_in.env_code)
        if tag_in.tag_type:
            q &= Q(tag_type=tag_in.tag_type.value)
        if tag_in.tag_mode:
            q &= Q(tag_mode__contains=tag_in.tag_mode)
        if tag_in.tag_name:
            q &= Q(tag_name__contains=tag_in.tag_name)
        if tag_in.created_user:
            q &= Q(created_user__iexact=tag_in.created_user)
        if tag_in.updated_user:
            q &= Q(updated_user__iexact=tag_in.updated_user)
        q &= Q(state=tag_in.state)
        total, instances = await AUTOTEST_API_TAG_CRUD.select_tags(
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
        LOGGER.info(f"按条件查询标签成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=e.message)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
