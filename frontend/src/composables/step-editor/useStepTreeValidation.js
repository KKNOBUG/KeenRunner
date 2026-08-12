import { validateAssertList, validateExtractList } from '@/utils/autotestExtractAssert'

const hasEmptyKeyInList = (list) => {
    if (!Array.isArray(list)) return false
    return list.some((item) => item != null && String(item.key ?? '').trim() === '' && String(item.value ?? '').trim() !== '')
}

const normalizeOperatesList = (ops) => {
    if (ops == null) return []
    if (Array.isArray(ops)) return ops
    if (typeof ops === 'object') {
        const keys = Object.keys(ops).map((k) => parseInt(k, 10)).filter((n) => !isNaN(n)).sort((a, b) => a - b)
        return keys.map((k) => ops[k])
    }
    return []
}

const resolveStepListField = (config, original, key) => {
    if (config[key] !== undefined) {
        return Array.isArray(config[key]) ? config[key] : []
    }
    return Array.isArray(original[key]) ? original[key] : []
}

export const getFixedBranchStepDisplayName = (step) => {
    if (!step?.type) return null
    if (step.type === 'if') {
        // 条件分支步骤名称固定，不随 IF/ELIF/ELSE 组合变化
        return '条件分支'
    }
    if (step.type === 'loop') {
        const mode = (step.config && step.config.loop_mode) || '次数循环'
        if (mode === '次数循环') return '循环结构(次数循环)'
        if (mode === '列表循环') return '循环结构(列表循环)'
        if (mode === '字典循环') return '循环结构(字典循环)'
        if (mode === '条件循环') return '循环结构(条件循环)'
        return '循环结构'
    }
    return null
}

const getStepNameAsWillPersist = (step) => {
    const original = step.original || {}
    const config = step.config || {}
    const fixed = getFixedBranchStepDisplayName(step)
    if (fixed) return String(fixed).trim()

    if (step.type === 'user_variables') {
        const v = config.step_name !== undefined ? config.step_name : (original.step_name || '')
        return String(v ?? '').trim()
    }
    if (step.type === 'quote' || step.type === 'quote_public_script') {
        const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
        return String(v ?? '').trim()
    }
    if (step.type === 'database') {
        const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
        return String(v ?? '').trim()
    }
    if (step.type === 'redis') {
        const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
        return String(v ?? '').trim()
    }

    return String(step.name || original.step_name || '').trim()
}

const isStepNameExplicitlyEmptyInEditor = (step) => {
    const config = step.config || {}
    if (!Object.prototype.hasOwnProperty.call(config, 'step_name')) return false
    return String(config.step_name ?? '').trim() === ''
}

const validateDatabaseSteps = (stepList) => {
    for (const step of stepList) {
        if (step.type === 'database') {
            const config = step.config || {}
            const original = step.original || {}
            const rawOps = config.database_operates ?? original.database_operates
            const stepName = step.name || original.step_name || '未命名步骤'

            if (rawOps != null && typeof rawOps !== 'object') {
                return { valid: false, message: `步骤：${stepName}，请求配置格式无效，请重新打开步骤编辑或删除后添加` }
            }

            const list = normalizeOperatesList(rawOps)
            if (!list.length) {
                return { valid: false, message: `步骤：${stepName}：请至少添加一条数据库操作` }
            }

            for (let i = 0; i < list.length; i++) {
                const o = list[i] || {}
                const idxLabel = `第${i + 1}条`
                const pid = o.project_id
                const hasApp =
                    String(o.project_name ?? '').trim() !== ''
                    || (pid != null && pid !== '' && String(pid).trim() !== '')
                if (!hasApp) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请选择所属应用` }
                }
                if (!String(o.config_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写配置名称` }
                }
                if (!String(o.database_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写数据库名称` }
                }
                if (!String(o.expr ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写SQL语句` }
                }
                if (!String(o.variable_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写存储变量` }
                }
                const opDisplayName = String(o.name ?? '').trim()
                if (!opDisplayName) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写操作名称` }
                }
            }

            const nameSet = new Set()
            for (let j = 0; j < list.length; j++) {
                const nm = String((list[j] || {}).name ?? '').trim()
                if (nameSet.has(nm)) {
                    return { valid: false, message: `步骤：${stepName}，操作名称不允许重复，请修改后再保存或调试` }
                }
                nameSet.add(nm)
            }
        }
        if (step.children && step.children.length > 0) {
            const child = validateDatabaseSteps(step.children)
            if (!child.valid) return child
        }
    }
    return { valid: true }
}

const validateRedisSteps = (stepList) => {
    for (const step of stepList) {
        if (step.type === 'redis') {
            const config = step.config || {}
            const original = step.original || {}
            const rawOps = config.redis_operates ?? original.redis_operates
            const stepName = step.name || original.step_name || '未命名步骤'

            if (rawOps != null && typeof rawOps !== 'object') {
                return { valid: false, message: `步骤：${stepName}，请求配置格式无效，请重新打开步骤编辑或删除后添加` }
            }

            const list = normalizeOperatesList(rawOps)
            if (!list.length) {
                return { valid: false, message: `步骤：${stepName}：请至少添加一条Redis操作` }
            }

            for (let i = 0; i < list.length; i++) {
                const o = list[i] || {}
                const idxLabel = `第${i + 1}条`
                const pid = o.project_id
                const hasApp =
                    String(o.project_name ?? '').trim() !== ''
                    || (pid != null && pid !== '' && String(pid).trim() !== '')
                if (!hasApp) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请选择所属应用` }
                }
                if (!String(o.config_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写配置名称` }
                }
                if (!String(o.database_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写库编号` }
                }
                if (!String(o.expr ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写Redis命令` }
                }
                if (!String(o.variable_name ?? '').trim()) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写存储变量` }
                }
                const opDisplayName = String(o.name ?? '').trim()
                if (!opDisplayName) {
                    return { valid: false, message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写操作名称` }
                }
            }

            const nameSet = new Set()
            for (let j = 0; j < list.length; j++) {
                const nm = String((list[j] || {}).name ?? '').trim()
                if (nameSet.has(nm)) {
                    return { valid: false, message: `步骤：${stepName}，操作名称不允许重复，请修改后再保存或调试` }
                }
                nameSet.add(nm)
            }
        }
        if (step.children && step.children.length > 0) {
            const child = validateRedisSteps(step.children)
            if (!child.valid) return child
        }
    }
    return { valid: true }
}

const validateHttpTcpStepsRequired = (stepList) => {
    const walk = (list) => {
        if (!Array.isArray(list)) return { valid: true }
        for (const step of list) {
            const stepLabel = step.name || step.original?.step_name || '未命名步骤'
            const config = step.config || {}
            const original = step.original || {}

            if (step.type === 'http') {
                const projectId = config.request_project_id ?? original.request_project_id ?? null
                const emptyProject = projectId === null || projectId === undefined || projectId === ''

                let cfgName = ''
                if (config.request_config_name !== undefined) {
                    cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
                } else {
                    cfgName = String(original.request_config_name ?? '').trim()
                }

                const url = String(config.url ?? original.request_url ?? '').trim()

                if (emptyProject) {
                    return { valid: false, message: `步骤：${stepLabel}，请选择所属应用后再保存` }
                }
                if (!cfgName) {
                    return { valid: false, message: `步骤：${stepLabel}，请填写配置名称后再保存` }
                }
                if (!url) {
                    return { valid: false, message: `步骤：${stepLabel}，请填写请求地址后再保存` }
                }
            }

            if (step.type === 'tcp') {
                const projectId = config.request_project_id ?? original.request_project_id ?? null
                const emptyProject = projectId === null || projectId === undefined || projectId === ''

                let cfgName = ''
                if (config.request_config_name !== undefined) {
                    cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
                } else {
                    cfgName = String(original.request_config_name ?? '').trim()
                }

                if (emptyProject) {
                    return { valid: false, message: `步骤：${stepLabel}，请选择所属应用后再保存` }
                }
                if (!cfgName) {
                    return { valid: false, message: `步骤：${stepLabel}，请填写配置名称后再保存` }
                }
            }

            if (step.children && step.children.length > 0) {
                const child = walk(step.children)
                if (!child.valid) return child
            }
        }
        return { valid: true }
    }
    return walk(stepList)
}

const validateExtractAssertInSteps = (stepList) => {
    for (const step of stepList) {
        const config = step.config || {}
        const original = step.original || {}
        const stepName = step.name || config.step_name || original.step_name || '未命名步骤'
        const extractResult = validateExtractList(resolveStepListField(config, original, 'extract_variables'))
        if (!extractResult.valid) {
            return { valid: false, message: `步骤：${stepName}，${extractResult.message}` }
        }
        const assertList = resolveStepListField(config, original, 'assert_validators')
        if (step.type === 'assert' && (!Array.isArray(assertList) || assertList.length === 0)) {
            return { valid: false, message: `步骤：${stepName}，断言步骤至少需要配置一条断言规则` }
        }
        const assertResult = validateAssertList(assertList)
        if (!assertResult.valid) {
            return { valid: false, message: `步骤：${stepName}，${assertResult.message}` }
        }
        if (step.children && step.children.length > 0) {
            const childResult = validateExtractAssertInSteps(step.children)
            if (!childResult.valid) return childResult
        }
    }
    return { valid: true }
}

const validateEmptyKeyInSteps = (stepList) => {
    for (const step of stepList) {
        const config = step.config || {}
        const original = step.original || {}
        const getList = (key) => (Array.isArray(config[key]) ? config[key] : Array.isArray(original[key]) ? original[key] : [])
        let listName = ''
        if (step.type === 'http') {
            if (hasEmptyKeyInList(getList('headers')) || hasEmptyKeyInList(getList('request_header'))) listName = '请求头'
            else if (hasEmptyKeyInList(getList('params')) || hasEmptyKeyInList(getList('request_params'))) listName = '请求体 params'
            else if (hasEmptyKeyInList(getList('form_data')) || hasEmptyKeyInList(getList('request_form_data'))) listName = '请求体 form-data'
            else if (hasEmptyKeyInList(getList('form_urlencoded')) || hasEmptyKeyInList(getList('request_form_urlencoded'))) listName = '请求体 x-www-form-urlencoded'
            else if (hasEmptyKeyInList(getList('defined_variables'))) listName = '变量'
        } else if (step.type === 'user_variables') {
            if (hasEmptyKeyInList(getList('session_variables'))) listName = '用户变量'
        }
        if (listName) {
            return { valid: false, stepName: step.name || step.original?.step_name || '未命名步骤', listName }
        }
        if (step.children && step.children.length > 0) {
            const childResult = validateEmptyKeyInSteps(step.children)
            if (!childResult.valid) return childResult
        }
    }
    return { valid: true }
}

const validateJsonBodyInSteps = (stepList) => {
    for (const step of stepList) {
        const config = step.config || {}
        const original = step.original || {}
        const stepName = step.name || config.step_name || original.step_name || '未命名步骤'

        if (step.type === 'http') {
            const requestArgsType = config.request_args_type ?? 'none'
            if (requestArgsType === 'json') {
                const raw = config.jsonBodyText ?? (config.data != null ? JSON.stringify(config.data) : '')
                const trimmed = (raw || '').trim()
                if (trimmed !== '') {
                    try {
                        JSON.parse(trimmed)
                    } catch (e) {
                        return { valid: false, message: e.message || 'JSON 格式错误', stepName }
                    }
                }
            }
            if (requestArgsType === 'xml') {
                const raw = config.request_text ?? ''
                const trimmed = (raw || '').trim()
                if (trimmed !== '') {
                    const parser = new DOMParser()
                    const doc = parser.parseFromString(trimmed, 'application/xml')
                    const parseError = doc.querySelector('parsererror')
                    if (parseError) {
                        return { valid: false, message: parseError.textContent || 'XML 格式错误', stepName }
                    }
                }
            }
        }

        if (step.type === 'tcp') {
            const raw = config.jsonBodyText ?? ''
            const trimmed = (raw || '').trim()
            if (trimmed !== '') {
                try {
                    JSON.parse(trimmed)
                } catch (e) {
                    return { valid: false, message: e.message || 'JSON 格式错误', stepName }
                }
            }
        }

        if (step.children && step.children.length > 0) {
            const childResult = validateJsonBodyInSteps(step.children)
            if (!childResult.valid) return childResult
        }
    }
    return { valid: true }
}

const validateXmlBodyInSteps = (stepList) => {
    for (const step of stepList) {
        if (step.type === 'tcp') {
            const config = step.config || {}
            const original = step.original || {}
            const stepName = step.name || config.step_name || original.step_name || '未命名步骤'
            const raw = config.xmlBodyText ?? ''
            const trimmed = (raw || '').trim()
            if (trimmed !== '') {
                const doc = new DOMParser().parseFromString(trimmed, 'text/xml')
                const pe = doc.querySelector('parsererror')
                if (pe && String(pe.textContent || '').trim()) {
                    return { valid: false, message: 'XML 语法错误', stepName }
                }
                if (!doc.documentElement) {
                    return { valid: false, message: 'XML 语法错误', stepName }
                }
            }
        }
        if (step.children && step.children.length > 0) {
            const childResult = validateXmlBodyInSteps(step.children)
            if (!childResult.valid) return childResult
        }
    }
    return { valid: true }
}

const validateStepNamesInSteps = (stepList, stepDefinitions) => {
    const walk = (list, usedNames) => {
        if (!Array.isArray(list)) return { valid: true }
        for (const step of list) {
            const typeLabel = stepDefinitions[step.type]?.label
                || (step.type === 'quote_public_script' ? '引用公共脚本' : (step.type || '步骤'))

            if (isStepNameExplicitlyEmptyInEditor(step)) {
                return { valid: false, message: `${typeLabel}：步骤名称不能为空，请填写后再保存` }
            }

            const name = getStepNameAsWillPersist(step)
            if (!name) {
                return { valid: false, message: `${typeLabel}：步骤名称不能为空，请填写后再保存` }
            }

            const exemptDuplicate = step.type === 'loop' || step.type === 'if'
            if (!exemptDuplicate) {
                if (usedNames.has(name)) {
                    return { valid: false, message: `步骤名称重复：${name}，除循环结构、条件分支外步骤名称不可重复，请修改后再保存` }
                }
                usedNames.set(name, true)
            }
            if (step.children && step.children.length > 0) {
                if (step.type === 'if') {
                    // 条件分支各分支互斥执行：分支之间允许重名，每个分支继承外层已用名称单独校验
                    const byBranch = new Map()
                    for (const child of step.children) {
                        const bi = child.branch_index ?? 0
                        if (!byBranch.has(bi)) byBranch.set(bi, [])
                        byBranch.get(bi).push(child)
                    }
                    for (const branchChildren of byBranch.values()) {
                        const child = walk(branchChildren, new Map(usedNames))
                        if (!child.valid) return child
                    }
                } else {
                    const child = walk(step.children, usedNames)
                    if (!child.valid) return child
                }
            }
        }
        return { valid: true }
    }

    return walk(stepList, new Map())
}

/**
 * 步骤树保存/调试前统一校验
 *
 * @param {object} options
 * @param {object} options.stepDefinitions - 步骤类型定义表（用于名称校验的 label）
 */
export function useStepTreeValidation({ stepDefinitions }) {

    const validateStepNames = (stepList) => validateStepNamesInSteps(stepList, stepDefinitions)

    /**
     * 按优先级顺序执行全部校验，首个失败即返回
     * @returns {{ valid: boolean, message?: string, stepName?: string, listName?: string }}
     */
    const validateAll = (stepList) => {
        const checks = [
            () => validateStepNames(stepList),
            () => validateHttpTcpStepsRequired(stepList),
            () => validateJsonBodyInSteps(stepList),
            () => validateXmlBodyInSteps(stepList),
            () => validateDatabaseSteps(stepList),
            () => validateRedisSteps(stepList),
            () => validateEmptyKeyInSteps(stepList),
            () => validateExtractAssertInSteps(stepList),
        ]
        for (const check of checks) {
            const result = check()
            if (!result.valid) return result
        }
        return { valid: true }
    }

    return {
        validateAll,
        validateStepNames,
        validateHttpTcpStepsRequired,
        validateJsonBodyInSteps,
        validateXmlBodyInSteps,
        validateDatabaseSteps,
        validateRedisSteps,
        validateEmptyKeyInSteps,
        validateExtractAssertInSteps,
    }
}
