<template>
  <div
      v-if="stepDefinitions[step.type]?.allowChildren && isStepExpanded(step.id)"
      @dragover.prevent.stop="handleDragOverInChildrenArea($event, step.id)"
      @dragleave.stop="handleDragLeaveInChildrenArea($event, step.id)"
  >
    <!-- 条件分支: 按分支分组渲染 -->
    <template v-if="step.type === 'if' && step.config?.branch_items?.length">
      <div
          v-for="(branch, bi) in step.config.branch_items"
          :key="'branch-' + bi"
          class="branch-group"
          :class="`branch-depth-${Math.min(depth, 3)}`"
      >
        <div class="branch-group-header">
          <span
              class="branch-collapse-btn"
              :title="isBranchCollapsed(step.id, bi) ? '展开该分支' : '折叠该分支'"
              @click.stop="toggleBranchCollapse(step.id, bi, $event)"
          >
            <TheIcon
                :icon="isBranchCollapsed(step.id, bi) ? 'gravity-ui:chevron-down' : 'gravity-ui:chevron-up'"
                :size="12"
            />
          </span>
          <span class="branch-tag" :class="`tag-${branch.branch_type}`">
            {{ branch.branch_type.toUpperCase() }}
          </span>
          <span
              v-if="branch.branch_type !== 'else' && branch.branch_conditions"
              class="branch-condition-summary"
              :title="`${branch.branch_conditions.condition_expr} ${branch.branch_conditions.condition_compare} ${branch.branch_conditions.condition_value}`"
          >
            {{ branch.branch_conditions.condition_expr }} {{ branch.branch_conditions.condition_compare }} {{ branch.branch_conditions.condition_value }}
          </span>
          <span v-if="branch.branch_type === 'else'" class="branch-else-hint">上述条件均未命中时执行</span>
          <span v-if="isBranchCollapsed(step.id, bi)" class="branch-collapsed-count">
            {{ getBranchChildren(bi).length }} 个步骤
          </span>
        </div>
        <div v-if="!isBranchCollapsed(step.id, bi)" class="branch-group-body">
          <template v-for="(child, childIndex) in getBranchChildren(bi)" :key="child.id">
            <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'before')"></div>
            <div
                class="step-item"
                :class="{
                  'is-selected': selectedKeys.includes(child.id),
                  'is-skipped': !!child.step_is_skipped,
                  'is-skip-inherited': isStepSkipInherited(child.id),
                  'is-drag-target': dragState.draggingId && stepDefinitions[child.type]?.allowChildren
                }"
                draggable="true"
                @click.stop="handleSelect([child.id])"
                @dragstart.stop="handleDragStart($event, child.id, step.id, getGlobalChildIndex(child.id))"
                @dragover.prevent.stop="handleDragOverOnChild($event, child.id, step.id, getGlobalChildIndex(child.id))"
                @dragleave.stop="handleDragLeaveOnChild($event, child.id)"
                @drop.stop="handleDrop($event, child.id, step.id, getGlobalChildIndex(child.id))"
            >
              <div class="step-item-child" :class="{ 'has-children-guide': stepDefinitions[child.type]?.allowChildren && isStepExpanded(child.id) }">
                <span class="step-name" :title="child.name">
                  <TheIcon :icon="getStepIcon(child.type)" :size="16" class="step-icon" :class="getStepIconClass(child.type)"/>
                  <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
                  <span class="step-actions">
                    <span class="step-number">#{{ getStepNumber(child.id) }}</span>
                    <n-button text size="tiny" class="action-btn"
                        :title="child.step_is_skipped ? '取消注释(恢复执行)' : '注释(跳过执行)'"
                        @click.stop="toggleSkipStep(child.id, $event)">
                      <template #icon><TheIcon :icon="child.step_is_skipped ? 'gravity-ui:eye' : 'gravity-ui:eye-slash'" :size="14"/></template>
                    </n-button>
                    <n-button v-if="stepDefinitions[child.type]?.allowChildren" text size="tiny" class="action-btn"
                        @click.stop="toggleStepExpand(child.id, $event)">
                      <template #icon><TheIcon :icon="isStepExpanded(child.id) ? 'gravity-ui:chevron-up' : 'gravity-ui:chevron-down'" :size="14"/></template>
                    </n-button>
                    <n-button text size="tiny" class="action-btn" title="复制当前步骤" @click.stop="handleCopyStep(child.id)">
                      <template #icon><TheIcon icon="gravity-ui:square-article" :size="14"/></template>
                    </n-button>
                    <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
                      <template #trigger>
                        <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                          <template #icon><TheIcon icon="material-symbols:delete" :size="14"/></template>
                        </n-button>
                      </template>
                      确认删除该步骤?
                    </n-popconfirm>
                  </span>
                </span>
                <RecursiveStepChildren v-if="stepDefinitions[child.type]?.allowChildren" :step="child" :depth="depth + 1"/>
              </div>
            </div>
            <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'after')"></div>
          </template>
          <!-- 分支为空时的拖拽区域 -->
          <div
              v-if="getBranchChildren(bi).length === 0"
              class="step-drop-zone branch-drop-zone"
              :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
              @drop.stop="handleDrop($event, step.id, step.id, getBranchInsertIndex(bi), bi)"
          >
            <div class="step-drop-zone-hint">拖拽步骤到此分支</div>
          </div>
          <div class="step-add-btn">
            <AddStepPopover :is-public-family-case="isPublicFamilyCase" @select="(key) => handleAddStepToBranch(key, step.id, bi)"/>
          </div>
        </div>
      </div>
    </template>

    <!-- 非条件分支(LOOP等): 原有平铺渲染 -->
    <template v-else>
      <div
          v-if="!step.children || step.children.length === 0"
          class="step-drop-zone"
          :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
          @drop.stop="handleDrop($event, step.id, step.id, 0)"
      >
        <div class="step-drop-zone-hint">拖拽步骤到这里</div>
      </div>

      <template v-for="(child, childIndex) in (step.children || [])" :key="child.id">
        <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'before')"></div>
        <div
            class="step-item"
            :class="{
              'is-selected': selectedKeys.includes(child.id),
              'is-skipped': !!child.step_is_skipped,
              'is-skip-inherited': isStepSkipInherited(child.id),
              'is-drag-target': dragState.draggingId && stepDefinitions[child.type]?.allowChildren
            }"
            draggable="true"
            @click.stop="handleSelect([child.id])"
            @dragstart.stop="handleDragStart($event, child.id, step.id, childIndex)"
            @dragover.prevent.stop="handleDragOverOnChild($event, child.id, step.id, childIndex)"
            @dragleave.stop="handleDragLeaveOnChild($event, child.id)"
            @drop.stop="handleDrop($event, child.id, step.id, childIndex)"
        >
          <div class="step-item-child" :class="{ 'has-children-guide': stepDefinitions[child.type]?.allowChildren && isStepExpanded(child.id) }">
            <span class="step-name" :title="child.name">
              <TheIcon :icon="getStepIcon(child.type)" :size="16" class="step-icon" :class="getStepIconClass(child.type)"/>
              <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
              <span class="step-actions">
                <span class="step-number">#{{ getStepNumber(child.id) }}</span>
                <n-button text size="tiny" class="action-btn"
                    :title="child.step_is_skipped ? '取消注释(恢复执行)' : '注释(跳过执行)'"
                    @click.stop="toggleSkipStep(child.id, $event)">
                  <template #icon><TheIcon :icon="child.step_is_skipped ? 'gravity-ui:eye' : 'gravity-ui:eye-slash'" :size="14"/></template>
                </n-button>
                <n-button v-if="stepDefinitions[child.type]?.allowChildren" text size="tiny" class="action-btn"
                    @click.stop="toggleStepExpand(child.id, $event)">
                  <template #icon><TheIcon :icon="isStepExpanded(child.id) ? 'gravity-ui:chevron-up' : 'gravity-ui:chevron-down'" :size="14"/></template>
                </n-button>
                <n-button text size="tiny" class="action-btn" title="复制当前步骤" @click.stop="handleCopyStep(child.id)">
                  <template #icon><TheIcon icon="gravity-ui:square-article" :size="14"/></template>
                </n-button>
                <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
                  <template #trigger>
                    <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                      <template #icon><TheIcon icon="material-symbols:delete" :size="14"/></template>
                    </n-button>
                  </template>
                  确认删除该步骤?
                </n-popconfirm>
              </span>
            </span>
            <RecursiveStepChildren v-if="stepDefinitions[child.type]?.allowChildren" :step="child" :depth="depth + 1"/>
          </div>
        </div>
        <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'after')"></div>
      </template>
      <div class="step-insert-indicator" :style="insertIndicatorStyle(null, 'after', true)"></div>
      <div class="step-add-btn">
        <AddStepPopover :is-public-family-case="isPublicFamilyCase" @select="(key) => handleAddStep(key, step.id)"/>
      </div>
    </template>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { NButton, NPopconfirm } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import AddStepPopover from './AddStepPopover.vue'

defineOptions({ name: 'RecursiveStepChildren' })

const props = defineProps({
  step: { type: Object, required: true },
  /** 当前子树层级（根级调用为 1，每递归一层 +1），用于分支组的深度样式 */
  depth: { type: Number, default: 1 }
})

const {
  stepDefinitions,
  isStepExpanded,
  toggleStepExpand,
  isBranchCollapsed,
  toggleBranchCollapse,
  selectedKeys,
  getStepIcon,
  getStepIconClass,
  getStepDisplayName,
  getStepNumber,
  handleSelect,
  handleDragStart,
  handleDragOverInChildrenArea,
  handleDragLeaveInChildrenArea,
  handleDragOverOnChild,
  handleDragLeaveOnChild,
  handleDrop,
  handleCopyStep,
  handleDeleteStep,
  toggleSkipStep,
  isStepSkipInherited,
  isPublicFamilyCase,
  handleAddStep,
  handleAddStepToBranch,
  dragState,
} = inject('stepTreeContext')

const getBranchChildren = (branchIndex) => {
  return (props.step.children || []).filter(c => (c.branch_index ?? 0) === branchIndex)
}

const getGlobalChildIndex = (childId) => {
  return (props.step.children || []).findIndex(c => c.id === childId)
}

const getBranchInsertIndex = (branchIndex) => {
  const children = props.step.children || []
  const branchChildren = children.filter(c => (c.branch_index ?? 0) === branchIndex)
  if (branchChildren.length === 0) {
    const nextBranchChildren = children.filter(c => (c.branch_index ?? 0) > branchIndex)
    if (nextBranchChildren.length > 0) {
      return children.indexOf(nextBranchChildren[0])
    }
    return children.length
  }
  return children.indexOf(branchChildren[branchChildren.length - 1]) + 1
}

const insertIndicatorStyle = (targetId, position, requireChildren = false) => {
  const ds = dragState.value
  const show = ds.draggingId
      && ds.dragOverId === props.step.id
      && ds.insertTargetId === targetId
      && ds.insertPosition === position
      && (!requireChildren || (props.step.children && props.step.children.length > 0))
  return { display: show ? 'block' : 'none' }
}
</script>

<style scoped>
/* 分支组框：外左边线对齐 16px 缩进网格，组内行因框体自然内凹（容器语义）；
   上下 margin 3px 与行 padding 3px 组成 6px 等距节奏（相邻组框 margin 折叠为 3px，形成紧凑堆叠） */
.branch-group {
  margin: 3px 0;
  border-radius: 8px;
  border: 1px dashed var(--n-border-color);
  overflow: hidden;
}

/* 组头：背景与步骤行名称药丸共用同一浅灰 token，内容左边线与组内行对齐 */
.branch-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: color-mix(in srgb, var(--n-border-color) 35%, transparent);
  font-size: 12px;
}

/* 深度色阶：组头背景随层级加深渐次变淡（后退感），降低深层嵌套的视觉噪音 */
.branch-depth-2 .branch-group-header {
  background: color-mix(in srgb, var(--n-border-color) 28%, transparent);
}

.branch-depth-3 .branch-group-header {
  background: color-mix(in srgb, var(--n-border-color) 22%, transparent);
}

/* 深度 ≥3：组框降级为左侧引导线，避免"盒子套盒子"的视觉堆积（层级归属由缩进参考线承担） */
.branch-depth-3.branch-group {
  border: none;
  border-left: 1px solid color-mix(in srgb, var(--n-border-color) 60%, transparent);
  border-radius: 0;
}

.branch-collapse-btn {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.2s;
}

.branch-collapse-btn:hover {
  opacity: 1;
}

.branch-condition-summary {
  flex: 1;
  min-width: 0;
  color: var(--n-text-color-2);
  font-family: monospace;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-else-hint {
  flex: 1;
  min-width: 0;
  color: var(--n-text-color-3);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-collapsed-count {
  flex-shrink: 0;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.branch-group-body {
  padding: 2px 6px;
}

.branch-drop-zone {
  min-height: 28px;
}
</style>
