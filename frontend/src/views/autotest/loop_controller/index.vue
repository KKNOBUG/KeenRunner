<template>
  <n-card :bordered="false" class="step-editor-card">
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
            <n-input
                v-model:value="form.loop_maximums"
                placeholder="正整数或变量占位符, 例如: 5 或 ${count}（执行时解析为1-100整数）"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环索引变量">
            <n-input
                v-model:value="form.loop_index"
                :maxlength="64"
                placeholder="默认 loop_index, 嵌套循环时可自定义避免同名冲突"
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
            <n-input
                v-model:value="form.loop_index"
                :maxlength="64"
                placeholder="默认 loop_index, 嵌套循环时可自定义避免同名冲突"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环数据变量">
            <n-input
                v-model:value="form.loop_value"
                :maxlength="64"
                placeholder="默认 loop_value, 嵌套循环时可自定义避免同名冲突"
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
            <n-input
                v-model:value="form.loop_index"
                :maxlength="64"
                placeholder="默认 loop_index, 嵌套循环时可自定义避免同名冲突"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环键名变量">
            <n-input
                v-model:value="form.loop_key"
                :maxlength="64"
                placeholder="默认 loop_key, 嵌套循环时可自定义避免同名冲突"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="循环数据变量">
            <n-input
                v-model:value="form.loop_value"
                :maxlength="64"
                placeholder="默认 loop_value, 嵌套循环时可自定义避免同名冲突"
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
            <n-input
                v-model:value="form.loop_index"
                :maxlength="64"
                placeholder="默认 loop_index, 嵌套循环时可自定义避免同名冲突"
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
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="最大循环时间">
            <n-input-number
                v-model:value="form.loop_timeout"
                :min="0"
                :max="300"
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
import { NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioGroup, NSpace, NCard, NSelect } from 'naive-ui'
import {
  assertionOperationSelectOptions,
  DEFAULT_ASSERTION_OPERATION,
} from '@/constants/autotestAssertionOperation'
import { useStepEditorForm } from '@/composables/step-editor'

/** 循环变量默认名：输入框初始值与空值回落口径，引擎侧同名字段为空时使用相同默认名 */
const DEFAULT_INDEX_VAR = 'loop_index'
const DEFAULT_KEY_VAR = 'loop_key'
const DEFAULT_VALUE_VAR = 'loop_value'
/** 条件循环最大循环时间上限(秒)，与后端 schema/执行引擎 clamp 同口径 */
const MAX_LOOP_TIMEOUT = 300

/** 规范化循环变量名：trim 后为空回落默认名 */
const normalizeLoopVar = (v, fallback) => {
  const text = v != null ? String(v).trim() : ''
  return text || fallback
}

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

const normalizeLoopMaximums = (v) => {
  if (v === undefined || v === null || v === '') return '5'
  return String(v)
}

const mergeConfigAndOriginal = (config, original) => {
  const merged = {
    loop_mode: normalizeLoopMode(config.loop_mode || original?.loop_mode),
    loop_on_error: config.loop_on_error || original?.loop_on_error || '中断循环',
    loop_maximums: config.loop_maximums !== undefined
      ? normalizeLoopMaximums(config.loop_maximums)
      : normalizeLoopMaximums(original?.loop_maximums),
    loop_interval: config.loop_interval !== undefined ? Number(config.loop_interval) : (original?.loop_interval ? Number(original.loop_interval) : 0),
    loop_iterable: config.loop_iterable !== undefined ? config.loop_iterable : (original?.loop_iterable || ''),
    loop_timeout: config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original?.loop_timeout ? Number(original.loop_timeout) : 0),
    loop_index: normalizeLoopVar(config.loop_index !== undefined ? config.loop_index : original?.loop_index, DEFAULT_INDEX_VAR),
    loop_key: normalizeLoopVar(config.loop_key !== undefined ? config.loop_key : original?.loop_key, DEFAULT_KEY_VAR),
    loop_value: normalizeLoopVar(config.loop_value !== undefined ? config.loop_value : original?.loop_value, DEFAULT_VALUE_VAR)
  }

  const fromConfigDict = config.loop_conditions && typeof config.loop_conditions === 'object' && !Array.isArray(config.loop_conditions)
      ? config.loop_conditions
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
  } else if (original?.loop_conditions) {
    Object.assign(merged, parseCondition(original.loop_conditions))
  } else {
    merged.condition_expr = ''
    merged.condition_compare = DEFAULT_ASSERTION_OPERATION
    merged.condition_value = ''
  }

  return merged
}

const createDefaults = () => ({
  loop_mode: '次数循环',
  loop_on_error: '中断循环',
  loop_maximums: '5',
  loop_interval: 0,
  loop_iterable: '',
  loop_timeout: 0,
  loop_index: DEFAULT_INDEX_VAR,
  loop_key: DEFAULT_KEY_VAR,
  loop_value: DEFAULT_VALUE_VAR,
  condition_expr: '',
  condition_compare: DEFAULT_ASSERTION_OPERATION,
  condition_value: ''
})

/** 循环变量名提交口径：trim 后为空传 null，由引擎回落默认名(页面输入框默认预填，后端以保存入库的为准)；非当前模式使用的变量名传null */
const loopVarOrNull = (v) => {
  const text = v != null ? String(v).trim() : ''
  return text || null
}

/** payload 按循环模式条件性输出字段 */
const buildLoopConfig = (f) => {
  const config = {
    loop_mode: f.loop_mode,
    loop_on_error: f.loop_on_error,
    loop_interval: f.loop_interval || 0
  }
  if (f.loop_mode === '次数循环') {
    config.loop_maximums = normalizeLoopMaximums(f.loop_maximums)
    config.loop_index = loopVarOrNull(f.loop_index)
    config.loop_key = null
    config.loop_value = null
  } else if (f.loop_mode === '列表循环' || f.loop_mode === '字典循环') {
    config.loop_iterable = f.loop_iterable
    config.loop_index = loopVarOrNull(f.loop_index)
    config.loop_value = loopVarOrNull(f.loop_value)
    config.loop_key = f.loop_mode === '字典循环' ? loopVarOrNull(f.loop_key) : null
  } else if (f.loop_mode === '条件循环') {
    config.loop_conditions = {
      condition_expr: f.condition_expr || '',
      condition_compare: f.condition_compare || DEFAULT_ASSERTION_OPERATION,
      condition_value: f.condition_value || ''
    }
    config.loop_timeout = Math.min(f.loop_timeout || 120, MAX_LOOP_TIMEOUT)
    config.loop_index = loopVarOrNull(f.loop_index)
    config.loop_key = null
    config.loop_value = null
  }
  return config
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: createDefaults,
  hydrate: (p) => mergeConfigAndOriginal(p.config || {}, p.step?.original),
  buildConfig: buildLoopConfig,
  watchFields: (f) => [
    f.loop_mode,
    f.loop_on_error,
    f.loop_interval,
    f.loop_maximums,
    f.loop_iterable,
    f.loop_timeout,
    f.loop_index,
    f.loop_key,
    f.loop_value,
    f.condition_expr,
    f.condition_compare,
    f.condition_value
  ],
  debounceMs: 300,
})
</script>

<style scoped>
:deep(.n-radio-group) {
  padding: 4px 0;
}
</style>
