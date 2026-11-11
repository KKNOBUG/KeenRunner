# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : scaffold.py
@DateTime: 2025/1/18 10:48
"""
import asyncio
import traceback
import uuid
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import Any
from typing import Dict, Generic, List, Tuple, Type, TypeVar, Union, Optional, Set

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema
from tortoise import fields, models
from tortoise.exceptions import DoesNotExist, OperationalError
from tortoise.expressions import Q
from tortoise.fields import JSONField
from tortoise.models import Model
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from backend.configure import GLOBAL_CONFIG, LOGGER
from backend.core.exceptions import ParameterException, NotFoundException, DataBaseStorageException


def unique_identify() -> str:
    """
    生成唯一标识字符串。

    时间戳保证趋势递增，随机 UUID 保证同一秒内不重复。

    :return: 时间戳与大写 UUID 以连字符拼接的字符串
    """
    timestamp: int = int(datetime.now().timestamp())
    uuid4_str: str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


class UpperStr(str):
    """
    大写字符串类型，用于 Pydantic 模型校验。

    非字符串输入直接判定校验失败，字符串一律转为大写后返回。
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """
        注册校验后置处理器。

        先由父类型完成字符串校验，再交由本类完成大小写转换。

        :param source_type: 声明类型，此处固定为字符串
        :param handler: 父类型 schema 生成器
        :return: 带后置校验的字符串 schema
        """
        return core_schema.with_info_after_validator_function(
            cls._validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, v: Optional[str], info: Any) -> 'UpperStr':
        """
        校验入参为字符串并转换为大写。

        :param v: 待校验的字符串
        :param info: 校验上下文，本方法不使用
        :return: 转大写后的字符串
        """
        if not isinstance(v, str):
            raise ValueError("必须是字符串类型")
        return cls(v.upper())


class LowerStr(str):
    """
    小写字符串类型，用于 Pydantic 模型校验。

    非字符串输入直接判定校验失败，字符串一律转为小写后返回。
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """
        注册校验后置处理器。

        先由父类型完成字符串校验，再交由本类完成大小写转换。

        :param source_type: 声明类型，此处固定为字符串
        :param handler: 父类型 schema 生成器
        :return: 带后置校验的字符串 schema
        """
        return core_schema.with_info_after_validator_function(
            cls._validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, v: Optional[str], info: Any) -> 'LowerStr':
        """
        校验入参为字符串并转换为小写。

        :param v: 待校验的字符串
        :param info: 校验上下文，本方法不使用
        :return: 转小写后的字符串
        """
        if not isinstance(v, str):
            raise ValueError("必须是字符串类型")
        return cls(v.lower())


class UpperCharField(fields.CharField):
    """
    大写字符串字段。

    写入数据库与从数据库读出时均自动转为大写，保证库内外口径一致。
    """

    def to_db_value(self, value: Any, instance) -> Optional[str]:
        """
        写入数据库前将字符串转为大写。

        :param value: 待写入的字段值
        :param instance: 字段所属模型实例
        :return: 转大写后的字段值
        """
        if isinstance(value, str):
            value = value.upper()
        return super().to_db_value(value, instance)

    def to_python_value(self, value: Any) -> Optional[str]:
        """
        从数据库读出后将字符串转为大写。

        :param value: 数据库中的原始值
        :return: 转大写后的字段值
        """
        value = super().to_python_value(value)
        if isinstance(value, str):
            return value.upper()
        return value


class LowerCharField(fields.CharField):
    """
    小写字符串字段。

    写入数据库与从数据库读出时均自动转为小写，保证库内外口径一致。
    """

    def to_db_value(self, value: Any, instance) -> Optional[str]:
        """
        写入数据库前将字符串转为小写。

        :param value: 待写入的字段值
        :param instance: 字段所属模型实例
        :return: 转小写后的字段值
        """
        if isinstance(value, str):
            value = value.lower()
        return super().to_db_value(value, instance)

    def to_python_value(self, value: Any) -> Optional[str]:
        """
        从数据库读出后将字符串转为小写。

        :param value: 数据库中的原始值
        :return: 转小写后的字段值
        """
        value = super().to_python_value(value)
        if isinstance(value, str):
            return value.lower()
        return value


class JSONTextField(JSONField):
    """
    以文本列存储 JSON 数据的字段。

    MySQL 的 JSON 列落库时会按键长度与字节值重排对象键，导致字段顺序丢失；
    该字段改用文本列原样保存序列化结果，读出时由父类完成反序列化。
    """

    # 覆盖父类的列类型，避免 MySQL 对 JSON 列做键重排
    SQL_TYPE = "LONGTEXT"

    def to_python_value(self, value: Any) -> Any:
        """
        将库内文本反序列化为 Python 对象。

        空串视为未赋值，直接返回空值，其余交给父类解析。

        :param value: 数据库中的原始文本
        :return: 反序列化后的对象或空值
        """
        if isinstance(value, str) and not value.strip():
            return None
        return super().to_python_value(value)


class UUIDModel:
    """
    为模型提供唯一标识字段的混入类。

    字段可空且唯一，允许历史数据不携带该标识。
    """
    uid = fields.UUIDField(unique=True, null=True, description="唯一标识符")


class PacketModel:
    """
    为模型提供分组标识字段的混入类。

    字段建立索引且不允许为空，用于按分组聚合查询。
    """
    pid = fields.BigIntField(index=True, description="分组标识符")


class StateModel:
    """
    为模型提供软删除标记字段的混入类。

    字段为 0 表示启用，为 1 表示禁用，软删除与恢复由 ScaffoldCrud 的对应方法维护。
    """
    state = fields.SmallIntField(default=0, index=True, description="状态(0:启用, 1:禁用)")


class ClassModel:
    """
    为模型提供代码、名称与描述字段的混入类。

    代码与名称均唯一，描述可空，适合字典类业务表。
    """
    code = fields.CharField(max_length=16, unique=True, description="代码")
    name = fields.CharField(max_length=64, unique=True, description="名称")
    description = fields.TextField(null=True, description="描述")


class TimestampMixin:
    """
    为模型提供创建时间与更新时间字段的混入类。

    创建时间仅在首次写入时记录，更新时间每次保存自动刷新，可用于记录最后操作时间。
    """
    created_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_time = fields.DatetimeField(auto_now=True, description="更新时间")


class MaintainMixin:
    """
    为模型提供创建人与更新人字段的混入类。

    字段写入时自动转大写；创建时更新人与创建人同值回填，对齐更新时间的自动刷新语义。
    """
    created_user = UpperCharField(max_length=16, default=None, null=True, description="创建人员")
    updated_user = UpperCharField(max_length=16, default=None, null=True, description="更新人员")


class ReserveFields:
    """
    为模型提供预留扩展字段的混入类。

    三个字段均可空，依次覆盖短文本、结构化数据与长文本三种存储需求。
    """
    reserve_1 = fields.CharField(max_length=255, default=None, null=True, description="备用字段1")
    reserve_2 = fields.JSONField(default=None, null=True, description="备用字段2")
    reserve_3 = fields.TextField(default=None, null=True, description="备用字段3")


class ScaffoldModel(models.Model):
    """
    脚手架模型基类，提供通用的模型序列化能力。

    业务模型继承后即可按需输出本表字段、外键对象与多对多集合，并支持字段裁剪与字段改名。
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
            m2m_replace_fields: Optional[Dict[str, Dict[str, str]]] = None,
            fk: bool = False,
            fk_include_fields: Optional[Union[List[str], Set[str]]] = None,
            fk_exclude_fields: Optional[Union[List[str], Set[str]]] = None,
            _cache: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        将模型实例序列化为字典。

        默认输出全部本表字段，可按需裁剪或改名；外键与多对多关系需显式开启后才会展开。
        同一实例在单次调用链内命中缓存时直接返回，缓存键为实例内存地址，不跨请求共享。

        :param include_fields: 需要输出的本表字段，为空表示全部字段
        :param exclude_fields: 需要排除的本表字段
        :param replace_fields: 本表字段别名映射，键为原字段名，值为输出字段名
        :param m2m: 是否展开多对多关系
        :param m2m_include_fields: 多对多关联对象需要输出的字段
        :param m2m_exclude_fields: 多对多关联对象需要排除的字段
        :param m2m_replace_fields: 按多对多字段名指定的关联对象字段别名映射
        :param fk: 是否展开外键关系
        :param fk_include_fields: 外键关联对象需要输出的字段
        :param fk_exclude_fields: 外键关联对象需要排除的字段
        :param _cache: 内部缓存字典，外部调用无需传入
        :return: 模型数据字典
        """
        # 初始化缓存
        cache = _cache or {}
        instance_id = id(self)

        # 检查缓存：如果该实例已经序列化过，直接返回缓存结果
        if instance_id in cache:
            return cache[instance_id]

        # 若未提供排除字段列表，则初始化为空列表
        exclude_fields = exclude_fields or []
        m2m_exclude_fields = m2m_exclude_fields or []
        fk_exclude_fields = fk_exclude_fields or []

        d = {}
        # 获取本表字段并根据include_fields参数确定要处理的字段列表
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

        # 如果fk为True，异步获取外键字段关联的数据
        if fk:
            tasks = [
                self.__fetch_fk_field(field, fk_include_fields, fk_exclude_fields, cache)
                for field in self._meta.fk_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        # 如果m2m为True，异步获取多对多关系字段的数据
        if m2m:
            tasks = [
                self.__fetch_m2m_field(field, m2m_include_fields, m2m_exclude_fields, m2m_replace_fields, cache)
                for field in self._meta.m2m_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        # 存入缓存
        cache[instance_id] = d
        return d

    @classmethod
    async def __format_value(cls, value: Any):
        """
        将字段值转换为可序列化类型。

        Decimal 与 timedelta 转为字符串，日期时间按全局格式转为字符串，字节按 UTF-8 解码；
        其余类型原样返回。

        :param value: 字段原始值
        :return: 可直接写入字典的值
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

    async def __fetch_fk_field(self, field, fk_include_fields, fk_exclude_fields, cache):
        """
        展开单个外键字段。

        关联对象存在时递归序列化，递归过程中禁止继续展开多对多与外键，避免环形引用导致无限递归。

        :param field: 外键字段名
        :param fk_include_fields: 关联对象需要输出的字段
        :param fk_exclude_fields: 关联对象需要排除的字段
        :param cache: 序列化缓存，避免同一对象重复查询
        :return: 字段名与关联对象字典，关联对象为空时字典为空值
        """
        fk_instance = getattr(self, field)
        if fk_instance:
            return field, await fk_instance.to_dict(
                include_fields=fk_include_fields,
                exclude_fields=fk_exclude_fields,
                m2m=False,  # 避免无限递归
                fk=False,  # 根据需求调整
                _cache=cache  # 传递缓存
            )
        return field, None

    async def __fetch_m2m_field(self, field, m2m_include_fields, m2m_exclude_fields, m2m_replace_fields, cache):
        """
        展开单个多对多字段。

        逐个序列化关联对象并汇总为列表，递归过程中禁止继续展开，别名映射按当前多对多字段名透传。

        :param field: 多对多字段名
        :param m2m_include_fields: 关联对象需要输出的字段
        :param m2m_exclude_fields: 关联对象需要排除的字段
        :param m2m_replace_fields: 按多对多字段名指定的关联对象字段别名映射
        :param cache: 序列化缓存，避免同一对象重复查询
        :return: 字段名与关联对象字典列表
        """
        instances = await getattr(self, field).all()
        values = []
        for instance in instances:
            value = await instance.to_dict(
                include_fields=m2m_include_fields,
                exclude_fields=m2m_exclude_fields,
                # 透传该m2m字段的别名映射，保证嵌套关联对象与顶层一样以*_id形式返回主键
                replace_fields=(m2m_replace_fields or {}).get(field),
                m2m=False,  # 避免无限递归
                fk=False,  # 根据需求调整
                _cache=cache  # 传递缓存
            )
            values.append(value)
        return field, values

    class Meta:
        """
        模型元数据。

        作为抽象基类不建表，统一使用默认数据库连接。
        """
        abstract = True  # 抽象基类，不会在数据库中创建表
        default_connection = "default"  # 默认数据库连接


# 类型变量定义，用于泛型约束
# ModelType: 限定为 Tortoise ORM 的 Model 子类
ModelType = TypeVar("ModelType", bound=Model)
# CreateSchemaType: 限定为 Pydantic BaseModel 子类，用于创建操作
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
# UpdateSchemaType: 限定为 Pydantic BaseModel 子类，用于更新操作
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class ScaffoldCrud(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    通用 CRUD 操作基类，基于 Tortoise ORM 实现。

    提供标准的增删改查、批量操作、事务写入与基于状态字段的软删除能力，子类只需绑定
    模型与读写 Schema 即可复用；模型未继承状态混入类时，软删除相关方法直接拒绝执行。

    泛型参数依次为数据库模型、创建 Schema 与更新 Schema。
    """

    def __init__(self, model: Type[ModelType]):
        """
        绑定业务模型。

        :param model: 数据库模型类，决定后续所有操作的默认表
        """
        # 子类无需重复声明模型，统一由构造函数注入
        self.model = model

    @staticmethod
    def normalize_order_fields(order: Optional[list]) -> list:
        """
        规范化排序字段列表。

        过滤空值与空白项，剔除仅由正负号构成的无效项；非字符串元素直接拒绝。

        :param order: 原始排序字段列表
        :return: 可用于排序的字段列表
        """
        if not order:
            return []
        cleaned: list = []
        for index, item in enumerate(order):
            if item is None:
                continue
            if not isinstance(item, str):
                error_message: str = "排序字段必须为字符串，请检查排序参数的写法"
                LOGGER.warning(
                    f"{error_message}, "
                    f"关键字段: [index={index}, type={type(item).__name__}]"
                )
                raise ParameterException(message=error_message)
            field = item.strip()
            if not field or field in ("-", "+"):
                continue
            cleaned.append(field)
        return cleaned

    def fill_created_user(self, obj_dict: Dict[str, Any], model: Optional[Type[Model]] = None) -> None:
        """
        创建时写入创建人与更新人。

        登录上下文存在时以服务端当前用户为准，否则沿用入参值；模型不含相应字段时直接跳过。

        :param obj_dict: 待写入字段字典，就地修改
        :param model: 目标模型，默认使用当前绑定的模型
        :return: 无返回值，结果直接写入入参字典
        """
        target = model or self.model
        if not hasattr(target, "created_user"):
            return

        # 惰性导入，避免 scaffold ↔ services.dependency 循环依赖
        from backend.services.ctx import get_current_username, normalize_username
        username = get_current_username()
        if username:
            obj_dict["created_user"] = username
        else:
            existing = obj_dict.get("created_user")
            if isinstance(existing, str) and existing.strip():
                obj_dict["created_user"] = normalize_username(existing)

        if hasattr(target, "updated_user") and not obj_dict.get("updated_user"):
            created = obj_dict.get("created_user")
            if created:
                obj_dict["updated_user"] = created

    def fill_updated_user(self, obj_dict: Dict[str, Any], model: Optional[Type[Model]] = None) -> None:
        """
        更新时写入更新人。

        登录上下文存在时以服务端当前用户为准，否则保留入参中的显式取值；模型不含该字段时直接跳过。

        :param obj_dict: 待写入字段字典，就地修改
        :param model: 目标模型，默认使用当前绑定的模型
        :return: 无返回值，结果直接写入入参字典
        """
        target = model or self.model
        if not hasattr(target, "updated_user"):
            return

        from backend.services.ctx import get_current_username, normalize_username
        username = get_current_username()
        if username:
            obj_dict["updated_user"] = username
            return

        existing = obj_dict.get("updated_user")
        if isinstance(existing, str) and existing.strip():
            obj_dict["updated_user"] = normalize_username(existing)

    @staticmethod
    def explicit_restored_null_fields(payload: Any, update_dict: Dict[str, Any], field_names: Tuple[str, ...]) -> None:
        """
        将显式置空的字段回补到更新字典。

        更新模型常以排除空值方式导出，字段被显式置空时会被丢弃，导致库内旧值残留；
        本方法根据入参的显式字段集合把空值写回更新字典。

        :param payload: 更新入参模型
        :param update_dict: 更新字典，就地修改
        :param field_names: 需要检查并回补的字段名
        :return: 无返回值，结果直接写入更新字典
        """
        for field_name in field_names:
            if field_name in payload.model_fields_set and getattr(payload, field_name, None) is None:
                update_dict[field_name] = None

    def soft_delete_values(self, updated_user: Optional[str] = None) -> Dict[str, Any]:
        """
        构造软删除的更新字典。

        固定写入禁用状态，并按统一规则填充更新人；登录上下文缺失时使用入参回落。

        :param updated_user: 无登录上下文时回落的更新人
        :return: 可直接用于条件更新的字段字典
        """
        values: Dict[str, Any] = {"state": 1}
        if updated_user is not None and str(updated_user).strip():
            values["updated_user"] = updated_user
        self.fill_updated_user(values)
        if not hasattr(self.model, "updated_user"):
            values.pop("updated_user", None)
        return values

    def soft_restore_values(self, updated_user: Optional[str] = None) -> Dict[str, Any]:
        """
        构造软删除恢复的更新字典。

        固定写入启用状态，并按统一规则填充更新人；登录上下文缺失时使用入参回落。

        :param updated_user: 无登录上下文时回落的更新人
        :return: 可直接用于条件更新的字段字典
        """
        values: Dict[str, Any] = {"state": 0}
        if updated_user is not None and str(updated_user).strip():
            values["updated_user"] = updated_user
        self.fill_updated_user(values)
        if not hasattr(self.model, "updated_user"):
            values.pop("updated_user", None)
        return values

    async def get_or_error(self, id: int, **kwargs) -> ModelType:
        """
        按主键获取单条记录。

        记录不存在时转为记录不存在异常，存在则原样返回。

        :param id: 记录主键
        :param kwargs: 额外的过滤条件
        :return: 数据库模型实例
        """
        try:
            return await self.model.get(id=id, **kwargs)
        except DoesNotExist as e:
            error_message: str = "查询目标数据不存在或已被删除，请刷新后重试"
            LOGGER.warning(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, id={id}, conditions={kwargs}]"
            )
            raise NotFoundException(message=error_message) from e

    async def get_or_none(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        按主键获取单条记录。

        与 get_or_error 的区别是记录不存在时返回空值而不抛出异常。

        :param id: 记录主键
        :param kwargs: 额外的过滤条件
        :return: 数据库模型实例或空值
        """
        return await self.model.filter(id=id, **kwargs).first()

    async def get_by_conditions(self, only_one: bool = True, on_error: bool = True, **kwargs) -> Optional[Union[ModelType, List[ModelType]]]:
        """
        按条件查询单条记录或记录列表。

        查询条件直接映射为模型字段过滤，字段不合法或数据库执行失败统一转为参数异常；
        查询结果为空且要求报错时转为记录不存在异常，否则原样返回空值。

        :param only_one: 是否只取首条记录
        :param on_error: 结果为空时是否抛出记录不存在异常
        :param kwargs: 查询条件字段
        :return: 单条记录、记录列表或空值
        """
        try:
            stmt: QuerySet = self.model.filter(**kwargs)
            instances = await (stmt.first() if only_one else stmt.all())
        except Exception as e:
            error_message: str = "查询数据失败，请检查查询条件后重试"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, only_one={only_one}, conditions={kwargs}]\n"
                f"{traceback.format_exc()}"
            )
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = "查询目标数据不存在或已被删除，请刷新后重试"
            LOGGER.warning(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, only_one={only_one}, conditions={kwargs}]"
            )
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
        按条件分页查询记录列表。

        排序字段先经规范化，非法排序字段直接拒绝；总数与当前页数据同查询一起返回。

        :param page: 页码，从 1 开始
        :param page_size: 每页记录数
        :param search: 搜索条件，使用 Q 对象组合复杂查询
        :param order: 排序字段列表，字段名前缀减号表示倒序
        :param related: 需要预加载的关联字段列表
        :return: 记录总数与当前页记录列表
        """
        order: list = self.normalize_order_fields(order)
        related: list = related or []
        query = self.model.filter(search)
        return (
            await query.count(),
            await query.offset((page - 1) * page_size).limit(page_size).order_by(*order).prefetch_related(*related)
        )

    async def create(self, obj_in: Union[CreateSchemaType, Dict]) -> ModelType:
        """
        创建单条记录。

        入参为字典时直接使用，为 Schema 实例时先导出为字典；创建人与更新人按统一规则补齐。

        :param obj_in: 创建数据，Pydantic Schema 实例或字典
        :return: 创建成功的数据库对象
        """
        if isinstance(obj_in, Dict):
            obj_dict = dict(obj_in)
        else:
            obj_dict = obj_in.model_dump(warnings=False)
        self.fill_created_user(obj_dict)
        obj = self.model(**obj_dict)
        await obj.save()
        return obj

    async def batch_create(self, obj_list: List[Union[CreateSchemaType, Dict]]) -> List[ModelType]:
        """
        批量创建记录。

        所有记录合并为一次批量写入；返回对象仅携带入参字段与模型默认值，数据库生成的主键不回填。

        :param obj_list: 创建数据列表，元素为 Pydantic Schema 实例或字典
        :return: 创建成功的数据库对象列表
        """
        if not obj_list:
            return []

        instances = []
        for obj_in in obj_list:
            if isinstance(obj_in, Dict):
                obj_dict = dict(obj_in)
            else:
                obj_dict = obj_in.model_dump(warnings=False)
            self.fill_created_user(obj_dict)
            instances.append(self.model(**obj_dict))

        await self.model.bulk_create(instances)
        LOGGER.info(f"批量创建成功, 关键字段: [model={self.model.__name__}, count={len(instances)}]")
        return instances

    async def update(self, id: int, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        """
        更新单条记录。

        记录不存在时抛出记录不存在异常；并发修改唯一值时把死锁与锁等待超时转为可重试的存储异常。

        :param id: 记录主键
        :param obj_in: 更新数据，Pydantic Schema 实例或字典
        :return: 更新后的数据库对象
        """
        obj = await self.get_or_error(id=id)
        if isinstance(obj_in, Dict):
            obj_dict = dict(obj_in)
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        self.fill_updated_user(obj_dict)
        obj = obj.update_from_dict(obj_dict)
        try:
            await obj.save()
        except OperationalError as e:
            # 并发改唯一值时 InnoDB 可能抛死锁(1213)/锁等待超时(1205)，转为可重试的存储异常
            raw = e.args[0] if e.args else None
            errno = raw.args[0] if isinstance(raw, BaseException) and getattr(raw, "args", None) else None
            if errno in (1213, 1205):
                error_message: str = "更新数据失败，操作存在并发冲突，请稍后重试"
                LOGGER.error(
                    f"{error_message}, "
                    f"关键字段: [model={self.model.__name__}, id={id}, errno={errno}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e
            raise
        LOGGER.info(f"更新成功, 关键字段: [model={self.model.__name__}, id={id}, fields={list(obj_dict.keys())}]")
        return obj

    async def batch_update(self, updates: List[Dict[str, Any]], key_field: str = "id", strict: bool = True) -> int:
        """
        批量更新记录。

        逐条按条件字段更新，缺少条件字段的记录直接跳过；字段不合法时按严格模式决定跳过整条
        还是忽略越界字段后继续。

        :param updates: 更新数据列表，每项必须包含条件字段
        :param key_field: 作为更新条件的字段名
        :param strict: 字段不合法时是否跳过整条记录
        :return: 实际更新的记录数
        """
        if not updates:
            return 0

        # 获取模型有效字段列表
        valid_fields = set(self.model._meta.db_fields)
        valid_fields.update(self.model._meta.fk_fields)

        total_updated = 0
        for index, update_data in enumerate(updates):
            key_value = update_data.get(key_field)
            if not key_value:
                LOGGER.warning(
                    f"批量更新跳过, 缺少条件字段, "
                    f"关键字段: [model={self.model.__name__}, index={index}, key_field={key_field}]"
                )
                continue

            # 移除条件字段
            update_dict = {k: v for k, v in update_data.items() if k != key_field}

            # 校验字段
            invalid_fields = set(update_dict.keys()) - valid_fields
            if invalid_fields:
                if strict:
                    LOGGER.warning(
                        f"批量更新跳过, 包含不存在的字段, "
                        f"关键字段: [model={self.model.__name__}, id={key_value}, invalid_fields={invalid_fields}]"
                    )
                    continue
                else:
                    LOGGER.warning(
                        f"批量更新忽略字段, "
                        f"关键字段: [model={self.model.__name__}, id={key_value}, invalid_fields={invalid_fields}]"
                    )
                    for field in invalid_fields:
                        update_dict.pop(field, None)

            if not update_dict:
                continue

            self.fill_updated_user(update_dict)

            # 执行更新
            count = await self.model.filter(**{key_field: key_value}).update(**update_dict)
            total_updated += count

        LOGGER.info(f"批量更新成功, 关键字段: [model={self.model.__name__}, count={total_updated}]")
        return total_updated

    async def remove_or_error(self, id: int, **kwargs) -> ModelType:
        """
        删除单条记录。

        记录不存在时抛出记录不存在异常，删除为物理删除。

        :param id: 记录主键
        :param kwargs: 额外的过滤条件
        :return: 被删除的数据库对象
        """
        obj = await self.get_or_error(id=id, **kwargs)
        await obj.delete()
        LOGGER.info(f"删除成功, 关键字段: [model={self.model.__name__}, id={id}]")
        return obj

    async def hard_delete(self, id: int) -> ModelType:
        """
        物理删除单条记录。

        不区分记录是否已被软删除，一律从数据库中移除。

        :param id: 记录主键
        :return: 被删除的数据库对象
        """
        obj = await self.get_or_error(id=id)
        await obj.delete()
        LOGGER.info(f"硬删除成功, 关键字段: [model={self.model.__name__}, id={id}]")
        return obj

    async def hard_batch_delete(self, ids: List[int]) -> int:
        """
        批量物理删除记录。

        不区分记录是否已被软删除，一律从数据库中移除。

        :param ids: 记录主键列表
        :return: 实际删除的记录数
        """
        if not ids:
            return 0

        count = await self.model.filter(id__in=ids).delete()
        LOGGER.info(f"批量硬删除成功, 关键字段: [model={self.model.__name__}, count={count}, ids={ids}]")
        return count

    def query(self) -> 'QueryBuilder[ModelType]':
        """
        获取查询构建器。

        构建器支持链式添加过滤、排序与分页条件，执行时才真正访问数据库。

        :return: 查询构建器实例
        """
        return QueryBuilder(self.model)

    async def count(self, search: Q = Q()) -> int:
        """
        统计符合条件的记录数量。

        :param search: 搜索条件
        :return: 记录数量
        """
        return await self.model.filter(search).count()

    async def exists(self, **kwargs) -> bool:
        """
        判断是否存在符合条件的记录。

        :param kwargs: 查询条件字段
        :return: 存在返回真，否则返回假
        """
        return await self.model.filter(**kwargs).exists()

    async def aggregate(self, search: Q = Q(), **aggregations) -> Dict[str, Any]:
        """
        执行聚合查询。

        支持求和、均值、最大值、最小值与计数，结果键与入参聚合表达式同名；无匹配记录时
        每个结果键的值为空。

        :param search: 搜索条件
        :param aggregations: 聚合表达式，键为结果字段名
        :return: 聚合结果字典
        """

        query = self.model.filter(search)
        result = await query.annotate(**aggregations).first()

        if result:
            return {
                key: getattr(result, key)
                for key in aggregations.keys()
            }
        return {key: None for key in aggregations.keys()}

    async def group_by(self, field: str, search: Q = Q(), **aggregations) -> List[Dict[str, Any]]:
        """
        按指定字段分组统计。

        每条结果同时包含分组字段与各聚合表达式的结果，目前仅支持单个分组字段。

        :param field: 分组字段
        :param search: 搜索条件
        :param aggregations: 聚合表达式，键为结果字段名
        :return: 分组统计结果列表
        """

        query = self.model.filter(search).group_by(field)
        results = await query.annotate(**aggregations).values(field, *aggregations.keys())

        return results

    @staticmethod
    def transactional(func):
        """
        将异步函数包装进数据库事务。

        被装饰函数会收到注入的数据库连接关键字参数，函数抛出异常时事务整体回滚。

        :param func: 要包装的异步函数
        :return: 包装后的函数
        """

        async def wrapper(*args, **kwargs):
            """
            在数据库事务中执行被装饰函数，并将连接注入kwargs。

            :param args: 原函数位置参数
            :param kwargs: 原函数关键字参数；执行前注入_connection
            :return: 原函数返回值
            """
            async with in_transaction() as connection:
                # 将 connection 注入 kwargs，供被装饰函数使用
                kwargs['_connection'] = connection
                return await func(*args, **kwargs)

        return wrapper

    async def create_with_related(
            self,
            obj_in: Union[CreateSchemaType, Dict],
            related_data: Optional[Dict[str, List[Union[BaseModel, Dict]]]] = None
    ) -> ModelType:
        """
        在事务中创建主记录及其关联数据。

        主记录与关联记录共用同一连接，任一步失败整体回滚；关联模型含维护字段时同样补齐
        创建人与更新人。

        :param obj_in: 主记录创建数据
        :param related_data: 关联数据，键为关联字段名，值为待创建记录列表
        :return: 创建成功的主记录对象
        """
        async with in_transaction() as connection:
            # 创建主记录
            if isinstance(obj_in, Dict):
                obj_dict = dict(obj_in)
            else:
                obj_dict = obj_in.model_dump(warnings=False)
            self.fill_created_user(obj_dict)
            obj = self.model(**obj_dict)
            await obj.save(using_db=connection)

            # 创建关联数据
            if related_data:
                for field_name, items in related_data.items():
                    related_manager = getattr(obj, field_name)
                    related_model = (
                            getattr(related_manager, "remote_model", None)
                            or getattr(related_manager, "model", None)
                    )
                    for item in items:
                        if isinstance(item, Dict):
                            item_dict = dict(item)
                        else:
                            item_dict = item.model_dump(warnings=False)
                        # 关联模型若含维护字段，同样按当前用户规则补齐（CTX 优先覆盖）
                        if related_model is None or hasattr(related_model, "created_user"):
                            self.fill_created_user(item_dict, model=related_model)
                        await related_manager.create(**item_dict, using_db=connection)

            LOGGER.info(f"事务创建成功, 关键字段: [model={self.model.__name__}, id={obj.id}]")
            return obj

    async def update_with_related(
            self,
            id: int,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]],
            related_updates: Optional[Dict[str, List[Dict[str, Any]]]] = None
    ) -> ModelType:
        """
        在事务中更新主记录及其关联数据。

        主记录与关联记录共用同一连接，任一步失败整体回滚；关联项缺少主键时跳过。

        :param id: 主记录主键
        :param obj_in: 主记录更新数据
        :param related_updates: 关联数据，键为关联字段名，值为带主键与更新字段的列表
        :return: 更新后的主记录对象
        """
        async with in_transaction() as connection:
            # 更新主记录
            obj = await self.get_or_error(id=id)
            if isinstance(obj_in, Dict):
                obj_dict = dict(obj_in)
            else:
                obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
            self.fill_updated_user(obj_dict)
            obj = obj.update_from_dict(obj_dict)
            await obj.save(using_db=connection)

            # 更新关联数据
            if related_updates:
                for field_name, items in related_updates.items():
                    related_manager = getattr(obj, field_name)
                    related_model = (
                            getattr(related_manager, "remote_model", None)
                            or getattr(related_manager, "model", None)
                    )
                    for item in items:
                        item_id = item.get("id")
                        item_data = dict(item.get("data", {}) or {})
                        if item_id:
                            if related_model is None or hasattr(related_model, "updated_user"):
                                self.fill_updated_user(item_data, model=related_model)
                            await related_manager.filter(id=item_id).update(**item_data, using_db=connection)

            LOGGER.info(f"事务更新成功, 关键字段: [model={self.model.__name__}, id={id}]")
            return obj

    async def soft_delete(self, id: int, updated_user: Optional[str] = None) -> ModelType:
        """
        软删除单条记录。

        模型未继承状态混入类时拒绝执行；仅更新状态与更新人字段。

        :param id: 记录主键
        :param updated_user: 无登录上下文时回落的更新人
        :return: 更新后的数据库对象
        """
        obj = await self.get_or_error(id=id)
        if not hasattr(obj, 'state'):
            error_message: str = "当前功能暂不可用，请联系管理员处理"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, id={id}, action=soft_delete]"
            )
            raise DataBaseStorageException(message=error_message)

        values = self.soft_delete_values(updated_user=updated_user)
        for key, value in values.items():
            setattr(obj, key, value)
        await obj.save(update_fields=list(values.keys()))
        LOGGER.info(f"软删除成功, 关键字段: [model={self.model.__name__}, id={id}]")
        return obj

    async def soft_delete_restore(self, id: int, updated_user: Optional[str] = None) -> ModelType:
        """
        恢复已软删除的单条记录。

        模型未继承状态混入类时拒绝执行；仅更新状态与更新人字段。

        :param id: 记录主键
        :param updated_user: 无登录上下文时回落的更新人
        :return: 恢复后的数据库对象
        """
        obj = await self.get_or_error(id=id)

        if not hasattr(obj, 'state'):
            error_message: str = "当前功能暂不可用，请联系管理员处理"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, id={id}, action=soft_delete_restore]"
            )
            raise DataBaseStorageException(message=error_message)

        values = self.soft_restore_values(updated_user=updated_user)
        for key, value in values.items():
            setattr(obj, key, value)
        await obj.save(update_fields=list(values.keys()))
        LOGGER.info(f"恢复软删除成功, 关键字段: [model={self.model.__name__}, id={id}]")
        return obj

    async def soft_deleted_list(
            self,
            page: int = 1,
            page_size: int = 10,
            search: Q = Q(),
            order: Optional[list] = None
    ) -> Tuple[int, List[ModelType]]:
        """
        分页查询已软删除的记录。

        状态条件由方法强制注入，入参搜索条件与之取交集。

        :param page: 页码，从 1 开始
        :param page_size: 每页记录数
        :param search: 额外的搜索条件
        :param order: 排序字段列表
        :return: 记录总数与已删除记录列表
        """
        if not hasattr(self.model, 'state'):
            error_message: str = "当前功能暂不可用，请联系管理员处理"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, action=soft_deleted_list]"
            )
            raise DataBaseStorageException(message=error_message)

        # 强制添加 state=1 条件
        q = Q(state=1) & search
        return await self.list(page=page, page_size=page_size, search=q, order=order)

    async def soft_delete_batch(self, ids: List[int], updated_user: Optional[str] = None) -> int:
        """
        批量软删除记录。

        模型未继承状态混入类时拒绝执行；已处于删除状态的记录不重复更新。

        :param ids: 记录主键列表
        :param updated_user: 无登录上下文时回落的更新人
        :return: 实际更新的记录数
        """
        if not hasattr(self.model, 'state'):
            error_message: str = "当前功能暂不可用，请联系管理员处理"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, ids={ids}, action=soft_delete_batch]"
            )
            raise DataBaseStorageException(message=error_message)

        if not ids:
            return 0

        update_fields = self.soft_delete_values(updated_user=updated_user)
        count = await self.model.filter(id__in=ids, state__not=1).update(**update_fields)
        LOGGER.info(f"批量软删除成功, 关键字段: [model={self.model.__name__}, count={count}, ids={ids}]")
        return count

    async def soft_delete_restore_batch(self, ids: List[int], updated_user: Optional[str] = None) -> int:
        """
        批量恢复已软删除的记录。

        模型未继承状态混入类时拒绝执行；仅更新处于删除状态的记录。

        :param ids: 记录主键列表
        :param updated_user: 无登录上下文时回落的更新人
        :return: 实际恢复的记录数
        """
        if not hasattr(self.model, 'state'):
            error_message: str = "当前功能暂不可用，请联系管理员处理"
            LOGGER.error(
                f"{error_message}, "
                f"关键字段: [model={self.model.__name__}, ids={ids}, action=soft_delete_restore_batch]"
            )
            raise DataBaseStorageException(message=error_message)

        if not ids:
            return 0

        update_fields = self.soft_restore_values(updated_user=updated_user)
        count = await self.model.filter(id__in=ids, state=1).update(**update_fields)
        LOGGER.info(f"批量恢复成功, 关键字段: [model={self.model.__name__}, count={count}, ids={ids}]")
        return count


class QueryBuilder(Generic[ModelType]):
    """
    链式查询构建器。

    过滤、排除、排序、分页与预加载条件先累积在实例上，执行方法被调用时才组装并发出查询；
    克隆方法返回互不影响的副本，便于复用同一组基础条件。
    """

    def __init__(self, model: Type[ModelType]):
        """
        初始化空条件的查询构建器。

        :param model: 查询目标模型
        """
        self.model = model
        # 以下字段均为累积中的查询条件，执行时才参与查询组装
        self._filters: List[Q] = []
        self._excludes: List[Q] = []
        self._order_by: List[str] = []
        self._offset: Optional[int] = None
        self._limit: Optional[int] = None
        self._prefetch: List[str] = []

    def clone(self) -> 'QueryBuilder[ModelType]':
        """
        复制当前查询构建器。

        新实例持有各条件列表的副本，与源实例互不影响。

        :return: 条件相同的独立构建器
        """
        new_builder = QueryBuilder(self.model)
        new_builder._filters = self._filters.copy()
        new_builder._excludes = self._excludes.copy()
        new_builder._order_by = self._order_by.copy()
        new_builder._offset = self._offset
        new_builder._limit = self._limit
        new_builder._prefetch = self._prefetch.copy()
        return new_builder

    def filter(self, *args, **kwargs) -> 'QueryBuilder[ModelType]':
        """
        追加过滤条件。

        位置参数按原样透传，关键字参数转为 Q 对象；返回自身以支持链式调用。

        :param args: Q 对象或其他过滤表达式
        :param kwargs: 字段过滤条件
        :return: 当前构建器
        """
        if args:
            self._filters.extend(args)
        if kwargs:
            self._filters.append(Q(**kwargs))
        return self

    def exclude(self, *args, **kwargs) -> 'QueryBuilder[ModelType]':
        """
        追加排除条件。

        位置参数按原样透传，关键字参数转为 Q 对象；返回自身以支持链式调用。

        :param args: Q 对象或其他排除表达式
        :param kwargs: 字段排除条件
        :return: 当前构建器
        """
        if args:
            self._excludes.extend(args)
        if kwargs:
            self._excludes.append(Q(**kwargs))
        return self

    def order_by(self, *fields: str) -> 'QueryBuilder[ModelType]':
        """
        追加排序字段。

        字段名前缀减号表示倒序，返回自身以支持链式调用。

        :param fields: 排序字段
        :return: 当前构建器
        """
        self._order_by.extend(fields)
        return self

    def offset(self, offset: int) -> 'QueryBuilder[ModelType]':
        """
        设置结果起始偏移量。

        :param offset: 跳过的记录数
        :return: 当前构建器
        """
        self._offset = offset
        return self

    def limit(self, limit: int) -> 'QueryBuilder[ModelType]':
        """
        设置单次返回的最大记录数。

        :param limit: 最大记录数
        :return: 当前构建器
        """
        self._limit = limit
        return self

    def prefetch(self, *fields: str) -> 'QueryBuilder[ModelType]':
        """
        追加需要预加载的关联字段。

        :param fields: 关联字段名
        :return: 当前构建器
        """
        self._prefetch.extend(fields)
        return self

    def _build_query(self) -> QuerySet:
        """
        按累积条件组装查询集。

        依次应用过滤、排除、排序、分页与预加载，未设置的分页参数不参与组装。

        :return: 可直接执行的查询集
        """
        query = self.model.filter()

        # 应用过滤条件
        for f in self._filters:
            query = query.filter(f)

        # 应用排除条件
        for e in self._excludes:
            query = query.exclude(e)

        # 应用排序
        if self._order_by:
            query = query.order_by(*self._order_by)

        # 应用分页
        if self._offset is not None:
            query = query.offset(self._offset)
        if self._limit is not None:
            query = query.limit(self._limit)

        # 应用预加载
        if self._prefetch:
            query = query.prefetch_related(*self._prefetch)

        return query

    async def all(self) -> List[ModelType]:
        """
        执行查询并返回全部结果。

        :return: 模型实例列表
        """
        return await self._build_query().all()

    async def first(self) -> Optional[ModelType]:
        """
        执行查询并返回首条结果。

        :return: 首条模型实例，无结果时为空值
        """
        return await self._build_query().first()

    async def count(self) -> int:
        """
        统计满足条件的记录数。

        :return: 记录数量
        """
        return await self._build_query().count()

    async def paginate(self, page: int = 1, page_size: int = 10) -> Tuple[int, List[ModelType]]:
        """
        执行分页查询。

        先取总数，再按页码与每页数量计算偏移后取当前页数据。

        :param page: 页码，从 1 开始
        :param page_size: 每页数量
        :return: 记录总数与当前页记录列表
        """
        query = self._build_query()
        total = await query.count()

        self._offset = (page - 1) * page_size
        self._limit = page_size
        items = await self._build_query().all()

        return total, items

    async def exists(self) -> bool:
        """
        判断是否存在满足条件的记录。

        :return: 存在返回真，否则返回假
        """
        return await self._build_query().exists()
