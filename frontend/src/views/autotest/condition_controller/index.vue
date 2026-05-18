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

const buildConditionsPayload = () => ({
  condition_expr: String(form.condition_expr ?? ''),
  condition_compare: form.condition_compare || DEFAULT_ASSERTION_OPERATION,
  condition_value: String(form.condition_value ?? ''),
  condition_desc: String(form.condition_desc ?? '')
})

const form = reactive({
  ...emptyConditionFields(),
  ...mergeConfigAndOriginal(props.config, props.step?.original)
})

let isExternalUpdate = false

/**
 * 与 user_variables_controller / run_code 修复方式一致：
 * - 仅在选择步骤（step.id 变化）时从 props 灌入 form
 * - 输入过程中父级会更新 config，但绝不再写回 form（否则与 v-model 抢值 → 卡顿丢字）
 */
watch(
    () => props.step?.id,
    () => {
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(props.config || {}, props.step?.original)
      form.condition_expr = merged.condition_expr
      form.condition_compare = merged.condition_compare
      form.condition_value = merged.condition_value
      form.condition_desc = merged.condition_desc
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {immediate: true}
)

/** 立即同步到父级，不做防抖（防抖期间 props 回写曾导致丢字） */
watch(
    () => [
      form.condition_expr,
      form.condition_compare,
      form.condition_value,
      form.condition_desc
    ],
    () => {
      if (isExternalUpdate || props.readonly) {
        return
      }
      emit('update:config', {
        conditions: buildConditionsPayload()
      })
    }
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
