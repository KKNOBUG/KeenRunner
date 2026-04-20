# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from typing import Optional, Dict, Any, List, Union

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiConfigCreate,
    AutoTestApiConfigUpdate,
    AutoTestApiConfigDelete
)
from backend.applications.aotutest.services.autotest_env_crud import AUTOTEST_API_ENV_ENUM_CRUD
from backend.applications.aotutest.services.autotest_project_crud import AUTOTEST_API_PROJECT_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)
from backend.enums import AutoTestConfigNodeType


class AutoTestApiEnvConfigCrud(ScaffoldCrud[AutoTestApiEnvConfigInfo, AutoTestApiConfigCreate, AutoTestApiConfigUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiEnvConfigInfo)
        self.required_fields = ["config_host", "config_port", "config_username", "config_password"]

    async def get_by_id(self, config_id: int, on_error: bool = False, is_active: bool = True) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据配置主键 ID 查询
        :param config_id: 配置主键
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :param is_active: 为 True 时自动添加state__not过滤条件
        :returns: 配置实例或 None
        :raises ParameterException: 当 config_id 为空时
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时
        """
        if not config_id:
            error_message: str = "查询配置信息失败, 参数(config_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        kwargs: Dict[str, Any] = {"id": config_id}
        if is_active:
            kwargs["state__not"] = 1
        instance = await self.model.filter(**kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 用例(id={config_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, config_code: str, on_error: bool = False, is_active: bool = True) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据配置标识代码查询
        :param config_code: 配置标识代码
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :param is_active: 为 True 时自动添加state__not过滤条件
        :returns: 配置实例或 None
        :raises ParameterException: 当 step_code 为空时
        :raises NotFoundException: 当 on_error 为 True 且记录不存在时
        """
        if not config_code:
            error_message: str = "查询配置信息失败, 参数(config_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        kwargs: Dict[str, Any] = {"config_code": config_code}
        if is_active:
            kwargs["state__not"] = 1
        instance = await self.model.filter(**kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 步骤(code={config_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
            on_error: bool = False,
            is_active: bool = True
    ) -> Optional[Union[AutoTestApiEnvConfigInfo, List[AutoTestApiEnvConfigInfo]]]:
        """
        根据条件查询
        :param conditions: 查询条件字典
        :param only_one: 为 True 时返回单条记录，否则返回列表
        :param on_error: 为 True 时若未找到则抛出 NotFoundException
        :param is_active: 为 True 时自动添加state__not过滤条件
        :returns: 单条配置、配置列表或 None
        :raises ParameterException: 条件非法或查询异常时
        :raises NotFoundException: 当 on_error 为 True 且无匹配记录时
        """
        try:
            if is_active and "state__not" not in conditions:
                conditions["state__not"] = 1
            stmt: QuerySet = self.model.filter(**conditions)
            instances = await (stmt.first() if only_one else stmt.all())
        except FieldError as e:
            error_message: str = f"查询配置信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
        except Exception as e:
            error_message: str = f"查询配置信息发生未知异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

        if not instances and on_error:
            error_message: str = f"查询配置信息失败, 条件{conditions}不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instances

    async def create_config(self, config_in: AutoTestApiConfigCreate) -> AutoTestApiEnvConfigInfo:
        """
        创建配置信息
        :param config_in: 配置创建 schema 定义
        :returns: 创建后的配置实例
        :raises ParameterException: 参数或查询异常时
        :raises NotFoundException: 配置不存在时
        :raises DataAlreadyExistsException: 同应用、环境下配置名重复时
        :raises DataBaseStorageException: 违反数据库约束时
        """
        env_id: id = config_in.env_id
        project_id: id = config_in.project_id
        config_name: str = config_in.config_name
        config_type: AutoTestConfigNodeType = config_in.config_type.value
        config_dict: Dict[str, Any] = config_in.model_dump(exclude_none=True, exclude_unset=True)
        # 业务层验证: 检查环境是否存在
        await AUTOTEST_API_ENV_ENUM_CRUD.get_by_id(env_id=env_id, on_error=True)
        # 业务层验证: 检查应用是否存在
        await AUTOTEST_API_PROJECT_CRUD.get_by_id(project_id=project_id, on_error=True)
        existing_config = await self.get_by_conditions(
            only_one=True,
            on_error=False,
            is_active=True,
            conditions={
                "env_id": env_id,
                "project_id": project_id,
                "config_type": config_type,
                "config_name": config_name,
            }
        )
        if not existing_config:
            # 业务层验证: 根据配置类型进行检查参数是否匹配
            if config_type not in AutoTestConfigNodeType.get_values():
                raise ParameterException(message=f"配置信息类型[{config_type}]不被支持")
            if config_type == AutoTestConfigNodeType.API.value:
                if not config_in.config_host:
                    raise ParameterException(message=f"配置信息类型为API时参数[config_host]不允许为空")
            elif config_type == AutoTestConfigNodeType.DB.value:
                missing_fields = [field for field in self.required_fields if not getattr(config_in, field, None)]
                if missing_fields:
                    raise ParameterException(message=f"配置信息类型为DB时参数[{', '.join(missing_fields)}]不允许为空")
            elif config_type == AutoTestConfigNodeType.FILE.value:
                missing_fields = [field for field in self.required_fields if not getattr(config_in, field, None)]
                if getattr(config_in, "is_authorization", None) is None:
                    missing_fields.append("is_authorization")
                if missing_fields:
                    raise ParameterException(message=f"配置信息类型为FILE时参数[{', '.join(missing_fields)}]不允许为空")

            try:
                instance: AutoTestApiEnvConfigInfo = await self.create(config_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增配置信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            config_dict = config_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.update(id=existing_config.id, obj_in=config_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增(更新)配置信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_config(self, config_in: AutoTestApiConfigUpdate) -> AutoTestApiEnvConfigInfo:
        """
        更新配置信息
        :param config_in: 更新配置 schema 定义
        :returns: 更新后的配置实例
        :raises NotFoundException: 配置不存在时
        :raises DataAlreadyExistsException: 同应用、环境下配置名重复时
        :raises DataBaseStorageException: 违反数据库约束时
        """
        config_id: Optional[int] = config_in.config_id
        config_code: Optional[str] = config_in.config_code
        config_type: AutoTestConfigNodeType = config_in.config_type

        # 业务层验证：检查配置信息是否存在
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True)
            config_code: str = instance.config_code
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True)
            config_id: int = instance.id
        update_dict = config_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"config_id", "config_code"}
        )

        # 业务层验证：检查应用、环境、名称是否唯一
        if "env_id" in update_dict or "project_id" in update_dict or "config_name" in update_dict:
            env_id = update_dict.get("env_id", instance.env_id)
            project_id = update_dict.get("project_id", instance.project_id)
            config_name = update_dict.get("config_name", instance.config_name)
            existing_config = await self.model.filter(
                env_id=env_id,
                project_id=project_id,
                config_name=config_name,
                state__not=1
            ).exclude(id=config_id).first()
            if existing_config:
                LOGGER.error(
                    f"同[应用&环境]下配置名称不允许重复: "
                    f"根据(env_id={env_id}, project_id={project_id}, config_name={config_name})条件检查配置信息已存在"
                )
                raise DataAlreadyExistsException(message="同[应用&环境]下配置名称不允许重复")

        # 业务层验证: 根据配置类型进行检查参数是否匹配
        if config_type not in AutoTestConfigNodeType.get_values():
            raise ParameterException(message=f"配置信息类型[{config_type}]不被支持")
        if config_type == AutoTestConfigNodeType.API.value:
            if not config_in.config_host:
                raise ParameterException(message=f"配置信息类型为API时参数[config_host]不允许为空")
        elif config_type == AutoTestConfigNodeType.DB.value:
            missing_fields = [field for field in self.required_fields if not getattr(config_in, field, None)]
            if missing_fields:
                raise ParameterException(message=f"配置信息类型为DB时参数[{', '.join(missing_fields)}]不允许为空")
        elif config_type == AutoTestConfigNodeType.FILE.value:
            missing_fields = [field for field in self.required_fields if not getattr(config_in, field, None)]
            if getattr(config_in, "is_authorization", None) is None:
                missing_fields.append("is_authorization")
            if missing_fields:
                raise ParameterException(message=f"配置信息类型为FILE时参数[{', '.join(missing_fields)}]不允许为空")
        try:
            instance = await self.update(id=config_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新配置信息失败, 用例(id={config_id}或code={config_code})不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新配置信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_config(self, config_id: Optional[int] = None, config_code: Optional[str] = None) -> AutoTestApiEnvConfigInfo:
        """
        删除配置信息
        :param config_id: 配置主键
        :param config_code: 配置标识代码
        :returns:
        :raises NotFoundException:
        :raises DataAlreadyExistsException:
        """
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True)
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_configs(self, config_in: AutoTestApiConfigDelete) -> int:
        """
        删除环境配置信息
        :param config_in: 环境配置删除 schema 定义
        :returns: 删除的数量
        """
        config_ids: Optional[List[int]] = config_in.config_ids
        config_codes: Optional[List[str]] = config_in.config_codes
        if config_ids:
            count = await self.model.filter(id__in=config_ids).update(state=1)
        elif config_codes:
            count = await self.model.filter(config_code__in=config_codes).update(state=1)
        else:
            count = 0
        return count

    async def select_config(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """

        :param search: Tortoise Q 查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :returns: 由 (总条数, 当前页记录列表) 组成的元组
        :raises ParameterException: 查询条件非法导致 FieldError 时
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询配置信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e


AUTOTEST_API_ENV_CONFIG_CRUD = AutoTestApiEnvConfigCrud()
