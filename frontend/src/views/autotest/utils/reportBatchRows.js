/**
 * 用例执行历史：按 batch_code 聚合报告行（一次「执行」= 一行）。
 * 与任务调度无关；调用方应自行排除 task_code 记录。
 */

export function isCaseSuccess(state) {
  return state === true || state === 'true'
}

export function parseElapsedSeconds(val) {
  if (val == null || val === '') return 0
  const s = String(val).trim().replace(/s$/i, '')
  const n = parseFloat(s)
  return Number.isFinite(n) ? n : 0
}

export function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '-'
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const m = Math.floor(seconds / 60)
  const sec = seconds - m * 60
  return `${m}m${sec.toFixed(1)}s`
}

export function filterCaseOnlyReports(reports) {
  return (reports || []).filter((r) => !r.task_code || !String(r.task_code).trim())
}

export function annotateDatasetRuns(reports) {
  const sorted = [...(reports || [])].sort((a, b) =>
    String(a.case_st_time || '').localeCompare(String(b.case_st_time || '')),
  )
  return sorted.map((r, index) => {
    const datasetName =
      r.dataset_name != null && String(r.dataset_name).trim()
        ? String(r.dataset_name).trim()
        : null
    return {
      ...r,
      run_index: index + 1,
      dataset_name: datasetName,
      dataset_display: datasetName || '未使用数据源',
    }
  })
}

/**
 * @param {Array} reports 报告列表（建议已排除 task_code）
 * @returns {Array} 批次汇总行
 */
export function buildBatchRows(reports) {
  const map = new Map()
  for (const r of reports || []) {
    const bc = r.batch_code != null ? String(r.batch_code).trim() : ''
    const key = bc || `single:${r.report_code || r.report_id || r.id}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }

  const rows = []
  for (const [key, list] of map) {
    const runs = annotateDatasetRuns(list)
    const passCount = runs.filter((r) => isCaseSuccess(r.case_state)).length
    const total = runs.length
    const allOk = total > 0 && passCount === total
    const elapsedSum = runs.reduce((acc, r) => acc + parseElapsedSeconds(r.case_elapsed), 0)
    const times = runs.map((r) => r.case_st_time).filter(Boolean).sort()
    const users = [...new Set(runs.map((r) => r.created_user).filter(Boolean))]
    const reportCodes = [
      ...new Set(runs.map((r) => r.report_code).filter((x) => x != null && String(x).trim())),
    ]
    const batchCode = key.startsWith('single:') ? null : key
    const first = runs[0] || {}

    rows.push({
      _key: key,
      batch_code: batchCode,
      report_code: total === 1 ? reportCodes[0] || null : null,
      case_id: first.case_id ?? null,
      case_name: first.case_name ?? '',
      report_type: first.report_type ?? null,
      execute_result: allOk,
      report_count: total,
      created_user: users[0] || '-',
      execute_time: times.length ? times[0] : null,
      elapsed_display: formatElapsed(elapsedSum),
      has_multi_dataset: total > 1,
      runs,
    })
  }

  rows.sort((a, b) =>
    String(b.execute_time || '').localeCompare(String(a.execute_time || '')),
  )
  return rows
}
