# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_model.py
@DateTime: 2025/1/21 09:35
"""
import asyncio
from datetime import datetime
from typing import Optional, List

from tortoise import fields, models

from backend import GLOBAL_CONFIG


class BaseModel(models.Model):
    id = fields.BigIntField(pk=True, index=True)

    async def to_dict(self, m2m: bool = False, exclude_fields: Optional[List[str]] = None):
        if exclude_fields is None:
            exclude_fields = []

        d = {}
        for field in self._meta.db_fields:
            if field not in exclude_fields:
                value = getattr(self, field)
                if isinstance(value, datetime):
                    value = value.strftime(GLOBAL_CONFIG.DATETIME_FORMAT)
                d[field] = value

        if m2m:
            tasks = [
                self.__fetch_m2m_field(field, exclude_fields)
                for field in self._meta.m2m_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        return d

    async def __fetch_m2m_field(self, field, exclude_fields):
        values = await getattr(self, field).all().values()
        formatted_values = []

        for value in values:
            formatted_value = {}
            for k, v in value.items():
                if k not in exclude_fields:
                    if isinstance(v, datetime):
                        formatted_value[k] = v.strftime(GLOBAL_CONFIG.DATETIME_FORMAT)
                    else:
                        formatted_value[k] = v
            formatted_values.append(formatted_value)

        return field, formatted_values

    class Meta:
        abstract = True
        default_connection = "default"


class UUIDModel:
    uuid = fields.UUIDField(unique=True, pk=False, index=True)


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True, index=True)
    updated_at = fields.DatetimeField(auto_now=True, index=True)


class MaintainMixin:
    created_user = fields.CharField(max_length=32, description="创建人", index=True)
    updated_user = fields.CharField(max_length=32, null=True, description="更新人", index=True)
