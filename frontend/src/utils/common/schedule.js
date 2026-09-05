// 结构化定时表达式(task_schedule_expr)前端工具：编辑状态⇄后端契约转换、摘要与预览格式化、任务列表标签流展示
// 后端契约：两种模式均落 trigger_month×trigger_times(编辑回显)；ONLY_ONCE={trigger_dates,trigger_month,trigger_times}；UNBOUNDED={trigger_cycle,trigger_weeks/trigger_month,trigger_times}
import dayjs from 'dayjs'

export const PERIODIC_ONLY_ONCE = '执行1次'
export const PERIODIC_UNBOUNDED = '执行N次'

/** 周期类型常量：与后端 AutoTestTaskCycleType 枚举值(daily/weekly/monthly)对齐，随 task_schedule_expr.trigger_cycle 落库 */
export const CYCLE_DAY = 'daily'
export const CYCLE_WEEK = 'weekly'
export const CYCLE_MONTH = 'monthly'

/** 星期多选标签：1=星期一~7=星期日，与后端 isoweekday 对齐 */
export const WEEK_LABELS = {
  1: '星期一',
  2: '星期二',
  3: '星期三',
  4: '星期四',
  5: '星期五',
  6: '星期六',
  7: '星期日',
}

const TIME_RE = /^\d{2}:\d{2}:\d{2}$/
const pad2 = (n) => String(n).padStart(2, '0')
const asc = (arr) => [...arr].sort((a, b) => a - b)

// 标签流展示：各分组数值标签(日期/星期/几号/时间)分别截取前 TAG_VALUE_LIMIT 个展示，溢出合并为「等 N 个」汇总标签
const TAG_VALUE_LIMIT = 2

export function createEmptyScheduleState() {
  // 周期模式必输、默认「仅执行一次」；预置一行空触发时间便于直接选择
  return { periodic: PERIODIC_ONLY_ONCE, cycle: null, monthDays: [], weeks: [], times: [''] }
}

/** 是否存在实质性定时配置（编辑态展开/收起判定）；周期模式恒有默认值，不参与判定 */
export function hasScheduleConfig(state) {
  if (!state) return false
  return Boolean(
    state.cycle ||
      (state.monthDays || []).length ||
      (state.weeks || []).length ||
      (state.times || []).some((t) => t),
  )
}

/**
 * 前端编辑状态 → 后端 task_periodic_expr/task_schedule_expr 契约。
 * ONLY_ONCE按当前年月将「日期×时间」展开为绝对触发日期时间列表（跳过当月不存在的日期）。
 * @returns {{periodic: string, schedule: object} | null} 配置不完整时返回null
 */
export function buildSchedulePayload(state) {
  if (!state?.periodic) return null
  const times = asc((state.times || []).filter((t) => TIME_RE.test(t || '')))
  if (!times.length) return null

  if (state.periodic === PERIODIC_ONLY_ONCE) {
    const days = asc(state.monthDays || [])
    if (!days.length) return null
    const now = dayjs()
    const dim = now.daysInMonth()
    const dates = []
    for (const d of days) {
      if (d < 1 || d > dim) continue
      for (const t of times) dates.push(`${now.format('YYYY-MM')}-${pad2(d)} ${t}`)
    }
    if (!dates.length) return null
    return {
      periodic: PERIODIC_ONLY_ONCE,
      // 日期多选与时间点随表达式落库：回显直读；trigger_dates为二者展开产物(当月不存在的日期被跳过)，反推必有损
      schedule: { trigger_dates: dates, trigger_month: days, trigger_times: times },
    }
  }

  if (!state.cycle) return null
  const schedule = { trigger_cycle: state.cycle, trigger_times: times }
  if (state.cycle === CYCLE_WEEK) {
    const weeks = asc(state.weeks || [])
    if (!weeks.length) return null
    schedule.trigger_weeks = weeks
  } else if (state.cycle === CYCLE_MONTH) {
    const days = asc(state.monthDays || [])
    if (!days.length) return null
    schedule.trigger_month = days
  }
  return { periodic: PERIODIC_UNBOUNDED, schedule }
}

/** 后端表达式 → 前端编辑状态（编辑任务回显） */
export function scheduleStateFromExpr(periodic, expr) {
  const state = createEmptyScheduleState()
  if (!periodic || !expr || typeof expr !== 'object') return state
  state.periodic = periodic
  if (periodic === PERIODIC_ONLY_ONCE) {
    // 直读落库的日期多选与时间点，与buildSchedulePayload落库契约对称，不做本地反推
    state.monthDays = asc(expr.trigger_month || [])
    state.times = [...(expr.trigger_times || [])].sort()
    return state
  }
  state.cycle = expr.trigger_cycle || null
  state.weeks = asc(expr.trigger_weeks || [])
  state.monthDays = asc(expr.trigger_month || [])
  state.times = asc(expr.trigger_times || [])
  return state
}

/** 预览/摘要时间格式：YY-MM-DD HH:mm:ss（对齐需求截图） */
export function formatFireTime(raw) {
  const m = String(raw || '').match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2}:\d{2})$/)
  if (!m) return raw || '-'
  return `${m[1].slice(2)}-${m[2]}-${m[3]} ${m[4]}`
}

/** 定时配置摘要：任务列表table「定时配置」列与定时设置收起态共用 */
export function formatScheduleSummary(periodic, expr) {
  if (!periodic || !expr || typeof expr !== 'object') return ''
  if (periodic === PERIODIC_ONLY_ONCE) {
    const dates = Array.isArray(expr.trigger_dates) ? expr.trigger_dates : []
    if (!dates.length) return ''
    return `执行1次 | ${dates.map(formatFireTime).join('、')}`
  }
  const cycle = expr.trigger_cycle
  if (!cycle) return ''
  const times = Array.isArray(expr.trigger_times) ? expr.trigger_times.join('、') : ''
  if (cycle === CYCLE_WEEK) {
    const weeks = (expr.trigger_weeks || []).map((w) => WEEK_LABELS[w] || w).join('、')
    return `执行N次 | 周 ${weeks} ${times}`
  }
  if (cycle === CYCLE_MONTH) {
    const days = (expr.trigger_month || []).map((d) => `${d}号`).join('、')
    return `执行N次 | 月 ${days} ${times}`
  }
  return `执行N次 | 日 ${times}`
}

/**
 * 后端表达式 → 任务列表「定时配置」列标签流：[{ label, kind }]
 * kind: cycle=周期标签(信息色：执行1次/执行N次/每日/每周/每月) / value=数值标签(橙色：日期/星期/几号/时间) / more=溢出汇总
 * 执行1次 → 「执行1次」+ trigger_dates 逐点「YYYY-MM-DD HH:mm」；执行N次 → 「执行N次」+ 周期标签 + 星期/几号/时间标签
 * @returns {Array<{label: string, kind: 'cycle'|'value'|'more'}>} 表达式为空或不完整时返回空数组
 */
export function buildScheduleTags(periodic, expr) {
  if (!periodic || !expr || typeof expr !== 'object') return []
  if (periodic === PERIODIC_ONLY_ONCE) {
    const dates = Array.isArray(expr.trigger_dates) ? expr.trigger_dates : []
    if (!dates.length) return []
    // 触发日期时间截去秒位，对齐需求截图「2026-08-10 22:00」
    const values = dates.map((raw) => ({ label: String(raw || '').slice(0, 16), kind: 'value' }))
    return [{ label: PERIODIC_ONLY_ONCE, kind: 'cycle' }, ...truncateScheduleTagGroups([values])]
  }
  const cycle = expr.trigger_cycle
  if (!cycle) return []
  const groups = []
  if (cycle === CYCLE_WEEK) {
    // 标签流用「周一」短标签对齐需求截图（WEEK_LABELS 为面板全称）
    groups.push((expr.trigger_weeks || []).map((w) => ({ label: (WEEK_LABELS[w] || w).replace('星期', '周'), kind: 'value' })))
  } else if (cycle === CYCLE_MONTH) {
    groups.push((expr.trigger_month || []).map((d) => ({ label: `${d}号`, kind: 'value' })))
  }
  groups.push((expr.trigger_times || []).map((t) => ({ label: String(t || '').slice(0, 5), kind: 'value' })))
  if (!groups.some((g) => g.length)) return []
  const cycleLabel = cycle === CYCLE_DAY ? '每日' : cycle === CYCLE_WEEK ? '每周' : cycle === CYCLE_MONTH ? '每月' : cycle
  return [
    { label: PERIODIC_UNBOUNDED, kind: 'cycle' },
    { label: cycleLabel, kind: 'cycle' },
    ...truncateScheduleTagGroups(groups),
  ]
}

/**
 * 各分组数值标签分别截取前 TAG_VALUE_LIMIT 个，溢出数量合并为单个「等 N 个」汇总标签引导点击明细弹窗
 * @param {Array<Array<{label: string, kind: string}>>} groups 按类别分组的数值标签(如[星期组, 时间组]d)
 */
function truncateScheduleTagGroups(groups) {
  const shown = []
  let hidden = 0
  for (const values of groups) {
    if (values.length > TAG_VALUE_LIMIT) hidden += values.length - TAG_VALUE_LIMIT
    shown.push(...values.slice(0, TAG_VALUE_LIMIT))
  }
  return hidden > 0 ? [...shown, { label: `等 ${hidden} 个`, kind: 'more' }] : shown
}
