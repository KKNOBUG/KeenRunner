import { defineStore } from 'pinia'

export const useStepEditorStore = defineStore('stepEditor', {
    state() {
        return {
            /** 脏检测基准：上次保存/加载时的步骤树序列化快照（JSON string），null 表示尚未建立基准 */
            lastSavedSnapshot: null,
        }
    },
    getters: {
        /** 是否已建立脏检测基准（加载完成或保存成功后才为 true） */
        hasDirtyBaseline(state) {
            return state.lastSavedSnapshot !== null
        },
    },
    actions: {
        /** 保存成功后调用：以当前快照作为新基准 */
        markSaved(snapshot) {
            this.lastSavedSnapshot = snapshot
        },
        /** 加载完成后调用：以当前快照作为初始基准 */
        markLoaded(snapshot) {
            this.lastSavedSnapshot = snapshot
        },
        /** 重置脏检测（离开页面/切换用例时） */
        resetDirty() {
            this.lastSavedSnapshot = null
        },
    },
})
