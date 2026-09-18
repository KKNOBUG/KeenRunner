<!--
  PerfApiDebugDrawer — 压测接口调试抽屉

  对已保存接口发一次真实请求（口径与施压引擎一致），回显状态码/耗时/响应片段与断言、提取结果；
  调试结论回写 api.debug_state，是施压前预检闸门的依据。地址为绝对地址时环境可留空。
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
                    @update:value="envName && loadConfigNames()"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="APP配置">
                <n-select
                    v-model:value="envConfigName"
                    :options="configOptions"
                    :loading="configLoading"
                    :disabled="!envName"
                    clearable
                    filterable
                    placeholder="施压目标APP节点"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="取数数据集">
                <n-select
                    v-model:value="dsCode"
                    :options="datasetOptions"
                    :loading="datasetLoading"
                    clearable
                    filterable
                    placeholder="绑定数据集（可选）"
                    @update:value="onDatasetChange"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="取数场景">
                <n-select
                    v-model:value="sceneIndex"
                    :options="sceneOptions"
                    :disabled="!dsCode"
                    placeholder="第几个场景(按声明顺序)"
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
  NDrawerContent, NForm, NFormItem, NGi, NGrid, NInput, NSelect, NSpace, NTag, NText,
} from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfApiDebugDrawer' })

/** 调试结论会回写 debug_state，通知父组件刷新列表 */
const emit = defineEmits(['finished'])

const show = defineModel('show', { type: Boolean, default: false })

const apiRow = ref(null)
const envName = ref(null)
const envConfigName = ref(null)
const dsCode = ref(null)
const sceneIndex = ref(0)

const envOptions = ref([])
const envLoading = ref(false)
const configOptions = ref([])
const configLoading = ref(false)
const datasetOptions = ref([])
const datasetLoading = ref(false)
/** 已选数据集的场景名声明序（调试取数按场景序号替换） */
const sceneNames = ref([])
const debugging = ref(false)
const result = ref(null)

/** 场景下拉：label=场景名，value=声明序号（0起，与后端 scene_index 同口径） */
const sceneOptions = computed(() =>
    sceneNames.value.map((name, index) => ({ label: `${index + 1}. ${name}`, value: index })),
)

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

async function loadConfigNames() {
  if (!apiRow.value?.api_project || !envName.value) {
    configOptions.value = []
    return
  }
  configLoading.value = true
  try {
    const res = await api.getEnvConfigList({
      project_id: apiRow.value.api_project,
      env_name: envName.value,
      env_type: 'app',
      page: 1,
      page_size: 100,
    })
    configOptions.value = (Array.isArray(res?.data) ? res.data : [])
        .map((row) => ({ label: row.config_name, value: row.config_name }))
  } catch (e) {
    configOptions.value = []
  } finally {
    configLoading.value = false
  }
}

/** 接口可用数据集（归属该接口），并缓存各数据集的场景名序供场景下拉 */
const datasetRows = ref([])

async function loadDatasets(apiId) {
  if (!apiId) return
  datasetLoading.value = true
  try {
    const res = await api.listPerfDatasetsForApi({ api_id: apiId })
    datasetRows.value = (res.data || []).filter((row) => row.bind_api_id === apiId)
    datasetOptions.value = datasetRows.value.map((row) => ({ label: row.ds_name, value: row.ds_code }))
    sceneNames.value = []
  } catch (e) {
    datasetRows.value = []
    datasetOptions.value = []
    sceneNames.value = []
  } finally {
    datasetLoading.value = false
  }
}

/** 选定数据集后同步场景名序（场景下拉取 dataset_names 声明序） */
function onDatasetChange(dsCodeValue) {
  sceneIndex.value = 0
  const matched = datasetRows.value.find((row) => row.ds_code === dsCodeValue)
  sceneNames.value = matched?.dataset_names || []
}

async function handleDebug() {
  debugging.value = true
  result.value = null
  try {
    const res = await api.debugPerfApi({
      api_id: apiRow.value.api_id,
      env_name: envName.value,
      env_config_name: envConfigName.value,
      ds_code: dsCode.value,
      scene_index: sceneIndex.value || 0,
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

/** 打开抽屉并预载环境与数据集候选 */
async function open(row) {
  apiRow.value = row
  envName.value = null
  envConfigName.value = null
  dsCode.value = null
  sceneIndex.value = 0
  result.value = null
  envOptions.value = []
  configOptions.value = []
  datasetOptions.value = []
  sceneNames.value = []
  show.value = true
  loadEnvNames(row?.api_project)
  loadDatasets(row?.api_id)
}

defineExpose({ open })
</script>
