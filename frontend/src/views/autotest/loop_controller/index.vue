<template>
  <n-card :bordered="false" style="width: 100%;" class="loop-card">
    <n-form label-placement="left" label-width="135px" :model="form">
      <!-- 循环模式选择 -->
      <n-form-item label="循环模式选择" required>
        <n-radio-group v-model:value="form.loop_mode" name="loop-mode">
          <n-space>
            <n-radio value="次数循环">次数循环</n-radio>
            <n-radio value="对象循环">对象循环</n-radio>
            <n-radio value="字典循环">字典循环</n-radio>
            <n-radio value="条件循环">条件循环</n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>

      <!-- 错误处理策略（所有模式都需要） -->
      <n-form-item label="错误处理策略" required>
        <n-select
            v-model:value="form.loop_on_error"
            :options="errorStrategyOptions"
            placeholder="请选择错误处理策略"
            style="width: 80%;"
        />
      </n-form-item>

      <div>
        <!-- 次数循环模式 -->
        <template v-if="form.loop_mode === '次数循环'">
          <n-form-item label="最大循环次数" required>
            <n-input-number
                v-model:value="form.loop_maximums"
                :min="1"
                placeholder="请输入最大循环次数, 最多循环100次"
                style="width: 80%;"
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
            />
          </n-form-item>
        </template>

        <!-- 对象循环模式 -->
        <template v-else-if="form.loop_mode === '对象循环'">
          <n-form-item label="数组对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或可迭代的数据对象, 例如: ${list} 或 [1, 2, 3, 4, 5]"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="索引变量名称">
            <n-input
                v-model:value="form.loop_iter_idx"
                placeholder="用于存储列表项的索引, 默认: loop_index"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="数据变量名称">
            <n-input
                v-model:value="form.loop_iter_val"
                placeholder="用于存储列表项的值, 默认: loop_value"
                style="width: 80%;"
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
            />
          </n-form-item>
        </template>

        <!-- 字典循环模式 -->
        <template v-else-if="form.loop_mode === '字典循环'">
          <n-form-item label="字典对象来源" required>
            <n-input
                v-model:value="form.loop_iterable"
                placeholder="变量名或字典对象，例如: ${dict} 或 {key1: value1, key2: value2}"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="索引变量名称">
            <n-input
                v-model:value="form.loop_iter_idx"
                placeholder="用于存储字典项的索引, 默认: loop_index"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="键变量名称">
            <n-input
                v-model:value="form.loop_iter_key"
                placeholder="用于存储字典项的键，默认: loop_key"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="值变量名称">
            <n-input
                v-model:value="form.loop_iter_val"
                placeholder="用于存储字典项的值, 默认: loop_value"
                style="width: 80%;"
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
            />
          </n-form-item>
        </template>

        <!-- 条件循环模式 -->
        <template v-else-if="form.loop_mode === '条件循环'">
          <n-form-item label="条件表达式" required>
            <n-input
                v-model:value="form.condition_value"
                placeholder="变量名, 例如: ${count} 或 ${status}"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="比较操作符" required>
            <n-select
                v-model:value="form.condition_operation"
                :options="operatorOptions"
                placeholder="请选择比较操作符"
                style="width: 80%;"
            />
          </n-form-item>
          <n-form-item label="条件比较值">
            <n-input
                v-model:value="form.condition_except_value"
                placeholder="字符串或变量, 例如: 3 或 ${target}"
                style="width: 80%;"
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

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:config'])

// 错误处理策略选项
const errorStrategyOptions = [
  { label: '继续下一次循环', value: '继续下一次循环' },
  { label: '中断循环', value: '中断循环' },
  { label: '停止整个用例执行', value: '停止整个用例执行' }
]

// 比对条件选项（用于条件循环）
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

// 解析条件JSON字符串
const parseCondition = (conditionStr) => {
  if (!conditionStr) return { value: '', operation: 'not_empty', except_value: '' }
  try {
    // 如果是字符串，尝试解析为JSON
    if (typeof conditionStr === 'string') {
      const parsed = JSON.parse(conditionStr)
      return {
        value: parsed.value || '',
        operation: parsed.operation || 'not_empty',
        except_value: parsed.except_value || ''
      }
    }
    // 如果已经是对象，直接使用
    if (typeof conditionStr === 'object') {
      return {
        value: conditionStr.value || '',
        operation: conditionStr.operation || 'not_empty',
        except_value: conditionStr.except_value || ''
      }
    }
  } catch (e) {
    console.error('解析条件失败:', e)
  }
  return { value: '', operation: 'not_empty', except_value: '' }
}

// 将条件对象转换为JSON字符串
const stringifyCondition = (conditionObj) => {
  if (!conditionObj || (!conditionObj.value && !conditionObj.operation)) {
    return null
  }
  return JSON.stringify({
    value: conditionObj.value || '',
    operation: conditionObj.operation || 'not_empty',
    except_value: conditionObj.except_value || ''
  })
}

// 从原始数据中初始化表单
const initFormFromOriginal = (original) => {
  if (!original) return {}

  const formData = {
    loop_mode: original.loop_mode || '次数循环',
    loop_on_error: original.loop_on_error || '继续下一次循环',
    loop_maximums: original.loop_maximums ? Number(original.loop_maximums) : null,
    loop_interval: original.loop_interval ? Number(original.loop_interval) : 1,
    loop_iterable: original.loop_iterable || '',
    loop_iter_idx: original.loop_iter_idx || '',
    loop_iter_key: original.loop_iter_key || '',
    loop_iter_val: original.loop_iter_val || '',
    loop_timeout: original.loop_timeout ? Number(original.loop_timeout) : 120
  }

  // 解析条件循环的conditions
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

// 合并config和原始数据
const mergeConfigAndOriginal = (config, original) => {
  // 优先使用config，如果没有则使用original
  const merged = {
    loop_mode: config.loop_mode || original?.loop_mode || '次数循环',
    loop_on_error: config.loop_on_error || original?.loop_on_error || '继续下一次循环',
    loop_maximums: config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original?.loop_maximums ? Number(original.loop_maximums) : null),
    loop_interval: config.loop_interval !== undefined ? Number(config.loop_interval) : (original?.loop_interval ? Number(original.loop_interval) : 0),
    loop_iterable: config.loop_iterable !== undefined ? config.loop_iterable : (original?.loop_iterable || ''),
    loop_iter_idx: config.loop_iter_idx !== undefined ? config.loop_iter_idx : (original?.loop_iter_idx || ''),
    loop_iter_key: config.loop_iter_key !== undefined ? config.loop_iter_key : (original?.loop_iter_key || ''),
    loop_iter_val: config.loop_iter_val !== undefined ? config.loop_iter_val : (original?.loop_iter_val || ''),
    loop_timeout: config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original?.loop_timeout ? Number(original.loop_timeout) : 0)
  }

  // 处理条件循环的conditions
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
  loop_on_error: '继续下一次循环',
  loop_maximums: null,
  loop_interval: 0,
  loop_iterable: '',
  loop_iter_idx: '',
  loop_iter_key: '',
  loop_iter_val: '',
  loop_timeout: 0,
  condition_value: '',
  condition_operation: 'not_empty',
  condition_except_value: ''
}

// 确保所有字段都被初始化，特别是条件循环的字段
const initialData = {
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original)
}

// 确保条件循环相关字段始终存在且不为 undefined
initialData.condition_value = initialData.condition_value ?? ''
initialData.condition_operation = initialData.condition_operation ?? 'not_empty'
initialData.condition_except_value = initialData.condition_except_value ?? ''

const form = reactive(initialData)

// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false
// 记录上一次的 config，用于判断是否真的发生了变化
let lastConfigRef = null

// 监听props变化，更新表单
watch(
    () => [props.step?.id, props.config, props.step?.original],
    ([stepId, config, original]) => {
      // 检查是否真的发生了变化（避免不必要的更新）
      const configStr = JSON.stringify(config || {})
      if (lastConfigRef === configStr && lastConfigRef !== null) {
        return // 没有实际变化，跳过更新
      }
      lastConfigRef = configStr

      // 当步骤变化时，重新初始化表单
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original)
      const updatedData = { ...defaults, ...merged }

      // 确保条件循环相关字段始终存在且不为 undefined
      updatedData.condition_value = updatedData.condition_value ?? ''
      updatedData.condition_operation = updatedData.condition_operation ?? 'not_empty'
      updatedData.condition_except_value = updatedData.condition_except_value ?? ''

      // 只在字段值真正不同时才更新，避免覆盖用户正在输入的值
      Object.keys(updatedData).forEach(key => {
        // 对于条件循环的字段，如果当前值不为空且新值不同，可能是用户正在输入，不覆盖
        if ((key === 'condition_value' || key === 'condition_except_value') &&
            form[key] && form[key].trim() !== '' &&
            form[key] !== updatedData[key] &&
            updatedData[key] === '') {
          // 用户正在输入，保留当前值
          return
        }
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      // 特别确保条件循环字段在 reactive 对象中存在
      if (form.condition_value === undefined || form.condition_value === null) {
        form.condition_value = ''
      }
      if (form.condition_operation === undefined || form.condition_operation === null) {
        form.condition_operation = 'not_empty'
      }
      if (form.condition_except_value === undefined || form.condition_except_value === null) {
        form.condition_except_value = ''
      }

      // 使用 nextTick 确保在下一个 tick 重置标志
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { deep: true, immediate: true }
)

// 监听循环模式变化，确保切换到条件循环时字段存在
watch(
    () => form.loop_mode,
    (newMode) => {
      if (newMode === '条件循环') {
        // 确保条件循环相关字段存在且为字符串类型
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

// 监听表单变化，转换为后端格式并发送
// 使用防抖，避免频繁触发
let emitTimer = null
watch(
    () => [
      form.loop_mode,
      form.loop_on_error,
      form.loop_interval,
      form.loop_maximums,
      form.loop_iterable,
      form.loop_iter_idx,
      form.loop_iter_key,
      form.loop_iter_val,
      form.loop_timeout,
      form.condition_value,
      form.condition_operation,
      form.condition_except_value
    ],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      // 清除之前的定时器
      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      // 使用防抖，延迟发送更新，避免在用户输入时频繁触发
      emitTimer = setTimeout(() => {
        const config = {
          loop_mode: form.loop_mode,
          loop_on_error: form.loop_on_error,
          loop_interval: form.loop_interval || 0
        }

        // 根据循环模式添加特定字段
        if (form.loop_mode === '次数循环') {
          config.loop_maximums = form.loop_maximums
        } else if (form.loop_mode === '对象循环') {
          config.loop_iterable = form.loop_iterable
          config.loop_iter_idx = form.loop_iter_idx
          config.loop_iter_val = form.loop_iter_val
        } else if (form.loop_mode === '字典循环') {
          config.loop_iterable = form.loop_iterable
          config.loop_iter_idx = form.loop_iter_idx
          config.loop_iter_key = form.loop_iter_key
          config.loop_iter_val = form.loop_iter_val
        } else if (form.loop_mode === '条件循环') {
          // 将条件对象转换为JSON字符串
          const conditionObj = {
            value: form.condition_value || '',
            operation: form.condition_operation || 'not_empty',
            except_value: form.condition_except_value || ''
          }
          config.condition_value = conditionObj.value
          config.condition_operation = conditionObj.operation
          config.condition_except_value = conditionObj.except_value
          config.conditions = stringifyCondition(conditionObj)
          config.loop_timeout = form.loop_timeout || 120
        }

        emit('update:config', config)
      }, 300) // 300ms 防抖延迟
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
