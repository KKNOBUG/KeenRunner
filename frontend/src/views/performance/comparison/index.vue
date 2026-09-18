<!--
  多记录对比/汇总列表页 — 结论快照实体（创建时一次性计算，无编辑语义）

  列表不含 result_snapshot/report_refs 大字段；详情经 PerfComparisonDrawer 全量拉取，
  含引用报告现存性复核、compare 指标矩阵与配置差异、merge 汇总与接口聚合。
-->
<template>
  <CommonPage show-footer title="多记录对比">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="fetchComparisonList"
        :query-bar-props="queryBarProps"
        :scroll-x="1180"
        row-key="comparison_id"
        @pagination-meta="onPaginationMeta"
        @query-bar-create="() => createModalRef?.open()"
    >
      <template #queryBar>
        <QueryBarItem label="对比名称" :label-width="70">
          <NInput v-model:value="queryItems.comparison_name" type="text" placeholder="对比名称(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="模式" :label-width="70">
          <NSelect
              v-model:value="queryItems.comparison_mode"
              :options="modeOptions"
              placeholder="请选择"
              clearable
              style="width: 150px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <PerfComparisonCreateModal ref="createModalRef" @saved="() => $table?.handleQuery()" />
    <PerfComparisonDrawer ref="drawerRef" />
  </CommonPage>
</template>

<script setup>
import { h, ref } from 'vue'
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfComparisonCreateModal from './components/PerfComparisonCreateModal.vue'
import PerfComparisonDrawer from './components/PerfComparisonDrawer.vue'

import { formatDateTime } from '@/utils'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '多记录对比' })

const MODE_LABELS = { compare: '横向对比', merge: '汇总合并', hybrid: '对比+汇总' }
const MODE_TAG_TYPES = { compare: 'info', merge: 'success', hybrid: 'warning' }

const modeOptions = [
  { label: '横向对比', value: 'compare' },
  { label: '汇总合并', value: 'merge' },
  { label: '对比+汇总', value: 'hybrid' },
]

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const createModalRef = ref(null)
const drawerRef = ref(null)

const queryItems = ref({
  comparison_name: null,
  comparison_mode: null,
})

/** 规范为 PerfComparisonSelect 请求体（空值剔除） */
function fetchComparisonList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.searchPerfComparisonList(body)
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
  { title: '结论编码', key: 'comparison_code', width: 180, ellipsis: { tooltip: true } },
  { title: '名称', key: 'comparison_name', width: 180, ellipsis: { tooltip: true } },
  {
    title: '模式',
    key: 'comparison_mode',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: MODE_TAG_TYPES[row.comparison_mode] || 'default' },
        { default: () => MODE_LABELS[row.comparison_mode] || row.comparison_mode }),
  },
  { title: '报告数', key: 'report_count', width: 80 },
  { title: '备注', key: 'comparison_desc', minWidth: 160, ellipsis: { tooltip: true }, render: (row) => row.comparison_desc || '-' },
  { title: '创建人', key: 'created_user', width: 100, render: (row) => row.created_user || '-' },
  {
    title: '创建时间',
    key: 'created_time',
    width: 160,
    render: (row) => (row.created_time ? formatDateTime(row.created_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => drawerRef.value?.open(row.comparison_code) },
              { default: () => '详情' }),
          // 结论快照不可修改，删除仅释放列表；同口径对比可随时重新创建
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'error', secondary: true },
                { default: () => '删除' }),
            default: () => `确认删除对比结论「${row.comparison_name}」？`,
          }),
        ],
      })
    },
  },
]

async function handleDelete(row) {
  try {
    await api.deletePerfComparison({ comparison_code: row.comparison_code })
    window.$message?.success('删除成功')
    $table.value?.handleQuery()
  } catch (e) {
    /* 拦截器已提示 */
  }
}
</script>
