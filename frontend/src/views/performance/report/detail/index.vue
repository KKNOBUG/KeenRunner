<!--
  压测报告详情页 — 一次施压的不可变结论（只读快照，独立标签页展示）

  由「压测报告」列表页「详情」跳转进入（隐藏菜单，query 传 report_code），替代原抽屉展示。
  报告是只读不可变快照；指标曲线经 /perf/report/metrics 代理 VictoriaMetrics 拉取。
  区块顺序参考 BrickCoreAI 报告页：概要 → 可信度风险 → 全局指标 → SLA 判定 → 基线对比 →
  指标曲线 → 接口维度 → 事务维度 → 准备与抽查 → 错误归因 → 失败原因 → 数据作业 → 原始产物 → 附录。
-->
<template>
  <CommonPage>
    <!-- 顶部栏：返回 + 报告标题 + 状态 + 页级操作（导出/配置快照） -->
    <template #header>
      <div class="report-header">
        <div class="report-header-left">
          <n-button size="small" quaternary @click="handleBack">← 返回列表</n-button>
          <span class="report-title">压测报告 · {{ report?.scene_name || reportCode || '' }}</span>
          <n-tag v-if="report" :type="STATUS_TAG_TYPES[report.status] || 'default'" size="small" round>
            {{ STATUS_LABELS[report.status] || report.status }}
          </n-tag>
        </div>
        <div class="report-header-right">
          <n-button size="small" secondary type="primary" :loading="exporting" :disabled="!reportCode" @click="handleExport">
            导出报告
          </n-button>
          <n-button size="small" secondary :disabled="!report" @click="configSnapshotShow = true">
            查看配置快照
          </n-button>
        </div>
      </div>
    </template>

    <n-empty v-if="!reportCode" description="缺少报告编码，无法加载报告详情" style="margin-top: 80px" />

    <n-spin v-else :show="loading">
      <n-space vertical :size="16">
        <!-- 区块一：概要（执行时刻的场景负载与结论头信息） -->
        <n-descriptions v-if="report" :column="3" size="small" label-placement="left" bordered>
          <n-descriptions-item label="报告编码">{{ report.report_code }}</n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="STATUS_TAG_TYPES[report.status] || 'default'" size="small">
              {{ STATUS_LABELS[report.status] || report.status }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="结束原因">
            {{ STOPPED_REASON_LABELS[report.stopped_reason] || report.stopped_reason || '-' }}
          </n-descriptions-item>
          <n-descriptions-item label="压测场景">{{ report.scene_name || '-' }}</n-descriptions-item>
          <n-descriptions-item label="施压模式">{{ RUN_MODE_LABELS[report.run_mode] || report.run_mode || '-' }}</n-descriptions-item>
          <n-descriptions-item label="负载快照">
            {{ report.concurrent_users }} 人 · 计划 {{ formatDuration(report.run_duration) }}
            · {{ report.process_count }} 进程<template v-if="report.target_rps"> · 目标 {{ report.target_rps }} RPS</template>
          </n-descriptions-item>
          <n-descriptions-item label="施压环境">
            {{ report.env_name || '-' }}{{ report.env_config_name ? ` / ${report.env_config_name}` : '' }}
          </n-descriptions-item>
          <n-descriptions-item label="目标地址" :span="2">
            <n-text code>{{ report.target_host || '-' }}</n-text>
          </n-descriptions-item>
          <n-descriptions-item label="开始时间">{{ report.started_time || '-' }}</n-descriptions-item>
          <n-descriptions-item label="结束时间">{{ report.finished_time || '-' }}</n-descriptions-item>
          <n-descriptions-item label="有效时长">
            {{ report.duration_seconds }}s（剔除预热 {{ report.warmup_seconds }}s）
          </n-descriptions-item>
          <n-descriptions-item label="执行人">{{ report.created_user || '-' }}</n-descriptions-item>
          <n-descriptions-item label="批次标识">{{ report.batch_code || '-' }}</n-descriptions-item>
        </n-descriptions>

        <!-- 区块二：统计可信度风险条 -->
        <template v-if="statWarnings.length">
          <n-alert v-for="(warning, index) in statWarnings" :key="index" :bordered="false" type="warning">
            {{ warning.text || warning }}
          </n-alert>
        </template>

        <!-- 区块三：全局指标卡（measured 口径） -->
        <n-grid v-if="report" :cols="4" :x-gap="10" :y-gap="10">
          <n-gi v-for="card in statCards" :key="card.label">
            <n-card size="small" :bordered="true">
              <n-statistic :label="card.label">
                <n-text :type="card.type || undefined">{{ card.value }}</n-text>
                <template #suffix>
                  <n-text depth="4" style="font-size: 12px">{{ card.suffix }}</n-text>
                </template>
              </n-statistic>
            </n-card>
          </n-gi>
        </n-grid>

        <!-- 区块四：SLA 判定 -->
        <template v-if="targetRows.length">
          <n-divider title-placement="left" style="margin: 8px 0">SLA 判定</n-divider>
          <n-data-table
              :columns="targetColumns"
              :data="targetRows"
              :pagination="false"
              size="small"
              :scroll-x="900"
          />
        </template>
        <n-alert v-else-if="report" :bordered="false" type="info">
          未配置性能验收目标，无法判定是否达标（可在场景「性能验收目标」中配置）
        </n-alert>

        <!-- 区块五：基线对比 -->
        <template v-if="baselineDiff">
          <n-divider title-placement="left" style="margin: 8px 0">
            基线对比（{{ report?.baseline_report_code || '基线报告' }}）
          </n-divider>
          <n-alert v-if="baselineDiff.comparable === false" :bordered="false" type="warning">
            基线不可比：{{ (baselineDiff.incomparable_reasons || []).join('；') || '配置指纹不一致' }}
          </n-alert>
          <template v-else>
            <n-grid :cols="3" :x-gap="10">
              <n-gi>
                <n-statistic label="P95 变化" :value="fmtSignedPercent(baselineDiff.diff?.p95)" suffix="%" />
              </n-gi>
              <n-gi>
                <n-statistic label="RPS 变化" :value="fmtSignedPercent(baselineDiff.diff?.qps)" suffix="%" />
              </n-gi>
              <n-gi>
                <n-statistic label="错误率变化" :value="fmtSignedPercent(baselineDiff.diff?.error_rate)" suffix="%" />
              </n-gi>
            </n-grid>
            <n-alert
                v-for="(violation, index) in (baselineDiff.violations || [])"
                :key="index"
                :bordered="false"
                type="error"
            >
              {{ violation }}
            </n-alert>
          </template>
        </template>

        <!-- 区块六：指标曲线 -->
        <n-text v-if="metricsUnavailable" type="warning" depth="2">
          指标服务不可用：{{ metricsReason || '未配置 VictoriaMetrics' }}
        </n-text>
        <template v-if="hasSeries">
          <n-divider title-placement="left" style="margin: 8px 0">指标曲线</n-divider>
          <n-select
              v-if="statTargetOptions.length > 1"
              v-model:value="statTarget"
              :options="statTargetOptions"
              size="small"
              style="width: 320px"
          />
          <v-chart :option="chartOption" autoresize style="height: 680px" />
        </template>

        <!-- 区块七：接口维度聚合 -->
        <template v-if="apiRows.length">
          <n-divider title-placement="left" style="margin: 8px 0">接口维度</n-divider>
          <n-data-table
              :columns="apiColumns"
              :data="apiRows"
              :pagination="{ pageSize: 10 }"
              size="small"
              :scroll-x="1060"
          />
        </template>

        <!-- 区块八：事务维度聚合 -->
        <template v-if="transactionRows.length">
          <n-divider title-placement="left" style="margin: 8px 0">事务维度</n-divider>
          <n-data-table
              :columns="transactionColumns"
              :data="transactionRows"
              :pagination="false"
              size="small"
              :scroll-x="760"
          />
        </template>

        <!-- 区块九：准备与抽查（不计业务吞吐） -->
        <template v-if="prepare || verify">
          <n-divider title-placement="left" style="margin: 8px 0">准备与抽查</n-divider>
          <n-grid :cols="2" :x-gap="16">
            <n-gi v-if="prepare">
              <n-descriptions :column="1" size="small" label-placement="left" bordered>
                <n-descriptions-item label="准备段(登录/取token)">
                  {{ prepare.rounds ?? '-' }} 轮 · 成功率 {{ fmtNum(prepare.success_rate) }}% · 平均 {{ fmtNum(prepare.avg_rt) }}ms
                </n-descriptions-item>
                <n-descriptions-item label="Token池命中 / 重试">
                  {{ prepare.token_pool_hit ?? '-' }} / {{ prepare.retry_count ?? '-' }}
                </n-descriptions-item>
              </n-descriptions>
            </n-gi>
            <n-gi v-if="verify">
              <n-descriptions :column="1" size="small" label-placement="left" bordered>
                <n-descriptions-item label="正确性抽查">
                  {{ verify.checks ?? '-' }} 次 · 通过率 {{ fmtNum(verify.pass_rate) }}%
                </n-descriptions-item>
                <n-descriptions-item label="抽查失败样本">
                  {{ (verify.fail_samples || []).length || '无' }}
                </n-descriptions-item>
              </n-descriptions>
            </n-gi>
          </n-grid>
          <n-data-table
              v-if="(verify?.fail_samples || []).length"
              :columns="verifyFailColumns"
              :data="verify.fail_samples"
              :pagination="false"
              size="small"
          />
        </template>

        <!-- 区块十：错误归因 -->
        <template v-if="errorRows.length">
          <n-divider title-placement="left" style="margin: 8px 0">错误归因</n-divider>
          <n-data-table
              :columns="errorColumns"
              :data="errorRows"
              :pagination="{ pageSize: 10 }"
              size="small"
              :scroll-x="720"
          />
        </template>

        <!-- 区块十一：失败原因 -->
        <n-alert v-if="report?.error_message" :bordered="false" type="error">
          {{ report.error_message }}
        </n-alert>

        <!-- 区块十二：数据作业与备注（带外作业结论回显，场景联动触发后才有值） -->
        <template v-if="jobNotesBlocks.length">
          <n-divider title-placement="left" style="margin: 8px 0">数据作业与备注</n-divider>
          <n-descriptions :column="1" size="small" label-placement="left" bordered>
            <n-descriptions-item v-for="block in jobNotesBlocks" :key="block.label" :label="block.label">
              {{ block.value }}
            </n-descriptions-item>
          </n-descriptions>
        </template>

        <!-- 区块十三：原始产物（引擎工作目录白名单文件，报告失败在引擎拉起前无产物则不渲染） -->
        <template v-if="artifacts.length">
          <n-divider title-placement="left" style="margin: 8px 0">原始产物</n-divider>
          <n-data-table
              :columns="artifactColumns"
              :data="artifacts"
              :pagination="false"
              size="small"
          />
        </template>

        <!-- 区块十四：附录 · 指标说明（术语释义，帮助阅读本报告各同名指标） -->
        <n-divider title-placement="left" style="margin: 8px 0">附录：指标说明</n-divider>
        <n-text depth="3" style="font-size: 12px">
          下列释义适用于本报告中的同名指标；若某区块未出现对应字段可忽略。
        </n-text>
        <n-data-table
            :columns="glossaryColumns"
            :data="GLOSSARY_ROWS"
            :pagination="false"
            size="small"
            :scroll-x="680"
        />
      </n-space>

      <!-- 配置快照弹窗：执行时刻的场景负载快照与配置指纹（事后改场景不影响本报告记载） -->
      <n-modal
          v-model:show="configSnapshotShow"
          preset="card"
          title="配置快照（执行时刻）"
          style="width: 760px"
      >
        <n-space vertical :size="8">
          <n-space justify="end">
            <n-button size="small" secondary @click="copyConfigSnapshot">复制 JSON</n-button>
          </n-space>
          <n-card :bordered="true" size="small">
            <pre class="snapshot-pre">{{ configSnapshotText }}</pre>
          </n-card>
        </n-space>
      </n-modal>
    </n-spin>
  </CommonPage>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  NAlert, NButton, NCard, NDataTable, NDescriptions, NDescriptionsItem, NDivider, NEmpty,
  NGi, NGrid, NModal, NSelect, NSpace, NSpin, NStatistic, NTag, NText,
} from 'naive-ui'
import VChart from 'vue-echarts'

import CommonPage from '@/components/page/CommonPage.vue'
import { useTagsStore } from '@/store'
import api from '@/api'
import { downloadBlobResponse } from '@/utils/common/downloadFile'
import {
  buildStatTargetOptions, buildZonedMetricsOption, resolveSeriesByTarget, TOTAL_SERIES_NAME,
} from '@/composables/usePerfMetrics'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测报告详情' })

const route = useRoute()
const tagsStore = useTagsStore()

const STATUS_LABELS = { running: '执行中', completed: '已完成', failed: '失败', stopped: '已停止' }
const STATUS_TAG_TYPES = { running: 'info', completed: 'success', failed: 'error', stopped: 'warning' }
const RUN_MODE_LABELS = { single: '单接口', mixed: '混合流量', journey: '业务链路' }
const STOPPED_REASON_LABELS = {
  completed: '正常完成', manual: '手动停止', circuit_break: '熔断触发',
  engine_error: '引擎异常', timeout_kill: '超时强杀',
}
/** SLA 指标中文口径（与 constants/perfApi.PERF_TARGET_METRIC_OPTIONS 一致） */
const TARGET_METRIC_LABELS = {
  rps: 'RPS', success_rps: '成功RPS', total_requests: '总请求数', avg_rt: '平均RT(ms)',
  p90: 'P90(ms)', p95: 'P95(ms)', p99: 'P99(ms)', error_rate: '失败率(%)',
}
const TARGET_SCOPE_LABELS = { global: '全局', api: '接口', transaction: '事务' }
const OP_SYMBOLS = { gt: '>', ge: '>=', lt: '<', le: '<=', eq: '=' }

const reportCode = ref(route.query.report_code || null)
const report = ref(null)
const loading = ref(false)
const exporting = ref(false)
const metricsUnavailable = ref(false)
const metricsReason = ref('')
/** 总口径与分接口序列（多被测接口时供统计对象切换） */
const metricsSeries = ref({})
const metricsSeriesByName = ref({})
const statTarget = ref(TOTAL_SERIES_NAME)
/** 报告产物清单与配置快照弹窗（产物请求404=引擎未拉起，静默置空） */
const artifacts = ref([])
const configSnapshotShow = ref(false)

const statTargetOptions = computed(() => buildStatTargetOptions(metricsSeriesByName.value))

/** 曲线配置：分区布局(吞吐/响应时间/错误率/施压机资源)按选定的统计对象取序列（多 target 施压时逐接口分开看；主机指标仅总口径，选定接口时无主机序列） */
const chartOption = computed(() => {
  const series = resolveSeriesByTarget(metricsSeries.value, metricsSeriesByName.value, statTarget.value)
  const pointCount = Object.values(series).reduce((sum, points) => sum + (points?.length || 0), 0)
  return pointCount > 0 ? buildZonedMetricsOption(series) : null
})

const hasSeries = computed(() => chartOption.value != null)

const statWarnings = computed(() => report.value?.stat_warnings || [])
const targetRows = computed(() => report.value?.target_result || [])
const apiRows = computed(() => report.value?.api_aggregations || [])
const transactionRows = computed(() => report.value?.transaction_aggregations || [])
const prepare = computed(() => report.value?.prepare_metrics || null)
const verify = computed(() => report.value?.verify_metrics || null)
const errorRows = computed(() => report.value?.error_breakdown || [])
const baselineDiff = computed(() => report.value?.baseline_diff || null)

/** 配置快照 JSON 文本：含指纹与接口版本映射，只读展示 */
const configSnapshotText = computed(() => {
  const r = report.value
  if (!r) return ''
  return JSON.stringify({
    config_fingerprint: r.config_fingerprint,
    api_versions: r.api_versions,
    config_snapshot: r.config_snapshot,
  }, null, 2)
})

/** E组作业关联与备注（仅展示有值项：联动链路未触发时四列均为空，不渲染区块） */
const jobNotesBlocks = computed(() => {
  const r = report.value || {}
  const blocks = []
  if ((r.prepare_job_ids || []).length) {
    blocks.push({ label: '施压前造数作业', value: r.prepare_job_ids.map((id) => `#${id}`).join('、') })
  }
  if ((r.verify_job_ids || []).length) {
    blocks.push({ label: '施压后校验作业', value: r.verify_job_ids.map((id) => `#${id}`).join('、') })
  }
  if ((r.verify_report_codes || []).length) {
    blocks.push({ label: '校验作业报告', value: r.verify_report_codes.join('、') })
  }
  if (r.notes) {
    blocks.push({ label: '备注', value: r.notes })
  }
  return blocks
})

function fmtNum(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

/** 基线差值带符号百分比（正=上升） */
function fmtSignedPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  const num = Number(value)
  return `${num > 0 ? '+' : ''}${num.toFixed(2)}`
}

function formatDuration(seconds) {
  const total = Number(seconds) || 0
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return rest ? `${minutes}m${rest}s` : `${minutes}m`
}

/** 全局指标卡（百分比口径 0~100 与场景判定、熔断阈值同一把尺子） */
const statCards = computed(() => [
  { label: 'RPS', value: fmtNum(report.value?.rps), suffix: 'req/s' },
  { label: '成功RPS', value: fmtNum(report.value?.success_rps), suffix: 'req/s' },
  { label: '总请求', value: report.value?.total_requests ?? '-', suffix: '次' },
  { label: '失败率', value: fmtNum(report.value?.error_rate), suffix: '%', type: (report.value?.error_rate || 0) > 0 ? 'error' : undefined },
  { label: '平均RT', value: fmtNum(report.value?.avg_rt), suffix: 'ms' },
  { label: 'P95', value: fmtNum(report.value?.p95), suffix: 'ms' },
  { label: 'P99', value: fmtNum(report.value?.p99), suffix: 'ms' },
  { label: '标准差', value: fmtNum(report.value?.std_dev), suffix: 'ms' },
])

// ---------- SLA 判定表格 ----------

const targetColumns = [
  { title: '层级', key: 'scope', width: 70, render: (row) => TARGET_SCOPE_LABELS[row.scope] || row.scope },
  { title: '指标', key: 'target', width: 100, render: (row) => TARGET_METRIC_LABELS[row.target] || row.target },
  { title: '对象', key: 'api_ref', minWidth: 140, ellipsis: { tooltip: true }, render: (row) => row.api_ref || '全局' },
  {
    title: '判定',
    key: 'expect',
    width: 160,
    render: (row) => `${OP_SYMBOLS[row.op] || row.op} ${fmtNum(row.expect)}`,
  },
  { title: '实际', key: 'actual', width: 110, render: (row) => (row.skipped ? '-' : fmtNum(row.actual)) },
  {
    title: '结论',
    key: 'passed',
    width: 90,
    render: (row) => {
      if (row.skipped) return h(NTag, { size: 'small' }, { default: () => '跳过' })
      return h(NTag, { size: 'small', type: row.passed ? 'success' : 'error' },
          { default: () => (row.passed ? '达标' : '未达标') })
    },
  },
  {
    title: '严重级',
    key: 'severity',
    width: 70,
    render: (row) => (row.severity === 'fail' ? '失败' : row.severity === 'warn' ? '告警' : row.severity || '-'),
  },
  {
    title: '说明',
    key: 'reason',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.reason || (row.skipped ? '样本量或时长不足，跳过判定' : '-'),
  },
]

// ---------- 接口维度聚合表格 ----------

const apiColumns = [
  { title: '接口', key: 'api_name', minWidth: 170, ellipsis: { tooltip: true } },
  { title: '方法', key: 'method', width: 70 },
  { title: '请求数', key: 'total_requests', width: 85 },
  { title: '失败数', key: 'failed_requests', width: 85 },
  { title: '失败率', key: 'error_rate', width: 80, render: (row) => `${fmtNum(row.error_rate)}%` },
  { title: '平均RT', key: 'avg_rt', width: 85, render: (row) => fmtNum(row.avg_rt) },
  { title: 'P90', key: 'p90', width: 80, render: (row) => fmtNum(row.p90) },
  { title: 'P95', key: 'p95', width: 80, render: (row) => fmtNum(row.p95) },
  { title: 'P99', key: 'p99', width: 80, render: (row) => fmtNum(row.p99) },
  { title: 'RPS', key: 'rps', width: 80, render: (row) => fmtNum(row.rps) },
  {
    title: '置信',
    key: 'low_confidence',
    width: 70,
    render: (row) => h(NTag, { size: 'small', type: row.low_confidence ? 'warning' : 'default' },
        { default: () => (row.low_confidence ? '低' : '正常') }),
  },
]

// ---------- 事务维度聚合表格 ----------

const transactionColumns = [
  { title: '事务', key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  { title: '圈数', key: 'rounds', width: 90 },
  { title: '失败圈', key: 'failed', width: 90 },
  { title: '平均RT(ms)', key: 'avg_rt', width: 110, render: (row) => fmtNum(row.avg_rt) },
  { title: 'P95(ms)', key: 'p95', width: 100, render: (row) => fmtNum(row.p95) },
  { title: '业务TPS', key: 'business_tps', width: 100, render: (row) => fmtNum(row.business_tps) },
]

// ---------- 抽查失败样本表格 ----------

const verifyFailColumns = [
  { title: '样本', key: 'name', minWidth: 160, ellipsis: { tooltip: true } },
  { title: '错误', key: 'error', minWidth: 260, ellipsis: { tooltip: true } },
  { title: '次数', key: 'occurrences', width: 80 },
]

// ---------- 错误归因表格 ----------

const errorColumns = [
  { title: '接口', key: 'api_name', minWidth: 160, ellipsis: { tooltip: true } },
  { title: '方法', key: 'method', width: 70 },
  { title: '错误', key: 'error', minWidth: 320, ellipsis: { tooltip: true } },
  { title: '次数', key: 'occurrences', width: 90 },
]

// ---------- 原始产物表格 ----------

const artifactColumns = [
  { title: '类型', key: 'kind', width: 90 },
  { title: '文件', key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  { title: '体积', key: 'size_human', width: 90 },
  { title: '修改时间', key: 'modified_time', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 70,
    render: (row) => h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => downloadArtifact(row) },
        { default: () => '下载' }),
  },
]

// ---------- 附录：指标说明（静态术语表，帮助阅读本报告各同名指标） ----------

const GLOSSARY_ROWS = [
  { metric: 'RPS', desc: '每秒完成的请求数（吞吐量），衡量系统单位时间处理能力' },
  { metric: '成功RPS', desc: '每秒成功完成的请求数，剔除失败请求后的吞吐' },
  { metric: '总请求', desc: '本次施压累计发出的请求总数' },
  { metric: '失败率', desc: '失败请求数 / 总请求数 × 100%，越低越好' },
  { metric: '平均RT', desc: '所有请求响应时间的算术平均值（ms）' },
  { metric: 'P90 / P95 / P99', desc: '分位响应时间：90% / 95% / 99% 的请求响应时间不超过该值（ms），比平均值更能反映长尾体验' },
  { metric: '标准差', desc: '响应时间的离散程度（ms），越大说明响应时间越不稳定' },
  { metric: '并发用户', desc: '施压期间模拟的虚拟用户数（VU）' },
  { metric: '有效时长', desc: '剔除预热后纳入统计的施压时长（s）' },
  { metric: '预热 Warmup', desc: '施压正式统计前的暖机时长，其数据不计入指标，避免冷启动干扰' },
  { metric: 'SLA 判定', desc: '按场景「性能验收目标」对指标逐项判定达标/未达标；未配置目标则不判定' },
  { metric: '基线对比', desc: '与场景钉选的基线报告做退化对比，展示 P95 / RPS / 错误率变化' },
  { metric: '低置信', desc: '样本量或施压时长不足，该接口指标仅供参考，不宜作为性能结论' },
  { metric: '接口维度', desc: '按被测接口聚合的指标；分位值基于采样样本，总请求/RPS/失败率不受采样限制' },
  { metric: '事务维度', desc: '按业务事务（多接口链路一圈）聚合的圈数、失败圈、业务 TPS 等' },
  { metric: '准备与抽查', desc: '施压前造数/登录取 token 与施压后正确性抽查结论，不计入业务吞吐' },
  { metric: '错误归因', desc: '按接口 + 错误信息聚合的失败次数，用于定位失败原因' },
]

const glossaryColumns = [
  { title: '指标', key: 'metric', width: 160, ellipsis: { tooltip: true } },
  { title: '含义', key: 'desc', minWidth: 480 },
]

/** 下载产物文件：blob 响应按 Content-Disposition 落盘 */
async function downloadArtifact(row) {
  try {
    const res = await api.downloadPerfReportArtifact({ report_code: reportCode.value, name: row.name })
    await downloadBlobResponse(res, row.name)
  } catch (e) {
    window.$message?.error?.(e?.message || '产物下载失败')
  }
}

/** 导出报告 xlsx 报表（概要/SLA/接口/事务/错误/基线多 sheet） */
async function handleExport() {
  if (!reportCode.value) return
  exporting.value = true
  try {
    const res = await api.exportPerfReport({ report_code: reportCode.value })
    await downloadBlobResponse(res, `压测报告_${reportCode.value}.xlsx`)
  } catch (e) {
    window.$message?.error?.(e?.message || '报告导出失败')
  } finally {
    exporting.value = false
  }
}

/** 复制配置快照 JSON 到剪贴板 */
async function copyConfigSnapshot() {
  try {
    await navigator.clipboard.writeText(configSnapshotText.value)
    window.$message?.success('配置快照已复制到剪贴板')
  } catch (e) {
    window.$message?.error?.('复制失败，请手动选择文本复制')
  }
}

/** 返回列表：关闭当前详情页签并回到相邻页签（列表页），避免残留详情标签 */
function handleBack() {
  tagsStore.removeTag(route.path)
}

/** 加载报告：并行拉取报告详情、全窗口指标曲线与产物清单（产物404静默） */
async function loadReport(code) {
  report.value = null
  metricsSeries.value = {}
  metricsSeriesByName.value = {}
  statTarget.value = TOTAL_SERIES_NAME
  metricsUnavailable.value = false
  metricsReason.value = ''
  artifacts.value = []
  configSnapshotShow.value = false
  loading.value = true
  try {
    const [reportRes, metricsRes, artifactsRes] = await Promise.allSettled([
      api.getPerfReport({ report_code: code }),
      api.getPerfReportMetrics({ report_code: code }),
      api.getPerfReportArtifacts({ report_code: code }),
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
    if (artifactsRes.status === 'fulfilled') {
      artifacts.value = artifactsRes.value.data?.data || []
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (reportCode.value) loadReport(reportCode.value)
})
</script>

<style scoped>
/* 顶部栏：左侧返回+标题+状态，右侧页级操作，两端对齐 */
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
}

.report-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.report-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.report-title {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 配置快照 JSON 只读展示: 等宽字体 + 最大高度内滚动 + 长行折行 */
.snapshot-pre {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
