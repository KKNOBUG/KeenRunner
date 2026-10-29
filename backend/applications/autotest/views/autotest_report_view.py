# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_report_view
@DateTime: 2025/11/27 09:33
"""
import traceback
from typing import Optional

from fastapi import APIRouter, Body, Query, Depends
from tortoise.expressions import Q

from backend.applications.autotest.dependencies import AutoTestServices, get_autotest_api_services
from backend.applications.autotest.schemas.autotest_report_schema import (
    AutoTestReportCreate,
    AutoTestReportSelect,
    AutoTestReportUpdate,
    AutoTestReportBatchDetailSelect,
    AutoTestReportBatchSelect,
    AutoTestReportBatchScriptSelect,
    AutoTestReportScriptReportSelect,
    AutoTestReportBatchDelete,
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

autotest_report = APIRouter()


@autotest_report.post("/create", summary="新增报告", description="新增报告信息")
async def create_report(
        report_in: AutoTestReportCreate = Body(..., description="报告信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        _current_user: User = DependSuperUser,
):
    """
    新增报告(仅任务执行引擎或管理员可直调)。

    :param report_in: 报告入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.create_report(report_in)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@autotest_report.delete("/delete", summary="删除报告", description="根据id或code删除报告信息")
async def delete_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告代码"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code删除报告。

    :param report_id: 报告主键ID
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的报告
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.delete_report(scope=scope, report_id=report_id, report_code=report_code)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@autotest_report.post("/deletes", summary="批量删除报告", description="根据报告ID或报告代码列表批量删除报告及其明细")
async def delete_reports(
        report_in: AutoTestReportBatchDelete = Body(..., description="批量删除报告入参"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    批量删除报告及其全部明细(物理删除)。

    :param report_in: 报告ID列表或报告代码列表(二选一)
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅允许删除创建人为自己的报告
    :return: 统一HTTP响应，data为实际删除的报告数量
    """
    try:
        deleted = await services.report_curd.delete_reports(scope=scope, report_in=report_in)
        return SuccessResponse(message="批量删除成功", data={"deleted": deleted}, total=deleted)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"批量删除报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量删除失败，异常描述: {str(e)}")


@autotest_report.post("/update", summary="更新报告", description="根据id或code更新报告信息")
async def update_report(
        report_in: AutoTestReportUpdate = Body(..., description="报告信息"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
        _current_user: User = DependSuperUser,
):
    """
    根据id或code更新报告(仅任务执行引擎或管理员可直调)。

    :param report_in: 报告入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文
    :return: 统一HTTP响应
    """
    try:
        instance = await services.report_curd.update_report(report_in, scope=scope)
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
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
        LOGGER.error(f"根据id或code更新报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@autotest_report.get("/get", summary="查询报告", description="根据id或code查询报告信息")
async def get_report(
        report_id: Optional[int] = Query(None, description="报告ID"),
        report_code: Optional[str] = Query(None, description="报告标识代码"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    根据id或code查询报告。

    :param report_id: 报告主键ID
    :param report_code: 报告业务标识
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，校验报告创建人可见性
    :return: 统一HTTP响应
    """
    try:
        if report_id:
            instance = await services.report_curd.get_by_id(report_id=report_id, on_error=True, state__not=1)
        else:
            instance = await services.report_curd.get_by_code(report_code=report_code, on_error=True, state__not=1)
        if not scope.can_read(instance.created_user):  # 报告含执行明细，详情需收口到可见范围
            raise NoPermissionException(
                message=f"查询报告失败, 报告[{instance.report_code}]创建人[{instance.created_user}]不在当前用户可见范围"
            )
        data = await instance.to_dict(
            exclude_fields={
                "state",
                "created_user", "updated_user",
                "created_time", "updated_time",
                "reserve_1", "reserve_2", "reserve_3"
            },
            replace_fields={"id": "report_id"}
        )
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NoPermissionException:  # 归属校验失败需向上抛出，交由全局处理器返回403
        raise
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询报告信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {e}")


@autotest_report.post("/search", summary="查询报告列表", description="分页查询手工执行报告列表(Body)")
async def search_reports(
        report_in: AutoTestReportSelect = Body(..., description="查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    执行历史主查询(执行维度)：一次执行唯一化为一行, 多数据源批次行携带批次标识供下钻报告明细; 任务调度报告不在此范围(由/search_task_batches查询)。

    :param report_in: 报告查询入参
    :param services: 自动化测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if report_in.case_id:
            q &= Q(case_id=report_in.case_id)
        if report_in.case_code:
            q &= Q(case_code=report_in.case_code)
        if report_in.case_name:
            # 报告表无case_name，先根据用例名称查出case_id再过滤
            matched_case_ids = await services.case_curd.model.filter(
                case_name__contains=report_in.case_name.strip(),
                state__not=1,
            ).values_list("id", flat=True)
            if not matched_case_ids:
                return SuccessResponse(message="查询成功", data=[], total=0)
            q &= Q(case_id__in=list(matched_case_ids))
        if report_in.report_id:
            q &= Q(id=report_in.report_id)
        if report_in.report_code:
            q &= Q(report_code__contains=report_in.report_code)
        if report_in.report_type:
            q &= Q(report_type=report_in.report_type.value)
        # 接口固定只查手工执行报告(任务调度报告由/search_task_batches按task维度聚合查询)
        q &= Q(task_code__isnull=True) | Q(task_code="")
        if report_in.batch_code:
            q &= Q(batch_code__contains=report_in.batch_code)
        if report_in.case_state is not None:
            q &= Q(case_state=report_in.case_state)
        if report_in.created_user:
            q &= Q(created_user=report_in.created_user)
        if report_in.updated_user:
            q &= Q(updated_user=report_in.updated_user)
        if report_in.step_pass_ratio:
            q &= Q(step_pass_ratio__gte=report_in.step_pass_ratio)
        # 执行时间范围：根据case_st_time筛选，仅日期时补全为当天起止
        if report_in.date_from:
            date_from = report_in.date_from.strip()
            if len(date_from) == 10:  # YYYY-MM-DD
                date_from = f"{date_from} 00:00:00"
            q &= Q(case_st_time__gte=date_from)
        if report_in.date_to:
            date_to = report_in.date_to.strip()
            if len(date_to) == 10:
                date_to = f"{date_to} 23:59:59.999999"
            q &= Q(case_st_time__lte=date_to)
        q &= Q(state=report_in.state)
        owner_q = scope.read_q("created_user")
        if owner_q is not None:
            q &= owner_q
        total, data = await services.report_curd.search_reports(search=q, report_in=report_in)
        # 行级可删标记：报告归属 created_user，按当前资源族的删除范围判定
        for item in data:
            item["can_delete"] = scope.can_delete(item.get("created_user"))
        return SuccessResponse(message="报告列表查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询报告列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_report.post("/search_batch_reports", summary="查询同批次报告列表", description="根据batch_code精确分页查询同批次报告")
async def search_batch_reports(
        batch_detail_in: AutoTestReportBatchDetailSelect = Body(..., description="批次报告查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    批次报告下钻查询(报告维度)：面向“执行报告”抽屉, 按批次标识精确分页返回同一次执行的全部报告, 一行=一条报告。

    :param batch_detail_in: 批次报告查询入参
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅返回可见范围内的报告
    :return: 统一HTTP响应
    """
    try:
        state = 0 if batch_detail_in.state is None else batch_detail_in.state
        total, data = await services.report_curd.search_batch_reports(
            page=batch_detail_in.page,
            page_size=batch_detail_in.page_size,
            order=batch_detail_in.order,
            batch_code=batch_detail_in.batch_code,
            case_id=batch_detail_in.case_id,
            state=state,
            scope=scope,
        )
        # 行级可删标记：批次报告同样按当前资源族的删除范围判定
        for item in data:
            item["can_delete"] = scope.can_delete(item.get("created_user"))
        return SuccessResponse(message="批次报告列表查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按batch_code查询批次报告列表失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_report.post("/search_task_batches", summary="查询任务执行历史", description="按任务聚合批次执行历史并计算结果")
async def search_task_batches(
        batch_in: AutoTestReportBatchSelect = Body(..., description="批次查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    任务执行历史查询(任务维度)：面向任务执行历史列表, 按任务标识聚合报告批次并计算执行结果, 一行=一个批次, 批次行不内嵌报告明细。

    :param batch_in: 含必填task_code；page/page_size针对批次数
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅聚合可见范围内的报告
    :return: 统一HTTP响应
    """
    try:
        total, batches = await services.report_curd.search_task_batches(batch_in, scope=scope)
        data = [item.model_dump(mode="json") for item in batches]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按task_code聚合batch_code计算成功/部分成功/失败状态失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_report.post("/search_batch_scripts", summary="查询批次脚本执行信息", description="按批次分页查询脚本执行信息")
async def search_report_batch_scripts(
        script_in: AutoTestReportBatchScriptSelect = Body(..., description="批次脚本查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    批次脚本维度下钻查询(脚本维度)：面向“脚本执行信息”抽屉, 按批次标识聚合脚本执行信息并分页, 一行记录代表一个脚本。
    执行次数case_execute_count=任务配置的执行轮次数(round_no去重数, 一轮内多数据源产生多条报告仅计1次), 供前端构建轮次列表; 历史数据无round_no时为报告行数。
    has_multiple_dataset=数据源名称去重数>1, 语义对齐/search_reports; 多数据源脚本行由前端触发报告批次下钻(/search_batch_reports)。

    :param script_in: 含必填batch_code；page/page_size针对脚本数
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅聚合可见范围内的报告
    :return: 统一HTTP响应
    """
    try:
        total, items = await services.report_curd.search_batch_scripts(script_in, scope=scope)
        data = [item.model_dump(mode="json") for item in items]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按batch_code聚合脚本维度执行信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@autotest_report.post("/search_script_round_reports", summary="查询轮次执行明细",
                      description="按批次与用例分页查询执行报告；round_no可选：传入时按轮次过滤，缺省时返回全部轮次明细")
async def search_script_round_reports(
        report_in: AutoTestReportScriptReportSelect = Body(..., description="轮次明细查询条件"),
        services: AutoTestServices = Depends(get_autotest_api_services),
        scope: DataScope = DependTagScope,
):
    """
    脚本执行明细分页查询(报告维度)：面向“脚本执行明细”抽屉, 按批次标识+用例ID分页返回执行报告, 一行=一次场景执行(含dataset_no)。

    双形态：传入round_no时按轮次过滤(轮次内明细)；缺省时返回全部轮次明细(执行次数模式无数据源场景), 统一按执行时间升序排列。

    :param report_in: 含必填batch_code、case_id, 可选round_no
    :param services: 自动化测试CRUD依赖聚合
    :param scope: 数据权限上下文，仅返回可见范围内的报告
    :return: 统一HTTP响应
    """
    try:
        total, data = await services.report_curd.search_script_round_reports(report_in, scope=scope)
        return SuccessResponse(message="查询成功", data=data, total=total)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"按batch_code+case_id查询脚本执行明细失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
