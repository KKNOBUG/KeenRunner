# -*- coding: utf-8 -*-
"""
多记录对比/汇总CRUD。

写操作收敛在本入口: 新增与软删除经 PerfComparisonCrud, 业务校验与结果快照
计算在 PerfComparisonService(业务在 services 分层红线), 本类只承载存取与查询。
列表查询按 COMPARISON_LIST_FIELDS 显式取列, result_snapshot/report_refs 两个
大字段经 detail 接口读取, 避免列表报文随记录数线性膨胀。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_comparison_crud.py
@DateTime: 2026/9/17 20:30
"""
import traceback
from typing import Any, List, Optional, Tuple

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_comparison_model import PerfComparisonModel
from backend.applications.performance.schemas.perf_comparison_schema import PerfComparisonCreate
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataBaseStorageException,
    NotFoundException,
    ParameterException,
)

# 列表接口返回列(排除 report_refs/result_snapshot 大字段)
COMPARISON_LIST_FIELDS = (
    "id", "comparison_name", "comparison_code", "comparison_mode",
    "report_count", "comparison_desc",
    "state", "created_user", "created_time", "updated_time", "updated_user",
)


class PerfComparisonCrud(ScaffoldCrud[PerfComparisonModel, PerfComparisonCreate, Any]):
    """多记录对比/汇总CRUD(契约无update端点: 结论快照创建后不可变, 重新对比请新建记录)。"""

    def __init__(self):
        super().__init__(model=PerfComparisonModel)

    async def get_by_id(self, comparison_id: int, on_error: bool = False, **kwargs) -> Optional[PerfComparisonModel]:
        """
        根据主键ID查询对比记录。

        :param comparison_id: 对比记录主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 对比记录实例或None
        """
        if not comparison_id:
            error_message: str = "查询对比记录失败, 参数[comparison_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=comparison_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询对比记录失败, 记录[id={comparison_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, comparison_code: str, on_error: bool = False, **kwargs) -> Optional[PerfComparisonModel]:
        """
        根据对比记录标识代码查询对比记录。

        :param comparison_code: 对比记录业务标识
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 对比记录实例或None
        """
        if not comparison_code:
            error_message: str = "查询对比记录失败, 参数[comparison_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        # 基类 get_or_none 的 id 为必传位参, 按业务标识查询必须走 model.filter(对齐 PerfJobCrud.get_by_code)
        instance = await self.model.filter(comparison_code=comparison_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询对比记录失败, 记录[comparison_code={comparison_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def select_perf_comparisons(
            self,
            search: Q,
            page: int = 1,
            page_size: int = 10,
            order: Optional[List[str]] = None,
    ) -> Tuple[int, List[dict]]:
        """
        按条件分页查询对比记录列表(显式取列, 不加载快照大字段)。

        :param search: 查询条件(view层组装, 含state过滤)
        :param page: 页码
        :param page_size: 每页数量
        :param order: 排序字段列表(缺省按更新时间倒序)
        :return: (记录总数, 当前页记录行列表)
        """
        total: int = await self.model.filter(search).count()
        order_fields = order or ["-updated_time"]
        queryset = self.model.filter(search).offset((page - 1) * page_size).limit(page_size)
        try:
            rows = await queryset.order_by(*order_fields).values(*COMPARISON_LIST_FIELDS)
        except (FieldError, DoesNotExist) as e:
            error_message: str = f"对比记录列表排序字段非法, 异常描述: {e}"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return total, rows

    async def create_perf_comparison(self, comparison_dict: dict) -> PerfComparisonModel:
        """
        新增对比记录(入参为服务层组装完成的落库字典: 含refs/结果快照)。

        :param comparison_dict: 落库字段字典
        :return: 创建后的对比记录实例
        """
        try:
            return await self.create(obj_in=comparison_dict)
        except IntegrityError as e:
            error_message: str = f"新增对比记录失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_perf_comparison(
            self,
            comparison_id: Optional[int] = None,
            comparison_code: Optional[str] = None,
    ) -> PerfComparisonModel:
        """
        软删除对比记录。

        :param comparison_id: 对比记录主键ID, 与comparison_code二选一
        :param comparison_code: 对比记录业务标识, 与comparison_id二选一
        :return: 软删除后的对比记录实例
        """
        if not comparison_id and not comparison_code:
            error_message: str = "删除对比记录失败, 参数[comparison_id]或[comparison_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if comparison_id:
            instance = await self.get_by_id(comparison_id=comparison_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(comparison_code=comparison_code, on_error=True, state__not=1)
        return await self.soft_delete(id=instance.id)
