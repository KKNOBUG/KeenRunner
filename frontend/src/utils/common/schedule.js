// 结构化定时表达式(task_schedule_expr)前端工具：编辑状态⇄后端契约转换、摘要与预览格式化
// 后端契约：ONLY_ONCE={"trigger_dates":[...]}；UNBOUNDED={"trigger_cycle","trigger_weeks"/"trigger_month","trigger_times"}
import dayjs from 'dayjs'

export const PERIODIC_ONLY_ONCE = '执行1次'
export const PERIODIC_UNBOUNDED = '执行N次'

export const CYCLE_DAY = '日'
export const CYCLE_WEEK = '周'
export const CYCLE_MONTH = '月'

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
    return { periodic: PERIODIC_ONLY_ONCE, schedule: { trigger_dates: dates } }
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
    const daySet = new Set()
    const timeSet = new Set()
    for (const raw of Array.isArray(expr.trigger_dates) ? expr.trigger_dates : []) {
      const m = String(raw || '').match(/^\d{4}-\d{2}-(\d{2}) (\d{2}:\d{2}:\d{2})$/)
      if (!m) continue
      daySet.add(Number(m[1]))
      timeSet.add(m[2])
    }
    state.monthDays = asc(daySet)
    state.times = asc(timeSet)
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
 * 定时配置模式标签：仅执行一次→「执行一次」，周期→「永久有效」，无实质配置返回空。
 * 任务列表「定时配置」列使用，与定时设置面板周期开关文案对齐；明细仍由点击弹窗查看。
 */
export function getScheduleModeLabel(periodic, expr) {
  if (!periodic || !expr || typeof expr !== 'object') return ''
  if (periodic === PERIODIC_ONLY_ONCE) {
    const dates = Array.isArray(expr.trigger_dates) ? expr.trigger_dates : []
    return dates.length ? '执行一次' : ''
  }
  return expr.trigger_cycle ? '永久有效' : ''
}
