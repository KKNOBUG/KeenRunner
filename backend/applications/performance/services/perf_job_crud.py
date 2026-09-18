# -*- coding: utf-8 -*-
"""
压测数据作业CRUD。

写操作收敛在本入口: 新增/删除与执行状态流转全部经 PerfJobCrud, 视图层与Celery
执行链不直写模型。执行状态流转(pending→running→success/failed)提供原子操作:
- mark_pending: run 下发前置排队, 排除 running 防重复下发, 并清空上一轮执行痕迹;
- claim_running: 执行链条件更新抢占置 running(仅 pending 可流转, 防消息重投双跑);
- mark_success/mark_failed: 终态回填执行观测字段(产出数据集/行数/最近报告)。

引用资产绑定字段(quote_case_*)一律回查覆盖, 不信任前端传入。
列表查询按 JOB_LIST_FIELDS 显式取列, error_message 大字段经 detail 接口读取。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_job_crud.py
@DateTime: 2026/9/17 17:40
"""
import traceback
from typing import Any, Dict, List, Optional, Tuple

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q

from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.performance.models.perf_api_model import PerfApiModel
from backend.applications.performance.models.perf_job_model import PerfJobModel
from backend.applications.performance.models.perf_scene_model import PerfSceneModel
from backend.applications.performance.schemas.perf_job_schema import (
    PerfJobCreate,
)
from backend.configure import LOGGER
from backend.core.exceptions import (
    NotFoundException,
    ParameterException,
    DataBaseStorageException,
)
from backend.enums import PerfJobStatus

# 列表接口返回列(排除 error_message 大字段; 执行观测字段保留供列表状态徽标展示)
JOB_LIST_FIELDS = (
    "id", "job_name", "job_desc", "job_code", "job_type",
    "quote_case_id", "quote_case_code", "quote_case_name",
    "bind_api_id", "bind_scene_id",
    "loop_times", "dataset_name", "extract_fields",
    "status", "celery_id", "result_dataset_id", "result_rows", "report_code",
    "perf_batch_code", "related_report_id",
    "state", "created_time", "updated_time", "created_user", "updated_user",
)


class PerfJobCrud(ScaffoldCrud[PerfJobModel, PerfJobCreate, Any]):
    """压测数据作业CRUD(契约无update端点, 状态流转由专用原子方法承载)。"""

    def __init__(self):
        super().__init__(model=PerfJobModel)

    async def get_by_id(self, job_id: int, on_error: bool = False, **kwargs) -> Optional[PerfJobModel]:
        """
        根据主键ID查询数据作业。

        :param job_id: 数据作业主键ID
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 数据作业实例或None
        """
        if not job_id:
            error_message: str = "查询压测数据作业信息失败, 参数[job_id]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.get_or_none(id=job_id, **kwargs)
        if not instance and on_error:
            error_message: str = f"查询压测数据作业信息失败, 记录[id={job_id}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    async def get_by_code(self, job_code: str, on_error: bool = False, **kwargs) -> Optional[PerfJobModel]:
        """
        根据数据作业标识代码查询数据作业。

        :param job_code: 数据作业标识代码
        :param on_error: 未找到时是否抛出异常
        :param kwargs: 额外过滤条件
        :return: 数据作业实例或None
        """
        if not job_code:
            error_message: str = "查询压测数据作业信息失败, 参数[job_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)

        instance = await self.model.filter(job_code=job_code, **kwargs).first()
        if not instance and on_error:
            error_message: str = f"查询压测数据作业信息失败, 记录[code={job_code}]不存在"
            LOGGER.error(error_message)
            raise NotFoundException(message=error_message)
        return instance

    @staticmethod
    async def resolve_quote_case(*, quote_case_id: int) -> Dict[str, Any]:
        """
        校验执行的脚本用例存在并返回快照落库值。

        脚本用例是作业的执行主体, 引用断链只会拖到执行期才失败, 保存期一次校验早失败;
        快照(code/name)落库使列表无需跨模块回查即可展示。跨模块引用走函数内导入
        (与数据集校验应用同一模式, 避免模块加载环)。

        :param quote_case_id: 脚本用例ID
        :return: {"quote_case_code": xx, "quote_case_name": xx}
        """
        from backend.applications.autotest.services.autotest_case_crud import AutoTestCaseCrud

        case = await AutoTestCaseCrud().get_by_id(case_id=quote_case_id, on_error=True, state__not=1)
        return {"quote_case_code": case.case_code, "quote_case_name": case.case_name}

    @staticmethod
    async def resolve_bind_api(*, bind_api_id: Optional[int]) -> Optional[PerfApiModel]:
        """
        校验产出归属压测接口存在, 返回实例供执行链派生数据集归属。

        :param bind_api_id: 归属压测接口ID, 可为空(verify/cleanup无需归属)
        :return: 压测接口实例或None
        """
        if not bind_api_id:
            return None
        api: Optional[PerfApiModel] = await PerfApiModel.filter(id=bind_api_id, state__not=1).first()
        if not api:
            error_message: str = f"校验压测数据作业失败, 产出归属压测接口[id={bind_api_id}]不存在或已禁用"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return api

    @staticmethod
    async def resolve_bind_scene(*, bind_scene_id: Optional[int]) -> Optional[PerfSceneModel]:
        """
        校验关联压测场景存在, 返回实例。

        场景联动(施压前自动触发prepare/施压后触发verify)由场景执行链反查本绑定,
        保存期校验存在性保证绑定不悬空。

        :param bind_scene_id: 关联压测场景ID, 可为空
        :return: 压测场景实例或None
        """
        if not bind_scene_id:
            return None
        scene: Optional[PerfSceneModel] = await PerfSceneModel.filter(id=bind_scene_id, state__not=1).first()
        if not scene:
            error_message: str = f"校验压测数据作业失败, 关联压测场景[id={bind_scene_id}]不存在或已禁用"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return scene

    async def create_perf_job(self, job_in: PerfJobCreate) -> PerfJobModel:
        """
        新增数据作业(引用资产全部回查校验, 用例快照落库)。

        :param job_in: 数据作业创建schema
        :return: 创建后的数据作业实例
        """
        quote_case: Dict[str, Any] = await self.resolve_quote_case(quote_case_id=job_in.quote_case_id)
        await self.resolve_bind_api(bind_api_id=job_in.bind_api_id)
        await self.resolve_bind_scene(bind_scene_id=job_in.bind_scene_id)

        job_dict: Dict[str, Any] = job_in.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        job_dict.update(quote_case)
        try:
            return await self.create(obj_in=job_dict)
        except IntegrityError as e:
            error_message: str = f"新增压测数据作业信息失败, 违反约束规则: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=error_message) from e

    async def delete_perf_job(self, job_id: Optional[int] = None, job_code: Optional[str] = None) -> PerfJobModel:
        """
        软删除数据作业。

        作业产出数据集为独立资产(ds_source=job仅溯源标记), 删作业不影响已产出数据集。

        :param job_id: 数据作业主键ID, 与job_code二选一
        :param job_code: 数据作业标识代码, 与job_id二选一
        :return: 软删除后的数据作业实例
        """
        if not job_id and not job_code:
            error_message: str = "删除压测数据作业信息失败, 参数[job_id]或[job_code]不允许为空"
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        if job_id:
            instance = await self.get_by_id(job_id=job_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(job_code=job_code, on_error=True, state__not=1)
        if instance.status == PerfJobStatus.RUNNING:
            error_message: str = (
                f"删除压测数据作业信息失败, 作业[{instance.job_name}]正在执行中, 请等待执行完成"
            )
            LOGGER.error(error_message)
            raise ParameterException(message=error_message)
        return await self.soft_delete(id=instance.id)

    async def select_perf_jobs(self, search: Q, page: int, page_size: int,
                               order: List[str]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        根据条件分页查询数据作业列表(显式取列, 不加载 error_message 大字段)。

        :param search: Tortoise Q查询条件
        :param page: 页码
        :param page_size: 每页条数
        :param order: 排序字段列表
        :return: (总条数, 当前页记录字典列表)
        """
        try:
            queryset = self.model.filter(search)
            total: int = await queryset.count()
            order_fields: List[str] = self.normalize_order_fields(order) or ["-updated_time"]
            rows: List[Dict[str, Any]] = await queryset.offset((page - 1) * page_size).limit(page_size) \
                .order_by(*order_fields).values(*JOB_LIST_FIELDS)
            return total, rows
        except FieldError as e:
            error_message: str = f"查询压测数据作业信息失败, 错误描述: {e}"
            LOGGER.error(f"{error_message}\n{traceback.format_exc()}")
            raise ParameterException(message=error_message)

    async def mark_pending(self, job_id: int) -> bool:
        """
        置排队(下发前): 排除 running 防并发重复下发, 并清空上一轮执行痕迹。

        重跑后旧执行结果(产出数据集引用/行数/最近报告)已过期, 全部清空由新一轮
        执行终态回填, 避免「排队中」状态下残留上轮结论造成误读。

        :param job_id: 数据作业主键ID
        :return: 是否更新成功(False=并发窗口内已被置为 running, 下发应被拒绝)
        """
        updated: int = await self.model.filter(id=job_id).exclude(
            status=PerfJobStatus.RUNNING,
        ).update(
            status=PerfJobStatus.PENDING,
            celery_id=None,
            error_message=None,
            result_dataset_id=None,
            result_rows=0,
            report_code=None,
        )
        return bool(updated)

    async def claim_running(self, job_id: int, celery_id: Optional[str]) -> bool:
        """
        抢占置 running(执行链): 仅 pending 可流转, 防消息重投/并发消费双跑。

        :param job_id: 数据作业主键ID
        :param celery_id: 本次执行的Celery任务ID
        :return: 是否抢占成功(False=状态非pending, 本次消费应跳过)
        """
        updated: int = await self.model.filter(
            id=job_id, status=PerfJobStatus.PENDING,
        ).update(status=PerfJobStatus.RUNNING, celery_id=celery_id)
        return bool(updated)

    async def mark_success(self, job_id: int, *, result_dataset_id: Optional[int] = None,
                           result_rows: Optional[int] = None,
                           report_code: Optional[str] = None) -> None:
        """
        置成功终态并回填执行观测字段(仅覆盖显式提供的字段)。

        :param job_id: 数据作业主键ID
        :param result_dataset_id: 产出数据集ID(prepare回填)
        :param result_rows: 产出数据行数(prepare回填)
        :param report_code: 最近一轮功能执行报告标识代码
        :return: None
        """
        values: Dict[str, Any] = {"status": PerfJobStatus.SUCCESS}
        if result_dataset_id is not None:
            values["result_dataset_id"] = result_dataset_id
        if result_rows is not None:
            values["result_rows"] = result_rows
        if report_code:
            values["report_code"] = report_code
        await self.model.filter(id=job_id).update(**values)

    async def mark_failed(self, job_id: int, error_message: str,
                          report_code: Optional[str] = None) -> None:
        """
        置失败终态并记录原因(报告代码非空时覆盖, 供追溯失败轮次的执行明细)。

        :param job_id: 数据作业主键ID
        :param error_message: 失败原因
        :param report_code: 失败轮次的功能执行报告标识代码
        :return: None
        """
        values: Dict[str, Any] = {"status": PerfJobStatus.FAILED, "error_message": error_message}
        if report_code:
            values["report_code"] = report_code
        await self.model.filter(id=job_id).update(**values)

