# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_exec_view
@DateTime: 2025/11/12 09:05
"""
from fastapi import APIRouter, Body, Query
from tortoise.expressions import Q

from backend.applications.aotutest.schemas.autotest_case_schema import (
    AutoTestApiCaseCreate,
    AutoTestApiCaseSelect,
    AutoTestApiCaseUpdate
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException
from backend.core.responses.http_response import (
    SuccessResponse,
    FailureResponse,
    DataAlreadyExistsResponse,
    NotFoundResponse,
)

autotest_exec = APIRouter()
