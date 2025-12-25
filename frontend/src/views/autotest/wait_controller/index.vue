<template>
  <n-form label-placement="left" label-width="auto" :model="form">
    <n-form-item label="等待时间">
      <n-input-number
          v-model:value="form.seconds"
          :min="0"
          suffix="秒"
      />
    </n-form-item>
  </n-form>
</template>

<script setup>
import {reactive, watch} from 'vue'
import {NForm, NFormItem, NInputNumber} from 'naive-ui'

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

const defaults = {
  seconds: 2
}

const form = reactive({...defaults, ...props.config})

watch(
    () => [props.step?.id, props.config],
    ([stepId, val]) => {
      // 当步骤变化时，重新初始化表单
      Object.assign(form, defaults, val || {})
    },
    {deep: true, immediate: true}
)

watch(
    form,
    () => emit('update:config', {...form}),
    {deep: true}
)
</script>
