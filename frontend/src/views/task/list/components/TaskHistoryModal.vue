<script setup>
/**
 * 任务执行历史：
 * 1) 弹窗：POST /report/search_batches 按批次分页，后端给出执行状态
 * 2) 左侧抽屉：本批次按脚本分组（轮次 × 数据源）
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

const scriptDrawerVisible = ref(false)
const scriptGroups = ref([])
const expandedScriptNames = ref([])

const detailDrawerVisible = ref(false)
const detailReportRow = ref(null)

const BATCH_RESULT_TAG_TYPE = {
  成功: 'success',
  部分成功: 'warning',
  失败: 'error',
}

function isCaseSuccess(state) {
  return state === true || state === 'true'
}

function renderBatchResultTag(row) {
  return h(
    NTag,
    {
      type: BATCH_RESULT_TAG_TYPE[row.execute_result] || 'error',
      size: 'small',
      round: true,
    },
    { default: () => row.execute_result || '失败' },
  )
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
  return top && typeof top === 'object' ? top : {}
}

function getCaseCfg(caseId) {
  const cfg = resolveCasesExecuteConfig(props.taskRow)
  const caseCfg = cfg[String(caseId)] || cfg[caseId]
  return caseCfg && typeof caseCfg === 'object' ? caseCfg : {}
}

function resolveEnvDisplay(caseId) {
  const cfg = resolveCasesExecuteConfig(props.taskRow)
  const caseCfg = getCaseCfg(caseId)
  const names = new Set()
  // 新结构：env_name为顶层全局环境；步骤级env_name一并纳入
  if (cfg.env_name) names.add(String(cfg.env_name).trim())
  const steps = caseCfg.steps_execute_config
  if (steps && typeof steps === 'object') {
    for (const stepCfg of Object.values(steps)) {
      if (stepCfg && typeof stepCfg === 'object' && stepCfg.env_name) {
        names.add(String(stepCfg.env_name).trim())
      }
    }
  }
  const list = [...names].filter(Boolean)
  return list.length ? list.join('、') : '-'
}

function enrichReportRow(report) {
  return {
    ...report,
    env_display: resolveEnvDisplay(report?.case_id),
  }
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
    const res = await api.getApiReportBatches({
      task_code: code,
      page: pagination.page,
      page_size: pagination.pageSize,
      include_reports: true,
    })
    const list = Array.isArray(res?.data) ? res.data : []
    batchRows.value = list.map((b, idx) => {
      const reports = (b.reports || []).map(enrichReportRow)
      const first = reports[0]
      return {
        _key: b.batch_code || `single:${first?.report_code || first?.report_id || idx}`,
        task_name: historyTaskName.value || '-',
        execute_result: b.execute_result,
        pass_rate: b.pass_rate,
        created_user: b.created_user || '-',
        execute_time: b.execute_time || '-',
        elapsed_display: formatElapsed(Number(b.elapsed_seconds) || 0),
        reports,
      }
    })
    pagination.itemCount = Number(res?.total) || 0
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行历史失败')
    batchRows.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

/**
 * 将同一脚本下的多次报告标注轮次 / 数据源。
 * 执行顺序与 batch_execute_cases 一致：外层 execute_count，内层 dataset。
 * 数据源为任务级 dataset_enabled 开关，配置中不再存场景名称列表；从报告自身收集去重场景名(保持出现顺序)。
 */
function annotateRunsForCase(reports) {
  const sorted = [...(reports || [])].sort((a, b) =>
    String(a.case_st_time || '').localeCompare(String(b.case_st_time || '')),
  )
  const knownDatasets = []
  const seenDs = new Set()
  sorted.forEach((r) => {
    const name = r.dataset_name != null && String(r.dataset_name).trim()
      ? String(r.dataset_name).trim()
      : null
    if (name && !seenDs.has(name)) {
      seenDs.add(name)
      knownDatasets.push(name)
    }
  })

  return sorted.map((r, index) => {
    let datasetName = r.dataset_name != null && String(r.dataset_name).trim()
      ? String(r.dataset_name).trim()
      : null
    if (!datasetName && knownDatasets.length) {
      datasetName = knownDatasets[index % knownDatasets.length] || null
    }
    const dsCount = knownDatasets.length || (datasetName ? 1 : 0)
    const roundNo = dsCount > 0 ? Math.floor(index / dsCount) + 1 : index + 1
    return {
      ...r,
      run_index: index + 1,
      round_label: `第 ${roundNo} 次`,
      dataset_name: datasetName || null,
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
    const runs = annotateRunsForCase(list)
    const passCount = runs.filter((r) => isCaseSuccess(r.case_state)).length
    const caseCfg = getCaseCfg(caseId)
    const cfgExecCount = Math.max(1, Number(caseCfg.execute_count) || 1)
    // 数据源为任务级 dataset_enabled 开关：场景数量执行时动态纳入，配置中不再存列表
    const planLabel = props.taskRow?.dataset_enabled
      ? `配置 ${cfgExecCount} 次 × 已启用数据源`
      : `配置执行 ${cfgExecCount} 次`

    const allOk = passCount === runs.length && runs.length > 0
    const allFail = passCount === 0 && runs.length > 0
    groups.push({
      _key: key,
      case_id: caseId,
      case_name: list[0]?.case_name || `用例${caseId ?? '-'}`,
      env_display: resolveEnvDisplay(caseId),
      plan_label: planLabel,
      run_count: runs.length,
      pass_count: passCount,
      all_ok: allOk,
      result_label: allOk ? '全部成功' : allFail ? '全部失败' : '存在失败',
      runs,
    })
  }

  groups.sort((a, b) => {
    const ta = a.runs[0]?.case_st_time || ''
    const tb = b.runs[0]?.case_st_time || ''
    return String(ta).localeCompare(String(tb))
  })
  return groups
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      scriptDrawerVisible.value = false
      detailDrawerVisible.value = false
      detailReportRow.value = null
      pagination.page = 1
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
  loadHistory()
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  loadHistory()
}

function openScriptDrawer(batchRow) {
  const groups = buildScriptGroups(batchRow?.reports || [])
  scriptGroups.value = groups
  expandedScriptNames.value = groups.map((g) => g._key)
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
      key: 'dataset_name',
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
    width: 110,
    align: 'center',
    render(row) {
      return renderBatchResultTag(row)
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
    width: 210,
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
    :title="'执行历史'"
    preset="card"
    class="task-history-modal"
    :style="modalStyle"
    @close="modalVisible = false"
  >
    <NSpin :show="loading">
      <div v-if="batchRows.length" class="history-table-wrap">
        <NDataTable
          :columns="batchColumns"
          :data="batchRows"
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
    <NDrawerContent title="脚本执行信息" closable :native-scrollbar="false">
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
                    {{ group.result_label }}
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
