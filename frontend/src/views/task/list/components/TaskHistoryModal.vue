<script setup>
/**
 * 任务执行历史（三层下钻）：
 * 1) 弹窗：POST /report/search_task_batches 按批次分页（批次行不内嵌报告明细）
 * 2) 左侧抽屉"脚本执行信息"：POST /report/search_batch_scripts 按脚本维度分页
 * 3) 左侧抽屉"脚本执行明细"：轮次元数据直接取自脚本行(rounds)渲染折叠菜单，
 *    展开轮次/翻页时 POST /report/search_script_round_reports 按 (batch_code, case_id, round_no, page, page_size) 服务端分页请求，行内"查看"打开 ReportDetailDrawer 步骤明细
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
  /** 任务行：需含 task_name / task_code */
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
const currentBatch = ref(null)
const scriptLoading = ref(false)
const scriptRows = ref([])
const scriptPagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
})

const detailDrawerVisible = ref(false)
const currentScript = ref(null)
const rounds = ref([])
const expandedRoundNames = ref([])
const detailReportRow = ref(null)
const reportDetailVisible = ref(false)

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
      type: BATCH_RESULT_TAG_TYPE[row.task_exec_status] || 'error',
      size: 'small',
      round: true,
    },
    { default: () => row.task_exec_status || '失败' },
  )
}

function renderScriptResultTag(row) {
  if (!row.case_execute_count) return h('span', '-')
  const allOk = row.case_exec_passed === row.case_execute_count
  const allFail = row.case_exec_passed === 0
  const label = allOk ? '全部成功' : allFail ? '全部失败' : '存在失败'
  const type = allOk ? 'success' : allFail ? 'error' : 'warning'
  return h(NTag, { type, size: 'small', round: true }, { default: () => label })
}

function renderCaseStateTag(state) {
  if (isCaseSuccess(state)) {
    return h(NTag, { type: 'success', size: 'small', round: true }, { default: () => '成功' })
  }
  if (state === false || state === 'false') {
    return h(NTag, { type: 'error', size: 'small', round: true }, { default: () => '失败' })
  }
  return h('span', '-')
}

function formatElapsed(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '-'
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const m = Math.floor(seconds / 60)
  const sec = seconds - m * 60
  return `${m}m${sec.toFixed(1)}s`
}

function joinEnvs(envs) {
  return Array.isArray(envs) && envs.length ? envs.join('、') : '-'
}

function resolveCaseName(row) {
  return row.case_name || `用例${row.case_id ?? '-'}`
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
    })
    const list = Array.isArray(res?.data) ? res.data : []
    batchRows.value = list.map((b, idx) => ({
      _key: b.batch_code || `single:${idx}`,
      batch_code: b.batch_code || null,
      task_name: historyTaskName.value || '-',
      task_exec_status: b.task_exec_status,
      task_bind_script: Number(b.task_bind_script) || 0,
      task_exec_passed: Number(b.task_exec_passed) || 0,
      task_exec_failed: Number(b.task_exec_failed) || 0,
      task_pass_rate: b.task_pass_rate,
      env_display: joinEnvs(b.involve_envs),
      task_st_time: b.task_st_time || '-',
      task_ed_time: b.task_ed_time || '-',
      elapsed_display: formatElapsed(Number(b.task_elapsed) || 0),
      created_user: b.created_user || '-',
    }))
    pagination.itemCount = Number(res?.total) || 0
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行历史失败')
    batchRows.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

async function loadScriptRows() {
  const batchCode = currentBatch.value?.batch_code
  if (!batchCode) {
    scriptRows.value = []
    scriptPagination.itemCount = 0
    return
  }
  scriptLoading.value = true
  try {
    const res = await api.getApiReportBatchScripts({
      batch_code: batchCode,
      page: scriptPagination.page,
      page_size: scriptPagination.pageSize,
    })
    scriptRows.value = Array.isArray(res?.data) ? res.data : []
    scriptPagination.itemCount = Number(res?.total) || 0
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载脚本执行信息失败')
    scriptRows.value = []
    scriptPagination.itemCount = 0
  } finally {
    scriptLoading.value = false
  }
}

/** 轮次内场景行分页：展开轮次/翻页时由服务端按轮次分页返回 */
const ROUND_PAGE_SIZE = 10
const ROUND_PAGE_SIZES = [10, 20, 50, 100]

/**
 * 打开脚本执行明细抽屉：轮次元数据直接取自脚本行(含rounds)，无需额外请求；轮次内场景行在展开轮次/翻页时按需请求。
 */
function openScriptDetailDrawer(scriptRow) {
  currentScript.value = scriptRow
  const metas = Array.isArray(scriptRow?.rounds) ? scriptRow.rounds : []
  rounds.value = metas.map((m) => ({
    _key: `round-${m.round_no}`,
    round_no: m.round_no,
    round_label: `第 ${m.round_no} 次执行`,
    dataset_names: Array.isArray(m.dataset_names) ? m.dataset_names : [],
    // 轮次内报告总数由 /search_script_round_reports 首次加载时按服务端total回填
    row_count: 0,
    page: 1,
    pageSize: ROUND_PAGE_SIZE,
    rows: [],
    loaded: false,
    loading: false,
  }))
  expandedRoundNames.value = []
  detailDrawerVisible.value = true
}

async function loadRoundRows(round) {
  round.loading = true
  try {
    const res = await api.getApiReportScriptReports({
      batch_code: currentBatch.value?.batch_code,
      case_id: currentScript.value?.case_id,
      round_no: round.round_no,
      page: round.page,
      page_size: round.pageSize,
    })
    round.rows = Array.isArray(res?.data) ? res.data : []
    round.row_count = Number(res?.total) || 0
    round.loaded = true
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载轮次执行明细失败')
    round.rows = []
  } finally {
    round.loading = false
  }
}

/** 折叠菜单展开时懒加载对应轮次的首页数据 */
watch(expandedRoundNames, (names) => {
  for (const name of names) {
    const round = rounds.value.find((r) => r._key === name)
    if (round && !round.loaded && !round.loading) loadRoundRows(round)
  }
})

function onRoundPageChange(round, page) {
  round.page = page
  loadRoundRows(round)
}

function onRoundPageSizeChange(round, pageSize) {
  round.pageSize = pageSize
  round.page = 1
  loadRoundRows(round)
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      scriptDrawerVisible.value = false
      detailDrawerVisible.value = false
      currentBatch.value = null
      currentScript.value = null
      pagination.page = 1
      loadHistory()
    } else {
      scriptDrawerVisible.value = false
      detailDrawerVisible.value = false
      currentBatch.value = null
      currentScript.value = null
    }
  },
)

watch(scriptDrawerVisible, (v) => {
  if (!v) {
    detailDrawerVisible.value = false
    currentScript.value = null
  }
})

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
  if (!batchRow?.batch_code) {
    window.$message?.warning?.('该批次记录缺少批次标识，无法下钻查看脚本执行信息')
    return
  }
  currentBatch.value = batchRow
  scriptPagination.page = 1
  scriptDrawerVisible.value = true
  detailDrawerVisible.value = false
  currentScript.value = null
  loadScriptRows()
}

function onScriptPageChange(page) {
  scriptPagination.page = page
  loadScriptRows()
}

function onScriptPageSizeChange(pageSize) {
  scriptPagination.pageSize = pageSize
  scriptPagination.page = 1
  loadScriptRows()
}

function openReportDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  reportDetailVisible.value = true
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
    key: 'task_exec_status',
    width: 110,
    align: 'center',
    render(row) {
      return renderBatchResultTag(row)
    },
  },
  {
    title: '用例数量',
    key: 'task_bind_script',
    width: 90,
    align: 'center',
  },
  {
    title: '成功数量',
    key: 'task_exec_passed',
    width: 90,
    align: 'center',
  },
  {
    title: '失败数量',
    key: 'task_exec_failed',
    width: 90,
    align: 'center',
  },
  {
    title: '通过率',
    key: 'task_pass_rate',
    width: 180,
    align: 'center',
    render(row) {
      return renderPassRateBar(row.task_pass_rate == null ? null : Number(row.task_pass_rate))
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
    title: '执行时间',
    key: 'task_st_time',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '结束时间',
    key: 'task_ed_time',
    width: 200,
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
    title: '执行人员',
    key: 'created_user',
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

const scriptColumns = [
  {
    title: '用例ID',
    key: 'case_id',
    width: 80,
    align: 'center',
  },
  {
    title: '用例名称',
    key: 'case_name',
    minWidth: 180,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return resolveCaseName(row)
    },
  },
  {
    title: '执行结果',
    key: 'result',
    width: 100,
    align: 'center',
    render(row) {
      return renderScriptResultTag(row)
    },
  },
  {
    title: '执行次数',
    key: 'case_execute_count',
    width: 110,
    align: 'center',
  },
  {
    title: '通过率',
    key: 'case_pass_rate',
    width: 180,
    align: 'center',
    render(row) {
      return renderPassRateBar(row.case_pass_rate == null ? null : Number(row.case_pass_rate))
    },
  },
  {
    title: '涉及环境',
    key: 'env_display',
    width: 120,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return joinEnvs(row.involve_envs)
    },
  },
  {
    title: '执行人员',
    key: 'created_user',
    width: 90,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行时间',
    key: 'case_st_time',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '结束时间',
    key: 'case_ed_time',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行耗时',
    key: 'elapsed_display',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return formatElapsed(Number(row.case_elapsed) || 0)
    },
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
          onClick: () => openScriptDetailDrawer(row),
        },
        {
          default: () => '查看',
          icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
        },
      )
    },
  },
]

const roundDetailColumns = [
  {
    title: '序号',
    key: 'dataset_no',
    width: 56,
    align: 'center',
  },
  {
    title: '场景名称',
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
  {
    title: '执行结果',
    key: 'case_state',
    width: 90,
    align: 'center',
    render(row) {
      return renderCaseStateTag(row.case_state)
    },
  },
  {
    title: '步骤数量',
    key: 'step_total',
    width: 90,
    align: 'center',
  },
  {
    title: '成功数量',
    key: 'step_pass_count',
    width: 90,
    align: 'center',
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
    render(row) {
      return joinEnvs(row.involve_envs)
    },
  },
  {
    title: '执行时间',
    key: 'case_st_time',
    width: 200,
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
          onClick: () => openReportDetailDrawer(row),
        },
        {
          default: () => '查看',
          icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
        },
      )
    },
  },
]

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
    :title="'任务执行历史'"
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
          :scroll-x="1600"
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
    <NDrawerContent title="脚本执行列表" closable :native-scrollbar="false">
      <NSpin :show="scriptLoading">
        <div v-if="scriptRows.length" class="script-table-wrap">
          <NDataTable
            :columns="scriptColumns"
            :data="scriptRows"
            :row-key="(row) => row.case_id ?? row.case_name"
            :scroll-x="1400"
            :single-line="true"
            size="small"
          />
        </div>
        <div v-else class="history-empty">该批次暂无脚本报告</div>
        <div v-if="scriptPagination.itemCount > 0" class="history-pagination">
          <NPagination
            v-model:page="scriptPagination.page"
            :page-count="Math.max(1, Math.ceil(scriptPagination.itemCount / scriptPagination.pageSize))"
            :page-size="scriptPagination.pageSize"
            :page-sizes="scriptPagination.pageSizes"
            show-size-picker
            :prefix="scriptPagination.prefix"
            @update:page="onScriptPageChange"
            @update:page-size="onScriptPageSizeChange"
          />
        </div>
      </NSpin>
    </NDrawerContent>
  </NDrawer>

  <NDrawer v-model:show="detailDrawerVisible" placement="left" width="60%" :trap-focus="false">
    <NDrawerContent :title="`脚本执行明细 - ${currentScript ? resolveCaseName(currentScript) : ''}`" closable :native-scrollbar="false">
      <div v-if="rounds.length" class="script-drawer-body">
        <NCollapse v-model:expanded-names="expandedRoundNames" display-directive="show">
          <NCollapseItem
            v-for="round in rounds"
            :key="round._key"
            :name="round._key"
          >
            <template #header>
              <div class="round-header">
                <NTag size="small" type="info" :bordered="false">{{ round.round_label }}</NTag>
                <span class="meta-text">{{ round.dataset_names.length ? `数据源：${round.dataset_names.join('、')}` : '未参数化执行' }}</span>
              </div>
            </template>
            <NCard size="small" :bordered="false" class="script-run-card">
              <NSpin :show="round.loading">
                <NDataTable
                  :columns="roundDetailColumns"
                  :data="round.rows"
                  :row-key="(r) => r.report_code ?? r.report_id"
                  :scroll-x="1400"
                  :single-line="true"
                  size="small"
                />
                <div v-if="round.row_count > 0" class="history-pagination round-pagination">
                  <NPagination
                    :page="round.page"
                    :page-count="Math.max(1, Math.ceil(round.row_count / round.pageSize))"
                    :page-size="round.pageSize"
                    :page-sizes="ROUND_PAGE_SIZES"
                    show-size-picker
                    :prefix="() => `共 ${round.row_count} 条`"
                    @update:page="(page) => onRoundPageChange(round, page)"
                    @update:page-size="(size) => onRoundPageSizeChange(round, size)"
                  />
                </div>
              </NSpin>
            </NCard>
          </NCollapseItem>
        </NCollapse>
      </div>
      <div v-else class="history-empty">该脚本在本批次暂无执行报告</div>
    </NDrawerContent>
  </NDrawer>

  <ReportDetailDrawer
    v-model:show="reportDetailVisible"
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

.script-table-wrap {
  overflow-x: auto;
}
.script-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.round-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta-text {
  font-size: 12px;
  color: var(--n-text-color-3);
  white-space: nowrap;
}
.script-run-card {
  background: transparent;
}
.round-pagination {
  margin-top: 12px;
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
