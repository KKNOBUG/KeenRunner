<template>
  <div
      v-if="stepDefinitions[step.type]?.allowChildren && isStepExpanded(step.id)"
      @dragover.prevent.stop="handleDragOverInChildrenArea($event, step.id)"
      @dragleave.stop="handleDragLeaveInChildrenArea($event, step.id)"
  >
    <!-- 条件分支: 按分支分组渲染 -->
    <template v-if="step.type === 'if' && step.config?.branches?.length">
      <div
          v-for="(branch, bi) in step.config.branches"
          :key="'branch-' + bi"
          class="branch-group"
          :class="[`branch-group-${branch.branch_type}`]"
      >
        <div class="branch-group-header">
          <span class="branch-tag" :class="`tag-${branch.branch_type}`">
            {{ branch.branch_type.toUpperCase() }}
          </span>
          <span v-if="branch.branch_type !== 'else' && branch.conditions" class="branch-condition-summary">
            {{ branch.conditions.condition_expr }} {{ branch.conditions.condition_compare }} {{ branch.conditions.condition_value }}
          </span>
          <span v-if="branch.branch_desc" class="branch-desc-label">{{ branch.branch_desc }}</span>
        </div>
        <div class="branch-group-body">
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
              <div class="step-item-child">
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
                <RecursiveStepChildren v-if="stepDefinitions[child.type]?.allowChildren" :step="child"/>
              </div>
            </div>
            <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'after')"></div>
          </template>
          <!-- 分支为空时的拖拽区域 -->
          <div
              v-if="getBranchChildren(bi).length === 0"
              class="step-drop-zone branch-drop-zone"
              :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
              @drop.stop="handleDrop($event, step.id, step.id, getBranchInsertIndex(bi))"
          >
            <div class="step-drop-zone-hint">拖拽步骤到此分支</div>
          </div>
          <div class="step-add-btn">
            <AddStepPopover :is-public-script-case="isPublicScriptCase" @select="(key) => handleAddStepToBranch(key, step.id, bi)"/>
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
          <div class="step-item-child">
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
            <RecursiveStepChildren v-if="stepDefinitions[child.type]?.allowChildren" :step="child"/>
          </div>
        </div>
        <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'after')"></div>
      </template>
      <div class="step-insert-indicator" :style="insertIndicatorStyle(null, 'after', true)"></div>
      <div class="step-add-btn">
        <AddStepPopover :is-public-script-case="isPublicScriptCase" @select="(key) => handleAddStep(key, step.id)"/>
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
  step: { type: Object, required: true }
})

const {
  stepDefinitions,
  isStepExpanded,
  toggleStepExpand,
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
  isPublicScriptCase,
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
.branch-group {
  margin: 4px 0;
  border-radius: 6px;
  border: 1px dashed var(--n-border-color);
  overflow: hidden;
}

.branch-group-if { border-left: 3px solid #18a058; }
.branch-group-elif { border-left: 3px solid #f0a020; }
.branch-group-else { border-left: 3px solid #2080f0; }

.branch-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--n-color-modal);
  font-size: 12px;
}

.branch-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
}

.tag-if { background: #18a058; }
.tag-elif { background: #f0a020; }
.tag-else { background: #2080f0; }

.branch-condition-summary {
  color: var(--n-text-color-2);
  font-family: monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-desc-label {
  color: var(--n-text-color-3);
  font-size: 11px;
}

.branch-group-body {
  padding: 4px 4px 4px 8px;
}

.branch-drop-zone {
  min-height: 28px;
}
</style>
