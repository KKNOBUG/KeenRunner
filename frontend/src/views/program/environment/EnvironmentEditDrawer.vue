<template>
  <NDrawer :show="show" :width="1200" placement="right" @update:show="(v) => emit('update:show', v)">
    <NDrawerContent :title="drawerTitle" closable @close="closeDrawer" class="env-drawer-content">
      <!-- 环境主表信息（节点类型决定子表类型；子表配置会自动创建对应环境枚举） -->
      <NCard size="small" :bordered="false" class="env-basic-card">
        <NForm ref="envFormRef" :model="envForm" label-placement="left" label-align="left" :label-width="90">
          <div class="env-grid">
            <NFormItem
                label="应用名称"
                path="project_id"
                :rule="{ required: true, type: 'number', message: '请选择应用名称', trigger: ['change', 'blur'] }"
            >
              <NSelect
                  v-model:value="envForm.project_id"
                  :options="projectSelectOptions"
                  :disabled="isEdit"
                  clearable
                  filterable
                  placeholder="请选择应用"
              />
            </NFormItem>
            <NFormItem
                label="节点类型"
                path="env_type"
                :rule="{ required: true, type: 'number', message: '请选择节点类型', trigger: ['change', 'blur'] }"
            >
              <NSelect
                  v-model:value="envForm.env_type"
                  :options="ENV_TYPE_OPTIONS"
                  :disabled="isEdit"
                  placeholder="APP / FILE / DB"
              />
            </NFormItem>
            <NFormItem
                label="环境名称"
                path="env_name"
                :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }"
            >
              <NInput
                  v-model:value="envForm.env_name"
                  maxlength="64"
                  clearable
                  placeholder="如 SIT、UAT（自动转为大写）"
              />
            </NFormItem>
            <NFormItem label="环境说明" path="env_desc" class="full-row">
              <NInput
                  v-model:value="envForm.env_desc"
                  type="textarea"
                  maxlength="2048"
                  show-count
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  placeholder="可选：说明该环境用途或接入范围"
              />
            </NFormItem>
          </div>
          <NSpace justify="end">
            <NButton size="small" type="primary" :loading="saving" @click="saveEnv">保存环境</NButton>
          </NSpace>
        </NForm>
      </NCard>

      <!-- 子表配置 -->
      <div class="sub-table-wrap">
        <div class="sub-table-header">
          <span class="sub-table-title">
            {{ subTableTitle }}
            <span v-if="isEdit" class="sub-table-env">环境：{{ envForm.env_name || '-' }}</span>
          </span>
          <NButton size="small" type="primary" @click="openCreateConfig">新增配置</NButton>
        </div>
        <NDataTable
            :columns="configColumns"
            :data="configRows"
            :loading="configLoading"
            :pagination="configPagination"
            :scroll-x="1000"
            size="small"
            :bordered="false"
            :single-line="true"
            remote
            @update:page="(p) => loadConfigList(p)"
        />
      </div>

      <template #footer>
        <NButton @click="closeDrawer">关闭</NButton>
      </template>
    </NDrawerContent>
  </NDrawer>

  <!-- 子表配置 Modal（按节点类型渲染对应字段） -->
  <NModal v-model:show="configModalShow" preset="card" style="width: 860px" :title="configModalTitle">
    <NForm ref="configFormRef" :model="configForm" label-placement="left" label-align="left" :label-width="100">
      <div class="config-grid">
        <NFormItem label="配置名称" path="config_name"
                   :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }">
          <NInput v-model:value="configForm.config_name" maxlength="64"/>
        </NFormItem>
        <NFormItem label="环境" path="env"
                   :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }">
          <NInput v-model:value="configForm.env" maxlength="64" placeholder="如 SIT、UAT"/>
        </NFormItem>

        <!-- APP -->
        <template v-if="envType === 1">
          <NFormItem label="IP地址" path="env_host"
                     :rule="{ required: true, message: '请输入IP地址', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.env_host" maxlength="128"/>
          </NFormItem>
          <NFormItem label="端口" path="env_port"
                     :rule="{ required: true, message: '请输入端口', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.env_port" maxlength="128"/>
          </NFormItem>
        </template>

        <!-- FILE -->
        <template v-else-if="envType === 2">
          <NFormItem label="服务器IP" path="server_ip"
                     :rule="{ required: true, message: '请输入服务器IP', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.server_ip" maxlength="128"/>
          </NFormItem>
          <NFormItem label="服务器端口" path="server_port"
                     :rule="{ required: true, message: '请输入服务器端口', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.server_port" maxlength="128"/>
          </NFormItem>
          <NFormItem label="服务器账号" path="server_account"
                     :rule="{ required: true, message: '请输入服务器账号', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.server_account" maxlength="128"/>
          </NFormItem>
          <NFormItem label="服务器密码" path="server_password"
                     :rule="{ required: true, message: '请输入服务器密码', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.server_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
          <NFormItem label="是否免密" path="is_no_password">
            <NSelect
                v-model:value="configForm.is_no_password"
                :options="[{ label: '免密', value: 0 }, { label: '非免密', value: 1 }]"
            />
          </NFormItem>
        </template>

        <!-- DB -->
        <template v-else-if="envType === 3">
          <NFormItem label="数据库类型" path="db_type"
                     :rule="{ required: true, message: '请选择数据库类型', trigger: ['change', 'blur'] }">
            <NSelect v-model:value="configForm.db_type" :options="DB_TYPE_OPTIONS"/>
          </NFormItem>
          <NFormItem label="数据库名称" path="db_name"
                     :rule="{ required: true, message: '请输入数据库名称', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.db_name" maxlength="128"/>
          </NFormItem>
          <NFormItem label="数据库IP" path="db_host"
                     :rule="{ required: true, message: '请输入数据库IP', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.db_host" maxlength="128"/>
          </NFormItem>
          <NFormItem label="数据库端口" path="db_port"
                     :rule="{ required: true, message: '请输入数据库端口', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.db_port" maxlength="128"/>
          </NFormItem>
          <NFormItem label="数据库账号" path="db_user"
                     :rule="{ required: true, message: '请输入数据库账号', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.db_user" maxlength="128"/>
          </NFormItem>
          <NFormItem label="数据库密码" path="db_password"
                     :rule="{ required: true, message: '请输入数据库密码', trigger: ['input', 'blur'] }">
            <NInput v-model:value="configForm.db_password" type="password" show-password-on="click" maxlength="128"/>
          </NFormItem>
        </template>

        <NFormItem label="维护人" path="maintainer"
                   :rule="{ required: true, message: '请输入维护人', trigger: ['input', 'blur'] }">
          <NInput v-model:value="configForm.maintainer" maxlength="128"/>
        </NFormItem>
        <NFormItem label="备注" path="remark" class="full-row">
          <NInput v-model:value="configForm.remark" type="textarea" :rows="2" maxlength="256"/>
        </NFormItem>
      </div>
      <NSpace justify="end">
        <NButton v-if="envType === 3 && configModalMode === 'edit'" :loading="testing" @click="handleTestConnection">
          测试连接
        </NButton>
        <NButton @click="configModalShow = false">取消</NButton>
        <NButton type="primary" :loading="configSaving" @click="submitConfig">保存</NButton>
      </NSpace>
    </NForm>
  </NModal>
</template>

<script setup>
import { computed, h, reactive, ref, resolveDirective, watch, withDirectives } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
} from 'naive-ui'
import api from '@/api'
import { apiPermissionKey, renderIcon } from '@/utils'
import { useUserStore } from '@/store'

defineOptions({ name: '环境明细编辑' })

const vPermission = resolveDirective('permission')
const userStore = useUserStore()

const props = defineProps({
  show: { type: Boolean, default: false },
  /** 主表行：{ id, project_id, project_name, env_name, env_type, ... }；新增时为 null */
  envRow: { type: Object, default: null },
  projectOptions: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:show', 'saved'])

const ENV_TYPE_OPTIONS = [
  { label: 'APP', value: 1 },
  { label: 'FILE', value: 2 },
  { label: 'DB', value: 3 },
]
const DB_TYPE_OPTIONS = [
  { label: 'mysql', value: 'mysql' },
  { label: 'oracle', value: 'oracle' },
  { label: 'tdsql', value: 'tdsql' },
]
const ENV_TYPE_LABEL = { 1: 'APP', 2: 'FILE', 3: 'DB' }

const isEdit = computed(() => props.envRow?.id != null && props.envRow?.id !== '')
const envType = computed(() => (isEdit.value ? Number(props.envRow.env_type) : Number(envForm.env_type || 1)))
const drawerTitle = computed(() => (isEdit.value ? `环境配置明细 - ${props.envRow.env_name}` : '新建环境'))
const subTableTitle = computed(() => `${ENV_TYPE_LABEL[envType.value] || ''} 环境配置（子表）`)

// ---------- 主表 ----------
const envFormRef = ref(null)
const envForm = reactive({
  project_id: undefined,
  env_type: 1,
  env_name: '',
  env_desc: '',
})
const saving = ref(false)

const projectSelectOptions = computed(() =>
    (props.projectOptions || []).map((p) => ({ label: p.label, value: p.value }))
)

async function saveEnv() {
  try {
    saving.value = true
    await envFormRef.value?.validate?.()
    const payload = {
      project_id: envForm.project_id,
      env_name: envForm.env_name,
      env_type: envForm.env_type,
      env_desc: envForm.env_desc || undefined,
      ...(isEdit.value ? { env_id: Number(props.envRow.id), updated_user: userStore.username } : {}),
    }
    if (isEdit.value) {
      await api.updateEnv(payload)
    } else {
      await api.createEnv(payload)
    }
    window.$message?.success?.('环境保存成功')
    emit('saved')
    if (!isEdit.value) closeDrawer()
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`环境保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

// ---------- 子表 ----------
const configRows = ref([])
const configLoading = ref(false)
const configPagination = reactive({ page: 1, pageSize: 10, itemCount: 0, showSizePicker: true, pageSizes: [10, 20, 50] })

async function loadConfigList(page = 1) {
  if (!isEdit.value) {
    configRows.value = []
    configPagination.itemCount = 0
    return
  }
  configLoading.value = true
  try {
    const res = await api.getEnvConfigList({
      env_info_id: Number(props.envRow.project_id),
      env_name: props.envRow.env_name,
      env_type: Number(props.envRow.env_type),
      page,
      page_size: configPagination.pageSize,
    })
    configRows.value = res?.data || []
    configPagination.page = page
    configPagination.itemCount = res?.total || 0
  } catch (_) {
    configRows.value = []
    configPagination.itemCount = 0
  } finally {
    configLoading.value = false
  }
}

const configColumns = computed(() => {
  const base = [
    { title: '配置名称', key: 'config_name', align: 'center', ellipsis: { tooltip: true } },
    { title: 'IP地址', key: 'ip', align: 'center', ellipsis: { tooltip: true } },
    { title: '端口', key: 'port', align: 'center', width: 90 },
  ]
  if (envType.value === 3) {
    base.push({ title: '数据库名称', key: 'db_name', align: 'center', ellipsis: { tooltip: true } })
    base.push({ title: '数据库类型', key: 'db_type', align: 'center', width: 100 })
    base.push({ title: '数据库账号', key: 'db_user', align: 'center', width: 110, ellipsis: { tooltip: true } })
  } else if (envType.value === 2) {
    base.push({ title: '服务器账号', key: 'server_account', align: 'center', width: 110, ellipsis: { tooltip: true } })
    base.push({
      title: '是否免密', key: 'is_no_password', align: 'center', width: 90,
      render: (row) => (row.is_no_password === 0 ? '免密' : row.is_no_password === 1 ? '非免密' : '-'),
    })
  }
  base.push({ title: '维护人', key: 'maintainer', align: 'center', width: 100, ellipsis: { tooltip: true } })
  base.push({ title: '更新时间', key: 'updated_time', align: 'center', width: 170, ellipsis: { tooltip: true } })
  base.push({
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 120,
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
            h(NButton, { size: 'tiny', quaternary: true, type: 'info', onClick: () => openEditConfig(row) },
                { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }),
            [[vPermission, apiPermissionKey('post', '/autotest/config/app/update')]]
        ),
        h(NPopconfirm, { onPositiveClick: () => deleteConfig(row), onNegativeClick: () => {} }, {
          trigger: () =>
              withDirectives(
                  h(NButton, { size: 'tiny', quaternary: true, type: 'error' },
                      { default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }),
                  [[vPermission, apiPermissionKey('post', '/autotest/config/delete')]]
              ),
          default: () => h('div', {}, '确定删除该配置吗?'),
        }),
      ]
    },
  })
  return base
})

// ---------- 子表新增 / 编辑 Modal ----------
const configModalShow = ref(false)
const configModalMode = ref('create')
const configSaving = ref(false)
const testing = ref(false)
const configFormRef = ref(null)
const configForm = reactive({
  id: undefined,
  config_name: '',
  env: '',
  // APP
  env_host: '',
  env_port: '',
  // FILE
  server_ip: '',
  server_port: '',
  server_account: '',
  server_password: '',
  is_no_password: 1,
  // DB
  db_name: '',
  db_host: '',
  db_port: '',
  db_user: '',
  db_password: '',
  db_type: 'mysql',
  // 公共
  maintainer: '',
  remark: '',
})

const configModalTitle = computed(() => {
  const action = configModalMode.value === 'edit' ? '编辑' : '新增'
  return `${action}${ENV_TYPE_LABEL[envType.value] || ''}配置`
})

function currentMaintainer() {
  return userStore.username || 'ADMIN'
}

function resetConfigForm() {
  Object.assign(configForm, {
    id: undefined,
    config_name: '',
    env: envForm.env_name || '',
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
    maintainer: currentMaintainer(),
    remark: '',
  })
}

function openCreateConfig() {
  if (!isEdit.value) return window.$message?.warning?.('请先保存环境基本信息')
  configModalMode.value = 'create'
  resetConfigForm()
  configModalShow.value = true
}

function openEditConfig(row) {
  configModalMode.value = 'edit'
  resetConfigForm()
  Object.assign(configForm, {
    id: row.id,
    config_name: row.config_name || '',
    env: props.envRow.env_name || '',
    env_host: envType.value === 1 ? row.ip || '' : '',
    env_port: envType.value === 1 ? row.port || '' : '',
    server_ip: envType.value === 2 ? row.ip || '' : '',
    server_port: envType.value === 2 ? row.port || '' : '',
    server_account: row.server_account || '',
    server_password: row.server_password || '',
    is_no_password: row.is_no_password ?? 1,
    db_name: row.db_name || '',
    db_host: envType.value === 3 ? row.ip || '' : '',
    db_port: envType.value === 3 ? row.port || '' : '',
    db_user: row.db_user || '',
    db_password: row.db_password || '',
    db_type: row.db_type || 'mysql',
    maintainer: row.maintainer || currentMaintainer(),
    remark: row.remark || '',
  })
  configModalShow.value = true
}

function buildPayload() {
  const base = {
    config_name: configForm.config_name,
    env: configForm.env,
    maintainer: configForm.maintainer,
    remark: configForm.remark || undefined,
  }
  if (configModalMode.value === 'edit') {
    base.id = configForm.id
    base.project_id = String(props.envRow.project_id)
    base.updated_user = currentMaintainer()
  } else {
    base.env_info_id = Number(props.envRow.project_id)
    base.created_user = currentMaintainer()
  }
  if (envType.value === 1) {
    Object.assign(base, { env_host: configForm.env_host, env_port: configForm.env_port })
  } else if (envType.value === 2) {
    Object.assign(base, {
      server_ip: configForm.server_ip,
      server_port: configForm.server_port,
      server_account: configForm.server_account,
      server_password: configForm.server_password,
      is_no_password: configForm.is_no_password,
    })
  } else if (envType.value === 3) {
    Object.assign(base, {
      db_name: configForm.db_name,
      db_host: configForm.db_host,
      db_port: configForm.db_port,
      db_user: configForm.db_user,
      db_password: configForm.db_password,
      db_type: configForm.db_type,
    })
  }
  return base
}

async function submitConfig() {
  try {
    configSaving.value = true
    await configFormRef.value?.validate?.()
    const payload = buildPayload()
    const t = envType.value
    if (configModalMode.value === 'edit') {
      if (t === 1) await api.updateAppEnvConfig(payload)
      else if (t === 2) await api.updateFileEnvConfig(payload)
      else if (t === 3) await api.updateDbEnvConfig(payload)
    } else {
      if (t === 1) await api.createAppEnvConfig(payload)
      else if (t === 2) await api.createFileEnvConfig(payload)
      else if (t === 3) await api.createDbEnvConfig(payload)
    }
    configModalShow.value = false
    window.$message?.success?.('保存成功')
    emit('saved')
    loadConfigList(configPagination.page)
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`保存失败：${e?.message || e}`)
  } finally {
    configSaving.value = false
  }
}

async function deleteConfig(row) {
  try {
    await api.deleteEnvConfig({ id: row.id, env_type: envType.value, updated_user: currentMaintainer() })
    window.$message?.success?.('删除成功')
    emit('saved')
    loadConfigList(configPagination.page)
  } catch (e) {
    window.$message?.error?.(`删除失败：${e?.message || e}`)
  }
}

async function handleTestConnection() {
  try {
    testing.value = true
    const res = await api.testDbConnection({
      id: configForm.id,
      project_id: String(props.envRow.project_id),
      env_name: configForm.env,
      config_name: configForm.config_name,
      db_name: configForm.db_name,
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

function closeDrawer() {
  configModalShow.value = false
  emit('update:show', false)
}

watch(() => props.show, (v) => {
  if (!v) {
    configModalShow.value = false
    return
  }
  // 初始化主表表单
  if (isEdit.value) {
    envForm.project_id = Number(props.envRow.project_id)
    envForm.env_type = Number(props.envRow.env_type)
    envForm.env_name = props.envRow.env_name || ''
    envForm.env_desc = ''
  } else {
    envForm.project_id = undefined
    envForm.env_type = 1
    envForm.env_name = ''
    envForm.env_desc = ''
  }
  configPagination.page = 1
  loadConfigList(1)
})
</script>

<style scoped>
.env-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px 18px;
}

.full-row {
  grid-column: 1 / -1;
}

.env-basic-card :deep(.n-form) {
  padding-top: 4px;
}

.sub-table-wrap {
  margin-top: 14px;
}

.sub-table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.sub-table-title {
  font-size: 14px;
  font-weight: 600;
}

.sub-table-env {
  margin-left: 10px;
  font-weight: 400;
  color: var(--n-text-color-3);
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 18px;
}

.env-drawer-content {
  font-size: 14px;
}

.env-drawer-content :deep(*) {
  font-size: inherit;
}
</style>
