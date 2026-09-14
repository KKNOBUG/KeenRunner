# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : perf_enum.py
@DateTime: 2026/9/14 10:30
"""
from backend.enums.base_enum_cls import StringEnum


class PerfLoadMode(StringEnum):
    """
    压测施压模式：fixed 固定并发(P0 实现)；stepped 阶梯加压(P1 实现，任务表字段先行建齐避免二次表变更)。
    """
    FIXED = "fixed"
    STEPPED = "stepped"


class PerfTaskStatus(StringEnum):
    """
    压测任务最近一次执行状态：idle 仅配置未执行；stopping 为用户请求停止的过渡态，由执行管线感知后落 stopped。
    """
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


class PerfReportStatus(StringEnum):
    """
    压测报告执行状态(报告为快照实体，状态机为任务执行状态的执行期子集)。
    """
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
