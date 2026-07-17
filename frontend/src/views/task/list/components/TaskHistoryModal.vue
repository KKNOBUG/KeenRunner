<script setup>
/**
 * 任务执行历史：
 * 1) 弹窗：按 task_code 查报告，再按 batch_code 分组 → 每次任务执行一条
 * 2) 左侧抽屉：按脚本分组展示本批次多次执行（轮次 × 数据源）
 * 3) 右侧抽屉：ReportDetailDrawer 步骤执行明细
 */
import { computed, h, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NModal,
  NPagination,
  NSpace,
  NSpin,
  NTag,
} from 'naive-ui'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  /** 任务行：需含 task_name / task_code / cases_execute_config */
  taskRow: { type: Object, default: null },
})

const emit = defineEmits(['update:show'])

const modalVisible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const historyTaskName = computed(() => props.taskRow?.task_name ?? '')
const historyTaskCode = computed(() => props.taskRow?.task_code ?? '')

const loading = ref(false)
const batchRows = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
})

const pagedBatchRows = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return batchRows.value.slice(start, start + pagination.pageSize)
})

const scriptDrawerVisible = ref(false)
const scriptDrawerTitle = ref('脚本执行信息')
/** 按脚本分组后的结构 */
const scriptGroups = ref([])
const expandedScriptNames = ref([])

const detailDrawerVisible = ref(false)
const detailReportRow = ref(null)

function isCaseSuccess(state) {
  return state === true || state === 'true'
}

function parseElapsedSeconds(val) {
  if (val == null || val === '') return 0
  const s = String(val).trim().replace(/s$/i, '')
  const n = parseFloat(s)
  return Number.isFinite(n) ? n : 0
}

function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '-'
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const m = Math.floor(seconds / 60)
  const sec = seconds - m * 60
  return `${m}m${sec.toFixed(1)}s`
}

function resolveCasesExecuteConfig(taskRow) {
  if (!taskRow || typeof taskRow !== 'object') return {}
  const top = taskRow.cases_execute_config
  if (top && typeof top === 'object') return top
  const kwargs = taskRow.task_kwargs
  if (kwargs && typeof kwargs === 'object' && kwargs.cases_execute_config) {
    return kwargs.cases_execute_config
  }
  return {}
}

function getCaseCfg(caseId) {
  const cfg = resolveCasesExecuteConfig(props.taskRow)
  const caseCfg = cfg[String(caseId)] || cfg[caseId]
  return caseCfg && typeof caseCfg === 'object' ? caseCfg : {}
}

function resolveEnvNamesForCases(caseIds) {
  const names = new Set()
  for (const id of caseIds) {
    const caseCfg = getCaseCfg(id)
    if (caseCfg.env_name) names.add(String(caseCfg.env_name).trim())
    const steps = caseCfg.steps_execute_config
    if (steps && typeof steps === 'object') {
      for (const stepCfg of Object.values(steps)) {
        if (stepCfg && typeof stepCfg === 'object' && stepCfg.env_name) {
          names.add(String(stepCfg.env_name).trim())
        }
      }
    }
  }
  return [...names].filter(Boolean)
}

function enrichReportRow(report) {
  const envNames = resolveEnvNamesForCases(report?.case_id != null ? [report.case_id] : [])
  return {
    ...report,
    env_display: envNames.length ? envNames.join('、') : '-',
  }
}

/**
 * 将同一脚本下的多次报告标注轮次 / 数据源。
 * 执行顺序与 batch_execute_cases 一致：外层 execute_count，内层 dataset。
 */
function annotateRunsForCase(reports, caseId) {
  const sorted = [...(reports || [])].sort((a, b) =>
    String(a.case_st_time || '').localeCompare(String(b.case_st_time || '')),
  )
  const caseCfg = getCaseCfg(caseId)
  const cfgDatasets = Array.isArray(caseCfg.selected_dataset_names)
    ? caseCfg.selected_dataset_names.map((x) => String(x).trim()).filter(Boolean)
    : []
  const cfgExecCount = Math.max(1, Number(caseCfg.execute_count) || 1)

  return sorted.map((r, index) => {
    let datasetName = r.dataset_name != null && String(r.dataset_name).trim()
      ? String(r.dataset_name).trim()
      : null
    // 历史报告无 dataset_name 时，按配置顺序推断（与执行循环一致）
    if (!datasetName && cfgDatasets.length) {
      datasetName = cfgDatasets[index % cfgDatasets.length] || null
    }
    const dsCount = cfgDatasets.length || (datasetName ? 1 : 0)
    let roundNo = index + 1
    if (dsCount > 0) {
      roundNo = Math.floor(index / dsCount) + 1
    }
    return {
      ...enrichReportRow(r),
      run_index: index + 1,
      round_no: roundNo,
      round_label: `第 ${roundNo} 次`,
      dataset_name: datasetName || null,
      dataset_display: datasetName || '未使用数据源',
      _cfg_execute_count: cfgExecCount,
      _cfg_dataset_count: cfgDatasets.length,
    }
  })
}

/** 左侧抽屉：按脚本分组 */
function buildScriptGroups(reports) {
  const map = new Map()
  for (const r of reports || []) {
    const caseId = r.case_id
    const key = caseId != null ? String(caseId) : `unknown:${r.report_code || r.id}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }

  const groups = []
  for (const [key, list] of map) {
    const caseId = list[0]?.case_id
    const runs = annotateRunsForCase(list, caseId)
    const passCount = runs.filter((r) => isCaseSuccess(r.case_state)).length
    const failCount = runs.length - passCount
    const caseCfg = getCaseCfg(caseId)
    const cfgDatasets = Array.isArray(caseCfg.selected_dataset_names)
      ? caseCfg.selected_dataset_names.map((x) => String(x).trim()).filter(Boolean)
      : []
    const cfgExecCount = Math.max(1, Number(caseCfg.execute_count) || 1)
    const envNames = resolveEnvNamesForCases(caseId != null ? [caseId] : [])
    const usedDatasets = [...new Set(runs.map((r) => r.dataset_name).filter(Boolean))]

    let planLabel = `配置执行 ${cfgExecCount} 次`
    if (cfgDatasets.length) {
      planLabel = `配置 ${cfgExecCount} 次 × ${cfgDatasets.length} 个数据源`
    }

    groups.push({
      _key: key,
      case_id: caseId,
      case_name: list[0]?.case_name || `用例${caseId ?? '-'}`,
      env_display: envNames.length ? envNames.join('、') : '-',
      plan_label: planLabel,
      cfg_execute_count: cfgExecCount,
      cfg_dataset_names: cfgDatasets,
      used_datasets: usedDatasets,
      run_count: runs.length,
      pass_count: passCount,
      fail_count: failCount,
      all_ok: failCount === 0 && runs.length > 0,
      pass_rate: runs.length ? (passCount / runs.length) * 100 : null,
      runs,
    })
  }

  // 按首次执行时间排序，贴近任务内脚本顺序
  groups.sort((a, b) => {
    const ta = a.runs[0]?.case_st_time || ''
    const tb = b.runs[0]?.case_st_time || ''
    return String(ta).localeCompare(String(tb))
  })
  return groups
}

function buildBatchRows(reports) {
  const map = new Map()
  for (const r of reports || []) {
    const bc = r.batch_code != null ? String(r.batch_code).trim() : ''
    const key = bc || `single:${r.report_code || r.report_id || r.id}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(r)
  }

  const rows = []
  for (const [key, list] of map) {
    const enriched = list.map(enrichReportRow)
    const passCount = enriched.filter((r) => isCaseSuccess(r.case_state)).length
    const total = enriched.length
    const allOk = total > 0 && passCount === total
    const passRate = total > 0 ? (passCount / total) * 100 : null
    const elapsedSum = enriched.reduce((acc, r) => acc + parseElapsedSeconds(r.case_elapsed), 0)
    const times = enriched.map((r) => r.case_st_time).filter(Boolean).sort()
    const users = [...new Set(enriched.map((r) => r.created_user).filter(Boolean))]
    const batchCode = key.startsWith('single:') ? null : key

    rows.push({
      _key: key,
      batch_code: batchCode,
      task_name: historyTaskName.value || '-',
      execute_result: allOk,
      pass_rate: passRate,
      created_user: users[0] || '-',
      execute_time: times.length ? times[0] : '-',
      elapsed_display: formatElapsed(elapsedSum),
      report_count: total,
      reports: enriched,
    })
  }

  rows.sort((a, b) => String(b.execute_time || '').localeCompare(String(a.execute_time || '')))
  return rows
}

async function fetchAllReportsByTaskCode(taskCode) {
  if (!taskCode) return []
  const pageSize = 200
  let page = 1
  let total = Infinity
  const collected = []
  while (collected.length < total) {
    const res = await api.getApiReportList({
      task_code: taskCode,
      page,
      page_size: pageSize,
      order: ['-case_st_time'],
    })
    const chunk = Array.isArray(res?.data) ? res.data : []
    total = Number(res?.total) || chunk.length
    collected.push(...chunk)
    if (!chunk.length || chunk.length < pageSize) break
    page += 1
    if (page > 50) break
  }
  return collected.filter((r) => String(r.task_code || '').trim() === String(taskCode).trim())
}

async function loadHistory() {
  const code = historyTaskCode.value
  if (!code) {
    batchRows.value = []
    pagination.itemCount = 0
    return
  }
  loading.value = true
  try {
    const reports = await fetchAllReportsByTaskCode(code)
    batchRows.value = buildBatchRows(reports)
    pagination.itemCount = batchRows.value.length
    pagination.page = 1
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行历史失败')
    batchRows.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      scriptDrawerVisible.value = false
      detailDrawerVisible.value = false
      detailReportRow.value = null
      loadHistory()
    } else {
      scriptDrawerVisible.value = false
      detailDrawerVisible.value = false
      detailReportRow.value = null
    }
  },
)

function onPageChange(page) {
  pagination.page = page
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
}

function openScriptDrawer(batchRow) {
  const groups = buildScriptGroups(batchRow?.reports || [])
  scriptGroups.value = groups
  // 默认全部展开，便于一眼看清
  expandedScriptNames.value = groups.map((g) => g._key)
  const timeLabel = batchRow?.execute_time && batchRow.execute_time !== '-' ? batchRow.execute_time : ''
  scriptDrawerTitle.value = timeLabel ? `脚本执行信息（${timeLabel}）` : '脚本执行信息'
  scriptDrawerVisible.value = true
  detailDrawerVisible.value = false
  detailReportRow.value = null
}

function openDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  detailDrawerVisible.value = true
}

function renderPassRateBar(ratioNum) {
  if (ratioNum == null || !Number.isFinite(ratioNum)) return h('span', '-')
  const passRatio = Math.max(0, Math.min(100, ratioNum))
  const failRatio = 100 - passRatio
  const ratioStr = passRatio.toFixed(2)
  const children = []
  if (passRatio > 0) {
    children.push(
      h('div', {
        style: {
          height: '100%',
          width: `${passRatio}%`,
          backgroundColor: '#18a058',
          transition: 'width 0.3s ease',
          minWidth: '1px',
        },
      }),
    )
  }
  if (failRatio > 0) {
    children.push(
      h('div', {
        style: {
          height: '100%',
          width: `${failRatio}%`,
          backgroundColor: '#F4511E',
          transition: 'width 0.3s ease',
          minWidth: '1px',
        },
      }),
    )
  }
  return h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', width: '100%' } }, [
    h(
      'div',
      {
        style: {
          flex: 1,
          maxWidth: '100px',
          height: '8px',
          borderRadius: '10px',
          overflow: 'hidden',
          backgroundColor: '#F4511E',
        },
      },
      children,
    ),
    h(
      'span',
      { style: { fontSize: 'var(--autotest-font-size-large)', whiteSpace: 'nowrap', minWidth: '60px' } },
      `${ratioStr}%`,
    ),
  ])
}

function makeRunColumns() {
  return [
    {
      title: '序号',
      key: 'run_index',
      width: 56,
      align: 'center',
    },
    {
      title: '执行轮次',
      key: 'round_label',
      width: 90,
      align: 'center',
      render(row) {
        return h(NTag, { size: 'small', type: 'info', bordered: false }, { default: () => row.round_label })
      },
    },
    {
      title: '数据源',
      key: 'dataset_display',
      width: 140,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        if (!row.dataset_name) {
          return h('span', { style: { color: 'var(--n-text-color-3)' } }, '未使用数据源')
        }
        return h(NTag, { size: 'small', type: 'warning', bordered: false }, { default: () => row.dataset_name })
      },
    },
    { title: '报告类型', key: 'report_type', width: 100, align: 'center', ellipsis: { tooltip: true } },
    {
      title: '执行结果',
      key: 'case_state',
      width: 90,
      align: 'center',
      render(row) {
        if (isCaseSuccess(row.case_state)) {
          return h(NTag, { type: 'success', size: 'small', round: true }, { default: () => '成功' })
        }
        if (row.case_state === false || row.case_state === 'false') {
          return h(NTag, { type: 'error', size: 'small', round: true }, { default: () => '失败' })
        }
        return h('span', '-')
      },
    },
    {
      title: '通过率',
      key: 'step_pass_ratio',
      width: 160,
      align: 'center',
      render(row) {
        const ratio = row.step_pass_ratio
        if (ratio === null || ratio === undefined) return h('span', '-')
        const ratioNum = typeof ratio === 'number' ? ratio : parseFloat(ratio)
        if (Number.isNaN(ratioNum)) return h('span', '-')
        return renderPassRateBar(ratioNum)
      },
    },
    {
      title: '涉及环境',
      key: 'env_display',
      width: 120,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '执行人员',
      key: 'created_user',
      width: 90,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '执行耗时',
      key: 'case_elapsed',
      width: 90,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      align: 'center',
      fixed: 'right',
      render(row) {
        return h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            onClick: () => openDetailDrawer(row),
          },
          {
            default: () => '查看',
            icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
          },
        )
      },
    },
  ]
}

const runColumns = makeRunColumns()

const batchColumns = computed(() => [
  {
    title: '序号',
    key: '_index',
    width: 64,
    align: 'center',
    render: (_, index) => (pagination.page - 1) * pagination.pageSize + index + 1,
  },
  {
    title: '任务名称',
    key: 'task_name',
    minWidth: 160,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行结果',
    key: 'execute_result',
    width: 100,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.execute_result ? 'success' : 'error', size: 'small', round: true },
        { default: () => (row.execute_result ? '成功' : '失败') },
      )
    },
  },
  {
    title: '通过率',
    key: 'pass_rate',
    width: 180,
    align: 'center',
    render(row) {
      return renderPassRateBar(row.pass_rate == null ? null : Number(row.pass_rate))
    },
  },
  {
    title: '执行人员',
    key: 'created_user',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行时间',
    key: 'execute_time',
    width: 170,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行耗时',
    key: 'elapsed_display',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          onClick: () => openScriptDrawer(row),
        },
        {
          default: () => '查看',
          icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
        },
      )
    },
  },
])

const modalStyle = {
  width: '80%',
  marginLeft: '10%',
  marginRight: '10%',
  marginTop: '5vh',
  marginBottom: '5vh',
  boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
  borderRadius: '8px',
}
</script>

<template>
  <NModal
    v-model:show="modalVisible"
    :title="historyTaskName ? `执行历史（${historyTaskName}）` : '执行历史'"
    preset="card"
    class="task-history-modal"
    :style="modalStyle"
    @close="modalVisible = false"
  >
    <NSpin :show="loading">
      <div v-if="pagedBatchRows.length" class="history-table-wrap">
        <NDataTable
          :columns="batchColumns"
          :data="pagedBatchRows"
          :row-key="(row) => row._key"
          :scroll-x="1000"
          :single-line="true"
          size="small"
        />
      </div>
      <div v-else class="history-empty">暂无任务执行历史</div>
      <div v-if="pagination.itemCount > 0" class="history-pagination">
        <NPagination
          v-model:page="pagination.page"
          :page-count="Math.max(1, Math.ceil(pagination.itemCount / pagination.pageSize))"
          :page-size="pagination.pageSize"
          :page-sizes="pagination.pageSizes"
          show-size-picker
          :prefix="pagination.prefix"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
        />
      </div>
    </NSpin>
  </NModal>

  <NDrawer v-model:show="scriptDrawerVisible" placement="left" width="60%" :trap-focus="false">
    <NDrawerContent :title="scriptDrawerTitle" closable :native-scrollbar="false">
      <div v-if="scriptGroups.length" class="script-drawer-body">
        <NCollapse v-model:expanded-names="expandedScriptNames" display-directive="show">
          <NCollapseItem
            v-for="(group, gIndex) in scriptGroups"
            :key="group._key"
            :name="group._key"
          >
            <template #header>
              <div class="script-group-header">
                <div class="script-group-title">
                  <span class="script-index">{{ gIndex + 1 }}</span>
                  <span class="script-name" :title="group.case_name">{{ group.case_name }}</span>
                  <NTag size="tiny" :bordered="false">ID {{ group.case_id ?? '-' }}</NTag>
                </div>
                <div class="script-group-meta" @click.stop>
                  <NTag
                    size="small"
                    round
                    :type="group.all_ok ? 'success' : 'error'"
                  >
                    {{ group.all_ok ? '全部成功' : '存在失败' }}
                  </NTag>
                  <span class="meta-text">{{ group.pass_count }}/{{ group.run_count }} 通过</span>
                  <span class="meta-text">{{ group.plan_label }}</span>
                  <span class="meta-text" v-if="group.env_display && group.env_display !== '-'">
                    环境：{{ group.env_display }}
                  </span>
                </div>
              </div>
            </template>
            <NCard size="small" :bordered="false" class="script-run-card">
              <div v-if="group.cfg_dataset_names.length" class="dataset-plan">
                <span class="dataset-plan-label">配置数据源：</span>
                <NSpace :size="6" wrap>
                  <NTag
                    v-for="ds in group.cfg_dataset_names"
                    :key="ds"
                    size="small"
                    type="warning"
                    :bordered="false"
                  >
                    {{ ds }}
                  </NTag>
                </NSpace>
              </div>
              <NDataTable
                :columns="runColumns"
                :data="group.runs"
                :row-key="(r) => r.report_code ?? r.report_id ?? r.id"
                :scroll-x="1200"
                :single-line="true"
                size="small"
              />
            </NCard>
          </NCollapseItem>
        </NCollapse>
      </div>
      <div v-else class="history-empty">该次执行暂无脚本报告</div>
    </NDrawerContent>
  </NDrawer>

  <ReportDetailDrawer
    v-model:show="detailDrawerVisible"
    :report-row="detailReportRow"
    title="报告明细"
  />
</template>

<style scoped>
.history-table-wrap {
  overflow-x: auto;
  max-height: calc(100vh - 280px);
  margin-bottom: 16px;
}
.history-empty {
  color: var(--n-text-color-3);
  text-align: center;
  padding: 24px;
}
.history-pagination {
  display: flex;
  justify-content: flex-end;
}

.script-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.script-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding-right: 8px;
  min-width: 0;
}
.script-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.script-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--n-primary-color, #18a058);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.script-name {
  font-weight: 600;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.script-group-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
  max-width: 58%;
}
.meta-text {
  font-size: 12px;
  color: var(--n-text-color-3);
  white-space: nowrap;
}
.script-run-card {
  background: transparent;
}
.dataset-plan {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.dataset-plan-label {
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 22px;
  flex-shrink: 0;
}
</style>

<style>
.task-history-modal .n-card,
.task-history-modal .n-modal-body-wrapper {
  width: 80% !important;
  margin-left: 10% !important;
  margin-right: 10% !important;
  margin-top: 5vh !important;
  margin-bottom: 5vh !important;
  max-width: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
}
.task-history-modal .n-card__content {
  padding: 20px;
}
</style>
