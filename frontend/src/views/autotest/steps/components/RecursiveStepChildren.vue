<template>
  <div
      v-if="stepDefinitions[step.type]?.allowChildren && isStepExpanded(step.id)"
      @dragover.prevent.stop="handleDragOverInChildrenArea($event, step.id)"
      @dragleave.stop="handleDragLeaveInChildrenArea($event, step.id)"
  >
    <!-- 无子女时显示空的拖拽区域 -->
    <div
        v-if="!step.children || step.children.length === 0"
        class="step-drop-zone"
        :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
        @drop.stop="handleDrop($event, step.id, step.id, 0)"
    >
      <div class="step-drop-zone-hint">拖拽步骤到这里</div>
    </div>

    <template v-for="(child, childIndex) in (step.children || [])" :key="child.id">
      <!-- 插入位置指示器：在子步骤之前 -->
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
            <TheIcon
                :icon="getStepIcon(child.type)"
                :size="16"
                class="step-icon"
                :class="getStepIconClass(child.type)"
            />
            <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
            <span class="step-actions">
              <span class="step-number">#{{ getStepNumber(child.id) }}</span>
              <n-button
                  text
                  size="tiny"
                  class="action-btn"
                  :title="child.step_is_skipped ? '取消注释(恢复执行)' : '注释(跳过执行)'"
                  @click.stop="toggleSkipStep(child.id, $event)"
              >
                <template #icon>
                  <TheIcon :icon="child.step_is_skipped ? 'gravity-ui:eye' : 'gravity-ui:eye-slash'" :size="14"/>
                </template>
              </n-button>
              <n-button
                  v-if="stepDefinitions[child.type]?.allowChildren"
                  text
                  size="tiny"
                  class="action-btn"
                  @click.stop="toggleStepExpand(child.id, $event)"
              >
                <template #icon>
                  <TheIcon :icon="isStepExpanded(child.id) ? 'gravity-ui:chevron-up' : 'gravity-ui:chevron-down'" :size="14"/>
                </template>
              </n-button>
              <n-button
                  text
                  size="tiny"
                  class="action-btn"
                  title="复制当前步骤"
                  @click.stop="handleCopyStep(child.id)"
              >
                <template #icon>
                  <TheIcon icon="gravity-ui:square-article" :size="14"/>
                </template>
              </n-button>
              <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
                <template #trigger>
                  <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                    <template #icon>
                      <TheIcon icon="material-symbols:delete" :size="14"/>
                    </template>
                  </n-button>
                </template>
                确认删除该步骤?
              </n-popconfirm>
            </span>
          </span>
          <!-- 递归渲染子步骤（只有当子步骤允许有子步骤时才渲染） -->
          <RecursiveStepChildren v-if="stepDefinitions[child.type]?.allowChildren" :step="child"/>
        </div>
      </div>

      <!-- 插入位置指示器：在子步骤之后 -->
      <div class="step-insert-indicator" :style="insertIndicatorStyle(child.id, 'after')"></div>
    </template>

    <!-- 插入位置指示器：在最后一个子步骤之后 -->
    <div class="step-insert-indicator" :style="insertIndicatorStyle(null, 'after', true)"></div>

    <div class="step-add-btn">
      <AddStepPopover
          :is-public-script-case="isPublicScriptCase"
          @select="(key) => handleAddStep(key, step.id)"
      />
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { NButton, NPopconfirm } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import AddStepPopover from './AddStepPopover.vue'

defineOptions({ name: 'RecursiveStepChildren' })

const props = defineProps({
  step: {
    type: Object,
    required: true
  }
})

/**
 * 步骤树上下文：由 steps/index.vue provide。
 * 递归组件层级深、共享绑定多，用 provide/inject 替代逐层透传 22 个 props。
 */
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
  dragState,
} = inject('stepTreeContext')

/** 拖拽插入位置指示器显隐：requireChildren 用于「末尾指示器」仅在有子步骤时出现 */
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
