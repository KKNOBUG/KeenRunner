/**
 * 压测指标曲线 composable：echarts 按需注册、指标元数据与轮询控制。
 *
 * 指标名与后端 perf_metrics_service.PERF_METRIC_NAMES / 引擎 metrics_push.METRIC_* 对齐，
 * 新增指标时三处同步维护；统计对象（total/接口名）与 metrics_push.TOTAL_SERIES_NAME 对齐。
 */
import { onUnmounted, ref, shallowRef } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

/** 指标元数据：中文名/单位/颜色/轴（rps|users 类左轴计数，latency 右轴毫秒，rate 百分比） */
export const PERF_METRIC_META = {
  krun_perf_rps: { label: 'RPS', unit: 'req/s', color: '#18a058', axis: 'count' },
  krun_perf_current_users: { label: '并发用户', unit: '人', color: '#2080f0', axis: 'count' },
  krun_perf_failure_rate: { label: '失败率', unit: '%', color: '#d03050', axis: 'rate' },
  krun_perf_avg_latency_ms: { label: '平均延迟', unit: 'ms', color: '#f0a020', axis: 'latency' },
  krun_perf_p95_latency_ms: { label: 'P95 延迟', unit: 'ms', color: '#722ed1', axis: 'latency' },
  krun_perf_requests_total: { label: '累计请求', unit: '次', color: '#0fa3a3', axis: 'count' },
  krun_perf_failures_total: { label: '累计失败', unit: '次', color: '#c2255c', axis: 'count' },
}

/** 总口径序列名（与后端 perf_metrics_service.TOTAL_SERIES_NAME、引擎 metrics_push 一致） */
export const TOTAL_SERIES_NAME = 'total'

/**
 * 归一化后端序列为 echarts 折线数据点。
 * @param {Array<{time:number, value:number}>} points 后端 series 元素（time 为 Unix 秒）
 * @returns {Array<[number, number]>} [毫秒时间戳, 数值]（NaN 转为 null 断线显示）
 */
export function toChartPoints(points = []) {
  return points.map((p) => [p.time * 1000, Number.isNaN(p.value) ? null : p.value])
}

/**
 * 构建指标曲线 echarts option（双 y 轴：计数 + 延迟毫秒；失败率并入计数轴百分比展示）。
 * @param {Object} series 后端归一化序列 { 指标名: [{time, value}] }
 * @param {string[]} [metricNames] 参与绘制的指标（缺省全部有元数据的指标）
 * @returns {Object} echarts option
 */
export function buildMetricsOption(series = {}, metricNames) {
  const names = metricNames || Object.keys(PERF_METRIC_META)
  const legendData = []
  const seriesList = []
  let hasLatency = false
  names.forEach((name) => {
    const meta = PERF_METRIC_META[name]
    const points = series[name]
    if (!meta || !Array.isArray(points)) return
    if (meta.axis === 'latency') hasLatency = true
    legendData.push(meta.label)
    seriesList.push({
      name: meta.label,
      type: 'line',
      // 延迟类指标走右轴毫秒，其余走左轴计数（与下方 yAxis 声明对应）
      yAxisIndex: meta.axis === 'latency' ? 1 : 0,
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 1.5, color: meta.color },
      itemStyle: { color: meta.color },
      data: toChartPoints(points),
    })
  })
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '-' : v) },
    legend: { data: legendData, top: 0, type: 'scroll' },
    grid: { left: 56, right: hasLatency ? 60 : 28, top: 36, bottom: 48 },
    xAxis: { type: 'time', axisLabel: { hideOverlap: true } },
    yAxis: [
      { type: 'value', name: '次数/用户', scale: true },
      { type: 'value', name: 'ms', scale: true, splitLine: { show: false } },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
    series: seriesList,
  }
}

/**
 * 统计对象下拉选项：总口径 + 各被测接口（多 target 施压时按接口独立成序列）。
 * @param {Object} seriesByName 后端分接口序列 {指标名: {接口名: [点]}}
 * @returns {Array<{label: string, value: string}>} 选项列表
 */
export function buildStatTargetOptions(seriesByName = {}) {
  const names = new Set()
  Object.values(seriesByName || {}).forEach((byName) => {
    Object.keys(byName || {}).forEach((name) => names.add(name))
  })
  const options = [...names].sort().map((name) => ({ label: name, value: name }))
  return [{ label: '总口径（全部接口）', value: TOTAL_SERIES_NAME }, ...options]
}

/**
 * 取出指定统计对象的指标序列集合。
 * @param {Object} series 总口径序列 {指标名: [点]}
 * @param {Object} seriesByName 分接口序列 {指标名: {接口名: [点]}}
 * @param {string} target 统计对象（total 或接口名）
 * @returns {Object} {指标名: [点]}，可直接交给 buildMetricsOption
 */
export function resolveSeriesByTarget(series, seriesByName, target) {
  if (!target || target === TOTAL_SERIES_NAME) return series || {}
  const resolved = {}
  Object.entries(seriesByName || {}).forEach(([metric, byName]) => {
    if (byName && byName[target]) resolved[metric] = byName[target]
  })
  return resolved
}

/**
 * 轮询控制：组件卸载自动停止，避免抽屉关闭后继续请求。
 * @param {Function} fetchFn 轮询执行函数（异步）
 * @param {number} intervalMs 轮询间隔毫秒
 */
export function usePolling(fetchFn, intervalMs = 2000) {
  const timer = shallowRef(null)
  const polling = ref(false)

  async function tick() {
    if (!polling.value) return
    try {
      await fetchFn()
    } finally {
      if (polling.value) timer.value = setTimeout(tick, intervalMs)
    }
  }

  function startPolling() {
    if (polling.value) return
    polling.value = true
    tick()
  }

  function stopPolling() {
    polling.value = false
    if (timer.value) {
      clearTimeout(timer.value)
      timer.value = null
    }
  }

  onUnmounted(stopPolling)
  return { polling, startPolling, stopPolling }
}
