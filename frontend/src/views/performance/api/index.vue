<!--
  压测接口列表页 — 性能域自有施压资产（一个资产 = 一个请求 + 断言 + 提取）

  新增/编辑跳转独立子页（/performance/api/edit，query 传 api_id，草稿队列经 sessionStorage 传递）；
  调试结论（debug_state）是场景执行预检闸门的依据，行内调试抽屉保留；
  导入通道从功能资产生成草稿后逐条跳转编辑页确认保存。
-->
<template>
  <CommonPage show-footer title="压测接口">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchApiList"
        :query-bar-props="queryBarProps"
        :scroll-x="1280"
        row-key="api_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="goCreate"
    >
      <template #queryBar>
        <QueryBarItem label="接口名称" :label-width="70">
          <NInput v-model:value="queryItems.api_name" type="text" placeholder="接口名称(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="所属应用" :label-width="70">
          <NSelect
              v-model:value="queryItems.api_project"
              :options="projectOptions"
              placeholder="请选择"
              clearable
              filterable
              style="width: 160px"
          />
        </QueryBarItem>
        <QueryBarItem label="请求类型" :label-width="70">
          <NSelect
              v-model:value="queryItems.step_type"
              :options="stepTypeOptions"
              placeholder="请选择"
              clearable
              style="width: 130px"
          />
        </QueryBarItem>
      </template>
      <template #toolbar>
        <NButton size="small" type="primary" @click="openImport">
          <TheIcon icon="material-symbols:download-2-rounded" :size="18" class="mr-4" />
          从用例导入
        </NButton>
      </template>
    </CrudTable>

    <PerfApiDebugDrawer ref="debugRef" @finished="() => $table?.handleQuery()" />
    <PerfApiImportModal ref="importRef" @imported="handleImported" />
  </CommonPage>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NInput, NPopconfirm, NSelect, NSpace, NTag, NText,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import PerfApiDebugDrawer from './components/PerfApiDebugDrawer.vue'
import PerfApiImportModal from './components/PerfApiImportModal.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测接口' })

const router = useRouter()

/** 导入草稿队列在 sessionStorage 的键（编辑页逐条消费，key 与编辑页一致） */
const DRAFT_QUEUE_KEY = 'perf_api_draft_queue'

const DEBUG_STATE_LABELS = { never: '未调试', success: '调试通过', failed: '调试失败' }
const DEBUG_STATE_TAG_TYPES = { success: 'success', failed: 'error' }

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const debugRef = ref(null)
const importRef = ref(null)

const queryItems = ref({
  api_name: null,
  api_project: null,
  step_type: null,
})

const stepTypeOptions = [
  { label: 'HTTP请求', value: 'http' },
  { label: 'TCP请求', value: 'tcp' },
]

const projectOptions = ref([])
async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 规范为 PerfApiSelect 请求体（空值剔除） */
function fetchApiList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.searchPerfApiList(body)
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
  { title: '接口名称', key: 'api_name', width: 170, ellipsis: { tooltip: true } },
  {
    title: '请求定义',
    key: 'request_url',
    minWidth: 260,
    ellipsis: { tooltip: true },
    render: (row) => h(NText, { code: true }, { default: () => `${(row.request_method || 'TCP').toUpperCase()} ${row.request_url || '-'}` }),
  },
  {
    title: '类型',
    key: 'step_type',
    width: 80,
    render: (row) => h(NTag, { size: 'small', type: row.step_type === 'tcp' ? 'warning' : 'info' },
        { default: () => (row.step_type === 'tcp' ? 'TCP' : 'HTTP') }),
  },
  {
    title: '调试结论',
    key: 'debug_state',
    width: 90,
    render: (row) => h(NTag, { size: 'small', type: DEBUG_STATE_TAG_TYPES[row.debug_state] || 'default' },
        { default: () => DEBUG_STATE_LABELS[row.debug_state] || row.debug_state || '未调试' }),
  },
  { title: '版本', key: 'version', width: 60 },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 160,
    render: (row) => (row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 250,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => goEdit(row) },
              { default: () => '编辑' }),
          h(NButton, { size: 'tiny', type: 'success', secondary: true, onClick: () => debugRef.value?.open(row) },
              { default: () => '调试' }),
          h(NPopconfirm, { onPositiveClick: () => handleCopy(row) }, {
            trigger: () => h(NButton, { size: 'tiny', secondary: true }, { default: () => '复制' }),
            default: () => '复制为同应用下的新接口？',
          }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true }, { default: () => '删除' }),
            default: () => '确认删除该压测接口？',
          }),
        ],
      })
    },
  },
]

/** 新增跳编辑子页（无 query）；编辑携 api_id 进入 */
function goCreate() {
  router.push('/performance/api/edit')
}

function goEdit(row) {
  router.push({ path: '/performance/api/edit', query: { api_id: String(row.api_id) } })
}

async function handleCopy(row) {
  try {
    await api.copyPerfApi({ api_id: row.api_id })
    window.$message?.success('复制成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

async function handleDelete(row) {
  try {
    await api.deletePerfApi({ api_id: row.api_id })
    window.$message?.success('删除成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

function openImport() {
  importRef.value?.open(projectOptions.value)
}

/** 导入草稿队列：入 sessionStorage 后跳编辑子页逐条确认保存 */
function handleImported(drafts) {
  const queue = drafts || []
  if (!queue.length) return
  sessionStorage.setItem(DRAFT_QUEUE_KEY, JSON.stringify(queue))
  window.$message?.success(`已生成 ${queue.length} 个接口草稿，请逐条确认保存`)
  router.push({ path: '/performance/api/edit', query: { draft: '1' } })
}

onMounted(() => {
  loadProjects()
})
</script>
