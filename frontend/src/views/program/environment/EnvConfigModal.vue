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
          <NInput v-model:value="form.config_name" maxlength="64"/>
        </NFormItem>
        <NFormItem
            label="环境"
            path="env"
            :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="form.env" maxlength="64" placeholder="如 SIT、UAT" :disabled="true"/>
        </NFormItem>

        <template v-if="configType === 1">
          <NFormItem
              label="IP地址"
              path="env_host"
              :rule="{ required: true, message: '请输入IP地址', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.env_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="端口"
              path="env_port"
              :rule="{ required: true, message: '请输入端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.env_port" maxlength="128"/>
          </NFormItem>
        </template>

        <template v-else-if="configType === 2">
          <NFormItem
              label="服务器IP"
              path="server_ip"
              :rule="{ required: true, message: '请输入服务器IP', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.server_ip" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="服务器端口"
              path="server_port"
              :rule="{ required: true, message: '请输入服务器端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.server_port" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="服务器账号"
              path="server_account"
              :rule="{ required: true, message: '请输入服务器账号', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.server_account" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="服务器密码"
              path="server_password"
              :rule="{ required: true, message: '请输入服务器密码', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.server_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
          <NFormItem label="是否免密" path="is_no_password">
            <NSelect
                v-model:value="form.is_no_password"
                :options="[{ label: '免密', value: 0 }, { label: '非免密', value: 1 }]"
            />
          </NFormItem>
        </template>

        <template v-else-if="configType === 3">
          <NFormItem
              label="数据库类型"
              path="db_type"
              :rule="{ required: true, message: '请选择数据库类型', trigger: ['change', 'blur'] }"
          >
            <NSelect v-model:value="form.db_type" :options="DB_TYPE_OPTIONS"/>
          </NFormItem>
          <NFormItem
              label="数据库名称"
              path="db_name"
              :rule="{ required: true, message: '请输入数据库名称', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.db_name" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库IP"
              path="db_host"
              :rule="{ required: true, message: '请输入数据库IP', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.db_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库端口"
              path="db_port"
              :rule="{ required: true, message: '请输入数据库端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.db_port" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库账号"
              path="db_user"
              :rule="{ required: true, message: '请输入数据库账号', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.db_user" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="数据库密码"
              path="db_password"
              :rule="{ required: true, message: '请输入数据库密码', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.db_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
        </template>

        <template v-else-if="configType === 4">
          <NFormItem
              label="Redis主机"
              path="redis_host"
              :rule="{ required: true, message: '请输入Redis主机', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.redis_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="Redis端口"
              path="redis_port"
              :rule="{ required: true, message: '请输入Redis端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.redis_port" maxlength="8"/>
          </NFormItem>
          <NFormItem label="库编号" path="redis_db">
            <NInput v-model:value="form.redis_db" maxlength="128" placeholder="默认 0"/>
          </NFormItem>
          <NFormItem label="用户名" path="redis_username">
            <NInput v-model:value="form.redis_username" maxlength="128" placeholder="可选"/>
          </NFormItem>
          <NFormItem label="密码" path="redis_password">
            <NInput v-model:value="form.redis_password" type="password" show-password-on="click" maxlength="128" placeholder="可选"/>
          </NFormItem>
        </template>

        <NFormItem
            label="维护人"
            path="maintainer"
            :rule="{ required: true, message: '请输入维护人', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="form.maintainer" maxlength="128"/>
        </NFormItem>
        <NFormItem label="备注" path="remark" class="full-row">
          <NInput v-model:value="form.remark" type="textarea" :rows="2" maxlength="256"/>
        </NFormItem>
      </div>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton v-if="configType === 3 && mode === 'edit'" :loading="testing" @click="handleTestConnection">
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

defineOptions({ name: '环境配置弹窗' })

const props = defineProps({
  show: { type: Boolean, default: false },
  /** create | edit | copy */
  mode: { type: String, default: 'create' },
  /** 1=APP 2=FILE 3=DB 4=REDIS */
  configType: { type: Number, required: true },
  /** 主表绑定行 */
  envRow: { type: Object, required: true },
  /** 编辑/复制时的配置行 */
  configRow: { type: Object, default: null },
})
const emit = defineEmits(['update:show', 'saved'])

const TYPE_LABEL = { 1: 'APP', 2: 'FILE', 3: 'DB', 4: 'REDIS' }
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
  id: undefined,
  config_name: '',
  env: '',
  env_host: '',
  env_port: '',
  server_ip: '',
  server_port: '',
  server_account: '',
  server_password: '',
  is_no_password: 1,
  db_name: '',
  db_host: '',
  db_port: '',
  db_user: '',
  db_password: '',
  db_type: 'mysql',
  redis_host: '',
  redis_port: '',
  redis_db: '0',
  redis_username: '',
  redis_password: '',
  maintainer: '',
  remark: '',
})

const modalTitle = computed(() => {
  const action = props.mode === 'edit' ? '编辑' : props.mode === 'copy' ? '复制' : '新增'
  return `${action}${TYPE_LABEL[props.configType] || ''}配置`
})

function currentMaintainer() {
  return userStore.username || 'ADMIN'
}

function resetForm() {
  Object.assign(form, {
    id: undefined,
    config_name: '',
    env: props.envRow?.env_name || '',
    env_host: '',
    env_port: '',
    server_ip: '',
    server_port: '',
    server_account: '',
    server_password: '',
    is_no_password: 1,
    db_name: '',
    db_host: '',
    db_port: '',
    db_user: '',
    db_password: '',
    db_type: 'mysql',
    redis_host: '',
    redis_port: '',
    redis_db: '0',
    redis_username: '',
    redis_password: '',
    maintainer: currentMaintainer(),
    remark: '',
  })
}

function fillFromRow(row, { asCopy = false } = {}) {
  const t = props.configType
  Object.assign(form, {
    id: asCopy ? undefined : row.id,
    config_name: asCopy ? `${row.config_name || ''}_copy` : (row.config_name || ''),
    env: props.envRow.env_name || '',
    env_host: t === 1 ? row.ip || '' : '',
    env_port: t === 1 ? row.port || '' : '',
    server_ip: t === 2 ? row.ip || '' : '',
    server_port: t === 2 ? row.port || '' : '',
    server_account: row.server_account || '',
    server_password: row.server_password || '',
    is_no_password: row.is_no_password ?? 1,
    db_name: row.db_name || '',
    db_host: t === 3 ? row.ip || '' : '',
    db_port: t === 3 ? row.port || '' : '',
    db_user: row.db_user || '',
    db_password: row.db_password || '',
    db_type: row.db_type || 'mysql',
    redis_host: t === 4 ? row.ip || '' : '',
    redis_port: t === 4 ? row.port || '' : '',
    redis_db: row.redis_db ?? '0',
    redis_username: row.redis_username || '',
    redis_password: row.redis_password || '',
    maintainer: row.maintainer || currentMaintainer(),
    remark: row.remark || '',
  })
}

function buildPayload() {
  const isEditMode = props.mode === 'edit'
  const base = {
    config_name: form.config_name,
    env: form.env,
    maintainer: form.maintainer,
    remark: form.remark || undefined,
  }
  if (isEditMode) {
    base.id = form.id
    base.project_id = String(props.envRow.project_id)
    base.updated_user = currentMaintainer()
  } else {
    base.env_info_id = Number(props.envRow.project_id)
    base.created_user = currentMaintainer()
  }
  const t = props.configType
  if (t === 1) Object.assign(base, { env_host: form.env_host, env_port: form.env_port })
  else if (t === 2) {
    Object.assign(base, {
      server_ip: form.server_ip,
      server_port: form.server_port,
      server_account: form.server_account,
      server_password: form.server_password,
      is_no_password: form.is_no_password,
    })
  } else if (t === 3) {
    Object.assign(base, {
      db_name: form.db_name,
      db_host: form.db_host,
      db_port: form.db_port,
      db_user: form.db_user,
      db_password: form.db_password,
      db_type: form.db_type,
    })
  } else if (t === 4) {
    Object.assign(base, {
      redis_host: form.redis_host,
      redis_port: form.redis_port,
      redis_db: form.redis_db || '0',
      redis_username: form.redis_username || '',
      redis_password: form.redis_password || '',
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
    if (t === 1) await (isEditMode ? api.updateAppEnvConfig(payload) : api.createAppEnvConfig(payload))
    else if (t === 2) await (isEditMode ? api.updateFileEnvConfig(payload) : api.createFileEnvConfig(payload))
    else if (t === 3) await (isEditMode ? api.updateDbEnvConfig(payload) : api.createDbEnvConfig(payload))
    else if (t === 4) await (isEditMode ? api.updateRedisEnvConfig(payload) : api.createRedisEnvConfig(payload))
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
      id: form.id,
      project_id: String(props.envRow.project_id),
      env_name: form.env,
      config_name: form.config_name,
      db_name: form.db_name,
    })
    if (res?.code === '000000' && res?.status === 'success') {
      window.$message?.success?.(res?.message || '连接成功')
    } else {
      window.$message?.error?.(res?.message || '连接失败')
    }
  } catch (e) {
    window.$message?.error?.(`连接失败：${e?.message || e}`)
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
