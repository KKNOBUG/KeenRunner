/**
 * 报告行展示工具（是否多数据源由后端 /autotest/report/search 每行回填 has_multiple_dataset）。
 */

export function isCaseSuccess(state) {
  return state === true || state === 'true'
}
