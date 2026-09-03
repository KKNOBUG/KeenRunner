# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : autotest_task_schedule
@DateTime: 2026/9/1 10:00
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Set

from tortoise.expressions import Q

from backend.applications.autotest.models.autotest_task_model import AutoTestTaskModel
from backend.configure import LOGGER
from backend.core.exceptions import ParameterException
from backend.enums import AutoTestTaskPeriodicMode, AutoTestTaskCycleType

# ==================== 常量与格式 ====================

# 触发日期时间/时间点格式，与前端定时设置交互对齐
FIRE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_OF_DAY_FORMAT = "%H:%M:%S"
# UNBOUNDED模式时间点上限(需求: 时间支持多个, 最多3个)
MAX_TRIGGER_TIMES = 3
# 执行预览条数上限(需求: 近10次)
PREVIEW_LIMIT = 10
# UNBOUNDED最近触发点回溯窗口(天): 日=2(今/昨), 周=8(7天内必命中), 月=62(覆盖仅选31号时相邻命中月最大61天间隔)
_LOOKBACK_DAYS: Dict[str, int] = {
    AutoTestTaskCycleType.DAY.value: 2,
    AutoTestTaskCycleType.WEEK.value: 8,
    AutoTestTaskCycleType.MONTH.value: 62,
}
# UNBOUNDED执行预览前推窗口(天): 仅选31号时一年命中7次, 10条预览约需1.5年
_PREVIEW_LOOKAHEAD_DAYS = 800


# ==================== 解析工具 ====================

def _enum_value(raw: Any) -> Optional[str]:
    """
    取枚举成员或普通字符串的原始值。

    :param raw: 枚举实例或字符串
    :return: 原始字符串值；空入参返回None
    """
    if raw is None:
        return None
    value = getattr(raw, "value", raw)
    return str(value).strip() if value is not None else None


def parse_fire_time(raw: Any) -> Optional[datetime]:
    """
    解析YYYY-MM-DD HH:MM:SS格式的触发日期时间字符串。

    :param raw: 待解析值
    :return: 解析成功返回datetime，否则返回None
    """
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip(), FIRE_TIME_FORMAT)
    except ValueError:
        return None


def parse_time_of_day(raw: Any) -> Optional[time]:
    """
    解析HH:MM:SS格式的时间点字符串。

    :param raw: 待解析值
    :return: 解析成功返回time，否则返回None
    """
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip(), TIME_OF_DAY_FORMAT).time()
    except ValueError:
        return None


def _normalize_int_set(raw: Any, low: int, high: int, field_name: str) -> List[int]:
    """
    整数多选列表去重校验并升序排序。

    :param raw: 待校验列表
    :param low: 元素下界(含)
    :param high: 元素上界(含)
    :param field_name: 字段名(用于异常提示)
    :return: 升序去重后的整数列表
    :raises ParameterException: 空列表、非法元素或越界元素
    """
    if not isinstance(raw, list) or not raw:
        raise ParameterException(message=f"参数[task_schedule_expr.{field_name}]不允许为空")
    values: Set[int] = set()
    for item in raw:
        try:
            number = int(item)
        except (TypeError, ValueError):
            raise ParameterException(message=f"参数[task_schedule_expr.{field_name}]存在非法元素: {item}")
        if not low <= number <= high:
            raise ParameterException(
                message=f"参数[task_schedule_expr.{field_name}]元素越界: {item}(允许{low}~{high})"
            )
        values.add(number)
    return sorted(values)


def _defensive_int_set(raw: Any) -> Set[int]:
    """
    整数列表防御性解析(扫描链路容错, 不抛异常)，丢弃非法元素。

    :param raw: 待解析列表
    :return: 整数集合；非列表入参返回空集合
    """
    if not isinstance(raw, list):
        return set()
    return {int(item) for item in raw if str(item).lstrip("-").isdigit()}


# ==================== 规范化校验(落库单一入口) ====================

def normalize_schedule(periodic: Any, schedule: Any) -> Optional[Dict[str, Any]]:
    """
    校验并规范化结构化定时表达式，创建/更新任务落库前的唯一入口。

    ONLY_ONCE模式仅保留trigger_dates(触发日期时间列表, 去重升序)；
    UNBOUNDED模式保留trigger_cycle、trigger_times(去重升序, 最多3个)，
    周模式追加trigger_weeks(1=周一~7=周日)，月模式追加trigger_month(1~31)。

    :param periodic: 时效枚举或字符串(执行1次/执行N次)
    :param schedule: 原始定时表达式字典
    :return: 规范化后的定时表达式字典；空入参返回None
    :raises ParameterException: 结构缺失、格式非法或越界
    """
    if schedule is None or schedule == {}:
        return None
    if not isinstance(schedule, dict):
        raise ParameterException(message="参数[task_schedule_expr]必须为JSON对象")

    periodic_value = _enum_value(periodic) or AutoTestTaskPeriodicMode.UNBOUNDED.value
    if periodic_value == AutoTestTaskPeriodicMode.ONLY_ONCE.value:
        raw_dates = schedule.get("trigger_dates")
        if not isinstance(raw_dates, list) or not raw_dates:
            raise ParameterException(message="执行1次模式下参数[task_schedule_expr.trigger_dates]不允许为空")
        parsed_dates: Set[datetime] = set()
        for raw in raw_dates:
            fired_at = parse_fire_time(raw)
            if fired_at is None:
                raise ParameterException(
                    message=f"参数[task_schedule_expr.trigger_dates]存在非法日期时间: {raw}(格式YYYY-MM-DD HH:MM:SS)"
                )
            parsed_dates.add(fired_at)
        return {"trigger_dates": [fired_at.strftime(FIRE_TIME_FORMAT) for fired_at in sorted(parsed_dates)]}

    cycle_value = _enum_value(schedule.get("trigger_cycle"))
    if cycle_value not in _LOOKBACK_DAYS:
        raise ParameterException(message="执行N次模式下参数[task_schedule_expr.trigger_cycle]必选, 可选值: 日/周/月")
    raw_times = schedule.get("trigger_times")
    if not isinstance(raw_times, list) or not raw_times:
        raise ParameterException(message="执行N次模式下参数[task_schedule_expr.trigger_times]不允许为空")
    if len(raw_times) > MAX_TRIGGER_TIMES:
        raise ParameterException(message=f"参数[task_schedule_expr.trigger_times]最多支持{MAX_TRIGGER_TIMES}个时间点")
    parsed_of_day: Set[time] = set()
    for raw in raw_times:
        of_day = parse_time_of_day(raw)
        if of_day is None:
            raise ParameterException(message=f"参数[task_schedule_expr.trigger_times]存在非法时间: {raw}(格式HH:MM:SS)")
        parsed_of_day.add(of_day)
    normalized: Dict[str, Any] = {
        "trigger_cycle": cycle_value,
        "trigger_times": [of_day.strftime(TIME_OF_DAY_FORMAT) for of_day in sorted(parsed_of_day)],
    }
    if cycle_value == AutoTestTaskCycleType.WEEK.value:
        normalized["trigger_weeks"] = _normalize_int_set(schedule.get("trigger_weeks"), 1, 7, "trigger_weeks")
    elif cycle_value == AutoTestTaskCycleType.MONTH.value:
        normalized["trigger_month"] = _normalize_int_set(schedule.get("trigger_month"), 1, 31, "trigger_month")
    return normalized


# ==================== 触发计算(运行时视图) ====================

class TaskSchedule:
    """
    任务结构化定时表达式(task_schedule_expr)的运行时视图。

    ONLY_ONCE持有trigger_dates触发日期时间列表；
    UNBOUNDED持有trigger_cycle×(trigger_weeks/trigger_month)×trigger_times。
    提供到期反推(Beat扫描)、正推预览(新增/编辑页)、完成判定(ONLY_ONCE全部触发后关闭)三类能力。

    from_expr为容错解析: 空定时返回None(未配置, 不参与扫描)，脏数据记录warning后返回None；
    落库校验走normalize_schedule，二者职责分离。
    """

    __slots__ = ("_periodic", "_trigger_dates", "_cycle", "_times", "_weeks", "_month")

    def __init__(
            self,
            periodic: str,
            trigger_dates: List[datetime],
            cycle: Optional[str],
            times: List[time],
            weeks: Set[int],
            month: Set[int],
    ) -> None:
        """
        构造运行时视图，入参均为已解析的内存结构。

        :param periodic: 时效原始值(执行1次/执行N次)
        :param trigger_dates: ONLY_ONCE触发日期时间升序列表
        :param cycle: UNBOUNDED调度周期(日/周/月)
        :param times: UNBOUNDED时间点升序列表
        :param weeks: 周模式星期命中集合(1=周一~7=周日)
        :param month: 月模式日期命中集合(1~31)
        """
        self._periodic = periodic
        self._trigger_dates = trigger_dates
        self._cycle = cycle
        self._times = times
        self._weeks = weeks
        self._month = month

    @classmethod
    def from_expr(cls, periodic: Any, schedule: Any) -> Optional["TaskSchedule"]:
        """
        容错解析时效与定时表达式为运行时视图。

        :param periodic: 时效枚举或字符串(执行1次/执行N次)
        :param schedule: 定时表达式字典
        :return: 解析成功返回实例；空定时返回None；脏数据记录warning后返回None
        """
        if not isinstance(schedule, dict) or not schedule:
            return None
        periodic_value = _enum_value(periodic) or AutoTestTaskPeriodicMode.UNBOUNDED.value
        if periodic_value not in (
            AutoTestTaskPeriodicMode.ONLY_ONCE.value,
            AutoTestTaskPeriodicMode.UNBOUNDED.value,
        ):
            LOGGER.warning(f"定时表达式解析失败: 非法时效[{periodic}], 该任务将不参与扫描")
            return None

        if periodic_value == AutoTestTaskPeriodicMode.ONLY_ONCE.value:
            trigger_dates = sorted(
                {fired_at for fired_at in (parse_fire_time(raw) for raw in schedule.get("trigger_dates") or []) if fired_at}
            )
            if not trigger_dates:
                LOGGER.warning(f"定时表达式解析失败: ONLY_ONCE缺少合法trigger_dates[{schedule}], 该任务将不参与扫描")
                return None
            return cls(periodic_value, trigger_dates, None, [], set(), set())

        cycle = _enum_value(schedule.get("trigger_cycle"))
        if cycle not in _LOOKBACK_DAYS:
            LOGGER.warning(f"定时表达式解析失败: 非法trigger_cycle[{schedule.get('trigger_cycle')}], 该任务将不参与扫描")
            return None
        times = sorted(
            {of_day for of_day in (parse_time_of_day(raw) for raw in schedule.get("trigger_times") or []) if of_day}
        )
        if not times:
            LOGGER.warning(f"定时表达式解析失败: UNBOUNDED缺少合法trigger_times[{schedule}], 该任务将不参与扫描")
            return None
        weeks = _defensive_int_set(schedule.get("trigger_weeks"))
        month = _defensive_int_set(schedule.get("trigger_month"))
        if cycle == AutoTestTaskCycleType.WEEK.value and not weeks:
            LOGGER.warning(f"定时表达式解析失败: 周模式缺少合法trigger_weeks[{schedule}], 该任务将不参与扫描")
            return None
        if cycle == AutoTestTaskCycleType.MONTH.value and not month:
            LOGGER.warning(f"定时表达式解析失败: 月模式缺少合法trigger_month[{schedule}], 该任务将不参与扫描")
            return None
        return cls(periodic_value, [], cycle, times, weeks, month)

    @property
    def is_only_once(self) -> bool:
        """时效是否为ONLY_ONCE(执行1次)。"""
        return self._periodic == AutoTestTaskPeriodicMode.ONLY_ONCE.value

    def _match_day(self, target_day: date) -> bool:
        """
        判断给定日期是否命中UNBOUNDED周期。

        :param target_day: 待判断日期
        :return: 日周期恒命中；周周期按星期命中；月周期按日期命中
        """
        if self._cycle == AutoTestTaskCycleType.DAY.value:
            return True
        if self._cycle == AutoTestTaskCycleType.WEEK.value:
            return target_day.isoweekday() in self._weeks
        return target_day.day in self._month

    def prev_fire_time(self, now: datetime) -> Optional[datetime]:
        """
        反推不晚于now的最近一个触发时间点，供Beat扫描做到期判断(对齐原Cron到期语义)。

        ONLY_ONCE取trigger_dates中不晚于now的最大值；
        UNBOUNDED自today起按周期逐日回溯，取首个命中日期上不晚于now的最大时间点。

        :param now: 扫描当前时间
        :return: 最近触发时间点；无到期点时返回None
        """
        if self.is_only_once:
            latest: Optional[datetime] = None
            for fired_at in self._trigger_dates:
                if fired_at <= now:
                    latest = fired_at
                else:
                    break
            return latest

        for back in range(_LOOKBACK_DAYS[self._cycle] + 1):
            target_day = now.date() - timedelta(days=back)
            if not self._match_day(target_day):
                continue
            candidates = [
                datetime.combine(target_day, of_day)
                for of_day in self._times
                if back > 0 or datetime.combine(target_day, of_day) <= now
            ]
            if candidates:
                return max(candidates)
        return None

    def preview_fire_times(self, now: Optional[datetime] = None, limit: int = PREVIEW_LIMIT) -> List[str]:
        """
        正推即将到来的触发日期时间列表，供新增/编辑页执行预览(近10次)。

        :param now: 预览基准时间，缺省当前时间
        :param limit: 预览条数上限
        :return: 升序的YYYY-MM-DD HH:MM:SS字符串列表
        """
        now = now or datetime.now()
        if self.is_only_once:
            upcoming = [fired_at for fired_at in self._trigger_dates if fired_at >= now]
            return [fired_at.strftime(FIRE_TIME_FORMAT) for fired_at in upcoming[:limit]]

        preview: List[datetime] = []
        for ahead in range(_PREVIEW_LOOKAHEAD_DAYS + 1):
            target_day = now.date() + timedelta(days=ahead)
            if not self._match_day(target_day):
                continue
            for of_day in self._times:
                fired_at = datetime.combine(target_day, of_day)
                if fired_at >= now:
                    preview.append(fired_at)
                    if len(preview) >= limit:
                        return [item.strftime(FIRE_TIME_FORMAT) for item in preview]
        return [item.strftime(FIRE_TIME_FORMAT) for item in preview]

    def is_completed(self, moment: datetime) -> bool:
        """
        判断ONLY_ONCE任务的全部触发日期时间是否均已到期(供执行后关闭调度)。

        :param moment: 判定基准时刻；调用方应传“上一次执行启动时刻(last_execute_time)”
            而非墙钟——触发点由扫描逐点派发，仅当上次执行启动时已越过最后一个触发点，
            才能确认全部触发点均已被派发，避免单次执行跨越后续触发点时误关调度
        :return: ONLY_ONCE且全部trigger_dates已到期为True；UNBOUNDED恒为False
        """
        return self.is_only_once and bool(self._trigger_dates) and moment >= self._trigger_dates[-1]


# ==================== 扫描链路入口 ====================

async def fetch_schedulable_tasks(task_type: Any) -> List[Any]:
    """
    拉取未删除、已启用且配置了结构化定时表达式的自动化任务，供Beat扫描使用。

    :param task_type: 任务类型枚举或字符串(如AutoTestTaskType.AUTOTEST_API)
    :return: 满足条件的AutoTestTaskModel列表；参数无效时返回空列表
    """
    if not task_type:
        return []
    type_val = getattr(task_type, "value", task_type)
    if not type_val:
        return []
    q = (
            Q(state=0)
            & Q(task_enabled=True)
            & Q(task_type=type_val)
            & ~Q(task_schedule_expr__isnull=True)
    )
    return list(await AutoTestTaskModel.filter(q).all())


def is_task_due(task: Any, now: Optional[datetime] = None) -> bool:
    """
    基于task_periodic_expr + task_schedule_expr判断任务是否已到执行时间，供Beat扫描使用。

    反推不晚于当前的最近触发时间点prev_fire，last_execute_time < prev_fire即到期，
    与原Cron表达式到期语义一致(幂等、停机后补发一次)。

    :param task: 任务模型实例(需含task_periodic_expr / task_schedule_expr / last_execute_time等字段)
    :param now: 扫描当前时间，缺省当前时间
    :return: 到期为True，否则为False；定时缺失或非法时返回False
    """
    schedule = getattr(task, "task_schedule_expr", None)
    if not isinstance(schedule, dict) or not schedule:
        return False

    now = now or datetime.now()
    last_run = getattr(task, "last_execute_time", None) or getattr(task, "created_time", None)
    if last_run and getattr(last_run, "tzinfo", None):
        last_run = last_run.replace(tzinfo=None)
    if isinstance(last_run, str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                last_run = (
                    datetime.strptime(last_run[:26], fmt)
                    if "." in last_run
                    else datetime.strptime(last_run[:19], "%Y-%m-%d %H:%M:%S")
                )
                break
            except ValueError:
                continue
        else:
            last_run = None

    task_id = getattr(task, "id", None)
    schedule_obj = TaskSchedule.from_expr(getattr(task, "task_periodic_expr", None), schedule)
    if schedule_obj is None:
        return False
    prev_fire = schedule_obj.prev_fire_time(now)
    if prev_fire is None:
        return False
    due = True if last_run is None else (last_run < prev_fire)
    LOGGER.debug(
        f"【Celery-Worker】定时到期判断 task_id={task_id} "
        f"now={now} prev_fire={prev_fire} last_run={last_run} due={due}"
    )
    return due
