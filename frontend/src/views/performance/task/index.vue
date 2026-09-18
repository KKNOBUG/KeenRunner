<!--
  压测任务列表页 — 调度层资产（打多狠、什么时候打）

  任务只承载场景引用 + 负载参数，流量结构与判定口径一律来自场景；
  执行先按未确认下发，命中后端高危闸门（场景含写入/高危接口）时弹出二次确认框重发。
-->
<template>
  <CommonPage show-footer title="压测任务">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchTaskList"
        :query-bar-props="queryBarProps"
        :scroll-x="1360"
        row-key="perf_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="() => formRef?.open(null)"
    >
      <template #queryBar>
        <QueryBarItem label="任务名称" :label-width="70">
          <NInput v-model:value="queryItems.perf_name" type="text" placeholder="任务名称(模糊)" clearable />
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
        <QueryBarItem label="施压模式" :label-width="70">
          <NSelect
              v-model:value="queryItems.load_mode"
              :options="loadModeOptions"
              placeholder="请选择"
              clearable
              style="width: 140px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <PerfTaskForm ref="formRef" @saved="() => $table?.handleQuery()" />

    <!-- 高危接口二次确认（与后端 perf_execute_service 高危闸门文案联动触发） -->
    <n-modal v-model:show="dangerShow" preset="dialog" type="warning" title="高危接口执行确认">
      <n-space vertical :size="12">
        <n-text>
          任务「{{ dangerTask?.perf_name }}」引用的场景包含写入/高危接口，执行将向被测端写入压测数据。
        </n-text>
        <n-checkbox v-model:checked="dangerChecked">
          我已确认被测端具备压测数据隔离与清理手段
        </n-checkbox>
      </n-space>
      <template #action>
        <n-space>
          <n-button @click="dangerShow = false">取 消</n-button>
          <n-button type="warning" :disabled="!dangerChecked" :loading="runningId != null" @click="confirmDangerRun">
            确认执行
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </CommonPage>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NCheckbox, NInput, NModal, NPopconfirm, NSelect, NSpace, NTag, NText } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfTaskForm from './components/PerfTaskForm.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测任务' })

const EXECUTE_STATE_LABELS = {
  idle: '待执行', queued: '排队中', running: '执行中', completed: '已完成',
  failed: '失败', stopping: '停止中', stopped: '已停止',
}
const EXECUTE_STATE_TAG_TYPES = {
  idle: 'default', queued: 'info', running: 'success', completed: 'success',
  failed: 'error', stopping: 'warning', stopped: 'default',
}
const LOAD_MODE_LABELS = { fixed: '固定并发', stepped: '阶梯加压', rps: 'RPS吞吐' }

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const loadModeOptions = [
  { label: '固定并发(fixed)', value: 'fixed' },
  { label: '阶梯加压(stepped)', value: 'stepped' },
  { label: 'RPS吞吐(rps)', value: 'rps' },
]

const $table = ref(null)
const formRef = ref(null)

const queryItems = ref({
  perf_name: null,
  perf_project: null,
  load_mode: null,
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

/** 秒数 → 可读时长（契约上限 8h，超过 1 分钟以分钟呈现） */
function formatDuration(seconds) {
  const total = Number(seconds) || 0
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return rest ? `${minutes}m${rest}s` : `${minutes}m`
}

const columns = [
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '任务名称', key: 'perf_name', width: 170, ellipsis: { tooltip: true } },
  { title: '压测场景', key: 'scene_name', width: 160, ellipsis: { tooltip: true } },
  {
    title: '施压模式',
    key: 'load_mode',
    width: 95,
    render: (row) => h(NTag, { size: 'small',
        type: { stepped: 'warning', rps: 'success' }[row.load_mode] || 'info' },
        { default: () => LOAD_MODE_LABELS[row.load_mode] || row.load_mode }),
  },
  {
    title: '负载',
    key: 'load_brief',
    minWidth: 170,
    render: (row) => (row.load_mode === 'stepped'
      ? `阶梯 ${row.step_start_users || '-'}→${row.step_max_users || '-'} 人`
      : row.load_mode === 'rps'
        ? `目标 ${row.target_rps ?? '-'} RPS × ${row.concurrent_users} 人`
        : `${row.concurrent_users} 人 × ${formatDuration(row.run_duration)}`),
  },
  {
    title: '最近执行',
    key: 'last_execute_state',
    width: 90,
    render: (row) => h(NTag, { size: 'small', type: EXECUTE_STATE_TAG_TYPES[row.last_execute_state] || 'default' },
        { default: () => EXECUTE_STATE_LABELS[row.last_execute_state] || row.last_execute_state || '待执行' }),
  },
  {
    title: '最近执行时间',
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
      const executing = ['queued', 'running', 'stopping'].includes(row.last_execute_state)
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, {
            size: 'tiny', type: 'primary', secondary: true,
            loading: runningId.value === row.perf_id,
            disabled: executing,
            onClick: () => handleRun(row),
          }, { default: () => '执行' }),
          executing
              ? h(NPopconfirm, { onPositiveClick: () => handleStop(row) }, {
                trigger: () => h(NButton, { size: 'tiny', type: 'warning', secondary: true }, { default: () => '停止' }),
                default: () => '确认下发停止指令？引擎将在数秒内终止任务',
              })
              : null,
          h(NButton, {
            size: 'tiny', type: 'primary', ghost: true,
            disabled: executing,
            onClick: () => formRef.value?.open({ perf_id: row.perf_id }),
          }, { default: () => '编辑' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true, disabled: executing },
                { default: () => '删除' }),
            default: () => '确认删除该压测任务？',
          }),
        ].filter(Boolean),
      })
    },
  },
]

// ---------- 执行与高危二次确认 ----------

const runningId = ref(null)
const dangerShow = ref(false)
const dangerChecked = ref(false)
const dangerTask = ref(null)

/**
 * 执行任务；首扫不带高危确认，命中后端高危闸门时弹出二次确认框。
 * 闸门文案与 perf_execute_service 保持联动：message 含「高危」即视为被闸门拦截。
 */
async function handleRun(row, confirmed = false) {
  runningId.value = row.perf_id
  try {
    await api.runPerfTask({ perf_id: row.perf_id, confirmed_dangerous: confirmed })
    window.$message?.success('已下发执行，请稍后在报告中查看结果')
    $table.value?.handleQuery()
  } catch (e) {
    if (!confirmed && String(e?.message || '').includes('高危')) {
      dangerTask.value = row
      dangerChecked.value = false
      dangerShow.value = true
    }
  } finally {
    runningId.value = null
  }
}

function confirmDangerRun() {
  if (!dangerTask.value) return
  const row = dangerTask.value
  dangerShow.value = false
  handleRun(row, true)
}

async function handleStop(row) {
  try {
    await api.stopPerfTask({ perf_id: row.perf_id })
    window.$message?.success('停止指令已下发，任务将在数秒内终止')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
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

onMounted(() => {
  loadProjects()
})
</script>
