<template>
  <CommonPage show-footer title="任务记录">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="getTaskRecordList"
        :scroll-x="3000"
        :single-line="true"
    >
      <template #queryBar>
        <QueryBarItem label="调度ID：">
          <NInput
              v-model:value="queryItems.celery_id"
              clearable
              type="text"
              placeholder="请输入调度ID(celery_id)"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="任务ID：">
          <NInput
              v-model:value="queryItems.task_id"
              clearable
              type="text"
              placeholder="请输入任务ID"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="任务名称：">
          <NInput
              v-model:value="queryItems.task_name"
              clearable
              type="text"
              placeholder="请输入任务名称"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="调度状态：">
          <NSelect
              v-model:value="queryItems.celery_status"
              :options="celeryStatusOptions"
              clearable
              placeholder="请选择状态"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="调度方式：">
          <NSelect
              v-model:value="queryItems.celery_scheduler"
              :options="celerySchedulerOptions"
              clearable
              placeholder="请选择调度方式"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="开始时间起：">
          <NInput
              v-model:value="queryItems.celery_start_time_begin"
              clearable
              type="text"
              placeholder="如 2026-01-01 00:00:00"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="开始时间止：">
          <NInput
              v-model:value="queryItems.celery_start_time_end"
              clearable
              type="text"
              placeholder="如 2026-01-31 23:59:59"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>
  </CommonPage>
</template>

<script setup>
import { h, ref } from 'vue'
import { NInput, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

defineOptions({ name: '任务记录' })

const $table = ref(null)
const queryItems = ref({})

// 与后端 AutoTestTaskStatus 枚举值一致
const celeryStatusOptions = [
  { label: '等待执行', value: '等待执行' },
  { label: '正在执行', value: '正在执行' },
  { label: '成功', value: '成功' },
  { label: '失败', value: '失败' },
]
// 与后端 AutoTestTaskScheduler 枚举值一致
const celerySchedulerOptions = [
  { label: 'cron', value: 'cron' },
  { label: 'interval', value: 'interval' },
  { label: 'datetime', value: 'datetime' },
]

const getTaskRecordList = async (params = {}) => {
  const res = await api.getApiTaskRecordList(params)
  return res
}

const formatJsonBrief = (val, maxLen = 50) => {
  if (val == null) return '-'
  if (typeof val === 'string') {
    try {
      const o = JSON.parse(val)
      const s = JSON.stringify(o)
      return s.length > maxLen ? s.slice(0, maxLen) + '...' : s
    } catch {
      return val.length > maxLen ? val.slice(0, maxLen) + '...' : val
    }
  }
  const s = JSON.stringify(val)
  return s.length > maxLen ? s.slice(0, maxLen) + '...' : s
}

const formatCaseIds = (row) => {
  const ids = row.task_case_ids
  if (!ids) return '-'
  if (Array.isArray(ids)) return ids.length ? ids.join(', ') : '-'
  if (typeof ids === 'string') return ids
  return String(ids)
}

// 列顺序与标题：执行记录ID、定时任务ID、定时任务名称、定时任务节点、关联用例IDS、调度状态、执行摘要、错误信息、
// 定时任务参数(args)、定时任务参数(kwargs)、调度ID、回溯ID、调度方式、开始时间、结束时间、耗时
const columns = [
  {
    title: '记录ID',
    key: 'record_id',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '任务ID',
    key: 'task_id',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '任务名称',
    key: 'task_name',
    width: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: '任务节点',
    key: 'celery_node',
    width: 200,
    ellipsis: { tooltip: true },
    render(row) {
      const s = row.celery_node
      return h('span', { title: s || '' }, s ?? '-')
    },
  },
  {
    title: '任务参数',
    key: 'task_kwargs',
    width: 320,
    ellipsis: { tooltip: true },
    render(row) {
      const s = formatJsonBrief(row.task_kwargs, 40)
      return h('span', { title: JSON.stringify(row.task_kwargs) }, s)
    },
  },
  {
    title: '调度方式',
    key: 'celery_scheduler',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '调度状态',
    key: 'celery_status',
    width: 100,
    align: 'center',
    render(row) {
      const typeMap = { '等待执行': 'default', '正在执行': 'warning', '成功': 'success', '失败': 'error' }
      return h(NTag, { type: typeMap[row.celery_status] || 'default', size: 'small', round: true }, () => row.celery_status || '-')
    },
  },
  {
    title: '执行摘要',
    key: 'task_summary',
    width: 300,
    ellipsis: { tooltip: true },
    render(row) {
      const s = row.task_summary
      if (!s) return h('span', '-')
      return h('span', { title: s }, s.length > 30 ? s.slice(0, 100) + '...' : s)
    },
  },
  {
    title: '错误信息',
    key: 'task_error',
    width: 300,
    ellipsis: { tooltip: true },
    render(row) {
      const s = row.task_error
      if (!s) return h('span', '-')
      return h('span', { title: s }, s.length > 30 ? s.slice(0, 100) + '...' : s)
    },
  },
  {
    title: '调度ID',
    key: 'celery_id',
    width: 320,
    ellipsis: { tooltip: true },
  },
  {
    title: '回溯ID',
    key: 'celery_trace_id',
    width: 320,
    ellipsis: { tooltip: true },
  },

  {
    title: '开始时间',
    key: 'celery_start_time',
    width: 180,
    align: 'center',
    render(row) {
      const val = row.celery_start_time
      return h('span', val ? formatDateTime(val) : '-')
    },
  },
  {
    title: '结束时间',
    key: 'celery_end_time',
    width: 180,
    align: 'center',
    render(row) {
      const val = row.celery_end_time
      return h('span', val ? formatDateTime(val) : '-')
    },
  },
  {
    title: '耗时',
    key: 'celery_duration',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
  },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
</style>
