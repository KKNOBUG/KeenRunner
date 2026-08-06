# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_tag_crud
@DateTime: 2026/1/16 16:35
"""
import traceback
from typing import Optional, Dict, Any, List, Union, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import AutoTestApiTagInfo
from backend.applications.aotutest.schemas.autotest_tag_schema import (
    AutoTestApiTagCreate,
    AutoTestApiTagUpdate,
    AutoTestApiTagDelete,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
)


class AutoTestApiTagCrud(ScaffoldCrud[AutoTestApiTagInfo, AutoTestApiTagCreate, AutoTestApiTagUpdate]):

    def __init__(self):
        super().__init__(model=AutoTestApiTagInfo)

    async def get_by_id(self, tag_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestApiTagInfo]:
        """
        根据主键ID查询标签。

        :param tag_id: 标签主键ID
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 标签实例或None
        :raises ParameterException: tag_id为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not tag_id:
            error_message: str = "查询标签信息失败, 参数[tag_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=tag_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询标签信息失败, 记录[id={tag_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_ids(self, tag_ids: List[int], on_error: bool = False, **kwargs) -> Union[bool, List[AutoTestApiTagInfo]]:
        """
        校验一批标签ID是否均存在；全部存在时返回实例列表。

        :param tag_ids: 标签主键ID列表
        :param on_error: 有缺失时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 全部存在时返回标签列表；有缺失且on_error为False时返回False
        :raises ParameterException: tag_ids为空或非列表
        :raises NotFoundException: 存在缺失ID且on_error为True
        """
        if not tag_ids:
            error_message: str = "查询标签信息失败, 参数[tag_ids]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if not isinstance(tag_ids, list):
            error_message: str = "查询标签信息失败, 参数[tag_ids]必须是List[int]类型"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        existing_tags = await self.model.filter(id__in=tag_ids, **kwargs).values_list("id", flat=True)
        missing_tags: Set[int] = set(tag_ids) - set(existing_tags)
        if missing_tags:
            error_message: str = f"查询标签信息失败, 记录[id_in={missing_tags}]不存在"
            LOGGER.error(error_message)
            if on_error:
                raise NotFoundException(message=error_message)
            return False
        return await self.model.filter(id__in=tag_ids, **kwargs).all()

    async def get_by_code(self, tag_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestApiTagInfo]:
        """
        根据标签标识代码查询标签。

        :param tag_code: 标签标识代码
        :param on_error: 未找到时是否抛出NotFoundException
        :param kwargs: 额外过滤条件
        :return: 标签实例或None
        :raises ParameterException: tag_code为空
        :raises NotFoundException: on_error为True且记录不存在
        """
        if not tag_code:
            error_message: str = "查询标签信息失败, 参数[tag_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(tag_code=tag_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询标签信息失败, 记录[code={tag_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_tag(self, tag_in: AutoTestApiTagCreate) -> AutoTestApiTagInfo:
        """
        创建标签；同应用下同大类/名称已存在则恢复并更新。

        :param tag_in: 标签创建schema
        :return: 创建或恢复后的标签实例
        :raises NotFoundException: 应用不存在
        :raises DataBaseStorageException: 违反数据库约束
        """
        tag_mode: str = tag_in.tag_mode
        tag_name: str = tag_in.tag_name
        tag_project: int = tag_in.tag_project

        # 业务层验证：检查应用是否存在
        from backend.applications.aotutest.services.autotest_project_crud import AutoTestApiProjectCrud
        await AutoTestApiProjectCrud().get_by_id(project_id=tag_project, on_error=True, state__not=1)

        # 业务层验证：同应用下相同大类及名称仅允许一条记录（含已禁用，命中则恢复启用）
        tag_dict: Dict[str, Any] = tag_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_tag = await self.model.filter(tag_project=tag_project, tag_mode=tag_mode, tag_name=tag_name).first()
        if not existing_tag:
            try:
                instance: AutoTestApiTagInfo = await self.create(obj_in=tag_dict)
                return instance
            except IntegrityError as e:
                error_message: str = f"新增标签信息失败, 违反约束规则: {e}"
                LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
                raise DataBaseStorageException(message=error_message) from e

        try:
            tag_dict["state"] = 0
            instance: AutoTestApiTagInfo = await self.update(id=existing_tag.id, obj_in=tag_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = f"新增(更新)标签信息异常, 违反约束规则或空指针异常: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_tag(self, tag_in: AutoTestApiTagUpdate) -> AutoTestApiTagInfo:
        """
        更新标签，根据tag_id或tag_code定位并校验 (tag_project, tag_mode, tag_name) 唯一。

        :param tag_in: 标签更新schema
        :return: 更新后的标签实例
        :raises NotFoundException: 标签不存在
        :raises DataAlreadyExistsException: 同应用同大类同名标签已存在
        :raises DataBaseStorageException: 违反约束
        """
        tag_id: Optional[int] = tag_in.tag_id
        tag_code: Optional[str] = tag_in.tag_code
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True, state__not=1)
            tag_id = instance.id

        update_dict: Dict[str, Any] = tag_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"tag_id", "tag_code"}
        )
        if "tag_project" in update_dict or "tag_mode" in update_dict or "tag_name" in update_dict:
            tag_project: int = update_dict.get("tag_project", instance.tag_project)
            tag_mode: str = update_dict.get("tag_mode", instance.tag_mode)
            tag_name: str = update_dict.get("tag_name", instance.tag_name)
            existing_tag = await self.model.filter(
                tag_project=tag_project,
                tag_mode=tag_mode,
                tag_name=tag_name,
                state__not=1
            ).exclude(id=tag_id).first()
            if existing_tag:
                error_message: str = (
                    f"标签[tag_project={tag_project}, tag_mode={tag_mode}, tag_name={tag_name}]已存在"
                )
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)

        try:
            instance = await self.update(id=tag_id, obj_in=update_dict)
            return instance
        except DoesNotExist as e:
            error_message: str = f"更新标签信息失败, 记录[id={tag_id}]或[code={tag_code}]不存在, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = f"更新标签信息异常, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_tag(self, tag_id: Optional[int] = None, tag_code: Optional[str] = None) -> AutoTestApiTagInfo:
        """
        软删除标签；需无用例关联该标签。

        :param tag_id: 标签主键ID，与tag_code二选一
        :param tag_code: 标签标识代码，与tag_id二选一
        :return: 软删除后的标签实例
        :raises NotFoundException: 标签不存在
        :raises DataAlreadyExistsException: 有用例关联该标签
        """
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True, state__not=1)

        from backend.applications.aotutest.services.autotest_case_crud import AutoTestApiCaseCrud
        cases_count = await AutoTestApiCaseCrud().model.filter(case_tags__contains=[instance.id], state__not=1).count()
        if cases_count > 0:
            error_message: str = f"删除标签信息失败, 记录[id={instance.id}]被{cases_count}个用例关联"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        instance.state = 1
        await instance.save()
        return instance

    async def delete_tags(self, tag_in: AutoTestApiTagDelete) -> int:
        """
        根据ID或code列表批量软删除标签；逐条复用单删关联校验。

        :param tag_in: 标签删除schema
        :return: 更新条数
        :raises ParameterException: tag_ids与tag_codes均未传
        :raises NotFoundException: 标签不存在
        :raises DataAlreadyExistsException: 有用例关联该标签
        """
        tag_ids: Optional[List[int]] = tag_in.tag_ids
        tag_codes: Optional[List[str]] = tag_in.tag_codes
        if not tag_ids and not tag_codes:
            error_message: str = "删除标签信息失败, 参数[tag_ids]或[tag_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        targets: List[AutoTestApiTagInfo] = []
        if tag_ids:
            for tid in tag_ids:
                targets.append(await self.get_by_id(tag_id=tid, on_error=True, state__not=1))
        else:
            for tcode in tag_codes:
                targets.append(await self.get_by_code(tag_code=tcode, on_error=True, state__not=1))

        for instance in targets:
            await self.delete_tag(tag_id=instance.id)

        return len(targets)

    async def select_tags(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestApiTagInfo]]:
        """
        根据条件分页查询标签列表。

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
            error_message: str = f"查询标签信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
