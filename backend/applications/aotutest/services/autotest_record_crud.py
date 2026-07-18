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

from backend.applications.aotutest.models.autotest_model import AutoTestApiRecordInfo
from backend.applications.aotutest.schemas.autotest_record_schema import AutoTestApiRecordSelect
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException


class _RecordCreatePlaceholder(BaseModel):
    """占位用 schema，任务执行记录由业务直接写字典。"""

    pass


class AutoTestApiTaskRecordCrud(
    ScaffoldCrud[AutoTestApiRecordInfo, _RecordCreatePlaceholder, _RecordCreatePlaceholder]
):
    """任务执行观测记录 CRUD。"""

    def __init__(self):
        super().__init__(model=AutoTestApiRecordInfo)

    async def get_by_celery_id(self, celery_id: str) -> Optional[AutoTestApiRecordInfo]:
        if not celery_id:
            return None
        return await self.model.filter(celery_id=celery_id).first()

    async def create_record(self, data: Dict[str, Any]) -> AutoTestApiRecordInfo:
        return await self.create(data)

    async def update_record_by_celery_id(
            self,
            celery_id: str,
            data: Dict[str, Any],
    ) -> Optional[AutoTestApiRecordInfo]:
        record = await self.get_by_celery_id(celery_id=celery_id)
        if not record:
            return None
        allow_none_keys = ("task_summary", "task_error", "batch_code")
        update_dict = {
            k: v for k, v in data.items()
            if hasattr(record, k) and (v is not None or k in allow_none_keys)
        }
        for key, value in update_dict.items():
            setattr(record, key, value)
        await record.save(update_fields=list(update_dict.keys()))
        return record

    async def select_records(self, record_in: AutoTestApiRecordSelect) -> tuple:
        try:
            q = Q()
            if record_in.celery_id:
                q &= Q(celery_id=record_in.celery_id)
            if record_in.task_id is not None:
                q &= Q(task_id=record_in.task_id)
            if record_in.task_code:
                q &= Q(task_code=record_in.task_code)
            if record_in.task_name:
                q &= Q(task_name__contains=record_in.task_name)
            if record_in.task_type is not None:
                type_val = getattr(record_in.task_type, "value", record_in.task_type)
                q &= Q(task_type=type_val)
            if record_in.task_project is not None:
                q &= Q(task_project=record_in.task_project)
            if record_in.trigger_type is not None:
                trigger_val = getattr(record_in.trigger_type, "value", record_in.trigger_type)
                q &= Q(trigger_type=trigger_val)
            if record_in.batch_code:
                q &= Q(batch_code=record_in.batch_code)
            if record_in.celery_status is not None:
                status_val = getattr(record_in.celery_status, "value", record_in.celery_status)
                q &= Q(celery_status=status_val)

            def _parse_dt(raw: Optional[str]):
                if not raw:
                    return None
                try:
                    return datetime.strptime(raw.strip()[:19], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None

            start_begin = _parse_dt(record_in.celery_start_time_begin)
            if start_begin:
                q &= Q(celery_start_time__gte=start_begin)
            start_end = _parse_dt(record_in.celery_start_time_end)
            if start_end:
                q &= Q(celery_start_time__lte=start_end)
            end_begin = _parse_dt(record_in.celery_end_time_begin)
            if end_begin:
                q &= Q(celery_end_time__gte=end_begin)
            end_end = _parse_dt(record_in.celery_end_time_end)
            if end_end:
                q &= Q(celery_end_time__lte=end_end)

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
