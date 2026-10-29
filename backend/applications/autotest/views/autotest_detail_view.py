# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_detail_view
@DateTime: 2025/11/27 14:25
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.schemas.autotest_detail_schema import (
    AutoTestDetailCreate,
    AutoTestDetailUpdate,
    AutoTestDetailSelect,
    AutoTestDetailTreeSelect,
    AutoTestDetailBatchDelete,
)
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    NoPermissionException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse
)
from backend.services import DataScope, DependTagScope, DependSuperUser

autotest_detail = APIRouter()


@autotest_detail.post("/create", summary="新增明细", description="新增明细信息")
async def create_step_detail(
        detail_in: AutoTestDetailCreate = Body(..., description="明细信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        _current_user: User = DependSuperUser,
):
    """
    新增明细(仅任务执行引擎或管理员可直调)。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.create_detail(detail_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {e}")


@autotest_detail.delete("/delete", summary="删除明细", description="根据id或步骤与报告code删除明细")
async def delete_step_detail(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code删除明细信息。

    :param detail_id: 明细主键ID
    :param step_code: 步骤业务标识
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的明细
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.delete_detail(
            scope=scope,
            detail_id=detail_id,
            step_code=step_code,
            report_code=report_code
        )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除明细信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {e}")


@autotest_detail.post("/deletes", summary="批量删除执行明细", description="根据明细ID列表批量删除执行明细")
async def delete_step_details(
        detail_in: AutoTestDetailBatchDelete = Body(..., description="批量删除明细入参"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    批量删除执行明细(物理删除)。

    :param detail_in: 明细ID列表
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的明细
    :return: 统一HTTP响应，data为实际删除的明细数量
    """
    try:
        deleted = await services.detail_curd.delete_details(scope=scope, detail_in=detail_in)
        return SuccessResponse(message="批量删除成功", data={"deleted": deleted}, total=deleted)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"批量删除明细信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量删除失败，异常描述: {e}")


@autotest_detail.post("/update", summary="更新明细", description="根据id或code更新明细信息")
async def update_step_detail(
        detail_in: AutoTestDetailUpdate = Body(..., description="明细信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
        _current_user: User = DependSuperUser,
):
    """
    根据id或code更新明细信息(仅任务执行引擎或管理员可直调)。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文
    :return: 统一HTTP响应
    """
    try:
        instance = await services.detail_curd.update_detail(detail_in, scope=scope)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        return SuccessResponse(message="更新成功", data=data, total=1)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code更新明细信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {e}")


@autotest_detail.get("/get", summary="查询明细", description="根据id或步骤与报告code查询明细")
async def get_step_detail(
        detail_id: Optional[int] = Query(None, description="明细ID"),
        step_code: Optional[str] = Query(None, description="步骤标识代码"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code查询明细信息。

    :param detail_id: 明细主键ID
    :param step_code: 步骤业务标识
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，校验明细创建人可见性
    :return: 统一HTTP响应
    """
    try:
        if detail_id:
            instance = await services.detail_curd.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        else:
            instance = await services.detail_curd.get_by_conditions(
                only_one=True,
                on_error=True,
                conditions={"step_code": step_code, "report_code": report_code}
            )
        if not scope.can_read(instance.created_user):  # 明细含报文快照，详情需收口到可见范围
            raise NoPermissionException(
                message=f"查询明细失败, 明细[{instance.id}]创建人[{instance.created_user}]不在当前用户可见范围"
            )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "detail_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询明细信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_detail.post("/search", summary="查询明细列表", description="根据条件分页查询明细列表信息(Body)")
async def search_step_details(
        detail_in: AutoTestDetailSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据条件分页查询明细列表信息。

    :param detail_in: 明细入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if detail_in.case_id:
            q &= Q(case_id=detail_in.case_id)
        if detail_in.case_code:
            q &= Q(case_code=detail_in.case_code)
        if detail_in.report_code:
            q &= Q(report_code=detail_in.report_code)
        if detail_in.step_id:
            q &= Q(step_id=detail_in.step_id)
        if detail_in.step_no:
            q &= Q(step_no=detail_in.step_no)
        if detail_in.step_code:
            q &= Q(step_code=detail_in.step_code)
        if detail_in.step_type:
            q &= Q(step_type=detail_in.step_type.value)
        if detail_in.step_state is not None:
            q &= Q(step_state=detail_in.step_state)
        if detail_in.detail_id:
            q &= Q(id=detail_in.detail_id)
        if detail_in.created_user:
            q &= Q(created_user=detail_in.created_user)
        if detail_in.updated_user:
            q &= Q(updated_user=detail_in.updated_user)
        q &= Q(state=detail_in.state)
        owner_q = scope.read_q("created_user")
        if owner_q is not None:
            q &= owner_q
        # 强制order传递 ["step_st_time", "id"] 确保按执行顺序排序
        total, instances = await services.detail_curd.select_details(
            search=q,
            page=detail_in.page,
            page_size=detail_in.page_size,
            order=detail_in.order
        )
        for row in instances:
            row["detail_id"] = row.pop("id")
            # 列表页行级删除按钮依据：与单删接口同一归属口径，避免展示后点击才报无权限
            row["can_delete"] = scope.can_delete(row.get("created_user"))
        return SuccessResponse(message="查询成功", data=instances, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询明细列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_detail.post("/tree", summary="查询明细树", description="根据报告标识查询完整明细树(后端组装, 不分页)")
async def search_step_detail_tree(
        detail_in: AutoTestDetailTreeSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据报告标识查询完整明细树；固定执行时间线排序组装，only_failed=True时仅保留失败步骤及其祖先链。

    :param detail_in: 明细树入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应(data为嵌套children树, children恒存在且无子时为空列表; total为明细总行数)
    """
    try:
        q = Q(report_code=detail_in.report_code)
        if detail_in.case_id:
            q &= Q(case_id=detail_in.case_id)
        if detail_in.case_code:
            q &= Q(case_code=detail_in.case_code)
        q &= Q(state=detail_in.state)
        owner_q = scope.read_q("created_user")
        if owner_q is not None:
            q &= owner_q
        # 固定执行时间线排序(保证父行先于子行)，由后端单遍组装为嵌套明细树
        total, instances = await services.detail_curd.select_tree_details(search=q, order=["step_st_time", "id"])
        for row in instances:
            row["detail_id"] = row.pop("id")
        data = services.detail_curd.build_detail_tree(instances, only_failed=detail_in.only_failed)
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"查询明细树失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询明细树失败，异常描述: {str(e)}")
