# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_mapping_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q

from backend.applications.aotutest.models.autotest_model import (
    AutoTestStepMapping, AutoTestStepInfo, AutoTestCaseInfo
)
from backend.applications.aotutest.schemas.autotest_mapping_schema import (
    AutoTestStepMappingCreate,
    AutoTestStepMappingUpdate
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestStepMappingCrud(ScaffoldCrud[AutoTestStepMapping, AutoTestStepMappingCreate, AutoTestStepMappingUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestStepMapping)

    async def get_by_id(self, mapping_id: int) -> Optional[AutoTestStepMapping]:
        """根据ID查询步骤映射"""
        return await self.model.filter(id=mapping_id).prefetch_related(
            "case", "step_info", "parent_mapping"
        ).first()

    async def get_by_case_id(self, case_id: int) -> List[AutoTestStepMapping]:
        """根据用例ID查询所有根步骤映射（没有父步骤的步骤）"""
        return await self.model.filter(
            case__id=case_id,
            parent_mapping__isnull=True
        ).prefetch_related(
            "case", "step_info", "parent_mapping"
        ).order_by("step_no").all()

    async def get_step_tree_by_mapping_id(self, mapping_id: int) -> Dict[str, Any]:
        """根据步骤映射ID获取步骤树（包含所有子步骤、引用测试用例中的步骤）"""
        # 获取步骤映射
        mapping = await self.get_by_id(mapping_id)
        if not mapping:
            raise NotFoundException(message=f"步骤映射(id={mapping_id})信息不存在")

        # 递归构建步骤树
        async def build_mapping_tree(mapping_obj: AutoTestStepMapping) -> Dict[str, Any]:
            # 获取步骤明细信息（关联数据已通过prefetch_related加载）
            step_info_dict = None
            if mapping_obj.step_info:
                step_info_dict = await mapping_obj.step_info.to_dict(fk=True)

            # 构建映射基本信息
            mapping_dict = {
                "id": mapping_obj.id,
                "case_id": mapping_obj.case.id if mapping_obj.case else None,
                "step_info_id": mapping_obj.step_info.id if mapping_obj.step_info else None,
                "parent_mapping_id": mapping_obj.parent_mapping.id if mapping_obj.parent_mapping else None,
                "step_no": mapping_obj.step_no,
                "step_info": step_info_dict,
                "children": []
            }

            # 获取子步骤映射
            child_mappings = await self.model.filter(
                parent_mapping__id=mapping_obj.id
            ).prefetch_related(
                "case", "step_info", "parent_mapping"
            ).order_by("step_no").all()

            # 递归构建子步骤树
            for child_mapping in child_mappings:
                mapping_dict["children"].append(await build_mapping_tree(child_mapping))

            # 如果步骤明细引用了其他用例，获取引用用例的步骤
            if step_info_dict and step_info_dict.get("quote_case_id"):
                quote_case_id = step_info_dict["quote_case_id"]
                # 获取引用用例的所有根步骤映射
                quote_case_mappings = await self.get_by_case_id(quote_case_id)
                quote_steps = []
                for quote_mapping in quote_case_mappings:
                    quote_steps.append(await build_mapping_tree(quote_mapping))
                mapping_dict["quote_steps"] = quote_steps
            else:
                mapping_dict["quote_steps"] = []

            return mapping_dict

        return await build_mapping_tree(mapping)

    async def create_mapping(self, mapping_in: AutoTestStepMappingCreate) -> AutoTestStepMapping:
        """创建步骤映射"""
        # 检查用例是否存在
        case = await AutoTestCaseInfo.filter(id=mapping_in.case_id).first()
        if not case:
            raise NotFoundException(message=f"用例(id={mapping_in.case_id})信息不存在")

        # 检查步骤明细是否存在
        step_info = await AutoTestStepInfo.filter(id=mapping_in.step_info_id).first()
        if not step_info:
            raise NotFoundException(message=f"步骤明细(id={mapping_in.step_info_id})信息不存在")

            # 如果指定了父步骤映射，检查父步骤映射是否存在
        if mapping_in.parent_mapping_id:
            parent_mapping = await self.model.filter(id=mapping_in.parent_mapping_id).prefetch_related("case").first()
            if not parent_mapping:
                raise NotFoundException(message=f"父级步骤映射(id={mapping_in.parent_mapping_id})信息不存在")
            # 确保父步骤映射属于同一个用例
            await parent_mapping.fetch_related("case")
            if parent_mapping.case.id != mapping_in.case_id:
                raise NotFoundException(
                    message=f"父级步骤映射(id={mapping_in.parent_mapping_id})与当前用例(id={mapping_in.case_id})不匹配"
                )

        # 检查同一用例下步骤序号是否已存在
        existing_mapping = await self.model.filter(
            case__id=mapping_in.case_id,
            step_no=mapping_in.step_no
        ).first()
        if existing_mapping:
            raise DataAlreadyExistsException(
                message=f"用例(id={mapping_in.case_id})下步骤序号(step_no={mapping_in.step_no})已存在"
            )

        try:
            instance = await self.create(mapping_in)
            # 重新加载关联数据
            return await self.get_by_id(instance.id)
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建步骤映射失败: {str(e)}")

    async def update_mapping(self, mapping_in: AutoTestStepMappingUpdate) -> AutoTestStepMapping:
        """更新步骤映射"""
        mapping_id = mapping_in.id
        instance = await self.query(mapping_id)
        if not instance:
            raise NotFoundException(message=f"步骤映射(id={mapping_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in mapping_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了步骤序号，检查是否冲突
        if "step_no" in update_dict:
            await instance.fetch_related("case")
            case_id = update_dict.get("case_id", instance.case.id)
            existing_mapping = await self.model.filter(
                case__id=case_id,
                step_no=update_dict["step_no"]
            ).exclude(id=mapping_id).first()
            if existing_mapping:
                raise DataAlreadyExistsException(
                    message=f"用例(id={case_id})下步骤序号(step_no={update_dict['step_no']})已存在"
                )

        # 如果更新了用例ID，检查用例是否存在
        if "case_id" in update_dict:
            case = await AutoTestCaseInfo.filter(id=update_dict["case_id"]).first()
            if not case:
                raise NotFoundException(message=f"用例(id={update_dict['case_id']})信息不存在")

        # 如果更新了步骤明细ID，检查步骤明细是否存在
        if "step_info_id" in update_dict:
            step_info = await AutoTestStepInfo.filter(id=update_dict["step_info_id"]).first()
            if not step_info:
                raise NotFoundException(message=f"步骤明细(id={update_dict['step_info_id']})信息不存在")

        # 如果更新了父步骤映射ID，检查父步骤映射是否存在
        if "parent_mapping_id" in update_dict:
            if update_dict["parent_mapping_id"]:
                parent_mapping = await self.model.filter(id=update_dict["parent_mapping_id"]).prefetch_related(
                    "case").first()
                if not parent_mapping:
                    raise NotFoundException(message=f"父级步骤映射(id={update_dict['parent_mapping_id']})信息不存在")
                # 确保父步骤映射属于同一个用例
                await instance.fetch_related("case")
                await parent_mapping.fetch_related("case")
                case_id = update_dict.get("case_id", instance.case.id)
                if parent_mapping.case.id != case_id:
                    raise NotFoundException(
                        message=f"父级步骤映射(id={update_dict['parent_mapping_id']})与当前用例(id={case_id})不匹配"
                    )
                # 检查是否形成循环引用
                if parent_mapping.id == mapping_id:
                    raise DataAlreadyExistsException(message="不能将自身设置为父步骤映射")

        try:
            instance = await self.update(id=mapping_id, obj_in=update_dict)
            # 重新加载关联数据
            return await self.get_by_id(instance.id)
        except DoesNotExist:
            raise NotFoundException(message=f"步骤映射(id={mapping_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新步骤映射失败: {str(e)}")

    async def delete_mapping(self, mapping_id: int) -> AutoTestStepMapping:
        """删除步骤映射"""
        instance = await self.query(mapping_id)
        if not instance:
            raise NotFoundException(message=f"步骤映射(id={mapping_id})信息不存在")

        # 检查是否有子步骤映射
        children_count = await self.model.filter(parent_mapping__id=mapping_id).count()
        if children_count > 0:
            raise DataAlreadyExistsException(
                message=f"步骤映射(id={mapping_id})存在子步骤映射，无法删除"
            )

        await instance.delete()
        return instance

    async def select_mappings(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询步骤映射"""
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order,
            related=["case", "step_info", "parent_mapping"]
        )


AUTO_TEST_STEP_MAPPING_CRUD = AutoTestStepMappingCrud()
