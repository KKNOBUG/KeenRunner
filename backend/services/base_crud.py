# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_crud.py
@DateTime: 2025/1/18 10:48
"""

from typing import Any, Dict, Generic, List, Tuple, Type, TypeVar, Union

from pydantic import BaseModel
from tortoise.models import Model
from tortoise.expressions import Q

# 类型变量 ModelType，限定为继承自 Model 的类型
ModelType = TypeVar("ModelType", bound=Model)
# 类型变量 CreateSchemaType，限定为继承自 BaseModel 的类型
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
# 类型变量 UpdateSchemaType，限定为继承自 BaseModel 的类型
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseCrud(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    一个通用的 CRUD（创建、读取、更新、删除）数据库操作类，使用 Tortoise-ORM。

    该类是泛型类，使用了三个类型变量：
    - ModelType：表示要操作的数据库模型，必须是 tortoise.models.Model 的子类。
    - CreateSchemaType：表示创建对象时使用的模式，必须是 pydantic.BaseModel 的子类。
    - UpdateSchemaType：表示更新对象时使用的模式，必须是 pydantic.BaseModel 的子类。

    通过这个类可以方便地对数据库进行基本的 CRUD 操作，包括获取、列表查询、创建、更新和删除。
    """

    def __init__(self, model: Type[ModelType]):
        """
        初始化 BaseCrud 实例。

        :param model: 要操作的数据库模型类，必须是 tortoise.models.Model 的子类。
        """
        self.model = model

    async def get(self, id: int) -> ModelType:
        """
        :param id: 要获取的对象的唯一标识符。
        :return: 与 ID 对应的数据库对象，如果不存在可能会抛出异常。
        """
        return await self.model.get(id=id)

    async def list(self, page: int, page_size: int, search: Q = Q(), order: list = []) -> Tuple[int, List[ModelType]]:
        """
        :param page: 页码，从 1 开始。
        :param page_size: 每页的对象数量。
        :param search: 搜索条件，使用 tortoise.expressions.Q 对象。默认为 Q()，表示不进行额外搜索。
        :param order: 排序条件，为一个列表，列表元素为排序字段，默认为空列表，表示不进行排序。
        :return: 一个元组，包含总对象数和该页的对象列表。
        """
        query = self.model.filter(search)
        return await query.count(), await query.offset((page - 1) * page_size).limit(page_size).order_by(*order)

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        :param obj_in: 用于创建新对象的数据，可以是 CreateSchemaType 实例或字典。
        :return: 创建成功的数据库对象。
        """
        if isinstance(obj_in, Dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump()
        obj = self.model(**obj_dict)
        await obj.save()
        return obj

    async def update(self, id: int, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        :param id: 要更新的对象的唯一标识符。
        :param obj_in: 用于更新对象的数据，可以是 UpdateSchemaType 实例或字典。
        :return: 更新后的数据库对象。
        """
        if isinstance(obj_in, Dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        obj = await self.get(id=id)
        obj = obj.update_from_dict(obj_dict)
        await obj.save()
        return obj

    async def remove(self, id: int) -> None:
        """
        :param id: 要删除的对象的唯一标识符。
        """
        obj = await self.get(id=id)
        await obj.delete()
