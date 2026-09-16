<template>
  <CommonPage show-footer title="执行记录">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchReportList"
        :query-bar-props="queryBarProps"
        :scroll-x="1300"
        row-key="report_id"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="报告编码" :label-width="70">
          <NInput v-model:value="queryItems.report_code" type="text" placeholder="报告编码(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="场景编码" :label-width="70">
          <NInput v-model:value="queryItems.perf_code" type="text" placeholder="场景编码(精确)" clearable />
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

    <PerfReportDrawer ref="reportDrawerRef" />
  </CommonPage>
</template>

<script setup>
import { h, onActivated, ref } from 'vue'
import { NButton, NInput, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfReportDrawer from '../components/PerfReportDrawer.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）；
// 路由名不再取菜单名，故与其他目录下的同名菜单共存不会引发 404
defineOptions({ name: '执行记录' })

/** 与后端 PerfReportStatus 对齐（running/completed/failed/stopped） */
const STATUS_LABELS = { running: '执行中', completed: '已完成', failed: '失败', stopped: '已停止' }
const STATUS_TAG_TYPES = { completed: 'success', running: 'info', failed: 'error', stopped: 'warning' }

/** 记录列表只读：查询/重置即可，无新增操作 */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const reportDrawerRef = ref(null)

const queryItems = ref({
  report_code: null,
  perf_code: null,
  status: null,
})

const statusOptions = Object.entries(STATUS_LABELS).map(([value, label]) => ({ label, value }))

/** 规范为 PerfReportSelect 请求体（空值剔除） */
function fetchReportList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.getPerfReportList(body)
}

const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

function renderRowNo(index) {
  return (listPaginationMeta.value.page - 1) * listPaginationMeta.value.page_size + index + 1
}

function renderNumber(value, digits = 0) {
  return value == null ? '-' : Number(value).toFixed(digits)
}

const columns = [
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '报告编码', key: 'report_code', width: 200, ellipsis: { tooltip: true } },
  { title: '场景编码', key: 'perf_code', width: 200, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { type: STATUS_TAG_TYPES[row.status] || 'default', size: 'small' },
        { default: () => STATUS_LABELS[row.status] || row.status }),
  },
  { title: '总请求', key: 'total_requests', width: 90 },
  { title: '总失败', key: 'total_failures', width: 90 },
  { title: 'RPS', key: 'rps', width: 90, render: (row) => renderNumber(row.rps, 1) },
  {
    title: '失败率',
    key: 'fail_rate',
    width: 80,
    render: (row) => (row.fail_rate == null ? '-' : `${(row.fail_rate * 100).toFixed(2)}%`),
  },
  { title: 'P95(ms)', key: 'p95_latency', width: 90, render: (row) => renderNumber(row.p95_latency, 1) },
  {
    title: '时长(s)',
    key: 'actual_duration',
    width: 85,
    render: (row) => (row.actual_duration == null ? '-' : row.actual_duration),
  },
  {
    title: '开始时间',
    key: 'started_time',
    width: 160,
    render: (row) => (row.started_time ? formatDateTime(row.started_time) : '-'),
  },
  { title: '执行人', key: 'created_user', width: 100, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => reportDrawerRef.value?.open(row.report_code) },
              { default: () => '查看报告' }),
        ],
      })
    },
  },
]

/**
 * KeepAlive 重新激活时重查：本页与任务管理下的「执行记录」同名，而 include 按组件名匹配，
 * 只要任一侧开了缓存两侧都会被缓存，靠重查保证跳回本页时不会停在旧状态（首次 activated 紧随挂载，跳过）。
 */
let skipFirstActivate = true
onActivated(() => {
  if (skipFirstActivate) {
    skipFirstActivate = false
    return
  }
  if (($table.value?.tableData || []).length) $table.value?.handleQuery()
})
</script>
