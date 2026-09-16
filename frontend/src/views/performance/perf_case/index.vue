<template>
  <CommonPage show-footer title="压测场景">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchTaskList"
        :query-bar-props="queryBarProps"
        :scroll-x="1280"
        row-key="perf_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="handleCreate"
    >
      <template #queryBar>
        <QueryBarItem label="场景名称" :label-width="70">
          <NInput v-model:value="queryItems.perf_name" type="text" placeholder="场景名称(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="所属应用" :label-width="70">
          <NSelect
              v-model:value="queryItems.perf_project"
              :options="projectOptions"
              placeholder="请选择"
              clearable
              filterable
              style="width: 160px"
          />
        </QueryBarItem>
        <QueryBarItem label="执行状态" :label-width="70">
          <NSelect
              v-model:value="queryItems.last_execute_state"
              :options="stateOptions"
              placeholder="请选择"
              clearable
              style="width: 140px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <PerfRunDrawer ref="runDrawerRef" @finished="() => $table?.handleQuery()" @view-report="openReport" />
    <PerfReportDrawer ref="reportDrawerRef" />
  </CommonPage>
</template>

<script setup>
import { h, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag, NText } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfRunDrawer from '../components/PerfRunDrawer.vue'
import PerfReportDrawer from '../components/PerfReportDrawer.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测场景' })

/** 与后端 PerfTaskStatus 对齐的执行状态展示 */
const STATE_LABELS = {
  idle: '未执行',
  queued: '排队中',
  running: '执行中',
  stopping: '停止中',
  completed: '已完成',
  failed: '失败',
  stopped: '已停止',
}
const STATE_TAG_TYPES = {
  running: 'info', queued: 'default', stopping: 'warning',
  completed: 'success', failed: 'error', stopped: 'warning',
}

const router = useRouter()

/** 与其它业务页一致：新增/搜索收纳在 QueryBar 操作区（split 模式「新增」进更多下拉） */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const runDrawerRef = ref(null)
const reportDrawerRef = ref(null)

const queryItems = ref({
  perf_name: null,
  perf_project: null,
  last_execute_state: null,
})

const stateOptions = Object.entries(STATE_LABELS).map(([value, label]) => ({ label, value }))

const projectOptions = ref([])
async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    // 项目行主键被后端 replace_fields 重命名为 project_id（无 id 字段）
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 规范为 PerfTaskSelect 请求体（空值剔除） */
function fetchTaskList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.getPerfTaskList(body)
}

const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

function renderRowNo(index) {
  return (listPaginationMeta.value.page - 1) * listPaginationMeta.value.page_size + index + 1
}

const columns = [
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '场景名称', key: 'perf_name', width: 160, ellipsis: { tooltip: true } },
  {
    title: '施压环境',
    key: 'env_name',
    minWidth: 170,
    ellipsis: { tooltip: true },
    // 缺省APP配置仅在步骤未单独指定配置时兜底, 有环境无配置时只展示环境名
    render: (row) => (row.env_name
        ? h(NText, { code: true }, { default: () => (row.env_config_name ? `${row.env_name} · ${row.env_config_name}` : row.env_name) })
        : '-'),
  },
  {
    title: '场景规模',
    key: 'step_count',
    width: 180,
    render: (row) => `用例 ${row.case_count || 0} / 步骤 ${row.step_count || 0} / 被测 ${row.target_count || 0}`,
  },
  {
    title: '施压模式',
    key: 'load_mode',
    width: 90,
    render: (row) => (row.load_mode === 'stepped' ? '阶梯加压' : '固定并发'),
  },
  { title: '并发', key: 'concurrent_users', width: 70 },
  { title: '时长(s)', key: 'run_duration', width: 80 },
  {
    title: '执行状态',
    key: 'last_execute_state',
    width: 90,
    render: (row) => h(NTag, { type: STATE_TAG_TYPES[row.last_execute_state] || 'default', size: 'small' },
        { default: () => STATE_LABELS[row.last_execute_state] || row.last_execute_state || '未执行' }),
  },
  {
    title: '最近执行',
    key: 'last_execute_time',
    width: 160,
    render: (row) => (row.last_execute_time ? formatDateTime(row.last_execute_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 250,
    fixed: 'right',
    render(row) {
      const running = ['queued', 'running', 'stopping'].includes(row.last_execute_state)
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => handleEdit(row) },
              { default: () => '编辑' }),
          running
              ? h(NButton, { size: 'tiny', type: 'info', secondary: true, onClick: () => runDrawerRef.value?.open(row, false) },
                  { default: () => '监控' })
              : h(NButton, { size: 'tiny', type: 'success', secondary: true, onClick: () => handleRun(row) },
                  { default: () => '执行' }),
          h(NButton, { size: 'tiny', secondary: true, onClick: () => openLatestReport(row) },
              { default: () => '报告' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true }, { default: () => '删除' }),
            default: () => '确认删除该压测场景？',
          }),
        ],
      })
    },
  },
]

/** 新增场景：跳转独立页面（菜单「新增场景」） */
function handleCreate() {
  router.push('/performance/create')
}

/** 编辑场景：跳转独立页面并携带场景ID */
function handleEdit(row) {
  router.push({ path: '/performance/edit', query: { perf_id: row.perf_id } })
}

/** 立即执行：直接打开执行监控抽屉（抽屉内负责下发 run 并轮询） */
function handleRun(row) {
  runDrawerRef.value?.open(row, true)
}

async function handleDelete(row) {
  try {
    await api.deletePerfTask({ perf_id: row.perf_id })
    window.$message?.success('删除成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

/** 查看该任务最近一条报告 */
async function openLatestReport(row) {
  try {
    const res = await api.getPerfReportList({ perf_code: row.perf_code, page: 1, page_size: 1 })
    const reportCode = res.data?.[0]?.report_code
    if (!reportCode) {
      window.$message?.warning('该任务还没有执行报告')
      return
    }
    reportDrawerRef.value?.open(reportCode)
  } catch (e) {
    /* 拦截器已提示 */
  }
}

function openReport(reportCode) {
  reportDrawerRef.value?.open(reportCode)
}

onMounted(() => {
  loadProjects()
})

/** 本页 keepalive=1（菜单配置），从新增/编辑页返回时实例不重建；首次 activated 紧随挂载触发，需跳过 */
let skipFirstActivate = true
onActivated(() => {
  // 列表沿用「不默认查询」约定：仅当已有数据(之前查过)时重查，避免展示保存/执行前的旧值
  if (skipFirstActivate) {
    skipFirstActivate = false
    return
  }
  if (($table.value?.tableData || []).length) $table.value?.handleQuery()
})
</script>
