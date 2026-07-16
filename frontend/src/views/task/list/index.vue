<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDatePicker,
  NDropdown,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NSelect,
  NSpace,
  NSwitch,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'
import ExecConfigModal from '@/views/autotest/steps/components/ExecConfigModal.vue'

import {formatDateTime, renderIcon} from '@/utils'
import {getCronNextRunTimes} from '@/utils/common/cron'
import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat'
import { useCRUD } from '@/composables'
import { useUserStore } from '@/store'
import api from '@/api'

dayjs.extend(customParseFormat)
defineOptions({ name: '任务列表' }) // 与菜单名一致，供 KeepAlive include 匹配

const userStore = useUserStore()

const TASK_STATUS_MAP = {
  '等待执行': '等待执行',
  '正在执行': '正在执行',
  '成功': '成功',
  '失败': '失败',
}

const $table = ref(null)
const queryItems = ref({})

/** 列表分页元数据（用于序号列） */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
const onPaginationMeta = (meta) => {
  listPaginationMeta.value = meta
}

/** 任务表多选（与弹窗内用例勾选的 checkedRowKeys 区分） */
const taskTableCheckedRowKeys = ref([])

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'dropdown',
}

async function handleBatchDelete() {
  const ids = taskTableCheckedRowKeys.value || []
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的任务')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 个任务吗？`,
    async confirm() {
      await Promise.all(ids.map((task_id) => api.deleteApiTaskList({ task_id })))
      window.$message?.success?.('删除成功')
      taskTableCheckedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

const { handleDelete } = useCRUD({
  name: '任务',
  doDelete: api.deleteApiTaskList,
  refresh: () => $table.value?.handleSearch(),
})

const projectOptions = ref([])
const projectLoading = ref(false)
const envOptions = ref([])
const envLoading = ref(false)
const tagOptions = ref([])
const tagLoading = ref(false)
const caseListFull = ref([])
const caseLoading = ref(false)
const casePage = ref(1)
const casePageSize = ref(10)
const caseTotal = ref(0)
const filterCaseName = ref('')
const filterCaseProject = ref(null)
const filterCaseTags = ref([])
const filterCreatedUser = ref('')
const checkedRowKeys = ref([])
const casesExecuteConfig = ref({})
const caseNameCache = ref({})
/** false=查看已选用例（开关关闭，默认）；true=查询新用例列表（开关开启，点查询后自动开启） */
const caseQueryNewMode = ref(false)
/** 任务已保存的 case_ids（入库），与表格勾选草稿 checkedRowKeys 区分 */
const persistedCaseIds = ref([])
const selectedCaseRowsCache = ref({})
const execCollapseExpanded = ref([])
const taskModalCollapseExpanded = ref(['cases'])
const cronNextRunTimes = ref([])
const cronNextRunVisible = ref(false)

// 历史（报告）弹框：布局和样式与「日志」一致，按 task_code 请求；内容与测试报告页一致（分组表格 + 分页）
const BATCH_KEY_SEP = '::'
const historyModalVisible = ref(false)
const historyTaskName = ref('')
const historyTaskCode = ref('')
const historyReportList = ref([])
const historyReportLoading = ref(false)
const historyExpandedKeys = ref({})
const historyPagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
})

function hasTaskAndBatch(row) {
  return !!(row.task_code && String(row.task_code).trim() && row.batch_code && String(row.batch_code).trim())
}

const flattenedHistoryData = computed(() => {
  const list = historyReportList.value || []
  const result = []
  const flatReports = list.filter(r => !hasTaskAndBatch(r))
  const groupable = list.filter(hasTaskAndBatch)
  for (const r of flatReports) {
    result.push({ ...r, _isGroup: false })
  }
  const taskCodeMap = new Map()
  for (const r of groupable) {
    const tk = String(r.task_code).trim()
    if (!taskCodeMap.has(tk)) taskCodeMap.set(tk, [])
    taskCodeMap.get(tk).push(r)
  }
  for (const [taskCode, reports] of taskCodeMap) {
    const groupExpanded = historyExpandedKeys.value[taskCode] !== false
    const passCount = reports.filter(r => r.case_state === true || r.case_state === 'true').length
    const failCount = reports.filter(r => r.case_state === false || r.case_state === 'false').length
    result.push({
      _isGroup: true,
      _groupKey: taskCode,
      task_code_display: taskCode,
      report_count: reports.length,
      pass_count: passCount,
      fail_count: failCount,
      expanded: groupExpanded,
    })
    if (!groupExpanded) continue
    const batchMap = new Map()
    for (const r of reports) {
      const bk = String(r.batch_code).trim()
      if (!batchMap.has(bk)) batchMap.set(bk, [])
      batchMap.get(bk).push(r)
    }
    for (const [batchCode, batchReports] of batchMap) {
      const batchKey = 'batch' + BATCH_KEY_SEP + taskCode + BATCH_KEY_SEP + batchCode
      const batchExpanded = historyExpandedKeys.value[batchKey] !== false
      result.push({
        _isBatchGroup: true,
        _batchKey: batchKey,
        _batchCodeDisplay: batchCode,
        report_count: batchReports.length,
        expanded: batchExpanded,
      })
      if (batchExpanded) {
        for (const r of batchReports) result.push({ ...r, _isGroup: false })
      }
    }
  }
  return result
})

function toggleHistoryExpand(groupKey) {
  historyExpandedKeys.value = { ...historyExpandedKeys.value, [groupKey]: historyExpandedKeys.value[groupKey] }
}

function shortenCode(str, head = 10, tail = 6) {
  if (str == null || str === '' || str === '-') return str === '' ? '' : (str ?? '-')
  const s = String(str)
  if (s.length <= head + tail) return s
  return s.slice(0, head) + '…' + s.slice(-tail)
}

function wrapHistoryColumnForGroup(col) {
  const origRender = col.render
  const key = col.key
  return {
    ...col,
    render(row) {
      if (row._isGroup || row._isBatchGroup) return h('span', '-')
      if (origRender) return origRender(row)
      const val = row[key]
      return h('span', { ellipsis: { tooltip: true } }, val != null ? String(val) : '-')
    },
  }
}

const historyGroupLeadColumn = {
  title: '任务代码/批次代码',
  key: '_taskOrBatch',
  width: 250,
  align: 'left',
  render(row) {
    if (row._isGroup) {
      const expandIconVNode = renderIcon(
          row.expanded ? 'material-symbols:expand-less' : 'material-symbols:expand-more',
          { size: 20 }
      )()
      return h(NSpace, { size: 6, align: 'center' }, [
        h(NButton, {
          quaternary: true,
          size: 'tiny',
          style: { width: '24px', minWidth: '24px', padding: 0 },
          onClick: (e) => { e.stopPropagation(); toggleHistoryExpand(row._groupKey) },
        }, { default: () => expandIconVNode }),
        h(NTooltip, { trigger: 'hover' }, {
          trigger: () => h('span', { style: { fontWeight: 600 } }, shortenCode(row.task_code_display)),
          default: () => row.task_code_display,
        }),
        h('span', { style: { color: '#999', fontSize: 'var(--autotest-font-size-mini)' } }, `(共${row.report_count}条)`),
      ])
    }
    if (row._isBatchGroup) {
      const expandIconVNode = renderIcon(
          row.expanded ? 'material-symbols:expand-less' : 'material-symbols:expand-more',
          { size: 18 }
      )()
      return h(NSpace, { size: 6, align: 'center' }, [
        h('span', { style: { width: '28px', display: 'inline-block' } }),
        h(NButton, {
          quaternary: true,
          size: 'tiny',
          style: { width: '22px', minWidth: '22px', padding: 0 },
          onClick: (e) => { e.stopPropagation(); toggleHistoryExpand(row._batchKey) },
        }, { default: () => expandIconVNode }),
        h(NTooltip, { trigger: 'hover' }, {
          trigger: () => h('span', { style: { fontSize: 'var(--autotest-font-size)', fontWeight: 600 } }, shortenCode(row._batchCodeDisplay)),
          default: () => row._batchCodeDisplay,
        }),
        h('span', { style: { color: '#999', fontSize: 'var(--autotest-font-size-mini)' } }, `(共${row.report_count}条)`),
      ])
    }
    const reportBatchCode = row.batch_code ?? '-'
    return h(NTooltip, { trigger: 'hover' }, {
      trigger: () => h('span', { style: { paddingLeft: '56px' } }, shortenCode(reportBatchCode)),
      default: () => (row.batch_code != null && row.batch_code !== '' ? row.batch_code : reportBatchCode),
    })
  },
}

const historyColumnsBase = [
  { title: '报告类型', key: 'report_type', width: 100, align: 'center', ellipsis: { tooltip: true } },
  { title: '用例ID', key: 'case_id', width: 80, align: 'center', ellipsis: { tooltip: true } },
  { title: '用例名称', key: 'case_name', width: 220, align: 'center', ellipsis: { tooltip: true } },
  { title: '成功步骤', key: 'step_pass_count', width: 80, align: 'center', ellipsis: { tooltip: true } },
  { title: '失败步骤', key: 'step_fail_count', width: 80, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '成功率',
    key: 'step_pass_ratio',
    width: 200,
    align: 'center',
    render(row) {
      const ratio = row.step_pass_ratio
      if (ratio === null || ratio === undefined) return h('span', '-')
      const ratioNum = typeof ratio === 'number' ? ratio : parseFloat(ratio)
      if (isNaN(ratioNum)) return h('span', '-')
      const passRatio = Math.max(0, Math.min(100, ratioNum))
      const failRatio = 100 - passRatio
      const ratioStr = passRatio.toFixed(2)
      const progressBarChildren = []
      if (passRatio > 0) progressBarChildren.push(h('div', { style: { height: '100%', width: `${passRatio}%`, backgroundColor: '#18a058', transition: 'width 0.3s ease', minWidth: '1px' } }))
      if (failRatio > 0) progressBarChildren.push(h('div', { style: { height: '100%', width: `${failRatio}%`, backgroundColor: '#F4511E', transition: 'width 0.3s ease', minWidth: '1px' } }))
      return h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', width: '100%' } }, [
        h('div', { style: { flex: 1, maxWidth: '100px', height: '8px', borderRadius: '10px', overflow: 'hidden', backgroundColor: '#F4511E' } }, progressBarChildren),
        h('span', { style: { fontSize: 'var(--autotest-font-size-large)', whiteSpace: 'nowrap', minWidth: '60px' } }, `${ratioStr}%`),
      ])
    },
  },
  { title: '总步骤数', key: 'step_total', width: 80, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '执行状态',
    key: 'case_state',
    width: 80,
    align: 'center',
    render(row) {
      if (row.case_state === true || row.case_state === 'true') return h(NTag, { type: 'success' }, { default: () => '成功' })
      if (row.case_state === false || row.case_state === 'false') return h(NTag, { type: 'error' }, { default: () => '失败' })
      return h('span', '-')
    },
  },
  { title: '执行时间', key: 'case_st_time', width: 200, align: 'center', ellipsis: { tooltip: true } },
  { title: '消耗时间', key: 'case_elapsed', width: 80, align: 'center', ellipsis: { tooltip: true } },
  { title: '创建人员', key: 'created_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render(row) {
      if (row._isGroup || row._isBatchGroup) return h('span', '-')
      return h(NButton, {
        size: 'small',
        type: 'primary',
        onClick: () => handleViewHistoryDetails(row),
      }, { default: () => '查看', icon: renderIcon('material-symbols:visibility-outline', { size: 16 }) })
    },
  },
]

const historyColumns = [historyGroupLeadColumn, ...historyColumnsBase.map(wrapHistoryColumnForGroup)]

function historyRowKey(row) {
  if (row._isGroup) return `group-${row._groupKey}`
  if (row._isBatchGroup) return row._batchKey
  return row.report_code ?? row.report_id ?? row.id
}

// ---------- 历史功能：与测试报告页 frontend/src/views/autotest/report/index.vue 保持一致 ----------
// 1. 主抽屉：执行历史（左侧 80%），按 task_code 请求报告列表，分组展示 + 分页；每行有「查看」。
// 2. 报告明细 + 步骤详情：使用公共组件 ReportDetailDrawer，点击「查看」后打开，组件内部请求步骤列表并支持「详情」「跳转」。

const historyReportDrawerVisible = ref(false)
const historyReportRow = ref(null)

/** 点击历史表格某条报告的「查看」：打开 ReportDetailDrawer，由组件内部根据 reportRow 请求步骤明细并展示（与测试报告页一致） */
const handleViewHistoryDetails = (row) => {
  historyReportRow.value = row
  historyReportDrawerVisible.value = true
}

// 日志（执行记录）弹框：数据来源与任务记录页面一致，按 task_id 请求，弹框大小与新增/编辑任务一致
const logModalVisible = ref(false)
const logTaskName = ref('')
const logTaskId = ref(null)
const logRecordList = ref([])
const logRecordLoading = ref(false)
const logPage = ref(1)
const logPageSize = ref(10)
const logTotal = ref(0)
const logPageSizes = [10, 20, 50, 100]
const logTableScrollX = 2000
const formatJsonBrief = (val, maxLen = 50) => {
  if (val == null) return '-'
  if (typeof val === 'string') {
    try {
      const o = JSON.parse(val)
      const s = JSON.stringify(o)
      return s.length > maxLen ? s.slice(0, maxLen) + '...' : s
    } catch {
      return val.length > maxLen ? val.slice(0, maxLen) + '...' : val
    }
  }
  const s = JSON.stringify(val)
  return s.length > maxLen ? s.slice(0, maxLen) + '...' : s
}
const logRecordColumns = [
  { title: '记录ID', key: 'record_id', width: 80, align: 'center', ellipsis: { tooltip: true }, render: (row) => h('span', row.record_id ?? row.id ?? '-') },
  { title: '任务ID', key: 'task_id', width: 100, align: 'center', ellipsis: { tooltip: true } },
  { title: '任务名称', key: 'task_name', width: 180, ellipsis: { tooltip: true } },
  { title: '任务节点', key: 'celery_node', width: 180, ellipsis: { tooltip: true }, render: (row) => h('span', { title: row.celery_node || '' }, row.celery_node ?? '-') },
  { title: '任务参数', key: 'task_kwargs', width: 200, ellipsis: { tooltip: true }, render: (row) => h('span', { title: JSON.stringify(row.task_kwargs) }, formatJsonBrief(row.task_kwargs, 40)) },
  { title: '调度方式', key: 'celery_scheduler', width: 100, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '调度状态',
    key: 'celery_status',
    width: 100,
    align: 'center',
    render: (row) => {
      const typeMap = { '等待执行': 'default', '正在执行': 'warning', '成功': 'success', '失败': 'error' }
      return h(NTag, { type: typeMap[row.celery_status] || 'default', size: 'small', round: true }, () => row.celery_status || '-')
    }
  },
  { title: '执行摘要', key: 'task_summary', width: 220, ellipsis: { tooltip: true }, render: (row) => (row.task_summary ? (row.task_summary.length > 50 ? row.task_summary.slice(0, 50) + '...' : row.task_summary) : '-') },
  { title: '错误信息', key: 'task_error', width: 220, ellipsis: { tooltip: true }, render: (row) => (row.task_error ? (row.task_error.length > 50 ? row.task_error.slice(0, 50) + '...' : row.task_error) : '-') },
  { title: '调度ID', key: 'celery_id', width: 200, ellipsis: { tooltip: true } },
  { title: '回溯ID', key: 'celery_trace_id', width: 200, ellipsis: { tooltip: true } },
  { title: '开始时间', key: 'celery_start_time', width: 170, align: 'center', render: (row) => h('span', formatDateTime(row.celery_start_time) || '-') },
  { title: '结束时间', key: 'celery_end_time', width: 170, align: 'center', render: (row) => h('span', formatDateTime(row.celery_end_time) || '-') },
  { title: '耗时', key: 'celery_duration', width: 80, align: 'center', ellipsis: { tooltip: true } },
]

const loadHistoryReports = async () => {
  const code = historyTaskCode.value
  if (!code) return
  historyReportLoading.value = true
  try {
    const res = await api.getApiReportList({
      task_code: code,
      page: historyPagination.page,
      page_size: historyPagination.pageSize,
      order: ['-case_st_time'],
    })
    historyReportList.value = res?.data ?? []
    historyPagination.itemCount = res?.total ?? 0
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载报告失败')
    historyReportList.value = []
    historyPagination.itemCount = 0
  } finally {
    historyReportLoading.value = false
  }
}

const openHistory = async (row) => {
  historyTaskName.value = row.task_name ?? ''
  historyTaskCode.value = row.task_code ?? ''
  historyExpandedKeys.value = {}
  historyPagination.page = 1
  historyModalVisible.value = true
  await loadHistoryReports()
}

const onHistoryPageChange = (page) => {
  historyPagination.page = page
  loadHistoryReports()
}

const onHistoryPageSizeChange = (pageSize) => {
  historyPagination.pageSize = pageSize
  historyPagination.page = 1
  loadHistoryReports()
}

const loadLogRecords = async () => {
  const id = logTaskId.value
  if (id == null) return
  logRecordLoading.value = true
  try {
    const res = await api.getApiTaskRecordList({
      task_id: id,
      page: logPage.value,
      page_size: logPageSize.value,
      order: ['-celery_start_time', '-id']
    })
    logRecordList.value = res?.data ?? []
    logTotal.value = res?.total ?? 0
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行记录失败')
  } finally {
    logRecordLoading.value = false
  }
}

const openLog = async (row) => {
  logTaskName.value = row.task_name ?? ''
  logTaskId.value = row.task_id
  logPage.value = 1
  logModalVisible.value = true
  await loadLogRecords()
}

const onLogPageChange = (page) => {
  logPage.value = page
  loadLogRecords()
}

const onLogPageSizeChange = (pageSize) => {
  logPageSize.value = pageSize
  logPage.value = 1
  loadLogRecords()
}

// 新增/编辑弹窗：卡片居中，左右各 15% 留白
const taskModalStyle = {
  width: '80%',
  marginLeft: '10%',
  marginRight: '10%',
  marginTop: '5vh',
  marginBottom: '5vh',
  boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
  borderRadius: '8px'
}
const modalVisible = ref(false)
const modalLoading = ref(false)
const isEdit = ref(false)
const schedulerTab = ref('cron')
const intervalUnit = ref('hours')
const intervalValue = ref(1)
const datetimePickerValue = ref(null)
const INTERVAL_UNITS = [
  {label: 'days', value: 'days'},
  {label: 'hours', value: 'hours'},
  {label: 'minutes', value: 'minutes'},
  {label: 'seconds', value: 'seconds'},
]
const taskForm = ref({
  task_id: null,
  task_code: null,
  task_name: '',
  task_desc: '',
  task_type: '',
  task_project: null,
  task_notify: null,
  task_notifier: [],
  task_kwargs: {},
  task_scheduler: 'cron',
  task_interval_expr: null,
  task_datetime_expr: '',
  task_crontabs_expr: '',
})

watch(() => filterCaseProject.value, (projectId) => {
  if (projectId == null) {
    tagOptions.value = []
    return
  }
  loadTags(projectId)
}, { immediate: false })

const selectedCaseIds = computed(() =>
    (checkedRowKeys.value || [])
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id) && id > 0),
)

watch(selectedCaseIds, (ids, prev) => {
  const prevSet = new Set(prev || [])
  const nextSet = new Set(ids || [])
  const cfg = { ...casesExecuteConfig.value }
  for (const id of prevSet) {
    if (!nextSet.has(id)) delete cfg[String(id)]
  }
  casesExecuteConfig.value = cfg
  execCollapseExpanded.value = ids.map((id) => String(id))
})

const onCaseExecConfigUpdate = (caseId, cfg) => {
  if (caseId == null) return
  casesExecuteConfig.value = {
    ...casesExecuteConfig.value,
    [String(caseId)]: cfg,
  }
}

const tagOptionsForFilter = computed(() =>
    tagOptions.value.map(t => ({label: t.tag_name ?? t.tag_id, value: t.tag_id}))
)

const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getProjectList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      projectOptions.value = res.data.map(item => ({
        label: item.project_name,
        value: item.project_id
      }))
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  } finally {
    projectLoading.value = false
  }
}

/** 执行环境下拉：无应用时全量环境；有应用时仅该应用下已配置的环境（去重） */
const loadEnvOptions = async (projectId = null) => {
  try {
    envLoading.value = true
    const allRes = await api.getEnvList({ page: 1, page_size: 9999, state: 0 })
    const allEnvs = Array.isArray(allRes?.data) ? allRes.data : []
    let list = allEnvs
    if (projectId != null) {
      const cfgRes = await api.searchEnvConfig({
        page: 1,
        page_size: 9999,
        state: 0,
        project_id: projectId,
      })
      const envIdSet = new Set(
          (Array.isArray(cfgRes?.data) ? cfgRes.data : [])
              .map((row) => Number(row.env_id))
              .filter((id) => Number.isFinite(id) && id > 0)
      )
      list = allEnvs.filter((row) => envIdSet.has(Number(row.env_id)))
    }
    envOptions.value = list.map((item) => ({
      label: item.env_name,
      value: item.env_id,
    }))
    // 当前选中环境不在新选项中时清空
    const cur = queryItems.value.env_id
    if (cur != null && !envOptions.value.some((o) => o.value === cur)) {
      queryItems.value.env_id = null
    }
  } catch (error) {
    console.error('加载环境列表失败:', error)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

// 执行时间范围（按 last_execute_time 筛选）
const dateRange = ref(null)
const formatDateForQuery = (ts) => {
  if (ts == null) return null
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const handleDateRangeChange = (value) => {
  if (value == null) {
    queryItems.value.date_from = null
    queryItems.value.date_to = null
  } else {
    queryItems.value.date_from = formatDateForQuery(value[0])
    queryItems.value.date_to = formatDateForQuery(value[1])
  }
}

watch(
    () => queryItems.value.task_project,
    (projectId) => {
      loadEnvOptions(projectId ?? null)
    }
)

watch(
    () => [queryItems.value.date_from, queryItems.value.date_to],
    ([from, to]) => {
      if (from == null && to == null) dateRange.value = null
    }
)

const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getTagList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      tagOptions.value = projectId != null
          ? res.data.filter(tag => tag.tag_project === projectId)
          : res.data
    } else {
      tagOptions.value = []
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

const loadCases = async () => {
  const projectId = filterCaseProject.value
  if (projectId == null) {
    caseListFull.value = []
    caseTotal.value = 0
    return
  }
  try {
    caseLoading.value = true
    const res = await api.getApiTestcaseList({
      page: casePage.value,
      page_size: casePageSize.value,
      state: 0,
      case_project: projectId,
      case_type: '用户脚本',
      case_name: filterCaseName.value || undefined,
      case_tags: filterCaseTags.value?.length ? filterCaseTags.value : undefined,
      created_user: filterCreatedUser.value?.trim() || undefined,
    })
    if (res?.data) {
      caseListFull.value = res.data
      caseTotal.value = res.total ?? res.data.length ?? 0
      const cache = { ...caseNameCache.value }
      res.data.forEach((row) => {
        if (row?.case_id != null) cache[String(row.case_id)] = row.case_name || ''
      })
      caseNameCache.value = cache
    } else {
      caseListFull.value = []
      caseTotal.value = 0
    }
  } catch (error) {
    console.error('加载用例列表失败:', error)
    caseListFull.value = []
    caseTotal.value = 0
  } finally {
    caseLoading.value = false
  }
}

const cacheCaseRowsByIds = (list, ids) => {
  const cache = { ...selectedCaseRowsCache.value }
  const keySet = new Set((ids || []).map((id) => String(id)))
  ;(list || []).forEach((row) => {
    if (row?.case_id != null && keySet.has(String(row.case_id))) {
      cache[String(row.case_id)] = row
    }
  })
  selectedCaseRowsCache.value = cache
  const nameCache = { ...caseNameCache.value }
  ;(list || []).forEach((row) => {
    if (row?.case_id != null && keySet.has(String(row.case_id))) {
      nameCache[String(row.case_id)] = row.case_name || ''
    }
  })
  caseNameCache.value = nameCache
}

watch([caseListFull, checkedRowKeys], () => {
  cacheCaseRowsByIds(caseListFull.value, checkedRowKeys.value)
}, { deep: true })

const ensurePersistedCasesInCache = async () => {
  const ids = (persistedCaseIds.value || [])
      .map((id) => Number(id))
      .filter((id) => Number.isFinite(id) && id > 0)
  if (!ids.length) return
  const missing = ids.filter((id) => !selectedCaseRowsCache.value[String(id)])
  if (!missing.length) return
  try {
    caseLoading.value = true
    const res = await api.getApiTestcaseList({
      page: 1,
      page_size: Math.min(Math.max(missing.length * 2, 50), 500),
      state: 0,
      case_type: '用户脚本',
    })
    const idSet = new Set(missing)
    const rows = (Array.isArray(res?.data) ? res.data : []).filter((r) => idSet.has(Number(r.case_id)))
    cacheCaseRowsByIds(rows, ids)
  } catch (e) {
    console.error('加载已入库用例失败', e)
  } finally {
    caseLoading.value = false
  }
}

watch(caseQueryNewMode, async (queryNew) => {
  if (!queryNew) await ensurePersistedCasesInCache()
})

const caseTableData = computed(() => {
  if (caseQueryNewMode.value) return caseListFull.value
  return (persistedCaseIds.value || [])
      .map((id) => selectedCaseRowsCache.value[String(id)])
      .filter(Boolean)
})

const onCaseFilter = () => {
  if (filterCaseProject.value == null) {
    window.$message?.warning?.('请先选择所属应用')
    return
  }
  caseQueryNewMode.value = true
  casePage.value = 1
  loadCases()
}

const onCasePageChange = (page) => {
  if (!caseQueryNewMode.value) return
  casePage.value = page
  loadCases()
}
const onCasePageSizeChange = (pageSize) => {
  if (!caseQueryNewMode.value) return
  casePageSize.value = pageSize
  casePage.value = 1
  loadCases()
}

const casePagination = computed(() => {
  if (!caseQueryNewMode.value) return false
  return {
    page: casePage.value,
    pageSize: casePageSize.value,
    itemCount: caseTotal.value,
    showSizePicker: true,
    pageSizes: [10, 20, 50],
    onUpdatePage: onCasePageChange,
    onUpdatePageSize: onCasePageSizeChange,
  }
})

const openAdd = () => {
  isEdit.value = false
  schedulerTab.value = 'cron'
  intervalUnit.value = 'hours'
  intervalValue.value = 1
  datetimePickerValue.value = null
  filterCaseName.value = ''
  filterCaseProject.value = null
  filterCaseTags.value = []
  filterCreatedUser.value = ''
  casesExecuteConfig.value = {}
  caseNameCache.value = {}
  selectedCaseRowsCache.value = {}
  persistedCaseIds.value = []
  caseQueryNewMode.value = false
  execCollapseExpanded.value = []
  taskModalCollapseExpanded.value = ['cases']
  taskForm.value = {
    task_id: null,
    task_code: null,
    task_name: '',
    task_desc: '',
    task_type: '',
    task_project: null,
    task_notify: null,
    task_notifier: [],
    task_kwargs: {},
    task_scheduler: 'cron',
    task_interval_expr: null,
    task_datetime_expr: '',
    task_crontabs_expr: '',
  }
  checkedRowKeys.value = []
  caseListFull.value = []
  caseTotal.value = 0
  casePage.value = 1
  modalVisible.value = true
}

const openEdit = async (row) => {
  isEdit.value = true
  filterCaseName.value = ''
  filterCaseTags.value = []
  filterCreatedUser.value = ''
  try {
    const res = await api.getApiTask({task_id: row.task_id})
    const d = res?.data || {}
    const taskKwargs = d.task_kwargs && typeof d.task_kwargs === 'object' ? d.task_kwargs : {}
    const caseIds = Array.isArray(taskKwargs.case_ids) ? taskKwargs.case_ids : []
    const rawCasesCfg = taskKwargs.cases_execute_config ?? {}
    casesExecuteConfig.value =
        rawCasesCfg && typeof rawCasesCfg === 'object' ? { ...rawCasesCfg } : {}
    selectedCaseRowsCache.value = {}
    persistedCaseIds.value = [...caseIds]
    caseQueryNewMode.value = false
    filterCaseProject.value = d.task_project ?? null
    caseListFull.value = []
    caseTotal.value = 0
    taskModalCollapseExpanded.value = ['cases']
    taskForm.value = {
      task_id: d.task_id,
      task_code: d.task_code || null,
      task_name: d.task_name || '',
      task_desc: d.task_desc || '',
      task_type: d.task_type || '',
      task_project: d.task_project ?? null,
      task_notify: Array.isArray(d.task_notify) ? d.task_notify : null,
      task_notifier: Array.isArray(d.task_notifier) ? d.task_notifier : [],
      task_kwargs: { ...taskKwargs, case_ids: caseIds },
      task_scheduler: d.task_scheduler || 'cron',
      task_interval_expr: d.task_interval_expr ?? null,
      task_datetime_expr: d.task_datetime_expr || '',
      task_crontabs_expr: d.task_crontabs_expr || '',
    }
    schedulerTab.value = d.task_scheduler || 'cron'
    if (d.task_scheduler === 'interval' && d.task_interval_expr != null) {
      const {value, unit} = secondsToInterval(d.task_interval_expr)
      intervalValue.value = value
      intervalUnit.value = unit
    } else {
      intervalUnit.value = 'hours'
      intervalValue.value = 1
    }
    checkedRowKeys.value = [...caseIds]
    tagOptions.value = []
    if (caseIds.length) ensurePersistedCasesInCache()
    if (d.task_datetime_expr) {
      const t = dayjs(d.task_datetime_expr, ['YYYY-MM-DD HH:mm:ss', 'YYYY.MM.DD HH:mm:ss'], true)
      datetimePickerValue.value = t.isValid() ? t.valueOf() : null
    } else {
      datetimePickerValue.value = null
    }
    modalVisible.value = true
  } catch (error) {
    console.error('加载任务详情失败:', error)
    window.$message?.error?.('加载任务详情失败')
  }
}

// 右侧用例列表列（勾选 + 分页）
const caseColumns = [
  {type: 'selection', disabled: () => false},
  {
    title: '序号',
    key: '_idx',
    width: 64,
    align: 'center',
    render: (row, index) => (casePage.value - 1) * casePageSize.value + index + 1
  },
  {title: '用例名称', key: 'case_name', ellipsis: {tooltip: true}, minWidth: 120},
  {title: '用例描述', key: 'case_desc', ellipsis: {tooltip: true}, render: row => row.case_desc || '-', minWidth: 100},
  {title: '创建时间', key: 'created_time', width: 160, render: row => formatDateTime(row.created_time) || '-'},
  {title: '创建人', key: 'created_user', width: 90},
]

const handleSubmit = async () => {
  if (!taskForm.value.task_name?.trim()) {
    window.$message?.warning?.('请输入任务名称')
    return
  }
  if (!taskForm.value.task_scheduler) {
    window.$message?.warning?.('请选择任务调度')
    return
  }
  const caseIds = selectedCaseIds.value
  if (!caseIds.length) {
    window.$message?.warning?.('请至少勾选一个用例')
    return
  }
  const taskProjectId =
      filterCaseProject.value ?? taskForm.value.task_project ?? null
  if (taskProjectId == null) {
    window.$message?.warning?.('请在用例选择中指定所属应用')
    return
  }
  const casesCfgPayload = {}
  for (const cid of caseIds) {
    const cfg = casesExecuteConfig.value[String(cid)]
    if (!cfg?.steps_execute_config || !cfg?.global_env_id) {
      const label = caseNameCache.value[String(cid)] || `用例 ${cid}`
      window.$message?.warning?.(`请完善「${label}」的执行配置（全局环境与步骤配置）`)
      return
    }
    casesCfgPayload[String(cid)] = cfg
  }
  modalLoading.value = true
  try {
    const taskKwargsPayload = {
      ...(taskForm.value.task_kwargs && typeof taskForm.value.task_kwargs === 'object' ? taskForm.value.task_kwargs : {}),
      case_ids: caseIds,
      cases_execute_config: casesCfgPayload,
    }
    delete taskKwargsPayload.env_name
    const payload = {
      task_name: taskForm.value.task_name.trim(),
      task_desc: taskForm.value.task_desc || null,
      task_type: taskForm.value.task_type || null,
      task_project: taskProjectId,
      task_notify: Array.isArray(taskForm.value.task_notify) ? taskForm.value.task_notify : null,
      task_notifier: Array.isArray(taskForm.value.task_notifier) ? taskForm.value.task_notifier : null,
      task_kwargs: taskKwargsPayload,
      task_scheduler: taskForm.value.task_scheduler || null,
      task_interval_expr: taskForm.value.task_scheduler === 'interval' ? intervalToSeconds(intervalValue.value, intervalUnit.value) : null,
      task_datetime_expr: taskForm.value.task_scheduler === 'datetime' ? (datetimePickerValue.value ? dayjs(datetimePickerValue.value).format('YYYY-MM-DD HH:mm:ss') : null) : null,
      task_crontabs_expr: taskForm.value.task_scheduler === 'cron' ? taskForm.value.task_crontabs_expr || null : null,
    }
    const currentUser = userStore.username || ''
    if (isEdit.value) {
      payload.task_id = taskForm.value.task_id
      if (currentUser) payload.updated_user = currentUser
      await api.updateApiTaskList(payload)
      window.$message?.success?.('更新成功')
    } else {
      if (currentUser) payload.created_user = currentUser
      await api.createApiTaskList(payload)
      window.$message?.success?.('新增成功')
    }
    persistedCaseIds.value = [...caseIds]
    caseQueryNewMode.value = false
    modalVisible.value = false
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error?.(error?.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

/** 立即执行任务（下发 Celery 异步执行） */
const handleRunTask = async (row) => {
  try {
    await api.runApiTask({task_id: row.task_id})
    window.$message?.success?.(`已下发执行：${row.task_name}，请稍后在报告中查看结果`)
    $table.value?.handleSearch?.()
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '执行失败')
  }
}

/** 启动任务（启用调度，task_enabled=true） */
const handleStartTask = async (row) => {
  try {
    await api.startApiTask({task_id: row.task_id})
    window.$message?.success?.(`已启动：${row.task_name}，将按调度执行`)
    $table.value?.handleSearch?.()
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '启动失败')
  }
}

/** 停止任务（关闭调度，task_enabled=false） */
const handleStopTask = async (row) => {
  try {
    await api.stopApiTask({task_id: row.task_id})
    window.$message?.success?.(`已停止：${row.task_name}，将不再按调度执行`)
    $table.value?.handleSearch?.()
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '停止失败')
  }
}

const showCronNextRun = () => {
  const expr = taskForm.value.task_crontabs_expr
  if (!expr?.trim()) {
    window.$message?.warning?.('请先输入 crontab 表达式')
    return
  }
  const times = getCronNextRunTimes(expr, 10)
  if (times.length === 0) {
    window.$message?.warning?.('无法解析该 crontab 表达式，请检查格式（分 时 日 月 周）')
    cronNextRunTimes.value = []
    return
  }
  cronNextRunTimes.value = times
  cronNextRunVisible.value = true
}

const onSchedulerTabChange = (v) => {
  schedulerTab.value = v
  taskForm.value.task_scheduler = v
}

const intervalToSeconds = (val, unit) => {
  if (val == null || val <= 0) return null
  const n = Number(val)
  if (unit === 'days') return n * 86400
  if (unit === 'hours') return n * 3600
  if (unit === 'minutes') return n * 60
  return n
}

const secondsToInterval = (totalSeconds) => {
  if (totalSeconds == null || totalSeconds <= 0) return {value: 1, unit: 'hours'}
  const s = Number(totalSeconds)
  if (s % 86400 === 0) return {value: s / 86400, unit: 'days'}
  if (s % 3600 === 0) return {value: s / 3600, unit: 'hours'}
  if (s % 60 === 0) return {value: s / 60, unit: 'minutes'}
  return {value: s, unit: 'seconds'}
}

const formatSchedulerExpr = (row) => {
  const mode = row.task_scheduler
  if (mode === 'cron') return row.task_crontabs_expr || '-'
  if (mode === 'datetime') return row.task_datetime_expr || '-'
  if (mode === 'interval') {
    const sec = row.task_interval_expr
    if (sec == null || sec === '') return '-'
    const { value, unit } = secondsToInterval(sec)
    const unitLabel = { days: '天', hours: '小时', minutes: '分钟', seconds: '秒' }[unit] || unit
    return `每 ${value} ${unitLabel}`
  }
  return '-'
}

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
  { type: 'selection', fixed: 'left', width: 48 },
  {
    title: '序号',
    key: '__seq',
    width: 64,
    align: 'center',
    fixed: 'left',
    render(_row, rowIndex) {
      return seqBase + rowIndex + 1
    },
  },
  {
    title: '任务名称',
    key: 'task_name',
    width: 180,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '任务描述',
    key: 'task_desc',
    width: 160,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.task_desc || '-')
    },
  },
  {
    title: '任务标识',
    key: 'task_code',
    width: 220,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '所属应用',
    key: 'task_project',
    width: 120,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      const opt = projectOptions.value.find(p => p.value === row.task_project)
      return h('span', opt?.label ?? row.task_project ?? '')
    },
  },
  {
    title: '调度方式',
    key: 'task_scheduler',
    width: 90,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '启动状态',
    key: 'task_enabled',
    width: 90,
    align: 'center',
    render(row) {
      return h('span', {class: row.task_enabled ? 'text-success' : 'text-secondary'}, row.task_enabled ? '已启动' : '未启动')
    },
  },
  {
    title: '任务调度',
    key: 'task_scheduler_expr',
    width: 160,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', formatSchedulerExpr(row))
    },
  },
  {
    title: '关联用例数',
    key: 'task_kwargs',
    width: 100,
    align: 'center',
    render(row) {
      const ids = row.task_kwargs?.case_ids
      const count = Array.isArray(ids) ? ids.length : 0
      return h('span', `${count} 个`)
    },
  },
  {
    title: '最后执行时间',
    key: 'last_execute_time',
    width: 170,
    align: 'center',
    render(row) {
      const val = row.last_execute_time
      if (val == null || val === '') return h('span', '-')
      const formatted = formatDateTime(val)
      return h('span', formatted || '-')
    },
  },
  {
    title: '最后执行结果',
    key: 'last_execute_state',
    width: 110,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      const v = row.last_execute_state
      return h('span', v ? (TASK_STATUS_MAP[v] || v) : '-')
    },
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.updated_user || '-')
    },
  },
  {
    title: '最后更新时间',
    key: 'updated_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time) || '-')
    },
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.created_user || '-')
    },
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 170,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time) || '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'center',
    fixed: 'right',
    render(row) {
      const dropdownOptions = [
        {
          label: '日志',
          key: 'log',
          icon: renderIcon('material-symbols:description-outline', {size: 16}),
          onClick: () => openLog(row),
        },
        {
          label: '历史',
          key: 'history',
          icon: renderIcon('material-symbols:history', {size: 16}),
          onClick: () => openHistory(row),
        },
        {
          label: '编辑',
          key: 'edit',
          icon: renderIcon('material-symbols:edit-outline', {size: 16}),
          onClick: () => openEdit(row),
        },
        {
          label: '删除',
          key: 'delete',
          icon: renderIcon('material-symbols:delete-outline', {size: 16}),
          onClick: () => {
            if (window.confirm('确定删除该任务吗？')) handleDelete({task_id: row.task_id}, false)
          },
        },
      ]
      return [
        h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'primary',
              onClick: () => handleRunTask(row),
            },
            {
              default: () => '执行',
              icon: renderIcon('material-symbols:play-arrow', {size: 16}),
            },
        ),
        row.task_enabled
            ? h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'error',
                  onClick: () => handleStopTask(row),
                },
                {
                  default: () => '停止',
                  icon: renderIcon('material-symbols:stop-circle-outline', {size: 16}),
                },
            )
            : h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'success',
                  onClick: () => handleStartTask(row),
                },
                {
                  default: () => '启动',
                  icon: renderIcon('material-symbols:play-circle-outline', {size: 16}),
                },
            ),
        h(
            NDropdown,
            {
              trigger: 'click',
              options: dropdownOptions.map((opt) => ({label: opt.label, key: opt.key, icon: opt.icon})),
              onSelect: (key) => dropdownOptions.find((o) => o.key === key)?.onClick?.(),
            },
            {
              default: () =>
                  h(
                      NButton,
                      {
                        size: 'tiny',
                        quaternary: true,
                        type: 'default',
                      },
                      {
                        default: () => '更多',
                        icon: renderIcon('material-symbols:more-horiz', {size: 16}),
                      },
                  ),
            },
        ),
      ]
    },
  },
]
})

onMounted(() => {
  loadProjects()
  loadEnvOptions(null)
})
</script>

<template>
  <CommonPage show-footer title="任务管理">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="taskTableCheckedRowKeys"
        :query-bar-props="queryBarProps"
        :remote="true"
        :is-pagination="true"
        :columns="columns"
        :get-data="api.getApiTaskList"
        row-key="task_id"
        :scroll-x="2600"
        :single-line="true"
        @query-bar-create="openAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="任务名称：">
          <NInput
              v-model:value="queryItems.task_name"
              clearable
              placeholder="请输入任务名称"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.task_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择所属应用"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="维护人员：">
          <NInput
              v-model:value="queryItems.updated_user"
              clearable
              placeholder="请输入维护人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="执行时间：">
          <NDatePicker
              v-model:value="dateRange"
              type="daterange"
              clearable
              class="query-input query-date-range"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              @update:value="handleDateRangeChange"
          />
        </QueryBarItem>
        <QueryBarItem label="执行环境：">
          <NSelect
              v-model:value="queryItems.env_id"
              :options="envOptions"
              :loading="envLoading"
              clearable
              filterable
              placeholder="请选择执行环境"
              class="query-input"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <NModal
        v-model:show="modalVisible"
        :title="isEdit ? '编辑任务' : '新增任务'"
        preset="card"
        class="task-modal task-form-modal"
        :style="taskModalStyle"
        :loading="modalLoading"
        @close="modalVisible = false"
    >
      <div class="task-modal-body">
        <NForm label-placement="left" label-width="88px" size="small" class="task-config-form task-config-section">
          <div class="task-config-layout">
            <NFormItem label="任务名称" required class="task-config-cell task-config-cell-name">
              <NInput v-model:value="taskForm.task_name" placeholder="请输入任务名称" clearable />
            </NFormItem>
            <NFormItem label="任务通知" class="task-config-cell task-config-cell-notify">
              <NDynamicTags v-model:value="taskForm.task_notifier" placeholder="请输入通知人员，回车添加" />
            </NFormItem>
            <NFormItem label="任务类型" class="task-config-cell task-config-cell-type">
              <NInput v-model:value="taskForm.task_type" placeholder="请输入任务类型" clearable />
            </NFormItem>
            <NFormItem label="任务调度" required class="task-config-cell task-config-cell-scheduler">
              <NTabs
                  v-model:value="schedulerTab"
                  type="line"
                  size="small"
                  class="scheduler-tabs task-config-scheduler-tabs"
                  @update:value="onSchedulerTabChange"
              >
                <NTabPane name="cron" tab="Crontab">
                  <div class="cron-block">
                    <div class="cron-desc-block">
                      <div class="cron-desc-title">Crontab表达式说明:</div>
                      <div class="cron-desc-fields">
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>分(0-59)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>时(0-23)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>日(1-31)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>月(1-12)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>周(0-7)</span></div>
                      </div>
                    </div>
                    <div class="cron-input-row">
                      <NInput
                          v-model:value="taskForm.task_crontabs_expr"
                          placeholder="请输入 crontab 表达式，例如: 11 * * * *"
                          clearable
                          class="cron-input"
                      />
                      <NButton size="small" tertiary type="primary" class="cron-view-btn" @click="showCronNextRun">
                        查看执行时间
                      </NButton>
                    </div>
                  </div>
                </NTabPane>
                <NTabPane name="interval" tab="Interval">
                  <div class="interval-block">
                    <NTabs v-model:value="intervalUnit" type="line" size="small" class="interval-unit-tabs">
                      <NTabPane v-for="u in INTERVAL_UNITS" :key="u.value" :name="u.value" :tab="u.label" />
                    </NTabs>
                    <div class="interval-input-wrap">
                      <NInputNumber v-model:value="intervalValue" :min="1" placeholder="请输入间隔数值" style="width: 100%;" />
                    </div>
                  </div>
                </NTabPane>
                <NTabPane name="datetime" tab="Datetime">
                  <NDatePicker
                      v-model:value="datetimePickerValue"
                      type="datetime"
                      clearable
                      placeholder="请选择执行时间"
                      style="width: 100%;"
                  />
                </NTabPane>
              </NTabs>
            </NFormItem>
            <NFormItem label="任务描述" class="task-config-cell task-config-cell-desc">
              <NInput
                  v-model:value="taskForm.task_desc"
                  type="textarea"
                  placeholder="请输入任务描述"
                  clearable
                  class="task-config-desc-textarea"
              />
            </NFormItem>
          </div>
        </NForm>

        <NCollapse
            v-model:expanded-names="taskModalCollapseExpanded"
            arrow-placement="right"
            class="task-form-collapse"
        >
          <NCollapseItem title="用例配置" name="cases" class="task-case-collapse-item">
            <template #header-extra>
              <NSwitch
                  v-model:value="caseQueryNewMode"
                  size="small"
                  class="task-case-view-switch"
                  @click.stop
              >
                <template #checked>查询新用例</template>
                <template #unchecked>查看已选用例</template>
              </NSwitch>
            </template>
            <div class="case-section">
              <div v-if="caseQueryNewMode" class="case-toolbar">
                <div class="case-filter-item">
                  <span class="case-filter-label">所属应用：</span>
                  <NSelect
                      v-model:value="filterCaseProject"
                      :options="projectOptions"
                      :loading="projectLoading"
                      size="small"
                      clearable
                      filterable
                      placeholder="请选择所属应用"
                      class="case-filter-control"
                  />
                </div>
                <div class="case-filter-item">
                  <span class="case-filter-label">用例名称：</span>
                  <NInput
                      v-model:value="filterCaseName"
                      placeholder="请输入用例名称"
                      size="small"
                      clearable
                      class="case-filter-control"
                      @keyup.enter="onCaseFilter"
                  />
                </div>
                <div class="case-filter-item">
                  <span class="case-filter-label">所属标签：</span>
                  <NSelect
                      v-model:value="filterCaseTags"
                      :options="tagOptionsForFilter"
                      placeholder="请选择所属标签"
                      size="small"
                      clearable
                      filterable
                      multiple
                      class="case-filter-control"
                  />
                </div>
                <div class="case-filter-item">
                  <span class="case-filter-label">创建人员：</span>
                  <NInput
                      v-model:value="filterCreatedUser"
                      placeholder="请输入创建人员"
                      size="small"
                      clearable
                      class="case-filter-control"
                      @keyup.enter="onCaseFilter"
                  />
                </div>
                <NButton tertiary type="primary" size="small" class="case-toolbar-query-btn" @click="onCaseFilter">查询</NButton>
              </div>
              <p
                  v-if="!caseQueryNewMode && !persistedCaseIds.length"
                  class="task-case-persisted-empty"
              >
                暂无已入库用例；保存任务后可通过「查看已选用例」查看。
              </p>
              <NDataTable
                  v-else
                  v-model:checked-row-keys="checkedRowKeys"
                  :columns="caseColumns"
                  :data="caseTableData"
                  :row-key="row => row.case_id"
                  :loading="caseLoading"
                  :pagination="casePagination"
                  size="small"
                  max-height="320"
                  class="case-table"
              />
            </div>
          </NCollapseItem>

          <NCollapseItem title="执行配置" name="exec">
            <div v-if="!selectedCaseIds.length" class="task-exec-empty">请先在「用例配置」中勾选至少一个用例</div>
            <NCollapse
                v-else
                v-model:expanded-names="execCollapseExpanded"
                class="task-exec-case-collapse"
                arrow-placement="right"
            >
              <NCollapseItem
                  v-for="cid in selectedCaseIds"
                  :key="cid"
                  :name="String(cid)"
                  class="task-exec-case-item"
                  :title="caseNameCache[String(cid)] || '未命名用例'"
              >
                <div class="task-exec-config-wrap">
                  <ExecConfigModal
                      embedded
                      :case-id="cid"
                      :project-options="projectOptions"
                      :saved-config="casesExecuteConfig[String(cid)]"
                      @update:config="(cfg) => onCaseExecConfigUpdate(cid, cfg)"
                  />
                </div>
              </NCollapseItem>
            </NCollapse>
          </NCollapseItem>
        </NCollapse>
      </div>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <NButton @click="modalVisible = false">取消</NButton>
          <NButton type="primary" :loading="modalLoading" @click="handleSubmit">保存</NButton>
        </div>
      </template>
    </NModal>

    <NModal
        v-model:show="cronNextRunVisible"
        title="查看执行时间"
        preset="dialog"
        :show-icon="false"
        positive-text="关闭"
        @positive-click="cronNextRunVisible = false"
    >
      <div v-if="cronNextRunTimes.length" class="cron-times-list">
        <div v-for="(t, i) in cronNextRunTimes" :key="i" class="cron-time-item">{{ t }}</div>
      </div>
      <div v-else class="cron-times-empty">无法解析该表达式</div>
    </NModal>

    <NModal
        v-model:show="historyModalVisible"
        :title="historyTaskName ? `执行历史（${historyTaskName}）` : '执行历史'"
        preset="card"
        class="task-modal history-modal"
        :style="taskModalStyle"
        @close="historyModalVisible = false"
    >
      <NSpin :show="historyReportLoading">
        <div v-if="flattenedHistoryData.length" class="history-modal-table-wrap">
          <NDataTable
              :columns="historyColumns"
              :data="flattenedHistoryData"
              :row-key="historyRowKey"
              :row-class-name="(row) => row._isGroup ? 'report-group-row' : row._isBatchGroup ? 'report-batch-row' : ''"
              :scroll-x="2000"
              :single-line="true"
          />
        </div>
        <div v-else class="history-modal-empty">暂无报告数据</div>
        <div v-if="historyPagination.itemCount > 0" class="history-modal-pagination">
          <NPagination
              v-model:page="historyPagination.page"
              :page-count="Math.ceil(historyPagination.itemCount / historyPagination.pageSize)"
              :page-size="historyPagination.pageSize"
              :page-sizes="historyPagination.pageSizes"
              show-size-picker
              :prefix="historyPagination.prefix"
              @update:page="onHistoryPageChange"
              @update:page-size="onHistoryPageSizeChange"
          />
        </div>
      </NSpin>
    </NModal>

    <!-- 报告明细 + 步骤详情：与测试报告页共用 ReportDetailDrawer，右侧步骤列表、左侧步骤详情（含请求/响应/提取/断言/会话变量等） -->
    <ReportDetailDrawer
        v-model:show="historyReportDrawerVisible"
        :report-row="historyReportRow"
        title="报告明细"
    />

    <NModal
        v-model:show="logModalVisible"
        :title="logTaskName ? `执行日志（${logTaskName}）` : '执行日志'"
        preset="card"
        class="task-modal log-modal"
        :style="taskModalStyle"
        @close="logModalVisible = false"
    >
      <NSpin :show="logRecordLoading">
        <div v-if="logRecordList.length" class="log-modal-table-wrap">
          <NDataTable
              :columns="logRecordColumns"
              :data="logRecordList"
              :row-key="r => r.id || r.record_id"
              size="small"
              :bordered="false"
              :scroll-x="logTableScrollX"
          />
        </div>
        <div v-else class="log-modal-empty">暂无执行记录</div>
        <div v-if="logTotal > 0" class="log-modal-pagination">
          <NPagination
              v-model:page="logPage"
              v-model:page-size="logPageSize"
              :page-sizes="logPageSizes"
              :item-count="logTotal"
              show-size-picker
              :prefix="() => `共 ${logTotal} 条`"
              @update:page="onLogPageChange"
              @update:page-size="onLogPageSizeChange"
          />
        </div>
      </NSpin>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.query-input {
  width: 200px;
}

.query-date-range {
  width: 280px;
}

/* 弹窗卡片：居中，左右各 15% 留白（70% 宽度） */
.task-modal :deep(.n-card),
.task-modal :deep(.n-modal-body-wrapper) {
  width: 80% !important;
  margin-left: 10% !important;
  margin-right: 10% !important;
  margin-top: 5vh !important;
  margin-bottom: 5vh !important;
  max-width: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
}

.task-modal :deep(.n-card__content) {
  padding: 20px;
}

.task-form-modal :deep(.n-card__content) {
  max-height: calc(90vh - 120px);
  overflow-y: auto;
  font-size: var(--autotest-font-size);
}

.task-modal-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.task-config-section {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.task-form-collapse {
  margin-top: 0;
}

/*
 * 三行两列：整体 min-height 272px；右侧调度填满并在 Tab 内滚动
 * 左侧任务描述 min-height 90px，可由用户拖拽增高；描述区不纵向拉伸，避免输入框下留白
 */
.task-config-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto minmax(0, 1fr);
  column-gap: var(--task-config-field-gap);
  row-gap: var(--task-config-field-gap);
  align-items: start;
  width: 100%;
  box-sizing: border-box;
}

.task-config-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.task-config-cell {
  margin-bottom: 0 !important;
  min-width: 0;
}

.task-config-cell-name {
  grid-column: 1;
  grid-row: 1;
}

.task-config-cell-notify {
  grid-column: 2;
  grid-row: 1;
}

.task-config-cell-type {
  grid-column: 1;
  grid-row: 2;
}

.task-config-cell-scheduler {
  grid-column: 2;
  grid-row: 2 / 4;
  align-self: stretch;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  width: 100%;
  /* 勿在表单项根节点设 flex-direction: column，否则「任务调度」标签与 Tab 会上下换行 */
  align-items: flex-start;
}

.task-config-cell-scheduler :deep(.n-form-item-label) {
  padding-top: 6px;
  flex-shrink: 0;
}

.task-config-cell-scheduler :deep(.n-form-item-blank) {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.task-config-cell-desc {
  grid-column: 1;
  grid-row: 3;
  align-self: start;
}

.task-config-cell-desc :deep(.n-form-item) {
  align-items: flex-start;
}

.task-config-cell-desc :deep(.n-form-item-label) {
  padding-top: 6px;
}

.task-config-cell-desc :deep(.n-form-item-blank) {
  display: block;
}

.task-config-scheduler-tabs {
  width: 100%;
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.task-config-scheduler-tabs :deep(.n-tabs-nav) {
  flex-shrink: 0;
}

.task-config-scheduler-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.task-config-scheduler-tabs :deep(.n-tab-pane) {
  padding-top: 4px;
}

.cron-block,
.interval-block {
  min-height: 0;
}

.task-config-desc-textarea {
  width: 100%;
  --task-config-desc-min-height: 90px;
}

.task-config-desc-textarea :deep(.n-input),
.task-config-desc-textarea :deep(.n-input-wrapper) {
  min-height: var(--task-config-desc-min-height);
}

.task-config-desc-textarea :deep(.n-input__textarea-el) {
  min-height: var(--task-config-desc-min-height);
  /* 勿设 resize：Naive textarea 默认 resizable，会在 wrapper 上提供拖拽；此处再设会与 wrapper 各出现一个角标 */
  resize: none;
  overflow-y: auto;
  box-sizing: border-box;
}

.task-case-collapse-item :deep(.n-collapse-item__header) {
  display: flex;
  align-items: center;
}

.task-case-collapse-item :deep(.n-collapse-item__header-extra) {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  margin-left: 12px;
}

.task-case-view-switch {
  flex-shrink: 0;
}

.task-case-persisted-empty {
  font-size: var(--autotest-font-size);
  color: var(--n-text-color-3);
  margin: 8px 0;
}

.case-filter-item {
  flex: 1;
  min-width: 120px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.case-filter-label {
  flex-shrink: 0;
  font-size: var(--autotest-font-size);
  color: var(--n-text-color);
  white-space: nowrap;
}

.case-filter-control {
  flex: 1;
  min-width: 0;
}

/* 与「查询」small 按钮高度对齐 */
.case-filter-control :deep(.n-input-wrapper),
.case-filter-control :deep(.n-base-selection) {
  --n-height: 28px;
  min-height: 28px;
  font-size: var(--autotest-font-size-small);
}

.case-toolbar-query-btn {
  flex-shrink: 0;
}

.task-exec-empty {
  color: var(--n-text-color-3);
  padding: 12px 0;
  font-size: var(--autotest-font-size);
}

.task-exec-case-collapse {
  margin-top: 4px;
}

/* 仅作用于「每个用例」折叠项，勿用后代选择器以免污染内部 exec-config-collapse */
.task-exec-case-collapse :deep(.task-exec-case-item.n-collapse-item) {
  margin-bottom: 8px;
  margin-left: 0 !important;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.task-exec-case-collapse > :deep(.n-collapse-item) {
  margin-left: 0 !important;
}

.task-exec-case-collapse :deep(.task-exec-case-item > .n-collapse-item__header) {
  padding: 8px 12px !important;
  font-weight: 500;
}

.task-exec-case-collapse :deep(.task-exec-case-item > .n-collapse-item__content-inner) {
  padding: 0 12px 12px;
  background-color: var(--n-card-color, var(--n-color));
}

.task-exec-case-collapse :deep(.task-exec-case-item > .n-collapse-item__content-wrapper) {
  background-color: var(--n-card-color, var(--n-color));
}

.task-exec-config-wrap {
  min-width: 0;
}

.case-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  width: 100%;
}

@media (min-width: 900px) {
  .case-toolbar {
    flex-wrap: nowrap;
  }
}

.scheduler-tabs {
  width: 100%;
}

.cron-block {
  width: 100%;
}

.cron-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
}

.cron-input-row .cron-input {
  flex: 1;
}

.cron-view-btn {
  flex-shrink: 0;
}

.cron-desc-block {
  margin-top: 0;
}

.cron-desc-title {
  font-size: var(--autotest-font-size-mini);
  color: var(--n-text-color);
  margin-bottom: 8px;
}

.cron-desc-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
}

.cron-desc-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: var(--autotest-font-size-mini);
  color: var(--n-text-color);
}

.cron-asterisk {
  font-size: var(--autotest-font-size-large);
  margin-bottom: 2px;
}

.interval-block {
  width: 100%;
}

.interval-unit-tabs {
  margin-bottom: 12px;
}

.interval-input-wrap {
  margin-top: 8px;
}

.case-table {
  margin-top: 8px;
}

.cron-times-list {
  max-height: 320px;
  overflow-y: auto;
}

.cron-time-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--n-border-color);
}

.cron-times-empty {
  color: var(--n-text-color-3);
}

/* 历史弹框：与日志弹框一致的表格与分页样式 */
.history-modal-table-wrap {
  overflow-x: auto;
  max-height: calc(100vh - 280px);
  margin-bottom: 16px;
}
.history-modal-empty {
  color: var(--n-text-color-3);
  text-align: center;
  padding: 24px;
}
.history-modal-pagination {
  display: flex;
  justify-content: flex-end;
}

/* 执行日志弹框：表格横向滚动 + 分页 */
.log-modal-table-wrap {
  overflow-x: auto;
  max-height: calc(100vh - 280px);
  margin-bottom: 16px;
}
.log-modal-empty {
  color: var(--n-text-color-3);
  text-align: center;
  padding: 24px;
}
.log-modal-pagination {
  display: flex;
  justify-content: flex-end;
}
</style>
