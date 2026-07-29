import { reactive, watch, nextTick } from 'vue'

/**
 * 步骤子编辑器通用表单生命周期
 *
 * 统一 9 个子编辑器（wait/if/loop/user_variables/code/database/redis/http/tcp）重复的：
 * - reactive form + defaults 工厂（每次重初始化拿新引用，避免数组/对象共享）
 * - watch(step.id) 切换步骤时重初始化（isExternalUpdate 抑制回写循环，防止输入丢字）
 * - 防抖/即时 emit('update:config', buildConfig(form))
 *
 * quote 为只读展示组件，不适用本 composable。
 *
 * @param {object} options
 * @param {object} options.props            - 组件 props（须含 config / step / readonly）
 * @param {function} options.emit           - defineEmits 返回的 emit
 * @param {function} options.defaults       - () => object，表单默认值工厂
 * @param {function} options.hydrate        - (props) => object，从 props 合并出表单值（config 优先、original 兜底）
 * @param {function} options.buildConfig    - (form) => object，序列化表单为 emit 的 config
 * @param {function} [options.watchFields]  - (form) => any[]，指定监听字段；省略则整体 deep watch
 * @param {number} [options.debounceMs=0]   - emit 防抖毫秒数，0 表示立即
 * @returns {{ form: object, isExternalUpdate: () => boolean, syncFromExternal: (fn: () => void) => void }}
 */
export function useStepEditorForm({
    props,
    emit,
    defaults,
    hydrate,
    buildConfig,
    watchFields,
    debounceMs = 0,
}) {
    const form = reactive(defaults())
    let isExternalUpdate = false
    let emitTimer = null

    watch(
        () => props.step?.id,
        () => {
            isExternalUpdate = true
            Object.assign(form, defaults(), hydrate(props))
            nextTick(() => { isExternalUpdate = false })
        },
        { immediate: true },
    )

    const source = watchFields ? () => watchFields(form) : () => form
    watch(source, () => {
        if (isExternalUpdate || props.readonly) return
        if (debounceMs > 0) {
            if (emitTimer) clearTimeout(emitTimer)
            emitTimer = setTimeout(() => emit('update:config', buildConfig(form)), debounceMs)
        } else {
            emit('update:config', buildConfig(form))
        }
    }, { deep: true })

    /**
     * 在外部同步标志下执行表单写入（如父级改写 props.config 后回填表单），
     * 写入不会触发 emit 回写循环。
     */
    const syncFromExternal = (fn) => {
        isExternalUpdate = true
        fn()
        nextTick(() => { isExternalUpdate = false })
    }

    return {
        form,
        isExternalUpdate: () => isExternalUpdate,
        syncFromExternal,
    }
}
