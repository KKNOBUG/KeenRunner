<template>
  <CommonPage show-footer title="任务记录">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="getTaskRecordList"
        :extra-params="extraParams"
        :scroll-x="1530"
        :single-line="true"
        row-key="record_id"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="任务名称：">
          <NInput
              v-model:value="queryItems.task_name"
              clearable
              type="text"
              placeholder="请输入任务名称(支持模糊)"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="任务状态：">
          <NSelect
              v-model:value="queryItems.celery_status"
              :options="statusOptions"
              clearable
              placeholder="请选择任务状态"
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
import { NButton, NDatePicker, NDropdown, NInput, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import api from '@/api'
import { formatDateTime, renderIcon } from '@/utils'
import { TASK_RECORD_TASK_TYPE_VALUES } from '@/constants/autotestTaskType'

defineOptions({ name: '任务记录' }) // 与菜单名一致，供 KeepAlive include 匹配

const $table = ref(null)
const queryItems = ref({})
/** 定时任务（多用例编排）执行记录范围：固定随请求下发，与异步中心互不重叠 */
const extraParams = { task_type_in: TASK_RECORD_TASK_TYPE_VALUES }
const statusOptions = ['等待执行', '正在执行', '成功', '失败', '部分成功'].map((v) => ({ label: v, value: v }))
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
const getTaskRecordList = (params = {}) => {
  const { _operate_date, ...rest } = params
  return api.getApiTaskRecordList(rest)
}

const onPaginationMeta = (meta) => {
  pageMeta.value = meta
}

/* ---------- 行状态口径 ---------- */

const STATUS_TAG_TYPE = { 成功: 'success', 失败: 'error', 正在执行: 'info', 等待执行: 'default', 部分成功: 'warning' }
const TRIGGER_TAG_TYPE = { 手动执行: 'info', 定时执行: 'warning' }

/* ---------- 详情与下载 ---------- */

const rowKeyOf = (row) => row.record_id ?? row.id

/** 详情：以 Message 浮层展示失败原因（可手动关闭；超长截断避免撑爆提示条） */
const showDetail = (row) => {
  const error = row.task_error || ''
  const brief = error.length > 300 ? `${error.slice(0, 300)}…` : error
  window.$message?.error?.(brief || '无失败原因信息', { closable: true, duration: 10000 })
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

/** 下载动作：无附件置灰；单附件直接下载；多附件下拉选择文件后下载 */
function renderDownloadAction(row) {
  const atts = attachmentsOf(row.task_summary)
  const icon = () => ({ default: () => '下载', icon: renderIcon('material-symbols:download', {size: 16}) })
  if (!atts.length) {
    return h(
        NButton,
        { size: 'tiny', quaternary: true, type: 'primary', disabled: true, title: '仅拥有产物文件的任务可下载' },
        icon,
    )
  }
  if (atts.length === 1) {
    return h(
        NButton,
        { size: 'tiny', quaternary: true, type: 'primary', title: '下载产物文件', onClick: () => downloadAttachment(row, atts[0]) },
        icon,
    )
  }
  return h(
      NDropdown,
      {
        trigger: 'click',
        options: atts.map((a, i) => ({ label: a.name || `附件${i + 1}`, key: String(i) })),
        onSelect: (key) => downloadAttachment(row, atts[Number(key)]),
      },
      {
        default: () =>
            h(NButton, { size: 'tiny', quaternary: true, type: 'primary', title: '选择产物文件下载' }, {
              default: () => `附件(${atts.length})`,
              icon: renderIcon('material-symbols:download', {size: 16}),
            }),
      },
  )
}

/* ---------- 列定义 ---------- */

const columns = [
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
    render: (row) => row.task_type || '-',
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
  {
    title: '触发来源',
    key: 'trigger_type',
    width: 100,
    align: 'center',
    render(row) {
      return h(
          NTag,
          { type: TRIGGER_TAG_TYPE[row.trigger_type] || 'default', size: 'small', round: true },
          () => row.trigger_type || '-',
      )
    },
  },
  { title: '批次码', key: 'batch_code', width: 160, align: 'center', ellipsis: { tooltip: true } },
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
  { title: '耗时', key: 'celery_duration', width: 80, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    align: 'center',
    fixed: 'right',
    render(row) {
      // 按钮样式对齐任务列表/异步中心操作列：quaternary 无底色按钮 + 16px 图标
      const actions = [
        h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'primary',
              disabled: !row.task_error,
              title: row.task_error ? '查看失败原因' : '仅存在失败原因的任务可查看详情',
              onClick: () => showDetail(row),
            },
            {
              default: () => '详情',
              icon: renderIcon('material-symbols:info-outline', {size: 16}),
            },
        ),
        renderDownloadAction(row),
      ]
      return actions
    },
  },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
</style>
