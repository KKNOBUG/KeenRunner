# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : department_view.py
@DateTime: 2025/2/3 18:21
"""
import traceback

from fastapi import APIRouter, Body, Query

from backend.applications.department.dependencies import DependDeptServices
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
    DataBaseStorageException,
    NotFoundException,
    ParameterException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    DataBaseStorageResponse,
    NotFoundResponse,
    ParameterResponse,
)

# 部门管理端点：最终挂载在 /dept，属 RBAC 权限端点
dept = APIRouter()


@dept.post("/create", summary="新增部门", description="新增部门信息")
async def create_department(
        department_in: DepartmentCreate = Body(..., description="部门信息"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    新增部门。

    :param department_in: 部门入参
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的部门信息，主键字段为 dept_id，total 为 1
    """
    try:
        instance = await dept_crud.create_department(department_in=department_in)
        data = await dept_crud.serialize_department(instance)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法新增部门，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [code={department_in.code}, name={department_in.name}, parent_id={department_in.parent_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.delete("/delete", summary="删除部门", description="根据id删除部门信息")
async def delete_department(
        department_id: int = Query(..., description="部门ID"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    根据 ID 删除部门。

    :param department_id: 部门 ID
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的部门信息，主键字段为 dept_id，total 为 1
    """
    try:
        instance = await dept_crud.delete_department(department_id)
        data = await dept_crud.serialize_department(instance)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法删除部门，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [department_id={department_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.post("/deletes", summary="批量删除部门", description="根据id列表批量删除部门信息")
async def batch_delete_departments(
        department_in: DepartmentBatchDelete = Body(..., description="批量删除参数"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    根据 ID 列表批量删除部门。

    :param department_in: 批量删除入参，department_ids 为空时不执行删除
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，data 中 deleted 为实际删除的 ID 列表，total 为条数
    """
    try:
        deleted_ids = await dept_crud.delete_departments(department_in=department_in)
        deleted_num = len(deleted_ids)
        return SuccessResponse(message="删除成功", data={"deleted": deleted_ids}, total=deleted_num)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法批量删除部门，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [department_ids={department_in.department_ids}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.post("/update", summary="更新部门", description="根据id更新部门信息")
async def update_department(
        department_in: DepartmentUpdate = Body(..., description="部门信息"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    根据 ID 更新部门。

    :param department_in: 部门入参，id 指定待更新部门
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的部门信息，主键字段为 dept_id，total 为 1
    """
    try:
        instance = await dept_crud.update_department(department_in=department_in)
        data = await dept_crud.serialize_department(instance)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法更新部门，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [department_id={department_in.id}, name={department_in.name}, parent_id={department_in.parent_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.get("/get", summary="查询部门", description="根据id查询部门信息")
async def get_department(
        department_id: int = Query(..., description="部门ID"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    根据 ID 查询部门。

    :param department_id: 部门 ID
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，成功时 data 为部门信息，主键字段为 dept_id，total 为 1
    """
    try:
        instance = await dept_crud.get_by_id(department_id=department_id, on_error=True, state=0)
        data = await dept_crud.serialize_department(instance)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询部门，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [department_id={department_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.get("/list", summary="查询部门列表(Query)", description="根据name查询部门列表信息")
async def list_departments(
        name: str = Query(default=None, description="部门名称"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    查询部门树。

    :param name: 部门名称，包含匹配；不传则返回全量
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，data 为顶级部门节点列表，节点含 children，主键字段为 dept_id，total 为顶级节点数
    """
    try:
        dept_tree = await dept_crud.get_dept_tree(name)
        return SuccessResponse(message="查询成功", data=dept_tree, total=len(dept_tree))
    except Exception:
        error_message: str = "暂时无法查询部门列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [name={name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@dept.post("/search", summary="查询部门列表(Body)", description="根据条件分页查询部门列表信息(Body)")
async def search_departments(
        department_in: DepartmentSelect = Body(..., description="查询条件"),
        dept_crud: DepartmentCrud = DependDeptServices,
):
    """
    按条件分页查询部门列表。

    :param department_in: 部门查询入参
    :param dept_crud: 部门 CRUD 服务
    :return: 统一响应，data 为部门列表，主键字段为 dept_id，total 为总条数
    """
    try:
        total, instances = await dept_crud.select_departments(department_in)
        data = [await dept_crud.serialize_department(instance) for instance in instances]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询部门列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={department_in.page}, page_size={department_in.page_size}, code={department_in.code}, name={department_in.name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
