<template>
  <n-card :bordered="false" class="step-editor-card">
    <template #header>
      <div class="panel-title">条件分支</div>
    </template>

    <n-space vertical :size="8" class="branch-list">
      <div
          v-for="(branch, index) in form.branch_items"
          :key="branch._key"
          class="branch-item"
      >
        <n-card
            size="small"
            hoverable
            :bordered="true"
            class="branch-card"
            :class="{ 'is-else-only': branch.branch_type === 'else' }"
        >
          <template #header>
            <div class="branch-card-header">
              <div class="branch-card-title-wrap">
                <span class="branch-tag" :class="`tag-${branch.branch_type}`">
                  {{ branch.branch_type.toUpperCase() }}
                </span>
                <span class="branch-card-title">{{ branchTitle(branch.branch_type) }}</span>
                <span v-if="branch.branch_type === 'else'" class="branch-else-hint">
                  {{ ELSE_FIXED_DESC }}
                </span>
              </div>
              <n-space :size="4" align="center">
                <template v-if="branch.branch_type === 'if'">
                  <n-button
                      size="tiny"
                      secondary 
                      type="primary"
                      :disabled="props.readonly || elifCount >= 15"
                      @click="addElif"
                  >
                    + 添加 ELIF
                  </n-button>
                  <n-button
                      size="tiny"
                      secondary 
                      type="primary"
                      :disabled="props.readonly || hasElse"
                      @click="addElse"
                  >
                    + 启用 ELSE
                  </n-button>
                </template>
                <n-button
                    v-if="branch.branch_type === 'elif'"
                    text
                    size="small"
                    title="上移"
                    :disabled="props.readonly || !canMoveElifUp(index)"
                    @click="moveBranch(index, -1)"
                >
                  <template #icon><TheIcon icon="gravity-ui:arrow-up" :size="16"/></template>
                </n-button>
                <n-button
                    v-if="branch.branch_type === 'elif'"
                    text
                    size="small"
                    title="下移"
                    :disabled="props.readonly || !canMoveElifDown(index)"
                    @click="moveBranch(index, 1)"
                >
                  <template #icon><TheIcon icon="gravity-ui:arrow-down" :size="16"/></template>
                </n-button>
                <n-button
                    v-if="branch.branch_type !== 'if'"
                    text
                    type="error"
                    size="small"
                    title="删除分支"
                    :disabled="props.readonly"
                    @click="removeBranch(index)"
                >
                  <template #icon><TheIcon icon="material-symbols:delete-outline" :size="18"/></template>
                </n-button>
              </n-space>
            </div>
          </template>

          <n-form
              v-if="branch.branch_type !== 'else'"
              label-width="90px"
              label-placement="left"
              size="small"
              class="step-ev-form"
          >
            <div class="step-ev-rows">
              <div class="step-ev-row">
                <n-form-item label="分支描述" class="step-ev-fi">
                  <n-input
                      v-model:value="branch.branch_desc"
                      placeholder="可添加分支描述, 用于分辨分支用途"
                      clearable
                      :disabled="props.readonly"
                  />
                </n-form-item>
              </div>

              <div class="step-ev-row step-ev-row--assert">
                <n-form-item label="条件表达式" required class="step-ev-fi">
                  <n-input
                      v-model:value="branch.branch_conditions.condition_expr"
                      placeholder="${var} 或具体数据"
                      :disabled="props.readonly"
                  />
                </n-form-item>
                <n-form-item label="条件比较符" required class="step-ev-fi">
                  <n-select
                      v-model:value="branch.branch_conditions.condition_compare"
                      :options="assertionOperationSelectOptions"
                      placeholder="请选择"
                      :disabled="props.readonly"
                  />
                </n-form-item>
                <n-form-item label="条件比较值" class="step-ev-fi">
                  <n-input
                      v-model:value="branch.branch_conditions.condition_value"
                      placeholder="${target} 或具体数据（不为空/为空时可不填）"
                      :disabled="props.readonly"
                  />
                </n-form-item>
              </div>
            </div>
          </n-form>
        </n-card>
      </div>
    </n-space>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'
import { NForm, NFormItem, NInput, NSelect, NCard, NButton, NSpace } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  assertionOperationSelectOptions,
  DEFAULT_ASSERTION_OPERATION,
} from '@/constants/autotestAssertionOperation'
import { useStepEditorForm } from '@/composables/step-editor'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  step: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:config'])

const ELSE_FIXED_DESC = '上述IF/ELIF条件均未命中时执行'

let branchKeySeq = 0
const nextBranchKey = () => `branch-${Date.now()}-${++branchKeySeq}`

const emptyCondition = () => ({
  condition_expr: '',
  condition_compare: DEFAULT_ASSERTION_OPERATION,
  condition_value: '',
})

const defaultBranchItems = () => ([
  { _key: nextBranchKey(), branch_type: 'if', branch_conditions: emptyCondition(), branch_desc: '' },
])

const hydrateBranchItems = (config) => {
  const raw = config?.branch_items
  if (Array.isArray(raw) && raw.length > 0) {
    return raw.map(b => ({
      // 保留已有 _key：分支结构变化（新增/删除/移动）时父级据此重映射子步骤 branch_index
      _key: b._key || nextBranchKey(),
      branch_type: b.branch_type || 'if',
      branch_conditions: b.branch_type !== 'else' && b.branch_conditions ? {
        condition_expr: b.branch_conditions.condition_expr != null ? String(b.branch_conditions.condition_expr) : '',
        condition_compare: b.branch_conditions.condition_compare || DEFAULT_ASSERTION_OPERATION,
        condition_value: b.branch_conditions.condition_value != null ? String(b.branch_conditions.condition_value) : '',
      } : emptyCondition(),
      branch_desc: b.branch_type === 'else' ? ELSE_FIXED_DESC : (b.branch_desc || ''),
    }))
  }
  return defaultBranchItems()
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ branch_items: defaultBranchItems() }),
  hydrate: (p) => ({ branch_items: hydrateBranchItems(p.config) }),
  buildConfig: (f) => ({
    branch_items: f.branch_items.map(b => ({
      _key: b._key,
      branch_type: b.branch_type,
      branch_desc: b.branch_type === 'else' ? ELSE_FIXED_DESC : (b.branch_desc || ''),
      branch_conditions: b.branch_type !== 'else' ? {
        condition_expr: String(b.branch_conditions?.condition_expr ?? ''),
        condition_compare: b.branch_conditions?.condition_compare || DEFAULT_ASSERTION_OPERATION,
        condition_value: String(b.branch_conditions?.condition_value ?? ''),
      } : null,
    })),
  }),
  watchFields: (f) => [f.branch_items],
})

const elifCount = computed(() => form.branch_items.filter(b => b.branch_type === 'elif').length)
const hasElse = computed(() => form.branch_items.some(b => b.branch_type === 'else'))

const branchTitle = (type) => {
  if (type === 'if') return '若条件成立'
  if (type === 'elif') return '否则若条件成立'
  return '否则'
}

const canMoveElifUp = (index) => index > 1

const canMoveElifDown = (index) => {
  const next = form.branch_items[index + 1]
  return !!next && next.branch_type !== 'else'
}

const addElif = () => {
  const elseIndex = form.branch_items.findIndex(b => b.branch_type === 'else')
  const newBranch = {
    _key: nextBranchKey(),
    branch_type: 'elif',
    branch_conditions: emptyCondition(),
    branch_desc: '',
  }
  if (elseIndex !== -1) {
    form.branch_items.splice(elseIndex, 0, newBranch)
  } else {
    form.branch_items.push(newBranch)
  }
}

const addElse = () => {
  form.branch_items.push({
    _key: nextBranchKey(),
    branch_type: 'else',
    branch_conditions: null,
    branch_desc: ELSE_FIXED_DESC,
  })
}

const removeBranch = (index) => {
  form.branch_items.splice(index, 1)
}

const moveBranch = (index, direction) => {
  const target = index + direction
  if (target < 1 || target >= form.branch_items.length) return
  if (form.branch_items[target].branch_type === 'else' && direction > 0) return
  const [item] = form.branch_items.splice(index, 1)
  form.branch_items.splice(target, 0, item)
}
</script>

<style scoped lang="scss">
@import '@/components/autotest/step-extract-assert-panel.scss';

.branch-list {
  width: 100%;
}

.branch-item {
  width: 100%;
}

.branch-item :deep(.n-card) {
  border: 1px solid var(--n-border-color);
  background-color: var(--n-color);
}

.branch-card :deep(.n-card-header) {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 6px 12px;
  box-sizing: border-box;
  background-color: var(--n-color-embedded);
}

.branch-card :deep(.n-card-header__main) {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.branch-card :deep(.n-card__content) {
  padding: 8px 12px;
}

.branch-card.is-else-only :deep(.n-card-header) {
  border-bottom: none;
}

.branch-card.is-else-only :deep(.n-card__content) {
  display: none;
  padding: 0;
}

.branch-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-height: 24px;
  line-height: 1.35;
  font-size: 13px;
}

.branch-card-title-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.branch-card-title {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 500;
}

.branch-else-hint {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 400;
  color: var(--n-text-color-3);
}
</style>
