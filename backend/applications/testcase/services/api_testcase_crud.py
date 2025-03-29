# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : api_testcase_crud.py
@DateTime: 2025/3/28 15:44
"""
from typing import Optional, List, Dict

from tortoise.exceptions import DoesNotExist

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.testcase.models.api_testcase_model import ApiTestCase
from backend.applications.testcase.schemas.api_testcase_schema import ApiTestCaseCreate, ApiTestCaseUpdate
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class ApiTestCaseCrud(ScaffoldCrud[ApiTestCase, ApiTestCaseCreate, ApiTestCaseUpdate]):
    def __init__(self):
        super().__init__(model=ApiTestCase)

    async def get_by_id(self, api_case_id: int) -> Optional[ApiTestCase]:
        return await self.model.filter(id=api_case_id).first()

    async def get_by_name(self, api_case_name: int) -> Optional[ApiTestCase]:
        return await self.model.filter(testcase_name=api_case_name).first()

    async def create_api_testcase(self, api_testcase_in: ApiTestCaseCreate) -> ApiTestCase:
        instance = await self.create(api_testcase_in)
        return instance

    async def create_or_update_api_testcase(self, api_testcase_in: ApiTestCaseCreate) -> ApiTestCase:
        url: str = api_testcase_in.url
        method: str = api_testcase_in.method
        testcase_name: str = api_testcase_in.testcase_name
        query: ApiTestCase = await self.model.filter(url=url, method=method, testcase_name=testcase_name).first()
        if not query:
            instance = await self.create(api_testcase_in)
        else:
            data = api_testcase_in.create_dict(exclude={"id", "created_user", "created_time"})
            instance = await self.update(id=query.id, obj_in=data)

        return instance

    async def delete_api_testcase(self, api_testcase_id: int) -> ApiTestCase:
        instance = await self.query(api_testcase_id)
        if not instance:
            raise NotFoundException(message=f"接口测试用例(id={api_testcase_id})信息不存在")

        await instance.delete()
        data = await instance.to_dict()
        return data

    async def update_api_testcase(self, api_testcase_in: ApiTestCaseUpdate) -> ApiTestCase:
        api_testcase_id: int = api_testcase_in.id
        api_testcase_if: dict = {
            key: value for key, value in api_testcase_in.dict().items()
            if value is not None
        }
        try:
            instance = await self.update(id=api_testcase_id, obj_in=api_testcase_if)
        except DoesNotExist as e:
            raise NotFoundException(message=f"接口测试用例(id={api_testcase_id})信息不存在")

        return instance


API_TESTCASE_CRUD = ApiTestCaseCrud()
