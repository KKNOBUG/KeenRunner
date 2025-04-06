# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_testcase_view.py
@DateTime: 2025/3/28 15:57
"""
import json
import time
import traceback

import aiohttp
import tortoise
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.testcase.schemas.api_testcase_schema import ApiTestCaseCreate, ApiTestCaseUpdate
from backend.applications.testcase.services.api_testcase_crud import API_TESTCASE_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.response.http_response import (
    NotFoundResponse,
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
)
from backend.enums.http_enum import HTTPMethod
from backend.enums.testcase_priority_enum import TestCasePriorityEnum
from backend import LOGGER

api_testcase = APIRouter()


@api_testcase.post("/updateOrCreate", summary="更新或新增API测试用例")
async def update_or_create_api_testcase(
        api_testcase_in: ApiTestCaseCreate = Body(..., description="API测试用例信息")
):
    try:
        instance = await API_TESTCASE_CRUD.create_or_update_api_testcase(api_testcase_in)
        data = await instance.to_dict()
        return SuccessResponse(data=data)
    except Exception as e:
        return FailureResponse(message=f"新增失败，异常描述:{e}")


@api_testcase.delete("/delete", summary="删除API测试用例信息", description="根据idAPI测试用例信息")
async def delete_router(
        api_testcase_id: int = Query(..., description="接口ID")
):
    try:
        instance = await API_TESTCASE_CRUD.delete_api_testcase(api_testcase_id)
        return SuccessResponse(data=instance)
    except NotFoundException as e:
        return NotFoundResponse(message=e.__str__())
    except Exception as e:
        return FailureResponse(message=f"删除失败，异常描述:{e}")


# 获取所有接口信息
@api_testcase.get("/list/", summary="查询API测试用例列表")
async def get_apis(
        page: int = Query(default=1, ge=1, description="页码"),
        page_size: int = Query(default=10, ge=10, description="每页数量"),
        order: list = Query(default=["id"], description="排序字段"),
        method: HTTPMethod = Query(None, description="路由请求路径"),
        priority: TestCasePriorityEnum = Query(None, description="路由作用简介"),
        project: str = Query(None, description="路由所属标签"),
        module: str = Query(None, description="路由所属标签"),
):
    q = Q()
    if method:
        q &= Q(method=method)
    if priority:
        q &= Q(priority=priority)
    if project:
        q &= Q(project__contains=project)
    if module:
        q &= Q(module__contains=module)
    total, router_objs = await API_TESTCASE_CRUD.list(
        page=page, page_size=page_size, search=q, order=order
    )
    data = [await obj.to_dict() for obj in router_objs]
    return SuccessResponse(data=data, total=total)


@api_testcase.get("/get", summary="获取单个API测试用例信息")
async def get_api_testcase(
        api_testcase_id: int = Query(None, description="API测试用例ID"),
):
    instance = await API_TESTCASE_CRUD.get_by_id(id=api_testcase_id)
    if not instance:
        return NotFoundResponse(message=f"API测试用例(id={api_testcase_id})信息不存在")

    data: dict = await instance.to_dict()
    return SuccessResponse(data=data)


# 后端代码 api_testcase_view.py 文件修改

@api_testcase.post("/debugging", summary="调试API测试用例信息")
async def debug_api_testcase(
        api_testcase_in: ApiTestCaseCreate = Body(..., description="API测试用例信息")
):
    start_time = time.time()

    # 参数处理
    params = {}
    if api_testcase_in.params:
        try:
            params = dict(item.split("=") for item in api_testcase_in.params.split("&"))
        except Exception as e:
            return FailureResponse(message=f"参数解析失败: {str(e)}")

    # 请求体处理
    data = None
    json_data = api_testcase_in.json_body
    if api_testcase_in.form_data:
        data = aiohttp.FormData()
        for key, value in api_testcase_in.form_data.items():
            if isinstance(value, dict) and 'file' in value:  # 处理文件上传
                data.add_field(key, value['file'], filename=value['filename'])
            else:
                data.add_field(key, str(value))

    # 发送请求
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(
                    method=api_testcase_in.method.value,
                    url=api_testcase_in.url,
                    params=params,
                    headers=api_testcase_in.headers,
                    json=json_data,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                duration = round((time.time() - start_time) * 1000, 2)
                response_body = await response.text()

                # 尝试解析JSON
                try:
                    formatted_data = json.loads(response_body)
                except json.JSONDecodeError:
                    formatted_data = response_body

                # 构造返回数据
                response_data = {
                    "status": response.status,
                    "statusText": response.reason,
                    "headers": dict(response.headers),
                    "data": formatted_data,
                    "size": f"{len(response_body) / 1024:.2f} KB",
                    "duration": duration
                }

                await API_TESTCASE_CRUD.create_or_update_api_testcase(api_testcase_in)
                return SuccessResponse(data=response_data)
        except aiohttp.ClientError as e:
            LOGGER.error(traceback.format_exc())
            return FailureResponse(message=f"请求失败: {str(e)}")
        except tortoise.exceptions.BaseORMException as e:
            LOGGER.error(traceback.format_exc())
            return FailureResponse(message=f"数据库交互异常: {str(e)}")
        except Exception as e:
            LOGGER.error(traceback.format_exc())
            return FailureResponse(message=f"调试接口时发生错误: {str(e)}")
