# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_testcase_view.py
@DateTime: 2025/3/28 15:57
"""
import base64
import json
import os
import tempfile
import time
import traceback
from typing import Dict, Any, Tuple, List

import aiohttp
import tortoise
from aiohttp import FormData
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q
from tortoise import exceptions as tortoise_exceptions

from backend.applications.testcase.schemas.api_testcase_schema import ApiTestCaseCreate, ApiTestCaseUpdate
from backend.applications.testcase.services.api_testcase_crud import API_TESTCASE_CRUD
from backend.core.exceptions.base_exceptions import (
    DataAlreadyExistsException,
    NotFoundException
)
from backend.core.responses.http_response import (
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


async def process_form_data(form_data_dict: Dict[str, Any]) -> Tuple[FormData, List[str]]:
    """处理form-data格式的数据，支持文件上传"""
    form_data = aiohttp.FormData()
    temp_files = []  # 用于跟踪临时文件

    for key, value in form_data_dict.items():
        if isinstance(value, dict) and 'file' in value:
            # 处理文件上传
            file_data = value['file']
            filename = value.get('filename', 'file')

            if isinstance(file_data, str) and file_data.startswith('data:'):
                # 处理Base64编码的文件
                try:
                    # 解析content type和base64数据
                    content_type = file_data.split(';')[0].split(':')[1]
                    base64_data = file_data.split(',')[1]
                    file_content = base64.b64decode(base64_data)

                    # 创建临时文件
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_file.write(file_content)
                    temp_file.close()
                    temp_files.append(temp_file.name)

                    # 添加到FormData
                    form_data.add_field(
                        key,
                        open(temp_file.name, 'rb'),
                        filename=filename,
                        content_type=content_type
                    )
                except Exception as e:
                    # 确保清理任何已创建的临时文件
                    for temp_file in temp_files:
                        try:
                            os.unlink(temp_file)
                        except:
                            pass
                    raise ValueError(f"处理文件 {filename} 失败: {str(e)}")
        else:
            # 处理普通字段
            form_data.add_field(key, str(value))

    return form_data, temp_files


@api_testcase.post("/debugging", summary="调试API测试用例信息")
async def debug_api_testcase(
        api_testcase_in: ApiTestCaseCreate = Body(..., description="API测试用例信息")
):
    """
    调试API测试用例，支持多种请求参数类型：
    - URL查询参数 (params)
    - JSON请求体 (json_body)
    - 表单数据 (form_data)
    - URL编码数据 (x_www_form_urlencoded)
    """
    start_time = time.time()
    temp_files = []  # 跟踪需要清理的临时文件

    try:
        # 1. 处理请求参数
        request_kwargs = {
            'method': api_testcase_in.method.value,
            'url': api_testcase_in.url,
            # 'headers': api_testcase_in.headers,
            'timeout': aiohttp.ClientTimeout(total=30),
            'params': api_testcase_in.params
        }

        # 2. 根据不同的请求体类型设置相应的参数
        if api_testcase_in.json_body:
            request_kwargs['json'] = api_testcase_in.json_body
        elif api_testcase_in.form_data:
            form_data, temp_files = await process_form_data(api_testcase_in.form_data)
            request_kwargs['data'] = form_data
        elif api_testcase_in.x_www_form_urlencoded:
            request_kwargs['data'] = api_testcase_in.x_www_form_urlencoded

        # 3. 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.request(**request_kwargs) as response:
                duration = round((time.time() - start_time) * 1000, 2)
                response_body = await response.text()

                # 4. 处理响应数据
                try:
                    formatted_data = json.loads(response_body)
                except json.JSONDecodeError:
                    formatted_data = response_body

                response_data = {
                    "status": response.status,
                    "statusText": response.reason,
                    "headers": dict(response.headers),
                    "data": formatted_data,
                    "size": f"{len(response_body) / 1024:.2f} KB",
                    "duration": duration
                }

                # 5. 保存测试用例
                await API_TESTCASE_CRUD.create_or_update_api_testcase(api_testcase_in)
                return SuccessResponse(data=response_data)

    except aiohttp.ClientError as e:
        LOGGER.error(traceback.format_exc())
        return FailureResponse(message=f"请求失败: {str(e)}")
    except tortoise_exceptions.BaseORMException as e:
        LOGGER.error(traceback.format_exc())
        return FailureResponse(message=f"数据库交互异常: {str(e)}")
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        return FailureResponse(message=f"调试接口时发生错误: {str(e)}")
    finally:
        # 6. 清理临时文件
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
