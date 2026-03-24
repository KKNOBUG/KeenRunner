# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_data_source_crud.py
@DateTime: 2026/3/6
"""
import traceback
from typing import Optional, Dict, Any, List, Union

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend import LOGGER
from backend.applications.aotutest.models.autotest_model import AutoTestApiDataSourceInfo
from backend.applications.aotutest.schemas.autotest_data_source_schema import (
    AutoTestDataSourceCreate,
    AutoTestDataSourceUpdate,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import (
    ParameterException,
    NotFoundException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


def make_cache_key(case_id: int, step_code: str) -> str:
    """
    生成 Redis 等使用的缓存键名。

    :param case_id: 用例主键。
    :param step_code: 步骤标识代码。
    :returns: 缓存键字符串。
    """
    return f"dataset_{case_id}_{step_code}"


class AutoTestDataSourceCrud(ScaffoldCrud[AutoTestApiDataSourceInfo, AutoTestDataSourceCreate, AutoTestDataSourceUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiDataSourceInfo)

    async def get_by_id(self, data_source_id: int, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        """
        根据数据源主键 ID 查询单条记录（排除已软删 state=1）。

        :param data_source_id: 数据源主键 ID。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 数据源实例或 None。
        :raises ParameterException: 当 data_source_id 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not data_source_id:
            error_message: str = "查询数据源失败, 参数(data_source_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(id=data_source_id, state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源失败, 数据源(id={data_source_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, data_source_code: str, on_error: bool = False) -> Optional[AutoTestApiDataSourceInfo]:
        """
        根据data_source_code查询单条数据源（排除已软删）。

        :param data_source_code: 数据驱动标识代码。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 数据源实例或 None。
        :raises ParameterException: 当 data_source_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时。
        """
        if not (data_source_code or "").strip():
            error_message: str = "查询数据源失败, 参数(data_source_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(data_source_code=data_source_code.strip(), state__not=1).first()
        if not instance and on_error:
            error_message: str = f"查询数据源失败, 数据源(data_source_code={data_source_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiDataSourceInfo, List[AutoTestApiDataSourceInfo]]]:
        """
        根据条件查询数据源（自动附加 state__not=1，排除已软删）。

        :param conditions: 查询条件字典（字段名与模型一致）。
        :param only_one: 为 True 时返回单条，否则返回列表。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 单条实例、实例列表或 None。
        :raises ParameterException: 条件非法或查询异常时。
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时。
        """
        try:
            stmt: QuerySet = self.model.filter(**conditions, state__not=1)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询数据源异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询数据源发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询数据源失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def get_by_case_step(
            self,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            on_error: bool = False
    ) -> Optional[Union[AutoTestApiDataSourceInfo, List[AutoTestApiDataSourceInfo]]]:
        """按用例 + 步骤查询数据源（排除已软删）。

        - case_id / case_code 至少传其一；
        - 若同时传入 step_id 或 step_code 之一，则返回单条；
        - 若未传任何 step 条件，则返回该用例下数据源列表。

        :param case_id: 用例主键。
        :param case_code: 用例标识代码。
        :param step_id: 步骤主键。
        :param step_code: 步骤标识代码。
        :param on_error: 为 True 时若未找到则抛出 NotFoundException。
        :returns: 单条实例、列表或 None。
        :raises ParameterException: 未传 case_id 且 case_code 为空时。
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时。
        """
        if not case_id and not (case_code or "").strip():
            error_message: str = "查询数据源失败, 参数(case_id或case_code)必须二选一传递"
            LOGGER.error(error_message)

            raise ParameterException(message=error_message)

        conditions: Dict[str, Any] = {}
        if case_id:
            conditions["case_id"] = case_id
        if case_code:
            conditions["case_code"] = case_code

        has_step_condition = False
        if step_id:
            conditions["step_id"] = step_id
            has_step_condition = True
        if step_code:
            conditions["step_code"] = step_code
            has_step_condition = True

        if has_step_condition:
            instance = await self.model.filter(**conditions, state__not=1).first()
            if not instance and on_error:
                error_message: str = "根据条件查询数据源暂无匹配记录"
                LOGGER.error(f"{error_message}, 条件明细: {conditions}")
                raise NotFoundException(message=error_message, data=conditions)
            return instance

        instances = await self.model.filter(**conditions).order_by("step_id", "step_code").all()
        if not instances and on_error:
            error_message: str = f"根据条件查询数据源暂无匹配记录"
            LOGGER.error(f"{error_message}, 条件明细: {conditions}")
            raise NotFoundException(message=error_message, data=conditions)
        return instances

    async def create_data_source(self, data_source_in: AutoTestDataSourceCreate) -> AutoTestApiDataSourceInfo:
        """
        创建数据源。

        按 (case_id, case_code, step_id, step_code) 定位：
        无记录则新增；已存在且 state=1 则按入参更新并恢复 state=0；
        已存在且启用则抛出 DataAlreadyExistsException。

        :param data_source_in: 创建 schema（data_source_code 由模型默认值生成，无需传入）。
        :returns: 新建或恢复后的数据源实例。
        :raises DataAlreadyExistsException: 同键已存在且为启用状态时。
        :raises DataBaseStorageException: 违反数据库约束时。
        :raises NotFoundException: 恢复路径上记录异常丢失时（极少见）。
        """
        data_dict: Dict[str, Any] = data_source_in.model_dump(exclude_none=True, exclude_unset=True)
        case_id = data_dict.get("case_id")
        case_code = data_dict.get("case_code")
        step_id = data_dict.get("step_id")
        step_code = data_dict.get("step_code")
        existing = await self.model.filter(case_id=case_id, case_code=case_code, step_id=step_id, step_code=step_code).first()

        if not existing:
            try:
                return await self.create(obj_in=data_dict)
            except IntegrityError as e:
                error_message: str = f"新增数据源异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        if existing.state == 1:
            update_dict: Dict[str, Any] = dict(data_dict)
            update_dict["state"] = 0
            if "created_user" in update_dict:
                update_dict["updated_user"] = update_dict.pop("created_user")
            try:
                return await self.update(id=existing.id, obj_in=update_dict)
            except DoesNotExist as e:
                error_message: str = f"恢复数据源失败, 数据源(id={existing.id})不存在, 错误描述: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise NotFoundException(message=error_message) from e
            except IntegrityError as e:
                error_message: str = f"恢复数据源异常, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        error_message: str = (
            f"新增数据源失败, 数据源(case_id={case_id}, case_code={case_code}, "
            f"step_id={step_id}, step_code={step_code})已存在且为启用状态"
        )
        LOGGER.error(error_message)
        raise DataAlreadyExistsException(message=error_message)

    async def update_data_source(self, data_source_in: AutoTestDataSourceUpdate) -> AutoTestApiDataSourceInfo:
        """
        更新数据源
        定位优先级：data_source_id > data_source_code > (case_id|case_code) 且 (step_id|step_code)。
        定位字段及 case_id / case_code / step_id / step_code / cache_key 不会写入更新字典。

        :param data_source_in: 更新 schema。
        :returns: 更新后的数据源实例。
        :raises ParameterException: 定位参数不足时。
        :raises NotFoundException: 记录不存在时。
        :raises DataBaseStorageException: 违反约束时。
        """
        case_id: Optional[int] = data_source_in.case_id
        step_id: Optional[int] = data_source_in.step_id
        case_code: Optional[str] = data_source_in.case_code
        step_code: Optional[str] = data_source_in.step_code
        data_source_id: Optional[int] = data_source_in.data_source_id
        data_source_code: Optional[str] = data_source_in.data_source_code

        if data_source_id:
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_id(
                data_source_id=data_source_id,
                on_error=True
            )
        elif (data_source_code or "").strip():
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_code(
                data_source_code=data_source_code.strip(),
                on_error=True
            )
        elif (case_id or (case_code or "").strip()) and (step_id or (step_code or "").strip()):
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_case_step(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                on_error=True
            )
        else:
            error_message: str = "更新数据源失败, 定位参数不足(需在 schema 中提供 data_source_id / data_source_code / case+step)"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        update_dict: Dict[str, Any] = data_source_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"cache_key", "case_id", "case_code", "step_id", "step_code", "data_source_id", "data_source_code"}
        )
        if not update_dict:
            return instance

        try:
            return await self.update(id=instance.id, obj_in=update_dict)
        except DoesNotExist as e:
            error_message: str = f"更新数据源失败, 数据源(id={instance.id})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新数据源异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_data_source(
            self,
            data_source_id: Optional[int] = None,
            data_source_code: Optional[str] = None,
            case_id: Optional[int] = None,
            case_code: Optional[str] = None,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
    ) -> AutoTestApiDataSourceInfo:
        """软删除数据源（state=1）。

        定位优先级：data_source_id > data_source_code > (case_id|case_code) 且 (step_id|step_code)。

        :param data_source_id: 主键 ID。
        :param data_source_code: 数据驱动标识代码。
        :param case_id: 用例主键（与 step 组合定位）。
        :param case_code: 用例标识代码。
        :param step_id: 步骤主键。
        :param step_code: 步骤标识代码。
        :returns: 软删除后的实例。
        :raises ParameterException: 定位参数不足时。
        :raises NotFoundException: 记录不存在时。
        """
        if data_source_id:
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_id(
                data_source_id=data_source_id,
                on_error=True
            )
        elif (data_source_code or "").strip():
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_code(
                data_source_code=data_source_code.strip(),
                on_error=True
            )
        elif (case_id or (case_code or "").strip()) and (step_id or (step_code or "").strip()):
            instance: Optional[AutoTestApiDataSourceInfo] = await self.get_by_case_step(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                on_error=True
            )
        else:
            error_message: str = "删除数据源失败, 定位参数不足(需 id/data_source_code/(case+step))"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def select_data_sources(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """
        分页查询数据源列表。

        :param search: Tortoise Q 查询条件。
        :param page: 页码。
        :param page_size: 每页条数。
        :param order: 排序字段列表。
        :returns: (总条数, 当前页记录列表) 元组。
        :raises ParameterException: 查询条件非法导致 FieldError 时。
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询数据源异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def get_dataset_scenario(self, case_id: int, step_code: str, dataset_name: str) -> Optional[Dict[str, Any]]:
        """
        根据用例、步骤、数据集名称取该步骤下单个场景的结构化数据。

        :param case_id: 用例主键。
        :param step_code: 步骤标识代码。
        :param dataset_name: 场景/数据集名称。
        :returns: 形如 {"head": ..., "body": ..., "assert": ...} 的字典；无数据时返回 None。
        """
        if not (dataset_name or "").strip():
            return None
        record = await self.get_by_case_step(
            case_id=case_id,
            step_code=(step_code or "").strip(),
            on_error=False,
        )
        if not record or not isinstance(record.dataset, dict):
            return None
        return record.dataset.get((dataset_name or "").strip())

    async def create_data_sources_from_parsed(
            self,
            case_id: int,
            case_code: str,
            step_id: int,
            step_code: str,
            file_name: Optional[str] = None,
            file_path: Optional[str] = None,
            file_hash: Optional[str] = None,
            file_desc: Optional[str] = None,
            parsed_data: Optional[Dict[str, Any]] = None,
            dataset_names: Optional[List[str]] = None,
            dataframe: Optional[List[Any]] = None,
            created_user: Optional[str] = None,
    ) -> AutoTestApiDataSourceInfo:
        """
        上传解析场景：按 case_id + step_id + step_code 若已存在则更新，否则创建。
        供视图/任务层调用，封装 cache_key 与 schema 组装。

        :param case_id: 用例主键。
        :param case_code: 用例标识代码。
        :param step_id: 步骤主键。
        :param step_code: 步骤标识代码。
        :param file_name: 存储文件名。
        :param file_path: 存储路径。
        :param file_hash: 文件哈希。
        :param file_desc: 描述。
        :param parsed_data: 解析后的 dataset 字典。
        :param dataset_names: 场景名称列表。
        dataframe: Optional[List[Any]] = None,
        :param created_user: 创建人（更新路径会映射为 updated_user）。
        :returns: 数据源实例。
        :raises ParameterException: parsed_data 为空时。
        """
        if not parsed_data:
            raise ParameterException(message="参数 parsed_data 不能为空")

        existing = await self.get_by_case_step(
            case_id=case_id,
            step_id=step_id,
            step_code=step_code,
            on_error=False,
        )
        cache_key = make_cache_key(case_id, step_code)
        if existing:
            return await self.update_data_source(
                AutoTestDataSourceUpdate(
                    data_source_id=existing.id,
                    case_id=case_id,
                    case_code=case_code,
                    step_id=step_id,
                    step_code=step_code,
                    file_name=file_name,
                    file_path=file_path,
                    file_hash=file_hash,
                    file_desc=file_desc,
                    cache_key=cache_key,
                    dataset=parsed_data,
                    dataset_names=dataset_names if dataset_names is not None else (existing.dataset_names or []),
                    dataframe=dataframe if dataframe is not None else (existing.dataframe or []),
                    updated_user=created_user,
                ),
            )

        return await self.create_data_source(
            AutoTestDataSourceCreate(
                case_id=case_id,
                case_code=case_code,
                step_id=step_id,
                step_code=step_code,
                file_name=file_name or "",
                file_path=file_path or "",
                file_hash=file_hash or "",
                file_desc=file_desc,
                cache_key=cache_key,
                dataset=parsed_data,
                dataset_names=dataset_names or [],
                dataframe=dataframe or [],
                created_user=created_user,
            )
        )

    async def list_by_case(
            self,
            case_id: int,
            state: int = 0,
    ) -> List[AutoTestApiDataSourceInfo]:
        """
        查询指定用例下的数据源列表。

        :param case_id: 用例主键。
        :param state: 状态过滤，默认 0（启用）。
        :returns: 按 updated_time 倒序及步骤字段排序的列表。
        :raises ParameterException: case_id 为空时。
        """
        if not case_id:
            raise ParameterException(message="参数(case_id)不允许为空")
        return await self.model.filter(case_id=case_id, state=state).order_by("-updated_time", "step_id", "step_code").all()


AUTOTEST_DATA_SOURCE_CRUD = AutoTestDataSourceCrud()
