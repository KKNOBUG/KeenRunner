<template>
  <n-card :bordered="false" size="medium" style="width: 100%;" class="condition-card">
  <!-- 顶部操作栏：步骤名称 -->
  <div class="top-bar">
    <div class="condition-icon">
      <TheIcon icon="tabler:arrow-loop-right-2" :size="32" />
    </div>
    <n-input
      v-model:value="form.step_name"
      autosize
      placeholder="条件分支(根据条件判断结果, 选择不同的执行路径)"
      class="step-name-input"
  />
  </div>
  </n-card>
  <n-card :bordered="false" size="medium" style="width: 100%;" class="condition-card">

    <n-form label-placement="left" label-width="100px" :model="form">
      <n-form-item label="条件表达式" required>
        <n-input
            v-model:value="form.value"
            placeholder="变量名或表达式,例如: ${token} 或 ${count}"
            style="width: 80%;"
        />
      </n-form-item>
      <n-form-item label="条件比较符" required>
        <n-select
            v-model:value="form.operation"
            :options="operatorOptions"
            placeholder="请选择条件比较符"
            style="width: 80%;"
        />
      </n-form-item>
      <n-form-item label="条件比对值">
        <n-input
            v-model:value="form.except_value"
            placeholder="字符串或变量,例如: 3 或 ${target} (非空/为空操作时可不填)"
            style="width: 80%;"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input
            v-model:value="form.desc"
            placeholder="请输入备注"
            style="width: 80%;"
        />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup>
import {reactive, watch, nextTick} from 'vue'
import {NForm, NFormItem, NInput, NSelect, NCard} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

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

const defaults = {
  step_name: '',
  value: '',
  operation: '非空',
  except_value: '',
  desc: ''
}

// 解析条件JSON字符串（后端存储格式：JSON对象，包含 value, operation, except_value, desc）
const parseCondition = (conditionStr) => {
  if (!conditionStr) return { value: '', operation: '非空', except_value: '', desc: '' }
  try {
    // 如果是字符串，尝试解析为JSON
    if (typeof conditionStr === 'string') {
      const parsed = JSON.parse(conditionStr)
      // 处理数组格式（后端可能返回数组）
      if (Array.isArray(parsed) && parsed.length > 0) {
        return {
          value: parsed[0].value || '',
          operation: parsed[0].operation || '非空',
          except_value: parsed[0].except_value || '',
          desc: parsed[0].desc || ''
        }
      }
      // 处理对象格式
      if (typeof parsed === 'object') {
        return {
          value: parsed.value || '',
          operation: parsed.operation || '非空',
          except_value: parsed.except_value || '',
          desc: parsed.desc || ''
        }
      }
    }
    // 如果已经是对象，直接使用
    if (typeof conditionStr === 'object') {
      if (Array.isArray(conditionStr) && conditionStr.length > 0) {
        return {
          value: conditionStr[0].value || '',
          operation: conditionStr[0].operation || '非空',
          except_value: conditionStr[0].except_value || '',
          desc: conditionStr[0].desc || ''
        }
      }
      return {
        value: conditionStr.value || '',
        operation: conditionStr.operation || '非空',
        except_value: conditionStr.except_value || '',
        desc: conditionStr.desc || ''
      }
    }
  } catch (e) {
    console.error('解析条件失败:', e)
  }
  return { value: '', operation: '非空', except_value: '', desc: '' }
}

// 合并config和原始数据
const mergeConfigAndOriginal = (config, original, stepName) => {
  // 处理 step_name：优先使用 config.step_name，然后是 step.name，最后是 original.step_name
  const step_name = config.step_name !== undefined
      ? config.step_name
      : (stepName || original?.step_name || '')

  // 优先使用config
  if (config.value !== undefined || config.operation !== undefined || config.except_value !== undefined || config.desc !== undefined) {
    return {
      step_name,
      value: config.value !== undefined ? (config.value || '') : '',
      operation: config.operation !== undefined ? (config.operation || '非空') : '非空',
      except_value: config.except_value !== undefined ? (config.except_value || '') : '',
      desc: config.desc !== undefined ? (config.desc || '') : ''
    }
  }

  // 从original的conditions中解析
  if (original?.conditions) {
    const condition = parseCondition(original.conditions)
    return {
      step_name,
      value: condition.value || '',
      operation: condition.operation || '非空',
      except_value: condition.except_value || '',
      desc: condition.desc || ''
    }
  }

  return {
    ...defaults,
    step_name
  }
}

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original, props.step?.name)
})

// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false

// 记录上一次的 config，用于判断是否真的发生了变化
let lastConfigRef = null

// 监听props变化，更新表单
watch(
    () => [props.step?.id, props.config, props.step?.original, props.step?.name],
    ([stepId, config, original, stepName]) => {
      // 检查是否真的发生了变化（避免不必要的更新）
      const currentConfigStr = JSON.stringify({ config, original, stepName })
      if (lastConfigRef === currentConfigStr && lastConfigRef !== null) {
        return // 没有实际变化，跳过更新
      }
      lastConfigRef = currentConfigStr

      // 当步骤变化时，重新初始化表单
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original, stepName)
      const updatedData = { ...defaults, ...merged }

      // 确保 operation 字段始终存在且为字符串类型
      if (updatedData.operation === undefined || updatedData.operation === null) {
        updatedData.operation = '非空'
      }

      // 只在字段值真正不同时才更新，避免覆盖用户正在输入的值
      Object.keys(updatedData).forEach(key => {
        if (form[key] !== updatedData[key]) {
          form[key] = updatedData[key]
        }
      })

      // 特别确保 operation 字段在 reactive 对象中存在且类型正确
      if (form.operation === undefined || form.operation === null || typeof form.operation !== 'string') {
        form.operation = '非空'
      }

      // 使用 nextTick 确保在下一个 tick 重置标志
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {deep: true, immediate: true}
)

// 监听表单变化，发送更新
// 使用防抖，避免频繁触发
let emitTimer = null
watch(
    () => [form.step_name, form.value, form.operation, form.except_value, form.desc],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      // 清除之前的定时器
      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      // 使用防抖，延迟发送更新
      emitTimer = setTimeout(() => {
        emit('update:config', {
          step_name: form.step_name || '',
          value: form.value || '',
          operation: form.operation || '非空',
          except_value: form.except_value || '',
          desc: form.desc || ''
        })
      }, 300) // 300ms 防抖延迟
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

.top-bar {
  display: flex;
  align-items: center;
}

.condition-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  color: #F4511E;
  width: 100px;
}

.step-name-input {
  width: 71%;
}

</style>
