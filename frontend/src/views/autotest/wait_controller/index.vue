<template>
  <n-card :bordered="false" class="step-editor-card">
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
import {NForm, NFormItem, NInputNumber, NCard} from 'naive-ui'
import {useStepEditorForm} from '@/composables/step-editor'

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

const DEFAULT_SECONDS = 2

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ seconds: DEFAULT_SECONDS }),
  hydrate: (p) => ({
    seconds: p.config?.seconds !== undefined
        ? Number(p.config.seconds)
        : (p.step?.original?.wait ? Number(p.step.original.wait) : DEFAULT_SECONDS)
  }),
  buildConfig: (f) => ({ seconds: f.seconds || 0 }),
  watchFields: (f) => [f.seconds],
  debounceMs: 300,
})
</script>
