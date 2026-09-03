import dayjs from 'dayjs'

/**
 * @desc  格式化时间
 * @param {(Object|string|number)} time
 * @param {string} format
 * @returns {string | null}
 */
export function formatDateTime(time = undefined, format = 'YYYY-MM-DD HH:mm:ss') {
    return dayjs(time).format(format)
}

export function formatDate(date = undefined, format = 'YYYY-MM-DD') {
    return formatDateTime(date, format)
}

/**
 * @desc  定义时间段
 * @returns {string}
 */
export function currentTimePeriod(regards= false) {
    // 获取当前时间并计算时间段
    const currentTime = new Date()
    const currentHour = currentTime.getHours()
    if (currentHour >= 0 && currentHour < 6) {
        return regards ? "凌晨啦" : "凌晨"
    } else if (currentHour >= 6 && currentHour < 9) {
        return regards ? "早上好" : "早上"
    } else if (currentHour >= 9 && currentHour < 12) {
        return regards ? "上午好" : "上午"
    } else if (currentHour >= 12 && currentHour < 13) {
        return regards ? "中午好" : "中午"
    } else if (currentHour >= 13 && currentHour < 17) {
        return regards ? "下午好" : "下午"
    } else if (currentHour >= 17 && currentHour < 20) {
        return regards ? "傍晚好" : "傍晚"
    } else if (currentHour >= 20 && currentHour < 23) {
      return regards ? "深夜啦" : "深夜"
    } else {
        return regards ? "夜间啦" : "夜间"
    }
}

/**
 * @desc  函数节流
 * @param {Function} fn
 * @param {Number} wait
 * @returns {Function}
 */
export function throttle(fn, wait) {
    var context, args
    var previous = 0

    return function () {
        var now = +new Date()
        context = this
        args = arguments
        if (now - previous > wait) {
            fn.apply(context, args)
            previous = now
        }
    }
}

/**
 * @desc  函数防抖
 * @param {Function} func
 * @param {number} wait
 * @param {boolean} immediate
 * @return {*}
 */
export function debounce(method, wait, immediate) {
    let timeout
    return function (...args) {
        let context = this
        if (timeout) {
            clearTimeout(timeout)
        }
        // 立即执行需要两个条件，一是immediate为true，二是timeout未被赋值或被置为null
        if (immediate) {
            /**
             * 如果定时器不存在，则立即执行，并设置一个定时器，wait毫秒后将定时器置为null
             * 这样确保立即执行后wait毫秒内不会被再次触发
             */
            let callNow = !timeout
            timeout = setTimeout(() => {
                timeout = null
            }, wait)
            if (callNow) {
                method.apply(context, args)
            }
        } else {
            // 如果immediate为false，则函数wait毫秒后执行
            timeout = setTimeout(() => {
                /**
                 * args是一个类数组对象，所以使用fn.apply
                 * 也可写作method.call(context, ...args)
                 */
                method.apply(context, args)
            }, wait)
        }
    }
}

/**
 * @desc  任意值转格式化 JSON 文本：对象直接美化；字符串尝试解析后美化，解析失败原样返回
 * @param {*} val 任意值
 * @returns {string}
 */
export function toPrettyJson(val) {
    if (val == null || val === '') return ''
    if (typeof val === 'string') {
        try {
            return JSON.stringify(JSON.parse(val), null, 2)
        } catch {
            return val
        }
    }
    try {
        return JSON.stringify(val, null, 2)
    } catch {
        return String(val)
    }
}

/**
 * @desc  JSON 摘要截断展示：字符串先规范化再截断，超长以省略号结尾
 * @param {*} val 任意值
 * @param {number} maxLen 最大长度
 * @returns {string}
 */
export function formatJsonBrief(val, maxLen = 50) {
    if (val == null || val === '') return '-'
    let s
    if (typeof val === 'string') {
        try {
            s = JSON.stringify(JSON.parse(val))
        } catch {
            s = val
        }
    } else {
        s = JSON.stringify(val)
    }
    return s.length > maxLen ? `${s.slice(0, maxLen)}...` : s
}

/**
 * @desc  任务结果摘要取信封 raw；旧记录无信封时整包展示
 * @param {*} summary 任务结果摘要
 * @returns {*}
 */
export function resultPayloadOf(summary) {
    return summary && typeof summary === 'object' && 'raw' in summary ? summary.raw : summary
}

/**
 * @desc  复制文本到剪贴板：clipboard API 优先，降级隐藏 textarea + execCommand
 * @param {string} text 待复制文本
 * @param {string} [successMsg] 复制成功提示，传空串则不提示
 * @returns {Promise<boolean>} 是否复制成功
 */
export async function copyTextToClipboard(text, successMsg = '已复制到剪贴板') {
    if (!text) {
        window.$message?.warning?.('暂无内容可复制')
        return false
    }
    try {
        if (navigator?.clipboard?.writeText) {
            await navigator.clipboard.writeText(text)
        } else {
            const ta = document.createElement('textarea')
            ta.value = text
            ta.style.position = 'fixed'
            ta.style.left = '-9999px'
            document.body.appendChild(ta)
            ta.select()
            document.execCommand('copy')
            document.body.removeChild(ta)
        }
        if (successMsg) window.$message?.success?.(successMsg)
        return true
    } catch {
        window.$message?.error?.('复制失败，请手动选择复制')
        return false
    }
}
