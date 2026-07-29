<template>
  <n-card :bordered="false" class="step-editor-card">
    <template #header>
      <div class="panel-title">条件分支</div>
    </template>
    <n-form
        class="step-editor-form"
        label-placement="left"
        label-width="110px"
        size="small"
        :model="form"
    >
      <n-form-item label="条件表达式" required>
        <n-input
            v-model:value="form.condition_expr"
            placeholder="变量名称或自定义表达式，例如: ${var} 或 具体数据"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比较符" required>
        <n-select
            v-model:value="form.condition_compare"
            :options="assertionOperationSelectOptions"
            placeholder="请选择条件比较符"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比对值">
        <n-input
            v-model:value="form.condition_value"
            placeholder="变量名称或自定义比较值，例如: ${target} 或 具体数据 (非空/为空操作时可不填)"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input
            v-model:value="form.condition_desc"
            placeholder="请输入备注"
            :disabled="props.readonly"
        />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup>
import {NForm, NFormItem, NInput, NSelect, NCard} from 'naive-ui'
import {
  assertionOperationSelectOptions,
  DEFAULT_ASSERTION_OPERATION,
} from '@/constants/autotestAssertionOperation'
import {useStepEditorForm} from '@/composables/step-editor'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  },
  readonly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:config'])

const emptyConditionFields = () => ({
  condition_expr: '',
  condition_compare: DEFAULT_ASSERTION_OPERATION,
  condition_value: '',
  condition_desc: ''
})

const fieldsFromConditionsDict = (d) => ({
  condition_expr: d.condition_expr !== undefined && d.condition_expr !== null ? String(d.condition_expr) : '',
  condition_compare: d.condition_compare !== undefined && d.condition_compare !== null
      ? String(d.condition_compare)
      : DEFAULT_ASSERTION_OPERATION,
  condition_value: d.condition_value !== undefined && d.condition_value !== null ? String(d.condition_value) : '',
  condition_desc: d.condition_desc !== undefined && d.condition_desc !== null ? String(d.condition_desc) : ''
})

const mergeConfigAndOriginal = (config, original) => {
  const c = config?.conditions
  if (c && typeof c === 'object' && !Array.isArray(c)) {
    return fieldsFromConditionsDict(c)
  }
  const o = original?.conditions
  if (o && typeof o === 'object' && !Array.isArray(o)) {
    return fieldsFromConditionsDict(o)
  }
  return emptyConditionFields()
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: emptyConditionFields,
  hydrate: (p) => mergeConfigAndOriginal(p.config, p.step?.original),
  buildConfig: (f) => ({
    conditions: {
      condition_expr: String(f.condition_expr ?? ''),
      condition_compare: f.condition_compare || DEFAULT_ASSERTION_OPERATION,
      condition_value: String(f.condition_value ?? ''),
      condition_desc: String(f.condition_desc ?? '')
    }
  }),
  watchFields: (f) => [f.condition_expr, f.condition_compare, f.condition_value, f.condition_desc],
})
</script>
