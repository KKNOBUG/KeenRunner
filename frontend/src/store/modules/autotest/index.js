/**
 * 自动化测试模块状态
 * - stepTreeCache: 步骤树缓存，按 case_id/case_code 缓存，切换页签时避免重复请求
 */
import { defineStore } from 'pinia'

export const useAutotestStore = defineStore('autotest', {
    state() {
        return {
            /** 步骤树缓存：key = `id:${caseId}_code:${caseCode}`，value = { rawData, steps } */
            stepTreeCache: {},
        }
    },
    actions: {
        getStepTreeCache(caseId, caseCode) {
            const key = (caseId || caseCode) ? `id:${caseId || ''}_code:${caseCode || ''}` : null
            return key ? this.stepTreeCache[key] : null
        },
        setStepTreeCache(caseId, caseCode, data) {
            const key = (caseId || caseCode) ? `id:${caseId || ''}_code:${caseCode || ''}` : null
            if (key) this.stepTreeCache[key] = data
        },
        clearStepTreeCache(caseId, caseCode) {
            const key = (caseId || caseCode) ? `id:${caseId || ''}_code:${caseCode || ''}` : null
            if (key) delete this.stepTreeCache[key]
        },
    },
})
