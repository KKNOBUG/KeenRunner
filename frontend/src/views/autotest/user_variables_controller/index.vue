<template>
  <n-card :bordered="false" class="step-editor-card">
    <template #header>
      <div class="panel-title">用户变量</div>
    </template>
    <n-form
        class="step-editor-form"
        :rules="formRules"
        label-placement="left"
        label-width="80px"
        size="small"
        :model="form"
    >
      <n-form-item label="步骤名称" path="step_name" required>
        <n-input
            v-model:value="form.step_name"
            placeholder="请输入步骤名称"
            clearable
            :disabled="props.readonly"
        />
      </n-form-item>
      <n-form-item label="步骤描述" path="step_desc">
        <n-input
            type="textarea"
            v-model:value="form.step_desc"
            placeholder="请输入步骤描述"
            clearable
            :resizable="false"
            :autosize="{ minRows: 1, maxRows: 3 }"
            :disabled="props.readonly"
        />
      </n-form-item>
    </n-form>
    <div class="variables-section">
      <KeyValueEditor
          v-model:items="form.session_variables"
          :body-type="'none'"
          :is-for-body="false"
          :available-variable-list="props.availableVariableList"
          :assist-functions="props.assistFunctions"
          :disabled="props.readonly"
      />
    </div>
  </n-card>
</template>

<script setup>
import { NForm, NFormItem, NInput, NCard } from 'naive-ui'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import { useStepEditorForm } from '@/composables/step-editor'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  },
  availableVariableList: {
    type: Array,
    default: () => []
  },
  assistFunctions: {
    type: Array,
    default: () => []
  },
  readonly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:config'])

const formRules = {
  step_name: [
    { required: true, message: '请输入步骤名称', trigger: 'blur' }
  ]
}

/** 标准化为 KeyValueEditor / 后端格式：key, value, desc */
const normalizeSessionVariables = (list) => {
  if (!Array.isArray(list)) return []
  return list.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc ?? item.description ?? ''
  }))
}

const mergeConfigAndOriginal = (config, original, stepName) => {
  const raw = config.session_variables ?? original?.session_variables ?? []
  return {
    step_name: config.step_name !== undefined
        ? config.step_name
        : (original?.step_name ?? stepName ?? ''),
    step_desc: config.step_desc !== undefined ? config.step_desc : (original?.step_desc ?? ''),
    session_variables: normalizeSessionVariables(raw)
  }
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ step_name: '', step_desc: '', session_variables: [] }),
  hydrate: (p) => mergeConfigAndOriginal(p.config || {}, p.step?.original, p.step?.name),
  buildConfig: (f) => ({
    step_name: f.step_name ?? '',
    step_desc: f.step_desc ?? '',
    session_variables: normalizeSessionVariables(f.session_variables)
  }),
  watchFields: (f) => [f.step_name, f.step_desc, f.session_variables],
})
</script>

<style scoped>
.variables-section {
  margin-top: 12px;
}
</style>


