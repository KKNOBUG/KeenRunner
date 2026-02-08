<template>
  <n-card :bordered="false" size="medium" style="width: 100%;" class="wait-card">
    <n-form label-placement="left" label-width="100px" :model="form">
      <n-form-item label="等待时间">
        <n-input-number
            v-model:value="form.seconds"
            :min="0"
            :precision="2"
            suffix="秒"
            placeholder="请输入等待时间（秒）"
            style="width: 30%;"
            :disabled="props.readonly"
        />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup>
import {reactive, watch, nextTick} from 'vue'
import {NForm, NFormItem, NInputNumber, NCard} from 'naive-ui'

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

const defaults = {
  seconds: 2
}

// 合并config和原始数据
const mergeConfigAndOriginal = (config, original) => {
  return {
    seconds: config.seconds !== undefined
        ? Number(config.seconds)
        : (original?.wait ? Number(original.wait) : defaults.seconds)
  }
}

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original)
})

// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false

// 监听props变化，更新表单
watch(
    () => [props.step?.id, props.config, props.step?.original],
    ([stepId, config, original]) => {
      // 当步骤变化时，重新初始化表单
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original)
      Object.assign(form, defaults, merged)
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
    () => form.seconds,
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
          seconds: form.seconds || 0
        })
      }, 300) // 300ms 防抖延迟
    },
    {deep: true}
)
</script>

<style scoped>
.wait-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}

</style>
