// 解析 crontab 5 段表达式，计算接下来 N 次执行时间
// 格式: 分(0-59) 时(0-23) 日(1-31) 月(1-12) 周(0-7, 0和7为周日)
// 支持: * , N , N-M , */S , N,M
import dayjs from 'dayjs'

function parseCronField(field, min, max) {
    const s = String(field).trim()
    if (s === '*' || s === '') return null
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
 * @param {string} expr - 5 段 cron 表达式，如 "0 0 * * *"
 * @param {number} count - 返回接下来几次执行时间
 * @returns {string[]} 格式化的时间字符串数组，解析失败返回 []
 */
export function getCronNextRunTimes(expr, count = 5) {
    if (!expr || typeof expr !== 'string') return []
    const parts = expr.trim().split(/\s+/)
    if (parts.length < 5) return []
    const minuteSet = parseCronField(parts[0], 0, 59)
    const hourSet = parseCronField(parts[1], 0, 23)
    const daySet = parseCronField(parts[2], 1, 31)
    const monthSet = parseCronField(parts[3], 1, 12)
    const dowSet = parseCronField(parts[4], 0, 7)
    const match = (d) => {
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
    let start = dayjs().add(1, 'minute').second(0).millisecond(0)
    const maxIter = 365 * 24 * 60
    let iter = 0
    while (results.length < count && iter < maxIter) {
        iter++
        if (match(start)) {
            results.push(start.format('YYYY-MM-DD HH:mm'))
        }
        start = start.add(1, 'minute')
    }
    return results
}
