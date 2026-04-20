<template>
  <NDrawer :show="show" :width="1200" placement="right" @update:show="(v) => emit('update:show', v)">
    <NDrawerContent :title="drawerTitle" closable @close="closeDrawer" class="env-drawer-content">
      <NCard size="small" :bordered="false">
        <NForm ref="envFormRef" :model="envForm" label-placement="left" label-align="left" :label-width="90">
          <div class="env-grid">
            <NFormItem label="环境名称" path="env_name"
                       :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }">
              <NInput v-model:value="envForm.env_name"/>
            </NFormItem>
            <NFormItem label="环境说明" path="env_desc" class="full-row">
              <NInput v-model:value="envForm.env_desc" type="textarea" :rows="3"/>
            </NFormItem>
          </div>
        </NForm>
      </NCard>
      <div class="tabs-wrap">
        <NTabs v-model:value="activeTab" type="line" animated>
          <NTabPane name="app" tab="应用配置">
            <CrudTable
                ref="appTableRef"
                v-model:query-items="tabQuery.app"
                :is-pagination="true"
                :columns="appColumns"
                :get-data="getAppConfigData"
                :single-line="true"
                :scroll-x="1200"
            >
              <template #queryBar>
                <QueryBarItem label="应用名称：" :label-width="90">
                  <NSelect
                      v-model:value="tabQuery.app.project_id"
                      :options="projectSelectOptions"
                      clearable
                      filterable
                      placeholder="应用名称"
                  />
                </QueryBarItem>
                <QueryBarItem label="配置名称：" :label-width="90">
                  <NInput
                      v-model:value="tabQuery.app.config_name"
                      clearable
                      placeholder="请输入配置名称"
                  />
                </QueryBarItem>
              </template>
              <template #action>
                <NButton type="primary" @click="openCreateAppConfig">新增</NButton>
              </template>
            </CrudTable>
          </NTabPane>

          <NTabPane name="database" tab="数据库配置">
            <CrudTable
                ref="databaseTableRef"
                v-model:query-items="tabQuery.database"
                :is-pagination="true"
                :columns="infraColumns"
                :get-data="getDatabaseConfigData"
                :single-line="true"
                :scroll-x="1200"
            >
              <template #queryBar>
                <QueryBarItem label="应用名称：" :label-width="90">
                  <NSelect
                      v-model:value="tabQuery.database.project_id"
                      :options="projectSelectOptions"
                      clearable
                      filterable
                      placeholder="应用名称"
                  />
                </QueryBarItem>
                <QueryBarItem label="配置名称：" :label-width="90">
                  <NInput
                      v-model:value="tabQuery.database.config_name"
                      clearable
                      placeholder="请输入配置名称"
                  />
                </QueryBarItem>
                <QueryBarItem label="分组编号：" :label-width="90">
                  <NInput
                      v-model:value="tabQuery.database.config_group"
                      clearable
                      placeholder="分组编号"
                  />
                </QueryBarItem>
              </template>
              <template #action>
                <NButton type="primary" @click="openCreateDatabaseConfig">新增</NButton>
              </template>
            </CrudTable>
          </NTabPane>

          <NTabPane name="file" tab="文件服务器配置">
            <CrudTable
                ref="fileTableRef"
                v-model:query-items="tabQuery.file"
                :is-pagination="true"
                :columns="infraColumns"
                :get-data="getFileConfigData"
                :single-line="true"
                :scroll-x="1200"
            >
              <template #queryBar>
                <QueryBarItem label="应用名称：" :label-width="90">
                  <NSelect
                      v-model:value="tabQuery.file.project_id"
                      :options="projectSelectOptions"
                      clearable
                      filterable
                      placeholder="应用名称"
                  />
                </QueryBarItem>
                <QueryBarItem label="配置名称：" :label-width="90">
                  <NInput
                      v-model:value="tabQuery.file.config_name"
                      clearable
                      placeholder="请输入配置名称"
                  />
                </QueryBarItem>
                <QueryBarItem label="是否免密：" :label-width="90">
                  <NSelect
                      v-model:value="tabQuery.file.is_authorization"
                      :options="[{ label: '免密', value: true }, { label: '非免密', value: false }]"
                      clearable
                      placeholder="是否免密"
                      style="width: 160px"
                  />
                </QueryBarItem>
              </template>
              <template #action>
                <NButton type="primary" @click="openCreateFileConfig">新增</NButton>
              </template>
            </CrudTable>
          </NTabPane>
        </NTabs>
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="closeDrawer">关闭</NButton>
          <NButton type="primary" :loading="saving" @click="saveEnv">保存环境</NButton>
        </NSpace>
      </template>
    </NDrawerContent>
  </NDrawer>
  <!-- 应用配置 Modal -->
  <NModal v-model:show="appModalShow" preset="card" style="width: 900px"
          :title="appModalMode === 'edit' ? '编辑应用配置' : '新增应用配置'">
    <NForm ref="appFormRef" :model="appForm" label-placement="left" label-align="left" :label-width="90">
      <div class="app-grid">
        <NFormItem label="配置名称" path="config_name"
                   :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }">
          <NInput v-model:value="appForm.config_name"/>
        </NFormItem>
        <NFormItem label="应用名称" path="project_id"
                   :rule="{ required: true, type: 'number', message: '请选择应用名称', trigger: ['change', 'blur'] }">
          <NSelect v-model:value="appForm.project_id" :options="projectSelectOptions" clearable filterable/>
        </NFormItem>
        <NFormItem label="应用主机" path="config_host"
                   :rule="{ required: true, message: '请输入应用主机', trigger: ['input', 'blur'] }">
          <NInput v-model:value="appForm.config_host"/>
        </NFormItem>
        <NFormItem label="应用端口" path="config_port">
          <NInput v-model:value="appForm.config_port"/>
        </NFormItem>
        <NFormItem label="应用描述" path="config_desc" class="full-row">
          <NInput v-model:value="appForm.config_desc" type="textarea" :rows="2"/>
        </NFormItem>
        <NFormItem label="请求头" class="full-row">
          <KeyValueEditor v-model:items="appForm.headers" :body-type="'none'" :is-for-body="false"/>
        </NFormItem>
        <NFormItem label="环境变量" class="full-row">
          <KeyValueEditor v-model:items="appForm.variables" :body-type="'none'" :is-for-body="false"/>
        </NFormItem>
      </div>
      <NSpace justify="end">
        <NButton @click="appModalShow = false">取消</NButton>
        <NButton type="primary" :loading="appModalSaving" @click="submitAppConfig">保存</NButton>
      </NSpace>
    </NForm>
  </NModal>

  <!-- 基础设施配置 Modal -->
  <NModal v-model:show="infraModalShow" preset="card" style="width: 900px"
          :title="infraModalMode === 'edit' ? '编辑配置' : '新增配置'">
    <NForm ref="infraFormRef" :model="infraForm" label-placement="left" label-align="left" :label-width="100">
      <div class="infra-grid">
        <NFormItem label="应用名称" path="project_id"
                   :rule="{ required: true, type: 'number', message: '请选择应用名称', trigger: ['change', 'blur'] }">
          <NSelect v-model:value="infraForm.project_id" :options="projectSelectOptions" clearable filterable/>
        </NFormItem>
        <NFormItem label="配置名称" path="config_name"
                   :rule="{ required: true, message: '请输入配置名称', trigger: ['input', 'blur'] }">
          <NInput v-model:value="infraForm.config_name"/>
        </NFormItem>
        <NFormItem v-if="isInfraDatabase" label="数据库类型" path="database_type"
                   :rule="{ required: true, message: '请选择数据库类型', trigger: ['change', 'blur'] }">
          <NSelect v-model:value="infraForm.database_type"
                   :options="[{ label: 'mysql', value: 'mysql' }, { label: 'oracle', value: 'oracle' }, { label: 'tdsql', value: 'tdsql' }]"
                   clearable/>
        </NFormItem>
        <NFormItem label="主机地址" path="config_host"
                   :rule="{ required: true, message: '请输入主机地址', trigger: ['input', 'blur'] }">
          <NInput v-model:value="infraForm.config_host"/>
        </NFormItem>
        <NFormItem label="主机端口" path="config_port"
                   :rule="{ required: isInfraDatabase, message: '数据库配置必须输入主机端口', trigger: ['input', 'blur'] }">
          <NInput v-model:value="infraForm.config_port"/>
        </NFormItem>
        <NFormItem label="主机账号" path="config_username"
                   :rule="{ required: isInfraDatabase, message: '数据库配置必须输入主机账号', trigger: ['input', 'blur'] }">
          <NInput v-model:value="infraForm.config_username"/>
        </NFormItem>
        <NFormItem label="主机密码" path="config_password"
                   :rule="{ required: isInfraDatabase, message: '数据库配置必须输入主机密码', trigger: ['input', 'blur'] }">
          <NInput v-model:value="infraForm.config_password" type="password" show-password-on="click"/>
        </NFormItem>
        <NFormItem v-if="isInfraDatabase" label="分组编号" path="config_group"
                   :rule="{ required: infraForm.database_type === 'tdsql', message: '数据库类型为 tdsql 时必须输入分组编号', trigger: ['input', 'blur', 'change'] }">
          <NInput v-model:value="infraForm.config_group"/>
        </NFormItem>
        <NFormItem v-if="!isInfraDatabase" label="是否免密" path="is_authorization">
          <NCheckbox v-model:checked="infraForm.is_authorization">免密/无需认证</NCheckbox>
        </NFormItem>
        <NFormItem label="额外参数" path="config_params_json" class="full-row">
          <NInput v-model:value="infraForm.config_params_json" type="textarea" :rows="4"/>
        </NFormItem>
        <NFormItem label="配置描述" path="config_desc" class="full-row">
          <NInput v-model:value="infraForm.config_desc" type="textarea" :rows="3"/>
        </NFormItem>
      </div>
      <NSpace justify="end">
        <NButton @click="infraModalShow = false">取消</NButton>
        <NButton type="primary" :loading="infraModalSaving" @click="submitInfraConfig">保存</NButton>
      </NSpace>
    </NForm>
  </NModal>
</template>

<script setup>
import {computed, h, nextTick, reactive, ref, watch} from 'vue'
import {
  NButton,
  NCheckbox,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
} from 'naive-ui'
import api from '@/api'
import {renderIcon} from '@/utils'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from "@/components/table/CrudTable.vue"

defineOptions({name: '环境明细编辑'})

const props = defineProps({
  show: {type: Boolean, default: false},
  envId: {type: Number, default: undefined},
  envRow: {type: Object, default: null},
  defaultProjectId: {type: Number, default: undefined},
  projectOptions: {type: Array, default: () => []},
})
const emit = defineEmits(['update:show', 'saved'])

const TAB_TYPE_MAP = {app: 'api', database: 'database', file: 'file'}

const activeTab = ref('app')
const drawerTitle = computed(() => (currentEnvId.value ? '环境明细编辑' : '新建环境'))

const envFormRef = ref(null)
const envForm = reactive({
  env_id: undefined,
  env_code: '',
  project_id: undefined,
  env_name: '',
  env_desc: '',
})
const saving = ref(false)
const currentEnvId = computed(() => envForm.env_id || props.envId)

const projectSelectOptions = ref([])

// CrudTable 引用
const appTableRef = ref(null)
const databaseTableRef = ref(null)
const fileTableRef = ref(null)

// 查询参数
const tabQuery = reactive({
  app: {project_id: null, config_name: '', config_host: '', created_user: ''},
  database: {project_id: null, config_name: '', config_host: '', config_group: ''},
  file: {project_id: null, config_name: '', config_host: '', is_authorization: null},
})

async function loadProjectOptions() {
  try {
    const res = await api.getProjectList({page: 1, page_size: 9999, state: 0})
    projectSelectOptions.value = (res?.data || []).map((p) => ({
      label: p.project_name || p.project_code,
      value: p.project_id
    }))
  } catch (_) {
    projectSelectOptions.value = Array.isArray(props.projectOptions) ? props.projectOptions : []
  }
}

// 获取数据的方法
async function getAppConfigData(params) {
  if (!currentEnvId.value) return {data: [], total: 0}
  const payload = {
    env_id: currentEnvId.value,
    config_type: 'api',
    page: params.page,
    page_size: params.page_size,
    state: 0,
    project_id: params.project_id || undefined,
    config_name: params.config_name || undefined,
    config_host: params.config_host || undefined,
    created_user: params.created_user || undefined,
  }
  const res = await api.searchEnvConfig(payload)
  return {data: res?.data || [], total: res?.total || 0}
}

async function getDatabaseConfigData(params) {
  if (!currentEnvId.value) return {data: [], total: 0}
  const payload = {
    env_id: currentEnvId.value,
    config_type: 'database',
    page: params.page,
    page_size: params.page_size,
    state: 0,
    project_id: params.project_id || undefined,
    config_name: params.config_name || undefined,
    config_host: params.config_host || undefined,
    config_group: params.config_group || undefined,
  }
  const res = await api.searchEnvConfig(payload)
  return {data: res?.data || [], total: res?.total || 0}
}

async function getFileConfigData(params) {
  if (!currentEnvId.value) return {data: [], total: 0}
  const payload = {
    env_id: currentEnvId.value,
    config_type: 'file',
    page: params.page,
    page_size: params.page_size,
    state: 0,
    project_id: params.project_id || undefined,
    config_name: params.config_name || undefined,
    config_host: params.config_host || undefined,
    is_authorization: params.is_authorization !== null ? params.is_authorization : undefined,
  }
  const res = await api.searchEnvConfig(payload)
  return {data: res?.data || [], total: res?.total || 0}
}

// 删除配置
async function deleteConfig(row) {
  try {
    await api.deleteEnvConfig({config_id: row.config_id})
    window.$message?.success?.('删除成功')
    // 刷新当前表格
    const tableRef = getCurrentTableRef()
    tableRef?.handleSearch()
  } catch (e) {
    window.$message?.error?.(`删除失败：${e?.message || e}`)
  }
}

function getCurrentTableRef() {
  const tabMap = {
    app: appTableRef,
    database: databaseTableRef,
    file: fileTableRef
  }
  return tabMap[activeTab.value]?.value
}

// 应用配置列定义
const appColumns = [
  {title: '应用名称', key: 'project_name', align: 'center', ellipsis: {tooltip: true}},
  {title: '配置名称', key: 'config_name', align: 'center', ellipsis: {tooltip: true}},
  {title: '应用主机', key: 'config_host', align: 'center', ellipsis: {tooltip: true}},
  {title: '应用端口', key: 'config_port', align: 'center', width: 100},
  {title: '创建人员', key: 'created_user', align: 'center', width: 100},
  {title: '更新时间', key: 'updated_time', align: 'center', width: 180, ellipsis: {tooltip: true}},
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 90,
    fixed: 'right',
    render(row) {
      return [
        h(NButton, {
          size: 'small',
          quaternary: true,
          circle: true,
          type: 'primary',
          style: 'margin-right: 4px;',
          title: '编辑',
          onClick: () => openEditAppConfig(row)
        }, {icon: renderIcon('material-symbols:edit-outline', {size: 16})}),
        h(NPopconfirm, {onPositiveClick: () => deleteConfig(row)}, {
          trigger: () => h(NButton, {
            size: 'small',
            quaternary: true,
            circle: true,
            type: 'error',
            title: '删除'
          }, {icon: renderIcon('material-symbols:delete-outline', {size: 16})}),
          default: () => h('div', {}, '确定删除该配置吗?'),
        }),
      ]
    },
  },
]

const infraColumns = [
  {title: '应用名称', key: 'project_name', align: 'center', ellipsis: {tooltip: true}},
  {title: '配置名称', key: 'config_name', align: 'center', ellipsis: {tooltip: true}},
  {title: '主机地址', key: 'config_host', align: 'center', ellipsis: {tooltip: true}},
  {title: '主机端口', key: 'config_port', align: 'center', width: 100},
  {title: '分组编号', key: 'config_group', align: 'center', ellipsis: {tooltip: true}},
  {title: '更新时间', key: 'updated_time', align: 'center', width: 180, ellipsis: {tooltip: true}},
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 90,
    fixed: 'right',
    render(row) {
      return [
        h(NButton, {
          size: 'small',
          quaternary: true,
          circle: true,
          type: 'primary',
          style: 'margin-right: 4px;',
          title: '编辑',
          onClick: () => openEditInfraConfig(row)
        }, {icon: renderIcon('material-symbols:edit-outline', {size: 16})}),
        h(NPopconfirm, {onPositiveClick: () => deleteConfig(row)}, {
          trigger: () => h(NButton, {
            size: 'small',
            quaternary: true,
            circle: true,
            type: 'error',
            title: '删除'
          }, {icon: renderIcon('material-symbols:delete-outline', {size: 16})}),
          default: () => h('div', {}, '确定删除该配置吗?'),
        }),
      ]
    },
  },
]

function closeDrawer() {
  appModalShow.value = false
  infraModalShow.value = false
  emit('update:show', false)
}

function resetByRow() {
  const row = props.envRow || {}
  envForm.env_id = row.env_id || props.envId
  envForm.env_code = row.env_code || ''
  envForm.project_id = row.project_id || props.defaultProjectId
  envForm.env_name = row.env_name || ''
  envForm.env_desc = row.env_desc || ''
}

async function saveEnv() {
  try {
    saving.value = true
    await envFormRef.value?.validate?.()
    const payload = {
      ...(currentEnvId.value ? {env_id: currentEnvId.value, env_code: envForm.env_code || undefined} : {}),
      project_id: envForm.project_id,
      env_name: envForm.env_name,
      env_desc: envForm.env_desc || undefined,
    }
    const res = currentEnvId.value ? await api.updateEnv(payload) : await api.createEnv(payload)
    const data = res?.data || {}
    if (!currentEnvId.value && data.env_id) {
      envForm.env_id = data.env_id
      envForm.env_code = data.env_code || ''
    }
    window.$message?.success?.('环境保存成功')
    emit('saved')
    // 刷新当前表格
    getCurrentTableRef()?.handleSearch()
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`环境保存失败：${e?.message || e}`)
  } finally {
    saving.value = false
  }
}

// 应用配置相关
const appModalShow = ref(false)
const appModalMode = ref('create')
const appModalSaving = ref(false)
const appFormRef = ref(null)
const appForm = reactive({
  config_id: undefined,
  config_code: '',
  config_name: '',
  project_id: undefined,
  config_host: '',
  config_port: '',
  config_desc: '',
  headers: [],
  variables: [],
})

function dictToKvList(obj) {
  if (Array.isArray(obj)) {
    return obj.map((item) => ({
      key: item?.key == null ? '' : String(item.key),
      value: item?.value == null ? '' : String(item.value),
      desc: item?.desc == null ? '' : String(item.desc),
    }))
  }
  if (!obj || typeof obj !== 'object') return []
  return Object.entries(obj).map(([key, v]) => {
    if (v != null && typeof v === 'object' && !Array.isArray(v)) return {
      key,
      value: v.value == null ? '' : String(v.value),
      desc: v.desc == null ? '' : String(v.desc)
    }
    return {key, value: v == null ? '' : String(v), desc: ''}
  })
}

function normalizeKvList(items) {
  const arr = []
  ;(Array.isArray(items) ? items : []).forEach((item) => {
    const key = String(item?.key || '').trim()
    if (!key) return
    arr.push({
      key,
      value: item?.value == null ? '' : String(item.value),
      desc: item?.desc == null ? '' : String(item.desc),
    })
  })
  return arr
}

async function openCreateAppConfig() {
  if (!currentEnvId.value) return window.$message?.warning?.('请先保存环境基础信息')
  await loadProjectOptions()
  appModalMode.value = 'create'
  Object.assign(appForm, {
    config_id: undefined, config_code: '', config_name: '', project_id: envForm.project_id,
    config_host: '', config_port: '', config_desc: '', headers: [], variables: [],
  })
  appModalShow.value = true
}

async function openEditAppConfig(row) {
  await loadProjectOptions()
  appModalMode.value = 'edit'
  Object.assign(appForm, {
    config_id: row.config_id,
    config_code: row.config_code || '',
    config_name: row.config_name || '',
    project_id: row.project_id || envForm.project_id,
    config_host: row.config_host || '',
    config_port: row.config_port == null ? '' : String(row.config_port),
    config_desc: row.config_desc || '',
    headers: dictToKvList(row.config_header),
    variables: dictToKvList(row.config_kwargs),
  })
  appModalShow.value = true
}

async function submitAppConfig() {
  try {
    appModalSaving.value = true
    await appFormRef.value?.validate?.()
    const payload = {
      env_id: currentEnvId.value,
      project_id: appForm.project_id,
      config_type: 'api',
      config_name: appForm.config_name,
      config_host: appForm.config_host,
      config_port: appForm.config_port || undefined,
      config_header: normalizeKvList(appForm.headers),
      config_kwargs: normalizeKvList(appForm.variables),
      config_desc: appForm.config_desc || undefined,
    }
    if (appModalMode.value === 'edit') {
      await api.updateEnvConfig({
        ...payload,
        config_id: appForm.config_id,
        config_code: appForm.config_code || undefined
      })
    } else {
      await api.createEnvConfig(payload)
    }
    appModalShow.value = false
    window.$message?.success?.('保存成功')
    appTableRef.value?.handleSearch()
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`保存失败：${e?.message || e}`)
  } finally {
    appModalSaving.value = false
  }
}

// 基础设施配置相关
const infraModalShow = ref(false)
const infraModalMode = ref('create')
const infraModalSaving = ref(false)
const infraType = ref('database')
const isInfraDatabase = computed(() => infraType.value === 'database')
const infraFormRef = ref(null)
const infraForm = reactive({
  config_id: undefined,
  config_code: '',
  project_id: undefined,
  config_name: '',
  config_desc: '',
  config_host: '',
  config_port: '',
  config_group: '',
  config_params_json: '',
  config_username: '',
  config_password: '',
  database_name: '',
  database_type: undefined,
  is_authorization: false,
})

async function openCreateDatabaseConfig() {
  if (!currentEnvId.value) return window.$message?.warning?.('请先保存环境基础信息')
  await loadProjectOptions()
  infraType.value = 'database'
  infraModalMode.value = 'create'
  Object.assign(infraForm, {
    config_id: undefined,
    config_code: '',
    project_id: envForm.project_id,
    config_name: '',
    config_desc: '',
    config_host: '',
    config_port: '',
    config_group: '',
    config_params_json: '',
    config_username: '',
    config_password: '',
    database_name: '',
    database_type: undefined,
    is_authorization: false,
  })
  infraModalShow.value = true
  nextTick(() => infraFormRef.value?.restoreValidation?.())
}

async function openCreateFileConfig() {
  if (!currentEnvId.value) return window.$message?.warning?.('请先保存环境基础信息')
  await loadProjectOptions()
  infraType.value = 'file'
  infraModalMode.value = 'create'
  Object.assign(infraForm, {
    config_id: undefined,
    config_code: '',
    project_id: envForm.project_id,
    config_name: '',
    config_desc: '',
    config_host: '',
    config_port: '',
    config_group: '',
    config_params_json: '',
    config_username: '',
    config_password: '',
    database_name: '',
    database_type: undefined,
    is_authorization: false,
  })
  infraModalShow.value = true
  nextTick(() => infraFormRef.value?.restoreValidation?.())
}

function openEditInfraConfig(row) {
  loadProjectOptions()
  infraType.value = row?.config_type === 'file' ? 'file' : 'database'
  infraModalMode.value = 'edit'
  Object.assign(infraForm, {
    config_id: row.config_id,
    config_code: row.config_code || '',
    project_id: row.project_id || envForm.project_id,
    config_name: row.config_name || '',
    config_desc: row.config_desc || '',
    config_host: row.config_host || '',
    config_port: row.config_port == null ? '' : String(row.config_port),
    config_group: row.config_group || '',
    config_params_json: row.config_params ? JSON.stringify(row.config_params, null, 2) : '',
    config_username: row.config_username || '',
    config_password: row.config_password || '',
    database_name: row.database_name || '',
    database_type: row.database_type,
    is_authorization: !!row.is_authorization,
  })
  infraModalShow.value = true
}

async function submitInfraConfig() {
  try {
    infraModalSaving.value = true
    await infraFormRef.value?.validate?.()
    let paramsObj = undefined
    const raw = (infraForm.config_params_json || '').trim()
    if (raw) {
      try {
        paramsObj = JSON.parse(raw)
      } catch (_) {
        window.$message?.warning?.('服务器参数必须是合法 JSON')
        return
      }
    }
    const payload = {
      env_id: currentEnvId.value,
      project_id: infraForm.project_id,
      config_type: infraType.value,
      config_name: infraForm.config_name,
      config_desc: infraForm.config_desc || undefined,
      config_host: infraForm.config_host,
      config_port: infraForm.config_port || undefined,
      config_group: infraForm.config_group || undefined,
      config_params: paramsObj,
      config_username: infraForm.config_username || undefined,
      config_password: infraForm.config_password || undefined,
      database_name: isInfraDatabase.value ? (infraForm.database_name || undefined) : undefined,
      database_type: isInfraDatabase.value ? (infraForm.database_type || undefined) : undefined,
      is_authorization: isInfraDatabase.value ? undefined : (infraForm.is_authorization || undefined),
    }
    if (infraModalMode.value === 'edit') {
      await api.updateEnvConfig({
        ...payload,
        config_id: infraForm.config_id,
        config_code: infraForm.config_code || undefined
      })
    } else {
      await api.createEnvConfig(payload)
    }
    infraModalShow.value = false
    window.$message?.success?.('保存成功')
    getCurrentTableRef()?.handleSearch()
  } catch (e) {
    if (!e?.errors) window.$message?.error?.(`保存失败：${e?.message || e}`)
  } finally {
    infraModalSaving.value = false
  }
}

watch(() => props.show, async (v) => {
  if (!v) {
    appModalShow.value = false
    infraModalShow.value = false
    return
  }
  resetByRow()
  await loadProjectOptions()
  activeTab.value = 'app'
  await nextTick()
  appTableRef.value?.handleSearch()
})
</script>

<style scoped>
.env-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px 18px;
}

.full-row {
  grid-column: 1 / -1;
}

.tabs-wrap {
  margin-top: 12px;
}

.app-grid,
.infra-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 18px;
}

/* 设置抽屉内容的字体为 14px */
.env-drawer-content {
  font-size: 14px;
}

/* 确保所有子元素继承 */
.env-drawer-content :deep(*) {
  font-size: inherit;
}

/* 但表单组件可能需要明确设置 */
.env-drawer-content :deep(.n-input),
.env-drawer-content :deep(.n-select),
.env-drawer-content :deep(.n-form-item-label),
.env-drawer-content :deep(.query-bar-item-label) {
  font-size: 14px;
}

</style>
