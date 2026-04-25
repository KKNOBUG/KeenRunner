<template>
  <n-card :bordered="false" size="medium" style="width: 100%;" class="condition-card">
    <n-form label-placement="left" label-width="100px" :model="form">
      <n-form-item label="条件表达式" required>
        <n-input
            v-model:value="form.condition_expr"
            placeholder="变量名或表达式,例如: ${token} 或 ${count}"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比较符" required>
        <n-select
            v-model:value="form.condition_compare"
            :options="operatorOptions"
            placeholder="请选择条件比较符"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比对值">
        <n-input
            v-model:value="form.condition_value"
            placeholder="字符串或变量,例如: 3 或 ${target} (非空/为空操作时可不填)"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input
            v-model:value="form.condition_desc"
            placeholder="请输入备注"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup>
import {reactive, watch, nextTick} from 'vue'
import {NForm, NFormItem, NInput, NSelect, NCard} from 'naive-ui'
import {
  assertionOperationSelectOptions,
  DEFAULT_ASSERTION_OPERATION,
} from '@/constants/autotestAssertionOperation'

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

const operatorOptions = assertionOperationSelectOptions

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

// 合并 config 与 original：conditions 与后端 ConditionsBase 字段一致
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

const form = reactive({
  ...emptyConditionFields(),
  ...mergeConfigAndOriginal(props.config, props.step?.original)
})

let isExternalUpdate = false
let lastConfigRef = null

watch(
    () => [props.step?.id, props.config, props.step?.original],
    ([stepId, config, original]) => {
      const currentConfigStr = JSON.stringify({ config, original, stepId })
      if (lastConfigRef === currentConfigStr && lastConfigRef !== null) {
        return
      }
      lastConfigRef = currentConfigStr

      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original)
      const updatedData = { ...emptyConditionFields(), ...merged }

      if (updatedData.condition_compare === undefined || updatedData.condition_compare === null) {
        updatedData.condition_compare = DEFAULT_ASSERTION_OPERATION
      }

      Object.keys(updatedData).forEach(key => {
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      if (form.condition_compare === undefined || form.condition_compare === null || typeof form.condition_compare !== 'string') {
        form.condition_compare = DEFAULT_ASSERTION_OPERATION
      }

      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {deep: true, immediate: true}
)

let emitTimer = null
watch(
    () => [form.condition_expr, form.condition_compare, form.condition_value, form.condition_desc],
    () => {
      if (isExternalUpdate) return

      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      emitTimer = setTimeout(() => {
        emit('update:config', {
          conditions: {
            condition_expr: form.condition_expr || '',
            condition_compare: form.condition_compare || DEFAULT_ASSERTION_OPERATION,
            condition_value: form.condition_value || '',
            condition_desc: form.condition_desc || ''
          }
        })
      }, 300)
    },
    {deep: true}
)
</script>

<style scoped>
.condition-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}
</style>
