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

/** 指标元数据：中文名/单位/颜色/轴（rps|users 类左轴计数，latency 右轴毫秒，rate 百分比，host 施压机资源） */
export const PERF_METRIC_META = {
  krun_perf_rps: { label: 'RPS', unit: 'req/s', color: '#18a058', axis: 'count' },
  krun_perf_current_users: { label: '并发用户', unit: '人', color: '#2080f0', axis: 'count' },
  krun_perf_failure_rate: { label: '失败率', unit: '%', color: '#d03050', axis: 'rate' },
  krun_perf_avg_latency_ms: { label: '平均延迟', unit: 'ms', color: '#f0a020', axis: 'latency' },
  krun_perf_p95_latency_ms: { label: 'P95 延迟', unit: 'ms', color: '#722ed1', axis: 'latency' },
  krun_perf_requests_total: { label: '累计请求', unit: '次', color: '#0fa3a3', axis: 'count' },
  krun_perf_failures_total: { label: '累计失败', unit: '次', color: '#c2255c', axis: 'count' },
  krun_perf_host_cpu_percent: { label: 'CPU 占用', unit: '%', color: '#e05d44', axis: 'host' },
  krun_perf_host_memory_percent: { label: '内存占用', unit: '%', color: '#3a8ee6', axis: 'host' },
  krun_perf_host_net_sent_kb_s: { label: '网卡发送', unit: 'KB/s', color: '#2bb596', axis: 'host' },
  krun_perf_host_net_recv_kb_s: { label: '网卡接收', unit: 'KB/s', color: '#e6a23c', axis: 'host' },
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
 * 曲线分区定义: 吞吐/响应时间/错误率/施压机资源各占一区, 指标名与 PERF_METRIC_META 对齐。
 * 累计类指标(requests_total/failures_total)单调递增不参与分区(与报告指标卡重复)。
 * 主机指标与引擎 host_monitor.py 的 METRIC_HOST_* 对齐(三处同步: 后端 perf_metrics_service/引擎/本文件)。
 */
export const PERF_METRIC_ZONES = [
  { title: '吞吐', metrics: ['krun_perf_rps', 'krun_perf_current_users'] },
  { title: '响应时间', metrics: ['krun_perf_avg_latency_ms', 'krun_perf_p95_latency_ms'] },
  { title: '错误率', metrics: ['krun_perf_failure_rate'] },
  { title: '施压机资源', metrics: ['krun_perf_host_cpu_percent', 'krun_perf_host_memory_percent', 'krun_perf_host_net_sent_kb_s', 'krun_perf_host_net_recv_kb_s'] },
]

/**
 * 构建指标曲线分区 echarts option: 吞吐/响应时间/错误率/施压机资源纵排分区,
 * 共享时间轴与缩放联动(定位突发毛刺时各区同步观察吞吐/延迟/错误率/主机资源的联动关系)。
 * @param {Object} series 后端归一化序列 { 指标名: [{time, value}] }
 * @returns {Object} echarts option
 */
export function buildZonedMetricsOption(series = {}) {
  const legendData = []
  const seriesList = []
  const gridList = []
  const xAxisList = []
  const yAxisList = []
  // 分区纵向布局按区数动态计算: 预留顶部 legend(7%)与底部缩放条(top 76% 起), 区间内均匀分布
  const zoneCount = PERF_METRIC_ZONES.length
  const layoutTop = 7
  const layoutBottom = 75
  const layoutGap = 2.5
  const layoutHeight = (layoutBottom - layoutTop - (zoneCount - 1) * layoutGap) / zoneCount
  PERF_METRIC_ZONES.forEach((zone, zoneIndex) => {
    const layout = { top: `${layoutTop + zoneIndex * (layoutHeight + layoutGap)}%`, height: `${layoutHeight}%` }
    gridList.push({ ...layout, left: 56, right: 24 })
    // 各区独立时间轴, 末区显示刻度其余隐藏
    xAxisList.push({
      type: 'time', gridIndex: zoneIndex,
      show: zoneIndex === PERF_METRIC_ZONES.length - 1,
      axisLabel: { hideOverlap: true },
    })
    yAxisList.push({ type: 'value', gridIndex: zoneIndex, name: zone.title, scale: true })
    zone.metrics.forEach((name) => {
      const meta = PERF_METRIC_META[name]
      const points = series[name]
      if (!meta || !Array.isArray(points)) return
      legendData.push(meta.label)
      seriesList.push({
        name: meta.label,
        type: 'line',
        xAxisIndex: zoneIndex,
        yAxisIndex: zoneIndex,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.5, color: meta.color },
        itemStyle: { color: meta.color },
        data: toChartPoints(points),
      })
    })
  })
  const zoomAxisIndexes = PERF_METRIC_ZONES.map((_, index) => index)
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => (v == null ? '-' : v),
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
    },
    legend: { data: legendData, top: 0, type: 'scroll' },
    grid: gridList,
    xAxis: xAxisList,
    yAxis: yAxisList,
    dataZoom: [
      { type: 'inside', xAxisIndex: zoomAxisIndexes },
      { type: 'slider', xAxisIndex: zoomAxisIndexes, height: 16, bottom: 4 },
    ],
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
 * @returns {Object} {指标名: [点]}，可直接交给 buildZonedMetricsOption
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
