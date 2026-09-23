<!--
  压测报告列表页 — 一次施压的不可变结论（只读快照，不回查场景与接口）

  列表不含 locust_stats/config_snapshot 大字段；详情跳转独立标签页
  /performance/report/detail（query 传 report_code）全量展示，
  含全局指标、SLA 判定、接口/事务维度聚合、准备与抽查、错误归因与指标曲线。
-->
<template>
  <CommonPage show-footer title="压测报告">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :get-data="fetchReportList"
        :query-bar-props="queryBarProps"
        :scroll-x="1700"
        row-key="report_id"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="报告编码" :label-width="70">
          <NInput v-model:value="queryItems.report_code" type="text" placeholder="报告编码(模糊)" clearable />
        </QueryBarItem>
        <QueryBarItem label="场景编码" :label-width="70">
          <NInput v-model:value="queryItems.scene_code" type="text" placeholder="场景编码(精确，梯度对比)" clearable />
        </QueryBarItem>
        <QueryBarItem label="执行状态" :label-width="70">
          <NSelect
              v-model:value="queryItems.status"
              :options="statusOptions"
              placeholder="请选择"
              clearable
              style="width: 140px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <PerfReportCompareModal ref="compareModalRef" />
  </CommonPage>
</template>

<script setup>
import { h, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NDropdown, NInput, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfReportCompareModal from '../components/PerfReportCompareModal.vue'

import { formatDateTime, renderIcon } from '@/utils'
import { downloadBlobResponse } from '@/utils/common/downloadFile'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测报告' })

const STATUS_LABELS = { running: '执行中', completed: '已完成', failed: '失败', stopped: '已停止' }
const STATUS_TAG_TYPES = { running: 'info', completed: 'success', failed: 'error', stopped: 'warning' }
const RUN_MODE_LABELS = { single: '单接口', mixed: '混合流量', journey: '业务链路' }

const statusOptions = [
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已停止', value: 'stopped' },
]

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'split',
}

const $table = ref(null)
const compareModalRef = ref(null)
const router = useRouter()
/** 跨页复选保留的勾选主键（同压测接口页逻辑） */
const checkedRowKeys = ref([])

/** 详情跳转独立标签页（query 传 report_code），对齐压测接口编辑子页的跳转约定 */
function goDetail(row) {
  router.push({ path: '/performance/report/detail', query: { report_code: row.report_code } })
}

const queryItems = ref({
  report_code: null,
  scene_code: null,
  status: null,
})

/** 规范为 PerfReportSelect 请求体（空值剔除） */
function fetchReportList(params = {}) {
  const body = { state: 0 }
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.getPerfReportList(body)
}

const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

function renderRowNo(index) {
  return (listPaginationMeta.value.page - 1) * listPaginationMeta.value.page_size + index + 1
}

function fmtNum(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

const columns = [
  { type: 'selection', fixed: 'left', width: 48 },
  { title: '序号', key: 'row_no', width: 50, align: 'center', fixed: 'left', render: (_row, index) => renderRowNo(index) },
  { title: '报告编码', key: 'report_code', width: 170, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '压测场景', key: 'scene_name', width: 150, align: 'center', ellipsis: { tooltip: true },
    render: (row) => row.scene_name || '-',
  },
  {
    title: '施压模式',
    key: 'run_mode',
    width: 100,
    align: 'center',
    render: (row) => h(NTag, { size: 'small', type: row.run_mode === 'mixed' ? 'warning' : 'info', round: true },
        { default: () => RUN_MODE_LABELS[row.run_mode] || row.run_mode || '-' }),
  },
  { title: '并发', key: 'concurrent_users', width: 70, align: 'center' },
  {
    title: '状态',
    key: 'status',
    width: 85,
    align: 'center',
    render: (row) => h(NTag, { size: 'small', type: STATUS_TAG_TYPES[row.status] || 'default', round: true },
        { default: () => STATUS_LABELS[row.status] || row.status }),
  },
  { title: '总请求', key: 'total_requests', width: 90, align: 'center' },
  { title: 'RPS', key: 'rps', width: 80, align: 'center', render: (row) => fmtNum(row.rps) },
  {
    title: '失败率',
    key: 'error_rate',
    width: 80,
    align: 'center',
    render: (row) => `${fmtNum(row.error_rate)}%`,
  },
  { title: '平均RT(ms)', key: 'avg_rt', width: 100, align: 'center', render: (row) => fmtNum(row.avg_rt) },
  {
    title: '开始时间',
    key: 'started_time',
    width: 180,
    align: 'center',
    render: (row) => h('span', row.started_time ? formatDateTime(row.started_time) : '-'),
  },
  { title: '创建人员', key: 'created_user', width: 150, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '创建时间', key: 'created_time', width: 180, align: 'center',
    render: (row) => h('span', row.created_time ? formatDateTime(row.created_time) : '-'),
  },
  {
    // 操作列对齐压测接口页：详情/导出平铺 + 「更多」下拉（对比、设为基线）
    title: '操作',
    key: 'actions',
    width: 130,
    align: 'center',
    fixed: 'right',
    render(row) {
      const dropdownOptions = [
        { label: '对比', key: 'compare', icon: renderIcon('material-symbols:compare-arrows', { size: 16 }), disabled: !row.scene_code, onClick: () => compareModalRef.value?.open(row) },
        { label: '设为基线', key: 'pin_baseline', icon: renderIcon('material-symbols:bookmark-outline', { size: 16 }), disabled: row.status !== 'completed' || !row.scene_code, onClick: () => handlePinBaselineConfirm(row) },
      ]
      return [
        h(NButton,
            { size: 'tiny', quaternary: true, type: 'primary', onClick: () => goDetail(row) },
            { default: () => '详情', icon: renderIcon('material-symbols:visibility-outline', { size: 16 }) }
        ),
        h(NButton,
            { size: 'tiny', quaternary: true, type: 'info', loading: exportingCode.value === row.report_code, onClick: () => handleExportReport(row) },
            { default: () => '导出', icon: renderIcon('material-symbols:download-2-rounded', { size: 16 }) }
        ),
        h(NDropdown,
            {
              trigger: 'click',
              options: dropdownOptions.map((opt) => ({ label: opt.label, key: opt.key, icon: opt.icon, disabled: opt.disabled })),
              onSelect: (key) => dropdownOptions.find((o) => o.key === key)?.onClick?.(),
            },
            {
              default: () => h(NButton, { size: 'tiny', quaternary: true, type: 'default' },
                  { default: () => '更多', icon: renderIcon('material-symbols:more-horiz', { size: 16 }) }),
            }
        ),
      ]
    },
  },
]

/** 设为基线: 钉选到报告所属场景, 后续执行报告将自动固化该基线做退化对比 */
function handlePinBaselineConfirm(row) {
  window.$dialog?.confirm({
    title: '提示',
    type: 'warning',
    content: `确认将报告 ${row.report_code} 钉为场景[${row.scene_name || row.scene_code}]的退化对比基线？`,
    async confirm() {
      await handlePinBaseline(row)
    },
  })
}

async function handlePinBaseline(row) {
  try {
    await api.pinPerfSceneBaseline({ scene_code: row.scene_code, report_code: row.report_code })
    window.$message?.success(`已将报告钉为场景[${row.scene_name || row.scene_code}]的基线`)
  } catch (e) {
    /* 拦截器已提示 */
  }
}

/** 行内导出防重复点击: 记录正在导出的报告编码 */
const exportingCode = ref(null)

/** 导出报告 xlsx 报表（概要/SLA/接口/事务/错误/基线多 sheet） */
async function handleExportReport(row) {
  exportingCode.value = row.report_code
  try {
    const res = await api.exportPerfReport({ report_code: row.report_code })
    await downloadBlobResponse(res, `压测报告_${row.report_code}.xlsx`)
  } catch (e) {
    window.$message?.error?.(e?.message || '报告导出失败')
  } finally {
    exportingCode.value = null
  }
}
</script>