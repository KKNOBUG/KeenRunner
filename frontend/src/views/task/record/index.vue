<template>
  <CommonPage show-footer title="任务记录">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="getTaskRecordList"
        :scroll-x="3050"
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

    <!-- 结果摘要/JSON 只读查看弹框（共用 TextPreviewModal：monaco 只读 + 复制） -->
    <TextPreviewModal
        v-model:show="previewShow"
        :title="previewTitle"
        :content="previewContent"
    />
  </CommonPage>
</template>

<script setup>
import { h, ref } from 'vue'
import { NButton, NDropdown, NInput, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TextPreviewModal from '@/components/common/TextPreviewModal.vue'

import api from '@/api'
import { formatDateTime, formatJsonBrief, resultPayloadOf, toPrettyJson } from '@/utils'

defineOptions({ name: '执行记录' })

const $table = ref(null)
const queryItems = ref({})

/** 结果摘要查看弹框（共用 TextPreviewModal） */
const previewShow = ref(false)
const previewTitle = ref('')
const previewContent = ref('')

const celeryStatusOptions = [
  { label: '等待执行', value: '等待执行' },
  { label: '正在执行', value: '正在执行' },
  { label: '成功', value: '成功' },
  { label: '失败', value: '失败' },
  { label: '部分成功', value: '部分成功' },
]

const triggerTypeOptions = [
  { label: '手动执行', value: '手动执行' },
  { label: '定时执行', value: '定时执行' },
]

const getTaskRecordList = async (params = {}) => {
  return api.getApiTaskRecordList(params)
}

/** 打开查看弹框：格式化后为空则提示不弹框 */
const openPreview = (title, val) => {
  const pretty = toPrettyJson(val)
  if (!pretty) {
    window.$message?.warning?.('暂无内容')
    return
  }
  previewTitle.value = title
  previewContent.value = pretty
  previewShow.value = true
}

const renderJsonCell = (title, val) => {
  const pretty = toPrettyJson(val)
  if (!pretty) return h('span', '-')
  return h(
    'span',
    {
      class: 'json-cell-trigger',
      title: '点击查看完整内容',
      onClick: () => openPreview(title, val),
    },
    formatJsonBrief(val),
  )
}

/** 附件列表：信封 attachments，或旧格式顶层 file_path/file_name */
const attachmentsOf = (summary) => {
  if (!summary || typeof summary !== 'object') return []
  if (Array.isArray(summary.attachments) && summary.attachments.length) {
    return summary.attachments.filter((a) => a && typeof a === 'object')
  }
  if (summary.file_path || summary.file_name) {
    return [{ key: 'main', name: summary.file_name || 'download.bin' }]
  }
  return []
}

const downloadAttachment = async (row, att) => {
  const recordId = row.record_id ?? row.id
  if (recordId == null) {
    window.$message?.warning?.('缺少记录ID')
    return
  }
  try {
    const res = await api.downloadApiTaskRecordAttachment(recordId, att?.key || 'main')
    const blob = new Blob([res.data], { type: att?.content_type || 'application/octet-stream' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const matched = /filename\*=UTF-8''([^;]+)/i.exec(cd) || /filename="?([^";]+)"?/i.exec(cd)
    link.download = matched?.[1] ? decodeURIComponent(matched[1]) : (att?.name || 'download.bin')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    window.$message?.error?.(e?.message || '下载失败')
  }
}

/** 单文件直接下；多文件下拉选文件后下 */
const renderAttachmentCell = (row) => {
  const items = attachmentsOf(row.task_summary)
  if (!items.length) return h('span', '-')
  if (items.length === 1) {
    const att = items[0]
    const label = att.name || att.key || '下载'
    return h(
      NButton,
      {
        size: 'tiny',
        type: 'primary',
        quaternary: true,
        onClick: () => downloadAttachment(row, att),
      },
      () => (label.length > 18 ? `${label.slice(0, 18)}...` : label),
    )
  }
  return h(
    NDropdown,
    {
      trigger: 'click',
      options: items.map((att, idx) => ({
        label: att.name || att.key || `文件${idx + 1}`,
        key: String(att.key ?? idx),
      })),
      onSelect: (key) => {
        const att = items.find((a, idx) => String(a.key ?? idx) === String(key))
        if (att) downloadAttachment(row, att)
      },
    },
    {
      default: () => h(
        NButton,
        { size: 'tiny', type: 'primary', quaternary: true },
        () => `附件(${items.length})`,
      ),
    },
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
      const typeMap = { 等待执行: 'default', 正在执行: 'warning', 成功: 'success', 失败: 'error', 部分成功: 'warning' }
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
      return renderJsonCell('执行结果', resultPayloadOf(row.task_summary))
    },
  },
  {
    title: '附件',
    key: 'attachments',
    width: 140,
    align: 'center',
    render: renderAttachmentCell,
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
  { title: '创建人员', key: 'created_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
  { title: '维护人员', key: 'updated_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
  { title: '批次标识', key: 'batch_code', width: 400, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务标识', key: 'task_code', width: 400, align: 'center', ellipsis: { tooltip: true } },
  { title: '记录ID', key: 'record_id', width: 80, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务ID', key: 'task_id', width: 90, align: 'center', ellipsis: { tooltip: true } },
  { title: '调度ID', key: 'celery_id', width: 400, align: 'center', ellipsis: { tooltip: true } },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
</style>

<style>
.json-cell-trigger {
  color: #2080f0;
  cursor: pointer;
  word-break: break-all;
}
</style>
