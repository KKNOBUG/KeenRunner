<template>
  <n-card :bordered="false" class="step-editor-card wait-card">
    <template #header>
      <div class="panel-title">等待控制</div>
    </template>
    <n-form
        class="step-editor-form"
        label-placement="left"
        label-width="80px"
        size="small"
        :model="form"
    >
      <n-form-item label="等待时间">
        <n-input-number
            v-model:value="form.seconds"
            :min="0"
            :precision="2"
            suffix="秒"
            placeholder="请输入等待时间（秒）"
            style="width: 240px;"
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

const mergeConfigAndOriginal = (config, original) => ({
  seconds: config.seconds !== undefined
      ? Number(config.seconds)
      : (original?.wait ? Number(original.wait) : defaults.seconds)
})

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
      const merged = mergeConfigAndOriginal(props.config || {}, props.step?.original)
      Object.assign(form, defaults, merged)
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {immediate: true}
)

let emitTimer = null
watch(
    () => form.seconds,
    () => {
      if (isExternalUpdate || props.readonly) return
      if (emitTimer) clearTimeout(emitTimer)
      emitTimer = setTimeout(() => {
        emit('update:config', {
          seconds: form.seconds || 0
        })
      }, 300)
    }
)
</script>
