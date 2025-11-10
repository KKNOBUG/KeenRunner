# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_case_view.py
@DateTime: 2025/4/28
"""
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_type_schema import (
    AutoTestTypeCreate,
    AutoTestTypeUpdate,
    AutoTestTypeSelect
)
from backend.applications.aotutest.services.autotest_type_crud import AUTO_TEST_TYPE_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

autotest_type = APIRouter()


@autotest_type.post("/create", summary="新增一个步骤类型信息")
async def create_type(
        type_in: AutoTestTypeCreate = Body(..., description="测试用例信息")
):
    """新增一个测试用例信息"""
    try:
        instance = await AUTO_TEST_TYPE_CRUD.create_type(type_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="创建步骤类型成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"创建步骤类型失败，异常描述: {str(e)}")


@autotest_type.get("/get", summary="按id查询一个步骤类型信息", description="根据id查询步骤类型信息")
async def get_type(
        type_id: int = Query(..., description="步骤类型ID")
):
    """按id查询一个测试用例信息"""
    try:
        instance = await AUTO_TEST_TYPE_CRUD.get_by_id(type_id)
        if not instance:
            return NotFoundResponse(message=f"步骤类型(id={type_id})信息不存在")
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询步骤类型失败，异常描述: {str(e)}")


@autotest_type.post("/search", summary="按条件查询多个步骤类型信息", description="支持分页按条件查询步骤类型信息")
async def search_cases(
        type_in: AutoTestTypeSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试用例信息"""
    try:
        q = Q()
        if type_in.id:
            q &= Q(id=type_in.id)
        if type_in.type_name:
            q &= Q(type_name__contains=type_in.type_name)
        if type_in.type_desc:
            q &= Q(type_desc_contains=type_in.type_desc)
        q &= Q(state=type_in.state)
        total, instances = await AUTO_TEST_TYPE_CRUD.select_cases(
            search=q,
            page=type_in.page,
            page_size=type_in.page_size,
            order=type_in.order
        )
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询步骤类型失败，异常描述: {str(e)}")


@autotest_type.post("/update", summary="按id修改一个步骤类型信息", description="根据id修改步骤类型信息")
async def update_type(
        type_in: AutoTestTypeUpdate = Body(..., description="步骤类型信息")
):
    """按id修改一个测试用例信息"""
    try:
        instance = await AUTO_TEST_TYPE_CRUD.update_type(type_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="更新步骤类型成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"修改步骤类型失败，异常描述: {str(e)}")


@autotest_type.delete("/delete", summary="按id删除一个步骤类型信息", description="根据id删除步骤类型信息")
async def delete_type(
        type_id: int = Query(..., description="步骤类型ID")
):
    """按id删除一个测试用例信息"""
    try:
        instance = await AUTO_TEST_TYPE_CRUD.delete_type(type_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除步骤类型成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        return FailureResponse(message=f"删除步骤类型失败，异常描述: {str(e)}")
