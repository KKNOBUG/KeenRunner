<template>
  <CommonPage show-footer title="异步中心">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:expanded-row-keys="expandedRowKeys"
        :columns="columns"
        :get-data="getAsyncCenterRecordList"
        :extra-params="extraParams"
        :scroll-x="1440"
        :single-line="true"
        row-key="record_id"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="任务类型：">
          <NSelect
              v-model:value="queryItems.task_type"
              :options="taskTypeOptions"
              clearable
              placeholder="请选择任务类型"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              type="text"
              placeholder="请输入创建人员(支持模糊)"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="操作时间：">
          <NDatePicker
              v-model:value="operateDate"
              type="date"
              clearable
              placeholder="请选择操作日期"
              class="query-input"
          />
        </QueryBarItem>
      </template>
    </CrudTable>
  </CommonPage>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { NButton, NDatePicker, NInput, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import api from '@/api'
import { formatDateTime } from '@/utils'
import {
  ASYNC_CENTER_TASK_TYPE_OPTIONS,
  ASYNC_CENTER_TASK_TYPE_VALUES,
  taskTypeLabel,
} from '@/constants/autotestTaskType'

defineOptions({ name: '异步中心' })

const $table = ref(null)
const queryItems = ref({})
/** 非脚本执行类任务类型集合：本页仅展示异步中心范围记录，固定随请求下发 */
const extraParams = { task_type_in: ASYNC_CENTER_TASK_TYPE_VALUES }
const taskTypeOptions = ASYNC_CENTER_TASK_TYPE_OPTIONS
/** 失败原因展开行（配合操作列「详情」按钮切换） */
const expandedRowKeys = ref([])
/** 分页元数据：渲染跨页「序号」列 */
const pageMeta = ref({ page: 1, page_size: 10 })

/** 操作时间(精确到日)：选择器时间戳 ⇄ celery_start_time 起止区间；键名带下划线表示纯前端字段，请求前剔除 */
const operateDate = computed({
  get: () => queryItems.value._operate_date ?? null,
  set: (ts) => {
    queryItems.value._operate_date = ts
    if (ts) {
      const d = new Date(ts)
      const pad = (n) => String(n).padStart(2, '0')
      const day = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
      queryItems.value.celery_start_time_begin = `${day} 00:00:00`
      queryItems.value.celery_start_time_end = `${day} 23:59:59`
    } else {
      queryItems.value.celery_start_time_begin = null
      queryItems.value.celery_start_time_end = null
    }
  },
})

/** 列表请求：剔除纯前端字段(操作时间原始值)后透传 */
const getAsyncCenterRecordList = (params = {}) => {
  const { _operate_date, ...rest } = params
  return api.getApiTaskRecordList(rest)
}

const onPaginationMeta = (meta) => {
  pageMeta.value = meta
}

/* ---------- 行状态口径 ---------- */

/** 终态状态集合：成功/失败/部分成功；终态行不可刷新、可删除 */
const FINAL_STATUSES = ['成功', '失败', '部分成功']
const isFinal = (row) => FINAL_STATUSES.includes(row.celery_status)
const STATUS_TAG_TYPE = { 成功: 'success', 失败: 'error', 正在执行: 'info', 等待执行: 'default', 部分成功: 'warning' }

/* ---------- 附件与下载 ---------- */

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

/* ---------- 行操作：详情展开 / 刷新 / 删除 ---------- */

const rowKeyOf = (row) => row.record_id ?? row.id

/** 详情：仅失败任务可用，切换行下方失败原因展开区 */
const toggleDetail = (row) => {
  const key = rowKeyOf(row)
  const idx = expandedRowKeys.value.indexOf(key)
  if (idx >= 0) expandedRowKeys.value.splice(idx, 1)
  else expandedRowKeys.value.push(key)
}

/** 刷新：仅进行中任务可用，按 celery_id 重查单条并原位替换行数据 */
const refreshRow = async (row) => {
  const celeryId = row.celery_id
  if (!celeryId) {
    window.$message?.warning?.('缺少调度ID，无法刷新')
    return
  }
  try {
    const res = await api.getApiTaskRecordList({
      celery_id: celeryId,
      task_type_in: ASYNC_CENTER_TASK_TYPE_VALUES,
      page: 1,
      page_size: 1,
    })
    const latest = res?.data?.[0]
    if (!latest) {
      window.$message?.warning?.('记录已不存在，正在刷新列表')
      $table.value?.handleQuery()
      return
    }
    const rows = $table.value?.tableData || []
    const idx = rows.findIndex((r) => rowKeyOf(r) === rowKeyOf(row))
    if (idx >= 0) rows.splice(idx, 1, latest)
    window.$message?.success?.('已刷新该任务状态')
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '刷新失败')
  }
}

/** 删除：仅终态任务可用，二次确认后硬删记录并清理产物文件 */
const removeRow = (row) => {
  $dialog.confirm({
    title: '删除确认',
    type: 'warning',
    content: '确定删除该任务记录吗？将同时清理产物文件，删除后不可恢复',
    async confirm() {
      await api.deleteApiTaskRecord(rowKeyOf(row))
      window.$message?.success?.('删除成功')
      $table.value?.handleSearch()
    },
  })
}

/* ---------- 列定义 ---------- */

const columns = [
  {
    type: 'expand',
    title: '失败原因',
    width: 90,
    renderExpand(row) {
      if (row.celery_status !== '失败') return h('span', { style: 'color:#999' }, '仅失败任务可查看失败原因')
      return h(
          'div',
          { style: 'white-space:pre-wrap;word-break:break-all;padding:8px 12px;line-height:1.6' },
          row.task_error || '无失败原因信息',
      )
    },
  },
  {
    title: '序号',
    key: 'index',
    width: 60,
    align: 'center',
    render: (row, index) => (pageMeta.value.page - 1) * pageMeta.value.page_size + index + 1,
  },
  { title: '任务名称', key: 'task_name', width: 300, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '任务类型',
    key: 'task_type',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => taskTypeLabel(row.task_type),
  },
  {
    title: '任务状态',
    key: 'celery_status',
    width: 100,
    align: 'center',
    render(row) {
      return h(
          NTag,
          { type: STATUS_TAG_TYPE[row.celery_status] || 'default', size: 'small', round: true },
          () => row.celery_status || '-',
      )
    },
  },
  { title: '创建人员', key: 'created_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作时间',
    key: 'celery_start_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', row.celery_start_time ? formatDateTime(row.celery_start_time) : '-')
    },
  },
  {
    title: '完成时间',
    key: 'celery_end_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', row.celery_end_time ? formatDateTime(row.celery_end_time) : '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(
              NButton,
              {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                disabled: row.celery_status !== '失败',
                onClick: () => toggleDetail(row),
              },
              { default: () => '详情' },
          ),
          h(
              NButton,
              {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                disabled: isFinal(row),
                title: isFinal(row) ? '仅进行中任务可刷新' : '',
                onClick: () => refreshRow(row),
              },
              { default: () => '刷新' },
          ),
          h(
              NButton,
              {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                disabled: row.celery_status !== '成功' || !attachmentsOf(row.task_summary).length,
                title: '仅成功且拥有可下载产物的任务可下载',
                onClick: () => downloadAttachment(row, attachmentsOf(row.task_summary)[0]),
              },
              { default: () => '下载' },
          ),
          h(
              NButton,
              {
                size: 'tiny',
                type: 'error',
                secondary: true,
                disabled: !isFinal(row),
                title: isFinal(row) ? '' : '仅成功/失败任务可删除',
                onClick: () => removeRow(row),
              },
              { default: () => '删除' },
          ),
        ],
      })
    },
  },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
</style>
