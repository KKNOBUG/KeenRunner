<!--
  压测接口列表页 — 性能域自有施压资产（一个资产 = 一个请求 + 断言 + 提取）

新增/编辑跳转独立子页（/performance/api/edit，query 传 api_id，草稿队列经 sessionStorage 传递）；
  操作列对齐测试用例页（调试/删除平铺 + 更多下拉：复制、编辑），行内调试抽屉保留；
  导入通道从功能资产生成草稿后逐条跳转编辑页确认保存。
-->
<template>
  <CommonPage show-footer title="压测接口">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :get-data="fetchApiList"
        :query-bar-props="queryBarProps"
        :scroll-x="2070"
        row-key="api_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="goCreate"
        @query-bar-delete="handleBatchDelete"
    >
      <template #queryBar>
        <QueryBarItem label="接口名称" :label-width="70">
          <NInput v-model:value="queryItems.api_name" type="text" placeholder="接口名称(模糊)" clearable />
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
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NDropdown, NInput, NPopconfirm, NSelect, NTag,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import PerfApiDebugDrawer from './components/PerfApiDebugDrawer.vue'
import PerfApiImportModal from './components/PerfApiImportModal.vue'

import { formatDateTime, renderIcon } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测接口' })

const router = useRouter()

/** 导入草稿队列在 sessionStorage 的键（编辑页逐条消费，key 与编辑页一致） */
const DRAFT_QUEUE_KEY = 'perf_api_draft_queue'

const DEBUG_STATE_LABELS = { never: '未调试', success: '成功', failed: '失败' }
const DEBUG_STATE_TAG_TYPES = { success: 'success', failed: 'error' }

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'split',
}

const $table = ref(null)
const debugRef = ref(null)
const importRef = ref(null)

/** 跨页复选保留的勾选主键（同测试用例页逻辑） */
const checkedRowKeys = ref([])

const queryItems = ref({
  api_name: null,
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

/** 所属应用列：request_project_id → 应用名映射 */
const projectNameMap = computed(() => Object.fromEntries(projectOptions.value.map((p) => [p.value, p.label])))

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

// 列宽与样式对齐测试用例页（序号/用例名称/用例描述/用例类型/最后执行结果/审计四列）
const columns = [
  { type: 'selection', fixed: 'left', width: 48 },
  {
    title: '序号',
    key: 'row_no',
    width: 50,
    align: 'center',
    fixed: 'left',
    render: (_row, index) => renderRowNo(index),
  },
  {
    title: '接口类型',
    key: 'step_type',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => h(NTag, { type: row.step_type === 'tcp' ? 'warning' : 'info', round: true, bordered: true },
        { default: () => (row.step_type === 'tcp' ? 'TCP' : 'HTTP') }),
  },
  {
    title: '接口名称',
    key: 'api_name',
    width: 300,
    align: 'center',
    ellipsis: { tooltip: true },
    // 名称超链接直达编辑子页（超链接样式对齐测试用例页用例名称列）
    render: (row) => {
      const name = row.api_name || ''
      return h(
        'a',
        {
          href: 'javascript:void(0)',
          title: name,
          style: {
            display: 'inline-block',
            maxWidth: '100%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: '#2080f0',
            textDecoration: 'underline',
            cursor: 'pointer',
          },
          onClick: (e) => {
            e.preventDefault()
            goEdit(row)
          },
        },
        name
      )
    },
  },
  {
    title: '接口描述',
    key: 'api_desc',
    width: 300,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '接口地址',
    key: 'request_url',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => row.request_url || '-',
  },
  {
    title: '所属应用',
    key: 'request_project_id',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => h('span', projectNameMap.value[row.request_project_id] || '-'),
  },
  {
    title: '最后调试结果',
    key: 'debug_state',
    width: 110,
    align: 'center',
    render: (row) => h(NTag, { type: DEBUG_STATE_TAG_TYPES[row.debug_state] || 'default', size: 'small', round: true },
        { default: () => DEBUG_STATE_LABELS[row.debug_state] || row.debug_state || '未调试' }),
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 180,
    align: 'center',
    render: (row) => h('span', row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 180,
    align: 'center',
    render: (row) => h('span', row.created_time ? formatDateTime(row.created_time) : '-'),
  },
  {
    // 操作列对齐测试用例页：调试/删除平铺 + 「更多」下拉（复制、编辑）
    title: '操作',
    key: 'actions',
    width: 130,
    align: 'center',
    fixed: 'right',
    render(row) {
      const dropdownOptions = [
        {
          label: '复制',
          key: 'copy',
          icon: renderIcon('material-symbols:content-copy-outline', { size: 16 }),
          onClick: () => handleCopy(row),
        },
        {
          label: '编辑',
          key: 'edit',
          icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
          onClick: () => goEdit(row),
        },
      ]
      return [
        h(NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'primary',
              onClick: () => debugRef.value?.open(row),
            },
            {
              default: () => '调试',
              icon: renderIcon('material-symbols:play-arrow', { size: 16 }),
            }
        ),
        h(NPopconfirm,
            {
              onPositiveClick: () => handleDelete(row),
              onNegativeClick: () => {},
            },
            {
              trigger: () =>
                  h(NButton,
                      {
                        size: 'tiny',
                        quaternary: true,
                        type: 'error',
                      },
                      {
                        default: () => '删除',
                        icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                      }
                  ),
              default: () => h('div', {}, '确定删除该压测接口?'),
            }
        ),
        h(NDropdown,
            {
              trigger: 'click',
              options: dropdownOptions.map((opt) => ({
                label: opt.label,
                key: opt.key,
                icon: opt.icon,
                disabled: opt.disabled,
              })),
              onSelect: (key) => dropdownOptions.find((o) => o.key === key)?.onClick?.(),
            },
            {
              default: () =>
                  h(NButton,
                      {
                        size: 'tiny',
                        quaternary: true,
                        type: 'default',
                      },
                      {
                        default: () => '更多',
                        icon: renderIcon('material-symbols:more-horiz', { size: 16 }),
                      }
                  ),
            }
        ),
      ]
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

/** 批量删除勾选项（跨页复选保留，口径对齐测试用例页） */
async function handleBatchDelete() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的压测接口')
    return
  }
  await window.$dialog?.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条压测接口吗？`,
    async confirm() {
      await Promise.all(ids.map((api_id) => api.deletePerfApi({ api_id })))
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
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
