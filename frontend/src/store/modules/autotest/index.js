/**
 * 自动化测试模块状态
 * - stepTreeCache: 步骤树缓存，按 case_id/case_code 缓存，切换页签时避免重复请求
 * - stepEditorFreshLoadKeys: 关闭页签/丢弃未保存后，下次进入该用例强制走接口
 * - stepEditor: 步骤编辑页脏检测基准
 */
import { defineStore } from 'pinia'

export { useStepEditorStore } from './stepEditor'

function stepTreeCacheKey(caseId, caseCode) {
    return (caseId || caseCode) ? `id:${caseId || ''}_code:${caseCode || ''}` : null
}

export const useAutotestStore = defineStore('autotest', {
    state() {
        return {
            /** 步骤树缓存：key = `id:${caseId}_code:${caseCode}`，value = { rawData, steps } */
            stepTreeCache: {},
            /** 需要强制重新拉取的用例 key 集合（关闭页签或丢弃脏数据时写入） */
            stepEditorFreshLoadKeys: {},
        }
    },
    actions: {
        getStepTreeCache(caseId, caseCode) {
            const key = stepTreeCacheKey(caseId, caseCode)
            return key ? this.stepTreeCache[key] : null
        },
        setStepTreeCache(caseId, caseCode, data) {
            const key = stepTreeCacheKey(caseId, caseCode)
            if (key) this.stepTreeCache[key] = data
        },
        clearStepTreeCache(caseId, caseCode) {
            const key = stepTreeCacheKey(caseId, caseCode)
            if (key) delete this.stepTreeCache[key]
        },
        /** 导入脚本等批量变更后清空全部缓存，避免已打开页签读到旧步骤树 */
        clearAllStepTreeCache() {
            this.stepTreeCache = {}
        },
        markStepEditorFreshLoad(caseId, caseCode) {
            const key = stepTreeCacheKey(caseId, caseCode)
            if (key) this.stepEditorFreshLoadKeys[key] = true
        },
        hasStepEditorFreshLoad(caseId, caseCode) {
            const key = stepTreeCacheKey(caseId, caseCode)
            return !!(key && this.stepEditorFreshLoadKeys[key])
        },
        /** 消费强制刷新标记；返回是否曾标记 */
        consumeStepEditorFreshLoad(caseId, caseCode) {
            const key = stepTreeCacheKey(caseId, caseCode)
            if (!key || !this.stepEditorFreshLoadKeys[key]) return false
            delete this.stepEditorFreshLoadKeys[key]
            return true
        },
    },
})
