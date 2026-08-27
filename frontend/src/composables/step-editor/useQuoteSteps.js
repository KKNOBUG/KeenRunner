import { ref } from 'vue'
import api from '@/api'
import { mapBackendStep, forEachStep } from '@/views/autotest/steps/utils/stepTreeMap'

const QUOTE_INNER_PREFIX = 'quote-inner:'

export const getQuoteInnerKey = (quoteStepId, flatIndex) => `${QUOTE_INNER_PREFIX}${quoteStepId}:${flatIndex}`

export const parseQuoteInnerKey = (key) => {
    if (!key || typeof key !== 'string' || !key.startsWith(QUOTE_INNER_PREFIX)) return null
    const rest = key.slice(QUOTE_INNER_PREFIX.length)
    const colon = rest.indexOf(':')
    if (colon === -1) return null
    const quoteStepId = rest.slice(0, colon)
    const flatIndex = parseInt(rest.slice(colon + 1), 10)
    if (Number.isNaN(flatIndex)) return null
    return { quoteStepId, flatIndex }
}

export const getQuoteStepsFlattened = (list, depth = 0, out = []) => {
    if (!list || !Array.isArray(list)) return out
    for (const step of list) {
        out.push({ step, depth })
        if (step.children && step.children.length) {
            getQuoteStepsFlattened(step.children, depth + 1, out)
        }
    }
    return out
}

/**
 * 引用公共脚本/接口管理：加载、展示、暂存/恢复、删除
 *
 * @param {object} deps
 * @param {import('vue').Ref<Array>} deps.steps - 前端步骤树
 * @param {(id: string) => object|null} deps.findStep - 按 id 查找步骤
 * @param {(id: string) => object|null} deps.findStepParent - 查找父节点
 * @param {(id: string) => boolean} deps.removeStep - 从树中删除步骤
 * @param {import('vue').Ref<Map>} deps.stepExpandStates - 展开状态
 * @param {import('vue').Ref<Array>} deps.selectedKeys - 选中步骤
 * @param {() => void} deps.updateStepDisplayNames - 刷新展示名
 */
export function useQuoteSteps({
    steps,
    findStep,
    findStepParent,
    removeStep,
    stepExpandStates,
    selectedKeys,
    updateStepDisplayNames,
}) {
    const quoteStepsMap = ref({})
    const stashedQuoteStepsWhenPublic = ref([])
    const stashedDataSourceWhenPublic = ref([])

    const forEachStepWithQuote = (list, fn, { includeQuoteInner = true } = {}) => {
        if (!list || !Array.isArray(list)) return
        for (const step of list) {
            fn(step)
            if (step.children && step.children.length) forEachStepWithQuote(step.children, fn, { includeQuoteInner })
            if (includeQuoteInner && step?.type === 'quote') {
                const inner = quoteStepsMap.value?.[step.id] || []
                if (Array.isArray(inner) && inner.length) {
                    forEachStepWithQuote(inner, fn, { includeQuoteInner: false })
                }
            }
        }
    }

    const loadQuoteStepsForStep = async (step) => {
        if (step.type !== 'quote' || !step.config?.quote_case_id) {
            quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
            return
        }
        try {
            const res = await api.getAutoTestStepTree({ case_id: step.config.quote_case_id })
            const data = Array.isArray(res?.data) ? res.data : []
            quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: data.map(mapBackendStep).filter(Boolean) }
        } catch (e) {
            console.error('加载引用脚本步骤失败', e)
            quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
        }
    }

    const loadQuoteStepsForAllQuoteSteps = () => {
        forEachStep(steps.value, (step) => {
            if (step.type === 'quote') loadQuoteStepsForStep(step)
        })
    }

    const loadQuoteStepsForAllQuoteStepsAsync = async () => {
        const quoteSteps = []
        forEachStep(steps.value, (s) => {
            if (s?.type === 'quote' && s?.config?.quote_case_id) quoteSteps.push(s)
        })
        if (!quoteSteps.length) return
        await Promise.all(quoteSteps.map((s) => loadQuoteStepsForStep(s)))
    }

    const fillQuoteStepsMapFromRawData = (rawList, mappedList) => {
        if (!rawList?.length || !mappedList?.length) return
        for (let i = 0; i < rawList.length; i++) {
            const raw = rawList[i]
            const mapped = mappedList[i]
            if (!raw || !mapped) continue
            if (raw.quote_steps?.length) {
                quoteStepsMap.value = {
                    ...quoteStepsMap.value,
                    [mapped.id]: raw.quote_steps.map(mapBackendStep).filter(Boolean),
                }
            }
            if (raw.children?.length && mapped.children?.length) {
                fillQuoteStepsMapFromRawData(raw.children, mapped.children)
            }
        }
    }

    const getQuoteInnerStep = (key) => {
        const parsed = parseQuoteInnerKey(key)
        if (!parsed) return null
        const list = quoteStepsMap.value[parsed.quoteStepId] || []
        const flat = getQuoteStepsFlattened(list)
        const item = flat[parsed.flatIndex]
        if (!item) return null
        return { ...item.step, isQuoteInner: true }
    }

    const removeAllQuoteSteps = () => {
        const quoteIds = []
        forEachStep(steps.value, (step) => {
            if (step.type === 'quote' || step.type === 'quote_public_script') {
                quoteIds.push(step.id)
            }
        })
        if (quoteIds.length === 0) return 0
        quoteIds.forEach((id) => {
            const step = findStep(id)
            if (step) {
                stepExpandStates.value.delete(id)
                removeStep(id)
            }
        })
        quoteIds.forEach((id) => {
            quoteStepsMap.value = { ...quoteStepsMap.value, [id]: [] }
        })
        if (quoteIds.includes(selectedKeys.value?.[0])) {
            selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
        }
        updateStepDisplayNames()
        return quoteIds.length
    }

    const collectQuoteStepsWithPosition = () => {
        const list = []
        forEachStep(steps.value, (step) => {
            if (step.type !== 'quote' && step.type !== 'quote_public_script') return
            const parent = findStepParent(step.id)
            const parentId = parent?.id ?? null
            const siblings = parentId === null ? steps.value : (parent?.children || [])
            const index = siblings.findIndex((s) => s.id === step.id)
            if (index === -1) return
            list.push({
                step: JSON.parse(JSON.stringify(step)),
                parentId,
                index,
            })
        })
        return list
    }

    const restoreStashedQuoteSteps = () => {
        const stashed = stashedQuoteStepsWhenPublic.value
        if (!stashed || stashed.length === 0) return 0
        const sorted = [...stashed].sort((a, b) => {
            const pa = a.parentId ?? ''
            const pb = b.parentId ?? ''
            if (pa !== pb) return String(pa).localeCompare(String(pb))
            return a.index - b.index
        })
        for (const { step, parentId, index } of sorted) {
            const list = parentId === null ? steps.value : (findStep(parentId)?.children || null)
            if (!list) continue
            const safeIndex = Math.min(index, list.length)
            list.splice(safeIndex, 0, step)
        }
        stashedQuoteStepsWhenPublic.value = []
        updateStepDisplayNames()
        loadQuoteStepsForAllQuoteSteps()
        return sorted.length
    }

    const stashAndClearDataSourceBindings = () => {
        const stashed = []
        forEachStep(steps.value, (step) => {
            if (step.type !== 'http' && step.type !== 'tcp') return
            const cfg = step.config
            if (!cfg || cfg.data_source_id == null) return
            stashed.push({
                stepId: step.id,
                data_source_id: cfg.data_source_id,
                data_source_name: cfg.data_source_name || '',
                data_source_desc: cfg.data_source_desc || '',
            })
            cfg.data_source_id = null
            cfg.data_source_name = ''
            cfg.data_source_desc = ''
        })
        return stashed
    }

    const restoreStashedDataSourceBindings = () => {
        const stashed = stashedDataSourceWhenPublic.value
        if (!stashed || stashed.length === 0) return 0
        for (const { stepId, data_source_id, data_source_name, data_source_desc } of stashed) {
            const cfg = findStep(stepId)?.config
            if (!cfg) continue
            cfg.data_source_id = data_source_id
            cfg.data_source_name = data_source_name
            cfg.data_source_desc = data_source_desc
        }
        stashedDataSourceWhenPublic.value = []
        return stashed.length
    }

    return {
        quoteStepsMap,
        stashedQuoteStepsWhenPublic,
        stashedDataSourceWhenPublic,
        forEachStepWithQuote,
        loadQuoteStepsForStep,
        loadQuoteStepsForAllQuoteSteps,
        loadQuoteStepsForAllQuoteStepsAsync,
        fillQuoteStepsMapFromRawData,
        getQuoteStepsFlattened,
        getQuoteInnerKey,
        getQuoteInnerStep,
        removeAllQuoteSteps,
        collectQuoteStepsWithPosition,
        restoreStashedQuoteSteps,
        stashAndClearDataSourceBindings,
        restoreStashedDataSourceBindings,
    }
}
