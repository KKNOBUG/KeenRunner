<!--
  PerfApiDebugDrawer — 压测接口调试抽屉（对齐 autotest 设计）

  对已保存接口发一次真实请求（口径与施压引擎一致），回显状态码/耗时/响应片段与断言、提取结果；
  调试结论回写 api.debug_state，是施压前预检闸门的依据。地址为绝对地址时环境可留空。

  数据源取数（对齐 autotest 设计）：
  - 一个接口绑定一个数据源，调试时选择"是否启用数据源"
  - 启用后选择场景名称（调试只可选一个场景，施压可选多个）
-->
<template>
  <n-drawer v-model:show="show" :width="720" placement="right">
    <n-drawer-content :title="`接口调试 · ${apiRow?.api_name || ''}`" closable>
      <n-space vertical :size="14">
        <n-form label-placement="left" label-width="96" size="small">
          <n-grid :cols="24" :x-gap="12">
            <n-gi :span="12">
              <n-form-item label="调试环境">
                <n-select
                    v-model:value="envName"
                    :options="envOptions"
                    :loading="envLoading"
                    clearable
                    filterable
                    placeholder="绝对地址可留空"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="启用数据源">
                <n-switch v-model:value="enableDataSource" @update:value="onEnableDataSourceChange" />
              </n-form-item>
            </n-gi>
            <n-gi v-if="enableDataSource" :span="12">
              <n-form-item label="场景名称">
                <n-select
                    v-model:value="sceneName"
                    :options="sceneOptions"
                    :loading="sceneLoading"
                    :disabled="!enableDataSource"
                    placeholder="选择场景（调试只可选一个）"
                    clearable
                    filterable
                />
              </n-form-item>
            </n-gi>
          </n-grid>
        </n-form>

        <n-button type="primary" block :loading="debugging" @click="handleDebug">
          发起调试请求
        </n-button>

        <template v-if="result">
          <n-alert :type="result.success ? 'success' : 'error'" :show-icon="true">
            {{ result.success ? '调试通过（状态码 < 400 且断言全部通过）' : '调试未通过' }}
          </n-alert>
          <n-descriptions :column="2" size="small" label-placement="left" bordered>
            <n-descriptions-item label="请求地址" :span="2">
              <n-text code>{{ result.request_url || '-' }}</n-text>
            </n-descriptions-item>
            <n-descriptions-item label="状态码">{{ result.status_code ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="耗时">{{ result.elapsed_ms != null ? `${result.elapsed_ms}ms` : '-' }}</n-descriptions-item>
          </n-descriptions>
          <n-text v-if="result.transport_error" type="error" depth="2">传输异常：{{ result.transport_error }}</n-text>

          <template v-if="(result.extracts || []).length">
            <n-divider title-placement="left" style="margin: 4px 0">提取结果</n-divider>
            <n-data-table
                :columns="extractColumns"
                :data="result.extracts"
                size="small"
                :pagination="false"
                :scroll-x="520"
            />
          </template>

          <template v-if="(result.assertions || []).length">
            <n-divider title-placement="left" style="margin: 4px 0">断言结果</n-divider>
            <n-data-table
                :columns="assertColumns"
                :data="result.assertions"
                size="small"
                :pagination="false"
                :scroll-x="620"
            />
          </template>

          <template v-if="result.response_body">
            <n-divider title-placement="left" style="margin: 4px 0">响应片段</n-divider>
            <n-input
                :value="result.response_body"
                type="textarea"
                readonly
                :rows="8"
                style="font-family: monospace"
            />
          </template>
        </template>
      </n-space>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import {
  NAlert, NButton, NDataTable, NDescriptions, NDescriptionsItem, NDivider, NDrawer,
  NDrawerContent, NForm, NFormItem, NGi, NGrid, NInput, NSelect, NSpace, NSwitch, NTag, NText,
} from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfApiDebugDrawer' })

/** 调试结论会回写 debug_state，通知父组件刷新列表 */
const emit = defineEmits(['finished'])

const show = defineModel('show', { type: Boolean, default: false })

const apiRow = ref(null)
const envName = ref(null)
// 数据源取数（对齐 autotest 设计：一个接口绑定一个数据源）
const enableDataSource = ref(false)
const sceneName = ref(null)

const envOptions = ref([])
const envLoading = ref(false)
const sceneOptions = ref([])
const sceneLoading = ref(false)
const debugging = ref(false)
const result = ref(null)

const extractColumns = [
  { title: '变量名', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '提取值', key: 'extract_value', minWidth: 200, ellipsis: { tooltip: true } },
  {
    title: '结果', key: 'success', width: 80,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', size: 'small' },
        { default: () => (row.success ? '成功' : '失败') }),
  },
  { title: '错误', key: 'error', minWidth: 140, ellipsis: { tooltip: true } },
]

const assertColumns = [
  { title: '断言', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '实际值', key: 'actual_value', minWidth: 140, ellipsis: { tooltip: true } },
  {
    title: '结果', key: 'success', width: 80,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', size: 'small' },
        { default: () => (row.success ? '通过' : '失败') }),
  },
  { title: '错误', key: 'error', minWidth: 140, ellipsis: { tooltip: true } },
]

async function loadEnvNames(projectId) {
  if (!projectId) return
  envLoading.value = true
  try {
    // 仅返回该应用挂载了 APP 配置的环境名称，与施压环境解析口径一致
    const res = await api.queryAssignConfigEnvs({ project_id: projectId, env_type: 'app' })
    envOptions.value = (Array.isArray(res?.data) ? res.data : []).map((name) => ({ label: name, value: name }))
  } catch (e) {
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

/** 加载接口绑定的数据源场景列表（一个接口只能有一个数据源） */
async function loadScenes(apiId) {
  if (!apiId) {
    sceneOptions.value = []
    return
  }
  sceneLoading.value = true
  try {
    const res = await api.listPerfDatasetsForApi({ api_id: apiId })
    const rows = (res.data || []).filter((row) => row.bind_api_id === apiId)
    // 一个接口只能有一个数据源，取第一条
    const dsRow = rows.length > 0 ? rows[0] : null
    if (dsRow) {
      sceneOptions.value = (dsRow.dataset_names || []).map((name) => ({ label: name, value: name }))
    } else {
      sceneOptions.value = []
    }
  } catch (e) {
    sceneOptions.value = []
  } finally {
    sceneLoading.value = false
  }
}

/** 启用数据源开关变化时加载场景列表 */
function onEnableDataSourceChange(enabled) {
  if (enabled) {
    loadScenes(apiRow.value?.api_id)
  } else {
    sceneName.value = null
    sceneOptions.value = []
  }
}

async function handleDebug() {
  // 启用数据源时必须选择场景
  if (enableDataSource.value && !sceneName.value) {
    window.$message?.warning('启用数据源时请选择场景名称')
    return
  }
  debugging.value = true
  result.value = null
  try {
    const res = await api.debugPerfApi({
      api_id: apiRow.value.api_id,
      env_name: envName.value,
      // 不再传 env_config_name（APP配置已在接口定义中）
      enable_data_source: enableDataSource.value,
      scene_name: enableDataSource.value ? sceneName.value : null,
    })
    result.value = res.data
    emit('finished')
    if (res.data?.success) {
      window.$message?.success('调试通过')
    } else {
      window.$message?.warning('调试未通过，请检查回显详情')
    }
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    debugging.value = false
  }
}

/** 打开抽屉并预载环境候选 */
async function open(row) {
  apiRow.value = row
  envName.value = null
  enableDataSource.value = false
  sceneName.value = null
  result.value = null
  envOptions.value = []
  sceneOptions.value = []
  show.value = true
  // 环境候选按接口所属应用(request_project_id)加载，与施压环境解析口径一致
  loadEnvNames(row?.request_project_id)
}

defineExpose({ open })
</script>
