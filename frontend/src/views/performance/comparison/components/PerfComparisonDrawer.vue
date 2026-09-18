<!--
  PerfComparisonDrawer — 多记录对比/汇总详情抽屉

  展示创建时固化的结论快照：引用报告清单（含事后被删标注）、compare 指标矩阵与
  配置差异摘要、merge 汇总指标与接口维度聚合；快照不可变，页面不提供编辑入口。
-->
<template>
  <n-drawer v-model:show="show" :width="980" placement="right">
    <n-drawer-content :title="`对比结论 · ${detail?.comparison_name || comparisonCode || ''}`" closable>
      <n-spin :show="loading">
        <n-space vertical :size="14">
          <n-alert v-if="missingCodes.length" type="warning" :show-icon="true">
            以下引用报告已被删除（结论快照仍保留创建时数据）：{{ missingCodes.join('、') }}
          </n-alert>

          <n-card title="概要" size="small">
            <n-descriptions :column="3" label-placement="left" size="small" bordered>
              <n-descriptions-item label="模式">{{ MODE_LABELS[detail?.comparison_mode] || detail?.comparison_mode || '-' }}</n-descriptions-item>
              <n-descriptions-item label="报告数">{{ detail?.report_count ?? '-' }}</n-descriptions-item>
              <n-descriptions-item label="创建人">{{ detail?.created_user || '-' }}</n-descriptions-item>
              <n-descriptions-item label="创建时间">{{ formatDateTime(detail?.created_time) }}</n-descriptions-item>
              <n-descriptions-item label="结论编码" :span="2">
                <n-text copyable>{{ detail?.comparison_code || '-' }}</n-text>
              </n-descriptions-item>
              <n-descriptions-item v-if="detail?.comparison_desc" label="备注" :span="3">
                {{ detail.comparison_desc }}
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <n-card title="引用报告" size="small">
            <n-data-table
                :columns="refColumns"
                :data="refs"
                :pagination="false"
                :row-key="(row) => row.report_code"
                size="small"
                :max-height="220"
            />
          </n-card>

          <template v-if="snapshot?.compare">
            <n-card title="横向对比（相对基准）" size="small">
              <n-data-table
                  :columns="compareColumns"
                  :data="snapshot.compare.metric_rows"
                  :pagination="false"
                  :row-key="(row) => row.report_code"
                  size="small"
                  :scroll-x="1180"
                  :max-height="360"
              />
              <n-text v-if="snapshot.compare.baseline_code" depth="3" style="font-size: 12px">
                基准：{{ snapshot.compare.baseline_code }}；变化列为相对基准的百分比（错误率另附百分点差、总请求为计数差）
              </n-text>
            </n-card>
            <n-card v-if="(snapshot.compare.per_report_diffs || []).length" title="配置差异摘要" size="small">
              <n-data-table
                  :columns="diffColumns"
                  :data="snapshot.compare.per_report_diffs"
                  :pagination="false"
                  :row-key="(row) => row.report_code"
                  size="small"
                  :max-height="260"
              />
            </n-card>
          </template>

          <template v-if="snapshot?.merge">
            <n-card title="汇总合并（并行实例聚合）" size="small">
              <n-alert v-for="warning in snapshot.merge.warnings" :key="warning" type="warning" :show-icon="true" style="margin-bottom: 8px">
                {{ warning }}
              </n-alert>
              <n-descriptions :column="4" label-placement="left" size="small" bordered>
                <n-descriptions-item label="场景">{{ snapshot.merge.scene_name || '-' }}</n-descriptions-item>
                <n-descriptions-item label="总请求">{{ fmt(snapshot.merge.total_requests, 0) }}</n-descriptions-item>
                <n-descriptions-item label="失败请求">{{ fmt(snapshot.merge.fail_requests, 0) }}</n-descriptions-item>
                <n-descriptions-item label="失败率(%)">{{ fmt(snapshot.merge.error_rate) }}</n-descriptions-item>
                <n-descriptions-item label="RPS">{{ fmt(snapshot.merge.rps) }}</n-descriptions-item>
                <n-descriptions-item label="业务吞吐RPS">{{ fmt(snapshot.merge.success_rps) }}</n-descriptions-item>
                <n-descriptions-item label="发送(KB/s)">{{ fmt(snapshot.merge.sent_kb_s) }}</n-descriptions-item>
                <n-descriptions-item label="接收(KB/s)">{{ fmt(snapshot.merge.received_kb_s) }}</n-descriptions-item>
                <n-descriptions-item label="平均RT(ms)">{{ fmt(snapshot.merge.avg_rt) }}</n-descriptions-item>
                <n-descriptions-item label="P50(ms)">{{ fmt(snapshot.merge.p50) }}</n-descriptions-item>
                <n-descriptions-item label="P90(ms)">{{ fmt(snapshot.merge.p90) }}</n-descriptions-item>
                <n-descriptions-item label="P95(ms)">{{ fmt(snapshot.merge.p95) }}</n-descriptions-item>
                <n-descriptions-item label="P99(ms)">{{ fmt(snapshot.merge.p99) }}</n-descriptions-item>
                <n-descriptions-item label="最小RT(ms)">{{ fmt(snapshot.merge.min_rt) }}</n-descriptions-item>
                <n-descriptions-item label="最大RT(ms)">{{ fmt(snapshot.merge.max_rt) }}</n-descriptions-item>
                <n-descriptions-item label="有效时长(s)">{{ fmt(snapshot.merge.duration_seconds, 0) }}</n-descriptions-item>
              </n-descriptions>

              <n-text depth="2" style="font-size: 13px; display: block; margin: 10px 0 6px">接口维度聚合</n-text>
              <n-data-table
                  :columns="apiColumns"
                  :data="snapshot.merge.api_merged"
                  :pagination="false"
                  :row-key="(row) => row.api_code"
                  size="small"
                  :scroll-x="980"
                  :max-height="280"
              />
            </n-card>
          </template>
        </n-space>
      </n-spin>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import {
  NAlert,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NDrawer,
  NDrawerContent,
  NSpace,
  NSpin,
  NTag,
  NText,
} from 'naive-ui'

import { formatDateTime } from '@/utils'
import api from '@/api'

defineOptions({ name: 'PerfComparisonDrawer' })

const MODE_LABELS = { compare: '横向对比', merge: '汇总合并', hybrid: '对比+汇总' }
/** 横向对比矩阵的指标列（相对变化与主值同格双行展示） */
const METRIC_COLUMNS = [
  { key: 'total_requests', title: '总请求', delta: 'total_requests_delta' },
  { key: 'error_rate', title: '失败率(%)', delta: 'error_rate_pp', pp: true },
  { key: 'rps', title: 'RPS', delta: 'rps' },
  { key: 'success_rps', title: '业务吞吐RPS', delta: 'success_rps' },
  { key: 'avg_rt', title: '平均RT(ms)', delta: 'avg_rt' },
  { key: 'p95', title: 'P95(ms)', delta: 'p95' },
  { key: 'p99', title: 'P99(ms)', delta: 'p99' },
]

const show = ref(false)
const loading = ref(false)
const comparisonCode = ref(null)
const detail = ref(null)
const missingCodes = ref([])

const snapshot = computed(() => detail.value?.result_snapshot || null)
const refs = computed(() => detail.value?.report_refs || [])

function fmt(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

const refColumns = [
  { title: '报告编码', key: 'report_code', width: 180, ellipsis: { tooltip: true } },
  { title: '场景', key: 'scene_name', width: 140, ellipsis: { tooltip: true }, render: (row) => row.scene_name || '-' },
  { title: '并发', key: 'concurrent_users', width: 70, render: (row) => row.concurrent_users ?? '-' },
  { title: '开始时间', key: 'started_time', width: 160, render: (row) => (row.started_time ? formatDateTime(row.started_time) : '-') },
  {
    title: '角色',
    key: 'is_baseline',
    width: 80,
    render: (row) => h(NTag, { size: 'small', type: row.is_baseline ? 'warning' : 'default' },
        { default: () => (row.is_baseline ? '基准' : '参与') }),
  },
]

/** 指标矩阵：主值 + 相对基准变化双行（pp=百分点差、delta=计数差，其余为百分比变化） */
function renderMetricCell(row, column) {
  const main = fmt(row[column.key])
  if (row.is_baseline || !row.relative) return main
  const deltaValue = row.relative[column.delta]
  if (deltaValue === null || deltaValue === undefined) return main
  const unit = column.pp ? 'pp' : '%'
  const deltaText = `${deltaValue >= 0 ? '+' : ''}${Number(deltaValue).toFixed(2)}${unit}`
  return h('div', null, [
    h('div', null, main),
    h('div', { style: 'font-size: 12px; color: var(--n-text-color-disabled, #999)' }, deltaText),
  ])
}

const compareColumns = [
  {
    title: '报告编码',
    key: 'report_code',
    width: 180,
    fixed: 'left',
    ellipsis: { tooltip: true },
    render: (row) => h('span', null, [
      h('span', null, row.report_code),
      row.is_baseline ? h(NTag, { size: 'tiny', type: 'warning', style: 'margin-left: 6px' }, { default: () => '基准' }) : null,
    ]),
  },
  { title: '场景', key: 'scene_name', width: 130, ellipsis: { tooltip: true }, render: (row) => row.scene_name || '-' },
  { title: '并发', key: 'concurrent_users', width: 65, render: (row) => row.concurrent_users ?? '-' },
  ...METRIC_COLUMNS.map((column) => ({
    title: column.title,
    key: column.key,
    width: 110,
    render: (row) => renderMetricCell(row, column),
  })),
]

const diffColumns = [
  { title: '报告编码', key: 'report_code', width: 180, ellipsis: { tooltip: true } },
  {
    title: '配置指纹',
    key: 'fingerprint_same',
    width: 100,
    render: (row) => h(NTag, { size: 'small', type: row.fingerprint_same ? 'success' : 'warning' },
        { default: () => (row.fingerprint_same ? '一致' : '不一致') }),
  },
  {
    title: '差异摘要',
    key: 'summary',
    render: (row) => (row.summary || []).length
        ? h('span', null, row.summary.join('；'))
        : '配置无差异',
  },
]

const apiColumns = [
  { title: '接口', key: 'api_code', width: 130, ellipsis: { tooltip: true } },
  { title: '名称', key: 'api_name', width: 130, ellipsis: { tooltip: true }, render: (row) => row.api_name || '-' },
  { title: '方法', key: 'method', width: 80, render: (row) => row.method || '-' },
  { title: '总请求', key: 'total_requests', width: 90, render: (row) => fmt(row.total_requests, 0) },
  { title: '失败', key: 'failed_requests', width: 80, render: (row) => fmt(row.failed_requests, 0) },
  { title: '失败率(%)', key: 'error_rate', width: 90, render: (row) => fmt(row.error_rate) },
  { title: 'RPS', key: 'rps', width: 90, render: (row) => fmt(row.rps) },
  { title: '平均RT(ms)', key: 'avg_rt', width: 100, render: (row) => fmt(row.avg_rt) },
  { title: 'P95(ms)', key: 'p95', width: 90, render: (row) => fmt(row.p95) },
  { title: 'P99(ms)', key: 'p99', width: 90, render: (row) => fmt(row.p99) },
  {
    title: '置信',
    key: 'low_confidence',
    width: 80,
    render: (row) => h(NTag, { size: 'small', type: row.low_confidence ? 'warning' : 'success' },
        { default: () => (row.low_confidence ? '低' : '正常') }),
  },
]

/** 打开抽屉：拉取对比记录详情（含结果快照与引用报告现存性复核） */
async function open(code) {
  comparisonCode.value = code
  detail.value = null
  missingCodes.value = []
  show.value = true
  loading.value = true
  try {
    const res = await api.getPerfComparison({ comparison_code: code })
    const payload = res?.data || {}
    detail.value = payload.detail || null
    missingCodes.value = payload.missing_report_codes || []
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
