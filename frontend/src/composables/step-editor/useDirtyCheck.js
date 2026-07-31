import { computed } from 'vue'
import { useStepEditorStore } from '@/store'

/**
 * 步骤编辑页脏检测
 *
 * 原理：将当前步骤树序列化为 JSON 快照，与 Store 中保存/加载时的基准快照对比。
 * - 保存成功 → markSaved()
 * - 加载完成 → markLoaded()
 * - 用户编辑 → 步骤树变化 → currentSnapshot 变化 → isDirty = true
 * - 离开页面 → confirmIfDirty() 弹窗拦截
 *
 * @param {() => string} getSnapshot - 返回当前步骤树序列化 JSON 的函数
 */
export function useDirtyCheck(getSnapshot) {
    const store = useStepEditorStore()

    const currentSnapshot = computed(() => getSnapshot())

    const isDirty = computed(() => {
        if (!store.hasDirtyBaseline) return false
        return store.lastSavedSnapshot !== currentSnapshot.value
    })

    const markSaved = () => {
        store.markSaved(currentSnapshot.value)
    }

    const markLoaded = () => {
        store.markLoaded(currentSnapshot.value)
    }

    const reset = () => {
        store.resetDirty()
    }

    /**
     * 路由离开前调用：若脏则弹窗确认，返回 Promise<boolean>
     * 用法：onBeforeRouteLeave(() => confirmIfDirty())
     */
    const confirmIfDirty = () => {
        if (!isDirty.value) return true
        return new Promise((resolve) => {
            window.$dialog?.confirm?.({
                title: '提示',
                type: 'warning',
                content: '步骤树有未保存的修改，确定要离开吗？',
                positiveText: '离开',
                negativeText: '留下',
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            }) ?? resolve(true)
        })
    }

    return { isDirty, currentSnapshot, markSaved, markLoaded, reset, confirmIfDirty }
}
