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
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import DataAlreadyExistsException, ParameterException, NotFoundException
from backend.core.responses import SuccessResponse, DataAlreadyExistsResponse, FailureResponse, ParameterResponse, NotFoundResponse
from backend.services import DependAuth

role = APIRouter()


@role.post("/create", summary="创建角色")
async def create_role(
        role_in: RoleCreate = Body(..., description="角色信息"),
        current_user: User = DependAuth,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    创建角色。

    :param role_in: 角色入参
    :param current_user: 当前登录用户
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        instance = await role_crud.create_role(role_in=role_in, created_user=current_user.username)
        data: dict = await instance.to_dict()
        LOGGER.info(f"创建角色成功, 结果明细: {data}")
        return SuccessResponse(message="新增成功", data=data, total=1)
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"创建角色失败，异常描述: {e}\n{traceback.format_exc()}")
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
        LOGGER.info(f"删除角色成功, 结果明细: {data}")
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"删除角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@role.post("/deletes", summary="批量删除角色", description="根据角色id或code列表删除")
async def delete_roles(
        role_in: RoleBatchDelete = Body(..., description="角色批量删除入参"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    批量删除角色。

    :param role_in: 角色批量删除入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        count = await role_crud.delete_roles(
            role_ids=role_in.role_ids,
            role_codes=role_in.role_codes,
        )
        LOGGER.info(f"批量删除角色成功, 数量: {count}")
        return SuccessResponse(message="删除成功", data={"affected": count}, total=count)
    except Exception as e:
        LOGGER.error(f"批量删除角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@role.post("/update", summary="更新角色", description="根据id更新角色信息")
async def update_role(
        role_in: RoleUpdate = Body(..., description="角色信息"),
        current_user: User = DependAuth,
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    更新角色。

    :param role_in: 角色入参
    :param current_user: 当前登录用户
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        update_dict = role_in.model_dump(exclude_unset=True, exclude={"id"})
        update_dict["updated_user"] = current_user.username
        instance = await role_crud.update(id=role_in.id, obj_in=update_dict)
        data: dict = await instance.to_dict()
        LOGGER.info(f"更新角色成功, 结果明细: {data}")
        return SuccessResponse(message="更新成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"更新角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@role.get("/get", summary="查看角色", description="根据角色id或code查看角色信息")
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
            return ParameterResponse(message="查询角色信息失败, 参数[role_id]或[code]或[name]不允许为空")
        if role_id:
            instance = await role_crud.get_by_id(role_id=role_id, on_error=True)
        elif code:
            instance = await role_crud.get_by_code(role_code=code, on_error=True)
        else:
            instance = await role_crud.get_by_name(role_name=name, on_error=True)
        data = await instance.to_dict()
        LOGGER.info(f"查看角色成功, 结果明细: {data}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查看角色失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.get("/list", summary="查看角色列表", description="根据角色id或code查看角色信息")
async def list_roles(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
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
        LOGGER.info(f"查看角色列表成功, 结果数量: {total}")
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查看角色列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.get("/authorized", summary="查看角色权限", description="根据角色id查看角色权限")
async def get_role_authorized(
        id: int = Query(..., description="角色id"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    查看角色权限。

    :param id: 角色 ID
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        role_obj = await role_crud.get_or_error(id=id)
        data = await role_obj.to_dict(m2m=True)
        LOGGER.info(f"查看角色权限成功, role_id={id}")
        return SuccessResponse(message="查询成功", data=data, total=1)
    except Exception as e:
        LOGGER.error(f"查看角色权限失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@role.post("/authorized", summary="更新角色权限", description="根据角色id修改角色权限")
async def update_role_authorized(
        role_in: RoleUpdateMenusRouters = Body(..., description="角色权限入参"),
        role_crud: RoleCrud = Depends(get_role_crud),
):
    """
    更新角色权限。

    :param role_in: 角色菜单与路由权限入参
    :param role_crud: 角色CRUD服务
    :return: 统一HTTP响应
    """
    try:
        role_obj = await role_crud.get_or_none(id=role_in.id)
        if not role_obj:
            return NotFoundResponse(message=f"更新角色权限失败, 记录[id={role_in.id}]不存在")
        await role_crud.update_roles(role=role_obj, menu_ids=role_in.menu_ids, router_infos=role_in.router_infos)
        LOGGER.info(f"更新角色权限成功, role_id={role_in.id}")
        return SuccessResponse(message="更新成功")
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"更新角色权限失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")
