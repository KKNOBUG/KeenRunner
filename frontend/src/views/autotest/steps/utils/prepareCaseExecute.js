/**
 * 已保存用例「执行」：拉取步骤树、加载引用脚本、打开 ExecConfigModal（与 steps/index handleRun 一致）
 */
import api from '@/api'
import { forEachStep, mapBackendStep } from './stepTreeMap'

export function toPositiveCaseId(v) {
  if (v == null || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n) || n < 1) return null
  return Math.floor(n)
}

export function resolveCaseIdFromSteps(steps, fallbackCaseId) {
  const fromParam = toPositiveCaseId(fallbackCaseId)
  if (fromParam != null) return fromParam
  let found = null
  const walk = (arr) => {
    if (!Array.isArray(arr) || found != null) return
    for (const s of arr) {
      const cid = s?.original?.case_id ?? s?.case_id
      const n = toPositiveCaseId(cid)
      if (n != null) {
        found = n
        return
      }
      walk(s.children)
    }
  }
  walk(steps)
  return found
}

async function loadQuoteStepsForStep(step, quoteStepsMap) {
  if (step.type !== 'quote' || !step.config?.quote_case_id) {
    quoteStepsMap[step.id] = []
    return
  }
  try {
    const res = await api.getAutoTestStepTree({ case_id: step.config.quote_case_id })
    const data = Array.isArray(res?.data) ? res.data : []
    quoteStepsMap[step.id] = data.map(mapBackendStep).filter(Boolean)
  } catch (e) {
    console.error('加载引用脚本步骤失败', e)
    quoteStepsMap[step.id] = []
  }
}

export async function loadQuoteStepsForList(list, quoteStepsMap) {
  const quoteSteps = []
  forEachStep(list, (s) => {
    if (s?.type === 'quote') quoteSteps.push(s)
  })
  if (!quoteSteps.length) return
  await Promise.all(quoteSteps.map((s) => loadQuoteStepsForStep(s, quoteStepsMap)))
}

/**
 * @param {import('vue').Ref} execConfigModalRef ExecConfigModal 组件 ref
 * @param {{ caseId?: *, caseCode?: string, projectOptions?: Array, executeType?: string }} options
 * @param executeType 后端 execute_type：步骤编辑页「异步执行」；用例列表「定时执行」
 */
export async function openSavedCaseExecModal(
    execConfigModalRef,
    { caseId, caseCode, projectOptions = [], executeType = '定时执行' },
) {
  const params = {}
  if (caseId) params.case_id = caseId
  if (caseCode) params.case_code = caseCode

  const res = await api.getAutoTestStepTree(params)
  const data = Array.isArray(res?.data) ? res.data : []
  const execSourceSteps = data.map(mapBackendStep).filter(Boolean)
  const quoteStepsMap = {}
  await loadQuoteStepsForList(execSourceSteps, quoteStepsMap)

  const resolveCaseId = () => resolveCaseIdFromSteps(execSourceSteps, caseId)
  const numericCaseId = resolveCaseId()
  if (numericCaseId == null) {
    window.$message?.warning?.('缺少用例 ID（case_id），无法执行，请先保存用例或从用例管理进入')
    return
  }

  await execConfigModalRef.value?.openRun({
    sourceSteps: execSourceSteps,
    quoteStepsMap: { ...quoteStepsMap },
    caseId: numericCaseId,
    projectOptions,
    resolveCaseId,
    executeType,
  })
}
