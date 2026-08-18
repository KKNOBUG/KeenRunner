<template>
  <NModal
      :show="show"
      preset="card"
      style="width: 860px"
      :title="modalTitle"
      @update:show="(v) => emit('update:show', v)"
  >
    <NForm ref="formRef" :model="form" label-placement="left" label-align="left" :label-width="100">
      <div class="config-grid">
        <NFormItem
            label="配置名称"
            path="config_name"
            :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="form.config_name" maxlength="128"/>
        </NFormItem>
        <NFormItem
            label="环境"
            path="env_name"
            :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="form.env_name" maxlength="64" placeholder="如 SIT、UAT" :disabled="true"/>
        </NFormItem>

        <template v-if="configType === ENV_TYPE.APP">
          <NFormItem
              label="主机地址"
              path="config_host"
              :rule="{ required: true, message: '请输入主机地址', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="端口"
              path="config_port"
              :rule="{ required: true, message: '请输入端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_port" maxlength="8"/>
          </NFormItem>
        </template>

        <template v-else-if="configType === ENV_TYPE.FILE">
          <NFormItem
              label="服务器IP"
              path="config_host"
              :rule="{ required: true, message: '请输入服务器IP', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="服务器端口"
              path="config_port"
              :rule="{ required: true, message: '请输入服务器端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_port" maxlength="8"/>
          </NFormItem>
          <NFormItem label="服务器账号" path="config_username">
            <NInput v-model:value="form.config_username" maxlength="128"/>
          </NFormItem>
          <NFormItem label="服务器密码" path="config_password">
            <NInput v-model:value="form.config_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
          <NFormItem label="是否免密" path="is_no_password">
            <NSelect
                v-model:value="form.is_no_password"
                :options="[{ label: '免密', value: true }, { label: '非免密', value: false }]"
            />
          </NFormItem>
        </template>

        <template v-else-if="configType === ENV_TYPE.DB">
          <NFormItem
              label="数据库类型"
              path="database_type"
              :rule="{ required: true, message: '请选择数据库类型', trigger: ['change', 'blur'] }"
          >
            <NSelect v-model:value="form.database_type" :options="DB_TYPE_OPTIONS"/>
          </NFormItem>
          <NFormItem
              label="数据库名称"
              path="database_name"
              :rule="{ required: true, message: '请输入数据库名称', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.database_name" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库IP"
              path="config_host"
              :rule="{ required: true, message: '请输入数据库IP', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库端口"
              path="config_port"
              :rule="{ required: true, message: '请输入数据库端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_port" maxlength="8"/>
          </NFormItem>
          <NFormItem
              label="数据库账号"
              path="config_username"
              :rule="{ required: true, message: '请输入数据库账号', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_username" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库密码"
              path="config_password"
              :rule="{ required: true, message: '请输入数据库密码', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
        </template>

        <template v-else-if="configType === ENV_TYPE.REDIS">
          <NFormItem
              label="Redis主机"
              path="config_host"
              :rule="{ required: true, message: '请输入Redis主机', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="Redis端口"
              path="config_port"
              :rule="{ required: true, message: '请输入Redis端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_port" maxlength="8"/>
          </NFormItem>
          <NFormItem label="库编号" path="database_name">
            <NInput v-model:value="form.database_name" maxlength="128" placeholder="可选，如 0"/>
          </NFormItem>
          <NFormItem label="用户名" path="config_username">
            <NInput v-model:value="form.config_username" maxlength="128" placeholder="可选"/>
          </NFormItem>
          <NFormItem label="密码" path="config_password">
            <NInput v-model:value="form.config_password" type="password" show-password-on="click" maxlength="128" placeholder="可选"/>
          </NFormItem>
        </template>

        <NFormItem label="备注" path="config_desc" class="full-row">
          <NInput v-model:value="form.config_desc" type="textarea" :rows="2" maxlength="2048"/>
        </NFormItem>
      </div>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton v-if="configType === ENV_TYPE.DB && mode === 'edit'" :loading="testing" @click="handleTestConnection">
          测试连接
        </NButton>
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
import { ENV_TYPE, ENV_TYPE_LABEL } from './envType'

defineOptions({ name: '环境配置弹窗' })

const props = defineProps({
  show: { type: Boolean, default: false },
  /** create | edit | copy */
  mode: { type: String, default: 'create' },
  /** app/file/database/redis */
  configType: { type: String, required: true },
  /** 主表绑定行 */
  envRow: { type: Object, required: true },
  /** 编辑/复制时的配置行 */
  configRow: { type: Object, default: null },
})
const emit = defineEmits(['update:show', 'saved'])

const DB_TYPE_OPTIONS = [
  { label: 'mysql', value: 'mysql' },
  { label: 'oracle', value: 'oracle' },
  { label: 'tdsql', value: 'tdsql' },
]

const userStore = useUserStore()
const formRef = ref(null)
const saving = ref(false)
const testing = ref(false)

const form = reactive({
  config_id: undefined,
  config_name: '',
  env_name: '',
  config_host: '',
  config_port: '',
  config_username: '',
  config_password: '',
  is_no_password: false,
  database_name: '',
  database_type: 'mysql',
  config_desc: '',
})

const modalTitle = computed(() => {
  const action = props.mode === 'edit' ? '编辑' : props.mode === 'copy' ? '复制' : '新增'
  return `${action}${ENV_TYPE_LABEL[props.configType] || ''}配置`
})

function currentUser() {
  return userStore.username || 'ADMIN'
}

function resetForm() {
  Object.assign(form, {
    config_id: undefined,
    config_name: '',
    env_name: props.envRow?.env_name || '',
    config_host: '',
    config_port: '',
    config_username: '',
    config_password: '',
    is_no_password: props.configType === ENV_TYPE.FILE ? true : false,
    database_name: '',
    database_type: 'mysql',
    config_desc: '',
  })
}

function fillFromRow(row, { asCopy = false } = {}) {
  Object.assign(form, {
    config_id: asCopy ? undefined : row.config_id,
    config_name: asCopy ? `${row.config_name || ''}_copy` : (row.config_name || ''),
    env_name: props.envRow.env_name || row.env_name || '',
    config_host: row.config_host || '',
    config_port: row.config_port || '',
    config_username: row.config_username || '',
    config_password: row.config_password || '',
    is_no_password: row.is_no_password ?? false,
    database_name: row.database_name || '',
    database_type: row.database_type || 'mysql',
    config_desc: row.config_desc || '',
  })
}

function buildPayload() {
  const isEditMode = props.mode === 'edit'
  const base = {
    config_name: form.config_name,
    env_name: form.env_name,
    config_host: form.config_host,
    config_port: form.config_port || undefined,
    config_desc: form.config_desc || undefined,
  }
  if (isEditMode) {
    base.config_id = form.config_id
    base.project_id = Number(props.envRow.project_id)
    base.updated_user = currentUser()
  } else {
    base.project_id = Number(props.envRow.project_id)
    base.created_user = currentUser()
  }

  const t = props.configType
  if (t === ENV_TYPE.FILE) {
    Object.assign(base, {
      config_username: form.config_username || '',
      config_password: form.config_password || '',
      is_no_password: !!form.is_no_password,
    })
  } else if (t === ENV_TYPE.DB) {
    Object.assign(base, {
      database_name: form.database_name,
      database_type: form.database_type,
      config_username: form.config_username,
      config_password: form.config_password,
    })
  } else if (t === ENV_TYPE.REDIS) {
    Object.assign(base, {
      database_name: form.database_name || undefined,
      config_username: form.config_username || undefined,
      config_password: form.config_password || undefined,
    })
  }
  return base
}

async function handleSave() {
  try {
    saving.value = true
    await formRef.value?.validate?.()
    const payload = buildPayload()
    const t = props.configType
    const isEditMode = props.mode === 'edit'
    if (t === ENV_TYPE.APP) await (isEditMode ? api.updateAppEnvConfig(payload) : api.createAppEnvConfig(payload))
    else if (t === ENV_TYPE.FILE) await (isEditMode ? api.updateFileEnvConfig(payload) : api.createFileEnvConfig(payload))
    else if (t === ENV_TYPE.DB) await (isEditMode ? api.updateDbEnvConfig(payload) : api.createDbEnvConfig(payload))
    else if (t === ENV_TYPE.REDIS) await (isEditMode ? api.updateRedisEnvConfig(payload) : api.createRedisEnvConfig(payload))
    window.$message?.success?.('保存成功')
    emit('saved')
    emit('update:show', false)
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

async function handleTestConnection() {
  try {
    testing.value = true
    const res = await api.testDbConnection({
      config_id: form.config_id,
      project_id: Number(props.envRow.project_id),
      env_name: form.env_name,
      config_name: form.config_name,
      database_name: form.database_name,
    })
    window.$message?.success?.(res?.message || '连接成功')
  } catch (e) {
    // 失败提示由请求拦截器统一处理；此处仅兜底无message场景
    if (!e?.message) window.$message?.error?.('连接失败')
  } finally {
    testing.value = false
  }
}

watch(
    () => props.show,
    (v) => {
      if (!v) return
      resetForm()
      if ((props.mode === 'edit' || props.mode === 'copy') && props.configRow) {
        fillFromRow(props.configRow, { asCopy: props.mode === 'copy' })
      }
    }
)
</script>

<style scoped>
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 18px;
}

.full-row {
  grid-column: 1 / -1;
}
</style>
