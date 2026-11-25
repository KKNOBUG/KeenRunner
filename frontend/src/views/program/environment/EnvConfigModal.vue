<template>
  <NModal
      :show="show"
      preset="card"
      class="env-config-modal"
      style="width: 560px; max-width: calc(100vw - 32px)"
      :title="modalTitle"
      @update:show="(v) => emit('update:show', v)"
  >
    <NForm ref="formRef" :model="form" label-placement="left" label-align="left" :label-width="100">
      <NCard tag="section" size="small" bordered class="config-section linked-section">
        <template #header>
          <NAlert type="info" :bordered="false" :show-icon="false" class="section-hint">
            <div class="section-hint-content">
              <span class="section-hint-title">联动字段</span>
              <span class="section-hint-desc">其他环境下的同名配置也会被同步修改</span>
            </div>
          </NAlert>
        </template>
        <NFormItem
            label="配置名称"
            path="config_name"
            :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="form.config_name" maxlength="128"/>
        </NFormItem>
      </NCard>

      <NCard tag="section" size="small" bordered class="config-section non-linked-section">
        <template #header>
          <NAlert type="info" :bordered="false" :show-icon="false" class="section-hint">
            <div class="section-hint-content">
              <span class="section-hint-title">非联动字段</span>
              <span class="section-hint-desc">其他环境下的具体配置不会被同步修改</span>
            </div>
          </NAlert>
        </template>

        <template v-if="configType === ENV_TYPE.APP">
          <NFormItem
              label="主机地址"
              path="config_host"
              :rule="{ required: true, message: '请输入主机地址', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_host" maxlength="128"/>
          </NFormItem>
          <NFormItem
              label="主机端口"
              path="config_port"
              :rule="{ required: true, message: '请输入主机端口', trigger: ['input', 'blur'] }"
          >
            <NInput v-model:value="form.config_port" maxlength="8"/>
          </NFormItem>
        </template>

        <template v-else-if="configType === ENV_TYPE.FILE">
          <NFormItem
              label="服务器地址"
              path="config_host"
              :rule="{ required: true, message: '请输入服务器地址', trigger: ['input', 'blur'] }"
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
              label="数据库地址"
              path="config_host"
              :rule="{ required: true, message: '请输入数据库地址', trigger: ['input', 'blur'] }"
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
          <NFormItem label="Redis库号" path="database_name">
            <NInput v-model:value="form.database_name" maxlength="128" placeholder="请输入Redis库号"/>
          </NFormItem>
          <NFormItem label="Redis账号" path="config_username">
            <NInput v-model:value="form.config_username" maxlength="128" placeholder="请输入Redis账号"/>
          </NFormItem>
          <NFormItem label="Redis密码" path="config_password">
            <NInput v-model:value="form.config_password" type="password" show-password-on="click" maxlength="128" placeholder="请输入Redis密码"/>
          </NFormItem>
        </template>

        <NFormItem label="备注" path="config_desc">
          <NInput v-model:value="form.config_desc" type="textarea" :rows="2" maxlength="2048" placeholder="请输入备注"/>
        </NFormItem>
      </NCard>
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
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, NModal, NSelect, NSpace } from 'naive-ui'
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
    // 可空字段显式传 null，后端才能区分“未修改”与“清空”
    config_port: form.config_port || null,
    config_desc: form.config_desc || null,
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
      database_name: form.database_name || null,
      config_username: form.config_username || null,
      config_password: form.config_password || null,
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
    },
    // 主表入口用 v-if 挂载弹窗并同时置 show=true，首次挂载不会产生 show 变更回调，需立即执行一次初始化
    { immediate: true }
)
</script>

<style scoped>
:global(.env-config-modal.n-card) {
  --env-config-modal-radius: 26px;
  --env-config-card-radius: 16px;
  border-radius: var(--env-config-modal-radius, 26px);
  corner-shape: squircle;
  overflow: hidden;
}

.env-config-modal > :deep(.n-card__content) {
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}

.config-section {
  border-radius: var(--env-config-card-radius, 16px);
  corner-shape: squircle;
  overflow: hidden;
  box-shadow: 0 2px 10px color-mix(in srgb, var(--n-border-color) 18%, transparent);
}

.linked-section {
  --env-linked-color: color-mix(in srgb, var(--primary-color, #F4511E) 10%, transparent);
  border-color: color-mix(in srgb, var(--primary-color, #F4511E) 22%, var(--n-border-color));
}

.non-linked-section {
  --env-non-linked-color: var(--info-color, #2080F0);
  border-color: color-mix(in srgb, var(--env-non-linked-color) 22%, var(--n-border-color));
}

.config-section + .config-section {
  margin-top: 8px;
}

.config-section :deep(.n-card-header) {
  padding: 0;
  /* 栏头自身保持直角，顶部由卡片的 squircle 溢出裁剪统一塑形 */
  border-radius: 0;
}

.linked-section :deep(.n-card-header) {
  background: var(--env-linked-color);
}

.linked-section .section-hint {
  background-color: transparent;
}

.linked-section .section-hint-title {
  color: var(--primary-color, #F4511E);
}

.non-linked-section .section-hint-title {
  color: var(--env-non-linked-color);
}

.config-section :deep(.n-card__content) {
  padding: 14px 16px 8px;
}

.section-hint {
  border-radius: 0;
}

.section-hint :deep(.n-alert-body) {
  padding: 10px 14px;
}

.section-hint-content {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  min-width: 0;
}

.section-hint-title {
  font-weight: 600;
}

.section-hint-desc {
  color: color-mix(in srgb, var(--n-content-text-color) 62%, transparent);
  font-size: 11px;
  line-height: 1.4;
}

.config-section :deep(.n-form-item) {
  margin-bottom: 8px;
}

.config-section :deep(.n-form-item:last-child) {
  margin-bottom: 0;
}

html.dark .linked-section {
  --env-linked-color: color-mix(in srgb, var(--primary-color, #F4511E) 15%, transparent);
}

html.dark .non-linked-section {
  --env-non-linked-color: var(--info-color-suppl, #4098FC);
}

html.dark .config-section {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.22);
}
</style>
