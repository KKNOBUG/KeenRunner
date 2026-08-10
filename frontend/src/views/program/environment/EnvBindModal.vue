<template>
  <NModal
      :show="show"
      preset="card"
      style="width: 640px"
      :title="isEdit ? '编辑环境' : '新建环境'"
      @update:show="(v) => emit('update:show', v)"
  >
    <NForm ref="formRef" :model="form" label-placement="left" label-align="left" :label-width="90">
      <NFormItem
          label="应用名称"
          path="project_id"
          :rule="{ required: true, type: 'number', message: '请选择应用名称', trigger: ['change', 'blur'] }"
      >
        <NSelect
            v-model:value="form.project_id"
            :options="projectSelectOptions"
            clearable
            filterable
            placeholder="请选择应用"
        />
      </NFormItem>
      <NFormItem
          label="节点类型"
          path="env_type"
          :rule="{ required: true, message: '请选择节点类型', trigger: ['change', 'blur'] }"
      >
        <NSelect
            v-model:value="form.env_type"
            :options="ENV_TYPE_OPTIONS"
            :disabled="isEdit"
            placeholder="APP / FILE / DB / REDIS"
        />
      </NFormItem>
      <NFormItem
          label="环境名称"
          path="env_name"
          :rule="{ required: true, message: '请选择或输入环境名称', trigger: ['change', 'blur'] }"
      >
        <NSelect
            v-model:value="form.env_name"
            :options="envNameOptions"
            :loading="envNameLoading"
            filterable
            tag
            clearable
            placeholder="选择已有环境，或输入新名称后回车"
        />
      </NFormItem>
      <NFormItem label="环境描述" path="env_desc">
        <NInput
            v-model:value="form.env_desc"
            type="textarea"
            maxlength="2048"
            show-count
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="可选：说明该环境用途或接入范围"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="emit('update:show', false)">取消</NButton>
        <NButton type="primary" :loading="saving" @click="handleSave">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NSpace } from 'naive-ui'
import api from '@/api'
import { useUserStore } from '@/store'
import { ENV_TYPE, ENV_TYPE_OPTIONS } from './envType'

defineOptions({ name: '环境绑定弹窗' })

const props = defineProps({
  show: { type: Boolean, default: false },
  /** 编辑时传入主表行；新增时为 null */
  envRow: { type: Object, default: null },
  projectOptions: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:show', 'saved'])

const userStore = useUserStore()
const formRef = ref(null)
const saving = ref(false)
const envNameLoading = ref(false)
const envNameOptions = ref([])
const isEdit = computed(() => props.envRow?.id != null && props.envRow?.id !== '')
const projectSelectOptions = computed(() =>
    (props.projectOptions || []).map((p) => ({ label: p.label, value: p.value }))
)

const form = reactive({
  project_id: undefined,
  env_type: ENV_TYPE.API,
  env_name: null,
  env_desc: '',
})

/** 加载全局环境枚举名称，供下拉选择；用户输入新值时由后端_get_or_create写入枚举表 */
async function loadEnvNameOptions() {
  envNameLoading.value = true
  try {
    const res = await api.getApiEnvNames()
    const names = (res?.data || [])
        .map((n) => String(n || '').trim().toUpperCase())
        .filter(Boolean)
    const unique = [...new Set(names)].sort((a, b) => a.localeCompare(b, 'zh-CN'))
    envNameOptions.value = unique.map((n) => ({ label: n, value: n }))
  } catch (_) {
    envNameOptions.value = []
  } finally {
    envNameLoading.value = false
  }
}

function ensureEnvNameOption(name) {
  const value = String(name || '').trim().toUpperCase()
  if (!value) return
  if (!envNameOptions.value.some((o) => o.value === value)) {
    envNameOptions.value = [...envNameOptions.value, { label: value, value }]
  }
  form.env_name = value
}

async function loadEditDetail() {
  form.project_id = Number(props.envRow.project_id)
  form.env_type = props.envRow.env_type || ENV_TYPE.API
  form.env_name = String(props.envRow.env_name || '').trim().toUpperCase() || null
  form.env_desc = ''
  ensureEnvNameOption(form.env_name)
  try {
    const res = await api.getEnv({ env_id: Number(props.envRow.id) })
    form.env_desc = res?.data?.env_desc || ''
  } catch (_) {
    /* 描述加载失败不影响弹窗 */
  }
}

async function handleSave() {
  try {
    saving.value = true
    // tag模式下可能是小写输入，统一规范为大写再校验
    if (form.env_name) {
      form.env_name = String(form.env_name).trim().toUpperCase()
      ensureEnvNameOption(form.env_name)
    }
    await formRef.value?.validate?.()
    if (isEdit.value) {
      await api.updateEnv({
        env_id: Number(props.envRow.id),
        env_name: form.env_name,
        project_id: Number(form.project_id),
        env_type: form.env_type,
        env_desc: form.env_desc || '',
        updated_user: userStore.username,
      })
    } else {
      await api.createEnv({
        project_id: form.project_id,
        env_name: form.env_name,
        env_type: form.env_type,
        env_desc: form.env_desc || undefined,
      })
    }
    window.$message?.success?.('保存成功')
    emit('saved')
    emit('update:show', false)
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

watch(
    () => props.show,
    async (v) => {
      if (!v) return
      await loadEnvNameOptions()
      if (isEdit.value) {
        await loadEditDetail()
      } else {
        form.project_id = undefined
        form.env_type = ENV_TYPE.API
        form.env_name = null
        form.env_desc = ''
      }
    }
)
</script>
