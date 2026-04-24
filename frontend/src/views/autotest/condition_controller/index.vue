<template>
  <n-card :bordered="false" size="medium" style="width: 100%;" class="condition-card">
    <n-form label-placement="left" label-width="100px" :model="form">
      <n-form-item label="条件表达式" required>
        <n-input
            v-model:value="form.value"
            placeholder="变量名或表达式,例如: ${token} 或 ${count}"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比较符" required>
        <n-select
            v-model:value="form.operation"
            :options="operatorOptions"
            placeholder="请选择条件比较符"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="条件比对值">
        <n-input
            v-model:value="form.except_value"
            placeholder="字符串或变量,例如: 3 或 ${target} (非空/为空操作时可不填)"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input
            v-model:value="form.desc"
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

// 操作符选项（必须与后端 ConditionStepExecutor.compare 中的 op_map 一致）
const operatorOptions = [
  {label: '等于', value: '等于'},
  {label: '不等于', value: '不等于'},
  {label: '大于', value: '大于'},
  {label: '大于等于', value: '大于等于'},
  {label: '小于', value: '小于'},
  {label: '小于等于', value: '小于等于'},
  {label: '非空', value: '非空'},
  {label: '为空', value: '为空'}
]

const emptyConditionFields = () => ({
  value: '',
  operation: '非空',
  except_value: '',
  desc: ''
})

const fieldsFromConditionsDict = (d) => ({
  value: d.value !== undefined && d.value !== null ? String(d.value) : '',
  operation: d.operation !== undefined && d.operation !== null ? String(d.operation) : '非空',
  except_value: d.except_value !== undefined && d.except_value !== null ? String(d.except_value) : '',
  desc: d.desc !== undefined && d.desc !== null ? String(d.desc) : ''
})

// 合并 config 与 original：conditions 仅为 plain object（与后端 Optional[Dict] 一致）
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

      if (updatedData.operation === undefined || updatedData.operation === null) {
        updatedData.operation = '非空'
      }

      Object.keys(updatedData).forEach(key => {
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      if (form.operation === undefined || form.operation === null || typeof form.operation !== 'string') {
        form.operation = '非空'
      }

      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {deep: true, immediate: true}
)

let emitTimer = null
watch(
    () => [form.value, form.operation, form.except_value, form.desc],
    () => {
      if (isExternalUpdate) return

      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      emitTimer = setTimeout(() => {
        emit('update:config', {
          conditions: {
            value: form.value || '',
            operation: form.operation || '非空',
            except_value: form.except_value || '',
            desc: form.desc || ''
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
