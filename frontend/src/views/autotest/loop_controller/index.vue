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
          <n-alert type="info" style="margin-bottom: 12px;" :bordered="false">
            每轮<strong>先</strong>判断条件是否成立；成立则执行循环内步骤，不成立则结束。首轮条件不成立时不会执行子步骤。
          </n-alert>
          <n-form-item label="条件表达式" required>
            <n-input
                v-model:value="form.condition_expr"
                placeholder="变量名, 例如: ${count} 或 ${status}"
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
          <n-form-item label="条件比较值">
            <n-input
                v-model:value="form.condition_value"
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
import { NAlert, NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioGroup, NSpace, NCard, NSelect } from 'naive-ui'
import {
  assertionOperationSelectOptions,
  DEFAULT_ASSERTION_OPERATION,
} from '@/constants/autotestAssertionOperation'

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

const operatorOptions = assertionOperationSelectOptions

const normalizeLoopMode = (m) => m || '次数循环'

const parseCondition = (c) => {
  if (!c || typeof c !== 'object' || Array.isArray(c)) {
    return {
      condition_expr: '',
      condition_compare: DEFAULT_ASSERTION_OPERATION,
      condition_value: ''
    }
  }
  return {
    condition_expr: c.condition_expr != null ? String(c.condition_expr) : '',
    condition_compare: c.condition_compare || DEFAULT_ASSERTION_OPERATION,
    condition_value: c.condition_value != null ? String(c.condition_value) : ''
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
    formData.condition_expr = condition.condition_expr
    formData.condition_compare = condition.condition_compare
    formData.condition_value = condition.condition_value
  } else {
    formData.condition_expr = ''
    formData.condition_compare = DEFAULT_ASSERTION_OPERATION
    formData.condition_value = ''
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

  if (
      config.condition_expr !== undefined ||
      config.condition_compare !== undefined ||
      config.condition_value !== undefined
  ) {
    merged.condition_expr = config.condition_expr != null ? String(config.condition_expr) : ''
    merged.condition_compare = config.condition_compare || DEFAULT_ASSERTION_OPERATION
    merged.condition_value = config.condition_value != null ? String(config.condition_value) : ''
  } else if (original?.conditions) {
    const condition = parseCondition(original.conditions)
    merged.condition_expr = condition.condition_expr
    merged.condition_compare = condition.condition_compare
    merged.condition_value = condition.condition_value
  } else {
    merged.condition_expr = ''
    merged.condition_compare = DEFAULT_ASSERTION_OPERATION
    merged.condition_value = ''
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
  condition_expr: '',
  condition_compare: DEFAULT_ASSERTION_OPERATION,
  condition_value: ''
}

const initialData = {
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original)
}

initialData.condition_expr = initialData.condition_expr ?? ''
initialData.condition_compare = initialData.condition_compare ?? DEFAULT_ASSERTION_OPERATION
initialData.condition_value = initialData.condition_value ?? ''

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

      updatedData.condition_expr = updatedData.condition_expr ?? ''
      updatedData.condition_compare = updatedData.condition_compare ?? DEFAULT_ASSERTION_OPERATION
      updatedData.condition_value = updatedData.condition_value ?? ''

      Object.keys(updatedData).forEach(key => {
        if ((key === 'condition_expr' || key === 'condition_value') &&
            form[key] && form[key].trim() !== '' &&
            form[key] !== updatedData[key] &&
            updatedData[key] === '') {
          return
        }
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      if (form.condition_expr === undefined || form.condition_expr === null) {
        form.condition_expr = ''
      }
      if (form.condition_compare === undefined || form.condition_compare === null) {
        form.condition_compare = DEFAULT_ASSERTION_OPERATION
      }
      if (form.condition_value === undefined || form.condition_value === null) {
        form.condition_value = ''
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
        if (typeof form.condition_expr !== 'string') {
          form.condition_expr = form.condition_expr ?? ''
        }
        if (typeof form.condition_compare !== 'string') {
          form.condition_compare = form.condition_compare ?? DEFAULT_ASSERTION_OPERATION
        }
        if (typeof form.condition_value !== 'string') {
          form.condition_value = form.condition_value ?? ''
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
      form.condition_expr,
      form.condition_compare,
      form.condition_value
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
            condition_expr: form.condition_expr || '',
            condition_compare: form.condition_compare || DEFAULT_ASSERTION_OPERATION,
            condition_value: form.condition_value || ''
          }
          config.condition_expr = conditionObj.condition_expr
          config.condition_compare = conditionObj.condition_compare
          config.condition_value = conditionObj.condition_value
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
