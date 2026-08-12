import { forEachStep } from '@/views/autotest/steps/utils/stepTreeMap'
import { toPositiveCaseId } from '@/views/autotest/steps/utils/prepareCaseExecute'
import {
    createEmptyStepTreePayloadTemplate,
    stripIdentityFieldsForNewCase,
} from '@/views/autotest/steps/utils/stepSourceJson'

const LOCAL_TYPE_TO_BACKEND = {
    user_variables: '用户变量',
    tcp: 'TCP请求',
    http: 'HTTP请求',
    code: '代码请求(Python)',
    if: '条件分支',
    loop: '循环结构',
    wait: '等待控制',
    quote: '引用公共脚本',
    database: '数据库请求',
    redis: 'Redis请求',
    assert: '断言',
}

export const localTypeToBackend = (localType) => LOCAL_TYPE_TO_BACKEND[localType] || '代码请求(Python)'

export const assignStepNumbers = (steps) => {
    const stepNoMap = new Map()
    let counter = 1
    const traverse = (step) => {
        stepNoMap.set(step, counter++)
        const orderedChildren = getBranchOrderedChildren(step)
        if (orderedChildren.length > 0) {
            orderedChildren.forEach(traverse)
        }
    }
    steps.forEach(traverse)
    return stepNoMap
}

export const filterKeyValueList = (list) => {
    // 空列表归一为null：与后端「有数据或NULL」两态语义对齐，不再产出空数组
    if (!Array.isArray(list)) return null
    const filtered = list.filter((item) => item && String(item.key ?? '').trim() !== '')
    return filtered.length > 0 ? filtered : null
}

/**
 * 条件分支子步骤按分支序号稳定排序（组内保持原有相对顺序）。
 * 后端保存与查询均按 branch_index 分组返回（success_detail、branch_children），
 * 前端所有依赖遍历顺序的环节（step_no 分配、保存后回写 step_id/step_code）
 * 必须使用同一顺序，否则步骤标识错配，导致 branch_index 标注错乱（多层嵌套时尤为明显）。
 */
export const getBranchOrderedChildren = (step) => {
    const children = step?.children || []
    if (step?.type !== 'if' || !Array.isArray(step?.config?.branch_items) || children.length === 0) {
        return children
    }
    return children
        .map((child, index) => ({ child, index }))
        .sort((a, b) => ((a.child.branch_index ?? 0) - (b.child.branch_index ?? 0)) || (a.index - b.index))
        .map(item => item.child)
}

export const mergeStepTreeWithSuccessDetail = (stepList, detailList) => {
    if (!Array.isArray(detailList) || detailList.length === 0) return
    // 已持有 step_code 的步骤按编码精确匹配，防御返回顺序与遍历顺序不一致
    const detailByCode = new Map()
    for (const detail of detailList) {
        if (detail && detail.step_code) detailByCode.set(detail.step_code, detail)
    }
    let idx = 0
    const traverse = (list) => {
        if (!Array.isArray(list)) return
        for (const step of list) {
            const stepCode = step.original?.step_code
            const detail = (stepCode && detailByCode.get(stepCode)) || detailList[idx]
            if (detail && (detail.step_id != null || detail.step_code != null)) {
                if (!step.original) step.original = {}
                if (detail.step_id != null) step.original.id = detail.step_id
                if (detail.step_code != null) step.original.step_code = detail.step_code
            }
            idx += 1
            const orderedChildren = getBranchOrderedChildren(step)
            if (orderedChildren.length > 0) traverse(orderedChildren)
        }
    }
    traverse(stepList)
}

const resolveArrayField = (config, original, key) => {
    // 空数组归一为null：只保留「有数据」或「null」两态
    if (config[key] !== undefined) {
        return Array.isArray(config[key]) && config[key].length > 0 ? config[key] : null
    }
    if (original[key] != null) {
        return Array.isArray(original[key]) && original[key].length > 0 ? original[key] : null
    }
    return null
}

/**
 * 步骤树前后端序列化
 *
 * @param {object} deps
 * @param {import('vue').Ref<Array>} deps.steps - 前端步骤树
 * @param {import('vue').ComputedRef<string|null>} deps.caseId - 路由 case_id
 * @param {import('vue').ComputedRef<string|null>} deps.caseCode - 路由 case_code
 * @param {import('vue').Ref<{case_id, case_code}>} deps.appliedCaseMeta - 已应用源数据的用例标识
 * @param {import('vue').Ref} deps.caseInfoPanelRef - CaseInfoPanel 组件 ref
 */
export function useStepTreeSerialization({ steps, caseId, caseCode, appliedCaseMeta, caseInfoPanelRef }) {

    const resolveCaseMetaForPayload = () => {
        const fromRouteId = toPositiveCaseId(caseId.value)
        const fromRouteCode = caseCode.value ? String(caseCode.value) : null
        const fromAppliedId = toPositiveCaseId(appliedCaseMeta.value?.case_id)
        const fromAppliedCode = appliedCaseMeta.value?.case_code
            ? String(appliedCaseMeta.value.case_code)
            : null

        let fromStepsId = null
        let fromStepsCode = null
        forEachStep(steps.value, (s) => {
            if (fromStepsId != null && fromStepsCode) return
            const o = s?.original || {}
            if (fromStepsId == null) {
                fromStepsId = toPositiveCaseId(o.case_id ?? o.case?.case_id)
            }
            if (!fromStepsCode) {
                const code = o.case_code ?? o.case?.case_code
                if (code) fromStepsCode = String(code)
            }
        })

        return {
            case_id: fromRouteId ?? fromAppliedId ?? fromStepsId ?? null,
            case_code: fromRouteCode || fromAppliedCode || fromStepsCode || null,
        }
    }

    const convertStepToBackend = (step, parentStepId = null, stepNoMap = null) => {
        const stepNo = stepNoMap ? (stepNoMap.get(step) || 1) : 1
        const original = step.original || {}
        const config = step.config || {}

        const hasStepId = original.id !== undefined && original.id !== null
        const hasStepCode = original.step_code !== undefined && original.step_code !== null && original.step_code !== ''
        const isUpdate = hasStepId && hasStepCode

        const backendStep = {
            step_name: step.name || original.step_name || '',
            step_desc: config.step_desc !== undefined ? (config.step_desc ?? '') : (original.step_desc || ''),
            step_type: localTypeToBackend(step.type),
            step_no: stepNo,
            case_id: original.case_id || caseId.value || null,
            parent_step_id: parentStepId,
            quote_case_id: original.quote_case_id || null,
            step_is_skipped: !!step.step_is_skipped,
            case_type: (caseInfoPanelRef.value?.caseForm?.case_type) || original.case_type || '用户脚本',
        }

        if (isUpdate) {
            backendStep.step_id = original.id
            backendStep.step_code = original.step_code
        }

        if (step.type === 'tcp') {
            backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
            backendStep.request_config_name = config.request_config_name !== undefined
                ? (config.request_config_name || null)
                : (original.request_config_name || null)
            backendStep.request_url = null
            backendStep.request_port = null

            const argsTypeRaw = (config.request_args_type ?? original.request_args_type ?? 'xml').toString().toLowerCase()
            backendStep.request_args_type = ['xml', 'json', 'raw'].includes(argsTypeRaw) ? argsTypeRaw : 'xml'

            backendStep.request_body = config.data !== undefined
                ? (config.data ?? null)
                : (original.request_body ?? null)

            backendStep.request_text = config.request_text != null
                ? config.request_text
                : (original.request_text ?? null)

            backendStep.extract_variables = resolveArrayField(config, original, 'extract_variables')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')

            backendStep.data_source_id = config.data_source_id !== undefined
                ? (config.data_source_id || null)
                : (original.data_source_id || null)
            backendStep.data_source_name = config.data_source_name !== undefined
                ? (config.data_source_name || null)
                : (original.data_source_name || null)
            backendStep.data_source_desc = config.data_source_desc !== undefined
                ? (config.data_source_desc || null)
                : (original.data_source_desc || null)
        }
        if (step.type === 'http') {
            backendStep.request_method = config.method || original.request_method || 'POST'
            backendStep.request_url = config.url || original.request_url || ''
            backendStep.request_args_type = config.request_args_type ?? original.request_args_type ?? 'none'
            backendStep.request_text = config.request_text ?? original.request_text ?? null
            backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
            backendStep.request_config_name = config.request_config_name !== undefined
                ? (config.request_config_name || null)
                : (original.request_config_name || null)
            backendStep.request_header = filterKeyValueList(Array.isArray(config.headers) ? config.headers : (Array.isArray(original.request_header) ? original.request_header : []))
            backendStep.request_params = filterKeyValueList(Array.isArray(config.params) ? config.params : (Array.isArray(original.request_params) ? original.request_params : []))
            backendStep.request_form_data = filterKeyValueList(Array.isArray(config.form_data) ? config.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : []))
            backendStep.request_form_urlencoded = filterKeyValueList(Array.isArray(config.form_urlencoded) ? config.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : []))
            backendStep.request_body = config.data !== undefined ? (config.data ?? null) : (original.request_body ?? null)
            backendStep.data_source_id = config.data_source_id !== undefined
                ? (config.data_source_id || null)
                : (original.data_source_id || null)
            backendStep.data_source_name = config.data_source_name !== undefined
                ? (config.data_source_name || null)
                : (original.data_source_name || null)
            backendStep.data_source_desc = config.data_source_desc !== undefined
                ? (config.data_source_desc || null)
                : (original.data_source_desc || null)

            backendStep.extract_variables = resolveArrayField(config, original, 'extract_variables')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')

            backendStep.defined_variables = filterKeyValueList(Array.isArray(config.defined_variables) ? config.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : []))
        } else if (step.type === 'code') {
            backendStep.code = config.code !== undefined ? config.code : (original.code || '')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')
        } else if (step.type === 'assert') {
            backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '断言')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')
        } else if (step.type === 'loop') {
            backendStep.loop_mode = config.loop_mode || original.loop_mode || '次数循环'
            backendStep.loop_on_error = config.loop_on_error || original.loop_on_error || '中断循环'
            backendStep.loop_interval = config.loop_interval !== undefined ? Number(config.loop_interval) : (original.loop_interval ? Number(original.loop_interval) : 0)

            if (backendStep.loop_mode === '次数循环') {
                backendStep.loop_maximums = config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original.loop_maximums != null ? Number(original.loop_maximums) : 5)
            } else if (backendStep.loop_mode === '列表循环') {
                backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
            } else if (backendStep.loop_mode === '字典循环') {
                backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
            } else if (backendStep.loop_mode === '条件循环') {
                const fromConfigDict = config.loop_conditions && typeof config.loop_conditions === 'object' && !Array.isArray(config.loop_conditions)
                    ? config.loop_conditions
                    : null
                if (fromConfigDict) {
                    backendStep.loop_conditions = {
                        condition_expr: fromConfigDict.condition_expr != null ? String(fromConfigDict.condition_expr) : '',
                        condition_compare: fromConfigDict.condition_compare || '非空',
                        condition_value: fromConfigDict.condition_value != null ? String(fromConfigDict.condition_value) : '',
                    }
                } else if (
                    config.condition_expr !== undefined
                    || config.condition_compare !== undefined
                    || config.condition_value !== undefined
                ) {
                    backendStep.loop_conditions = {
                        condition_expr: config.condition_expr != null ? String(config.condition_expr) : '',
                        condition_compare: config.condition_compare || '非空',
                        condition_value: config.condition_value != null ? String(config.condition_value) : '',
                    }
                } else if (original.loop_conditions && typeof original.loop_conditions === 'object' && !Array.isArray(original.loop_conditions)) {
                    const oc = original.loop_conditions
                    backendStep.loop_conditions = {
                        condition_expr: oc.condition_expr != null ? String(oc.condition_expr) : '',
                        condition_compare: oc.condition_compare || '非空',
                        condition_value: oc.condition_value != null ? String(oc.condition_value) : '',
                    }
                } else {
                    backendStep.loop_conditions = null
                }
                backendStep.loop_timeout = config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original.loop_timeout ? Number(original.loop_timeout) : 0)
            }
        } else if (step.type === 'if') {
            const branchItems = Array.isArray(config.branch_items) ? config.branch_items : []
            const childrenByBranch = {}
            for (const child of (step.children || [])) {
                const bi = child.branch_index ?? 0
                if (!childrenByBranch[bi]) childrenByBranch[bi] = []
                childrenByBranch[bi].push(child)
            }
            backendStep.branch_items = branchItems.map((branch, bi) => {
                const branchPayload = {
                    branch_type: branch.branch_type || 'if',
                    branch_desc: branch.branch_desc || '',
                    branch_conditions: null,
                }
                if (branch.branch_type !== 'else' && branch.branch_conditions) {
                    branchPayload.branch_conditions = {
                        condition_expr: branch.branch_conditions.condition_expr != null ? String(branch.branch_conditions.condition_expr) : '',
                        condition_compare: branch.branch_conditions.condition_compare || '非空',
                        condition_value: branch.branch_conditions.condition_value != null ? String(branch.branch_conditions.condition_value) : '',
                    }
                }
                const branchChildren = childrenByBranch[bi] || []
                const parentIdForChildren = isUpdate ? original.id : null
                branchPayload.branch_children = branchChildren.map((child) => convertStepToBackend(child, parentIdForChildren, stepNoMap))
                return branchPayload
            })
            backendStep.loop_conditions = null
        } else if (step.type === 'wait') {
            backendStep.wait = config.seconds || original.wait || 0
        } else if (step.type === 'user_variables') {
            backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || '')
            backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
            const sv = config.session_variables ?? original.session_variables
            const list = Array.isArray(sv) ? sv : []
            backendStep.session_variables = filterKeyValueList(list.map(item => ({
                key: item.key || '',
                value: item.value ?? '',
                desc: item.desc ?? item.description ?? '',
            })))
        } else if (step.type === 'quote') {
            backendStep.quote_case_id = config.quote_case_id ?? original.quote_case_id ?? null
            backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
        } else if (step.type === 'database') {
            backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
            backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
            backendStep.database_searched = !!(config.database_searched ?? original.database_searched)
            const ops = config.database_operates ?? original.database_operates
            backendStep.database_operates = Array.isArray(ops) && ops.length > 0 ? ops : null
            backendStep.extract_variables = resolveArrayField(config, original, 'extract_variables')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')
        } else if (step.type === 'redis') {
            backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
            backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
            backendStep.redis_searched = !!(config.redis_searched ?? original.redis_searched)
            const ops = config.redis_operates ?? original.redis_operates
            backendStep.redis_operates = Array.isArray(ops) && ops.length > 0 ? ops : null
            backendStep.extract_variables = resolveArrayField(config, original, 'extract_variables')
            backendStep.assert_validators = resolveArrayField(config, original, 'assert_validators')
        }

        if (step.type !== 'if' && step.children && step.children.length > 0) {
            const parentIdForChildren = isUpdate ? original.id : null
            backendStep.children = step.children.map((child) => convertStepToBackend(child, parentIdForChildren, stepNoMap))
        }

        if (original.case) {
            backendStep.case = original.case
        } else {
            const casePayload = caseInfoPanelRef.value?.getCasePayload?.() ?? {}
            const caseMeta = resolveCaseMetaForPayload()
            backendStep.case = {
                case_id: caseMeta.case_id,
                case_code: caseMeta.case_code,
                ...casePayload,
            }
        }

        const cleanedStep = {}
        for (const key in backendStep) {
            const value = backendStep[key]
            if (!isUpdate && (key === 'step_id' || key === 'step_code')) continue
            if (isUpdate && (key === 'step_id' || key === 'step_code')) {
                if (value === undefined || value === null) continue
            }
            if (value !== undefined) {
                cleanedStep[key] = value
            }
        }

        return cleanedStep
    }

    const buildUpdateOrCreateTreePayload = () => {
        const isNewCasePage = toPositiveCaseId(caseId.value) == null && !caseCode.value
        const casePayload = caseInfoPanelRef.value?.getCasePayload?.() ?? {}
        const countTotalSteps = (list) => {
            let count = 0
            for (const step of list || []) {
                count++
                if (step.children?.length) count += countTotalSteps(step.children)
            }
            return count
        }
        const totalSteps = countTotalSteps(steps.value)

        let caseInfo
        if (isNewCasePage) {
            caseInfo = {
                case_id: null,
                case_code: null,
                ...casePayload,
                case_steps: totalSteps,
            }
        } else {
            const caseMeta = resolveCaseMetaForPayload()
            caseInfo = {
                case_id: caseMeta.case_id,
                case_code: caseMeta.case_code,
                ...casePayload,
                case_steps: totalSteps,
            }
        }

        if (!steps.value?.length) {
            return createEmptyStepTreePayloadTemplate(caseInfo)
        }
        const stepNoMap = assignStepNumbers(steps.value)
        const backendSteps = steps.value.map((step) => convertStepToBackend(step, null, stepNoMap))
        const payload = { case: caseInfo, steps: backendSteps }
        return isNewCasePage ? stripIdentityFieldsForNewCase(payload) : payload
    }

    return {
        resolveCaseMetaForPayload,
        convertStepToBackend,
        buildUpdateOrCreateTreePayload,
    }
}
