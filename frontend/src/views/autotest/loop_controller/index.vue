<template>
  <n-card :bordered="false" class="step-editor-card loop-card">
    <template #header>
      <div class="panel-title">循环结构</div>
    </template>
    <n-form class="step-editor-form" label-placement="left" label-width="110px" size="small" :model="form">
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

      <n-form-item label="异常策略" required>
        <n-select
            v-model:value="form.loop_on_error"
            :options="errorStrategyOptions"
            placeholder="请选择错误处理策略"
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
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引变量">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index"  />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '列表循环'">
          <n-form-item label="列表对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或可迭代的数据对象, 例如: ${list} 或 [1, 2, 3, 4, 5]"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引变量">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index"  />
          </n-form-item>
          <n-form-item label="循环数据变量">
            <n-input :value="LOOP_VALUE_NAME" disabled placeholder="loop_value"  />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '字典循环'">
          <n-form-item label="字典对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或字典对象，例如: ${dict} 或 {key1: value1, key2: value2}"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引变量">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index"  />
          </n-form-item>
          <n-form-item label="循环键名变量">
            <n-input :value="LOOP_KEY_NAME" disabled placeholder="loop_key"  />
          </n-form-item>
          <n-form-item label="循环数据变量">
            <n-input :value="LOOP_VALUE_NAME" disabled placeholder="loop_value"  />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
                :disabled="props.readonly"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.loop_mode === '条件循环'">
          <n-form-item label="条件表达式" required>
            <n-input
                v-model:value="form.condition_expr"
                placeholder="变量名, 例如: ${count} 或 ${status}"
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
          <n-form-item label="条件比较值">
            <n-input
                v-model:value="form.condition_value"
                placeholder="字符串或变量, 例如: 3 或 ${target}"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引变量">
            <n-input :value="LOOP_INDEX_NAME" disabled placeholder="loop_index"  />
          </n-form-item>
          <n-form-item label="循环间隔时间">
            <n-input-number
                v-model:value="form.loop_interval"
                :min="0"
                :precision="2"
                suffix="秒"
                placeholder="请输入循环间隔时间（秒）"
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

const mergeConfigAndOriginal = (config, original) => {
  const merged = {
    loop_mode: normalizeLoopMode(config.loop_mode || original?.loop_mode),
    loop_on_error: config.loop_on_error || original?.loop_on_error || '中断循环',
    loop_maximums: config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original?.loop_maximums ? Number(original.loop_maximums) : 5),
    loop_interval: config.loop_interval !== undefined ? Number(config.loop_interval) : (original?.loop_interval ? Number(original.loop_interval) : 0),
    loop_iterable: config.loop_iterable !== undefined ? config.loop_iterable : (original?.loop_iterable || ''),
    loop_timeout: config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original?.loop_timeout ? Number(original.loop_timeout) : 0)
  }

  const fromConfigDict = config.conditions && typeof config.conditions === 'object' && !Array.isArray(config.conditions)
      ? config.conditions
      : null
  if (fromConfigDict) {
    Object.assign(merged, parseCondition(fromConfigDict))
  } else if (
      config.condition_expr !== undefined ||
      config.condition_compare !== undefined ||
      config.condition_value !== undefined
  ) {
    merged.condition_expr = config.condition_expr != null ? String(config.condition_expr) : ''
    merged.condition_compare = config.condition_compare || DEFAULT_ASSERTION_OPERATION
    merged.condition_value = config.condition_value != null ? String(config.condition_value) : ''
  } else if (original?.conditions) {
    Object.assign(merged, parseCondition(original.conditions))
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

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original)
})

let isExternalUpdate = false

/** 仅在步骤切换时从 props 灌入，避免 config 回写与输入抢值 */
watch(
    () => props.step?.id,
    () => {
      isExternalUpdate = true
      Object.assign(form, defaults, mergeConfigAndOriginal(props.config || {}, props.step?.original))
      nextTick(() => {
        isExternalUpdate = false
      })
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
      if (isExternalUpdate || props.readonly) return
      if (emitTimer) clearTimeout(emitTimer)

      emitTimer = setTimeout(() => {
        const config = {
          loop_mode: form.loop_mode,
          loop_on_error: form.loop_on_error,
          loop_interval: form.loop_interval || 0
        }

        if (form.loop_mode === '次数循环') {
          config.loop_maximums = form.loop_maximums
        } else if (form.loop_mode === '列表循环' || form.loop_mode === '字典循环') {
          config.loop_iterable = form.loop_iterable
        } else if (form.loop_mode === '条件循环') {
          config.conditions = {
            condition_expr: form.condition_expr || '',
            condition_compare: form.condition_compare || DEFAULT_ASSERTION_OPERATION,
            condition_value: form.condition_value || ''
          }
          config.loop_timeout = form.loop_timeout || 120
        }

        emit('update:config', config)
      }, 300)
    }
)
</script>

<style scoped>
:deep(.n-radio-group) {
  padding: 4px 0;
}
</style>
