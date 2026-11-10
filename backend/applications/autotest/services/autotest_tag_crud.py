# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : autotest_tag_crud
@DateTime: 2026/1/16 16:35
"""
import traceback
from typing import Optional, Dict, Any, List, Union, Set, Tuple

from tortoise.exceptions import DoesNotExist, IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.autotest.models.autotest_tag_model import AutoTestTagModel
from backend.applications.autotest.schemas.autotest_tag_schema import (
    AutoTestTagCreate,
    AutoTestTagUpdate,
    AutoTestTagDelete,
)
from backend.applications.autotest.services.autotest_scope_guard import load_readable_project
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
    DataAlreadyExistsException,
    NoPermissionException,
)
from backend.services import DataScope


class AutoTestTagCrud(ScaffoldCrud[AutoTestTagModel, AutoTestTagCreate, AutoTestTagUpdate]):
    """
    标签CRUD：应用下的二级配置项，用例通过 case_tags(ID数组) 引用标签。

    唯一口径：(tag_project, tag_mode, tag_name) 联合唯一，数据库索引不区分 state，
    因此软删行同样占用组合；同组合的软删记录在写权限内复用复活。
    父资源校验：创建时经 load_readable_project 确认所属应用对当前用户可读（B级）。
    引用约束：物理/批量软删前须确认无用例标签数组引用，否则拒绝删除。
    归属口径：以 created_user 为归属人。
    """

    def __init__(self):
        """绑定标签模型（krun_autotest_tag），供基类通用CRUD复用。"""
        super().__init__(model=AutoTestTagModel)

    async def get_by_id(self, tag_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestTagModel]:
        """
        根据主键ID查询标签。

        :param tag_id: 标签主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 标签实例或None
        :raises ParameterException: tag_id 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def get_by_ids(self, tag_ids: List[int], on_error: bool = False, **kwargs) -> Union[bool, List[AutoTestTagModel]]:
        """
        根据主键ID列表批量查询标签；用于用例写入时校验标签存在与列表回显。

        先只查一次主键判断缺失：有缺失且 on_error=False 时直接返回 False（而非空列表，
        历史契约，调用方须按真值判断），全部存在才二次查询返回完整实例列表。

        :param tag_ids: 标签主键ID列表
        :param on_error: 存在缺失ID时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 全部存在时返回标签列表；存在缺失且on_error为False时返回False
        :raises ParameterException: 列表为空或类型不是 list
        :raises NotFoundException: on_error=True 且存在缺失ID
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

    async def get_by_code(self, tag_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestTagModel]:
        """
        根据标签标识代码查询标签。

        :param tag_code: 标签标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 标签实例或None
        :raises ParameterException: tag_code 为空
        :raises NotFoundException: on_error=True 且记录不存在
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

    async def create_tag(self, tag_in: AutoTestTagCreate, scope: DataScope) -> AutoTestTagModel:
        """
        创建标签；同应用下同大类/名称的活跃记录报错，软删记录在写权限内恢复并更新。

        :param tag_in: 标签创建schema
        :param scope: 数据权限上下文，恢复软删标签时要求创建人允许当前用户写入
        :return: 创建或恢复后的标签实例
        :raises NotFoundException: 所属应用不存在或已软删
        :raises NoPermissionException: 应用归属不可见，或待恢复标签的创建人不在可写范围
        :raises DataAlreadyExistsException: 同应用同大类同名的活跃标签已存在
        :raises DataBaseStorageException: 落库失败（并发撞唯一索引或关联应用无效）
        """
        tag_mode: str = tag_in.tag_mode
        tag_name: str = tag_in.tag_name
        tag_project: int = tag_in.tag_project

        # 业务层验证：应用必须存在且对当前用户可读(B级父资源校验)
        await load_readable_project(scope, tag_project)
        # 业务层验证：同应用下相同大类及名称仅允许一条记录（唯一索引不区分state，含软删行；命中软删则恢复启用）
        tag_dict: Dict[str, Any] = tag_in.model_dump(exclude_none=True, exclude_unset=True)
        existing_tag = await self.model.filter(
            tag_project=tag_project,
            tag_mode=tag_mode,
            tag_name=tag_name,
        ).first()
        if not existing_tag:
            try:
                instance: AutoTestTagModel = await self.create(obj_in=tag_dict)
                return instance
            except IntegrityError as e:
                error_message: str = "新增标签信息失败，相同应用下标签大类和名称可能重复，或关联应用无效，请检查后重试"
                LOGGER.error(
                    f"{error_message}, 关键字段: [tag_project={tag_project}, "
                    f"tag_mode={tag_mode}, tag_name={tag_name}]\n"
                    f"{traceback.format_exc()}"
                )
                raise DataBaseStorageException(message=error_message) from e

        try:
            if existing_tag.state != 1:
                error_message: str = f"标签[tag_name={tag_name}]已存在"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)
            # 软删恢复不得跨写范围接管他人标签，且不覆盖原创建人
            await scope.load_owners([existing_tag.created_user])
            if not scope.can_write(existing_tag.created_user):
                error_message: str = f"新增标签信息失败, 标签[{tag_name}]创建人[{existing_tag.created_user}]不在当前用户可操作范围内, 无权操作"
                LOGGER.error(error_message)
                raise NoPermissionException(message=error_message)
            tag_dict.pop("created_user", None)
            tag_dict["state"] = 0
            instance: AutoTestTagModel = await self.update(id=existing_tag.id, obj_in=tag_dict)
            return instance
        except (DoesNotExist, IntegrityError) as e:
            error_message: str = "恢复标签信息失败，目标标签可能已被删除，或标签信息与现有记录冲突，请刷新后重试"
            LOGGER.error(
                f"{error_message}, 关键字段: [tag_id={existing_tag.id}, tag_project={tag_project}, "
                f"tag_mode={tag_mode}, tag_name={tag_name}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def update_tag(self, tag_in: AutoTestTagUpdate, scope: DataScope) -> AutoTestTagModel:
        """
        更新标签，根据tag_id或tag_code定位并校验(tag_project, tag_mode, tag_name)唯一。

        仅在入参触及三键时重做判重；与创建不同，这里的判重只比对非软删行，
        只要目标组合还处于软删态就不算冲突。

        :param tag_in: 标签更新schema
        :param scope: 数据权限上下文，仅允许修改归属人在当前用户可操作范围内的标签
        :return: 更新后的标签实例
        :raises ParameterException: tag_id 与 tag_code 同时为空（由 get_by_code 抛出）
        :raises NotFoundException: 标签不存在或已软删
        :raises NoPermissionException: 归属人不在当前用户可写范围
        :raises DataAlreadyExistsException: 目标三键与另一条启用标签重复
        :raises DataBaseStorageException: 落库失败（并发撞唯一索引或关联应用无效）
        """
        tag_id: Optional[int] = tag_in.tag_id
        tag_code: Optional[str] = tag_in.tag_code
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True, state__not=1)
            tag_id = instance.id

        await scope.load_owners([instance.created_user])
        if not scope.can_write(instance.created_user):
            error_message: str = f"更新标签信息失败, 标签[{instance.tag_name}]创建人[{instance.created_user}]不在当前用户可操作范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

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
            error_message: str = "更新标签信息失败，目标标签不存在或已被删除，请刷新后重试"
            LOGGER.error(
                f"{error_message}, 关键字段: [tag_id={tag_id}, tag_code={tag_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise NotFoundException(message=error_message) from e
        except IntegrityError as e:
            error_message: str = "更新标签信息失败，相同应用下标签大类和名称可能重复，或关联应用无效，请检查后重试"
            LOGGER.error(
                f"{error_message}, 关键字段: [tag_id={tag_id}, tag_code={tag_code}]\n"
                f"{traceback.format_exc()}"
            )
            raise DataBaseStorageException(message=error_message) from e

    async def delete_tag(self, scope: DataScope, tag_id: Optional[int] = None, tag_code: Optional[str] = None) -> AutoTestTagModel:
        """
        物理删除标签；删除前校验无启用用例的标签数组引用该标签。

        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的标签
        :param tag_id: 标签主键ID，与tag_code二选一
        :param tag_code: 标签标识代码，与tag_id二选一
        :return: 删除后的标签实例快照
        :raises ParameterException: 两个定位参数同时为空
        :raises NotFoundException: 标签不存在或已软删
        :raises NoPermissionException: 归属人不在当前用户可删范围
        :raises DataAlreadyExistsException: 仍有启用用例引用该标签
        """
        if not tag_id and not tag_code:
            error_message: str = "删除标签信息失败, 参数[tag_id]或[tag_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if tag_id:
            instance = await self.get_by_id(tag_id=tag_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(tag_code=tag_code, on_error=True, state__not=1)

        await scope.load_owners([instance.created_user])
        if not scope.can_delete(instance.created_user):
            error_message: str = f"删除标签信息失败, 标签[{instance.tag_name}]创建人[{instance.created_user}]不在当前用户可删除范围内, 无权操作"
            LOGGER.error(error_message)
            raise NoPermissionException(message=error_message)

        from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
        cases_count = await AutoTestCaseCrud().model.filter(case_tags__contains=[instance.id], state__not=1).count()
        if cases_count > 0:
            error_message: str = f"删除标签信息失败, 记录[id={instance.id}]被{cases_count}个用例关联"
            LOGGER.error(error_message)
            raise DataAlreadyExistsException(message=error_message)

        await instance.delete()
        return instance

    async def delete_tags(self, tag_in: AutoTestTagDelete, scope: DataScope) -> int:
        """
        根据ID或code列表批量软删除标签；逐条复用单删的归属与引用校验。

        先一次性批量定位，再逐条校验权限与引用，全部通过后才单次批量软删，
        中途失败不会落库，具备全有或全无语义。

        :param tag_in: 标签删除schema
        :param scope: 数据权限上下文，仅允许删除归属人在当前用户可删除范围内的标签
        :return: 实际软删条数
        :raises ParameterException: 两个ID/code列表同时为空，或列表内存在空值
        :raises NotFoundException: 列表内存在不存在或已软删的标签
        :raises NoPermissionException: 任一归属人不在当前用户可删范围
        :raises DataAlreadyExistsException: 任一标签仍被启用用例引用
        """
        tag_ids: Optional[List[int]] = tag_in.tag_ids
        tag_codes: Optional[List[str]] = tag_in.tag_codes
        if not tag_ids and not tag_codes:
            error_message: str = "删除标签信息失败, 参数[tag_ids]或[tag_codes]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 单次批量定位并按入参顺序收集，首个缺失(或空参)按单条查询原文案抛出，替代循环逐条查询
        targets: List[AutoTestTagModel] = []
        if tag_ids:
            id_map: Dict[int, AutoTestTagModel] = {
                obj.id: obj for obj in await self.model.filter(id__in=tag_ids, state__not=1)
            }
            for tid in tag_ids:
                if not tid:
                    error_message: str = "查询标签信息失败, 参数[tag_id]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = id_map.get(tid)
                if not instance:
                    error_message: str = f"查询标签信息失败, 记录[id={tid}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)
        else:
            code_map: Dict[str, AutoTestTagModel] = {
                obj.tag_code: obj for obj in await self.model.filter(tag_code__in=tag_codes, state__not=1)
            }
            for tcode in tag_codes:
                if not tcode:
                    error_message: str = "查询标签信息失败, 参数[tag_code]不允许为空"
                    LOGGER.error(error_message)
                    raise ParameterException(message=error_message)
                instance = code_map.get(tcode)
                if not instance:
                    error_message: str = f"查询标签信息失败, 记录[code={tcode}]不存在"
                    LOGGER.error(error_message)
                    raise NotFoundException(message=error_message)
                targets.append(instance)

        # 先全量校验行级权限与引用关系，再单次批量软删，保证批量操作全有或全无
        from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
        await scope.load_owners([instance.created_user for instance in targets])
        for instance in targets:
            if not scope.can_delete(instance.created_user):
                error_message: str = f"删除标签信息失败, 标签[{instance.tag_name}]创建人[{instance.created_user}]不在当前用户可删除范围内, 无权操作"
                LOGGER.error(error_message)
                raise NoPermissionException(message=error_message)
            cases_count = await AutoTestCaseCrud().model.filter(case_tags__contains=[instance.id], state__not=1).count()
            if cases_count > 0:
                error_message: str = f"删除标签信息失败, 记录[id={instance.id}] 被{cases_count}个用例关联"
                LOGGER.error(error_message)
                raise DataAlreadyExistsException(message=error_message)
        await self.soft_delete_batch(ids=[instance.id for instance in targets])
        return len(targets)

    async def select_tags(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[AutoTestTagModel]]:
        """
        根据条件分页查询标签列表。

        :param search: Tortoise Q查询条件（归属过滤由视图层拼接）
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录列表)
        :raises ParameterException: 查询或排序字段不被ORM支持
        """
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            error_message: str = "查询标签信息失败，查询或排序条件包含不支持的字段，请调整筛选或排序条件"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e
