import { ref } from 'vue'

const createInitialDragState = () => ({
    draggingId: null,
    dragOverId: null,
    dragOverParent: null,
    dragOverIndex: null,
    insertPosition: null,
    insertTargetId: null,
})

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

    const resetDragState = () => {
        dragState.value = createInitialDragState()
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

        if (dragState.value.draggingId && targetId) {
            const targetStep = findStep(targetId)
            if (targetStep && stepDefinitions[targetStep.type]?.allowChildren) {
                dragState.value.dragOverId = targetId
                dragState.value.dragOverParent = targetParentId
            }
        }
    }

    const handleDragOverInChildrenArea = (event, parentId) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !parentId) return

        const parentStep = findStep(parentId)
        if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) return

        dragState.value.dragOverId = parentId
        dragState.value.dragOverParent = parentId

        if (!parentStep.children || parentStep.children.length === 0) {
            dragState.value.insertTargetId = null
            dragState.value.insertPosition = 'before'
            dragState.value.dragOverIndex = 0
        }
    }

    const handleDragLeaveInChildrenArea = (event, parentId) => {
        if (dragState.value.dragOverId === parentId) {
            setTimeout(() => {
                if (dragState.value.dragOverId === parentId) {
                    dragState.value.insertTargetId = null
                    dragState.value.insertPosition = null
                    dragState.value.dragOverIndex = null
                }
            }, 50)
        }
    }

    const handleDragOverOnChild = (event, childId, parentId, childIndex) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !parentId) return

        const parentStep = findStep(parentId)
        if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) return

        dragState.value.dragOverId = parentId
        dragState.value.dragOverParent = parentId

        const rect = event.currentTarget.getBoundingClientRect()
        const stepCenterY = rect.top + rect.height / 2
        const position = event.clientY < stepCenterY ? 'before' : 'after'

        dragState.value.insertTargetId = childId
        dragState.value.insertPosition = position
        dragState.value.dragOverIndex = position === 'before' ? childIndex : childIndex + 1
    }

    const handleDragLeaveOnChild = (event, childId) => {
        if (dragState.value.insertTargetId === childId) {
            setTimeout(() => {
                if (dragState.value.insertTargetId === childId) {
                    dragState.value.insertTargetId = null
                    dragState.value.insertPosition = null
                }
            }, 50)
        }
    }

    const handleDragLeave = (event, targetId) => {
        if (dragState.value.dragOverId === targetId) {
            setTimeout(() => {
                if (dragState.value.dragOverId === targetId) {
                    dragState.value.dragOverId = null
                    dragState.value.insertTargetId = null
                    dragState.value.insertPosition = null
                    dragState.value.dragOverIndex = null
                }
            }, 50)
        }
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

    const handleDrop = (event, targetId, targetParentId, targetIndex) => {
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

        removeFromList(steps.value, draggingId)

        if (dragState.value.dragOverId) {
            const parentStep = findStep(dragState.value.dragOverId)
            if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
                if (!parentStep.children) parentStep.children = []
                const insertIndex = dragState.value.dragOverIndex !== null
                    ? dragState.value.dragOverIndex
                    : parentStep.children.length
                parentStep.children.splice(insertIndex, 0, draggingStep)
                resetDragState()
                return
            }
        }

        const targetStep = findStep(targetId)
        if (targetStep && stepDefinitions[targetStep.type]?.allowChildren && targetId === targetParentId) {
            if (!targetStep.children) targetStep.children = []
            targetStep.children.push(draggingStep)
            resetDragState()
            return
        }

        if (targetParentId) {
            const parentStep = findStep(targetParentId)
            if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
                if (!parentStep.children) parentStep.children = []
                const insertIndex = targetIndex !== null ? targetIndex : parentStep.children.length
                parentStep.children.splice(insertIndex, 0, draggingStep)
                resetDragState()
                return
            }
        }

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
