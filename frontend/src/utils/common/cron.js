// 解析 crontab 表达式，计算接下来 N 次执行时间
// 5 段: 分(0-59) 时(0-23) 日(1-31) 月(1-12) 周(0-7, 0和7为周日)
// 6 段: 秒(0-59) 分 时 日 月 周
// 支持: * , N , N-M , */S , N,M ；日/周字段中的 ? 按 * 处理
// 返回时间一律精确到秒：YYYY-MM-DD HH:mm:ss
import dayjs from 'dayjs'

function parseCronField(field, min, max) {
  let s = String(field ?? '').trim()
  if (s === '?' || s === '') s = '*'
  if (s === '*') return null
  const list = new Set()
  const parts = s.split(',')
  for (const p of parts) {
    const stepMatch = p.trim().match(/^\*\/(\d+)$/)
    if (stepMatch) {
      const step = parseInt(stepMatch[1], 10)
      if (step > 0) for (let i = min; i <= max; i += step) list.add(i)
      continue
    }
    const rangeMatch = p.trim().match(/^(\d+)-(\d+)(?:\/(\d+))?$/)
    if (rangeMatch) {
      let a = parseInt(rangeMatch[1], 10)
      let b = parseInt(rangeMatch[2], 10)
      const step = rangeMatch[3] ? parseInt(rangeMatch[3], 10) : 1
      if (a > b) [a, b] = [b, a]
      for (let i = a; i <= b; i += step) if (i >= min && i <= max) list.add(i)
      continue
    }
    const num = parseInt(p.trim(), 10)
    if (!Number.isNaN(num) && num >= min && num <= max) list.add(num)
  }
  return list.size ? list : null
}

/**
 * 规范化为字段数组；去掉末尾「年」字段（若有）
 * @returns {{ parts: string[], hasSecond: boolean } | null}
 */
export function normalizeCronParts(expr) {
  if (!expr || typeof expr !== 'string') return null
  let parts = expr.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 7) parts = parts.slice(0, 6)
  if (parts.length === 5) return { parts, hasSecond: false }
  if (parts.length === 6) return { parts, hasSecond: true }
  return null
}

function sortedSeconds(secondSet, hasSecond) {
  if (!hasSecond) return [0]
  if (!secondSet) {
    const all = []
    for (let i = 0; i <= 59; i++) all.push(i)
    return all
  }
  return [...secondSet].sort((a, b) => a - b)
}

/**
 * @param {string} expr - 5 或 6 段 cron 表达式
 * @param {number} count - 返回接下来几次执行时间
 * @returns {string[]} YYYY-MM-DD HH:mm:ss，解析失败返回 []
 */
export function getCronNextRunTimes(expr, count = 10) {
  const normalized = normalizeCronParts(expr)
  if (!normalized) return []
  const { parts, hasSecond } = normalized
  const offset = hasSecond ? 1 : 0
  const secondSet = hasSecond ? parseCronField(parts[0], 0, 59) : new Set([0])
  const minuteSet = parseCronField(parts[offset], 0, 59)
  const hourSet = parseCronField(parts[offset + 1], 0, 23)
  const daySet = parseCronField(parts[offset + 2], 1, 31)
  const monthSet = parseCronField(parts[offset + 3], 1, 12)
  const dowSet = parseCronField(parts[offset + 4], 0, 7)
  const seconds = sortedSeconds(secondSet, hasSecond)

  const matchDateTime = (d) => {
    const m = d.month() + 1
    const day = d.date()
    const h = d.hour()
    const min = d.minute()
    const dow = d.day()
    if (monthSet && !monthSet.has(m)) return false
    if (daySet && !daySet.has(day)) return false
    if (dowSet && !dowSet.has(dow) && !(dow === 0 && dowSet.has(7))) return false
    if (hourSet && !hourSet.has(h)) return false
    if (minuteSet && !minuteSet.has(min)) return false
    return true
  }

  const results = []
  const now = dayjs()
  // 按分钟扫描，分钟内再匹配秒，避免逐秒遍历过慢
  let cursor = now.startOf('minute')
  const maxIter = 365 * 24 * 60
  let iter = 0
  while (results.length < count && iter < maxIter) {
    iter++
    if (matchDateTime(cursor)) {
      for (const sec of seconds) {
        const t = cursor.second(sec).millisecond(0)
        if (t.isAfter(now)) {
          results.push(t.format('YYYY-MM-DD HH:mm:ss'))
          if (results.length >= count) break
        }
      }
    }
    cursor = cursor.add(1, 'minute')
  }
  return results
}
