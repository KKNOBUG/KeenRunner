# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : role_view.py
@DateTime: 2025/2/19 23:11
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Depends
from fastapi.params import Query
from tortoise.expressions import Q

from backend.applications.base.dependencies import get_role_crud
from backend.applications.base.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleUpdateMenusRouters,
    RoleBatchDelete,
)
from backend.applications.base.services.role_crud import RoleCrud
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException
from backend.core.responses import SuccessResponse, DataAlreadyExistsResponse, FailureResponse, ParameterResponse, NotFoundResponse

role = APIRouter()


@role.post("/create", summary="新增角色", description="新增角色信息")
async def create_role(
        role_in: RoleCreate = Body(..., description="角色信息"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    创建角色。

    :param role_in: 角色入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await role_crud.create_role(role_in=role_in)
        data: dict = await instance.to_dict()
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@role.delete("/delete", summary="删除角色", description="根据id删除角色信息")
async def delete_role(
        role_id: int = Query(..., description="角色id"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    删除角色。

    :param role_id: 角色 ID
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await role_crud.delete_role(role_id=role_id)
        data = await instance.to_dict()
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id删除角色信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@role.post("/deletes", summary="删除角色(批量)", description="根据角色id或code列表删除")
async def batch_delete_roles(
        role_in: RoleBatchDelete = Body(..., description="id或code列表"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    批量删除角色。

    :param role_in: 角色批量删除入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        deleted_ids_or_codes = await role_crud.delete_roles(
            role_ids=role_in.role_ids,
            role_codes=role_in.role_codes,
        )
        deleted_num = len(deleted_ids_or_codes)
        return SuccessResponse(message="删除成功", data={"deleted": deleted_ids_or_codes}, total=deleted_num)
    except Exception as e:
        LOGGER.error(f"根据角色id或code列表删除失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@role.post("/update", summary="更新角色", description="根据id更新角色信息")
async def update_role(
        role_in: RoleUpdate = Body(..., description="角色信息"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    更新角色。

    :param role_in: 角色入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await role_crud.update_role(role_in=role_in)
        data: dict = await instance.to_dict()
        return SuccessResponse(message="更新成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except IntegrityError as e:
        error_message: str = f"根据id更新角色信息失败, 违反约束规则: {e}"
        LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
        return DataBaseStorageResponse(message=error_message)
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id更新角色信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新角色失败，异常描述: {e}")


@role.get("/get", summary="查询角色", description="根据角色id或code或name查询角色信息")
async def get_role(
        role_id: Optional[int] = Query(default=None, ge=1, description="角色ID"),
        code: Optional[str] = Query(default=None, description="角色代码"),
        name: Optional[str] = Query(default=None, description="角色名称"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    查看角色。

    :param role_id: 角色主键ID，与code/name三选一
    :param code: 角色代码
    :param name: 角色名称
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        if not role_id and not code and not name:
            return ParameterResponse(message="查询角色信息失败, 参数[id]或[code]或[name]不允许为空")
        if role_id:
            instance = await role_crud.get_by_id(role_id=role_id, on_error=True)
        elif code:
            instance = await role_crud.get_by_code(role_code=code, on_error=True)
        else:
            instance = await role_crud.get_by_name(role_name=name, on_error=True)
        data = await instance.to_dict()
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据角色id或code或name查询角色信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.get("/list", summary="查询角色列表", description="根据角色name查询角色信息")
async def search_roles(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default_factory=lambda: ["id"], description="排序字段"),
        name: str = Query(default="", description="角色名称"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    查看角色列表。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param name: 角色名称
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if name:
            q = Q(name__contains=name)
        total, role_objs = await role_crud.list(
            page=page, page_size=page_size, search=q, order=order
        )
        data = [await obj.to_dict() for obj in role_objs]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"根据角色name查询角色信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.get("/authorized", summary="查询角色权限", description="根据角色id查询角色权限")
async def get_role_authorized(
        id: int = Query(..., description="角色id"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    查看角色权限。

    :param id: 角色ID
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        role_obj = await role_crud.get_or_error(id=id)
        data = await role_obj.to_dict(m2m=True)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"根据角色id查询角色权限失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.post("/authorized", summary="更新角色权限", description="根据角色id更新角色权限")
async def update_role_authorized(
        role_in: RoleUpdateMenusRouters,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    更新角色权限。

    :param role_in: 角色菜单与路由权限入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        role_obj = await role_crud.get_by_id(role_id=role_in.id, on_error=True)
        await role_crud.update_roles(role=role_obj, menu_ids=role_in.menu_ids, router_infos=role_in.router_infos)
        return SuccessResponse(message="更新成功")
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据角色id更新角色权限失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")
