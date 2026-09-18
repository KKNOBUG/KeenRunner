# -*- coding: utf-8 -*-
"""
压测接口资产视图：/perf/api/* 路由编排(参数接收 -> 服务调用 -> 统一响应)。

压测接口是场景编排的最小施压单元, 调试结论(debug_state)是执行前预检的依据;
导入通道只产出草稿不落库, 落库一律走 create/update 唯一写入口。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_api_view.py
@DateTime: 2026/9/16 10:30
"""
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from tortoise.expressions import Q

from backend.applications.performance.dependencies import PerfServices, get_perf_api_services
from backend.applications.performance.schemas.perf_api_schema import (
    PerfApiCreate,
    PerfApiCurlParse,
    PerfApiDebug,
    PerfApiImport,
    PerfApiLocate,
    PerfApiOpenapiParse,
    PerfApiSelect,
    PerfApiSimpleSelect,
    PerfApiUpdate,
)
from backend.applications.performance.services.perf_api_service import PerfApiService
from backend.common.curl_utils import parse_curl_command
from backend.common.openapi_utils import parse_openapi_document
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

perf_api = APIRouter()

# 接口序列化统一排除脚手架字段(列表/详情共用, 对齐 task 视图模式)
API_EXCLUDE_FIELDS = {
    "state",
    "created_user", "created_time",
    "updated_user", "updated_time",
    "reserve_1", "reserve_2", "reserve_3",
}
API_REPLACE_FIELDS = {"id": "api_id"}


@perf_api.post("/create", summary="新增压测接口", description="新增压测接口资产信息")
async def create_perf_api(
        api_in: PerfApiCreate = Body(..., description="压测接口信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    新增压测接口。

    :param api_in: 压测接口入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.api_curd.create_perf_api(api_in=api_in)
        data = await instance.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
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
        LOGGER.error(f"新增压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"新增失败，异常描述: {str(e)}")


@perf_api.delete("/delete", summary="删除压测接口", description="根据id或code删除压测接口信息(被场景引用时禁止)")
async def delete_perf_api(
        api_id: Optional[int] = Query(None, description="接口ID"),
        api_code: Optional[str] = Query(None, description="接口标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code删除压测接口。

    :param api_id: 接口主键ID
    :param api_code: 接口业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.api_curd.delete_perf_api(api_id=api_id, api_code=api_code)
        data = await instance.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
        return SuccessResponse(message="删除成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code删除压测接口信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败，异常描述: {str(e)}")


@perf_api.post("/update", summary="更新压测接口", description="根据id或code更新压测接口信息(版本号自增)")
async def update_perf_api(
        api_in: PerfApiUpdate = Body(..., description="压测接口信息"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code更新压测接口。

    :param api_in: 压测接口入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.api_curd.update_perf_api(api_in=api_in)
        data = await instance.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
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
        LOGGER.error(f"根据id或code更新压测接口信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"更新失败，异常描述: {str(e)}")


@perf_api.get("/get", summary="查询压测接口", description="根据id或code查询压测接口信息")
async def get_perf_api(
        api_id: Optional[int] = Query(None, description="接口ID"),
        api_code: Optional[str] = Query(None, description="接口标识代码"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据id或code查询压测接口。

    :param api_id: 接口主键ID
    :param api_code: 接口业务标识
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        if api_id:
            instance = await services.api_curd.get_by_id(api_id=api_id, on_error=True, state__not=1)
        else:
            instance = await services.api_curd.get_by_code(api_code=api_code, on_error=True, state__not=1)
        data = await instance.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
        return SuccessResponse(message="查询成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据id或code查询压测接口信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_api.post("/search", summary="查询压测接口列表", description="根据条件分页查询压测接口列表信息(Body)")
async def search_perf_apis(
        api_in: PerfApiSelect = Body(..., description="查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    根据条件查询压测接口。

    :param api_in: 压测接口入参
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        q = Q()
        if api_in.api_id:
            q &= Q(id=api_in.api_id)
        if api_in.api_code:
            q &= Q(api_code=api_in.api_code)
        if api_in.api_project:
            q &= Q(api_project=api_in.api_project)
        if api_in.api_name:
            q &= Q(api_name__contains=api_in.api_name)
        if api_in.step_type:
            q &= Q(step_type=api_in.step_type)
        if api_in.request_project_id:
            q &= Q(request_project_id=api_in.request_project_id)
        if api_in.created_user:
            q &= Q(created_user=api_in.created_user)
        if api_in.updated_user:
            q &= Q(updated_user=api_in.updated_user)
        q &= Q(state=api_in.state)
        total, instances = await services.api_curd.select_perf_apis(
            search=q,
            page=api_in.page,
            page_size=api_in.page_size,
            order=api_in.order
        )
        data: List[Dict[str, Any]] = [
            await obj.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
            for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=total)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"根据条件分页查询压测接口列表信息失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")


@perf_api.post("/copy", summary="复制压测接口", description="复制压测接口为同应用下的新资产(名称追加副本后缀, 调试结论不继承)")
async def copy_perf_api(
        locate_in: PerfApiLocate = Body(..., description="接口定位入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    复制压测接口。

    :param locate_in: 接口定位入参(id或code二选一)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instance = await services.api_curd.copy_perf_api(
            api_id=locate_in.api_id,
            api_code=locate_in.api_code,
            created_user=get_current_username(),
        )
        data = await instance.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
        return SuccessResponse(message="复制成功", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except DataBaseStorageException as e:
        return DataBaseStorageResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"复制压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"复制失败，异常描述: {str(e)}")


@perf_api.post("/debug", summary="压测接口调试", description="以一次真实请求验证已保存接口定义(口径与施压引擎一致, 回写调试结论)")
async def debug_perf_api(
        debug_in: PerfApiDebug = Body(..., description="调试入参"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    压测接口调试。

    :param debug_in: 调试入参(接口定位+环境+临时变量池+取数行)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(状态码/耗时/响应体截断/断言与提取快照; 传输异常属有效调试结果)
    """
    try:
        data = await PerfApiService.debug_api(debug_in=debug_in)
        return SuccessResponse(message="调试完成", data=data, total=1)
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"压测接口调试失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"调试失败，异常描述: {str(e)}")


@perf_api.post("/import_from_case", summary="从功能资产导入压测接口", description="读取公共接口或用例步骤转为压测接口草稿(仅返回不落库, 确认后走create保存)")
async def import_perf_api_from_case(
        import_in: PerfApiImport = Body(..., description="导入入参(来源用例与步骤)"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    从功能资产导入压测接口草稿。

    :param import_in: 导入入参(case_id必填; 普通用例必须显式指定step_ids)
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应(接口草稿列表, 由用户确认后走create落库)
    """
    try:
        drafts = await PerfApiService.import_from_case(case_id=import_in.case_id, step_ids=import_in.step_ids)
        return SuccessResponse(message="导入成功", data=drafts, total=len(drafts))
    except NotFoundException as e:
        return NotFoundResponse(message=str(e.message))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"从功能资产导入压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"导入失败，异常描述: {str(e)}")


@perf_api.post("/parse_curl", summary="cURL粘贴解析压测接口", description="解析cURL命令为接口草稿(仅返回不落库, 主机地址剥离由环境承接, 确认后走create保存)")
async def parse_perf_api_curl(
        parse_in: PerfApiCurlParse = Body(..., description="cURL解析入参"),
):
    """
    解析 cURL 命令文本为压测接口草稿。

    :param parse_in: cURL解析入参(curl_text必填)
    :return: 统一HTTP响应(单条接口草稿, 与import_from_case草稿同构, 另含warnings解析提示)
    """
    try:
        draft = parse_curl_command(parse_in.curl_text)
        return SuccessResponse(message="解析成功", data=draft, total=1)
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except ValueError as e:
        return ParameterResponse(message=f"cURL解析失败，{e}")
    except Exception as e:
        LOGGER.error(f"cURL解析压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"解析失败，异常描述: {str(e)}")


@perf_api.post("/parse_openapi", summary="OpenAPI/Swagger批量解析压测接口", description="解析OpenAPI 3.x/Swagger 2.0文档(json/yaml)为接口草稿列表(仅返回不落库, 逐条确认后走create保存)")
async def parse_perf_api_openapi(
        parse_in: PerfApiOpenapiParse = Body(..., description="OpenAPI解析入参"),
):
    """
    解析 OpenAPI/Swagger 文档为压测接口草稿列表。

    :param parse_in: OpenAPI解析入参(openapi_text必填)
    :return: 统一HTTP响应(接口草稿列表, 与import_from_case草稿同构, 各条另含warnings解析提示)
    """
    try:
        drafts = parse_openapi_document(parse_in.openapi_text)
        return SuccessResponse(message="解析成功", data=drafts, total=len(drafts))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except ValueError as e:
        return ParameterResponse(message=f"OpenAPI解析失败，{e}")
    except Exception as e:
        LOGGER.error(f"OpenAPI解析压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"解析失败，异常描述: {str(e)}")


@perf_api.post("/list_for_scene", summary="场景选择器查询压测接口", description="按应用查询启用接口(不分页+名称搜索, 供场景编排抽屉选择)")
async def list_perf_apis_for_scene(
        select_in: PerfApiSimpleSelect = Body(..., description="选择器查询条件"),
        services: PerfServices = Depends(get_perf_api_services),
):
    """
    场景选择器查询压测接口(不分页, 仅启用态)。

    :param select_in: 选择器查询条件
    :param services: 性能测试CRUD依赖聚合
    :return: 统一HTTP响应
    """
    try:
        instances = await services.api_curd.list_for_scene(
            api_project=select_in.api_project,
            api_name=select_in.api_name,
            step_type=select_in.step_type.value if select_in.step_type else None,
        )
        data: List[Dict[str, Any]] = [
            await obj.to_dict(exclude_fields=API_EXCLUDE_FIELDS, replace_fields=API_REPLACE_FIELDS)
            for obj in instances
        ]
        return SuccessResponse(message="查询成功", data=data, total=len(data))
    except ParameterException as e:
        return ParameterResponse(message=str(e.message))
    except Exception as e:
        LOGGER.error(f"场景选择器查询压测接口失败，异常描述: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败，异常描述: {str(e)}")
