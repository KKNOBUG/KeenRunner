<template>
  <CommonPage show-footer title="任务记录">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="getTaskRecordList"
        :scroll-x="2900"
        :single-line="true"
    >
      <template #queryBar>
        <QueryBarItem label="调度ID：">
          <NInput
              v-model:value="queryItems.celery_id"
              clearable
              type="text"
              placeholder="请输入调度ID"
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
        <QueryBarItem label="任务标识：">
          <NInput
              v-model:value="queryItems.task_code"
              clearable
              type="text"
              placeholder="请输入任务标识"
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
        <QueryBarItem label="触发来源：">
          <NSelect
              v-model:value="queryItems.trigger_type"
              :options="triggerTypeOptions"
              clearable
              placeholder="请选择"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="执行状态：">
          <NSelect
              v-model:value="queryItems.celery_status"
              :options="celeryStatusOptions"
              clearable
              placeholder="请选择状态"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="开始时间：">
          <NInput
              v-model:value="queryItems.celery_start_time_begin"
              clearable
              type="text"
              placeholder="如 2026-01-01 00:00:00"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="开始时间：">
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

    <NModal
      v-model:show="jsonModalShow"
      preset="card"
      :title="jsonModalTitle"
      :mask-closable="true"
      :close-on-esc="true"
      style="width: min(720px, 92vw)"
      @update:show="(v) => { if (!v) closeJsonModal() }"
    >
      <pre class="json-modal-pre">{{ jsonModalContent }}</pre>
      <template #footer>
        <div class="json-modal-footer">
          <NButton size="small" type="primary" @click="copyJsonContent">复制</NButton>
        </div>
      </template>
    </NModal>
  </CommonPage>
</template>

<script setup>
import { h, ref } from 'vue'
import { NButton, NInput, NModal, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import api from '@/api'
import { formatDateTime } from '@/utils'

defineOptions({ name: '执行记录' })

const $table = ref(null)
const queryItems = ref({})

const jsonModalShow = ref(false)
const jsonModalTitle = ref('')
const jsonModalContent = ref('')

const celeryStatusOptions = [
  { label: '等待执行', value: '等待执行' },
  { label: '正在执行', value: '正在执行' },
  { label: '成功', value: '成功' },
  { label: '失败', value: '失败' },
]

const triggerTypeOptions = [
  { label: '手动执行', value: '手动执行' },
  { label: '定时执行', value: '定时执行' },
]

const getTaskRecordList = async (params = {}) => {
  return api.getApiTaskRecordList(params)
}

const toPrettyJson = (val) => {
  if (val == null || val === '') return ''
  if (typeof val === 'string') {
    try {
      return JSON.stringify(JSON.parse(val), null, 2)
    } catch {
      return val
    }
  }
  try {
    return JSON.stringify(val, null, 2)
  } catch {
    return String(val)
  }
}

const formatJsonBrief = (val, maxLen = 48) => {
  if (val == null || val === '') return '-'
  const s = typeof val === 'string' ? val : JSON.stringify(val)
  return s.length > maxLen ? `${s.slice(0, maxLen)}...` : s
}

const openJsonModal = (title, val) => {
  const pretty = toPrettyJson(val)
  if (!pretty) {
    window.$message?.warning?.('暂无内容')
    return
  }
  jsonModalTitle.value = title
  jsonModalContent.value = pretty
  jsonModalShow.value = true
}

const closeJsonModal = () => {
  jsonModalShow.value = false
  jsonModalTitle.value = ''
  jsonModalContent.value = ''
}

const copyJsonContent = async () => {
  const text = jsonModalContent.value || ''
  if (!text) {
    window.$message?.warning?.('暂无内容可复制')
    return
  }
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    window.$message?.success?.('已复制到剪贴板')
  } catch (e) {
    window.$message?.error?.('复制失败，请手动选择复制')
  }
}

const renderJsonCell = (title, val) => {
  const pretty = toPrettyJson(val)
  if (!pretty) return h('span', '-')
  return h(
    'span',
    {
      class: 'json-cell-trigger',
      title: '点击查看完整内容',
      onClick: () => openJsonModal(title, val),
    },
    formatJsonBrief(val),
  )
}

const formatCaseIds = (ids) => {
  if (!Array.isArray(ids) || !ids.length) return '-'
  const s = ids.join(', ')
  return s.length > 40 ? `${s.slice(0, 40)}...` : s
}

const columns = [
  { title: '任务名称', key: 'task_name', width: 300, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务类型', key: 'task_type', width: 200, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '触发来源',
    key: 'trigger_type',
    width: 100,
    align: 'center',
    render(row) {
      const typeMap = { 手动执行: 'info', 定时执行: 'warning' }
      return h(
        NTag,
        { type: typeMap[row.trigger_type] || 'default', size: 'small', round: true },
        () => row.trigger_type || '-',
      )
    },
  },
  {
    title: '用例ID',
    key: 'case_ids',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const s = formatCaseIds(row.case_ids)
      return h('span', { title: Array.isArray(row.case_ids) ? row.case_ids.join(', ') : '' }, s)
    },
  },
  {
    title: '执行状态',
    key: 'celery_status',
    width: 100,
    align: 'center',
    render(row) {
      const typeMap = { 等待执行: 'default', 正在执行: 'warning', 成功: 'success', 失败: 'error' }
      return h(
        NTag,
        { type: typeMap[row.celery_status] || 'default', size: 'small', round: true },
        () => row.celery_status || '-',
      )
    },
  },
  {
    title: '执行参数',
    key: 'exec_snapshot',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return renderJsonCell('执行参数', row.exec_snapshot)
    },
  },
  {
    title: '执行结果',
    key: 'task_summary',
    width: 220,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return renderJsonCell('执行结果', row.task_summary)
    },
  },
  { title: '执行耗时', key: 'celery_duration', width: 90, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '错误信息',
    key: 'task_error',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const s = row.task_error
      if (!s) return h('span', '-')
      return h('span', { title: s }, s.length > 80 ? `${s.slice(0, 80)}...` : s)
    },
  },
  {
    title: '开始时间',
    key: 'celery_start_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', row.celery_start_time ? formatDateTime(row.celery_start_time) : '-')
    },
  },
  {
    title: '结束时间',
    key: 'celery_end_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', row.celery_end_time ? formatDateTime(row.celery_end_time) : '-')
    },
  },
  { title: '批次标识', key: 'batch_code', width: 400, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务标识', key: 'task_code', width: 400, align: 'center', ellipsis: { tooltip: true } },
  { title: '记录ID', key: 'record_id', width: 80, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务ID', key: 'task_id', width: 90, align: 'center', ellipsis: { tooltip: true } },
  { title: '调度ID', key: 'celery_id', width: 400, align: 'center', ellipsis: { tooltip: true } },
  { title: '回溯ID', key: 'celery_trace_id', width: 400, align: 'center', ellipsis: { tooltip: true } },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
.json-modal-footer {
  display: flex;
  justify-content: flex-end;
}
.json-modal-pre {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  padding: 12px;
  border-radius: 6px;
  background: #f7f8fa;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.45;
}
</style>

<style>
.json-cell-trigger {
  color: #2080f0;
  cursor: pointer;
  word-break: break-all;
}
</style>
