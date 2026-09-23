<!--
  压测场景列表页 — 编排层资产（打什么、怎么打 + 判定口径）

  主视图 = scene 列表；支持复选框多选批量删除；
  行操作：编辑（跳转独立编辑页）/ 删除 / 更多（预检、跑全部、复制）。
-->
<template>
  <CommonPage show-footer title="压测场景">
    <QueryBar
        mb-30
        :add-reset="true"
        :add-search="true"
        :add-create="true"
        :add-delete="true"
        action-mode="split"
        @search="handleSearch"
        @reset="handleReset"
        @create="handleCreate"
        @delete="handleBatchDelete"
    >
      <QueryBarItem label="场景名称" :label-width="70">
        <NInput v-model:value="queryItems.scene_name" type="text" placeholder="场景名称(模糊)" clearable />
      </QueryBarItem>
      <QueryBarItem label="所属应用" :label-width="70">
        <NSelect
            v-model:value="queryItems.scene_project"
            :options="projectOptions"
            placeholder="请选择"
            clearable
            filterable
            style="width: 160px"
        />
      </QueryBarItem>
      <QueryBarItem label="施压模式" :label-width="70">
        <NSelect
            v-model:value="queryItems.run_mode"
            :options="runModeFilterOptions"
            placeholder="请选择"
            clearable
            style="width: 150px"
        />
      </QueryBarItem>
    </QueryBar>

    <n-data-table
        :remote="true"
        :loading="loading"
        :columns="columns"
        :data="tableData"
        :scroll-x="2010"
        :row-key="(row) => row.scene_id"
        :pagination="pagination"
        v-model:checked-row-keys="checkedRowKeys"
        @update:page="onPageChange"
    />

    <PerfScenePrecheckModal ref="precheckRef" />
  </CommonPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NDataTable, NDropdown, NInput, NPopconfirm, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import PerfScenePrecheckModal from './components/PerfScenePrecheckModal.vue'

import { formatDateTime, renderIcon } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测场景' })

const router = useRouter()

const RUN_MODE_LABELS = { single: '单接口', mixed: '混合流量', journey: '业务链路' }
const RUN_MODE_TAG_TYPES = { single: 'info', mixed: 'warning', journey: 'error' }
const ASSERT_MODE_LABELS = { all: '逐请求', sample_ratio: '抽样' }

const runModeFilterOptions = [
  { label: '单接口(single)', value: 'single' },
  { label: '混合流量(mixed)', value: 'mixed' },
]

const queryItems = ref({
  scene_name: null,
  scene_project: null,
  run_mode: null,
})

const projectOptions = ref([])
async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 所属应用列：scene_project → 应用名映射 */
const projectNameMap = computed(() => Object.fromEntries(projectOptions.value.map((p) => [p.value, p.label])))

// ---------- 表格数据 ----------

const loading = ref(false)
const tableData = ref([])
/** 跨页复选保留的勾选主键（同压测接口页逻辑） */
const checkedRowKeys = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  itemCount: 0,
  prefix({ itemCount }) { return `共 ${itemCount} 条` },
  onChange: (page) => { pagination.page = page },
  onUpdatePageSize: (pageSize) => { pagination.pageSize = pageSize; pagination.page = 1; handleQuery() },
})

function buildQueryBody() {
  const body = { state: 0, page: pagination.page, page_size: pagination.pageSize }
  Object.entries(queryItems.value).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return body
}

async function handleQuery() {
  try {
    loading.value = true
    const res = await api.searchPerfSceneList(buildQueryBody())
    tableData.value = res.data || []
    pagination.itemCount = res.total || 0
  } catch (e) {
    tableData.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { pagination.page = 1; handleQuery() }
function handleReset() {
  queryItems.value = { scene_name: null, scene_project: null, run_mode: null }
  pagination.page = 1
  handleQuery()
}
function onPageChange(page) { pagination.page = page; handleQuery() }

function renderRowNo(index) {
  return (pagination.page - 1) * pagination.pageSize + index + 1
}

// ---------- 场景列表列 ----------

// 列宽与样式对齐压测接口页（复选框/序号/名称/描述/所属应用/审计四列）
const columns = [
  { type: 'selection', fixed: 'left', width: 48 },
  { title: '序号', key: 'row_no', width: 50, align: 'center', fixed: 'left', render: (_row, index) => renderRowNo(index) },
  {
    title: '场景名称', key: 'scene_name', width: 300, align: 'center', ellipsis: { tooltip: true },
    render: (row) => {
      const name = row.scene_name || ''
      return h('a', {
        href: 'javascript:void(0)', title: name,
        style: { display: 'inline-block', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#2080f0', textDecoration: 'underline', cursor: 'pointer' },
        onClick: (e) => { e.preventDefault(); goEdit(row) },
      }, name)
    },
  },
  { title: '场景描述', key: 'scene_desc', width: 300, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '所属应用', key: 'scene_project', width: 150, align: 'center', ellipsis: { tooltip: true },
    render: (row) => h('span', projectNameMap.value[row.scene_project] || '-'),
  },
  {
    title: '施压模式', key: 'run_mode', width: 100, align: 'center',
    render: (row) => h(NTag, { size: 'small', type: RUN_MODE_TAG_TYPES[row.run_mode] || 'default', round: true },
        { default: () => RUN_MODE_LABELS[row.run_mode] || row.run_mode }),
  },
  { title: '接口数量', key: 'item_count', width: 90, align: 'center' },
  {
    title: '熔断阈值(%)', key: 'error_rate_threshold', width: 100, align: 'center',
    render: (row) => (row.error_rate_threshold === null || row.error_rate_threshold === undefined ? '未启用' : row.error_rate_threshold),
  },
  {
    title: '断言口径', key: 'assert_mode', width: 90, align: 'center',
    render: (row) => ASSERT_MODE_LABELS[row.assert_mode] || row.assert_mode,
  },
  { title: '创建人员', key: 'created_user', width: 150, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '创建时间', key: 'created_time', width: 180, align: 'center',
    render: (row) => h('span', row.created_time ? formatDateTime(row.created_time) : '-'),
  },
  { title: '更新人员', key: 'updated_user', width: 150, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '更新时间', key: 'updated_time', width: 180, align: 'center',
    render: (row) => h('span', row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作', key: 'actions', width: 130, align: 'center', fixed: 'right',
    render(row) {
      const dropdownOptions = [
        { label: '预检', key: 'precheck', icon: renderIcon('material-symbols:fact-check-outline', { size: 16 }), onClick: () => precheckRef.value?.open({ scene_id: row.scene_id, scene_name: row.scene_name, scene_project: row.scene_project }) },
        { label: '跑全部', key: 'run_all', icon: renderIcon('material-symbols:rocket-launch-outline', { size: 16 }), onClick: () => handleRunAll(row) },
        { label: '复制', key: 'copy', icon: renderIcon('material-symbols:content-copy-outline', { size: 16 }), onClick: () => handleCopy(row) },
      ]
      return [
        h(NButton,
            { size: 'tiny', quaternary: true, type: 'primary', onClick: () => goEdit(row) },
            { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
        ),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
          trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' },
              { default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }),
          default: () => h('div', {}, '确定删除该压测场景?'),
        }),
        h(NDropdown,
            { trigger: 'click', options: dropdownOptions.map((opt) => ({ label: opt.label, key: opt.key, icon: opt.icon })), onSelect: (key) => dropdownOptions.find((o) => o.key === key)?.onClick?.() },
            { default: () => h(NButton, { size: 'tiny', quaternary: true, type: 'default' },
                { default: () => '更多', icon: renderIcon('material-symbols:more-horiz', { size: 16 }) }) }
        ),
      ]
    },
  },
]

// ---------- 跳转 ----------

const precheckRef = ref(null)

function handleCreate() {
  router.push('/performance/scene/edit')
}

function goEdit(row) {
  router.push({ path: '/performance/scene/edit', query: { scene_id: row.scene_id } })
}

// ---------- 场景操作 ----------

async function handleCopy(row) {
  try {
    await api.copyPerfScene({ scene_id: row.scene_id })
    window.$message?.success('复制成功')
    handleQuery()
  } catch (e) { /* 拦截器已提示 */ }
}

async function handleDelete(row) {
  try {
    await api.deletePerfScene({ scene_id: row.scene_id })
    window.$message?.success('删除成功')
    handleQuery()
  } catch (e) { /* 拦截器已提示 */ }
}

/** 批量删除勾选项（跨页复选保留，口径对齐压测接口页） */
async function handleBatchDelete() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的压测场景')
    return
  }
  await window.$dialog?.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条压测场景吗？`,
    async confirm() {
      await Promise.all(ids.map((scene_id) => api.deletePerfScene({ scene_id })))
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      handleQuery()
    },
  })
}

// ---------- 一键跑全部 ----------

async function handleRunAll(row) {
  try {
    const res = await api.runAllPerfScenePresets({ scene_id: row.scene_id })
    const data = res.data || {}
    window.$message?.success(res.message || `已下发 ${data.dispatched || 0}/${data.total || 0} 份负载预设`)
  } catch (e) { /* 拦截器已提示 */ }
}

onMounted(() => {
  loadProjects()
  handleQuery()
})
</script>
