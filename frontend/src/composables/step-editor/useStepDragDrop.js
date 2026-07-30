import { ref } from 'vue'

const createInitialDragState = () => ({
    draggingId: null,
    dragOverId: null,
    dragOverParent: null,
    dragOverIndex: null,
    insertPosition: null,
    insertTargetId: null,
})

/** 中线滞回区（px）：光标在目标行中线附近抖动时保持上次方位，避免插入指示线上下跳动 */
const MIDLINE_HYSTERESIS_PX = 4

/**
 * 步骤树拖拽排序
 *
 * @param {object} deps
 * @param {import('vue').Ref<Array>} deps.steps - 前端步骤树
 * @param {object} deps.stepDefinitions - 步骤类型定义表（判断 allowChildren）
 * @param {(id: string) => object|null} deps.findStep - 按 id 查找步骤节点
 */
export function useStepDragDrop({ steps, stepDefinitions, findStep }) {
    const dragState = ref(createInitialDragState())

    let lastMidlineTargetId = null
    let lastMidlinePosition = null

    const resetDragState = () => {
        dragState.value = createInitialDragState()
        lastMidlineTargetId = null
        lastMidlinePosition = null
    }

    /**
     * 仅在值真正变化时写入响应式状态。
     * dragover 事件高频触发（每秒数十次），相同值的写入会导致整树无效重渲染，引发视觉抖动。
     */
    const patchDragState = (patch) => {
        for (const key in patch) {
            if (dragState.value[key] !== patch[key]) {
                dragState.value[key] = patch[key]
            }
        }
    }

    /** 按光标与目标行中线关系计算插入方位，带滞回区防抖 */
    const resolveInsertPosition = (event, targetId) => {
        const rect = event.currentTarget.getBoundingClientRect()
        const offset = event.clientY - (rect.top + rect.height / 2)
        if (
            lastMidlineTargetId === targetId
            && Math.abs(offset) <= MIDLINE_HYSTERESIS_PX
            && lastMidlinePosition
        ) {
            return lastMidlinePosition
        }
        const position = offset < 0 ? 'before' : 'after'
        lastMidlineTargetId = targetId
        lastMidlinePosition = position
        return position
    }

    /**
     * dragleave 在穿越自身嵌套子元素（图标/文本/按钮）时也会触发，
     * 通过 relatedTarget 判断是否真正离开当前元素边界，仅真正离开时才清除状态。
     */
    const isStillInside = (event) => {
        const related = event.relatedTarget
        return !!related && event.currentTarget.contains(related)
    }

    const isMovingWithinSameList = (event) => {
        const related = event.relatedTarget
        return !!related && !!event.currentTarget.parentElement?.contains(related)
    }

    const handleDragStart = (event, stepId, parentId, index) => {
        dragState.value.draggingId = stepId
        dragState.value.dragOverParent = parentId
        dragState.value.dragOverIndex = index
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData('text/plain', stepId)
    }

    const handleDragOver = (event, targetId, targetParentId) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !targetId) return
        const targetStep = findStep(targetId)
        if (!targetStep) return

        const patch = {}
        if (stepDefinitions[targetStep.type]?.allowChildren) {
            patch.dragOverId = targetId
            patch.dragOverParent = targetParentId
        }
        const position = resolveInsertPosition(event, targetId)
        patch.insertTargetId = targetId
        patch.insertPosition = position
        const rootIndex = steps.value.findIndex(s => s.id === targetId)
        patch.dragOverIndex = position === 'before' ? rootIndex : rootIndex + 1
        patchDragState(patch)
    }

    const handleDragOverInChildrenArea = (event, parentId) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !parentId) return

        const parentStep = findStep(parentId)
        if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) return

        const patch = {
            dragOverId: parentId,
            dragOverParent: parentId,
        }
        if (!parentStep.children || parentStep.children.length === 0) {
            patch.insertTargetId = null
            patch.insertPosition = 'before'
            patch.dragOverIndex = 0
        }
        patchDragState(patch)
    }

    const handleDragLeaveInChildrenArea = (event, parentId) => {
        if (isStillInside(event)) return
        if (dragState.value.dragOverId === parentId) {
            patchDragState({
                dragOverId: null,
                dragOverParent: null,
                insertTargetId: null,
                insertPosition: null,
                dragOverIndex: null,
            })
        }
    }

    const handleDragOverOnChild = (event, childId, parentId, childIndex) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !parentId) return

        const parentStep = findStep(parentId)
        if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) return

        const position = resolveInsertPosition(event, childId)
        patchDragState({
            dragOverId: parentId,
            dragOverParent: parentId,
            insertTargetId: childId,
            insertPosition: position,
            dragOverIndex: position === 'before' ? childIndex : childIndex + 1,
        })
    }

    const handleDragLeaveOnChild = (event, childId) => {
        // 移到相邻行/容器内部时保留插入指示（下一次 dragover 会立即覆写），仅真正离开列表时清除
        if (isStillInside(event) || isMovingWithinSameList(event)) return
        if (dragState.value.insertTargetId === childId) {
            patchDragState({ insertTargetId: null, insertPosition: null })
        }
    }

    const handleDragLeave = (event, targetId) => {
        if (isStillInside(event)) return
        const patch = {}
        // 容器高亮归属当前行，离开即清除（移到相邻根行时由下一次 dragover 重新点亮）
        if (dragState.value.dragOverId === targetId) {
            patch.dragOverId = null
            patch.dragOverParent = null
        }
        if (!isMovingWithinSameList(event) && dragState.value.insertTargetId === targetId) {
            patch.insertTargetId = null
            patch.insertPosition = null
        }
        patchDragState(patch)
    }

    const removeFromList = (list, id) => {
        const idx = list.findIndex(item => item.id === id)
        if (idx !== -1) {
            list.splice(idx, 1)
            return true
        }
        for (const item of list) {
            if (item.children && item.children.length) {
                if (removeFromList(item.children, id)) return true
            }
        }
        return false
    }

    const handleDrop = (event, targetId, targetParentId, targetIndex, branchIndex = null) => {
        event.preventDefault()
        const draggingId = dragState.value.draggingId
        if (!draggingId || draggingId === targetId) {
            resetDragState()
            return
        }

        const draggingStep = findStep(draggingId)
        if (!draggingStep) {
            resetDragState()
            return
        }

        // 条件分支父级：维护被拖拽步骤的 branch_index 归属；非条件分支父级/根级则清理残留的 branch_index
        const applyBranchIndex = (parentStep, insertIndex, explicitBranchIndex) => {
            if (!parentStep || parentStep.type !== 'if') {
                delete draggingStep.branch_index
                return
            }
            if (explicitBranchIndex != null) {
                draggingStep.branch_index = explicitBranchIndex
                return
            }
            const after = parentStep.children[insertIndex + 1]
            const before = parentStep.children[insertIndex - 1]
            if (dragState.value.insertPosition === 'before' && after && after.id !== draggingId) {
                draggingStep.branch_index = after.branch_index ?? 0
            } else if (before && before.id !== draggingId) {
                draggingStep.branch_index = before.branch_index ?? 0
            } else if (after && after.id !== draggingId) {
                draggingStep.branch_index = after.branch_index ?? 0
            } else {
                draggingStep.branch_index = 0
            }
        }

        removeFromList(steps.value, draggingId)

        if (dragState.value.dragOverId) {
            const parentStep = findStep(dragState.value.dragOverId)
            if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
                if (!parentStep.children) parentStep.children = []
                const insertIndex = branchIndex != null && targetIndex != null
                    ? targetIndex
                    : (dragState.value.dragOverIndex !== null
                        ? dragState.value.dragOverIndex
                        : parentStep.children.length)
                parentStep.children.splice(insertIndex, 0, draggingStep)
                applyBranchIndex(parentStep, insertIndex, branchIndex)
                resetDragState()
                return
            }
        }

        const targetStep = findStep(targetId)
        if (targetStep && stepDefinitions[targetStep.type]?.allowChildren && targetId === targetParentId) {
            if (!targetStep.children) targetStep.children = []
            targetStep.children.push(draggingStep)
            applyBranchIndex(targetStep, targetStep.children.length - 1, branchIndex)
            resetDragState()
            return
        }

        if (targetParentId) {
            const parentStep = findStep(targetParentId)
            if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
                if (!parentStep.children) parentStep.children = []
                const insertIndex = targetIndex !== null ? targetIndex : parentStep.children.length
                parentStep.children.splice(insertIndex, 0, draggingStep)
                applyBranchIndex(parentStep, insertIndex, branchIndex)
                resetDragState()
                return
            }
        }

        delete draggingStep.branch_index
        const insertIndex = targetIndex !== null ? targetIndex : steps.value.length
        steps.value.splice(insertIndex, 0, draggingStep)
        resetDragState()
    }

    return {
        dragState,
        handleDragStart,
        handleDragOver,
        handleDragLeave,
        handleDragOverInChildrenArea,
        handleDragLeaveInChildrenArea,
        handleDragOverOnChild,
        handleDragLeaveOnChild,
        handleDrop,
    }
}
