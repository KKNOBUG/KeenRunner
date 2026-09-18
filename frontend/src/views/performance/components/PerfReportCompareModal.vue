<!--
  PerfReportCompareModal — 报告对比弹窗

  任选两份报告出对比结论（不限同场景，差异由明细自说明）：双侧核心指标对照 + 配置差异
  可读摘要 + 结构化差异明细；基线候选默认列出同场景已完成报告，支撑「同场景梯度并发对比」。
-->
<template>
  <n-modal v-model:show="show" preset="card" title="报告对比" style="width: 1080px">
    <n-space vertical :size="12">
      <n-space :size="8" :wrap-item="false">
        <n-select
            v-model:value="baselineCode"
            :options="baselineOptions"
            :loading="optionsLoading"
            placeholder="选择基线报告(默认同场景已完成报告)"
            clearable
            filterable
            style="width: 420px"
        />
        <n-button type="primary" secondary :disabled="!baselineCode" :loading="comparing" @click="handleCompare">
          开始对比
        </n-button>
        <n-text depth="3" style="font-size: 12px; line-height: 28px">
          当前：{{ currentRow?.report_code || '-' }}（{{ currentRow?.scene_name || '-' }}）
        </n-text>
      </n-space>

      <template v-if="result">
        <n-alert v-if="!result.diff.same_scene" type="warning" :show-icon="true">
          两份报告不属于同一压测场景（{{ result.current.scene_name }} vs {{ result.baseline.scene_name }}），指标差异包含场景口径因素。
        </n-alert>
        <n-alert v-else-if="!result.diff.fingerprint_same" type="info" :show-icon="true">
          两份报告负载/编排口径不一致（指纹不同），指标差异可能来自配置变更而非性能退化，请结合下方差异明细解读。
        </n-alert>

        <n-data-table
            :columns="metricColumns"
            :data="metricRows"
            :pagination="false"
            :row-key="(row) => row.label"
            size="small"
            :max-height="300"
            :scroll-x="560"
        />

        <n-alert v-if="!detailRows.length" type="success" :show-icon="true">配置完全一致，指标差异可归因于运行波动。</n-alert>
        <template v-else>
          <n-text depth="2" style="font-size: 13px">配置差异明细</n-text>
          <n-data-table
              :columns="detailColumns"
              :data="detailRows"
              :pagination="false"
              :row-key="(row) => `${row.category}-${row.target}-${row.current}`"
              size="small"
              :max-height="240"
              :scroll-x="620"
          />
        </template>
      </template>
    </n-space>
    <template #footer>
      <n-space justify="end">
        <n-button @click="show = false">关 闭</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { NAlert, NButton, NDataTable, NModal, NSelect, NSpace, NText } from 'naive-ui'

import { formatDateTime } from '@/utils'
import api from '@/api'

defineOptions({ name: 'PerfReportCompareModal' })

const show = defineModel('show', { type: Boolean, default: false })

// ---------- 对比双方与结果状态 ----------
const currentRow = ref(null)
const baselineCode = ref(null)
const baselineOptions = ref([])
const optionsLoading = ref(false)
const comparing = ref(false)
const result = ref(null)

/** 双侧指标对照行(只取对比结论需要的核心口径, 数值统一两位小数) */
const METRIC_ROWS = [
  { key: 'concurrent_users', label: '并发用户' },
  { key: 'target_rps', label: '目标RPS' },
  { key: 'run_duration', label: '计划时长(s)' },
  { key: 'duration_seconds', label: '有效时长(s)' },
  { key: 'total_requests', label: '总请求' },
  { key: 'error_rate', label: '失败率(%)' },
  { key: 'rps', label: 'RPS(含失败)' },
  { key: 'success_rps', label: '业务吞吐RPS' },
  { key: 'avg_rt', label: '平均RT(ms)' },
  { key: 'p95', label: 'P95(ms)' },
  { key: 'p99', label: 'P99(ms)' },
]

function fmtMetric(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(2)
}

const metricColumns = [
  { title: '指标', key: 'label', width: 140 },
  { title: '当前报告', key: 'current', width: 160, render: (row) => fmtMetric(row.current) },
  { title: '基线报告', key: 'baseline', width: 160, render: (row) => fmtMetric(row.baseline) },
  {
    title: '差异',
    key: 'delta',
    minWidth: 120,
    render: (row) => {
      const base = Number(row.baseline)
      if (!row.baseline || Number.isNaN(base) || base === 0) return '-'
      const pct = ((row.current - base) / base) * 100
      return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
    },
  },
]

const metricRows = computed(() => {
  if (!result.value) return []
  return METRIC_ROWS.map(({ key, label }) => ({
    label,
    current: result.value.current[key],
    baseline: result.value.baseline[key],
  }))
})

const detailColumns = [
  { title: '类别', key: 'category', width: 150, ellipsis: { tooltip: true } },
  { title: '对象', key: 'target', width: 140, ellipsis: { tooltip: true } },
  { title: '基线', key: 'baseline', minWidth: 120, ellipsis: { tooltip: true } },
  { title: '当前', key: 'current', minWidth: 120, ellipsis: { tooltip: true } },
]

/** 结构化差异 -> 明细表行(全局标量字段 + 接口项增删改逐字段展开) */
const detailRows = computed(() => {
  const diff = result.value?.diff
  if (!diff) return []
  const rows = []
  for (const f of diff.field_diffs || []) {
    rows.push({ category: '全局配置', target: f.label, baseline: String(f.baseline ?? '—'), current: String(f.current ?? '—') })
  }
  for (const item of diff.item_diffs || []) {
    const name = item.api_name || item.api_code
    if (item.kind === 'added') {
      rows.push({ category: '接口项', target: name, baseline: '不存在', current: '新增' })
    } else if (item.kind === 'removed') {
      rows.push({ category: '接口项', target: name, baseline: '存在', current: '已移除' })
    } else {
      for (const f of item.fields || []) {
        rows.push({ category: `接口项[${name}]`, target: f.label, baseline: String(f.baseline ?? '—'), current: String(f.current ?? '—') })
      }
    }
  }
  return rows
})

/** 基线候选: 默认同场景已完成报告(支撑同场景梯度并发对比), 排除当前报告自身 */
async function loadBaselineOptions(sceneCode) {
  baselineOptions.value = []
  if (!sceneCode) return
  optionsLoading.value = true
  try {
    const res = await api.getPerfReportList({ state: 0, scene_code: sceneCode, status: 'completed', page: 1, page_size: 100 })
    const rows = Array.isArray(res?.data) ? res.data : []
    baselineOptions.value = rows
        .filter((row) => row.report_code !== currentRow.value?.report_code)
        .map((row) => ({
          label: `${row.report_code}（并发${row.concurrent_users ?? '-'} · ${formatDateTime(row.created_time)}）`,
          value: row.report_code,
        }))
  } catch (e) {
    baselineOptions.value = []
  } finally {
    optionsLoading.value = false
  }
}

async function handleCompare() {
  comparing.value = true
  try {
    const res = await api.getPerfReportSnapshotDiff({
      report_code: currentRow.value.report_code,
      baseline_code: baselineCode.value,
    })
    result.value = res.data || null
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    comparing.value = false
  }
}

/**
 * 打开弹窗。
 * @param {Object} row 报告列表行({ report_code, scene_code, scene_name })
 */
function open(row = {}) {
  currentRow.value = row
  baselineCode.value = null
  result.value = null
  show.value = true
  loadBaselineOptions(row.scene_code)
}

defineExpose({ open })
</script>
