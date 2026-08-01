# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_config_crud
@DateTime: 2026/4/16 10:51
"""
import traceback
from typing import Optional, Dict, Any, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError, DoesNotExist
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import AutoTestApiEnvConfigInfo
from backend.applications.aotutest.schemas.autotest_env_config_schema import (
    AutoTestApiConfigCreate,
    AutoTestApiConfigUpdate,
    AutoTestApiConfigDelete
)
from backend.applications.aotutest.services.autotest_env_crud import AutoTestApiEnvEnumCrud
from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
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

    async def get_by_id(self, config_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据主键ID查询环境配置。

        :param config_id: 配置主键
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
        :raises ParameterException: config_id为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not config_id:
            error_message: str = "查询配置信息失败, 参数(config_id)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        instance = await self.model.filter(id=config_id, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 用例(id={config_id})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, config_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiEnvConfigInfo]:
        """
        根据配置标识代码查询环境配置。

        :param config_code: 配置标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 配置实例或None
        :raises ParameterException: config_code为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not config_code:
            error_message: str = "查询配置信息失败, 参数(config_code)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(config_code=config_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询配置信息失败, 步骤(code={config_code})不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_config(self, config_in: AutoTestApiConfigCreate) -> AutoTestApiEnvConfigInfo:
        """
        创建环境配置；同应用/环境/类型/名称已存在则覆盖更新。

        :param config_in: 配置创建schema
        :return: 创建或覆盖更新后的配置实例
        :raises ParameterException: 配置类型或必填字段非法
        :raises NotFoundException: 环境或应用不存在
        :raises DataBaseStorageException: 违反数据库约束
        """
        env_id: int = config_in.env_id
        project_id: int = config_in.project_id
        config_name: str = config_in.config_name
        config_type: AutoTestConfigNodeType = config_in.config_type
        config_dict: Dict[str, Any] = config_in.model_dump(exclude_none=True, exclude_unset=True)
        # 业务层验证: 检查环境是否存在
        await AutoTestApiEnvEnumCrud().get_by_id(env_id=env_id, on_error=True, state__not=1)
        # 业务层验证: 检查应用是否存在
        await AutoTestApiProjectCrud().get_by_id(project_id=project_id, on_error=True, state__not=1)
        existing_config = await self.get_by_conditions(
            only_one=True,
            on_error=False,
            state__not=1,
            env_id=env_id,
            project_id=project_id,
            config_type=config_type.value,
            config_name=config_name,
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
            elif config_type == AutoTestConfigNodeType.REDIS.value:
                if not config_in.config_host:
                    raise ParameterException(message="配置信息类型为REDIS时参数[config_host]不允许为空")

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
        更新环境配置，根据config_id或config_code定位。

        :param config_in: 配置更新schema
        :return: 更新后的配置实例
        :raises ParameterException: 配置类型或必填字段非法
        :raises NotFoundException: 配置不存在
        :raises DataAlreadyExistsException: 同应用/环境下配置名重复
        :raises DataBaseStorageException: 违反数据库约束
        """
        config_id: Optional[int] = config_in.config_id
        config_code: Optional[str] = config_in.config_code
        config_type: AutoTestConfigNodeType = config_in.config_type

        # 业务层验证：检查配置信息是否存在
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True, state__not=1)
            config_code: str = instance.config_code
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True, state__not=1)
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
        elif config_type == AutoTestConfigNodeType.REDIS.value:
            if not config_in.config_host:
                raise ParameterException(message="配置信息类型为REDIS时参数[config_host]不允许为空")
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
        软删除环境配置。

        :param config_id: 配置主键，与config_code二选一
        :param config_code: 配置标识代码，与config_id二选一
        :return: 软删除后的配置实例
        :raises NotFoundException: 配置不存在
        """
        if config_id:
            instance = await self.get_by_id(config_id=config_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(config_code=config_code, on_error=True, state__not=1)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_configs(self, config_in: AutoTestApiConfigDelete) -> int:
        """
        根据ID或code列表批量软删除环境配置。

        :param config_in: 环境配置删除schema
        :return: 更新条数
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

    async def select_config(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiEnvConfigInfo]]:
        """
        根据条件分页查询环境配置列表。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询字段非法
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = f"查询配置信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def query_classified_by_project_ids(self, project_ids: List[int]) -> Dict[int, Dict[int, Dict[str, Dict[str, Dict[str, Any]]]]]:
        """
        按应用ID列表查询环境配置并按类型嵌套归类。

        :param project_ids: 应用主键ID列表
        :return: 嵌套归类结果；请求中的应用ID均出现在第一层
        :raises ParameterException: project_ids为空
        """
        if not project_ids:
            error_message: str = "根据应用列表查询环境配置失败, 参数(project_ids)不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        distinct_project_ids: List[int] = list(dict.fromkeys(project_ids))
        classified_config_result: Dict[int, Dict[int, Dict[str, Dict[str, Dict[str, Any]]]]] = {
            project_id: {}
            for project_id in distinct_project_ids
        }
        classified_config_type: Tuple[str, ...] = (
            AutoTestConfigNodeType.API.value,
            AutoTestConfigNodeType.DB.value,
            AutoTestConfigNodeType.REDIS.value,
            AutoTestConfigNodeType.FILE.value,
        )
        env_config_instances: Optional[List[AutoTestApiEnvConfigInfo]] = await self.model.filter(
            project_id__in=distinct_project_ids,
            state__not=1,
        ).all()
        for cfg_instance in env_config_instances:
            env_id: int = cfg_instance.env_id
            project_id: int = cfg_instance.project_id
            if project_id not in classified_config_result:
                continue
            config_type_raw: AutoTestConfigNodeType = cfg_instance.config_type
            config_type_act = config_type_raw.value if hasattr(config_type_raw, "value") else str(config_type_raw)
            if config_type_act not in classified_config_type:
                LOGGER.warning(f"跳过未知配置类型: project_id={project_id}, env_id={env_id}, config_type={config_type_act}")
                continue
            if env_id not in classified_config_result[project_id]:
                classified_config_result[project_id][env_id] = {t: {} for t in classified_config_type}

            config_info: Dict[str, Any] = {
                "config_host": cfg_instance.config_host,
                "config_port": cfg_instance.config_port,
                "database_name": cfg_instance.database_name,
            }
            classified_config_result[project_id][env_id][config_type_act][cfg_instance.config_name] = config_info
        return classified_config_result

    async def list_distinct_config_names(
            self,
            project_id: Optional[int] = None,
            env_id: Optional[int] = None,
            config_type: Optional[str] = None,
    ) -> List[str]:
        """
        未删除配置中config_name去重后的列表。

        :param project_id: 应用ID
        :param env_id: 环境ID
        :param config_type: 配置类型
        :return: 去重且升序排列的配置名称列表
        """
        stmt: QuerySet = self.model.filter(state__not=1)
        if project_id is not None:
            stmt = stmt.filter(project_id=project_id)
        if env_id is not None:
            stmt = stmt.filter(env_id=env_id)
        if config_type is not None:
            stmt = stmt.filter(config_type=config_type)
        names = await stmt.values_list("config_name", flat=True)
        return sorted(set(names))
