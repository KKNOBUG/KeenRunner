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
        :columns="columns"
        :get-data="fetchReportList"
        :query-bar-props="queryBarProps"
        :scroll-x="1320"
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
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import PerfReportCompareModal from '../components/PerfReportCompareModal.vue'

import { formatDateTime } from '@/utils'
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
  { title: '序号', key: 'row_no', width: 60, render: (_row, index) => renderRowNo(index) },
  { title: '报告编码', key: 'report_code', width: 170, ellipsis: { tooltip: true } },
  { title: '压测场景', key: 'scene_name', width: 150, ellipsis: { tooltip: true } },
  {
    title: '施压模式',
    key: 'run_mode',
    width: 90,
    render: (row) => h(NTag, { size: 'small', type: row.run_mode === 'mixed' ? 'warning' : 'info' },
        { default: () => RUN_MODE_LABELS[row.run_mode] || row.run_mode || '-' }),
  },
  { title: '并发', key: 'concurrent_users', width: 70 },
  {
    title: '状态',
    key: 'status',
    width: 85,
    render: (row) => h(NTag, { size: 'small', type: STATUS_TAG_TYPES[row.status] || 'default' },
        { default: () => STATUS_LABELS[row.status] || row.status }),
  },
  { title: '总请求', key: 'total_requests', width: 90 },
  { title: 'RPS', key: 'rps', width: 80, render: (row) => fmtNum(row.rps) },
  {
    title: '失败率',
    key: 'error_rate',
    width: 80,
    render: (row) => `${fmtNum(row.error_rate)}%`,
  },
  { title: '平均RT(ms)', key: 'avg_rt', width: 100, render: (row) => fmtNum(row.avg_rt) },
  {
    title: '开始时间',
    key: 'started_time',
    width: 160,
    render: (row) => (row.started_time ? formatDateTime(row.started_time) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, wrap: false }, {
        default: () => [
          h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => goDetail(row) },
              { default: () => '详情' }),
          h(NButton, { size: 'tiny', type: 'info', secondary: true, disabled: !row.scene_code, onClick: () => compareModalRef.value?.open(row) },
              { default: () => '对比' }),
          h(NButton, { size: 'tiny', type: 'success', secondary: true, loading: exportingCode.value === row.report_code, onClick: () => handleExportReport(row) },
              { default: () => '导出' }),
          // 基线钉在场景上: 仅同场景已完成报告可钉(后端同口径校验), 失败/运行中报告无稳定结论可比
          h(NPopconfirm, { onPositiveClick: () => handlePinBaseline(row) }, {
            trigger: () => h(NButton, { size: 'tiny', type: 'warning', secondary: true, disabled: row.status !== 'completed' || !row.scene_code },
                { default: () => '设为基线' }),
            default: () => `确认将报告 ${row.report_code} 钉为场景[${row.scene_name || row.scene_code}]的退化对比基线？`,
          }),
        ],
      })
    },
  },
]

/** 设为基线: 钉选到报告所属场景, 后续执行报告将自动固化该基线做退化对比 */
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