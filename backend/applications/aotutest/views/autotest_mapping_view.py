# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_mapping_view.py
@DateTime: 2025/4/28
"""
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_mapping_schema import AutoTestStepMappingCreate, \
    AutoTestStepMappingSelect, AutoTestStepMappingUpdate
from backend.applications.aotutest.services.autotest_mapping_crud import AUTO_TEST_STEP_MAPPING_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

autotest_mapping = APIRouter()


@autotest_mapping.post("/create", summary="新增一个测试步骤映射")
async def create_mapping(
        mapping_in: AutoTestStepMappingCreate = Body(..., description="步骤映射信息")
):
    """新增一个测试步骤映射"""
    try:
        instance = await AUTO_TEST_STEP_MAPPING_CRUD.create_mapping(mapping_in)
        data = await instance.to_dict(fk=True)
        return SuccessResponse(data=data, message="创建步骤映射成功")
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_mapping.get("/get", summary="按id查询一个测试步骤映射", description="根据id查询步骤映射信息")
async def get_mapping(
        mapping_id: int = Query(..., description="步骤映射ID")
):
    """按id查询一个测试步骤映射"""
    try:
        instance = await AUTO_TEST_STEP_MAPPING_CRUD.get_by_id(mapping_id)
        if not instance:
            return NotFoundResponse(message=f"步骤映射(id={mapping_id})信息不存在")
        data = await instance.to_dict(fk=True)
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_mapping.post("/search", summary="按条件查询多个测试步骤映射", description="支持分页按条件查询步骤映射信息")
async def search_mappings(
        mapping_in: AutoTestStepMappingSelect = Body(..., description="查询条件")
):
    """按条件查询多个测试步骤映射"""
    try:
        q = Q()
        if mapping_in.id:
            q &= Q(id=mapping_in.id)
        if mapping_in.case_id:
            q &= Q(case__id=mapping_in.case_id)
        if mapping_in.step_info_id:
            q &= Q(step_info__id=mapping_in.step_info_id)
        if mapping_in.parent_mapping_id is not None:
            if mapping_in.parent_mapping_id == 0:
                q &= Q(parent_mapping__isnull=True)
            else:
                q &= Q(parent_mapping__id=mapping_in.parent_mapping_id)
        if mapping_in.step_no:
            q &= Q(step_no=mapping_in.step_no)

        total, instances = await AUTO_TEST_STEP_MAPPING_CRUD.select_mappings(
            search=q,
            page=mapping_in.page,
            page_size=mapping_in.page_size,
            order=mapping_in.order
        )
        data = [await obj.to_dict(fk=True) for obj in instances]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_mapping.post("/update", summary="按id修改一个测试步骤映射", description="根据id修改步骤映射信息")
async def update_mapping(
        mapping_in: AutoTestStepMappingUpdate = Body(..., description="步骤映射信息")
):
    """按id修改一个测试步骤映射"""
    try:
        instance = await AUTO_TEST_STEP_MAPPING_CRUD.update_mapping(mapping_in)
        data = await instance.to_dict(fk=True)
        return SuccessResponse(data=data, message="更新步骤映射成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"修改失败，异常描述: {str(e)}")


@autotest_mapping.delete("/delete", summary="按id删除一个测试步骤映射", description="根据id删除步骤映射信息")
async def delete_mapping(
        mapping_id: int = Query(..., description="步骤映射ID")
):
    """按id删除一个测试步骤映射"""
    try:
        instance = await AUTO_TEST_STEP_MAPPING_CRUD.delete_mapping(mapping_id)
        data = await instance.to_dict()
        return SuccessResponse(data=data, message="删除步骤映射成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_mapping.get("/tree", summary="按测试用例步骤映射id查询所有对应步骤",
                      description="包含所有子步骤、引用测试用例中的步骤")
async def get_step_tree(
        mapping_id: int = Query(..., description="测试用例步骤映射ID")
):
    """按测试用例步骤映射id查询所有对应步骤（包含所有子步骤、引用测试用例中的步骤）"""
    try:
        tree_data = await AUTO_TEST_STEP_MAPPING_CRUD.get_step_tree_by_mapping_id(mapping_id)
        return SuccessResponse(data=tree_data, message="获取步骤树成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e))
    except Exception as e:
        return FailureResponse(message=f"获取步骤树失败，异常描述: {str(e)}")
