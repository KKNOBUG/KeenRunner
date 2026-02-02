# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_record_crud
@DateTime: 2026/2/1 12:13
"""
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from tortoise.exceptions import FieldError
from tortoise.expressions import Q

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiRecordInfo
from backend.applications.aotutest.schemas.autotest_record_schema import AutoTestApiRecordSelect
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import ParameterException


class _RecordCreatePlaceholder(BaseModel):
    pass


class AutoTestApiTaskRecordCrud(
    ScaffoldCrud[AutoTestApiRecordInfo, _RecordCreatePlaceholder, _RecordCreatePlaceholder]
):
    def __init__(self):
        super().__init__(model=AutoTestApiRecordInfo)

    async def get_by_celery_id(self, celery_id: str) -> Optional[AutoTestApiRecordInfo]:
        """按调度ID(celery_id)查询一条记录。"""
        if not celery_id:
            return None
        return await self.model.filter(celery_id=celery_id).first()

    async def create_record(self, data: Dict[str, Any]) -> AutoTestApiRecordInfo:
        """创建一条执行记录（由 Worker task_prerun 调用）。"""
        instance = await self.create(data)
        return instance

    async def update_record_by_celery_id(
            self,
            celery_id: str,
            data: Dict[str, Any],
    ) -> Optional[AutoTestApiRecordInfo]:
        """按调度ID(celery_id)更新记录（由 Worker on_success/on_failure 调用）。"""
        record = await self.get_by_celery_id(celery_id=celery_id)
        if not record:
            return None
        allow_none_keys = ("task_summary", "task_error")
        update_dict = {k: v for k, v in data.items() if hasattr(record, k) and (v is not None or k in allow_none_keys)}
        for key, value in update_dict.items():
            setattr(record, key, value)
        await record.save(update_fields=list(update_dict.keys()))
        return record

    async def select_records(
            self,
            record_in: AutoTestApiRecordSelect,
    ) -> tuple:
        """分页按条件查询任务执行记录。"""
        try:
            q = Q()
            if record_in.celery_id:
                q &= Q(celery_id=record_in.celery_id)
            if record_in.task_id is not None:
                q &= Q(task_id=record_in.task_id)
            if record_in.task_name:
                q &= Q(task_name__contains=record_in.task_name)
            if record_in.celery_node:
                q &= Q(celery_node__contains=record_in.celery_node)
            if record_in.celery_status:
                q &= Q(celery_status=record_in.celery_status)
            if record_in.celery_scheduler:
                q &= Q(celery_scheduler=record_in.celery_scheduler)
            if record_in.celery_start_time_begin:
                try:
                    start_begin = datetime.strptime(record_in.celery_start_time_begin.strip()[:19], "%Y-%m-%d %H:%M:%S")
                    q &= Q(celery_start_time__gte=start_begin)
                except ValueError:
                    pass
            if record_in.celery_start_time_end:
                try:
                    start_end = datetime.strptime(record_in.celery_start_time_end.strip()[:19], "%Y-%m-%d %H:%M:%S")
                    q &= Q(celery_start_time__lte=start_end)
                except ValueError:
                    pass
            if record_in.celery_end_time_begin:
                try:
                    end_begin = datetime.strptime(record_in.celery_end_time_begin.strip()[:19], "%Y-%m-%d %H:%M:%S")
                    q &= Q(celery_end_time__gte=end_begin)
                except ValueError:
                    pass
            if record_in.celery_end_time_end:
                try:
                    end_end = datetime.strptime(record_in.celery_end_time_end.strip()[:19], "%Y-%m-%d %H:%M:%S")
                    q &= Q(celery_end_time__lte=end_end)
                except ValueError:
                    pass

            total, instances = await self.list(
                page=record_in.page,
                page_size=record_in.page_size,
                search=q,
                order=record_in.order or ["-celery_start_time", "-id"],
            )
            return total, list(instances)
        except FieldError as e:
            error_message: str = f"查询任务执行记录异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_RECORD_CRUD = AutoTestApiTaskRecordCrud()
