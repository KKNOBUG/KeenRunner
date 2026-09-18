<!--
  PerfApiImportModal — 压测接口导入弹窗（功能资产 / cURL 粘贴 / OpenAPI 批量解析）

  功能资产：左栏查用例，右栏勾选 HTTP/TCP 步骤；公共接口整体导入不可勾选；
  cURL 粘贴：解析浏览器复制的 curl 命令为单条草稿（主机地址剥离由环境承接）；
  OpenAPI 导入：解析 OpenAPI 3.x/Swagger 2.0 文档为草稿队列（上限100条，支持本地文件）；
  导入仅返回草稿不落库，由父页面跳转编辑子页逐条确认保存（溯源字段随草稿写入）。
-->
<template>
  <n-modal v-model:show="show" type="warning" preset="card" title="导入压测接口" style="width: 1020px">
    <n-tabs v-model:value="activeTab" type="line" size="small" animated>
      <!-- 渠道一：功能资产 -->
      <n-tab-pane name="case" tab="从功能资产导入">
        <n-grid :cols="24" :x-gap="16">
        <!-- 左栏：候选用例 -->
        <n-gi :span="11">
          <div class="pane-title">
            候选用例
            <n-text depth="3">勾选一条后展示可导入步骤</n-text>
          </div>
          <n-space :size="8" :wrap-item="false" style="margin-bottom: 8px">
            <n-select
                v-model:value="queryProject"
                :options="projectOptions"
                placeholder="所属应用"
                clearable
                filterable
                style="width: 170px"
                @update:value="handleSearch"
            />
            <n-input
                v-model:value="queryName"
                placeholder="用例名称"
                clearable
                style="width: 150px"
                @keypress.enter="handleSearch"
            />
            <n-select
                v-model:value="queryType"
                :options="caseTypeOptions"
                placeholder="用例类型"
                clearable
                style="width: 120px"
                @update:value="handleSearch"
            />
            <n-button size="small" type="primary" secondary @click="handleSearch">查询</n-button>
          </n-space>
          <n-data-table
              v-model:checked-row-keys="checkedCaseKeys"
              :columns="caseColumns"
              :data="caseRows"
              :loading="caseLoading"
              :pagination="casePagination"
              :row-key="(row) => row.case_id"
              size="small"
              :max-height="380"
              :scroll-x="380"
              @update:page="handleCasePageChange"
          />
        </n-gi>

        <!-- 右栏：步骤勾选 -->
        <n-gi :span="13">
          <div class="pane-title">
            可导入步骤
            <n-text v-if="selectedCase" depth="3">
              {{ isPublicApi ? '公共接口整体导入' : `已选 ${checkedStepKeys.length} 个步骤` }}
            </n-text>
          </div>
          <n-empty v-if="!selectedCase" description="请先在左侧勾选一条用例" class="py-80" />
          <n-alert v-else-if="isPublicApi" :bordered="false" type="info">
            公共接口本身等价一个请求单元，导入后生成 1 个压测接口草稿。
          </n-alert>
          <template v-else>
            <n-alert v-if="!pressableSteps.length" :bordered="false" type="warning" style="margin-bottom: 8px">
              该用例下没有可施压的 HTTP/TCP 步骤
            </n-alert>
            <n-data-table
                v-model:checked-row-keys="checkedStepKeys"
                :columns="stepColumns"
                :data="pressableSteps"
                :loading="stepLoading"
                :pagination="false"
                :row-key="(row) => row.id"
                size="small"
                :max-height="380"
                :scroll-x="420"
            />
          </template>
        </n-gi>
      </n-grid>
      </n-tab-pane>

      <!-- 渠道二：cURL 粘贴 -->
      <n-tab-pane name="curl" tab="cURL 粘贴导入">
        <n-space vertical :size="8">
          <n-alert :bordered="false" type="info">
            粘贴浏览器 DevTools「Copy as cURL」复制的命令；主机地址不落库，施压目标由执行环境解析；
            解析结果为草稿，需补全名称与所属应用后保存。
          </n-alert>
          <n-input
              v-model:value="curlText"
              type="textarea"
              :rows="10"
              placeholder="curl -X POST 'https://host/api/v1/xxx' -H 'Content-Type: application/json' --data-raw '{...}'"
          />
        </n-space>
      </n-tab-pane>

      <!-- 渠道三：OpenAPI/Swagger 批量解析 -->
      <n-tab-pane name="openapi" tab="OpenAPI 导入">
        <n-space vertical :size="8">
          <n-alert :bordered="false" type="info">
            粘贴 OpenAPI 3.x / Swagger 2.0 文档（JSON/YAML）或选择本地文件；
            每个接口操作解析为一条草稿（上限 100 条），逐条补全名称与所属应用后保存。
          </n-alert>
          <n-space :size="8" :wrap-item="false">
            <n-button size="small" secondary @click="triggerOpenapiFile">选择本地文件</n-button>
            <n-text v-if="openapiFileName" depth="3">{{ openapiFileName }}</n-text>
          </n-space>
          <n-input
              v-model:value="openapiText"
              type="textarea"
              :rows="9"
              :input-props="{ spellcheck: false }"
              placeholder='{"openapi": "3.0.1", "paths": {"/api/v1/xxx": {"get": {...}}}}'
          />
        </n-space>
      </n-tab-pane>
    </n-tabs>
    <!-- 文档文件选择器：读取文本填入粘贴框，不在选择阶段发起解析 -->
    <input
        ref="openapiFileRef"
        type="file"
        accept=".json,.yaml,.yml,.txt"
        style="display: none"
        @change="onOpenapiFileChange"
    />
    <template #footer>
      <n-space justify="end">
        <n-button @click="show = false">取 消</n-button>
        <n-button
           v-if="activeTab === 'case'"
            type="primary"
            :loading="importing"
            :disabled="!canImport"
            @click="handleImport"
        >
          导入草稿
        </n-button>
        <n-button
           v-else-if="activeTab === 'curl'"
            type="primary"
            :loading="importing"
            :disabled="!curlText.trim()"
            @click="handleParseCurl"
        >
          解析并导入
        </n-button>
        <n-button
           v-else
            type="primary"
            :loading="importing"
            :disabled="!openapiText.trim()"
            @click="handleParseOpenapi"
        >
          解析并导入
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import {
  NAlert, NButton, NDataTable, NEmpty, NGi, NGrid, NInput, NModal, NSelect, NSpace,
  NTabPane, NTabs, NTag, NText,
} from 'naive-ui'

import { formatDateTime } from '@/utils'
import api from '@/api'

defineOptions({ name: 'PerfApiImportModal' })

const emit = defineEmits(['imported'])

const show = defineModel('show', { type: Boolean, default: false })

/** 导入渠道: case 功能资产 / curl 粘贴解析 / openapi 文档批量解析 */
const activeTab = ref('case')
const curlText = ref('')
const openapiText = ref('')
const openapiFileRef = ref(null)
const openapiFileName = ref('')

const projectOptions = ref([])
const queryProject = ref(null)
const queryName = ref(null)
const queryType = ref(null)

/** 与后端 AutoTestCaseType 一致：公共接口整体导入；用户脚本步骤可转 HTTP 压测接口 */
const caseTypeOptions = [
  { label: '公共接口', value: '公共接口' },
  { label: '用户脚本', value: '用户脚本' },
]

const checkedCaseKeys = ref([])
const caseRows = ref([])
const caseLoading = ref(false)
const casePagination = ref({ page: 1, page_size: 10, pageCount: 1, onChange: (page) => handleCasePageChange(page) })

const checkedStepKeys = ref([])
const stepRows = ref([])
const stepLoading = ref(false)
const importing = ref(false)

/** 步骤树中可施压的节点类型（与后端 AutoTestStepType 中文枚举值一致） */
const PRESSABLE_STEP_TYPES = ['HTTP请求', 'TCP请求']

const selectedCase = computed(() => {
  if (!checkedCaseKeys.value.length) return null
  return caseRows.value.find((row) => row.case_id === checkedCaseKeys.value[0]) || null
})
const isPublicApi = computed(() => selectedCase.value?.case_type === '公共接口')
/** 仅 HTTP/TCP 步骤可转压测接口（与后端导入过滤口径一致） */
const pressableSteps = computed(() =>
    (stepRows.value || []).filter((row) => PRESSABLE_STEP_TYPES.includes(String(row.type || ''))),
)
const canImport = computed(() => {
  if (!selectedCase.value) return false
  return isPublicApi.value || checkedStepKeys.value.length > 0
})

const caseColumns = [
  { type: 'selection', multiple: false },
  { title: '用例名称', key: 'case_name', minWidth: 150, ellipsis: { tooltip: true } },
  { title: '类型', key: 'case_type', width: 88 },
  { title: '更新时间', key: 'updated_time', width: 100, render: (row) => (row.updated_time ? formatDateTime(row.updated_time).slice(0, 10) : '-') },
]

const stepColumns = [
  { type: 'selection' },
  { title: '步骤名称', key: 'name', minWidth: 140, ellipsis: { tooltip: true } },
  {
    title: '类型', key: 'type', width: 80,
    render: (row) => h(NTag, { size: 'small', type: row.type === 'TCP请求' ? 'warning' : 'info' },
        { default: () => (row.type === 'TCP请求' ? 'TCP' : 'HTTP') }),
  },
  { title: '地址', key: 'request_url', minWidth: 160, ellipsis: { tooltip: true } },
]

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

async function loadCases(page = 1) {
  caseLoading.value = true
  try {
    const res = await api.getApiTestcaseList({
      case_project: queryProject.value,
      case_name: queryName.value,
      case_type: queryType.value,
      page,
      page_size: 10,
      state: 0,
    })
    caseRows.value = res.data || []
    casePagination.value.page = res.meta?.page || page
    casePagination.value.pageCount = res.meta?.total ? Math.ceil(res.meta.total / 10) : 1
  } catch (e) {
    caseRows.value = []
  } finally {
    caseLoading.value = false
  }
}

function handleCasePageChange(page) {
  checkedCaseKeys.value = []
  loadCases(page)
}

function handleSearch() {
  checkedCaseKeys.value = []
  loadCases(1)
}

/** 勾选用例后拉取步骤树并平铺（子步骤一并展示，保持树内顺序） */
async function handleCaseChecked(keys) {
  checkedStepKeys.value = []
  stepRows.value = []
  const caseId = keys[0]
  if (!caseId) return
  stepLoading.value = true
  try {
    const res = await api.getStepTree({ case_id: caseId })
    stepRows.value = flattenSteps(res.data || [])
  } catch (e) {
    stepRows.value = []
  } finally {
    stepLoading.value = false
  }
}

/** 步骤树平铺：容器子步骤排在其父节点之后（树节点字段为 id/name/type/children，type 为中文枚举值） */
function flattenSteps(nodes) {
  const rows = []
  const walk = (list) => {
    ;(list || []).forEach((node) => {
      rows.push(node)
      if (Array.isArray(node.children) && node.children.length) walk(node.children)
    })
  }
  walk(nodes)
  return rows
}

async function handleImport() {
  if (!selectedCase.value) return
  importing.value = true
  try {
    const res = await api.importPerfApisFromCase({
      case_id: selectedCase.value.case_id,
      step_ids: isPublicApi.value ? null : checkedStepKeys.value,
    })
    const drafts = res.data || []
    if (!drafts.length) {
      window.$message?.warning('没有产出可保存的接口草稿')
      return
    }
    window.$message?.success(`已生成 ${drafts.length} 个接口草稿，请逐条确认保存`)
    show.value = false
    emit('imported', drafts)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    importing.value = false
  }
}

/** cURL 解析为单条草稿；解析提示以警告消息展示（草稿内 warnings 字段不进表单） */
async function handleParseCurl() {
  const text = curlText.value.trim()
  if (!text) return
  importing.value = true
  try {
    const res = await api.parsePerfApiCurl({ curl_text: text })
    const draft = res.data || {}
    const warnings = draft.warnings || []
    delete draft.warnings
    warnings.slice(0, 3).forEach((warning) => window.$message?.warning(warning, { duration: 6000 }))
    if (warnings.length > 3) {
      window.$message?.warning(`...等共 ${warnings.length} 条解析提示`, { duration: 6000 })
    }
    show.value = false
    window.$message?.success('解析成功，请确认草稿并补全名称与所属应用')
    emit('imported', [draft])
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    importing.value = false
  }
}

/** OpenAPI 批量解析为草稿队列；各条草稿的 warnings 以警告消息回显（字段不进表单） */
async function handleParseOpenapi() {
  const text = openapiText.value.trim()
  if (!text) return
  importing.value = true
  try {
    const res = await api.parsePerfApisOpenapi({ openapi_text: text })
    const drafts = res.data || []
    if (!drafts.length) {
      window.$message?.warning('没有解析到可导入的接口草稿')
      return
    }
    const warnings = drafts.flatMap((draft) => draft.warnings || [])
    drafts.forEach((draft) => delete draft.warnings)
    warnings.slice(0, 3).forEach((warning) => window.$message?.warning(warning, { duration: 6000 }))
    if (warnings.length > 3) {
      window.$message?.warning(`...等共 ${warnings.length} 条解析提示`, { duration: 6000 })
    }
    show.value = false
    window.$message?.success(`已解析 ${drafts.length} 条接口草稿，请逐条确认保存`)
    emit('imported', drafts)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    importing.value = false
  }
}

/** 触发本地文档选择（读取文本填入粘贴框，与粘贴通道共用同一解析链路） */
function triggerOpenapiFile() {
  openapiFileRef.value?.click()
}

function onOpenapiFileChange(event) {
  const input = event.target
  const file = input?.files?.[0]
  input.value = ''
  if (!file) return
  openapiFileName.value = file.name
  const reader = new FileReader()
  reader.onload = () => {
    openapiText.value = String(reader.result || '')
  }
  reader.readAsText(file)
}

/** 打开弹窗（应用候选项由父页面传入，避免重复拉取全量项目） */
function open(options = []) {
  show.value = true
  activeTab.value = 'case'
  curlText.value = ''
  openapiText.value = ''
  openapiFileName.value = ''
  if (options.length) projectOptions.value = options
  if (!queryProject.value) loadProjects()
  handleSearch()
}

defineExpose({ open })
</script>

<style scoped>
.pane-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
}
</style>
