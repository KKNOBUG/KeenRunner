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

/** 根级容器行三区判定的边缘占比：上/下 30% 为根级前/后插入，中间 40% 为放入容器内部 */
const CONTAINER_EDGE_RATIO = 0.3

/** 行头高度上限（px）：容器行的 rect 包含展开的子区域，三区判定只针对行头 */
const ROW_HEADER_MAX_PX = 32

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
    let lastZoneTargetId = null
    let lastZone = null

    const resetDragState = () => {
        dragState.value = createInitialDragState()
        lastMidlineTargetId = null
        lastMidlinePosition = null
        lastZoneTargetId = null
        lastZone = null
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
     * 根级容器行的三区判定：光标位于行头上/下边缘时按根级前/后插入，
     * 位于中部时放入容器内部；边界带滞回，避免区域间来回抖动。
     * 注意 rect 含展开子区域（子区域事件已 stop 不会到达），故按行头高度上限计算。
     */
    const resolveContainerZone = (event, targetId) => {
        const rect = event.currentTarget.getBoundingClientRect()
        const headerHeight = Math.min(rect.height, ROW_HEADER_MAX_PX)
        const y = event.clientY - rect.top
        const upper = headerHeight * CONTAINER_EDGE_RATIO
        const lower = headerHeight * (1 - CONTAINER_EDGE_RATIO)
        if (lastZoneTargetId === targetId && lastZone) {
            if (lastZone === 'before' && y <= upper + MIDLINE_HYSTERESIS_PX) return 'before'
            if (lastZone === 'after' && y >= lower - MIDLINE_HYSTERESIS_PX) return 'after'
            if (lastZone === 'into' && y > upper - MIDLINE_HYSTERESIS_PX && y < lower + MIDLINE_HYSTERESIS_PX) return 'into'
        }
        const zone = y <= upper ? 'before' : y >= lower ? 'after' : 'into'
        lastZoneTargetId = targetId
        lastZone = zone
        return zone
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
        // 兜底：拖拽被 ESC 取消或未落在任何目标时，dragend 复位高亮/指示线状态
        document.addEventListener('dragend', resetDragState, { once: true })
    }

    const handleDragOver = (event, targetId, targetParentId) => {
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'

        if (!dragState.value.draggingId || !targetId) return
        const targetStep = findStep(targetId)
        if (!targetStep) return

        const rootIndex = steps.value.findIndex(s => s.id === targetId)

        // 根级容器行（loop/if）：按光标区域区分「放入容器内部」与「根级前/后插入」，
        // 否则容器会吞掉所有根级落点，导致树中仅有容器步骤时无法将内部步骤拖出到根目录
        if (stepDefinitions[targetStep.type]?.allowChildren) {
            const zone = resolveContainerZone(event, targetId)
            if (zone === 'into') {
                patchDragState({
                    dragOverId: targetId,
                    dragOverParent: targetParentId,
                    insertTargetId: null,
                    insertPosition: null,
                    dragOverIndex: null,
                })
                return
            }
            patchDragState({
                dragOverId: null,
                dragOverParent: null,
                insertTargetId: targetId,
                insertPosition: zone,
                dragOverIndex: zone === 'before' ? rootIndex : rootIndex + 1,
            })
            return
        }

        const position = resolveInsertPosition(event, targetId)
        patchDragState({
            dragOverId: null,
            dragOverParent: null,
            insertTargetId: targetId,
            insertPosition: position,
            dragOverIndex: position === 'before' ? rootIndex : rootIndex + 1,
        })
    }

    /** 根容器空白区域（行下方/间隙）作为根级末尾的拖放目标，保证任何树形都能拖回根目录 */
    const handleDragOverOnRootSpace = (event) => {
        if (event.target !== event.currentTarget || !dragState.value.draggingId) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'
        const last = steps.value[steps.value.length - 1]
        patchDragState({
            dragOverId: null,
            dragOverParent: null,
            insertTargetId: last ? last.id : null,
            insertPosition: 'after',
            dragOverIndex: steps.value.length,
        })
    }

    const handleDragLeaveOnRootSpace = (event) => {
        if (event.target !== event.currentTarget || isStillInside(event)) return
        patchDragState({ insertTargetId: null, insertPosition: null, dragOverIndex: null })
    }

    const handleDropOnRootSpace = (event) => {
        if (event.target !== event.currentTarget) return
        handleDrop(event, null, null, steps.value.length)
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

    /** 定位节点所在数组与下标，用于移除后的插入索引修正 */
    const locateNode = (list, id) => {
        const idx = list.findIndex(item => item.id === id)
        if (idx !== -1) return { list, index: idx }
        for (const item of list) {
            if (item.children && item.children.length) {
                const found = locateNode(item.children, id)
                if (found) return found
            }
        }
        return null
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

        // 先记录来源位置：若拖拽项从同一数组中较靠前的位置移除，插入下标需前移一位
        const source = locateNode(steps.value, draggingId)
        removeFromList(steps.value, draggingId)
        const adjustIndex = (targetList, insertIndex) => (
            source && source.list === targetList && source.index < insertIndex
                ? insertIndex - 1
                : insertIndex
        )

        if (dragState.value.dragOverId) {
            const parentStep = findStep(dragState.value.dragOverId)
            if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
                if (!parentStep.children) parentStep.children = []
                const insertIndex = branchIndex != null && targetIndex != null
                    ? targetIndex
                    : (dragState.value.dragOverIndex !== null
                        ? dragState.value.dragOverIndex
                        : parentStep.children.length)
                const adjustedIndex = adjustIndex(parentStep.children, insertIndex)
                parentStep.children.splice(adjustedIndex, 0, draggingStep)
                applyBranchIndex(parentStep, adjustedIndex, branchIndex)
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
                const adjustedIndex = adjustIndex(parentStep.children, insertIndex)
                parentStep.children.splice(adjustedIndex, 0, draggingStep)
                applyBranchIndex(parentStep, adjustedIndex, branchIndex)
                resetDragState()
                return
            }
        }

        // 根级插入：优先使用 dragover 阶段按 before/after 算好的下标（targetIndex 仅为行自身下标，不含方位）
        delete draggingStep.branch_index
        const rootInsertIndex = dragState.value.dragOverIndex !== null
            ? dragState.value.dragOverIndex
            : (targetIndex !== null ? targetIndex : steps.value.length)
        steps.value.splice(adjustIndex(steps.value, rootInsertIndex), 0, draggingStep)
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
        handleDragOverOnRootSpace,
        handleDragLeaveOnRootSpace,
        handleDropOnRootSpace,
        handleDrop,
    }
}
