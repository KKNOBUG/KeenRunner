<template>
  <n-drawer v-model:show="show" :width="860" placement="right">
    <n-drawer-content :title="`压测报告 · ${report?.perf_name || reportCode || ''}`" closable>
      <n-spin :show="loading">
        <n-space vertical size="large">
          <n-descriptions v-if="report" :column="3" size="small" label-placement="left" bordered>
            <n-descriptions-item label="报告编码">{{ report.report_code }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="statusTagType" size="small">{{ report.status }}</n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="执行人">{{ report.created_user || '-' }}</n-descriptions-item>
            <n-descriptions-item label="开始时间">{{ report.started_time || '-' }}</n-descriptions-item>
            <n-descriptions-item label="结束时间">{{ report.finished_time || '-' }}</n-descriptions-item>
            <n-descriptions-item label="实际时长">{{ report.actual_duration ?? '-' }}s</n-descriptions-item>
          </n-descriptions>

          <!-- 聚合指标卡片 -->
          <n-grid v-if="report" :cols="4" :x-gap="10" :y-gap="10">
            <n-gi v-for="card in statCards" :key="card.label">
              <n-statistic :label="card.label" :value="card.value">
                <template #suffix>
                  <n-text depth="4" style="font-size: 12px">{{ card.suffix }}</n-text>
                </template>
              </n-statistic>
            </n-gi>
          </n-grid>

          <n-text v-if="metricsUnavailable" type="warning" depth="2">
            指标服务不可用：{{ metricsReason || '未配置 VictoriaMetrics' }}
          </n-text>
          <template v-if="hasSeries">
            <n-select
                v-if="statTargetOptions.length > 1"
                v-model:value="statTarget"
                :options="statTargetOptions"
                size="small"
                style="width: 320px"
            />
            <v-chart :option="chartOption" autoresize style="height: 340px" />
          </template>

          <!-- locust 统计明细 -->
          <template v-if="entries.length">
            <n-divider title-placement="left" style="margin: 8px 0">接口统计明细</n-divider>
            <n-data-table
                :columns="entryColumns"
                :data="entries"
                :pagination="{ pageSize: 10 }"
                size="small"
                :scroll-x="720"
            />
          </template>

          <template v-if="errors.length">
            <n-divider title-placement="left" style="margin: 8px 0">错误统计</n-divider>
            <n-list bordered>
              <n-list-item v-for="(err, i) in errors" :key="i">
                <n-thing :title="err.name" content-style="font-size: 12px; color: var(--n-text-color-disabled)">
                  {{ `出现 ${err.occurrences ?? '-'} 次 · ${err.method || ''} ${err.error_message || ''}` }}
                </n-thing>
              </n-list-item>
            </n-list>
          </template>
        </n-space>
      </n-spin>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  NDescriptions, NDescriptionsItem, NDivider, NDrawer, NDrawerContent, NGi, NGrid,
  NList, NListItem, NSelect, NStatistic, NSpin, NTag, NText, NThing,
} from 'naive-ui'
import VChart from 'vue-echarts'
import api from '@/api'
import {
  buildMetricsOption, buildStatTargetOptions, PERF_METRIC_META, resolveSeriesByTarget, TOTAL_SERIES_NAME,
} from '@/composables/usePerfMetrics'

defineOptions({ name: 'PerfReportDrawer' })

const show = defineModel('show', { type: Boolean, default: false })

const reportCode = ref(null)
const report = ref(null)
const loading = ref(false)
const metricsUnavailable = ref(false)
const metricsReason = ref('')
/** 总口径与分接口序列（多被测接口时供统计对象切换） */
const metricsSeries = ref({})
const metricsSeriesByName = ref({})
const statTarget = ref(TOTAL_SERIES_NAME)

const statTargetOptions = computed(() => buildStatTargetOptions(metricsSeriesByName.value))

/** 曲线配置：按选定的统计对象取序列（多 target 施压时逐接口分开看） */
const chartOption = computed(() => {
  const series = resolveSeriesByTarget(metricsSeries.value, metricsSeriesByName.value, statTarget.value)
  const pointCount = Object.values(series).reduce((sum, points) => sum + (points?.length || 0), 0)
  return pointCount > 0 ? buildMetricsOption(series, Object.keys(PERF_METRIC_META)) : null
})

const hasSeries = computed(() => chartOption.value != null)

const STATUS_TAG_TYPES = { completed: 'success', running: 'info', failed: 'error', stopped: 'warning' }
const statusTagType = computed(() => STATUS_TAG_TYPES[report.value?.status] || 'default')

/** 聚合指标卡片（口径与报告静态统计列一致；无数据展示 '-'） */
const statCards = computed(() => [
  { label: 'RPS', value: report.value?.rps ?? '-', suffix: 'req/s' },
  { label: '失败率', value: report.value?.fail_rate != null ? `${(report.value.fail_rate * 100).toFixed(2)}` : '-', suffix: '%' },
  { label: '总请求', value: report.value?.total_requests ?? '-', suffix: '次' },
  { label: '总失败', value: report.value?.total_failures ?? '-', suffix: '次' },
  { label: '平均延迟', value: report.value?.avg_latency ?? '-', suffix: 'ms' },
  { label: 'P95 延迟', value: report.value?.p95_latency ?? '-', suffix: 'ms' },
  { label: '实际时长', value: report.value?.actual_duration ?? '-', suffix: 's' },
  { label: '执行人', value: report.value?.created_user || '-', suffix: '' },
])

/** locust 统计明细行（管线入库结构为 {stats: {total, entries}, errors}，字段对齐 result_writer._serialize_stats_entry）；
 * 单接口 RPS 不能取 current_rps（压测结束后归零，与 total 同一陷阱），改按 请求数/实际时长 折算 */
const entries = computed(() => {
  const rows = report.value?.locust_stats?.stats?.entries || []
  const seconds = Number(report.value?.actual_duration) || 0
  return rows.map((row) => ({ ...row, rps: seconds >= 1 ? row.num_requests / seconds : 0 }))
})
const errors = computed(() => report.value?.locust_stats?.errors || [])

function renderMs(value) {
  return value == null ? '-' : `${Number(value).toFixed(1)}`
}

const entryColumns = [
  { title: '接口', key: 'name', minWidth: 200, ellipsis: { tooltip: true } },
  { title: '方法', key: 'method', width: 80 },
  { title: '请求数', key: 'num_requests', width: 80 },
  { title: '失败数', key: 'num_failures', width: 80 },
  { title: '中位(ms)', key: 'median_response_time', width: 90, render: (row) => renderMs(row.median_response_time) },
  { title: '平均(ms)', key: 'avg_response_time', width: 90, render: (row) => renderMs(row.avg_response_time) },
  { title: '最小(ms)', key: 'min_response_time', width: 90, render: (row) => renderMs(row.min_response_time) },
  { title: '最大(ms)', key: 'max_response_time', width: 90, render: (row) => renderMs(row.max_response_time) },
  { title: 'P95(ms)', key: 'p95_response_time', width: 90, render: (row) => renderMs(row.p95_response_time) },
  { title: 'RPS', key: 'rps', width: 80, render: (row) => renderMs(row.rps) },
]

/** 打开抽屉：并行拉取报告详情与全窗口指标曲线 */
async function open(code) {
  reportCode.value = code
  report.value = null
  metricsSeries.value = {}
  metricsSeriesByName.value = {}
  statTarget.value = TOTAL_SERIES_NAME
  metricsUnavailable.value = false
  metricsReason.value = ''
  show.value = true
  loading.value = true
  try {
    const [reportRes, metricsRes] = await Promise.allSettled([
      api.getPerfReport({ report_code: code }),
      api.getPerfReportMetrics({ report_code: code }),
    ])
    if (reportRes.status === 'fulfilled') {
      report.value = reportRes.value.data
    } else {
      window.$message?.error('报告详情加载失败')
    }
    if (metricsRes.status === 'fulfilled') {
      const data = metricsRes.value.data || {}
      metricsUnavailable.value = data.available === false
      metricsReason.value = data.reason || ''
      metricsSeries.value = data.series || {}
      metricsSeriesByName.value = data.series_by_name || {}
    }
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
