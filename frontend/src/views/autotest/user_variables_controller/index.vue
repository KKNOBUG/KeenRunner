<template>
  <n-card :bordered="false" style="width: 100%;" class="user-variables-card">
    <n-form
        label-placement="left"
        label-width="80px"
        :model="state.form"
    >
      <n-form-item label="步骤名称" path="step_name">
        <n-input
            v-model:value="state.form.step_name"
            placeholder="请输入步骤名称"
            clearable
            style="width: 100%;"
        />
      </n-form-item>
      <n-form-item label="步骤描述" path="step_desc">
        <n-input
            type="textarea"
            v-model:value="state.form.step_desc"
            placeholder="请输入步骤描述"
            clearable
            style="width: 100%; min-height: 4rem;"
        />
      </n-form-item>
    </n-form>
    <div class="variables-section">
      <KeyValueEditor
          v-model:items="state.form.session_variables"
          :body-type="'none'"
          :is-for-body="false"
          :show-description="true"
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
  }
})

const emit = defineEmits(['update:config'])

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

const mergeConfigAndOriginal = (config, original) => {
  const raw = config.session_variables ?? original?.session_variables ?? defaults.session_variables
  return {
    step_name: config.step_name !== undefined ? config.step_name : (original?.step_name ?? defaults.step_name),
    step_desc: config.step_desc !== undefined ? config.step_desc : (original?.step_desc ?? defaults.step_desc),
    session_variables: initSessionVariables(raw)
  }
}

const state = reactive({
  form: {
    ...defaults,
    ...mergeConfigAndOriginal(props.config, props.step?.original)
  }
})

let isExternalUpdate = false

watch(
    () => [props.step?.id, props.config, props.step?.original],
    ([, config, original]) => {
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original)
      state.form.step_name = merged.step_name
      state.form.step_desc = merged.step_desc
      state.form.session_variables = merged.session_variables
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { deep: true, immediate: true }
)

let emitTimer = null
watch(
    () => [state.form.step_name, state.form.step_desc, state.form.session_variables],
    () => {
      if (isExternalUpdate) return
      if (emitTimer) clearTimeout(emitTimer)
      emitTimer = setTimeout(() => {
        emit('update:config', {
          step_name: state.form.step_name ?? '',
          step_desc: state.form.step_desc ?? '',
          session_variables: normalizeSessionVariables(state.form.session_variables)
        })
      }, 300)
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
