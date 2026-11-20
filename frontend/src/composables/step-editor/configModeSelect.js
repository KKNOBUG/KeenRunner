import { h } from 'vue'

/** 失效引用文案：mode 已不在启用配置集合中（配置被删除或历史步骤未回填） */
export const CONFIG_MODE_INVALID_LABEL = '配置已失效，请重新选择'

/**
 * 构造「配置名称」下拉选项：label=config_name、value=config_mode（8.1 契约）。
 *
 * 当前值不在启用配置集合中时补一条失效项：保证旧步骤仍能看到“已失效”，
 * 且用户重新选择任一有效项即可覆盖，避免下拉把 43 位 mode 原样暴露给用户。
 *
 * @param {Array<{config_name?: string, config_mode?: string}>} pairs 配置名称/逻辑标识对（服务端已按 mode 去重）
 * @param {string|null|undefined} currentMode 当前选中的逻辑标识
 * @returns {Array<{label: string, value: string}>}
 */
export const buildConfigModeOptions = (pairs, currentMode) => {
    const options = []
    const seen = new Set()
    for (const item of Array.isArray(pairs) ? pairs : []) {
        const mode = String(item?.config_mode ?? '').trim()
        if (!mode || seen.has(mode)) continue
        seen.add(mode)
        options.push({ label: String(item?.config_name ?? '').trim() || mode.slice(0, 8), value: mode })
    }
    const current = String(currentMode ?? '').trim()
    if (current && !seen.has(current)) {
        options.unshift({ label: CONFIG_MODE_INVALID_LABEL, value: current })
    }
    return options
}

/** 失效项标红（n-select render-label），其余保持默认文本渲染 */
export const renderConfigModeLabel = (option) => {
    const label = String(option?.label ?? '')
    if (!label.startsWith(CONFIG_MODE_INVALID_LABEL)) return option?.label
    return h('span', { style: 'color: #d03050' }, label)
}