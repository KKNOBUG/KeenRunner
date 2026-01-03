# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scaffold.py
@DateTime: 2025/1/18 10:48
"""
import asyncio
from decimal import Decimal
from datetime import datetime, date, time
from typing import Any, Dict, Generic, List, Tuple, Type, TypeVar, Union, Optional, Set

from pydantic import BaseModel
from tortoise.models import Model
from tortoise.expressions import Q
from tortoise import fields, models

from backend import GLOBAL_CONFIG


class ScaffoldModel(models.Model):
    id = fields.BigIntField(pk=True, description="主键")

    async def to_dict(self,
                      include_fields: Optional[Union[List[str], Set[str]]] = None,
                      exclude_fields: Optional[Union[List[str], Set[str]]] = None,
                      replace_fields: Optional[Dict[str, str]] = None,
                      m2m: bool = False,
                      m2m_include_fields: Optional[Union[List[str], Set[str]]] = None,
                      m2m_exclude_fields: Optional[Union[List[str], Set[str]]] = None,
                      fk: bool = False,
                      fk_include_fields: Optional[Union[List[str], Set[str]]] = None,
                      fk_exclude_fields: Optional[Union[List[str], Set[str]]] = None,
                      ):
        """
        将模型实例转换为字典形式，支持灵活配置要包含或排除的字段，以及是否处理多对多关系和外键关系。
        :param include_fields: 需要引入的本表字段列表，默认为 None
        :param exclude_fields: 需要排除的本表字段列表，默认为 None
        :param replace_fields: 需要别名的本表字段列表，默认为 None
        :param m2m: 是否获取多对多关系字段的数据，默认为 False
        :param m2m_include_fields: 需要引入的多对多表字段列表，默认为 None
        :param m2m_exclude_fields: 需要排除的多对多表字段列表，默认为 None
        :param fk: 是否获取外键字段对应的数据，默认为 False
        :param fk_include_fields: 需要引入的外键表字段列表，默认为 None
        :param fk_exclude_fields: 需要排除的外键表字段列表，默认为 None
        :return:
        """
        # 若未提供排除字段列表，则初始化为空列表
        exclude_fields = exclude_fields or []
        m2m_exclude_fields = m2m_exclude_fields or []
        fk_exclude_fields = fk_exclude_fields or []

        d = {}
        # 获取本表字段并根据 include_fields 参数确定要处理的字段列表
        db_fields_process = self._meta.db_fields
        if include_fields:
            db_fields_process = include_fields

        # 遍历字段列表，将字段值添加到字典中，并对特定类型的值进行预处理
        for field in db_fields_process:
            if field in exclude_fields:
                continue
            value = getattr(self, field)
            if replace_fields:
                field = replace_fields.get(field, field)
            d[field] = await self.__format_value(value)

        # 如果 fk 为 True，异步获取外键字段关联的数据
        if fk:
            tasks = [
                self.__fetch_fk_field(field, fk_include_fields, fk_exclude_fields)
                for field in self._meta.fk_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        # 如果 m2m 为 True，异步获取多对多关系字段的数据
        if m2m:
            tasks = [
                self.__fetch_m2m_field(field, m2m_include_fields, m2m_exclude_fields)
                for field in self._meta.m2m_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        return d

    @classmethod
    async def __format_value(cls, value: Any):
        if isinstance(value, datetime):
            value = value.strftime(GLOBAL_CONFIG.DATETIME_FORMAT)
        elif isinstance(value, date):
            value = value.strftime(GLOBAL_CONFIG.DATE_FORMAT)
        elif isinstance(value, time):
            value = value.strftime(GLOBAL_CONFIG.TIME_FORMAT)
        elif isinstance(value, bytes):
            value = value.decode("utf-8")
        elif isinstance(value, Decimal):
            value = float(value)

        return value

    async def __fetch_fk_field(self, field, fk_include_fields, fk_exclude_fields):
        """
        获取外键字段关联对象的数据，并将其转换为字典形式
        :param field: 外键字段名
        :param fk_include_fields: 需要引入的外键表字段列表
        :param fk_exclude_fields: 需要排除的外键表字段列表
        :return: 外键字段名和关联对象转换后的字典
        """
        fk_instance = getattr(self, field)
        if fk_instance:
            return field, await fk_instance.to_dict(
                include_fields=fk_include_fields,
                exclude_fields=fk_exclude_fields,
                m2m=False,  # 避免无限递归
                fk=False  # 根据需求调整
            )
        return field, None

    async def __fetch_m2m_field(self, field, m2m_include_fields, m2m_exclude_fields):
        """
        获取多对多关系字段的数据，并将其转换为字典形式
        :param field: 外键字段名
        :param m2m_include_fields: 需要引入的外键表字段列表
        :param m2m_exclude_fields: 需要排除的外键表字段列表
        :return: 多对多字段名和关联对象转换后的字典
        """
        instances = await getattr(self, field).all()
        values = []
        for instance in instances:
            value = await instance.to_dict(
                include_fields=m2m_include_fields,
                exclude_fields=m2m_exclude_fields,
                m2m=False,  # 避免无限递归
                fk=False  # 根据需求调整
            )
            values.append(value)
        return field, values

    class Meta:
        abstract = True  # 表明这个类是一个抽象基类，不会在数据库中创建对应的表。其他模型类可以继承这个基类，复用其方法和字段
        default_connection = "default"  # 指定默认使用的数据库连接


class UUIDModel:
    uuid = fields.UUIDField(unique=True, description="唯一标识符")


class PacketModel:
    pid = fields.BigIntField(index=True, description="分组标识符")


class StateModel:
    state = fields.SmallIntField(default=-1, index=True, description="状态")


class ClassModel:
    code = fields.CharField(max_length=16, unique=True, description="代码")
    name = fields.CharField(max_length=64, unique=True, description="名称")
    description = fields.TextField(null=True, description="描述")


class TimestampMixin:
    created_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_time = fields.DatetimeField(auto_now=True, description="更新时间")


class MaintainMixin:
    created_user = fields.CharField(max_length=16, default=None, null=True, description="创建人")
    updated_user = fields.CharField(max_length=16, default=None, null=True, description="更新人")


# 类型变量 ModelType，限定为继承自 Model 的类型
ModelType = TypeVar("ModelType", bound=Model)
# 类型变量 CreateSchemaType，限定为继承自 BaseModel 的类型
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
# 类型变量 UpdateSchemaType，限定为继承自 BaseModel 的类型
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class ScaffoldCrud(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
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

    async def query(self, id: int) -> Optional[ModelType]:
        """
        :param id: 要获取的对象的唯一标识符。
        :return: 与 ID 对应的数据库对象，如果不存在会返回None。
        """
        return await self.model.filter(id=id).first()

    async def select(self, **kwargs) -> Optional[List[ModelType]]:
        """
        :param kwargs: 要获取的对象的关键字。
        :return: 与 kwargs 对应的数据库对象，如果不存在会返回None。
        """
        return await self.model.filter(**kwargs).all()

    async def list(self, page: int, page_size: int, search: Q = Q(),
                   order: Optional[list] = None, related: Optional[list] = None) -> Tuple[int, List[ModelType]]:
        """
        :param page: 页码，从 1 开始。
        :param page_size: 每页的对象数量。
        :param search: 搜索条件，使用 tortoise.expressions.Q 对象。默认为 Q()，表示不进行额外搜索。
        :param order: 排序条件，为一个列表，列表元素为排序字段，默认为空列表，表示不进行排序。
        :param related: 关联字段，为一个列表，所有的外键字段所对应的信息，默认为None，表示没有关联字段或不查询关联字段。
        :return: 一个元组，包含总对象数和该页的对象列表。
        """
        order: list = order or []
        related: list = related or []
        query = self.model.filter(search)
        return await query.count(), await query.offset((page - 1) * page_size).limit(page_size).order_by(
            *order).prefetch_related(*related)

    async def create(self, obj_in: Union[CreateSchemaType, Dict]) -> ModelType:
        """
        :param obj_in: 用于创建新对象的数据，可以是 CreateSchemaType 实例或字典。
        :return: 创建成功的数据库对象。
        """
        if isinstance(obj_in, Dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(warnings=False)
        obj = self.model(**obj_dict)
        await obj.save()
        return obj

    async def update(self, id: int, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        :param id: 要更新的对象的唯一标识符。
        :param obj_in: 用于更新对象的数据，可以是 UpdateSchemaType 实例或字典。
        :return: 更新后的数据库对象。
        """
        obj = await self.get(id=id)
        if isinstance(obj_in, Dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        obj = obj.update_from_dict(obj_dict)
        await obj.save()
        return obj

    async def remove(self, id: int) -> ModelType:
        """
        :param id: 要删除的对象的唯一标识符（如果不存在可能会抛出异常）。
        """
        obj = await self.get(id=id)
        await obj.delete()
        return obj

    async def delete(self, id: int) -> ModelType:
        """
        :param id: 要删除的对象的唯一标识符。
        """
        obj = await self.model.filter(id=id).first()
        if obj:
            await obj.delete()
        return obj


class UpperStr(str):
    @classmethod
    def __get__validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args):
        if v is None:
            return v
        if isinstance(v, str):
            return v.upper()
        return v


class LowerStr(str):
    @classmethod
    def __get__validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args):
        if v is None:
            return v
        if isinstance(v, str):
            return v.lower()
        return v
