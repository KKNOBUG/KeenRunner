import { ref } from 'vue'
import { mapBackendStep, forEachStep } from '@/views/autotest/steps/utils/stepTreeMap'
import { toPositiveCaseId } from '@/views/autotest/steps/utils/prepareCaseExecute'
import {
    isJsonTextEqual,
    parseAndValidateStepTreePayload,
    stripIdentityFieldsForNewCase,
} from '@/views/autotest/steps/utils/stepSourceJson'

/**
 * 源数据 JSON 模式：与步骤树模式互切，JSON 应用/重置
 *
 * @param {object} deps
 * @param {import('vue').Ref<Array>} deps.steps - 前端步骤树
 * @param {import('vue').ComputedRef<string|null>} deps.caseId - 路由 case_id
 * @param {import('vue').ComputedRef<string|null>} deps.caseCode - 路由 case_code
 * @param {import('vue').Ref<{case_id, case_code}>} deps.appliedCaseMeta - 已应用源数据的用例标识
 * @param {import('vue').Ref<Map>} deps.stepExpandStates - 展开状态
 * @param {import('vue').Ref<Array>} deps.selectedKeys - 选中步骤
 * @param {import('vue').Ref} deps.caseInfoPanelRef - CaseInfoPanel 组件 ref
 * @param {object} deps.stepDefinitions - 步骤类型定义表
 * @param {() => string} deps.buildSourceJsonFromMemoryTree - 内存树序列化
 * @param {() => void} deps.updateStepDisplayNames - 刷新展示名
 * @param {() => void} deps.loadQuoteStepsForAllQuoteSteps - 加载引用脚本步骤
 * @param {(msg: string) => void} deps.notifyError - 错误提示
 */
export function useSourceJsonMode({
    steps,
    caseId,
    caseCode,
    appliedCaseMeta,
    stepExpandStates,
    selectedKeys,
    caseInfoPanelRef,
    stepDefinitions,
    buildSourceJsonFromMemoryTree,
    updateStepDisplayNames,
    loadQuoteStepsForAllQuoteSteps,
    notifyError,
}) {
    const treeMode = ref(true)
    const sourceJsonText = ref('')
    const sourceJsonApplyLoading = ref(false)

    const isSourceJsonDirty = () => !isJsonTextEqual(sourceJsonText.value, buildSourceJsonFromMemoryTree())

    const markExpandStatesForMappedSteps = (list) => {
        forEachStep(list, (s) => {
            if (stepDefinitions[s.type]?.allowChildren) {
                stepExpandStates.value.set(s.id, true)
            }
        })
    }

    const applyValidatedSourcePayload = (payload) => {
        const isNewCasePage = toPositiveCaseId(caseId.value) == null && !caseCode.value
        const normalized = isNewCasePage ? stripIdentityFieldsForNewCase(payload) : payload

        const mapped = (normalized.steps || []).map(mapBackendStep).filter(Boolean)
        if ((normalized.steps || []).length && mapped.length !== normalized.steps.length) {
            return { ok: false, message: '部分步骤无法转换为步骤树（请检查 step_type 等字段）' }
        }
        caseInfoPanelRef.value?.hydrateFromCasePayload?.(normalized.case)
        if (isNewCasePage) {
            appliedCaseMeta.value = { case_id: null, case_code: null }
        } else {
            appliedCaseMeta.value = {
                case_id: toPositiveCaseId(caseId.value) ?? toPositiveCaseId(normalized.case?.case_id) ?? null,
                case_code: (caseCode.value || normalized.case?.case_code)
                    ? String(caseCode.value || normalized.case.case_code)
                    : null,
            }
        }
        steps.value = mapped
        stepExpandStates.value = new Map()
        markExpandStatesForMappedSteps(mapped)
        selectedKeys.value = mapped[0]?.id ? [mapped[0].id] : []
        updateStepDisplayNames()
        loadQuoteStepsForAllQuoteSteps()
        sourceJsonText.value = buildSourceJsonFromMemoryTree()
        return { ok: true }
    }

    const tryApplySourceJsonText = (text) => {
        const parsed = parseAndValidateStepTreePayload(text)
        if (!parsed.ok) return parsed
        return applyValidatedSourcePayload(parsed.payload)
    }

    const resetSourceJson = () => {
        sourceJsonText.value = buildSourceJsonFromMemoryTree()
        window.$message?.success?.('已恢复为当前步骤树数据')
    }

    const applySourceJsonFromEditor = () => {
        sourceJsonApplyLoading.value = true
        try {
            const result = tryApplySourceJsonText(sourceJsonText.value)
            if (!result.ok) {
                notifyError(result.message || '应用失败')
                return false
            }
            window.$message?.success?.('已应用到步骤树（尚未落库，请切回步骤树模式后点击保存）')
            return true
        } finally {
            sourceJsonApplyLoading.value = false
        }
    }

    const enterSourceMode = () => {
        sourceJsonText.value = buildSourceJsonFromMemoryTree()
        treeMode.value = false
    }

    const switchToTreeModeDiscardingJson = () => {
        treeMode.value = true
    }

    const handleTreeModeChange = (wantTree) => {
        if (wantTree === treeMode.value) return
        if (!wantTree) {
            enterSourceMode()
            return
        }
        if (!isSourceJsonDirty()) {
            treeMode.value = true
            return
        }
        window.$dialog?.confirm?.({
            title: '切回步骤树模式',
            type: 'warning',
            content: '当前 JSON 相对步骤树有改动。是否将 JSON 应用到步骤树？选「取消」将丢弃 JSON 改动并直接切回。',
            positiveText: '应用并切回',
            negativeText: '不应用，直接切回',
            confirm() {
                const result = tryApplySourceJsonText(sourceJsonText.value)
                if (!result.ok) {
                    notifyError(result.message || '应用失败，请修正 JSON 或点击「重置」')
                    return false
                }
                treeMode.value = true
                window.$message?.success?.('已应用 JSON 并切回步骤树模式')
            },
            cancel() {
                switchToTreeModeDiscardingJson()
            },
        })
    }

    return {
        treeMode,
        sourceJsonText,
        sourceJsonApplyLoading,
        isSourceJsonDirty,
        resetSourceJson,
        applySourceJsonFromEditor,
        handleTreeModeChange,
    }
}
