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
import { reactive, watch, nextTick } from 'vue'
import { NForm, NFormItem, NInput, NCard } from 'naive-ui'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'

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

const defaults = {
  step_name: '',
  step_desc: '',
  session_variables: []
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
  const raw = config.session_variables ?? original?.session_variables ?? defaults.session_variables
  return {
    step_name: config.step_name !== undefined
        ? config.step_name
        : (original?.step_name ?? stepName ?? defaults.step_name),
    step_desc: config.step_desc !== undefined ? config.step_desc : (original?.step_desc ?? defaults.step_desc),
    session_variables: normalizeSessionVariables(raw)
  }
}

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original, props.step?.name)
})

let isExternalUpdate = false

// 与 run_code_controller 一致：仅在步骤切换时从 props 同步到表单（监听 step.id），避免输入时被 config 回写导致卡字/丢字
watch(
    () => props.step?.id,
    () => {
      isExternalUpdate = true
      const config = props.config || {}
      const original = props.step?.original
      const stepName = props.step?.name
      const merged = mergeConfigAndOriginal(config, original, stepName)
      form.step_name = merged.step_name
      form.step_desc = merged.step_desc
      form.session_variables = merged.session_variables
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { immediate: true }
)

// 与 run_code_controller 一致：表单变化时立即 emit，不做防抖，避免输入卡顿/丢字
watch(
    () => [form.step_name, form.step_desc, form.session_variables],
    () => {
      if (isExternalUpdate || props.readonly) return
      emit('update:config', {
        step_name: form.step_name ?? '',
        step_desc: form.step_desc ?? '',
        session_variables: normalizeSessionVariables(form.session_variables)
      })
    },
    { deep: true }
)
</script>

<style scoped>
.variables-section {
  margin-top: 12px;
}
</style>


