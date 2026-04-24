<template>
  <n-card :bordered="false" style="width: 100%;" class="loop-card">
    <n-form label-placement="left" label-width="135px" :model="form">
      <n-form-item label="循环模式" required>
        <n-radio-group v-model:value="form.loop_mode" name="loop-mode" :disabled="props.readonly">
          <n-space>
            <n-radio value="次数循环">次数循环</n-radio>
            <n-radio value="列表循环">列表循环</n-radio>
            <n-radio value="字典循环">字典循环</n-radio>
            <n-radio value="条件循环">条件循环</n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>

      <n-form-item label="错误处理策略" required>
        <n-select
            v-model:value="form.loop_on_error"
            :options="errorStrategyOptions"
            placeholder="请选择错误处理策略"
            style="width: 80%;"
            :disabled="props.readonly"
        />
      </n-form-item>

      <div>
        <template v-if="form.loop_mode === '次数循环'">
          <n-form-item label="最大循环次数" required>
            <n-input-number
                v-model:value="form.loop_maximums"
                :min="1"
                placeholder="请输入最大循环次数, 最多循环100次"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '列表循环'">
          <n-form-item label="列表对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或可迭代的数据对象, 例如: ${list} 或 [1, 2, 3, 4, 5]"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环数据">
            <n-input :value="LOOP_VALUE_NAME" disabled placeholder="loop_value" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '字典循环'">
          <n-form-item label="字典对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或字典对象，例如: ${dict} 或 {key1: value1, key2: value2}"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环键名">
            <n-input :value="LOOP_KEY_NAME" disabled placeholder="loop_key" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环数据">
            <n-input :value="LOOP_VALUE_NAME" disabled placeholder="loop_value" style="width: 80%;" />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '条件循环'">
          <n-form-item label="条件表达式" required>
            <n-input
                v-model:value="form.condition_value"
                placeholder="变量名, 例如: ${count} 或 ${status}"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="条件比较符" required>
            <n-select
                v-model:value="form.condition_operation"
                :options="operatorOptions"
                placeholder="请选择条件比较符"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="条件比较值">
            <n-input
                v-model:value="form.condition_except_value"
                placeholder="字符串或变量, 例如: 3 或 ${target}"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="最大循环时间">
            <n-input-number
                v-model:value="form.loop_timeout"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="0 表示不超时, 最大循环时间: 300"
                style="width: 80%;"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>
      </div>
    </n-form>
  </n-card>
</template>

<script setup>
import { reactive, watch, nextTick } from 'vue'
import { NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioGroup, NSpace, NCard, NSelect } from 'naive-ui'

/** 执行引擎写入会话变量的固定名称（不再落库配置字段） */
const LOOP_INDEX_NAME = 'loop_index'
const LOOP_VALUE_NAME = 'loop_value'
const LOOP_KEY_NAME = 'loop_key'

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

const errorStrategyOptions = [
  { label: '继续下一次循环', value: '继续下一次循环' },
  { label: '中断循环', value: '中断循环' },
  { label: '停止整个用例执行', value: '停止整个用例执行' }
]

const operatorOptions = [
  { label: '等于', value: 'eq' },
  { label: '不等于', value: 'ne' },
  { label: '大于', value: 'gt' },
  { label: '大于等于', value: 'gte' },
  { label: '小于', value: 'lt' },
  { label: '小于等于', value: 'lte' },
  { label: '包含', value: 'contains' },
  { label: '不包含', value: 'not_contains' },
  { label: '非空', value: 'not_empty' },
  { label: '为空', value: 'empty' },
  { label: '正则匹配', value: 'regex' }
]

const normalizeLoopMode = (m) => m || '次数循环'

const parseCondition = (c) => {
  if (!c || typeof c !== 'object' || Array.isArray(c)) {
    return { value: '', operation: 'not_empty', except_value: '' }
  }
  return {
    value: c.value || '',
    operation: c.operation || 'not_empty',
    except_value: c.except_value || ''
  }
}

const initFormFromOriginal = (original) => {
  if (!original) return {}

  const formData = {
    loop_mode: normalizeLoopMode(original.loop_mode),
    loop_on_error: original.loop_on_error || '中断循环',
    loop_maximums: original.loop_maximums ? Number(original.loop_maximums) : 5,
    loop_interval: original.loop_interval ? Number(original.loop_interval) : 1,
    loop_iterable: original.loop_iterable || '',
    loop_timeout: original.loop_timeout ? Number(original.loop_timeout) : 120
  }

  if (original.conditions) {
    const condition = parseCondition(original.conditions)
    formData.condition_value = condition.value
    formData.condition_operation = condition.operation
    formData.condition_except_value = condition.except_value
  } else {
    formData.condition_value = ''
    formData.condition_operation = 'not_empty'
    formData.condition_except_value = ''
  }

  return formData
}

const mergeConfigAndOriginal = (config, original) => {
  const merged = {
    loop_mode: normalizeLoopMode(config.loop_mode || original?.loop_mode),
    loop_on_error: config.loop_on_error || original?.loop_on_error || '中断循环',
    loop_maximums: config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original?.loop_maximums ? Number(original.loop_maximums) : 5),
    loop_interval: config.loop_interval !== undefined ? Number(config.loop_interval) : (original?.loop_interval ? Number(original.loop_interval) : 0),
    loop_iterable: config.loop_iterable !== undefined ? config.loop_iterable : (original?.loop_iterable || ''),
    loop_timeout: config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original?.loop_timeout ? Number(original.loop_timeout) : 0)
  }

  if (config.condition_value !== undefined || config.condition_operation !== undefined || config.condition_except_value !== undefined) {
    merged.condition_value = config.condition_value || ''
    merged.condition_operation = config.condition_operation || 'not_empty'
    merged.condition_except_value = config.condition_except_value || ''
  } else if (original?.conditions) {
    const condition = parseCondition(original.conditions)
    merged.condition_value = condition.value
    merged.condition_operation = condition.operation
    merged.condition_except_value = condition.except_value
  } else {
    merged.condition_value = ''
    merged.condition_operation = 'not_empty'
    merged.condition_except_value = ''
  }

  return merged
}

const defaults = {
  loop_mode: '次数循环',
  loop_on_error: '中断循环',
  loop_maximums: 5,
  loop_interval: 0,
  loop_iterable: '',
  loop_timeout: 0,
  condition_value: '',
  condition_operation: 'not_empty',
  condition_except_value: ''
}

const initialData = {
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original)
}

initialData.condition_value = initialData.condition_value ?? ''
initialData.condition_operation = initialData.condition_operation ?? 'not_empty'
initialData.condition_except_value = initialData.condition_except_value ?? ''

const form = reactive(initialData)

let isExternalUpdate = false
let lastConfigRef = null

watch(
    () => [props.step?.id, props.config, props.step?.original],
    ([stepId, config, original]) => {
      const configStr = JSON.stringify(config || {})
      if (lastConfigRef === configStr && lastConfigRef !== null) {
        return
      }
      lastConfigRef = configStr

      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original)
      const updatedData = { ...defaults, ...merged }

      updatedData.condition_value = updatedData.condition_value ?? ''
      updatedData.condition_operation = updatedData.condition_operation ?? 'not_empty'
      updatedData.condition_except_value = updatedData.condition_except_value ?? ''

      Object.keys(updatedData).forEach(key => {
        if ((key === 'condition_value' || key === 'condition_except_value') &&
            form[key] && form[key].trim() !== '' &&
            form[key] !== updatedData[key] &&
            updatedData[key] === '') {
          return
        }
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      if (form.condition_value === undefined || form.condition_value === null) {
        form.condition_value = ''
      }
      if (form.condition_operation === undefined || form.condition_operation === null) {
        form.condition_operation = 'not_empty'
      }
      if (form.condition_except_value === undefined || form.condition_except_value === null) {
        form.condition_except_value = ''
      }

      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { deep: true, immediate: true }
)

watch(
    () => form.loop_mode,
    (newMode) => {
      if (newMode === '条件循环') {
        if (typeof form.condition_value !== 'string') {
          form.condition_value = form.condition_value ?? ''
        }
        if (typeof form.condition_operation !== 'string') {
          form.condition_operation = form.condition_operation ?? 'not_empty'
        }
        if (typeof form.condition_except_value !== 'string') {
          form.condition_except_value = form.condition_except_value ?? ''
        }
      }
    },
    { immediate: true }
)

let emitTimer = null
watch(
    () => [
      form.loop_mode,
      form.loop_on_error,
      form.loop_interval,
      form.loop_maximums,
      form.loop_iterable,
      form.loop_timeout,
      form.condition_value,
      form.condition_operation,
      form.condition_except_value
    ],
    () => {
      if (isExternalUpdate) return

      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      emitTimer = setTimeout(() => {
        const config = {
          loop_mode: form.loop_mode,
          loop_on_error: form.loop_on_error,
          loop_interval: form.loop_interval || 0
        }

        if (form.loop_mode === '次数循环') {
          config.loop_maximums = form.loop_maximums
        } else if (form.loop_mode === '列表循环') {
          config.loop_iterable = form.loop_iterable
        } else if (form.loop_mode === '字典循环') {
          config.loop_iterable = form.loop_iterable
        } else if (form.loop_mode === '条件循环') {
          const conditionObj = {
            value: form.condition_value || '',
            operation: form.condition_operation || 'not_empty',
            except_value: form.condition_except_value || ''
          }
          config.condition_value = conditionObj.value
          config.condition_operation = conditionObj.operation
          config.condition_except_value = conditionObj.except_value
          config.conditions = { ...conditionObj }
          config.loop_timeout = form.loop_timeout || 120
        }

        emit('update:config', config)
      }, 300)
    },
    { deep: true }
)
</script>

<style scoped>
.loop-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}

:deep(.n-radio-group) {
  padding: 4px 0;
}
</style>
