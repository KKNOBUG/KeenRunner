# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : celery_worker
@DateTime: 2026/1/27 16:25
"""
import asyncio
import logging
import traceback
import uuid
from abc import ABC

from celery import Celery
from celery import Task
from celery._state import _task_stack
from celery.signals import setup_logging, task_prerun
from celery.worker.request import Request

from backend import LOGGER
from backend.common.async_or_sync_convert import AsyncEventLoopContextIOPool
from backend.configure.celery_config import CELERY_CONFIG
from backend.configure.logging_config import InterceptHandler
from celery_base import ensure_tortoise_orm_initialized, LOCAL_CONTEXT_VAR

ASYNC_EVENT_LOOP_CONTEXT_IO_POOL = AsyncEventLoopContextIOPool()


@task_prerun.connect
def receiver_task_pre_run(task: Task, *args, **kwargs):
    """
    任务执行前执行（任务被worker接收时）
    用于记录任务开始信息和确保数据库连接已初始化
    :param task: task 实例
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return:
    """
    try:
        ensure_tortoise_orm_initialized()

        task_type = task.request.properties.get("__task_type", None)
        business_id = task.request.properties.get("__business_id", None)
        trace_id = task.request.headers.get("trace_id", None)

        LOGGER.info(
            f"[Celery-Worker][trace_id={trace_id}]任务提交完成 --> task id [{task.request.id}], "
            f"task_name=[{task.name}], "
            f"business_id=[{business_id}], "
            f"task_type=[{task_type}]"
        )
    except Exception as e:
        trace_id = task.request.headers.get("trace_id", None)
        LOGGER.error(
            f"[Celery-Worker][trace_id={trace_id}]任务提交错误 --> task id [{task.request.id}]:"
            f"error_message=[{str(e)}], \n"
            f"traceback: {traceback.format_exc()}"
        )


@setup_logging.connect
def setup_loggers(*args, **kwargs):
    """logger 初始化统一处理日志格式"""
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)


class TaskRequest(Request):
    """
    重写 task request 设置 trace_id
    这里可以设置所有传递过来的参数
    """

    def __init__(self, *args, **kwargs):
        super(TaskRequest, self).__init__(*args, **kwargs)
        self.set_trace_id()

    def set_trace_id(self):
        """
        设置消息发送时的 trace_id 能与请求保持一致
        特殊处理用于保持请求追踪
        """
        trace_id = self.request_dict.get("trace_id", str(uuid.uuid4()))
        LOCAL_CONTEXT_VAR.trace_id = trace_id


def create_celery():
    """
    原生Celery采取的是对象入列模式因此只能执行同步函数，无法直接调用async def函数；
    由于所有的数据库操作都是异步的（Tortoise-ORM是纯异步实现，不像Sqlalchemy属于同步异步混合模式），
    改造异步至同步代码存在工作量，且为了celery降低数据库方面的性能不值得，
    所以需要改造Celery，让其支持异步函数调用（利用单例线程池整合异步事件循环的环境信息）
    :return:
    """

    class NewCelery(Celery):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def send_task(self, *args, **kwargs):
            """
            发送任务时自动添加 trace_id
            """
            headers = {
                "headers": {
                    "trace_id": LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
                }
            }
            if kwargs:
                kwargs.update(headers)
            else:
                kwargs = headers
            return super().send_task(*args, **kwargs)

    class ContextTask(Task, ABC):
        """
        自定义 Task 类
        支持异步函数执行，并自动处理任务记录
        """
        Request = TaskRequest

        def delay(self, *args, **kwargs):
            return self.apply_async(args, kwargs)

        def apply_async(self, args=None, kwargs=None, task_id=None, producer=None,
                        link=None, link_error=None, shadow=None, **options):
            """
            异步应用任务
            自动添加 trace_id 和任务类型
            """
            __task_type = options.get("__task_type", None)
            __task_type = __task_type if __task_type else 10

            headers = {
                "headers": {
                    "trace_id": LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
                },
                "__task_type": __task_type
            }

            if options:
                options.update(headers)
            else:
                options = headers

            return super(ContextTask, self).apply_async(
                args, kwargs, task_id, producer, link, link_error, shadow, **options
            )

        def on_success(self, retval, task_id, args, kwargs):
            """
            Celery-Worker 任务执行成功时回调函数
            :param retval:
            :param task_id:
            :param args:
            :param kwargs:
            :return:
            """
            trace_id = self.request.headers.get("trace_id", None)
            LOGGER.info(f"[Celery-Worker][trace_id={trace_id}]任务执行成功 --> task_id=[{task_id}]")
            return super(ContextTask, self).on_success(retval, task_id, args, kwargs)

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            """
            Celery-Worker 任务执行失败时回调函数
            :param retval:
            :param task_id:
            :param args:
            :param kwargs:
            :return:
            """
            trace_id = self.request.headers.get("trace_id", None)
            LOGGER.error(
                f"[Celery-Worker][trace_id={trace_id}]任务执行失败 --> task_id=[{task_id}], "
                f"error_message=[{str(exc)}], \n"
                f"traceback: {einfo.traceback}"
            )
            return super(ContextTask, self).on_failure(exc, task_id, args, kwargs, einfo)

        def __call__(self, *args, **kwargs):
            """
            重写 call 方法，让其支持异步函数的运行
            """
            # 设置 trace_id
            # 从 request headers 中获取 trace_id
            try:
                ensure_tortoise_orm_initialized()

                trace_id = self.request.headers.get("trace_id", None)
                if trace_id:
                    LOCAL_CONTEXT_VAR.trace_id = trace_id
                else:
                    LOCAL_CONTEXT_VAR.trace_id = LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())
            except:
                LOCAL_CONTEXT_VAR.trace_id = LOCAL_CONTEXT_VAR.trace_id or str(uuid.uuid4())

            # 推送任务到堆栈
            _task_stack.push(self)
            self.push_request(args=args, kwargs=kwargs)

            try:
                if asyncio.iscoroutinefunction(self.run):
                    # 异步函数使用 ASYNC_EVENT_LOOP_CONTEXT_IO_POOL 执行
                    return ASYNC_EVENT_LOOP_CONTEXT_IO_POOL.run(self.run(*args, **kwargs))
                else:
                    # 同步函数直接执行
                    return self.run(*args, **kwargs)
            finally:
                # 清理
                self.pop_request()
                _task_stack.pop()

    # 创建 Celery 实例
    _celery_: Celery = NewCelery("krun-celery-worker", task_cls=ContextTask)
    _celery_.config_from_object(CELERY_CONFIG)
    return _celery_


celery = create_celery()

# celery_worker 专用于 celery 的 worker
# worker windows 启动，只能单线程
# celery -A celery_worker.worker worker --pool=solo -l INFO
# worker linux  启动
# celery -A celery_worker.worker worker --pool=solo -c 10 -l INFO
# beat
# celery -A celery_worker.worker beat -l INFO  启动节拍器，定时任务需要
# beat 数据库
# celery -A celery_worker.worker beat -S celery_worker.scheduler.schedulers:DatabaseScheduler -l INFO

if __name__ == '__main__':
    import sys

    celery.start(argv=sys.argv[1:])
