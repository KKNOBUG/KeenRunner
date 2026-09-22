<!--
  压测场景列表页 — 编排层资产（打什么、怎么打 + 判定口径）

  主视图 = scene 列表；展开子行显示该场景下所有负载预设简要；
  行操作：编辑（跳转独立编辑页）/ 复制 / 删除 / 一键跑全部预设 / 预检。
-->
<template>
  <CommonPage show-footer title="压测场景">
    <QueryBar
        mb-30
        :add-reset="true"
        :add-search="true"
        :add-create="true"
        :add-delete="false"
        action-mode="split"
        @search="handleSearch"
        @reset="handleReset"
        @create="handleCreate"
    >
      <QueryBarItem label="场景名称" :label-width="70">
        <NInput v-model:value="queryItems.scene_name" type="text" placeholder="场景名称(模糊)" clearable />
      </QueryBarItem>
      <QueryBarItem label="所属应用" :label-width="70">
        <NSelect
            v-model:value="queryItems.scene_project"
            :options="projectOptions"
            placeholder="请选择"
            clearable
            filterable
            style="width: 160px"
        />
      </QueryBarItem>
      <QueryBarItem label="施压模式" :label-width="70">
        <NSelect
            v-model:value="queryItems.run_mode"
            :options="runModeFilterOptions"
            placeholder="请选择"
            clearable
            style="width: 150px"
        />
      </QueryBarItem>
    </QueryBar>

    <n-data-table
        :remote="true"
        :loading="loading"
        :columns="columns"
        :data="tableData"
        :scroll-x="1280"
        :row-key="(row) => row.scene_id"
        :pagination="pagination"
        :expanded-row-keys="expandedRowKeys"
        @update:expanded-row-keys="handleExpandedRowKeys"
        @update:page="onPageChange"
    >
      <template #expand="{ row }">
        <div class="preset-expand">
          <n-space align="center" justify="space-between" style="margin-bottom: 8px">
            <n-text strong>负载预设（{{ (presetsMap[row.scene_id] || []).length }} 份）</n-text>
            <n-space :size="8">
              <n-button size="tiny" type="primary" :loading="runningSceneId === row.scene_id" :disabled="!(presetsMap[row.scene_id] || []).length" @click="handleRunAll(row)">
                一键跑全部
              </n-button>
              <n-button size="tiny" @click="goEdit(row)">编辑场景</n-button>
            </n-space>
          </n-space>
          <n-empty v-if="presetsLoading[row.scene_id]" description="加载中..." class="py-12" />
          <n-empty v-else-if="!(presetsMap[row.scene_id] || []).length" description="该场景下暂无负载预设" class="py-12" />
          <n-data-table
              v-else
              :columns="presetColumns"
              :data="presetsMap[row.scene_id]"
              :pagination="false"
              :row-key="(r) => r.preset_id"
              size="small"
              :scroll-x="900"
          />
        </div>
      </template>
    </n-data-table>

    <PerfScenePrecheckModal ref="precheckRef" />

    <!-- 高危接口二次确认 -->
    <n-modal v-model:show="dangerShow" preset="dialog" type="warning" title="高危接口执行确认">
      <n-space vertical :size="12">
        <n-text>
          负载预设「{{ dangerPreset?.preset_name }}」引用的场景包含写入/高危接口，执行将向被测端写入压测数据。
        </n-text>
        <n-checkbox v-model:checked="dangerChecked">
          我已确认被测端具备压测数据隔离与清理手段
        </n-checkbox>
      </n-space>
      <template #action>
        <n-space>
          <n-button @click="dangerShow = false">取 消</n-button>
          <n-button type="warning" :disabled="!dangerChecked" :loading="runningPresetId != null" @click="confirmDangerRun">
            确认执行
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </CommonPage>
</template>

<script setup>
import { h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCheckbox, NDataTable, NEmpty, NInput, NModal, NPopconfirm, NSelect, NSpace, NTag, NText } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import PerfScenePrecheckModal from './components/PerfScenePrecheckModal.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测场景' })

const router = useRouter()

const RUN_MODE_LABELS = { single: '单接口', mixed: '混合流量', journey: '业务链路' }
const RUN_MODE_TAG_TYPES = { single: 'info', mixed: 'warning', journey: 'error' }
const ASSERT_MODE_LABELS = { all: '逐请求', sample_ratio: '抽样' }
const LOAD_MODE_LABELS = { fixed: '固定并发', stepped: '阶梯加压', rps: 'RPS吞吐' }
const EXECUTE_STATE_LABELS = {
  idle: '待执行', queued: '排队中', running: '执行中', completed: '已完成',
  failed: '失败', stopping: '停止中', stopped: '已停止',
}
const EXECUTE_STATE_TAG_TYPES = {
  idle: 'default', queued: 'info', running: 'success', completed: 'success',
  failed: 'error', stopping: 'warning', stopped: 'default',
}

const runModeFilterOptions = [
  { label: '单接口(single)', value: 'single' },
  { label: '混合流量(mixed)', value: 'mixed' },
]

const queryItems = ref({
  scene_name: null,
  scene_project: null,
  run_mode: null,
})

const projectOptions = ref([])
async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

// ---------- 表格数据 ----------

const loading = ref(false)
const tableData = ref([])
const expandedRowKeys = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  itemCount: 0,
  prefix({ itemCount }) { return `共 ${itemCount} 条` },
  onChange: (page) => { pagination.page = page },
  onUpdatePageSize: (pageSize) => { pagination.pageSize = pageSize; pagination.page = 1; handleQuery() },
})

function buildQueryBody() {
  const body = { state: 0, page: pagination.page, page_size: pagination.pageSize }
  Object.entries(queryItems.value).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return body
}

async function handleQuery() {
  try {
    loading.value = true
    const res = await api.searchPerfSceneList(buildQueryBody())
    tableData.value = res.data || []
    pagination.itemCount = res.total || 0
  } catch (e) {
    tableData.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { pagination.page = 1; handleQuery() }
function handleReset() {
  queryItems.value = { scene_name: null, scene_project: null, run_mode: null }
  pagination.page = 1
  handleQuery()
}
function onPageChange(page) { pagination.page = page; handleQuery() }

function handleExpandedRowKeys(keys) {
  expandedRowKeys.value = keys
  // 懒加载展开行的预设
  keys.forEach((sceneId) => { if (!presetsMap.value[sceneId]) loadPresetsForScene(sceneId) })
}

function renderRowNo(index) {
  return (pagination.page - 1) * pagination.pageSize + index + 1
}

// ---------- 展开子行：负载预设 ----------

const presetsMap = ref({})
const presetsLoading = ref({})

async function loadPresetsForScene(sceneId) {
  if (presetsMap.value[sceneId]) return
  presetsLoading.value = { ...presetsLoading.value, [sceneId]: true }
  try {
    const res = await api.getPerfLoadPresetList({ scene_id: sceneId, page_size: 200, state: 0 })
    presetsMap.value = { ...presetsMap.value, [sceneId]: res.data || [] }
  } catch (e) {
    presetsMap.value = { ...presetsMap.value, [sceneId]: [] }
  } finally {
    presetsLoading.value = { ...presetsLoading.value, [sceneId]: false }
  }
}

function formatDuration(seconds) {
  const total = Number(seconds) || 0
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return rest ? `${minutes}m${rest}s` : `${minutes}m`
}

const presetColumns = [
  { title: '预设名称', key: 'preset_name', minWidth: 150, ellipsis: { tooltip: true } },
  {
    title: '施压模式', key: 'load_mode', width: 95,
    render: (row) => h(NTag, { size: 'small', type: { stepped: 'warning', rps: 'success' }[row.load_mode] || 'info' },
        { default: () => LOAD_MODE_LABELS[row.load_mode] || row.load_mode }),
  },
  {
    title: '负载', key: 'load_brief', minWidth: 160,
    render: (row) => (row.load_mode === 'stepped'
      ? `阶梯 ${row.step_start_users || '-'}→${row.step_max_users || '-'} 人`
      : row.load_mode === 'rps'
        ? `目标 ${row.target_rps ?? '-'} RPS × ${row.concurrent_users} 人`
        : `${row.concurrent_users} 人 × ${formatDuration(row.run_duration)}`),
  },
  {
    title: '最近执行', key: 'last_execute_state', width: 90,
    render: (row) => h(NTag, { size: 'small', type: EXECUTE_STATE_TAG_TYPES[row.last_execute_state] || 'default' },
        { default: () => EXECUTE_STATE_LABELS[row.last_execute_state] || row.last_execute_state || '待执行' }),
  },
  {
    title: '最近执行时间', key: 'last_execute_time', width: 160,
    render: (row) => (row.last_execute_time ? formatDateTime(row.last_execute_time) : '-'),
  },
  {
    title: '操作', key: 'actions', width: 180, fixed: 'right',
    render(row) {
      const executing = ['queued', 'running', 'stopping'].includes(row.last_execute_state)
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, {
            size: 'tiny', type: 'primary', secondary: true,
            loading: runningPresetId.value === row.preset_id,
            disabled: executing,
            onClick: () => handleRunPreset(row),
          }, { default: () => '执行' }),
          executing
              ? h(NPopconfirm, { onPositiveClick: () => handleStopPreset(row) }, {
                trigger: () => h(NButton, { size: 'tiny', type: 'warning', secondary: true }, { default: () => '停止' }),
                default: () => '确认下发停止指令？引擎将在数秒内终止',
              })
              : null,
          h(NPopconfirm, { onPositiveClick: () => handleDeletePreset(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true, disabled: executing }, { default: () => '删除' }),
            default: () => '确认删除该负载预设？',
          }),
        ].filter(Boolean),
      })
    },
  },
]

// ---------- 场景列表列 ----------

const columns = [
  { type: 'expand', expandable: () => true, width: 40 },
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '场景名称', key: 'scene_name', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '施压模式', key: 'run_mode', width: 100,
    render: (row) => h(NTag, { size: 'small', type: RUN_MODE_TAG_TYPES[row.run_mode] || 'default' },
        { default: () => RUN_MODE_LABELS[row.run_mode] || row.run_mode }),
  },
  { title: '接口项数', key: 'item_count', width: 90 },
  {
    title: '熔断阈值(%)', key: 'error_rate_threshold', width: 100,
    render: (row) => (row.error_rate_threshold === null || row.error_rate_threshold === undefined ? '未启用' : row.error_rate_threshold),
  },
  {
    title: '断言口径', key: 'assert_mode', width: 90,
    render: (row) => ASSERT_MODE_LABELS[row.assert_mode] || row.assert_mode,
  },
  {
    title: '更新时间', key: 'updated_time', width: 160,
    render: (row) => (row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作', key: 'actions', width: 300, fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => goEdit(row) }, { default: () => '编辑' }),
          h(NButton, { size: 'tiny', type: 'info', secondary: true, onClick: () => precheckRef.value?.open({ scene_id: row.scene_id, scene_name: row.scene_name, scene_project: row.scene_project }) }, { default: () => '预检' }),
          h(NButton, { size: 'tiny', type: 'success', secondary: true, loading: runningSceneId.value === row.scene_id, onClick: () => handleRunAll(row) }, { default: () => '跑全部' }),
          h(NPopconfirm, { onPositiveClick: () => handleCopy(row) }, {
            trigger: () => h(NButton, { size: 'tiny', secondary: true }, { default: () => '复制' }),
            default: () => '复制为同应用下的新场景？（编排全量平移，基线不继承）',
          }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true }, { default: () => '删除' }),
            default: () => '确认删除该压测场景？',
          }),
        ],
      })
    },
  },
]

// ---------- 跳转 ----------

const precheckRef = ref(null)

function handleCreate() {
  router.push('/performance/scene/edit')
}

function goEdit(row) {
  router.push({ path: '/performance/scene/edit', query: { scene_id: row.scene_id } })
}

// ---------- 场景操作 ----------

async function handleCopy(row) {
  try {
    await api.copyPerfScene({ scene_id: row.scene_id })
    window.$message?.success('复制成功')
    handleQuery()
  } catch (e) { /* 拦截器已提示 */ }
}

async function handleDelete(row) {
  try {
    await api.deletePerfScene({ scene_id: row.scene_id })
    window.$message?.success('删除成功')
    handleQuery()
  } catch (e) { /* 拦截器已提示 */ }
}

// ---------- 一键跑全部 ----------

const runningSceneId = ref(null)

async function handleRunAll(row) {
  runningSceneId.value = row.scene_id
  try {
    const res = await api.runAllPerfScenePresets({ scene_id: row.scene_id })
    const data = res.data || {}
    window.$message?.success(res.message || `已下发 ${data.dispatched || 0}/${data.total || 0} 份负载预设`)
    // 刷新展开子行
    delete presetsMap.value[row.scene_id]
    loadPresetsForScene(row.scene_id)
  } catch (e) { /* 拦截器已提示 */ } finally {
    runningSceneId.value = null
  }
}

// ---------- 预设执行与高危二次确认 ----------

const runningPresetId = ref(null)
const dangerShow = ref(false)
const dangerChecked = ref(false)
const dangerPreset = ref(null)

async function handleRunPreset(row, confirmed = false) {
  runningPresetId.value = row.preset_id
  try {
    await api.runPerfLoadPreset({ preset_id: row.preset_id, confirmed_dangerous: confirmed })
    window.$message?.success('已下发执行，请稍后在报告中查看结果')
    // 刷新展开子行
    const sceneId = row.scene_id
    if (sceneId) { delete presetsMap.value[sceneId]; loadPresetsForScene(sceneId) }
  } catch (e) {
    if (!confirmed && String(e?.message || '').includes('高危')) {
      dangerPreset.value = row
      dangerChecked.value = false
      dangerShow.value = true
    }
  } finally {
    runningPresetId.value = null
  }
}

function confirmDangerRun() {
  if (!dangerPreset.value) return
  const row = dangerPreset.value
  dangerShow.value = false
  handleRunPreset(row, true)
}

async function handleStopPreset(row) {
  try {
    await api.stopPerfLoadPreset({ preset_id: row.preset_id })
    window.$message?.success('停止指令已下发，负载预设将在数秒内终止')
    const sceneId = row.scene_id
    if (sceneId) { delete presetsMap.value[sceneId]; loadPresetsForScene(sceneId) }
  } catch (e) { /* 拦截器已提示 */ }
}

async function handleDeletePreset(row) {
  try {
    await api.deletePerfLoadPreset({ preset_id: row.preset_id })
    window.$message?.success('删除成功')
    const sceneId = row.scene_id
    if (sceneId) { delete presetsMap.value[sceneId]; loadPresetsForScene(sceneId) }
  } catch (e) { /* 拦截器已提示 */ }
}

onMounted(() => {
  loadProjects()
  handleQuery()
})
</script>

<style scoped>
.preset-expand {
  padding: 8px 16px;
  background: #fafafa;
}
</style>
