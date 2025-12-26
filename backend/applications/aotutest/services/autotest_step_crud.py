# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_step_crud.py
@DateTime: 2025/4/28
"""
from typing import Optional, List, Dict, Any, Set

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from backend.applications.aotutest.models.autotest_model import (
    AutoTestApiStepInfo, AutoTestApiCaseInfo, StepType
)
from backend.applications.aotutest.schemas.autotest_step_schema import (
    AutoTestApiStepCreate, AutoTestApiStepUpdate, AutoTestStepTreeUpdateItem
)
from backend.applications.aotutest.services.autotest_case_crud import AUTOTEST_API_CASE_CRUD
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.core.exceptions.base_exceptions import DataAlreadyExistsException, NotFoundException


class AutoTestApiStepCrud(ScaffoldCrud[AutoTestApiStepInfo, AutoTestApiStepCreate, AutoTestApiStepUpdate]):
    def __init__(self):
        super().__init__(model=AutoTestApiStepInfo)

    async def get_by_id(self, step_id: int) -> Optional[AutoTestApiStepInfo]:
        """根据ID查询步骤明细"""
        return await self.model.filter(id=step_id, state__not=1).first()

    async def get_by_code(self, step_code: str) -> Optional[AutoTestApiStepInfo]:
        """根据code查询用例信息"""
        return await self.model.filter(step_code=step_code, state__not=1).first()

    async def get_by_conditions(
            self,
            conditions: Dict[str, Any],
            only_one: bool = True,
    ) -> Optional[AutoTestApiStepInfo]:
        """根据条件查询用例信息"""
        stmt: QuerySet = self.model.filter(**conditions, state__not=1)
        return await (stmt.first() if only_one else stmt.all())

    async def get_by_case_id(self, case_id: int) -> List[Dict[str, Any]]:
        """
        根据用例ID获取所有步骤（包含所有子步骤、引用测试用例中的步骤）

        该方法通过递归方式构建完整的步骤树结构，包括：
        1. 根步骤（parent_step_id 为 None 的步骤）
        2. 所有子步骤（递归包含子步骤的子步骤）
        3. 引用用例的步骤（如果步骤中配置了 quote_case_id）

        同时会统计并记录该用例所拥有的步骤总数，包括：
        - 直接步骤：属于该用例的所有步骤
        - 子步骤：所有步骤的子级步骤（递归统计）
        - 引用步骤：通过 quote_case_id 引用的其他用例的步骤

        Args:
            case_id (int): 测试用例ID

        Returns:
            List[Dict[str, Any]]: 步骤树列表，每个元素是一个根步骤及其完整的子树结构。
                                 每个步骤字典包含以下字段：
                                 - 步骤基本信息（id, step_no, step_name, step_type等）
                                 - case: 所属用例信息
                                 - children: 子步骤列表（递归结构）
                                 - quote_steps: 引用用例的步骤列表（如果存在）
                                 - quote_case: 引用用例的基本信息（如果存在）

        Raises:
            NotFoundException: 当指定的用例ID不存在时抛出异常

        Note:
            - 只返回状态为正常（state__not=1）的步骤
            - 步骤按照 step_no 排序
            - 引用用例的步骤也会递归构建完整的树结构
            - 步骤数量统计包括所有层级的子步骤和引用步骤

        Example:
            >>> crud = AutoTestApiStepCrud()
            >>> steps = await crud.get_by_case_id(case_id=1)
            >>> # steps 是一个列表，包含所有根步骤的完整树结构
            >>> # 可以通过递归遍历 children 和 quote_steps 访问所有步骤
        """
        # 业务层验证：检查用例是否存在
        case = await AutoTestApiCaseInfo.filter(id=case_id, state__not=1).first()
        if not case:
            raise NotFoundException(message=f"用例(id={case_id})信息不存在")

        # 获取所有根步骤（没有父步骤的步骤）
        root_steps = await self.model.filter(
            case_id=case_id,
            parent_step_id__isnull=True,
            state__not=1
        ).order_by("step_no").all()

        # 步骤计数器：用于统计该用例拥有的步骤总数
        # 使用列表存储以便在嵌套函数中修改
        step_counter = {
            "direct_steps": 0,  # 直接属于该用例的步骤数（根步骤）
            "child_steps": 0,  # 所有子步骤数（递归统计，不包括根步骤）
            "quote_steps": 0,  # 引用用例的步骤数
            "total_steps": 0  # 总步骤数（direct_steps + child_steps + quote_steps）
        }

        # 递归构建步骤树
        async def build_step_tree(step: AutoTestApiStepInfo, is_quote: bool = False) -> Dict[str, Any]:
            """
            递归构建步骤树

            Args:
                step: 当前步骤对象
                is_quote: 是否为引用步骤（用于统计区分）

            Returns:
                包含步骤信息和子树的字典
            """
            # 统计步骤数量
            step_counter["total_steps"] += 1
            if is_quote:
                # 引用步骤及其所有子步骤都计入 quote_steps
                step_counter["quote_steps"] += 1
            else:
                # 非引用步骤：根据是否有父步骤判断是根步骤还是子步骤
                if step.parent_step_id is None:
                    # 根步骤（parent_step_id 为 None）
                    step_counter["direct_steps"] += 1
                else:
                    # 子步骤（parent_step_id 不为 None）
                    step_counter["child_steps"] += 1

            # 获取步骤基本信息
            # step_dict = await step.to_dict(fk=False)
            step_dict = await step.to_dict()
            step_dict["step_id"] = step_dict.pop("id")

            # 获取用例信息（业务层手动查询）
            if step.case_id:
                case = await AutoTestApiCaseInfo.filter(id=step.case_id, state__not=1).first()
                if case:
                    step_dict["case"] = await case.to_dict()

            # 获取子步骤（递归构建）
            children = await self.model.filter(
                parent_step_id=step.id,
                state__not=1
            ).order_by("step_no").all()

            if children:
                step_dict["children"] = [await build_step_tree(child, is_quote=is_quote) for child in children]
            else:
                step_dict["children"] = []

            # 如果引用了其他用例，获取引用用例的所有步骤（包含子步骤）
            if step.quote_case_id:
                # 业务层验证：检查引用用例是否存在
                quote_case = await AutoTestApiCaseInfo.filter(id=step.quote_case_id, state__not=1).first()
                if quote_case:
                    # 递归获取引用用例的所有根步骤
                    quote_case_root_steps = await self.model.filter(
                        case_id=step.quote_case_id,
                        parent_step_id__isnull=True,
                        state__not=1
                    ).order_by("step_no").all()

                    quote_steps = []
                    for quote_step in quote_case_root_steps:
                        # 标记为引用步骤进行统计
                        quote_steps.append(await build_step_tree(quote_step, is_quote=True))

                    step_dict["quote_steps"] = quote_steps
                    # 添加引用用例的基本信息
                    step_dict["quote_case"] = await quote_case.to_dict()
                else:
                    step_dict["quote_steps"] = []
                    step_dict["quote_case"] = None
            else:
                step_dict["quote_steps"] = []
                step_dict["quote_case"] = None

            return step_dict

        # 构建所有根步骤的树
        result = []
        for root_step in root_steps:
            result.append(await build_step_tree(root_step))

        # 没有测试步骤明细时将测试用例本身添加到返回结果
        if not result:
            result.append({"case": await case.to_dict()})
        result.append(step_counter)
        return result

    async def create_step(self, step_in: AutoTestApiStepCreate) -> AutoTestApiStepInfo:
        """创建步骤明细"""
        # 业务层验证：检查用例是否存在
        case = await AutoTestApiCaseInfo.filter(id=step_in.case_id, state__not=1).first()
        if not case:
            raise NotFoundException(message=f"用例(id={step_in.case_id})信息不存在")

        # 业务层验证：如果指定了父步骤，检查父步骤是否存在
        if step_in.parent_step_id:
            parent_step = await self.model.filter(id=step_in.parent_step_id, state__not=1).first()
            if not parent_step:
                raise NotFoundException(message=f"父级步骤(id={step_in.parent_step_id})信息不存在")
            # 确保父步骤属于同一个用例
            if parent_step.case_id != step_in.case_id:
                raise NotFoundException(
                    message=f"父级步骤(id={step_in.parent_step_id})与当前用例(id={step_in.case_id})不匹配"
                )

        # 业务层验证：如果指定了引用用例，检查引用用例是否存在
        if step_in.quote_case_id:
            quote_case = await AutoTestApiCaseInfo.filter(id=step_in.quote_case_id, state__not=1).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={step_in.quote_case_id})信息不存在")

        # 检查同一用例下步骤序号是否已存在
        existing_step = await self.model.filter(
            case_id=step_in.case_id,
            step_no=step_in.step_no,
            state__not=1
        ).first()
        if existing_step:
            raise DataAlreadyExistsException(
                message=f"用例(id={step_in.case_id})下步骤序号(step_no={step_in.step_no})已存在"
            )

        try:
            instance = await self.create(step_in)
            # 重新加载步骤数据
            return await self.get_by_id(instance.id)
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"创建步骤明细失败: {str(e)}")

    async def update_step(self, step_in: AutoTestApiStepUpdate) -> AutoTestApiStepInfo:
        """更新步骤明细"""
        step_id = step_in.step_id
        instance = await self.query(step_id)
        if not instance or instance.state != -1:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 构建更新字典
        update_dict = {
            key: value for key, value in step_in.model_dump(exclude_unset=True, exclude={"id"}).items()
            if value is not None
        }

        # 如果更新了步骤序号，检查是否冲突
        if "step_no" in update_dict:
            case_id = update_dict.get("case_id", instance.case_id)
            existing_step = await self.model.filter(
                case_id=case_id,
                step_no=update_dict["step_no"],
                state__not=1
            ).exclude(id=step_id).first()
            if existing_step:
                raise DataAlreadyExistsException(
                    message=f"用例(id={case_id})下步骤序号(step_no={update_dict['step_no']})已存在"
                )

        # 业务层验证：如果更新了用例ID，检查用例是否存在
        if "case_id" in update_dict:
            case = await AutoTestApiCaseInfo.filter(id=update_dict["case_id"], state__not=1).first()
            if not case:
                raise NotFoundException(message=f"用例(id={update_dict['case_id']})信息不存在")

        # 业务层验证：如果更新了父步骤ID，检查父步骤是否存在
        if "parent_step_id" in update_dict:
            if update_dict["parent_step_id"]:
                parent_step = await self.model.filter(id=update_dict["parent_step_id"], state__not=1).first()
                if not parent_step:
                    raise NotFoundException(message=f"父级步骤(id={update_dict['parent_step_id']})信息不存在")
                # 确保父步骤属于同一个用例
                case_id = update_dict.get("case_id", instance.case_id)
                if parent_step.case_id != case_id:
                    raise NotFoundException(
                        message=f"父级步骤(id={update_dict['parent_step_id']})与当前用例(id={case_id})不匹配"
                    )
                # 检查是否形成循环引用
                if parent_step.id == step_id:
                    raise DataAlreadyExistsException(message="不能将自身设置为父步骤")
                # 检查循环引用（防止父步骤的父步骤链中包含当前步骤）
                visited = set()
                current_parent_id = parent_step.parent_step_id
                while current_parent_id:
                    if current_parent_id == step_id:
                        raise DataAlreadyExistsException(message="检测到循环引用，无法更新步骤")
                    if current_parent_id in visited:
                        break
                    visited.add(current_parent_id)
                    parent = await self.model.filter(id=current_parent_id, state__not=1).first()
                    if not parent:
                        break
                    current_parent_id = parent.parent_step_id

        # 业务层验证：如果更新了引用用例ID，检查引用用例是否存在
        if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
            quote_case = await AutoTestApiCaseInfo.filter(id=update_dict["quote_case_id"], state__not=1).first()
            if not quote_case:
                raise NotFoundException(message=f"引用用例(id={update_dict['quote_case_id']})信息不存在")

        try:
            instance = await self.update(id=step_id, obj_in=update_dict)
            # 重新加载步骤数据
            return await self.get_by_id(instance.id)
        except DoesNotExist:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")
        except IntegrityError as e:
            raise DataAlreadyExistsException(message=f"更新步骤明细失败: {str(e)}")

    async def delete_step(self, step_id: int) -> AutoTestApiStepInfo:
        """删除步骤明细（软删除）"""
        instance = await self.query(step_id)
        if not instance or instance.state != -1:
            raise NotFoundException(message=f"步骤明细(id={step_id})信息不存在")

        # 检查是否有子步骤
        children_count = await self.model.filter(parent_step_id=step_id, state__not=1).count()
        if children_count > 0:
            raise DataAlreadyExistsException(
                message=f"步骤明细(id={step_id})存在子步骤，无法删除"
            )

        # 软删除
        instance.state = 1
        await instance.save()
        return instance

    async def delete_steps_recursive(
            self,
            step_id: Optional[int] = None,
            step_code: Optional[str] = None,
            parent_step_id: Optional[int] = None,
            case_id: Optional[int] = None,
            exclude_step_ids: Optional[Set[tuple]] = None
    ) -> int:
        """
        递归删除步骤及其所有子步骤（软删除）

        Args:
            step_id: 要删除的步骤ID（与step_code二选一）
            step_code: 要删除的步骤代码（与step_id二选一）
            parent_step_id: 要删除的父步骤ID下的所有子步骤
            case_id: 要删除的用例ID下的所有根步骤（parent_step_id为None的步骤）
            exclude_step_ids: 排除的步骤集合，格式为 {(step_id, step_code), ...}，这些步骤不会被删除

        Returns:
            int: 删除的步骤数量（包括子步骤）

        Note:
            - step_id/step_code 和 parent_step_id 和 case_id 只能指定一个
            - 如果指定了 exclude_step_ids，则这些步骤及其子步骤不会被删除
            - 删除是递归的，会删除所有子步骤
        """
        if exclude_step_ids is None:
            exclude_step_ids = set()

        deleted_count = 0

        async def delete_step_and_children(step: AutoTestApiStepInfo) -> int:
            """递归删除步骤及其所有子步骤"""
            deleted = 0
            # 先删除所有子步骤
            children = await self.model.filter(parent_step_id=step.id, state__not=1).all()
            for child in children:
                deleted += await delete_step_and_children(child)
            # 然后删除当前步骤（软删除）
            if (step.id, step.step_code) not in exclude_step_ids:
                step.state = 1
                await step.save()
                deleted += 1
            return deleted

        # 根据参数类型执行不同的删除逻辑
        if step_id is not None or step_code is not None:
            # 单步骤删除
            conditions = {"state__not": 1}
            if step_id is not None:
                conditions["id"] = step_id
            if step_code is not None:
                conditions["step_code"] = step_code

            step = await self.model.filter(**conditions).first()
            if step:
                deleted_count = await delete_step_and_children(step)
        elif parent_step_id is not None:
            # 删除指定父步骤下的所有子步骤
            existing_steps = await self.model.filter(
                parent_step_id=parent_step_id,
                state__not=1
            ).all()
            for step in existing_steps:
                if (step.id, step.step_code) not in exclude_step_ids:
                    deleted_count += await delete_step_and_children(step)
        elif case_id is not None:
            # 删除指定用例下的所有根步骤（parent_step_id为None的步骤）
            existing_steps = await self.model.filter(
                case_id=case_id,
                parent_step_id__isnull=True,
                state__not=1
            ).all()
            for step in existing_steps:
                if (step.id, step.step_code) not in exclude_step_ids:
                    deleted_count += await delete_step_and_children(step)

        return deleted_count

    async def select_steps(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        """按条件查询步骤明细"""
        # 默认只查询未删除的记录
        search &= Q(state__not=1)
        return await self.list(
            page=page,
            page_size=page_size,
            search=search,
            order=order
        )

    async def batch_update_or_create_steps(
            self,
            steps_data: List[AutoTestStepTreeUpdateItem],
            parent_step_id: Optional[int] = None,
            processed_step_ids: Optional[set] = None
    ) -> Dict[str, Any]:
        if processed_step_ids is None:
            processed_step_ids: Set = set()

        created_count: int = 0
        updated_count: int = 0
        deleted_count: int = 0  # 删除的步骤数量
        failed_steps: List[Dict[str, Any]] = []
        passed_steps: List[Dict[str, Any]] = []  # 存储处理成功的步骤信息

        # 收集所有传入步骤的case_id，用于后续删除多余步骤
        case_ids: Set[int] = set()
        for step_data in steps_data:
            if step_data.case_id:
                case_ids.add(step_data.case_id)

        for step_data in steps_data:
            # 去重：如果已经处理过该步骤，跳过
            step_id: Optional[int] = step_data.step_id
            step_no: Optional[int] = step_data.step_no
            step_code: Optional[str] = step_data.step_code
            if step_id and step_code and (step_id, step_code) in processed_step_ids:
                continue
            try:
                # 检查步骤是否存在（只有在提供了 step_id 时才查询）
                if not step_id and not step_code:
                    instance = None
                else:
                    instance: Optional[AutoTestApiStepInfo] = await self.get_by_conditions(
                        only_one=True,
                        conditions={"id": step_id, "step_code": step_code}
                    )
                if not instance:
                    # 步骤不存在，执行新增，及验证必填字段
                    if not step_data.case_id:
                        failed_steps.append({"step_no": step_no, "reason": "新增步骤时，步骤所属用例不能为空"})
                        continue
                    if not step_data.step_no:
                        failed_steps.append({"step_no": step_no, "reason": "新增步骤时，步骤序号不能为空"})
                        continue
                    if not step_data.step_type:
                        failed_steps.append({"step_no": step_no, "reason": "新增步骤时，步骤类型不能为空"})
                        continue
                    if not step_data.case_type:
                        failed_steps.append({"step_no": step_no, "reason": "新增步骤时，用例所属类型不能为空"})
                        continue

                    # 检查用例是否存在
                    case: Optional[AutoTestApiCaseInfo] = await AUTOTEST_API_CASE_CRUD.get_by_id(
                        case_id=step_data.case_id
                    )
                    if not case:
                        failed_steps.append({"step_no": step_no, "reason": f"用例({step_data.case_id})信息不存在"})
                        continue

                    # 检查同一用例下步骤序号是否已存在
                    existing_step: Optional[AutoTestApiStepInfo] = await self.model.filter(
                        case_id=step_data.case_id,
                        step_no=step_data.step_no,
                        state__not=1
                    ).first()
                    if existing_step:
                        failed_steps.append({"step_no": step_no, "reason": f"步骤序号已存在"})
                        continue

                    # 验证父步骤
                    final_parent_step_id = parent_step_id if parent_step_id is not None else step_data.parent_step_id
                    if final_parent_step_id:
                        parent_step = await self.model.filter(id=final_parent_step_id, state__not=1).first()
                        if not parent_step:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"父级步骤(id={final_parent_step_id})信息不存在"
                            })
                            continue
                        # 确保父步骤属于同一个用例
                        if parent_step.case_id != step_data.case_id:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"父级步骤(id={final_parent_step_id})与当前用例(id={step_data.case_id})不匹配"
                            })
                            continue
                        # 验证父步骤类型：只有循环结构和条件分支允许拥有子级步骤
                        ALLOWED_CHILDREN_TYPES = {StepType.LOOP, StepType.IF}
                        if parent_step.step_type not in ALLOWED_CHILDREN_TYPES:
                            failed_steps.append({
                                "step_no": step_no,
                                "reason": f"父级步骤(id={final_parent_step_id}, step_type={parent_step.step_type})不允许包含子步骤，仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                            })
                            continue

                    # 构建新增数据
                    create_dict = step_data.model_dump(
                        exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code"},
                        exclude_none=True
                    )
                    if final_parent_step_id is not None:
                        create_dict["parent_step_id"] = final_parent_step_id

                    # 执行新增（直接使用字典，因为create方法接受字典）
                    new_instance: AutoTestApiStepInfo = await self.create(create_dict)
                    created_count += 1
                    processed_step_ids.add((new_instance.id, new_instance.step_code))
                    step_dict: Dict[str, Any] = await new_instance.to_dict(
                        include_fields=["step_code", "step_name"]
                    )
                    step_dict["created"] = True
                    step_dict["step_id"] = new_instance.id
                    passed_steps.append(step_dict)

                    # 递归处理子步骤
                    children: List[AutoTestStepTreeUpdateItem] = step_data.children
                    if children:
                        child_result = await self.batch_update_or_create_steps(
                            steps_data=children,
                            parent_step_id=new_instance.id,
                            processed_step_ids=processed_step_ids
                        )
                        created_count += child_result["created_count"]
                        updated_count += child_result["updated_count"]
                        deleted_count += child_result.get("deleted_count", 0)
                        failed_steps.extend(child_result["failed_steps"])
                        passed_steps.extend(child_result.get("passed_steps", []))

                else:
                    # 步骤存在，执行更新
                    # 构建更新数据，排除 case、children、quote_steps、quote_case 等字段
                    update_dict = step_data.model_dump(
                        exclude={"id", "case", "children", "quote_steps", "quote_case", "step_code"},
                        exclude_none=True
                    )
                    # 处理 parent_step_id
                    if "parent_step_id" not in step_data.model_dump(exclude_unset=True) and parent_step_id is not None:
                        update_dict["parent_step_id"] = parent_step_id
                    elif step_data.parent_step_id is not None:
                        update_dict["parent_step_id"] = step_data.parent_step_id
                    elif step_data.parent_step_id is None and parent_step_id is None:
                        # 明确设置为None（根步骤）
                        update_dict["parent_step_id"] = None

                    # 如果更新了步骤序号，检查是否冲突
                    if "step_no" in update_dict:
                        case_id = update_dict.get("case_id", instance.case_id)
                        existing_step = await self.model.filter(
                            case_id=case_id,
                            step_no=update_dict["step_no"],
                            state__not=1
                        ).exclude(id=step_id).first()
                        if existing_step:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"用例(id={case_id})下步骤序号(step_no={update_dict['step_no']})已存在"
                            })
                            # 即使序号冲突，也要递归处理子步骤
                            children: List[AutoTestStepTreeUpdateItem] = step_data.children
                            if children:
                                child_result = await self.batch_update_or_create_steps(
                                    steps_data=children,
                                    parent_step_id=step_id,
                                    processed_step_ids=processed_step_ids
                                )
                                created_count += child_result["created_count"]
                                updated_count += child_result["updated_count"]
                                failed_steps.extend(child_result["failed_steps"])
                                passed_steps.extend(child_result.get("passed_steps", []))
                            continue

                    # 业务层验证：如果更新了用例ID，检查用例是否存在
                    if "case_id" in update_dict:
                        case: Optional[AutoTestApiCaseInfo] = await AutoTestApiCaseInfo.filter(
                            id=update_dict["case_id"], state__not=1).first()
                        if not case:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"用例(id={update_dict['case_id']})信息不存在"
                            })
                            continue

                    # 业务层验证：如果更新了父步骤ID，检查父步骤是否存在
                    if "parent_step_id" in update_dict and update_dict["parent_step_id"]:
                        parent_step = await self.model.filter(
                            id=update_dict["parent_step_id"],
                            state__not=1
                        ).first()
                        if not parent_step:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"父级步骤(id={update_dict['parent_step_id']})信息不存在"
                            })
                            continue
                        # 确保父步骤属于同一个用例
                        case_id = update_dict.get("case_id", instance.case_id)
                        if parent_step.case_id != case_id:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"父级步骤(id={update_dict['parent_step_id']})与当前用例(id={case_id})不匹配"
                            })
                            continue
                        # 验证父步骤类型：只有循环结构和条件分支允许拥有子级步骤
                        ALLOWED_CHILDREN_TYPES = {StepType.LOOP, StepType.IF}
                        if parent_step.step_type not in ALLOWED_CHILDREN_TYPES:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"父级步骤(id={update_dict['parent_step_id']}, step_type={parent_step.step_type})不允许包含子步骤，仅允许'循环结构'和'条件分支'类型的步骤包含子步骤"
                            })
                            continue
                        # 检查是否形成循环引用（包括深层循环引用）
                        if parent_step.id == step_id:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": "不能将自身设置为父步骤"
                            })
                            continue
                        # 检查深层循环引用（防止父步骤的父步骤链中包含当前步骤）
                        visited = set()
                        current_parent_id = parent_step.parent_step_id
                        while current_parent_id:
                            if current_parent_id == step_id:
                                failed_steps.append({
                                    "step_id": step_id,
                                    "reason": "检测到循环引用，无法更新步骤"
                                })
                                break
                            if current_parent_id in visited:
                                break
                            visited.add(current_parent_id)
                            parent = await self.model.filter(id=current_parent_id, state__not=1).first()
                            if not parent:
                                break
                            current_parent_id = parent.parent_step_id
                        # 如果检测到循环引用，跳过当前步骤的更新
                        if current_parent_id == step_id:
                            continue

                    # 业务层验证：如果更新了引用用例ID，检查引用用例是否存在
                    if "quote_case_id" in update_dict and update_dict["quote_case_id"]:
                        quote_case = await AutoTestApiCaseInfo.filter(
                            id=update_dict["quote_case_id"],
                            state__not=1
                        ).first()
                        if not quote_case:
                            failed_steps.append({
                                "step_id": step_id,
                                "reason": f"引用用例(id={update_dict['quote_case_id']})信息不存在"
                            })
                            continue

                    # 执行更新
                    updated_instance = await self.update(id=step_id, obj_in=update_dict)
                    updated_count += 1
                    processed_step_ids.add((step_id, updated_instance.step_code))
                    step_dict: Dict[str, Any] = await updated_instance.to_dict(
                        include_fields=["step_code", "step_name"]
                    )
                    step_dict["created"] = False
                    step_dict["step_id"] = step_id
                    passed_steps.append(step_dict)

                    # 递归处理子步骤
                    children: List[AutoTestStepTreeUpdateItem] = step_data.children
                    if children:
                        child_result = await self.batch_update_or_create_steps(
                            steps_data=children,
                            parent_step_id=step_id,
                            processed_step_ids=processed_step_ids
                        )
                        created_count += child_result["created_count"]
                        updated_count += child_result["updated_count"]
                        deleted_count += child_result.get("deleted_count", 0)
                        failed_steps.extend(child_result["failed_steps"])
                        passed_steps.extend(child_result.get("passed_steps", []))

            except Exception as e:
                failed_steps.append({"step_id": step_id, "reason": str(e)})
                # 即使当前步骤处理失败，也尝试递归处理子步骤
                children: List[AutoTestStepTreeUpdateItem] = step_data.children
                if children:
                    try:
                        child_result = await self.batch_update_or_create_steps(
                            steps_data=children,
                            parent_step_id=parent_step_id,
                            processed_step_ids=processed_step_ids
                        )
                        created_count += child_result["created_count"]
                        updated_count += child_result["updated_count"]
                        deleted_count += child_result.get("deleted_count", 0)
                        failed_steps.extend(child_result["failed_steps"])
                        passed_steps.extend(child_result.get("passed_steps", []))
                    except Exception as child_e:
                        pass

        # 删除多余的步骤：处理完所有传入的步骤后，删除那些不在processed_step_ids中的步骤
        # 只处理根步骤（parent_step_id为None）或指定父步骤的子步骤
        if case_ids or parent_step_id is not None:
            if parent_step_id is not None:
                # 删除指定父步骤下的所有子步骤（排除已处理的步骤）
                deleted_count = await self.delete_steps_recursive(
                    parent_step_id=parent_step_id,
                    exclude_step_ids=processed_step_ids
                )
            elif case_ids:
                # 删除所有case_ids下的根步骤（排除已处理的步骤）
                for case_id in case_ids:
                    deleted_count += await self.delete_steps_recursive(
                        case_id=case_id,
                        exclude_step_ids=processed_step_ids
                    )

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
            "failed_steps": failed_steps,
            "passed_steps": passed_steps
        }


AUTOTEST_API_STEP_CRUD = AutoTestApiStepCrud()
