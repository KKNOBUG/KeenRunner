<!--
  数据作业列表页 — 带外作业资产（prepare造数 / verify校验 / cleanup清理）

  作业执行走 {port}_perf 队列异步跑脚本用例 N 轮；下发后轮询 /status 直到终态，
  期间列表行禁用执行/删除。契约无 update，配置变更走「删除重建」。
-->
<template>
  <CommonPage show-footer title="数据作业">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchJobList"
        :query-bar-props="queryBarProps"
        :scroll-x="1280"
        row-key="job_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="() => formRef?.open()"
    >
      <template #queryBar>
        <QueryBarItem label="作业名称" :label-width="70">
          <NInput v-model:value="queryItems.job_name" type="text" placeholder="作业名称(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="作业类型" :label-width="70">
          <NSelect
              v-model:value="queryItems.job_type"
              :options="jobTypeOptions"
              placeholder="请选择"
              clearable
              style="width: 140px"
          />
        </QueryBarItem>
        <QueryBarItem label="执行状态" :label-width="70">
          <NSelect
              v-model:value="queryItems.status"
              :options="statusOptions"
              placeholder="请选择"
              clearable
              style="width: 140px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <PerfJobForm ref="formRef" @saved="() => $table?.handleQuery()" />
  </CommonPage>
</template>

<script setup>
import { h, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag, NTooltip } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfJobForm from './components/PerfJobForm.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '数据作业' })

const JOB_TYPE_LABELS = { prepare: '造数', verify: '校验', cleanup: '清理' }
const JOB_TYPE_TAG_TYPES = { prepare: 'warning', verify: 'info', cleanup: 'default' }
const STATUS_LABELS = { pending: '排队中', running: '执行中', success: '成功', failed: '失败' }
const STATUS_TAG_TYPES = { pending: 'info', running: 'warning', success: 'success', failed: 'error' }

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const jobTypeOptions = [
  { label: '造数(prepare)', value: 'prepare' },
  { label: '校验(verify)', value: 'verify' },
  { label: '清理(cleanup)', value: 'cleanup' },
]
const statusOptions = [
  { label: '排队中', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const $table = ref(null)
const formRef = ref(null)

const queryItems = ref({
  job_name: null,
  job_type: null,
  status: null,
})

/** 规范为 PerfJobSelect 请求体（空值剔除） */
function fetchJobList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.searchPerfJobList(body)
}

const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

function renderRowNo(index) {
  return (listPaginationMeta.value.page - 1) * listPaginationMeta.value.page_size + index + 1
}

/** 执行锁定态：执行/删除按钮禁用口径（排队中/执行中不允许并发动作） */
const EXECUTE_LOCKED = ['pending', 'running']

const columns = [
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '作业名称', key: 'job_name', width: 170, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'job_type',
    width: 80,
    render: (row) => h(NTag, { size: 'small', type: JOB_TYPE_TAG_TYPES[row.job_type] || 'default' },
        { default: () => JOB_TYPE_LABELS[row.job_type] || row.job_type }),
  },
  { title: '脚本用例', key: 'quote_case_name', width: 160, ellipsis: { tooltip: true } },
  {
    title: '执行配置',
    key: 'execute_brief',
    width: 150,
    render: (row) => `${row.loop_times} 轮${row.dataset_name ? ` × ${row.dataset_name}` : ''}`,
  },
  {
    title: '提取列',
    key: 'extract_fields',
    width: 140,
    render: (row) => {
      const fields = row.extract_fields || []
      if (!fields.length) return '-'
      const text = fields.join(', ')
      return h(NTooltip, {}, {
        trigger: () => h('span', { style: 'display:inline-block;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom' }, text),
        default: () => text,
      })
    },
  },
  {
    title: '执行状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { size: 'small', type: STATUS_TAG_TYPES[row.status] || 'default' },
        { default: () => STATUS_LABELS[row.status] || row.status || '-' }),
  },
  {
    title: '产出',
    key: 'produce_brief',
    minWidth: 130,
    render: (row) => {
      if (row.job_type !== 'prepare' || !row.result_rows) return '-'
      return `${row.result_rows} 行 → 数据集#${row.result_dataset_id ?? '-'}`
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 160,
    render: (row) => (row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    fixed: 'right',
    render(row) {
      const locked = EXECUTE_LOCKED.includes(row.status)
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, {
            size: 'tiny', type: 'primary', secondary: true,
            loading: runningId.value === row.job_id,
            disabled: locked,
            onClick: () => handleRun(row),
          }, { default: () => '执行' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true, disabled: locked },
                { default: () => '删除' }),
            default: () => '确认删除该数据作业？已产出的数据集不受影响',
          }),
        ],
      })
    },
  },
]

// ---------- 执行下发与状态轮询 ----------

const runningId = ref(null)

async function handleRun(row) {
  runningId.value = row.job_id
  try {
    await api.runPerfJob({ job_id: row.job_id })
    window.$message?.success('已下发执行，作业状态将自动刷新')
    $table.value?.handleQuery()
    startPolling(row.job_id)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    runningId.value = null
  }
}

const pollingIds = ref(new Set())
let pollTimer = null
const POLL_INTERVAL_MS = 3000

/** 下发后轮询 /status 直到终态，结束时提示结论并刷新列表 */
function startPolling(jobId) {
  pollingIds.value.add(jobId)
  if (!pollTimer) pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollOnce() {
  const ids = [...pollingIds.value]
  if (!ids.length) {
    stopPolling()
    return
  }
  await Promise.all(ids.map(async (jobId) => {
    try {
      const res = await api.getPerfJobStatus({ job_id: jobId })
      const st = res.data?.status
      if (st && !EXECUTE_LOCKED.includes(st)) {
        pollingIds.value.delete(jobId)
        if (st === 'success') {
          window.$message?.success(`作业执行成功${res.data?.result_rows ? `，产出 ${res.data.result_rows} 行数据` : ''}`)
        } else {
          window.$message?.error(`作业执行失败：${res.data?.error_message || '请查看作业详情'}`)
        }
        $table.value?.handleQuery()
      }
    } catch (e) {
      pollingIds.value.delete(jobId)
    }
  }))
  if (!pollingIds.value.size) stopPolling()
}

async function handleDelete(row) {
  try {
    await api.deletePerfJob({ job_id: row.job_id })
    window.$message?.success('删除成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

onMounted(() => {
  /* 首次列表由 CrudTable 自行加载 */
})

onUnmounted(() => {
  stopPolling()
})
</script>
