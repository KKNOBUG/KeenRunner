# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_project_sync_service
@DateTime: 2026/11/17
"""
import asyncio
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from backend.applications.autotest.models.autotest_project_model import AutoTestProjectModel
from backend.applications.autotest.services.autotest_project_crud import AutoTestProjectCrud
from backend.configure import LOGGER, PROJECT_CONFIG
from backend.services.semaphores import AdaptiveSemaphore


@dataclass
class SyncProjectsResult:
    """ATPM应用信息同步结果：成功标志、用户提示文案与统计数据。"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    total: int = 0


class AutoTestProjectSyncService:
    """ATPM应用信息同步服务：承载第三方请求、数据校验、并发落库与结果统计。"""

    def __init__(self, project_crud: AutoTestProjectCrud):
        self._project_crud = project_crud
        self._semaphore = AdaptiveSemaphore(max_concurrent=5)

    async def _fetch_application_details(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        """
        请求第三方接口获取应用明细响应体，网络或解析异常记入日志并返回None。

        :param client: 外部HTTP客户端，由调用方管理生命周期
        :return: 响应体字典；请求或解析失败时返回None
        """
        try:
            app_response: httpx.Response = await client.request(
                method="POST",
                url=PROJECT_CONFIG.ATPM_SYNC_API_URL,
            )
            return app_response.json()
        except Exception as e:
            error_message: str = (
                f"【同步ATPM应用信息】请求服务器发生未知错误, "
                f"错误类型: {type(e).__name__}, "
                f"错误描述: {e}"
            )
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            return None

    async def _upsert_single_project(self, app_info: Dict[str, Any]):
        """新增或更新单条应用记录，按信号量限制并发。"""
        async with self._semaphore.semaphore:
            return await self._project_crud.model.update_or_create(
                defaults={
                    "project_name": app_info["subApplicationName"],
                    "project_mark": app_info["subApplicationIdentify"],
                },
                project_name=app_info["subApplicationName"],
                project_mark=app_info["subApplicationIdentify"],
                state=0,
            )

    async def sync_projects(self) -> SyncProjectsResult:
        """同步ATPM应用信息：请求第三方、校验明细、并发落库并按新增与更新归类统计。"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), trust_env=False) as client:
                response_details: Optional[Dict[str, Any]] = await self._fetch_application_details(client)
        except Exception as e:
            error_message: str = f"【同步ATPM应用信息】构建HTTP客户端失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            return SyncProjectsResult(success=False, message="HTTP请求调试异常", data=error_message)

        if response_details is None:
            return SyncProjectsResult(
                success=False,
                message="HTTP请求调试异常",
                data="第三方接口请求失败, 详见服务日志",
            )

        app_details: List[Dict[str, Any]] = response_details.get("data")
        if not app_details:
            return SyncProjectsResult(
                success=False,
                message="同步应用失败, 获取应用明细信息为空",
                data=response_details,
            )

        sync_tasks = [asyncio.create_task(self._upsert_single_project(app_info)) for app_info in app_details]
        sync_result = await asyncio.gather(*sync_tasks, return_exceptions=True)

        failure_details: List[str] = []
        created_numbers: set = set()
        updated_numbers: set = set()
        affected_detail: List[Dict[str, Any]] = []
        for index, result in enumerate(sync_result):
            if (
                    not isinstance(result, tuple) or len(result) != 2
                    or not isinstance(result[0], AutoTestProjectModel)
            ):
                # 键缺失或落库异常：明细不回写，仅计数并落日志
                failure_details.append(f"第{index + 1}条失败: {type(result).__name__}: {result}")
                continue
            obj, created = result
            if created:
                created_numbers.add(obj.id)
            else:
                updated_numbers.add(obj.id)
            affected_detail.append({
                "project_id": obj.id,
                "project_name": obj.project_name,
                "project_mark": obj.project_mark,
                "created": created,
            })

        for detail in failure_details:
            LOGGER.warning(detail)

        created_num: int = len(created_numbers)
        updated_num: int = len(updated_numbers)
        if failure_details:
            message: str = f"同步应用存在{len(failure_details)}条失败"
        else:
            message: str = "同步应用全部成功"
        return SyncProjectsResult(
            success=True,
            message=message,
            data={
                "created_numbers": created_num,
                "updated_numbers": updated_num,
                "affected_detail": affected_detail,
            },
            total=created_num + updated_num,
        )