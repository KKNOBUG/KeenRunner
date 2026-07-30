<template>
  <n-card :bordered="false" class="step-editor-card">
    <template #header>
      <div class="panel-title">条件分支</div>
    </template>
    <div class="branch-list">
      <div
          v-for="(branch, index) in form.branches"
          :key="index"
          class="branch-card"
          :class="[`branch-type-${branch.branch_type}`]"
      >
        <div class="branch-card-header">
          <n-tag :type="branchTagType(branch.branch_type)" size="small" round>
            {{ branch.branch_type.toUpperCase() }}
          </n-tag>
          <n-input
              v-model:value="branch.branch_desc"
              placeholder="分支描述"
              size="tiny"
              class="branch-desc-input"
              :disabled="props.readonly"
          />
          <span class="branch-card-actions">
            <n-button
                v-if="branch.branch_type === 'elif'"
                text size="tiny" :disabled="props.readonly || index <= 1"
                @click="moveBranch(index, -1)"
            >
              <template #icon><TheIcon icon="gravity-ui:arrow-up" :size="14"/></template>
            </n-button>
            <n-button
                v-if="branch.branch_type === 'elif'"
                text size="tiny" :disabled="props.readonly || index >= form.branches.length - 1 || form.branches[index + 1]?.branch_type === 'else' && index + 1 >= form.branches.length - 1"
                @click="moveBranch(index, 1)"
            >
              <template #icon><TheIcon icon="gravity-ui:arrow-down" :size="14"/></template>
            </n-button>
            <n-button
                v-if="branch.branch_type !== 'if'"
                text size="tiny" type="error" :disabled="props.readonly"
                @click="removeBranch(index)"
            >
              <template #icon><TheIcon icon="material-symbols:delete" :size="14"/></template>
            </n-button>
          </span>
        </div>
        <n-form
            v-if="branch.branch_type !== 'else'"
            class="branch-form"
            label-placement="left"
            label-width="90px"
            size="small"
        >
          <n-form-item label="条件表达式" required>
            <n-input
                v-model:value="branch.conditions.condition_expr"
                placeholder="${var} 或具体数据"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="条件比较符" required>
            <n-select
                v-model:value="branch.conditions.condition_compare"
                :options="assertionOperationSelectOptions"
                placeholder="请选择"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="条件比对值">
            <n-input
                v-model:value="branch.conditions.condition_value"
                placeholder="${target} 或具体数据 (非空/为空时可不填)"
                :disabled="props.readonly"
            />
          </n-form-item>
        </n-form>
        <div v-else class="branch-else-hint">上述分支均未命中时执行</div>
      </div>
    </div>
    <div class="branch-actions">
      <n-button
          size="small" dashed :disabled="props.readonly || elifCount >= 15"
          @click="addElif"
      >
        + 添加 ELIF
      </n-button>
      <n-button
          size="small" dashed :disabled="props.readonly || hasElse"
          @click="addElse"
      >
        + 启用 ELSE
      </n-button>
    </div>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'
import { NForm, NFormItem, NInput, NSelect, NCard, NButton, NTag } from 'naive-ui'
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

const emptyCondition = () => ({
  condition_expr: '',
  condition_compare: DEFAULT_ASSERTION_OPERATION,
  condition_value: '',
  condition_desc: '',
})

const defaultBranches = () => ([
  { branch_type: 'if', conditions: emptyCondition(), branch_desc: '' },
])

const hydrateBranches = (config) => {
  const raw = config?.branches
  if (Array.isArray(raw) && raw.length > 0) {
    return raw.map(b => ({
      branch_type: b.branch_type || 'if',
      conditions: b.branch_type !== 'else' && b.conditions ? {
        condition_expr: b.conditions.condition_expr != null ? String(b.conditions.condition_expr) : '',
        condition_compare: b.conditions.condition_compare || DEFAULT_ASSERTION_OPERATION,
        condition_value: b.conditions.condition_value != null ? String(b.conditions.condition_value) : '',
        condition_desc: b.conditions.condition_desc != null ? String(b.conditions.condition_desc) : '',
      } : emptyCondition(),
      branch_desc: b.branch_desc || '',
    }))
  }
  return defaultBranches()
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ branches: defaultBranches() }),
  hydrate: (p) => ({ branches: hydrateBranches(p.config) }),
  buildConfig: (f) => ({
    branches: f.branches.map(b => ({
      branch_type: b.branch_type,
      branch_desc: b.branch_desc || '',
      conditions: b.branch_type !== 'else' ? {
        condition_expr: String(b.conditions?.condition_expr ?? ''),
        condition_compare: b.conditions?.condition_compare || DEFAULT_ASSERTION_OPERATION,
        condition_value: String(b.conditions?.condition_value ?? ''),
        condition_desc: String(b.conditions?.condition_desc ?? ''),
      } : null,
    })),
  }),
  watchFields: (f) => [f.branches],
  debounceMs: 300,
})

const elifCount = computed(() => form.branches.filter(b => b.branch_type === 'elif').length)
const hasElse = computed(() => form.branches.some(b => b.branch_type === 'else'))

const branchTagType = (type) => {
  if (type === 'if') return 'success'
  if (type === 'elif') return 'warning'
  return 'info'
}

const addElif = () => {
  const elseIndex = form.branches.findIndex(b => b.branch_type === 'else')
  const newBranch = { branch_type: 'elif', conditions: emptyCondition(), branch_desc: '' }
  if (elseIndex !== -1) {
    form.branches.splice(elseIndex, 0, newBranch)
  } else {
    form.branches.push(newBranch)
  }
}

const addElse = () => {
  form.branches.push({ branch_type: 'else', conditions: null, branch_desc: '' })
}

const removeBranch = (index) => {
  form.branches.splice(index, 1)
}

const moveBranch = (index, direction) => {
  const target = index + direction
  if (target < 1 || target >= form.branches.length) return
  if (form.branches[target].branch_type === 'else' && direction > 0) return
  const temp = form.branches[index]
  form.branches[index] = form.branches[target]
  form.branches[target] = temp
}
</script>

<style scoped>
.branch-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.branch-card {
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  padding: 12px;
  border-left: 3px solid var(--n-border-color);
}

.branch-type-if { border-left-color: #18a058; }
.branch-type-elif { border-left-color: #f0a020; }
.branch-type-else { border-left-color: #2080f0; }

.branch-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.branch-desc-input {
  flex: 1;
}

.branch-card-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.branch-form {
  margin-top: 4px;
}

.branch-else-hint {
  color: var(--n-text-color-3);
  font-size: 12px;
  padding: 4px 0;
}

.branch-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
