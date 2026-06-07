# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : scaffold.py
@DateTime: 2025/1/18 10:48
"""
import asyncio
import traceback
import uuid
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import Any, Dict, Generic, List, Tuple, Type, TypeVar, Union, Optional, Set

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema
from tortoise import fields, models
from tortoise.exceptions import FieldError
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet

from backend.configure import GLOBAL_CONFIG, LOGGER
from backend.core.exceptions import ParameterException, NotFoundException


def unique_identify() -> str:
    """
    生成唯一标识字符串，由时间戳与 UUID 组合而成。

    :returns: 格式为{timestamp}-{uuid4_hex_upper}的唯一标识字符串。
    :rtype: str
    """
    timestamp: int = int(datetime.now().timestamp())
    uuid4_str: str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class ScaffoldModel(models.Model):
    """
    脚手架模型基类，提供通用的模型序列化能力。

    所有业务模型应继承此类，以获得 to_dict 序列化支持。
    支持本表字段的包含/排除/别名，以及外键和多对多关系的递归序列化。
    """
    id = fields.BigIntField(pk=True, description="主键")

    async def to_dict(
            self,
            include_fields: Optional[Union[List[str], Set[str]]] = None,
            exclude_fields: Optional[Union[List[str], Set[str]]] = None,
            replace_fields: Optional[Dict[str, str]] = None,
            m2m: bool = False,
            m2m_include_fields: Optional[Union[List[str], Set[str]]] = None,
            m2m_exclude_fields: Optional[Union[List[str], Set[str]]] = None,
            fk: bool = False,
            fk_include_fields: Optional[Union[List[str], Set[str]]] = None,
            fk_exclude_fields: Optional[Union[List[str], Set[str]]] = None,
    ) -> Dict[str, Any]:
        """
        将模型实例转换为字典形式，支持灵活配置要包含或排除的字段，以及是否处理多对多关系和外键关系。

        :param include_fields: 需要引入的本表字段列表，默认为 None（表示包含所有字段）
        :param exclude_fields: 需要排除的本表字段列表，默认为 None
        :param replace_fields: 字段别名映射，如 {"old_name": "new_name"}
        :param m2m: 是否获取多对多关系字段的数据，默认为 False
        :param m2m_include_fields: 多对多关系中需要引入的字段列表
        :param m2m_exclude_fields: 多对多关系中需要排除的字段列表
        :param fk: 是否获取外键字段对应的数据，默认为 False
        :param fk_include_fields: 外键关系中需要引入的字段列表
        :param fk_exclude_fields: 外键关系中需要排除的字段列表
        :return: 包含模型数据的字典
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
        """
        格式化字段值为可序列化的类型。

        支持的类型转换：
        - Decimal -> str（避免 JSON 序列化错误）
        - datetime/date/time -> str（按全局配置格式化）
        - bytes -> str（UTF-8 解码）
        - timedelta -> str
        """
        if isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, datetime):
            value = value.strftime(GLOBAL_CONFIG.DATETIME_FORMAT2)
        elif isinstance(value, date):
            value = value.strftime(GLOBAL_CONFIG.DATE_FORMAT)
        elif isinstance(value, time):
            value = value.strftime(GLOBAL_CONFIG.TIME_FORMAT)
        elif isinstance(value, bytes):
            value = value.decode("utf-8")
        elif isinstance(value, timedelta):
            value = str(value)
        return value

    async def __fetch_fk_field(self, field, fk_include_fields, fk_exclude_fields):
        """
        获取外键字段关联对象的数据，并将其转换为字典形式。

        :param field: 外键字段名
        :param fk_include_fields: 需要引入的外键表字段列表
        :param fk_exclude_fields: 需要排除的外键表字段列表
        :return: (字段名, 关联对象字典或 None)
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
        获取多对多关系字段的数据，并将其转换为字典列表。

        :param field: 多对多字段名
        :param m2m_include_fields: 需要引入的多对多表字段列表
        :param m2m_exclude_fields: 需要排除的多对多表字段列表
        :return: (字段名, 关联对象字典列表)
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
        """元数据配置"""
        abstract = True  # 抽象基类，不会在数据库中创建表
        default_connection = "default"  # 默认数据库连接


class UUIDModel:
    """UUID 唯一标识 Mixin，为模型添加 uid 字段。"""
    uid = fields.UUIDField(unique=True, description="唯一标识符")


class PacketModel:
    """分组标识 Mixin，为模型添加 pid 字段用于分组。"""
    pid = fields.BigIntField(index=True, description="分组标识符")


class StateModel:
    """
    状态模型 Mixin，为模型添加 state 字段。

    状态约定：
    - 0: 启用/正常
    - 1: 禁用/删除（软删除状态）

    配合 ScaffoldCrud 的软删除方法使用：
        await crud.soft_delete(id=1)      # state = 1
        await crud.soft_delete_restore(id=1)  # state = 0
    """
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")


class ClassModel:
    """分类模型 Mixin，为模型添加代码、名称、描述字段。"""
    code = fields.CharField(max_length=16, unique=True, description="代码")
    name = fields.CharField(max_length=64, unique=True, description="名称")
    description = fields.TextField(null=True, description="描述")


class TimestampMixin:
    """
    时间戳 Mixin，自动记录创建和更新时间。

    - created_time: 记录首次创建时间，不可变
    - updated_time: 每次保存自动更新，可用于记录最后操作时间（如软删除时间）
    """
    created_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_time = fields.DatetimeField(auto_now=True, description="更新时间")


class MaintainMixin:
    """
    维护信息 Mixin，记录数据的创建人和最后更新人。

    - created_user: 记录数据的创建者
    - updated_user: 记录最后修改者（可用于记录软删除操作人）
    """
    created_user = fields.CharField(max_length=16, default=None, null=True, description="创建人员")
    updated_user = fields.CharField(max_length=16, default=None, null=True, description="更新人员")


class ReserveFields:
    """备用字段 Mixin，为模型预留扩展字段。"""
    reserve_1 = fields.CharField(max_length=64, default=None, null=True, description="备用字段1")
    reserve_2 = fields.CharField(max_length=128, default=None, null=True, description="备用字段2")
    reserve_3 = fields.CharField(max_length=255, default=None, null=True, description="备用字段3")


# 类型变量定义，用于泛型约束
# ModelType: 限定为 Tortoise ORM 的 Model 子类
ModelType = TypeVar("ModelType", bound=Model)
# CreateSchemaType: 限定为 Pydantic BaseModel 子类，用于创建操作
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
# UpdateSchemaType: 限定为 Pydantic BaseModel 子类，用于更新操作
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class ScaffoldCrud(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    通用 CRUD 操作基类，基于 Tortoise-ORM 实现。

    提供标准的增删改查操作，以及基于 StateModel 的软删除支持。
    通过泛型参数实现类型安全，子类只需指定 Model 和 Schema 类型。

    类型参数：
        ModelType: 数据库模型类（如 User）
        CreateSchemaType: 创建数据的 Pydantic Schema
        UpdateSchemaType: 更新数据的 Pydantic Schema

    使用示例：
        class UserCrud(ScaffoldCrud[User, UserCreate, UserUpdate]):
            def __init__(self):
                super().__init__(model=User)
    """

    def __init__(self, model: Type[ModelType]):
        """
        初始化 CRUD 实例。

        :param model: 数据库模型类，必须是 ScaffoldModel 的子类
        """
        self.model = model

    # ==================== 查询方法 ====================

    async def get_or_error(self, id: int, **kwargs) -> ModelType:
        """
        根据 ID 获取对象，不存在时抛出异常。

        :param id: 对象唯一标识符
        :param kwargs: 额外的过滤条件
        :return: 数据库模型实例
        :raises DoesNotExist: 对象不存在时抛出
        """
        return await self.model.get(id=id, **kwargs)

    async def get_or_none(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        根据 ID 获取对象，不存在时返回 None。

        :param id: 对象唯一标识符
        :param kwargs: 额外的过滤条件
        :return: 数据库模型实例或 None
        """
        return await self.model.filter(id=id, **kwargs).first()

    async def get_by_conditions(
            self,
            only_one: bool = True,
            on_error: bool = True,
            **kwargs
    ) -> Optional[Union[ModelType, List[ModelType]]]:
        """
        根据条件查询对象。

        :param only_one: True 返回单条记录，False 返回列表
        :param on_error: True 时未找到则抛出 NotFoundException
        :param kwargs: 查询条件字段
        :return: 单条记录、记录列表或 None
        :raises ParameterException: 查询条件字段错误时抛出
        :raises NotFoundException: 未找到记录且 on_error=True 时抛出
        """
        try:
            stmt: QuerySet = self.model.filter(**kwargs)
            instances = await (stmt.first() if only_one else stmt.all())
        except (FieldError, Exception) as e:
            error_message: str = f"根据条件[{kwargs}]查询数据异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"根据条件[{kwargs}]查询数据为空"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def list(
            self,
            page: int,
            page_size: int,
            search: Q = Q(),
            order: Optional[list] = None,
            related: Optional[list] = None
    ) -> Tuple[int, List[ModelType]]:
        """
        分页查询记录列表。

        :param page: 页码，从 1 开始
        :param page_size: 每页记录数
        :param search: 搜索条件，使用 Q 对象组合复杂查询
        :param order: 排序字段列表，如 ["-created_time"] 表示按创建时间倒序
        :param related: 预加载的关联字段列表
        :return: (总记录数, 当前页记录列表)
        """
        order: list = order or []
        related: list = related or []
        query = self.model.filter(search)
        return (
            await query.count(),
            await query.offset((page - 1) * page_size).limit(page_size).order_by(*order).prefetch_related(*related)
        )

    # ==================== 创建和更新方法 ====================

    async def create(self, obj_in: Union[CreateSchemaType, Dict]) -> ModelType:
        """
        创建新记录。

        :param obj_in: 创建数据，可以是 Pydantic Schema 实例或字典
        :return: 创建成功的数据库对象
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
        更新记录。

        :param id: 要更新的记录 ID
        :param obj_in: 更新数据，可以是 Pydantic Schema 实例或字典
        :return: 更新后的数据库对象
        :raises DoesNotExist: 记录不存在时抛出
        """
        obj = await self.get_or_error(id=id)
        if isinstance(obj_in, Dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        obj = obj.update_from_dict(obj_dict)
        await obj.save()
        return obj

    # ==================== 删除方法（物理删除） ====================

    async def remove_or_error(self, id: int, **kwargs) -> ModelType:
        """
        删除记录（物理删除），不存在时抛出异常。

        :param id: 要删除的记录 ID
        :param kwargs: 额外的过滤条件
        :return: 被删除的数据库对象
        :raises DoesNotExist: 记录不存在时抛出
        """
        obj = await self.get_or_error(id=id, **kwargs)
        await obj.delete()
        return obj

    async def hard_delete(self, id: int) -> ModelType:
        """
        硬删除：从数据库中永久移除记录，无论记录是否已软删除（state=1），都将被物理删除。
        :param id: 要硬删除的记录 ID
        :return: 被删除的数据库对象
        :raises DoesNotExist: 记录不存在时抛出
        """
        obj = await self.get_or_error(id=id)
        await obj.delete()
        LOGGER.info(f"硬删除成功: {self.model.__name__}(id={id})")
        return obj

    async def batch_hard_delete(self, ids: List[int]) -> int:
        """
        批量硬删除：从数据库中永久移除多条记录。

        :param ids: 要硬删除的记录 ID 列表
        :return: 实际删除的记录数
        """
        if not ids:
            return 0

        count = await self.model.filter(id__in=ids).delete()
        LOGGER.info(f"批量硬删除成功: {self.model.__name__}, 数量={count}, ids={ids}")
        return count

    # ==================== 软删除方法（基于 StateModel） ====================

    async def soft_delete(self, id: int, updated_user: Optional[str] = None) -> ModelType:
        """
        软删除：将记录标记为已删除（state=1）。

        :param id: 要软删除的记录 ID
        :param updated_user: 执行操作的用户标识（可选）
        :return: 更新后的数据库对象
        :raises NotFoundException: 记录不存在时抛出
        :raises ParameterException: 模型未继承 StateModel 时抛出
        """
        obj = await self.get_or_error(id=id)
        if not hasattr(obj, 'state'):
            error_message: str = f"模型[{self.model.__name__}]未继承 StateModel，无法执行软删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 如果模型有 updated_user 字段，记录删除人
        if updated_user is not None and hasattr(obj, 'updated_user'):
            obj.updated_user = updated_user

        # 保存更新
        obj.state = 1
        await obj.save(update_fields=["state", "updated_user"] if hasattr(obj, 'updated_user') else ["state"])
        LOGGER.info(f"软删除成功: {self.model.__name__}(id={id})")
        return obj

    async def soft_delete_restore(self, id: int, updated_user: Optional[str] = None) -> ModelType:
        """
        恢复软删除的记录（state=0）。

        :param id: 要恢复的记录 ID
        :param updated_user: 执行操作的用户标识（可选）
        :return: 恢复后的数据库对象
        :raises NotFoundException: 记录不存在时抛出
        :raises ParameterException: 模型未继承 StateModel 时抛出
        """
        obj = await self.get_or_error(id=id)

        if not hasattr(obj, 'state'):
            error_message: str = f"模型[{self.model.__name__}]未继承 StateModel，无法执行恢复操作"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 如果模型有 updated_user 字段，记录更新人
        if updated_user is not None and hasattr(obj, 'updated_user'):
            obj.updated_user = updated_user

        obj.state = 0
        await obj.save(update_fields=["state", "updated_user"] if hasattr(obj, 'updated_user') else ["state"])
        LOGGER.info(f"恢复软删除成功: {self.model.__name__}(id={id})")
        return obj

    async def soft_deleted_list(
            self,
            page: int = 1,
            page_size: int = 10,
            search: Q = Q(),
            order: Optional[list] = None
    ) -> Tuple[int, List[ModelType]]:
        """
        查询已软删除的记录列表（state=1）。

        :param page: 页码，从 1 开始
        :param page_size: 每页记录数
        :param search: 额外的搜索条件
        :param order: 排序字段列表，默认按 updated_time 倒序（即最近删除的在前）
        :return: (总记录数, 已删除记录列表)
        :raises ParameterException: 模型未继承 StateModel 时抛出
        """
        if not hasattr(self.model, 'state'):
            error_message: str = f"模型[{self.model.__name__}]未继承 StateModel，无法查询已删除记录"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 强制添加 state=1 条件
        q = Q(state=1) & search
        return await self.list(page=page, page_size=page_size, search=q, order=order or ["-updated_time"])

    async def soft_delete_batch(self, ids: List[int], updated_user: Optional[str] = None) -> int:
        """
        批量软删除（state=1）。

        :param ids: 要软删除的记录 ID 列表
        :param updated_user: 执行操作的用户标识（可选）
        :return: 实际更新的记录数
        :raises ParameterException: 模型未继承 StateModel 时抛出
        """
        if not hasattr(self.model, 'state'):
            error_message: str = f"模型[{self.model.__name__}]未继承 StateModel，无法执行批量软删除"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if not ids:
            return 0

        update_fields: Dict[str, Any] = {"state": 1}
        if hasattr(self.model, 'updated_user') and updated_user is not None:
            update_fields["updated_user"] = updated_user

        count = await self.model.filter(id__in=ids, state__not=1).update(**update_fields)
        LOGGER.info(f"批量软删除成功: {self.model.__name__}, 数量={count}, ids={ids}")
        return count

    async def soft_delete_restore_batch(self, ids: List[int], updated_user: Optional[str] = None) -> int:
        """
        批量恢复软删除的记录（state=0）。

        :param ids: 要恢复的记录 ID 列表
        :param updated_user: 执行操作的用户标识（可选）
        :return: 实际恢复的记录数
        :raises ParameterException: 模型未继承 StateModel 时抛出
        """
        if not hasattr(self.model, 'state'):
            error_message: str = f"模型[{self.model.__name__}]未继承 StateModel，无法执行批量恢复"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if not ids:
            return 0

        update_fields: Dict[str, Any] = {"state": 0}
        if hasattr(self.model, 'updated_user') and updated_user is not None:
            update_fields["updated_user"] = updated_user

        count = await self.model.filter(id__in=ids, state=1).update(**update_fields)
        LOGGER.info(f"批量恢复成功: {self.model.__name__}, 数量={count}, ids={ids}")
        return count


class UpperStr(str):
    """大写字符串类型，用于 Pydantic 模型验证。"""

    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            source_type: Any,
            handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            cls._validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, v: Optional[str], info: Any) -> 'UpperStr':
        """验证并转换为大写字符串"""
        if not isinstance(v, str):
            raise ValueError("必须是字符串类型")
        return cls(v.upper())


class LowerStr(str):
    """小写字符串类型，用于 Pydantic 模型验证。"""

    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            source_type: Any,
            handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            cls._validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, v: Optional[str], info: Any) -> 'LowerStr':
        """验证并转换为小写字符串"""
        if not isinstance(v, str):
            raise ValueError("必须是字符串类型")
        return cls(v.lower())
