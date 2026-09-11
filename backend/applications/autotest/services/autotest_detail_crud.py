# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_detail_crud
@DateTime: 2025/11/27 14:25
"""
import traceback
from typing import Any, Dict, Optional, List, Tuple

from tortoise.exceptions import IntegrityError, FieldError
from tortoise.expressions import Q

from backend.applications.autotest.models.autotest_detail_model import AutoTestDetailModel
from backend.applications.autotest.schemas.autotest_detail_schema import (
    AutoTestDetailCreate,
    AutoTestDetailUpdate
)
from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud
from backend.applications.autotest.services.autotest_report_crud import AutoTestReportCrud
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)


class AutoTestDetailCrud(ScaffoldCrud[AutoTestDetailModel, AutoTestDetailCreate, AutoTestDetailUpdate]):
    # 明细轻量列清单：分页查询与树模式全量查询共用，保证两模式返回字段结构一致
    DETAIL_LIGHT_COLUMNS: Tuple[str, ...] = (
        "id", "case_id", "parent_step_id",
        "step_id", "step_no", "step_name", "step_type", "step_state", "step_elapsed", "step_exec_except",
        "loop_cycles", "branch_index", "branch_match", "dataset_name", "response_elapsed",
        "request_env_name", "request_config_name", "database_operates",
    )

    def __init__(self):
        super().__init__(model=AutoTestDetailModel)

    async def get_by_id(self, detail_id: int, on_error: bool = False, **kwargs) -> Optional[AutoTestDetailModel]:
        """
        根据主键ID查询明细。

        :param detail_id: 明细主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 明细实例或None
        """
        if not detail_id:
            error_message: str = "查询明细信息失败, 参数[detail_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=detail_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 记录[id={detail_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, detail_code: str, on_error: bool = False, **kwargs) -> Optional[AutoTestDetailModel]:
        """
        根据报告标识代码查询明细。

        :param detail_code: 报告标识代码report_code
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 明细实例或None
        """
        if not detail_code:
            error_message: str = "查询明细信息失败, 参数[detail_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(report_code=detail_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询明细信息失败, 记录[detail_code={detail_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def create_detail(self, detail_in: AutoTestDetailCreate, *, skip_report_check: bool = False) -> AutoTestDetailModel:
        """
        创建执行明细，校验用例与报告存在(可跳过报告校验)。

        :param detail_in: 明细创建schema
        :param skip_report_check: 为True时不校验报告是否存在
        :return: 创建后的明细实例
        """
        case_id: int = detail_in.case_id
        case_code: str = detail_in.case_code

        await AutoTestCaseCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            id=case_id,
            case_code=case_code,
            state__not=1,
        )

        if not skip_report_check:
            report_code: str = detail_in.report_code
            await AutoTestReportCrud().get_by_conditions(
                only_one=True,
                on_error=True,
                case_id=case_id,
                case_code=case_code,
                report_code=report_code,
                state__not=1,
            )
        try:
            report_dict = detail_in.model_dump(exclude_none=True, exclude_unset=True)
            instance = await self.create(report_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"新增明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e
        except Exception as e:
            error_message: str = f"新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def create_details(self, details_in: List[AutoTestDetailCreate]) -> List[AutoTestDetailModel]:
        """
        批量创建执行明细，仅供落库事务内使用(不校验用例与报告存在性，调用方(执行/调试落库事务)在调用前已完成用例校验，并在同一事务内创建了与明细)。
        report_code同源的报告，故跳过存在性校验；唯一约束(report_code+case_code+step_code+loop_cycles)
        冲突时整批失败，由外层事务统一回滚，与逐条创建的事务语义一致。

        :param details_in: 明细创建schema列表
        :return: 创建后的明细实例列表(自增主键不回填)
        """
        if not details_in:
            return []
        try:
            instances: List[AutoTestDetailModel] = []
            for detail in details_in:
                detail_dict = detail.model_dump(exclude_none=True, exclude_unset=True)
                self.fill_created_user(detail_dict)
                instances.append(self.model(**detail_dict))
            await self.model.bulk_create(instances)
            return instances
        except IntegrityError as e:
            error_message: str = f"批量新增明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e
        except Exception as e:
            error_message: str = f"批量新增明细信息异常, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def update_detail(self, detail_in: AutoTestDetailUpdate) -> AutoTestDetailModel:
        """
        更新明细，需提供detail_id或(report_code, step_code)定位。

        :param detail_in: 明细更新schema
        :return: 更新后的明细实例
        """
        case_id: Optional[int] = detail_in.case_id
        case_code: Optional[str] = detail_in.case_code

        await AutoTestCaseCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            id=case_id,
            case_code=case_code,
            state__not=1,
        )

        report_code = detail_in.report_code
        await AutoTestReportCrud().get_by_conditions(
            only_one=True,
            on_error=True,
            case_id=case_id,
            case_code=case_code,
            report_code=report_code,
            state__not=1,
        )

        detail_id: Optional[int] = detail_in.detail_id
        step_code: Optional[str] = detail_in.step_code
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数[detail_id]或[report_code, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if detail_id:
            await self.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                report_code=report_code,
                step_code=step_code,
                state__not=1,
            )
            detail_id = instance.id
        try:
            update_dict = detail_in.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude={"report_code", "step_code", "case_code", "case_id", "detail_id"}
            )
            instance = await self.update(id=detail_id, obj_in=update_dict)
            return instance
        except IntegrityError as e:
            error_message: str = f"更新明细信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_detail(
            self,
            detail_id: Optional[int] = None,
            step_code: Optional[str] = None,
            report_code: Optional[str] = None
    ) -> AutoTestDetailModel:
        """
        软删除明细，需提供detail_id或(report_code, step_code)。

        :param detail_id: 明细主键ID，与(report_code, step_code)二选一
        :param step_code: 步骤标识代码
        :param report_code: 报告标识代码
        :return: 软删除后的明细实例
        """
        if not detail_id and (not report_code or not step_code):
            error_message: str = f"参数[detail_id]或[report_code, step_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        if detail_id:
            instance = await self.get_by_id(detail_id=detail_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_conditions(
                only_one=True,
                on_error=True,
                report_code=report_code,
                step_code=step_code,
                state__not=1,
            )
        return await self.soft_delete(id=instance.id)

    async def select_details(self, search: Q, page: int, page_size: int, order: List[str]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        根据条件分页查询明细列表(轻量列，不含请求、响应、变量等大字段数据)。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页轻量列字典列表，大字段请通过/get详情接口按行获取)
        """
        try:
            query = self.model.filter(search)
            page_offset = (page - 1) * page_size
            order_fields = self.normalize_order_fields(order)
            dataset = await query.offset(page_offset).limit(page_size).order_by(*order_fields).values(*self.DETAIL_LIGHT_COLUMNS)
            return len(dataset), dataset
        except FieldError as e:
            error_message: str = f"查询明细信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    async def select_tree_details(self, search: Q, order: List[str]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        查询明细树数据源：全量轻量列(不分页)，与select_details同列清单；返回平铺行(非树)，供build_detail_tree组装。

        :param search: Tortoise Q查询条件
        :param order: 排序字段列表(固定执行时间线序, 保证父行先于子行)
        :return: (总条数, 全量轻量列字典列表)
        """
        try:
            query = self.model.filter(search)
            order_fields = self.normalize_order_fields(order)
            rows = await query.order_by(*order_fields).values(*self.DETAIL_LIGHT_COLUMNS)
            return len(rows), rows
        except FieldError as e:
            error_message: str = f"树模式全量查询明细失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message) from e

    @staticmethod
    def build_detail_tree(rows: List[Dict[str, Any]], only_failed: bool = False) -> List[Dict[str, Any]]:
        """
        按执行时间线序(rows需父行先于子行, 即按步骤开始时间+id排序)单遍扫描组装明细树。

        规则：
        - 以step_id记录"最近活跃父行"：子行归属时间上最近的同步骤容器行(兼容嵌套容器多圈多行)；
        - parent_step_id为NULL或父行缺失(存量报告/孤儿明细)时归为根节点，宁降级不丢行；
        - 生成层级路径序号tree_node(1、1.1、2.1)供前端展示；children恒输出，无子记录时为空列表；
        - only_failed=True时仅保留失败步骤及其祖先链。

        :param rows: 时间线序明细字典列表
        :param only_failed: 是否仅保留失败节点及其祖先链
        :return: 树结构列表(每个节点含children与tree_node)
        """
        last_node_by_step_id: Dict[int, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []
        for row in rows:
            node: Dict[str, Any] = {**row, "children": []}
            parent_step_id = row.get("parent_step_id")
            parent = last_node_by_step_id.get(parent_step_id) if parent_step_id is not None else None
            if parent is not None:
                parent["children"].append(node)
            else:
                roots.append(node)
            last_node_by_step_id[row.get("step_id")] = node

        def walk(nodes: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
            """自底向上生成tree_node并按only_failed裁剪保留祖先链；children恒输出(无子为空列表)。"""
            kept: List[Dict[str, Any]] = []
            for index, node in enumerate(nodes):
                node["tree_node"] = f"{prefix}.{index + 1}" if prefix else str(index + 1)
                children = walk(node["children"], node["tree_node"]) if node["children"] else []
                is_failed = node.get("step_state") in (False, 0)
                if not only_failed or is_failed or children:
                    node["children"] = children
                    kept.append(node)
            return kept

        return walk(roots, "")
