# -*- coding: utf-8 -*-
"""
压测场景视图：/perf/scene/* 路由编排(参数接收 -> 服务调用 -> 统一响应)。

场景回答「打什么、怎么打」: 编排(scene_items)与判定口径(perf_targets)是负载预设执行的唯一来源,
保存期已由 crud 完成资产引用校验(validate_and_fill_items), 视图只做查询条件与序列化编排。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_scene_view.py
@DateTime: 2026/9/16 10:30
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_scene_schema import (
    PerfPresetBatchDuplicate,
    PerfSceneCreate,
    PerfSceneLocate,
    PerfScenePinBaseline,
    PerfScenePrecheck,
    PerfSceneRunAllPresets,
    PerfSceneSelect,
    PerfSceneUpdate,
    PerfSceneWizardPayload,
)
from backend.applications.performance.services.perf_scene_service import PerfSceneService
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    DataAlreadyExistsException,
    ParameterException,
    DataBaseStorageException,
)
from backend.core.responses import (
    SuccessResponse,
    FailureResponse,
    ParameterResponse,
    NotFoundResponse,
    DataBaseStorageResponse,
    DataAlreadyExistsResponse,
)
from backend.services.ctx import get_current_username

perf_scene = APIRouter()

# 场景序列化统一排除脚手架字段(对齐 load_preset 视图模式)
SCENE_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
SCENE_REPLACE_FIELDS = {"id": "scene_id"}
# 列表页不下发容器大字段(scene_items/journey/perf_targets), 以接口项计数替代; 创建/更新人员与时间供列表列展示
SCENE_LIST_EXCLUDE_FIELDS = {"state", "reserve_1", "reserve_2", "reserve_3", "scene_items", "journey", "perf_targets", "baseline_policy"}


@perf_scene.post("/create", summary="新增压测场景", description="新增压测场景(接口项引用在保存期完成存在性校验)")
async def create_perf_scene(
        scene_in: PerfSceneCreate = Body(..., description="压测场景信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增压测场景。

    :param scene_in: 压测场景入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.scene_curd.create_perf_scene(scene_in=scene_in)
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
        return SuccessResponse(message="新增成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"新增压测场景失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_scene.delete("/delete", summary="删除压测场景", description="根据id或code删除压测场景信息(被负载预设引用时禁止)")
async def delete_perf_scene(
        scene_id: Optional[int] = Query(None, description="场景ID"),
        scene_code: Optional[str] = Query(None, description="场景标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除压测场景。

    :param scene_id: 场景主键ID
    :param scene_code: 场景业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.scene_curd.delete_perf_scene(scene_id=scene_id, scene_code=scene_code)
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除压测场景信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@perf_scene.post("/update", summary="更新压测场景", description="根据id或code更新压测场景信息")
async def update_perf_scene(
        scene_in: PerfSceneUpdate = Body(..., description="压测场景信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code更新压测场景。

    :param scene_in: 压测场景入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.scene_curd.update_perf_scene(scene_in=scene_in)
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
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
        LOGGER.error(f"根据id或code更新压测场景信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@perf_scene.get("/get", summary="查询压测场景", description="根据id或code查询压测场景信息(含编排与判定口径全量字段)")
async def get_perf_scene(
        scene_id: Optional[int] = Query(None, description="场景ID"),
        scene_code: Optional[str] = Query(None, description="场景标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询压测场景。

    :param scene_id: 场景主键ID
    :param scene_code: 场景业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if scene_id:
            instance = await services.scene_curd.get_by_id(scene_id=scene_id, on_error=True, state__not=1)
        else:
            instance = await services.scene_curd.get_by_code(scene_code=scene_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询压测场景信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_scene.post("/search", summary="查询压测场景列表", description="根据条件分页查询压测场景列表信息(Body, 不含容器大字段)")
async def search_perf_scenes(
        scene_in: PerfSceneSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件查询压测场景。

    :param scene_in: 压测场景入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if scene_in.scene_id:
            q &= Q(id=scene_in.scene_id)
        if scene_in.scene_code:
            q &= Q(scene_code=scene_in.scene_code)
        if scene_in.scene_project:
            q &= Q(scene_project=scene_in.scene_project)
        if scene_in.scene_name:
            q &= Q(scene_name__contains=scene_in.scene_name)
        if scene_in.run_mode:
            q &= Q(run_mode=scene_in.run_mode)
        # 按引用接口检索: 场景对接口是JSON容器引用(无外键), 先由业务层扫出引用场景再转code集合查询
        if scene_in.api_code:
            scene_codes = await services.scene_curd.list_scene_codes_referencing_api(api_code=scene_in.api_code)
            if not scene_codes:
                return SuccessResponse(message="查询成功", data=[], total=0)
            q &= Q(scene_code__in=scene_codes)
        q &= Q(state=scene_in.state)
        total, instances = await services.scene_curd.select_perf_scenes(
            search=q,
            page=scene_in.page,
            page_size=scene_in.page_size,
            order=scene_in.order
        )
        data: List[Dict[str, Any]] = []
        for obj in instances:
            row = await obj.to_dict(
                exclude_fields=SCENE_LIST_EXCLUDE_FIELDS,
                replace_fields=SCENE_REPLACE_FIELDS,
            )
            row["item_count"] = len(obj.scene_items or [])
            data.append(row)
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询压测场景列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_scene.post("/precheck", summary="场景连通性预检", description="对场景内启用接口逐个发1次真实请求回显连通性与业务结论(复用调试链, 结论回写口径一致)")
async def precheck_perf_scene(
        precheck_in: PerfScenePrecheck = Body(..., description="场景预检入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    场景连通性预检。

    :param precheck_in: 预检入参(场景定位 + 可选施压环境)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data含预检汇总与逐接口items回显
    """
    try:
        data = await services.scene_curd.precheck_scene(precheck_in=precheck_in)
        return SuccessResponse(message="预检完成", data=data, total=int(data.get("total") or 0))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"场景连通性预检失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"预检失败，异常描述: {str(e)}")


@perf_scene.post("/pin_baseline", summary="钉选场景基线报告", description="将同场景的已完成报告钉为退化对比基线; report_code留空为取消钉选")
async def pin_baseline_perf_scene(
        pin_in: PerfScenePinBaseline = Body(..., description="基线钉选入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    钉选/取消钉选场景基线报告。

    :param pin_in: 钉选入参(场景定位 + 基线报告标识; report_code留空=取消钉选)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(含更新后的场景信息)
    """
    try:
        instance = await services.scene_curd.pin_baseline(pin_in=pin_in, updated_user=get_current_username())
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
        message = "钉选基线成功" if (pin_in.report_code or "").strip() else "已取消基线钉选"
        return SuccessResponse(message=message, data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"钉选场景基线报告失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"钉选基线失败，异常描述: {str(e)}")


@perf_scene.post("/copy", summary="复制压测场景", description="复制压测场景为同应用下的新场景(编排全量平移, 基线不继承)")
async def copy_perf_scene(
        locate_in: PerfSceneLocate = Body(..., description="场景定位入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    复制压测场景。

    :param locate_in: 场景定位入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.scene_curd.copy_perf_scene(
            scene_id=locate_in.scene_id,
            scene_code=locate_in.scene_code,
            created_user=get_current_username(),
        )
        data = await instance.to_dict(exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS)
        return SuccessResponse(message="复制成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"复制压测场景失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {str(e)}")


@perf_scene.post("/save_wizard", summary="一体化保存场景+负载预设", description="场景独立编辑页 4 Tab 唯一提交入口: upsert scene + diff upsert presets(新增/更新/软删)")
async def save_wizard_perf_scene(
        payload: PerfSceneWizardPayload = Body(..., description="场景 + 负载预设一体化保存入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    场景独立编辑页一体化保存(Tab 编辑页唯一提交入口)。

    :param payload: PerfSceneWizardPayload(scene + presets)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data = {scene: {...}, presets: [{...}]}
    """
    try:
        result = await PerfSceneService.save_wizard(payload, current_user=get_current_username())
        scene_data = await result["scene"].to_dict(
            exclude_fields=SCENE_EXCLUDE_FIELDS, replace_fields=SCENE_REPLACE_FIELDS,
        )
        preset_data = [
            await p.to_dict(
                exclude_fields={"state", "created_user", "created_time", "updated_user", "updated_time",
                                "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "preset_id"},
            )
            for p in result["presets"]
        ]
        return SuccessResponse(message="保存成功", data={"scene": scene_data, "presets": preset_data}, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"一体化保存场景失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"保存失败，异常描述: {str(e)}")


@perf_scene.post("/preset/batch_duplicate", summary="批量派生负载预设档位", description="拐点测试快捷操作: 基于已有预设批量派生多个并发档位")
async def batch_duplicate_perf_presets(
        payload: PerfPresetBatchDuplicate = Body(..., description="批量派生入参(基准预设 + 并发列表)"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    批量派生负载预设档位(拐点测试快捷操作)。

    :param payload: PerfPresetBatchDuplicate(base_preset_id/base_preset_code + concurrent_users_list + name_template)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data = [{...}] 新建预设列表
    """
    try:
        created = await PerfSceneService.batch_duplicate_presets(payload, current_user=get_current_username())
        data = [
            await p.to_dict(
                exclude_fields={"state", "created_user", "created_time", "updated_user", "updated_time",
                                "reserve_1", "reserve_2", "reserve_3"},
                replace_fields={"id": "preset_id"},
            )
            for p in created
        ]
        return SuccessResponse(message=f"已派生 {len(created)} 份负载预设", data=data, total=len(created))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except DataAlreadyExistsException as e:
        return DataAlreadyExistsResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"批量派生负载预设失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"派生失败，异常描述: {str(e)}")


@perf_scene.post("/run_all_presets", summary="一键跑全部负载预设", description="批量下发场景下所有预设执行(锁定态跳过, 失败逐条记录不阻塞其余)")
async def run_all_perf_scene_presets(
        locate_in: PerfSceneRunAllPresets = Body(..., description="场景定位入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    一键批量下发场景下所有负载预设执行。

    :param locate_in: PerfSceneRunAllPresets(scene_id 或 scene_code)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应, data = {scene_id, scene_code, total, dispatched, skipped, failed, items}
    """
    try:
        result = await PerfSceneService.run_all_presets(locate_in, current_user=get_current_username())
        message = (
            f"已下发 {result['dispatched']}/{result['total']} 份负载预设"
            f"(跳过 {result['skipped']}, 失败 {result['failed']})"
        )
        return SuccessResponse(message=message, data=result, total=result["total"])
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"一键跑全部负载预设失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"批量下发失败，异常描述: {str(e)}")
