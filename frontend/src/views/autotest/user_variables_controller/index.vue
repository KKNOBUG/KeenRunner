<template>
  <n-card :bordered="false" style="width: 100%;" class="user-variables-card">
    <n-form
        ref="formRef"
        :rules="formRules"
        label-placement="left"
        label-width="80px"
        :model="form"
    >
      <n-form-item label="步骤名称" path="step_name" required>
        <n-input
            v-model:value="form.step_name"
            placeholder="请输入步骤名称"
            clearable
            style="width: 100%;"
        />
      </n-form-item>
      <n-form-item label="步骤描述" path="step_desc">
        <n-input
            type="textarea"
            v-model:value="form.step_desc"
            placeholder="请输入步骤描述"
            clearable
            style="width: 100%; min-height: 4rem;"
        />
      </n-form-item>
    </n-form>
    <div class="variables-section">
      <KeyValueEditor
          v-model:items="form.session_variables"
          :body-type="'none'"
          :is-for-body="false"
          :show-description="true"
      />
    </div>
  </n-card>
</template>

<script setup>
import { reactive, ref, watch, nextTick } from 'vue'
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
  }
})

const emit = defineEmits(['update:config'])
const formRef = ref(null)

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

// 标准化为后端格式 key, value, desc
const normalizeSessionVariables = (list) => {
  if (!Array.isArray(list)) return []
  return list.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc ?? item.description ?? ''
  }))
}

// 初始化时同时设置 description 供 KeyValueEditor 描述列显示
const initSessionVariables = (list) => {
  return normalizeSessionVariables(list).map(item => ({
    ...item,
    description: item.desc
  }))
}

// 与 run_code_controller 一致：合并 config / original，stepName 作为 step_name 回退
const mergeConfigAndOriginal = (config, original, stepName) => {
  const raw = config.session_variables ?? original?.session_variables ?? defaults.session_variables
  return {
    step_name: config.step_name !== undefined
        ? config.step_name
        : (original?.step_name ?? stepName ?? defaults.step_name),
    step_desc: config.step_desc !== undefined ? config.step_desc : (original?.step_desc ?? defaults.step_desc),
    session_variables: initSessionVariables(raw)
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
      if (isExternalUpdate) return
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
.user-variables-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}

.variables-section {
  margin-top: 16px;
}

.section-label {
  margin-bottom: 8px;
  font-size: 14px;
  color: #666;
}
</style>


