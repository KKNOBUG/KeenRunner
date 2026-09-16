<template>
  <n-drawer v-model:show="show" :width="720" placement="right">
    <n-drawer-content :title="`执行监控 · ${task?.perf_name || ''}`" closable>
      <n-space vertical size="large">
        <n-alert :type="stateAlertType" :show-icon="true">
          {{ stateText }}
        </n-alert>

        <n-space>
          <n-popconfirm v-if="canStop" @positive-click="handleStop">
            <template #trigger>
              <n-button type="error" secondary :loading="stopping">停止压测</n-button>
            </template>
            确认停止当前压测任务？
          </n-popconfirm>
          <n-button v-if="finished && reportCode" type="primary" secondary @click="openReport">
            查看报告
          </n-button>
        </n-space>

        <n-text v-if="metricsUnavailable" type="warning" depth="2">
          指标服务不可用：{{ metricsReason || '未配置 VictoriaMetrics' }}（不影响压测执行与报告统计）
        </n-text>

        <n-select
            v-if="statTargetOptions.length > 1"
            v-model:value="statTarget"
            :options="statTargetOptions"
            size="small"
            style="width: 320px"
        />
        <v-chart v-if="hasSeries" :option="chartOption" autoresize style="height: 380px" />
        <n-empty v-else-if="!pollingActive" description="暂无指标数据" />
        <n-text v-else depth="3">正在等待指标上报…（每 2 秒刷新）</n-text>
      </n-space>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, ref, shallowRef } from 'vue'
import { NAlert, NButton, NDrawer, NDrawerContent, NEmpty, NPopconfirm, NSelect, NSpace, NText } from 'naive-ui'
import VChart from 'vue-echarts'
import api from '@/api'
import {
  buildMetricsOption, buildStatTargetOptions, resolveSeriesByTarget, TOTAL_SERIES_NAME, usePolling,
} from '@/composables/usePerfMetrics'

defineOptions({ name: 'PerfRunDrawer' })

const emit = defineEmits(['finished', 'view-report'])

const show = defineModel('show', { type: Boolean, default: false })

/** 当前监控的任务行（perf_id/perf_code/perf_name/last_execute_state） */
const task = ref(null)
const taskState = ref(null)
const reportCode = ref(null)
const stopping = ref(false)
const finished = ref(false)
const metricsUnavailable = ref(false)
const metricsReason = ref('')
/** 总口径与分接口序列（每轮轮询整体覆盖） */
const metricsSeries = shallowRef({})
const metricsSeriesByName = shallowRef({})
const statTarget = ref(TOTAL_SERIES_NAME)

const statTargetOptions = computed(() => buildStatTargetOptions(metricsSeriesByName.value))
const chartOption = computed(() => {
  const series = resolveSeriesByTarget(metricsSeries.value, metricsSeriesByName.value, statTarget.value)
  const pointCount = Object.values(series).reduce((sum, points) => sum + (points?.length || 0), 0)
  return pointCount > 0 ? buildMetricsOption(series) : null
})
const hasSeries = computed(() => chartOption.value != null)

/** 执行中可停止：排队/执行中/停止过渡态 */
const canStop = computed(() => !finished.value && ['queued', 'running', 'stopping'].includes(taskState.value))
const stateAlertType = computed(() => {
  const mapping = { running: 'info', queued: 'default', stopping: 'warning', completed: 'success', failed: 'error', stopped: 'warning' }
  return mapping[taskState.value] || 'default'
})
const stateText = computed(() => {
  if (stopping.value) return '正在下发停止指令…'
  const labels = {
    queued: '已排队，等待施压进程启动…',
    running: '压测执行中',
    stopping: '停止指令已下发，正在终止进程…',
    completed: '压测完成',
    failed: '压测失败',
    stopped: '压测已停止',
  }
  return labels[taskState.value] || `状态：${taskState.value || '未知'}`
})
const pollingActive = computed(() => polling.polling.value)

/**
 * 轮询体：任务状态 + 最新报告 + 指标曲线。
 * 报告按 perf_code 查询取最新一条（列表按起始时间倒序）；报告进入终态即结束轮询。
 */
async function pollOnce() {
  try {
    const taskRes = await api.getPerfTask({ perf_id: task.value?.perf_id })
    taskState.value = taskRes.data?.last_execute_state || taskState.value
  } catch (e) { /* 单轮失败不中断轮询 */ }

  if (!reportCode.value) {
    try {
      const reportRes = await api.getPerfReportList({ perf_code: task.value?.perf_code, page: 1, page_size: 1 })
      reportCode.value = reportRes.data?.[0]?.report_code || null
    } catch (e) { /* 报告可能尚未创建 */ }
  }
  if (reportCode.value) {
    try {
      const metricsRes = await api.getPerfReportMetrics({ report_code: reportCode.value })
      metricsUnavailable.value = metricsRes.data?.available === false
      metricsReason.value = metricsRes.data?.reason || ''
      metricsSeries.value = metricsRes.data?.series || {}
      metricsSeriesByName.value = metricsRes.data?.series_by_name || {}
    } catch (e) { /* 指标拉取失败不影响状态轮询 */ }
  }

  if (['completed', 'failed', 'stopped'].includes(taskState.value)) {
    finished.value = true
    polling.stopPolling()
    emit('finished', taskState.value)
  }
}

const polling = usePolling(pollOnce, 2000)

/**
 * 打开抽屉并开始监控。
 * @param {Object} row 任务行
 * @param {boolean} autoRun true 时先下发执行（列表「执行」入口）；false 直接监控当前状态
 */
async function open(row, autoRun = true) {
  task.value = row
  taskState.value = row?.last_execute_state || null
  reportCode.value = null
  finished.value = false
  metricsSeries.value = {}
  metricsSeriesByName.value = {}
  statTarget.value = TOTAL_SERIES_NAME
  metricsUnavailable.value = false
  metricsReason.value = ''
  show.value = true
  if (autoRun) {
    try {
      await api.runPerfTask({ perf_code: row.perf_code })
      taskState.value = 'queued'
      window.$message?.success('已下发执行')
    } catch (e) {
      window.$message?.error('下发执行失败')
      return
    }
  }
  polling.startPolling()
}

async function handleStop() {
  stopping.value = true
  try {
    await api.stopPerfTask({ perf_code: task.value?.perf_code })
    window.$message?.success('停止指令已下发，任务将在数秒内终止')
    taskState.value = 'stopping'
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    stopping.value = false
  }
}

function openReport() {
  emit('view-report', reportCode.value)
}

defineExpose({ open })
</script>
