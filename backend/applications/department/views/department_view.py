# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : department_view.py
@DateTime: 2025/2/3 18:21
"""
import traceback

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.department.dependencies import get_dept_crud
from backend.applications.department.schemas.department_schema import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentSelect,
    DepartmentBatchDelete,
)
from backend.applications.department.services.department_crud import DepartmentCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataAlreadyExistsException,
    NotFoundException,
    ParameterException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
    ParameterResponse,
)

dept = APIRouter()


@dept.post("/create", summary="新增部门", description="新增部门信息")
async def create_department(
        department_in: DepartmentCreate = Body(..., description="部门信息"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    新增部门信息。

    :param department_in: 部门入参
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await dept_crud.create_department(department_in=department_in)
        data = await instance.to_dict()
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增部门失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@dept.delete("/delete", summary="删除部门", description="根据id删除部门信息")
async def delete_department(
        department_id: int = Query(..., description="部门ID"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    删除部门信息。

    :param department_id: 部门 ID
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await dept_crud.delete_department(department_id)
        data = await instance.to_dict()
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除部门失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@dept.post("/deletes", summary="删除部门(批量)", description="根据id列表批量删除部门信息")
async def batch_delete_departments(
        department_in: DepartmentBatchDelete = Body(..., description="批量删除参数"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    批量删除部门。

    :param department_in: 批量删除入参
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        deleted_ids = await dept_crud.delete_departments(department_in=department_in)
        deleted_num = len(deleted_ids)
        LOGGER.info(f"根据id列表批量删除部门信息成功, 结果数量: {deleted_num}")
        return SuccessResponse(message="删除成功", data={"deleted": deleted_ids}, total=deleted_num)
    except Exception as e:
        LOGGER.error(f"根据id列表批量删除部门信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@dept.post("/update", summary="更新部门", description="根据id更新部门信息")
async def update_department(
        department_in: DepartmentUpdate = Body(..., description="部门信息"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    更新部门信息。

    :param department_in: 部门入参
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await dept_crud.update_department(department_in=department_in)
        data = await instance.to_dict()
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id更新部门信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@dept.get("/get", summary="查询部门", description="根据id查询部门信息")
async def get_department(
        department_id: int = Query(..., description="部门ID"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询部门信息。

    :param department_id: 部门ID
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await dept_crud.get_or_none(id=department_id)
        if not instance:
            return NotFoundResponse(message=f"记录[id={department_id}]不存在")

        data: dict = await instance.to_dict()
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"根据id查询部门信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@dept.get("/list", summary="查询部门列表", description="根据name查询部门列表信息")
async def list_departments(
        name: str = Query(default=None, description="部门名称"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询部门列表。

    :param name: 部门名称
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        dept_tree = await dept_crud.get_dept_tree(name)
        return SuccessResponse(message="查询成功", data=dept_tree, total=len(dept_tree))
    except Exception as e:
        LOGGER.error(f"根据name查询部门列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@dept.post("/search", summary="查询部门列表", description="根据条件分页查询部门列表信息(Body)")
async def search_departments(
        department_in: DepartmentSelect = Body(..., description="查询条件"),
        dept_crud: DepartmentCrud = Depends(get_dept_crud),
):
    """
    查询部门列表。

    :param department_in: 部门入参
    :param dept_crud: 部门CRUD服务
    :return: 统一HTTP响应
    """
    try:
        page = department_in.page
        page_size = department_in.page_size
        order = department_in.order
        code = department_in.code
        name = department_in.name
        state = department_in.state
        created_user = department_in.created_user
        updated_user = department_in.updated_user

        q = Q()
        if code:
            q &= Q(code__contains=code)
        if name:
            q &= Q(name__contains=name)
        if created_user:
            q &= Q(created_user=created_user)
        if updated_user:
            q &= Q(updated_user=updated_user)
        q &= Q(state=0)
        total, instances = await dept_crud.list(page=page, page_size=page_size, search=q, order=order)
        data = [await obj.to_dict() for obj in instances]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"根据条件分页查询部门列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")
