import { ref } from 'vue'
import { openSavedCaseExecModal } from '@/views/autotest/steps/utils/prepareCaseExecute'

/**
 * 与步骤编辑页 handleRun 一致：加载已保存步骤树并打开 ExecConfigModal
 * @param {import('vue').Ref} execConfigModalRef
 * @param {import('vue').Ref<boolean>} [runLoadingRef] 与 ExecConfigModal v-model:run-loading 同步
 */
export function useAutotestSavedCaseRun(execConfigModalRef, runLoadingRef) {
  const internalLoading = ref(false)
  const loading = runLoadingRef || internalLoading

  const runSavedCase = async ({ caseId, caseCode, projectOptions, executeType = '定时执行' }) => {
    if (!caseId && !caseCode) {
      window.$message?.warning?.('缺少用例标识，无法执行')
      return
    }
    loading.value = true
    try {
      await openSavedCaseExecModal(execConfigModalRef, {
        caseId,
        caseCode,
        projectOptions,
        executeType,
      })
    } catch (e) {
      console.error('加载已保存步骤树失败', e)
      window.$message?.error?.(e?.message || '加载步骤树失败')
    } finally {
      loading.value = false
    }
  }

  return { runLoading: loading, runSavedCase }
}
