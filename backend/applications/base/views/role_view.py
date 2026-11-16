# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : role_view.py
@DateTime: 2025/2/19 23:11
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body
from fastapi.params import Query

from backend.applications.base.dependencies import DependRoleServices
from backend.applications.base.schemas.role_schema import (
    RoleCreate,
    RoleUpdate,
    RoleUpdateMenusRouters,
    RoleBatchDelete,
    RoleSelect,
)
from backend.applications.base.services.role_crud import RoleCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataAlreadyExistsException,
    ParameterException,
    NotFoundException,
    DataBaseStorageException
)
from backend.core.responses import (
    SuccessResponse,
    DataAlreadyExistsResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse
)
from backend.services import DependSuperUser

role = APIRouter()


@role.post("/create", summary="新增角色", description="新增角色信息")
async def create_role(
        role_in: RoleCreate = Body(..., description="角色信息"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    新增角色。

    :param role_in: 角色入参
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为新增后的角色信息，主键字段为 role_id，total 为 1
    """
    try:
        instance = await role_crud.create_role(role_in=role_in)
        data = await role_crud.serialize_role(instance)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法新增角色，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [code={role_in.code}, name={role_in.name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.delete("/delete", summary="删除角色", description="根据id删除角色信息")
async def delete_role(
        role_id: int = Query(..., description="角色id"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    根据 ID 删除单个角色（物理删除）。

    :param role_id: 角色 ID
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为被删除的角色信息，主键字段为 role_id，total 为 1
    """
    try:
        instance = await role_crud.delete_role(role_id=role_id)
        data = await role_crud.serialize_role(instance)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法删除角色，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_id={role_id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.post("/deletes", summary="批量删除角色", description="根据角色id或code列表删除")
async def batch_delete_roles(
        role_in: RoleBatchDelete = Body(..., description="id或code列表"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    根据 ID 或编码列表批量删除角色（物理删除）。

    :param role_in: 批量删除入参，含 role_ids 与 role_codes，role_ids 优先
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，data 中 deleted 为实际删除的 ID 或编码列表，total 为条数
    """
    try:
        deleted_ids_or_codes = await role_crud.delete_roles(
            role_ids=role_in.role_ids,
            role_codes=role_in.role_codes,
        )
        deleted_num = len(deleted_ids_or_codes)
        return SuccessResponse(message="删除成功", data={"deleted": deleted_ids_or_codes}, total=deleted_num)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法批量删除角色，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_ids={role_in.role_ids}, role_codes={role_in.role_codes}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.post("/update", summary="更新角色", description="根据id更新角色信息")
async def update_role(
        role_in: RoleUpdate = Body(..., description="角色信息"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    根据 ID 更新角色基础字段，不含菜单、接口与标签范围绑定。

    :param role_in: 角色入参，id 指定待更新角色
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为更新后的角色信息，主键字段为 role_id，total 为 1
    """
    try:
        instance = await role_crud.update_role(role_in=role_in)
        data = await role_crud.serialize_role(instance)
        return SuccessResponse(message="更新成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法更新角色，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_id={role_in.id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.get("/get", summary="查询角色", description="根据角色id或code或name查询角色信息")
async def get_role(
        role_id: Optional[int] = Query(default=None, ge=1, description="角色ID"),
        code: Optional[str] = Query(default=None, description="角色代码"),
        name: Optional[str] = Query(default=None, description="角色名称"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    按 ID、编码或名称查询单个角色。

    :param role_id: 角色 ID
    :param code: 角色编码
    :param name: 角色名称
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为角色信息，主键字段为 role_id，total 为 1
    """
    try:
        if not role_id and not code and not name:
            return ParameterResponse(message="查询角色信息失败, 参数[id, code, name]不允许同时为空")
        if role_id:
            instance = await role_crud.get_by_id(role_id=role_id, on_error=True)
        elif code:
            instance = await role_crud.get_by_code(role_code=code, on_error=True)
        else:
            instance = await role_crud.get_by_name(role_name=name, on_error=True)
        data = await role_crud.serialize_role(instance)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询角色，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_id={role_id}, code={code}, name={name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.get("/list", summary="查询角色列表(Query)", description="根据角色name查询角色信息")
async def search_roles(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, le=99999, description="每页数量"),
        order: list = Query(default_factory=lambda: ["id"], description="排序字段"),
        name: str = Query(default="", description="角色名称"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    按名称分页查询角色列表（Query 入参）。

    :param page: 页码
    :param page_size: 每页条数
    :param order: 排序字段
    :param name: 角色名称，包含匹配；空串表示不筛选
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为角色列表，主键字段为 role_id，total 为总条数
    """
    try:
        role_in = RoleSelect(page=page, page_size=page_size, order=order, name=name or None)
        total, role_objs = await role_crud.select_roles(role_in=role_in)
        data = [await role_crud.serialize_role(obj) for obj in role_objs]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询角色列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={page}, page_size={page_size}, name={name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.post("/search", summary="查询角色列表(Body)", description="根据条件分页查询角色列表信息(Body)")
async def search_roles_by_body(
        role_in: RoleSelect = Body(..., description="查询条件"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    按条件分页查询角色列表（Body 入参）。

    :param role_in: 角色查询入参
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时 data 为角色列表，主键字段为 role_id，total 为总条数
    """
    try:
        total, role_objs = await role_crud.select_roles(role_in=role_in)
        data = [await role_crud.serialize_role(obj) for obj in role_objs]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except Exception:
        error_message: str = "暂时无法查询角色列表，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [page={role_in.page}, page_size={role_in.page_size}, code={role_in.code}, name={role_in.name}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.get(
    "/authorized",
    summary="查询角色权限",
    description="根据角色id查询角色权限",
    dependencies=[DependSuperUser],
)
async def get_role_authorized(
        id: int = Query(..., description="角色id"),
        role_crud: RoleCrud = DependRoleServices,
):
    """
    查询角色的菜单、接口与标签范围配置（仅管理员可调用）。

    :param id: 角色 ID
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，data 含 menus、routers、tag_scopes 与 builtin_admin 标记
    """
    try:
        data = await role_crud.get_authorization_data(role_id=id)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法查询角色权限，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_id={id}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)


@role.post(
    "/authorized",
    summary="更新角色权限",
    description="根据角色id更新角色权限",
    dependencies=[DependSuperUser],
)
async def update_role_authorized(
        role_in: RoleUpdateMenusRouters,
        role_crud: RoleCrud = DependRoleServices,
):
    """
    更新角色的菜单、接口与标签范围配置（仅管理员可调用）。

    :param role_in: 授权入参，含角色 ID、菜单 ID、接口绑定项与标签范围
    :param role_crud: 角色 CRUD 服务
    :return: 统一响应，成功时不携带 data
    """
    try:
        role_obj = await role_crud.get_by_id(role_id=role_in.id, on_error=True)
        await role_crud.save_authorization(
            role=role_obj,
            menu_ids=role_in.menu_ids,
            router_infos=role_in.router_infos,
            tag_scopes=role_in.tag_scopes,
        )
        return SuccessResponse(message="更新成功")
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except Exception:
        error_message: str = "暂时无法更新角色权限，请稍后重试"
        LOGGER.error(
            f"{error_message}, "
            f"关键字段: [role_id={role_in.id}, menu_count={len(role_in.menu_ids)}, router_count={len(role_in.router_infos)}]\n"
            f"异常回溯: {traceback.format_exc()}"
        )
        return FailureResponse(message=error_message)
