/**
 * 性能测试域共用下拉常量。
 * 提取/断言来源选项已改由 autotest RESPONSE_EXTRACT/ASSERT_OBJECT_OPTIONS 承担
 * （perf 小写 source 与面板大写 object 的映射见 utils/perfExtractAssert.js）。
 */

/** 接口项指标口径角色 */
export const PERF_API_ROLE_OPTIONS = [
  { label: '被测(measured)', value: 'measured' },
  { label: '准备(prepare)', value: 'prepare' },
  { label: '抽查(verify)', value: 'verify' },
]

/** 思考时间模式 */
export const PERF_DELAY_MODE_OPTIONS = [
  { label: '固定毫秒', value: 'fixed' },
  { label: '区间随机', value: 'uniform' },
]

/** 参数化行分配策略 */
export const PERF_DATASET_STRATEGY_OPTIONS = [
  { label: '循环轮询', value: 'round_robin' },
  { label: '独占一行', value: 'unique' },
  { label: '随机取行', value: 'random' },
]

/** 断言执行口径 */
export const PERF_ASSERT_MODE_OPTIONS = [
  { label: '逐请求断言', value: 'all' },
  { label: '按比例抽样', value: 'sample_ratio' },
]

/** SLA 判定对象层级 */
export const PERF_TARGET_SCOPE_OPTIONS = [
  { label: '全局', value: 'global' },
  { label: '接口', value: 'api' },
  { label: '事务', value: 'transaction' },
]

/** SLA 判定指标（与报告统计字段名一致） */
export const PERF_TARGET_METRIC_OPTIONS = [
  { label: 'RPS', value: 'rps' },
  { label: '成功RPS', value: 'success_rps' },
  { label: '总请求数', value: 'total_requests' },
  { label: '平均RT(ms)', value: 'avg_rt' },
  { label: 'P90(ms)', value: 'p90' },
  { label: 'P95(ms)', value: 'p95' },
  { label: 'P99(ms)', value: 'p99' },
  { label: '失败率(%)', value: 'error_rate' },
]

/** SLA 比较运算符 */
export const PERF_TARGET_OP_OPTIONS = [
  { label: '>', value: 'gt' },
  { label: '>=', value: 'ge' },
  { label: '<', value: 'lt' },
  { label: '<=', value: 'le' },
  { label: '=', value: 'eq' },
]

/** SLA 未达成严重级 */
export const PERF_TARGET_SEVERITY_OPTIONS = [
  { label: '失败', value: 'fail' },
  { label: '告警', value: 'warn' },
]
