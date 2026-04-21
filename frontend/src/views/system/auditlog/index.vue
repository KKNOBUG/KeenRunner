<script setup>
import { computed, h, ref } from 'vue'
import {
  NButton,
  NCard,
  NDatePicker,
  NDescriptions,
  NDescriptionsItem,
  NInput,
  NModal,
  NScrollbar,
  NSelect,
  NTabPane,
  NTabs,
  NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import api from '@/api'
import { formatDateTime, renderIcon } from '@/utils'

defineOptions({ name: '审计日志' })

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: true,
  actionMode: 'dropdown',
}

async function handleBatchDelete() {
  const ids = checkedRowKeys.value || []
  if (!ids.length) {
    $message.warning('请先勾选要删除的日志')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条审计日志吗？删除后不可恢复。`,
    async confirm() {
      await api.deleteAuditLogBatch({ audit_ids: ids })
      $message.success('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

const detailVisible = ref(false)
const detailRow = ref(null)

function formatTimestamp(timestamp) {
  const date = new Date(timestamp)
  const pad = (num) => num.toString().padStart(2, '0')
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hours = pad(date.getHours())
  const minutes = pad(date.getMinutes())
  const seconds = pad(date.getSeconds())
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

function getStartOfDayTimestamp() {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  return now.getTime()
}

function getEndOfDayTimestamp() {
  const now = new Date()
  now.setHours(23, 59, 59, 999)
  return now.getTime()
}

function makeDefaultQuery() {
  const s = getStartOfDayTimestamp()
  const e = getEndOfDayTimestamp()
  return {
    username: '',
    request_tags: '',
    request_summary: '',
    request_method: undefined,
    request_router: '',
    response_code: '',
    start_time: formatTimestamp(s),
    end_time: formatTimestamp(e),
  }
}

const queryItems = ref(makeDefaultQuery())

/** 与 queryItems 同步，重置 QueryBar 时日期控件一致 */
const datetimeRangeModel = computed({
  get() {
    const st = queryItems.value.start_time
    const et = queryItems.value.end_time
    if (!st || !et) return null
    const t0 = new Date(String(st).replace(' ', 'T')).getTime()
    const t1 = new Date(String(et).replace(' ', 'T')).getTime()
    if (Number.isNaN(t0) || Number.isNaN(t1)) return null
    return [t0, t1]
  },
  set(value) {
    if (value == null) {
      queryItems.value.start_time = null
      queryItems.value.end_time = null
    } else {
      queryItems.value.start_time = formatTimestamp(value[0])
      queryItems.value.end_time = formatTimestamp(value[1])
    }
  },
})

const methodOptions = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'DELETE', value: 'DELETE' },
]

/** 请求状态：根据响应代码判断成功/失败 */
function getRequestStatus(row) {
  const code = String(row.response_code || '')
  if (code === '000000' || code === '200') return { text: '成功', type: 'success' }
  return { text: '失败', type: 'error' }
}

/** 格式化请求/响应参数：支持 JSON、XML、Text */
function formatParams(value) {
  if (value == null || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  const str = String(value)
  const trimmed = str.trim()
  if (!trimmed) return '-'
  // 尝试 JSON 格式化
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed)
      return JSON.stringify(parsed, null, 2)
    } catch {
      return trimmed
    }
  }
  // 尝试 XML 格式化（简单缩进）
  if (trimmed.startsWith('<?xml') || trimmed.startsWith('<')) {
    try {
      return formatXml(trimmed)
    } catch {
      return trimmed
    }
  }
  return trimmed
}

function formatXml(xml) {
  let formatted = ''
  let indent = 0
  const parts = xml.replace(/>\s*</g, '><').split(/(?=<)|(?<=>)/)
  for (const part of parts) {
    if (part.startsWith('</')) indent = Math.max(0, indent - 1)
    formatted += '  '.repeat(indent) + part + (part.endsWith('>') && !part.startsWith('</') ? '\n' : '')
    if (part.startsWith('<') && !part.startsWith('</') && !part.endsWith('/>')) indent++
  }
  return formatted.trim() || xml
}

/** 渲染对象为 JSON 字符串（如请求头） */
function formatObject(value) {
  if (value == null) return ''
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function openDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    { type: 'selection', fixed: 'left', width: 48 },
    {
      title: '序号',
      key: '__seq',
      width: 64,
      align: 'center',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '日志ID',
      key: 'id',
      width: 80,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '用户名称',
      key: 'username',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h(NTag, { type: 'primary' }, { default: () => row.username || '-' })
      },
    },
    {
      title: '功能模块',
      key: 'request_tags',
      width: 120,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h(NTag, { type: 'info' }, { default: () => row.request_tags || '-' })
      },
    },
    {
      title: '接口概要',
      key: 'request_summary',
      width: 160,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '请求方法',
      key: 'request_method',
      width: 90,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '请求路由',
      key: 'request_router',
      width: 180,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '请求状态',
      key: 'request_status',
      width: 90,
      align: 'center',
      render(row) {
        const { text, type } = getRequestStatus(row)
        return h(NTag, { type }, { default: () => text })
      },
    },
    {
      title: '响应代码',
      key: 'response_code',
      width: 90,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '响应信息',
      key: 'response_message',
      width: 140,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      align: 'center',
      fixed: 'right',
      render(row) {
        return h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'info',
              onClick: () => openDetail(row),
            },
            { default: () => '详情', icon: renderIcon('material-symbols:visibility-outline', { size: 16 }) }
        )
      },
    },
  ]
})
</script>

<template>
  <CommonPage>
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="api.getAuditLogList"
        :single-line="true"
        :scroll-x="1320"
        row-key="id"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="用户名称：">
          <NInput
              v-model:value="queryItems.username"
              clearable
              type="text"
              placeholder="请输入用户名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="功能模块：">
          <NInput
              v-model:value="queryItems.request_tags"
              clearable
              type="text"
              placeholder="请输入功能模块"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="接口概要：">
          <NInput
              v-model:value="queryItems.request_summary"
              clearable
              type="text"
              placeholder="请输入接口概要"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="请求方法：">
          <NSelect
              v-model:value="queryItems.request_method"
              style="width: 180px"
              :options="methodOptions"
              clearable
              placeholder="请选择请求方法"
          />
        </QueryBarItem>
        <QueryBarItem label="请求路由：">
          <NInput
              v-model:value="queryItems.request_router"
              clearable
              type="text"
              placeholder="请输入请求路由"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="响应代码：">
          <NInput
              v-model:value="queryItems.response_code"
              clearable
              type="text"
              placeholder="请输入响应代码"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="创建时间：">
          <NDatePicker
              v-model:value="datetimeRangeModel"
              type="datetimerange"
              clearable
              placeholder="请选择时间范围"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <!-- 详情弹窗：居中，左右各 10% 边距 -->
    <NModal
        v-model:show="detailVisible"
        preset="card"
        title="详情"
        class="audit-log-detail-modal"
        transform-origin="center"
        :bordered="false"
        size="medium"
        :style="{ width: '80%' }"
    >
      <template v-if="detailRow">
        <NTabs type="line" class="audit-detail-tabs">
          <NTabPane name="request" tab="请求信息">
            <div class="audit-detail-content">
              <NDescriptions :column="1" label-placement="left" :label-style="{ width: '90px', fontWeight: 500 }">
                <NDescriptionsItem label="请求方法">{{ detailRow.request_method || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="请求路由">{{ detailRow.request_router || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="请求来源">{{ detailRow.request_client || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="请求时间">{{ formatDateTime(detailRow.request_time) }}</NDescriptionsItem>
              </NDescriptions>
              <div class="audit-params-section">
                <div>请求头部：</div>
                <NCard size="small" content-style="padding: 12px;">
                  <NScrollbar style="max-height: 300px;">
                    <textarea v-if="formatObject(detailRow.request_header)" class="audit-code" readonly rows="12" :value="formatObject(detailRow.request_header)" />
                    <span v-else>-</span>
                  </NScrollbar>
                </NCard>
              </div>
              <div class="audit-params-section">
                <div>请求参数：</div>
                <NCard size="small" content-style="padding: 12px;">
                  <NScrollbar style="max-height: 300px;">
                    <textarea v-if="formatParams(detailRow.request_params) !== '-'" class="audit-code" readonly rows="12" :value="formatParams(detailRow.request_params)" />
                    <span v-else>-</span>
                  </NScrollbar>
                </NCard>
              </div>
            </div>
          </NTabPane>
          <NTabPane name="response" tab="响应信息">
            <div class="audit-detail-content">
              <NDescriptions :column="1" label-placement="left" :label-style="{ width: '90px', fontWeight: 500 }">
                <NDescriptionsItem label="响应代码">{{ detailRow.response_code || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="响应信息">{{ detailRow.response_message || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="响应时间">{{ detailRow.response_time || '-' }}</NDescriptionsItem>
                <NDescriptionsItem label="响应耗时">{{ detailRow.response_elapsed || '-' }}</NDescriptionsItem>
              </NDescriptions>
              <div class="audit-params-section">
                <div>响应头部：</div>
                <NCard size="small" content-style="padding: 12px;">
                  <NScrollbar style="max-height: 300px;">
                    <textarea v-if="formatObject(detailRow.response_header)" class="audit-code" readonly rows="12" :value="formatObject(detailRow.response_header)" />
                    <span v-else>-</span>
                  </NScrollbar>
                </NCard>
              </div>
              <div class="audit-params-section">
                <div>响应参数：</div>
                <NCard size="small" content-style="padding: 12px;">
                  <NScrollbar style="max-height: 300px;">
                    <textarea v-if="formatParams(detailRow.response_params) !== '-'" class="audit-code" readonly rows="12" :value="formatParams(detailRow.response_params)" />
                    <span v-else>-</span>
                  </NScrollbar>
                </NCard>
              </div>
            </div>
          </NTabPane>
        </NTabs>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.audit-detail-tabs {
  margin-top: 8px;
}

.audit-detail-content {
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.audit-params-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 只读 textarea：支持 Ctrl+A 全选、Ctrl+C 复制，仅选中当前块内容；颜色继承主题 */
.audit-code {
  display: block;
  width: 100%;
  margin: 0;
  padding: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--n-text-color, inherit);
  cursor: text;
}

</style>
