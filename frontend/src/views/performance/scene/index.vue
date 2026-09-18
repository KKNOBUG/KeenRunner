<!--
  压测场景列表页 — 编排层资产（打什么、怎么打 + 判定口径）

  场景以接口项（scene_items）引用压测接口资产，任务执行时按场景下发施压；
  新增/编辑共用 PerfSceneForm 四步抽屉，复制为编排全量平移（基线不继承），
  预检对启用接口逐个发真实请求回显连通性与业务结论（结论回写接口调试状态）。
-->
<template>
  <CommonPage show-footer title="压测场景">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchSceneList"
        :query-bar-props="queryBarProps"
        :scroll-x="1180"
        row-key="scene_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="() => formRef?.open(null)"
    >
      <template #queryBar>
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
      </template>
    </CrudTable>

    <PerfSceneForm ref="formRef" @saved="() => $table?.handleQuery()" />
    <PerfScenePrecheckModal ref="precheckRef" />
  </CommonPage>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfSceneForm from './components/PerfSceneForm.vue'
import PerfScenePrecheckModal from './components/PerfScenePrecheckModal.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测场景' })

const RUN_MODE_LABELS = { single: '单接口', mixed: '混合流量', journey: '业务链路' }
const RUN_MODE_TAG_TYPES = { single: 'info', mixed: 'warning', journey: 'error' }
const ASSERT_MODE_LABELS = { all: '逐请求', sample_ratio: '抽样' }

// M1 编辑器不提供 journey 编排，但存量数据与后端枚举仍可能为 journey，过滤项保留展示口径
const runModeFilterOptions = [
  { label: '单接口(single)', value: 'single' },
  { label: '混合流量(mixed)', value: 'mixed' },
]

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const formRef = ref(null)
const precheckRef = ref(null)

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

/** 规范为 PerfSceneSelect 请求体（空值剔除） */
function fetchSceneList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.searchPerfSceneList(body)
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
  { title: '场景名称', key: 'scene_name', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '施压模式',
    key: 'run_mode',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: RUN_MODE_TAG_TYPES[row.run_mode] || 'default' },
        { default: () => RUN_MODE_LABELS[row.run_mode] || row.run_mode }),
  },
  { title: '接口项数', key: 'item_count', width: 90 },
  {
    title: '熔断阈值(%)',
    key: 'error_rate_threshold',
    width: 100,
    render: (row) => (row.error_rate_threshold === null || row.error_rate_threshold === undefined ? '未启用' : row.error_rate_threshold),
  },
  {
    title: '断言口径',
    key: 'assert_mode',
    width: 90,
    render: (row) => ASSERT_MODE_LABELS[row.assert_mode] || row.assert_mode,
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 160,
    render: (row) => (row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => formRef.value?.open({ scene_id: row.scene_id }) },
              { default: () => '编辑' }),
          h(NButton, { size: 'tiny', type: 'info', secondary: true, onClick: () => precheckRef.value?.open({ scene_id: row.scene_id, scene_name: row.scene_name, scene_project: row.scene_project }) },
              { default: () => '预检' }),
          h(NPopconfirm, { onPositiveClick: () => handleCopy(row) }, {
            trigger: () => h(NButton, { size: 'tiny', secondary: true }, { default: () => '复制' }),
            default: () => '复制为同应用下的新场景？（编排全量平移，基线不继承）',
          }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true }, { default: () => '删除' }),
            default: () => '确认删除该压测场景？',
          }),
        ],
      })
    },
  },
]

async function handleCopy(row) {
  try {
    await api.copyPerfScene({ scene_id: row.scene_id })
    window.$message?.success('复制成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

async function handleDelete(row) {
  try {
    await api.deletePerfScene({ scene_id: row.scene_id })
    window.$message?.success('删除成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}

onMounted(() => {
  loadProjects()
})
</script>
