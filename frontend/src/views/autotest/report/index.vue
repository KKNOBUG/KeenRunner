<script setup>
import {computed, h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {
  NButton,
  NCard,
  NCheckbox,
  NCode,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDatePicker,
  NDescriptions,
  NDescriptionsItem,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTooltip
} from 'naive-ui'
import {useRouter} from 'vue-router'
import MonacoEditor from '@/components/monaco/index.vue'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'

import {renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'

defineOptions({name: '测试报告'})

const router = useRouter()

const queryItems = ref({})
const vPermission = resolveDirective('permission')

// 执行日期范围（用于查询条件，按 case_st_time 筛选）：默认最近三天（当天减去两天 ～ 当天）
const getTodayRange = () => {
  const end = new Date()
  end.setHours(23, 59, 59, 999)
  const start = new Date()
  start.setDate(start.getDate() - 2)
  start.setHours(0, 0, 0, 0)
  return [start.getTime(), end.getTime()]
}
const dateRange = ref(getTodayRange())
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

// 抽屉相关状态
const drawerVisible = ref(false)
const detailList = ref([])
const loading = ref(false)
const onlyShowFailed = ref(false)
const currentReport = ref(null)

// 详情抽屉相关状态
const detailDrawerVisible = ref(false)
const currentDetail = ref(null)

const {
  handleDelete,
} = useCRUD({
  name: '报告',
  doDelete: api.deleteApiReport,
  refresh: () => handleSearch(),
})

// ---------- 分组 + 可折叠：状态与分页 ----------
// 分组规则：
// 1. 不存在 task_code 或不存在 batch_code：不分组，直接在列表中平铺显示。
// 2. 同时存在 task_code 和 batch_code：分组展示。第一层按 task_code 分组（展开显示 task_code），第二层按 batch_code 分组（一个 task_code 下可有多个 batch_code），再展开展示报告行。默认折叠。
const BATCH_KEY_SEP = '::'
const rawReportList = ref([])
const totalCount = ref(0)
const tableLoading = ref(false)
const expandedKeys = ref({}) // 第一层 key = task_code；第二层 key = 'batch::' + task_code + '::' + batch_code
const pagination = reactive({
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

// 扁平化：先平铺「无 task_code 或 无 batch_code」的报告；再按 task_code → batch_code 两层分组输出（默认折叠）
const flattenedTableData = computed(() => {
  const list = rawReportList.value || []
  const result = []
  const flatReports = list.filter(r => !hasTaskAndBatch(r))
  const groupable = list.filter(hasTaskAndBatch)

  // 1. 不分组：直接平铺
  for (const r of flatReports) {
    result.push({ ...r, _isGroup: false })
  }

  // 2. 按 task_code 分组，再按 batch_code 分组
  const taskCodeMap = new Map()
  for (const r of groupable) {
    const tk = String(r.task_code).trim()
    if (!taskCodeMap.has(tk)) taskCodeMap.set(tk, [])
    taskCodeMap.get(tk).push(r)
  }
  for (const [taskCode, reports] of taskCodeMap) {
    const groupExpanded = expandedKeys.value[taskCode] === true
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
      const batchExpanded = expandedKeys.value[batchKey] === true
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

function toggleExpand(groupKey) {
  expandedKeys.value = { ...expandedKeys.value, [groupKey]: !expandedKeys.value[groupKey] }
}

async function handleQuery() {
  try {
    tableLoading.value = true
    const queryParams = {
      ...queryItems.value,
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (queryParams.case_id === '' || queryParams.case_id === undefined) {
      queryParams.case_id = null
    } else if (queryParams.case_id !== null) {
      queryParams.case_id = Number(queryParams.case_id)
    }
    const res = await api.getApiReportList(queryParams)
    const data = res?.data || []
    const total = res?.total ?? 0
    rawReportList.value = data
    totalCount.value = total
    pagination.itemCount = total
  } catch (e) {
    rawReportList.value = []
    totalCount.value = 0
    pagination.itemCount = 0
  } finally {
    tableLoading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  handleQuery()
}

function handleReset() {
  for (const key of Object.keys(queryItems.value)) {
    queryItems.value[key] = null
  }
  dateRange.value = null
  handleDateRangeChange(null)
  pagination.page = 1
  handleQuery()
}

function onPageChange(page) {
  pagination.page = page
  handleQuery()
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  handleQuery()
}

onMounted(() => {
  // 报告类型默认「定时执行」；执行日期默认当天（dateRange 已初始为当天，需同步到 queryItems）
  if (queryItems.value.report_type == null) queryItems.value.report_type = '定时执行'
  if (queryItems.value.date_from == null && dateRange.value) handleDateRangeChange(dateRange.value)
  handleQuery()
})

// 查看明细
const handleViewDetails = async (row) => {
  currentReport.value = row
  drawerVisible.value = true
  loading.value = true
  try {
    const res = await api.getApiDetailList({
      case_id: row.case_id,
      report_code: row.report_code,
      page: 1,
      page_size: 1000, // 获取所有明细
      state: 0
    })
    if (res?.data) {
      detailList.value = res.data
    } else {
      detailList.value = []
    }
  } catch (error) {
    window.$message?.error?.('查询明细失败')
    detailList.value = []
  } finally {
    loading.value = false
  }
}

// 过滤后的明细列表
const filteredDetailList = computed(() => {
  if (!onlyShowFailed.value) {
    return detailList.value
  }
  return detailList.value.filter(item => item.step_state === false || item.step_state === 'false')
})

// 格式化JSON
const formatJson = (data) => {
  if (!data) return ''
  if (typeof data === 'string') {
    try {
      return JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      return data
    }
  }
  return JSON.stringify(data, null, 2)
}

// 判断响应是否为JSON
const isJsonResponse = computed(() => {
  if (!currentDetail.value?.response_body) return false
  try {
    const body = currentDetail.value.response_body
    if (typeof body === 'string') {
      JSON.parse(body)
    } else if (typeof body === 'object') {
      return true
    }
    return false
  } catch {
    return false
  }
})

// 响应语言类型
const responseLanguage = computed(() => {
  if (!currentDetail.value?.response_header) return 'text'
  const headers = currentDetail.value.response_header
  if (typeof headers === 'object') {
    const contentType = headers['content-type'] || headers['Content-Type'] || ''
    if (contentType.includes('json')) return 'json'
    if (contentType.includes('xml')) return 'xml'
    if (contentType.includes('html')) return 'html'
  }
  return 'text'
})

// 格式化响应文本
const formatResponseText = () => {
  if (!currentDetail.value) return ''
  if (currentDetail.value.response_text) {
    return currentDetail.value.response_text
  }
  if (currentDetail.value.response_body) {
    return formatJson(currentDetail.value.response_body)
  }
  return ''
}

// Monaco编辑器配置
const monacoEditorOptions = (readOnly = false, language = 'json') => ({
  readOnly,
  language,
  theme: 'vs',
  automaticLayout: true,
  minimap: {enabled: false},
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  formatOnPaste: true,
  formatOnType: true
})

// 数据提取数据（与 HTTP 控制器调试结果布局一致：变量名、提取来源、提取范围、提取路径、提取值、提取结果、错误信息）
const extractVariablesData = computed(() => {
  if (!currentDetail.value?.extract_variables) return []
  const vars = currentDetail.value.extract_variables
  if (typeof vars === 'object' && !Array.isArray(vars)) {
    return Object.entries(vars).map(([name, value]) => ({
      name,
      source: '-',
      range: '-',
      expr: '-',
      extracted_value: value,
      success: true,
      error: '-'
    }))
  }
  if (Array.isArray(vars)) {
    return vars.map((item) => ({
      name: item.name ?? item.key ?? '-',
      source: item.source ?? '-',
      range: item.range ?? '-',
      expr: item.expr ?? '-',
      extracted_value: item.extracted_value ?? item.value ?? '-',
      success: item.success !== false,
      error: item.error ?? '-'
    }))
  }
  return []
})

// 断言结果数据（与 HTTP 控制器调试结果布局一致：断言名称、断言对象、断言路径、结果值、断言方式、期望值、断言结果、错误信息）
const assertValidatorsData = computed(() => {
  if (!currentDetail.value?.assert_validators) return []
  const validators = currentDetail.value.assert_validators
  if (Array.isArray(validators)) {
    return validators.map((v) => ({
      name: v.name ?? '-',
      source: v.source ?? '-',
      expr: v.expr ?? '-',
      actual_value: v.actual_value ?? '-',
      operation: v.operation ?? '-',
      except_value: v.except_value ?? v.expect_value ?? '-',
      success: v.success !== false,
      error: v.error ?? '-'
    }))
  }
  return []
})

// 判断会话变量是否为JSON
const isJsonSessionVariables = computed(() => {
  if (!currentDetail.value?.session_variables) return false
  return typeof currentDetail.value.session_variables === 'object'
})

// 数据提取表格列定义（与 HTTP 控制器调试结果一致）
const reportExtractColumns = [
  { title: '变量名', key: 'name', width: 120 },
  {
    title: '提取来源',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Response Json': 'Response Json',
        'Response Text': 'Response Text',
        'Response XML': 'Response XML',
        'Response Header': 'Response Header',
        'Response Cookie': 'Response Cookie'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '提取范围',
    key: 'range',
    width: 120,
    render: (row) => (row.range === 'ALL' ? '全部提取' : (row.range || '-'))
  },
  { title: '提取路径', key: 'expr', width: 120, ellipsis: { tooltip: true } },
  {
    title: '提取值',
    key: 'extracted_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.extracted_value === null || row.extracted_value === undefined) return '-'
      const value = typeof row.extracted_value === 'object'
          ? JSON.stringify(row.extracted_value)
          : String(row.extracted_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '提取结果',
    key: 'success',
    width: 120,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error',
      round: true,
      size: 'small'
    }, { default: () => row.success ? 'pass' : 'fail' })
  },
  { title: '错误信息', key: 'error', width: 120, ellipsis: { tooltip: true }, render: (row) => row.error || '-' }
]

// 断言结果表格列定义（与 HTTP 控制器调试结果一致）
const reportValidatorColumns = [
  { title: '断言名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Response Json': 'responseJson',
        'Response Text': 'responseText',
        'Response XML': 'responseXml',
        'Response Header': 'responseHeader',
        'Response Cookie': 'responseCookie',
        '变量池': '变量池'
      }
      return sourceMap[row.source] || row.source
    }
  },
  { title: '断言路径', key: 'expr', width: 130, ellipsis: { tooltip: true } },
  {
    title: '结果值',
    key: 'actual_value',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.actual_value === null || row.actual_value === undefined) return '-'
      return String(row.actual_value)
    }
  },
  { title: '断言方式', key: 'operation', width: 100 },
  {
    title: '期望值',
    key: 'expect_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => {
      const val = row.except_value ?? row.expect_value
      if (val === null || val === undefined) return '-'
      return String(val)
    }
  },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error',
      round: true,
      size: 'small'
    }, { default: () => row.success ? 'pass' : 'fail' })
  },
  { title: '错误信息', key: 'error', ellipsis: { tooltip: true }, render: (row) => row.error || '-' }
]

// 请求信息相关计算属性
const stepInfo = computed(() => {
  return currentDetail.value?.step || {}
})

const requestMethod = computed(() => {
  return stepInfo.value.request_method || '-'
})

const requestUrl = computed(() => {
  return stepInfo.value.request_url || '-'
})

const requestHeaders = computed(() => {
  return stepInfo.value.request_header
})

const requestParams = computed(() => {
  const params = stepInfo.value.request_params
  if (typeof params === 'string') {
    try {
      return JSON.parse(params)
    } catch {
      return {}
    }
  }
  return params || {}
})

const requestBody = computed(() => {
  return stepInfo.value.request_body
})

const requestFormData = computed(() => {
  return stepInfo.value.request_form_data
})

const requestFormUrlencoded = computed(() => {
  return stepInfo.value.request_form_urlencoded
})

const requestText = computed(() => {
  return stepInfo.value.request_text
})

const run_code = computed(() => {
  return stepInfo.value.code
})

const hasResponseInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false;
  const hasResponseData = !!(currentDetail.value?.response_body) ||
      !!(currentDetail.value?.response_header) ||
      !!(currentDetail.value?.response_text) ||
      !!(currentDetail.value?.response_cookie)
  return isRequestStep && hasResponseData;
})

const hasRequestInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false;
  const hasRequestData = !!(requestMethod.value && requestMethod.value !== '-') ||
      !!(requestUrl.value && requestUrl.value !== '-') ||
      !!requestHeaders.value ||
      !!requestBody.value ||
      !!requestFormData.value ||
      !!requestFormUrlencoded.value ||
      !!requestText.value ||
      !!run_code.value;
  return isRequestStep && hasRequestData;
})

const hasRequestBody = computed(() => {
  return !!(requestBody.value || requestFormData.value || requestFormUrlencoded.value || requestText.value)
})

const requestBodyType = computed(() => {
  if (requestBody.value) return 'JSON'
  if (requestFormData.value) return 'Form Data'
  if (requestFormUrlencoded.value) return 'x-www-form-urlencoded'
  if (requestText.value) return 'Text'
  return 'None'
})

const requestBodyText = computed(() => {
  if (requestText.value) return requestText.value
  if (requestFormUrlencoded.value) {
    if (typeof requestFormUrlencoded.value === 'object') {
      return Object.entries(requestFormUrlencoded.value)
          .map(([key, value]) => `${key}=${value}`)
          .join('&')
    }
    return String(requestFormUrlencoded.value)
  }
  return ''
})

const isJsonRequestHeaders = computed(() => {
  return requestHeaders.value && typeof requestHeaders.value === 'object'
})

const isJsonRequestParams = computed(() => {
  return requestParams.value && typeof requestParams.value === 'object' && Object.keys(requestParams.value).length > 0
})

const isJsonRequestBody = computed(() => {
  return requestBody.value && typeof requestBody.value === 'object'
})

const requestFormDataTable = computed(() => {
  if (!requestFormData.value) return []
  if (typeof requestFormData.value === 'object') {
    return Object.entries(requestFormData.value).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }))
  }
  return []
})

const formatRequestHeadersText = () => {
  if (!requestHeaders.value) return ''
  if (typeof requestHeaders.value === 'object') {
    return Object.entries(requestHeaders.value)
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n')
  }
  return String(requestHeaders.value)
}

const getMethodTagType = (method) => {
  if (!method || method === '-') return 'default'
  const upperMethod = method.toUpperCase()
  if (upperMethod === 'GET') return 'info'
  if (upperMethod === 'POST') return 'success'
  if (upperMethod === 'PUT') return 'warning'
  if (upperMethod === 'DELETE') return 'error'
  return 'default'
}

// 获取HTTP状态码
const getHttpCode = (item) => {
  if (item.response_body && typeof item.response_body === 'object') {
    return item.response_body.status_code || item.response_body.code || item.response_body.status || '-'
  }
  return '-'
}

// 获取HTTP状态码显示样式
const getHttpCodeTag = (code) => {
  if (!code || code === '-') return {type: 'default', text: '-'}
  const codeNum = parseInt(code)
  if (codeNum >= 200 && codeNum < 300) {
    return {type: 'success', text: `${code} OK`}
  } else if (codeNum >= 400 && codeNum < 500) {
    return {type: 'warning', text: `${code}`}
  } else if (codeNum >= 500) {
    return {type: 'error', text: `${code}`}
  }
  return {type: 'default', text: `${code}`}
}

// 获取请求方法
const getRequestMethod = (item) => {
  // 尝试从 session_variables 中获取（可能存储了请求信息）
  if (item.session_variables && typeof item.session_variables === 'object') {
    if (item.session_variables.request_method) {
      return item.session_variables.request_method
    }
  }
  // 尝试从 response_body 中获取
  if (item.response_body && typeof item.response_body === 'object') {
    if (item.response_body.request_info && item.response_body.request_info.method) {
      return item.response_body.request_info.method
    }
    if (item.response_body.method) {
      return item.response_body.method
    }
  }
  // 如果步骤类型是 api/http，可能需要从其他字段获取
  if (item.step_type === 'api' || item.step_type === 'http') {
    // 默认返回 POST，实际应该从数据中获取
    return 'POST'
  }
  return '-'
}

// 获取URL
const getUrl = (item) => {
  // 尝试从 session_variables 中获取
  if (item.session_variables && typeof item.session_variables === 'object') {
    if (item.session_variables.request_url) {
      return item.session_variables.request_url
    }
  }
  // 尝试从 response_body 中获取
  if (item.response_body && typeof item.response_body === 'object') {
    if (item.response_body.request_info && item.response_body.request_info.url) {
      return item.response_body.request_info.url
    }
    if (item.response_body.url || item.response_body.request_url) {
      return item.response_body.url || item.response_body.request_url
    }
  }
  return '-'
}

// 明细表格列定义
const detailColumns = [
  {
    title: '步骤序号',
    key: 'step_no',
    width: 40,
    align: 'center',
  },
  {
    title: '步骤名称',
    key: 'step_name',
    width: 100,
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤类型',
    key: 'step_type',
    width: 60,
    align: 'center',
  },
  {
    title: '步骤状态',
    key: 'step_state',
    width: 40,
    align: 'center',
    render(row) {
      if (row.step_state === true || row.step_state === 'true') {
        return h(NTag, {type: 'success'}, {default: () => '成功'})
      } else if (row.step_state === false || row.step_state === 'false') {
        return h(NTag, {type: 'error'}, {default: () => '失败'})
      }
      return h('span', '-')
    },
  },
  {
    title: '步骤消耗时间',
    key: 'step_elapsed',
    width: 60,
    align: 'center',
    render(row) {
      const elapsed = row.step_elapsed
      if (elapsed) {
        const elapsedNum = parseFloat(elapsed)
        if (!isNaN(elapsedNum)) {
          return h('span', elapsedNum.toFixed(3))
        }
      }
      return h('span', '-')
    },
  },
  {
    title: '步骤错误信息',
    key: 'step_exec_except',
    width: 200,
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.step_exec_except || '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 30,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, {size: 'small'}, [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => {
            currentDetail.value = row
            detailDrawerVisible.value = true
          }
        }, {default: () => '详情'}),
        h(NButton, {
          size: 'small',
          type: 'warning',
          onClick: () => {
            router.push({
              path: '/autotest/api',
              query: {
                case_id: row.case_id
              }
            })
          }
        }, {default: () => '跳转'})
      ])
    },
  },
]

// 报告类型选项
const reportTypeOptions = [
  {label: '调试执行', value: '调试执行'},
  {label: '同步执行', value: '同步执行'},
  {label: '异步执行', value: '异步执行'},
  {label: '定时执行', value: '定时执行'}
]

// 执行状态选项
const caseStateOptions = [
  {label: '成功', value: true},
  {label: '失败', value: false}
]

// 分组表头列：顶层组行 / 批次子头行 / 报告行
const groupLeadColumn = {
  title: '任务代码/批次代码',
  key: '_taskOrBatch',
  width: 300,
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
          onClick: (e) => {
            e.stopPropagation()
            toggleExpand(row._groupKey)
          },
        }, { default: () => expandIconVNode }),
        h(NTooltip, { trigger: 'hover' }, {
          trigger: () => h('span', { style: { fontWeight: 600 } }, shortenCode(row.task_code_display)),
          default: () => row.task_code_display,
        }),
        h('span', { style: { color: '#999', fontSize: '12px' } }, `(共${row.report_count}条)`),
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
          onClick: (e) => {
            e.stopPropagation()
            toggleExpand(row._batchKey)
          },
        }, { default: () => expandIconVNode }),
        h(NTooltip, { trigger: 'hover' }, {
          trigger: () => h('span', { style: { fontSize: '13px', fontWeight: 600  } }, shortenCode(row._batchCodeDisplay)),
          default: () => row._batchCodeDisplay,
        }),
        h('span', { style: { color: '#999', fontSize: '12px' } }, `(共${row.report_count}条)`),
      ])
    }
    const reportBatchCode = row.batch_code ?? '-'
    return h(NTooltip, { trigger: 'hover' }, {
      trigger: () => h('span', { style: { paddingLeft: '56px' } }, shortenCode(reportBatchCode)),
      default: () => (row.batch_code != null && row.batch_code !== '' ? row.batch_code : reportBatchCode),
    })
  },
}

// 任务/批次列中长码显示：前 10 位 + 省略 + 后 6 位
function shortenCode(str, head = 10, tail = 6) {
  if (str == null || str === '' || str === '-') return str === '' ? '' : (str ?? '-')
  const s = String(str)
  if (s.length <= head + tail) return s
  return s.slice(0, head) + '…' + s.slice(-tail)
}

// 将普通列包装为：组行与批次行显示 '-'，报告行走原逻辑
function wrapColumnForGroup(col) {
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

const columnsBase = [
  {
    title: '用例ID',
    key: 'case_id',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '报告类型',
    key: 'report_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '总步骤数',
    key: 'step_total',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '成功步骤',
    key: 'step_pass_count',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '失败步骤',
    key: 'step_fail_count',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '成功率',
    key: 'step_pass_ratio',
    width: 200,
    align: 'center',
    render(row) {
      const ratio = row.step_pass_ratio
      if (ratio === null || ratio === undefined) {
        return h('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '50%'
          }
        }, [
          h('span', {
            style: {
              fontSize: '10px',
            }
          }, '-')
        ])
      }

      // 转换为数字
      const ratioNum = typeof ratio === 'number' ? ratio : parseFloat(ratio)
      if (isNaN(ratioNum)) {
        return h('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '100%'
          }
        }, [
          h('span', {
            style: {
              fontSize: '14px',
            }
          }, '-')
        ])
      }

      // 确保比率在 0-100 之间
      const passRatio = Math.max(0, Math.min(100, ratioNum))
      const failRatio = 100 - passRatio

      // 格式化显示文本
      const ratioStr = passRatio.toFixed(2)

      // 构建进度条的子元素
      const progressBarChildren = []

      // 绿色部分（通过）- 只有当 passRatio > 0 时才显示
      if (passRatio > 0) {
        progressBarChildren.push(
            h('div', {
              style: {
                height: '100%',
                width: `${passRatio}%`,
                backgroundColor: '#18a058',
                transition: 'width 0.3s ease',
                minWidth: passRatio > 0 ? '1px' : '0'
              }
            })
        )
      }
      // 红色部分（失败）- 只有当 failRatio > 0 时才显示
      if (failRatio > 0) {
        progressBarChildren.push(
            h('div', {
              style: {
                height: '100%',
                width: `${failRatio}%`,
                backgroundColor: '#F4511E',
                transition: 'width 0.3s ease',
                minWidth: failRatio > 0 ? '1px' : '0'
              }
            })
        )
      }
      return h('div', {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          justifyContent: 'flex-start'
        }
      }, [
        h('div', {
          style: {
            display: 'flex',
            width: '100px',
            height: '8px',
            borderRadius: '10px',
            overflow: 'hidden',
            backgroundColor: '#F4511E',
            flexShrink: 0,
          }
        }, progressBarChildren),
        h('span', {
          style: {
            fontSize: '14px',
            whiteSpace: 'nowrap',
            minWidth: '60px',
            textAlign: 'left',
            fontWeight: '500'
          }
        }, `${ratioStr}%`)
      ])
    },
  },
  {
    title: '执行状态',
    key: 'case_state',
    width: 100,
    align: 'center',
    render(row) {
      if (row.case_state === true || row.case_state === 'true') {
        return h(NTag, {type: 'success'}, {default: () => '成功'})
      } else if (row.case_state === false || row.case_state === 'false') {
        return h(NTag, {type: 'error'}, {default: () => '失败'})
      }
      return h('span', '-')
    },
  },
  {
    title: '执行时间',
    key: 'case_st_time',
    width: 200,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '消耗时间',
    key: 'case_elapsed',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, {size: 'small'}, [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => handleViewDetails(row)
        }, {
          default: () => '查看',
          icon: renderIcon('material-symbols:visibility-outline', {size: 16})
        }),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({report_id: row.report_id}, false),
              onNegativeClick: () => {
              },
            },
            {
              trigger: () =>
                  withDirectives(
                      h(
                          NButton,
                          {
                            size: 'small',
                            type: 'error',
                          },
                          {
                            default: () => '删除',
                            icon: renderIcon('material-symbols:delete-outline', {size: 16}),
                          }
                      ),
                      [[vPermission, 'delete/api/v1/role/delete']]
                  ),
              default: () => h('div', {}, '确定删除该报告吗?'),
            }
        ),
      ])
    },
  },
]

// 带分组支持的列：首列任务/批次 + 其余列对组行显示 '-'
const columns = [groupLeadColumn, ...columnsBase.map(wrapColumnForGroup)]

// 表格行 key：组行用 groupKey，报告行用 report_code
const rowKey = (row) => {
  if (row._isGroup) return `group-${row._groupKey}`
  if (row._isBatchGroup) return row._batchKey
  return row.report_code ?? row.report_id ?? row.id
}

</script>

<template>
  <CommonPage show-footer title="测试报告">
    <!--  搜索栏  -->
    <QueryBar mb-30 @search="handleSearch" @reset="handleReset">
      <QueryBarItem label="用例ID：">
        <NInput
            v-model:value="queryItems.case_id"
            clearable
            type="text"
            placeholder="请输入用例ID"
            class="query-input"
            @keypress.enter="handleSearch"
        />
      </QueryBarItem>
      <QueryBarItem label="报告类型：">
        <NSelect
            v-model:value="queryItems.report_type"
            :options="reportTypeOptions"
            clearable
            placeholder="请选择报告类型"
            class="query-input"
        />
      </QueryBarItem>
      <QueryBarItem label="执行状态：">
        <NSelect
            v-model:value="queryItems.case_state"
            :options="caseStateOptions"
            clearable
            placeholder="请选择执行状态"
            class="query-input"
        />
      </QueryBarItem>
      <QueryBarItem label="成功率：">
        <NInput
            v-model:value="queryItems.step_pass_ratio"
            clearable
            type="text"
            placeholder="请输入成功率"
            class="query-input"
            @keypress.enter="handleSearch"
        />
      </QueryBarItem>
      <QueryBarItem label="任务标识：">
        <NInput
            v-model:value="queryItems.task_code"
            clearable
            type="text"
            placeholder="请输入任务标识"
            class="query-input"
            @keypress.enter="handleSearch"
        />
      </QueryBarItem>
      <QueryBarItem label="批次标识：">
        <NInput
            v-model:value="queryItems.batch_code"
            clearable
            type="text"
            placeholder="请输入批次标识"
            class="query-input"
            @keypress.enter="handleSearch"
        />
      </QueryBarItem>
      <QueryBarItem label="执行日期：">
        <NDatePicker
            v-model:value="dateRange"
            type="daterange"
            clearable
            class="query-input"
            placeholder="请选择执行日期范围"
            @update:value="handleDateRangeChange"
        />
      </QueryBarItem>
      <QueryBarItem label="创建人员：">
        <NInput
            v-model:value="queryItems.created_user"
            clearable
            type="text"
            placeholder="请输入创建人员"
            class="query-input"
            @keypress.enter="handleSearch"
        />
      </QueryBarItem>
    </QueryBar>

    <!--  按任务分组 + 可折叠 表格  -->
    <div>
      <NDataTable
          :loading="tableLoading"
          :columns="columns"
          :data="flattenedTableData"
          :row-key="rowKey"
          :row-class-name="(row) => row._isGroup ? 'report-group-row' : row._isBatchGroup ? 'report-batch-row' : ''"
          :scroll-x="1800"
          :single-line="true"
      />
    </div>
    <div v-if="pagination.itemCount > 0" class="report-pagination mt-4 flex justify-end">
      <NPagination
          v-model:page="pagination.page"
          :page-count="Math.ceil(pagination.itemCount / pagination.pageSize)"
          :page-size="pagination.pageSize"
          :page-sizes="pagination.pageSizes"
          show-size-picker
          :prefix="pagination.prefix"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
      />
    </div>

    <!-- 明细抽屉 -->
    <NDrawer v-model:show="drawerVisible" placement="right" width="50%">
      <NDrawerContent>
        <template #header>
          <div style="display: flex; align-items: center; justify-content: flex-end; width: 100%;">
            <NCheckbox v-model:checked="onlyShowFailed">
              仅看失败步骤
            </NCheckbox>
          </div>
        </template>
        <NDataTable
            :columns="detailColumns"
            :data="filteredDetailList"
            :loading="loading"
            :scroll-x="1200"
            :single-line="false"
            striped
        />
      </NDrawerContent>
    </NDrawer>

    <!-- 详情抽屉 -->
    <NDrawer v-model:show="detailDrawerVisible" placement="left" width="50%">
      <NDrawerContent>
        <NCard v-if="currentDetail" :bordered="false" style="width: 100%;">
          <template #header-extra>
            <NSpace align="center">
              <NTag :type="currentDetail.step_state ? 'success' : 'error'" round size="small">
                {{ currentDetail.step_state ? '成功' : '失败' }}
              </NTag>
              <NTag round size="small">类型: {{ currentDetail.step_type }}</NTag>
              <NTag round size="small">耗时: {{ currentDetail.step_elapsed || '-' }}s</NTag>
            </NSpace>
          </template>
          <NTabs type="line" animated>
            <!-- 基本信息 -->
            <NTabPane name="basic" tab="基本信息">
              <NSpace vertical :size="16">
                <NCard title="步骤信息" size="small" :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">用例ID：</div>
                      <div class="step-info-value">{{ currentDetail.case_id || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">用例标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.case_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">报告标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.report_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.step_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤序号：</div>
                      <div class="step-info-value">{{ currentDetail.step_no || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤状态：</div>
                      <div class="step-info-value">
                        <NTag :type="currentDetail.step_state ? 'success' : 'error'">
                          {{ currentDetail.step_state ? '成功' : '失败' }}
                        </NTag>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤名称：</div>
                      <div class="step-info-value">
                        <NText strong>{{ currentDetail.step_name || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤类型：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ currentDetail.step_type || '-' }}</NTag>
                      </div>
                    </div>
                    <div class="step-info-row" v-if="currentDetail.num_cycles">
                      <div class="step-info-label">循环次数：</div>
                      <div class="step-info-value">
                        <NTag type="warning">第 {{ currentDetail.num_cycles }} 次循环</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <!-- 循环结构额外信息 -->
                <NCard v-if="currentDetail.step_type === '循环结构'" title="循环结构配置" size="small"
                       :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">最大循环次数：</div>
                      <div class="step-info-value">{{ stepInfo.loop_maximums || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环间隔时间：</div>
                      <div class="step-info-value">{{ stepInfo.loop_interval ? `${stepInfo.loop_interval}s` : '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环对象来源：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iterable || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">索引变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_idx || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">键的变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_key || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">数据变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_val || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">错误处理策略：</div>
                      <div class="step-info-value">
                        <NTag type="warning">{{ stepInfo.loop_on_error || '-' }}</NTag>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环超时时间：</div>
                      <div class="step-info-value">{{ stepInfo.loop_timeout ? `${stepInfo.loop_timeout}s` : '-' }}</div>
                    </div>
                  </div>
                </NCard>

                <!-- 条件分支额外信息 -->
                <NCard v-if="currentDetail.step_type === '条件分支'" title="条件分支配置" size="small"
                       :bordered="false">
                  <div
                      v-if="stepInfo.conditions && Array.isArray(stepInfo.conditions) && stepInfo.conditions.length > 0">
                    <MonacoEditor
                        :value="formatJson(stepInfo.conditions)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 200px; height: auto;"
                    />
                  </div>
                </NCard>

                <!-- 等待控制额外信息 -->
                <NCard v-if="currentDetail.step_type === '等待控制'" title="等待控制配置" size="small"
                       :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">等待时间：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ stepInfo.wait ? `${stepInfo.wait}s` : '-' }}</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <NCard title="执行时间" size="small" :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">开始时间：</div>
                      <div class="step-info-value">{{ currentDetail.step_st_time || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">结束时间：</div>
                      <div class="step-info-value">{{ currentDetail.step_ed_time || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">消耗时间：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ currentDetail.step_elapsed ? `${currentDetail.step_elapsed}s` : '-' }}</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <NCard title="执行日志" size="small" :bordered="false">
                  <NCollapse :default-expanded-names="['errorInfo', 'execLogger']" arrow-placement="right">
                    <NCollapseItem title="错误日志" name="errorInfo" v-if="currentDetail.step_exec_except">
                      <pre
                          style="white-space: pre-wrap; word-wrap: break-word; color: #d03050; background: #fff5f5; padding: 12px; border-radius: 4px; border: 1px solid #ffccc7;">{{
                          currentDetail.step_exec_except
                        }}</pre>
                    </NCollapseItem>
                    <NCollapseItem title="普通日志" name="execLogger" v-if="currentDetail.step_exec_logger">
                      <pre
                          style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0;">{{
                          currentDetail.step_exec_logger
                        }}</pre>
                    </NCollapseItem>
                  </NCollapse>
                </NCard>
              </NSpace>

            </NTabPane>

            <!-- 请求信息 -->
            <NTabPane name="request" tab="请求信息" v-if="hasRequestInfo">
              <NSpace vertical :size="16">
                <NCollapse :default-expanded-names="['requestBasic', 'requestHeaders', 'requestParams', 'requestBody', 'requestCode']"
                           arrow-placement="right">
                  <NCollapseItem title="Basic" name="requestBasic">
                    <NDescriptions bordered :column="2" size="small">
                      <NDescriptionsItem label="请求方法">
                        <NTag :type="getMethodTagType(requestMethod)" size="small">{{ requestMethod || '-' }}</NTag>
                      </NDescriptionsItem>
                      <NDescriptionsItem label="请求URL">
                        <NText copyable style="font-family: monospace; font-size: 12px;">{{ requestUrl || '-' }}</NText>
                      </NDescriptionsItem>
                    </NDescriptions>
                  </NCollapseItem>
                  <NCollapseItem title="Headers" name="requestHeaders" v-if="requestHeaders">
                    <div v-if="isJsonRequestHeaders">
                      <MonacoEditor
                          :value="formatJson(requestHeaders)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 200px; height: auto;"
                      />
                    </div>
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        formatRequestHeadersText()
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Params" name="requestParams"
                                 v-if="requestParams && Object.keys(requestParams).length > 0">
                    <div v-if="isJsonRequestParams">
                      <MonacoEditor
                          :value="formatJson(requestParams)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 200px; height: auto;"
                      />
                    </div>
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        formatJson(requestParams)
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem :title="`Body (${requestBodyType})`" name="requestBody" v-if="hasRequestBody">
                    <div v-if="isJsonRequestBody">
                      <MonacoEditor
                          :value="formatJson(requestBody)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 400px; height: auto;"
                      />
                    </div>
                    <NDataTable
                        v-else-if="requestFormData"
                        :columns="[{title: 'Key', key: 'key'}, {title: 'Value', key: 'value'}]"
                        :data="requestFormDataTable"
                        size="small"
                        :bordered="true"
                    />
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        requestBodyText
                      }}</pre>
                  </NCollapseItem>
                  <!-- Python代码 -->
                  <NCollapseItem title="Code (Python)" name="requestCode"
                                 v-if="currentDetail.step_type === '执行代码请求(Python)' && stepInfo.code">
                    <MonacoEditor
                        :value="stepInfo.code"
                        :options="monacoEditorOptions(true, 'python')"
                        style="min-height: 400px; height: auto;"
                    />
                  </NCollapseItem>
                </NCollapse>
              </NSpace>
            </NTabPane>

            <!-- 响应信息 -->
            <NTabPane name="response" tab="响应信息" v-if="hasResponseInfo">
              <NSpace vertical :size="16">
                <NCollapse :default-expanded-names="['responseHeaders', 'responseBody']" arrow-placement="right">
                  <NCollapseItem title="Headers" name="responseHeaders" v-if="currentDetail.response_header">
                      <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
                          formatJson(currentDetail.response_header)
                        }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Cookies" name="responseCookies" v-if="currentDetail.response_cookie">
                    <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
                        formatJson(currentDetail.response_header)
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Body" name="responseBody">
                    <div v-if="isJsonResponse">
                      <MonacoEditor
                          :value="formatJson(currentDetail.response_body)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 400px; height: auto;"
                      />
                    </div>
                    <NCode
                        v-else
                        :code="formatResponseText()"
                        :language="responseLanguage"
                        show-line-numbers
                    />
                  </NCollapseItem>
                </NCollapse>
              </NSpace>
            </NTabPane>

            <!-- 数据提取（与 HTTP 控制器调试结果布局一致） -->
            <NTabPane name="extract" tab="数据提取">
              <NDataTable
                  v-if="extractVariablesData.length > 0"
                  :columns="reportExtractColumns"
                  :data="extractVariablesData"
                  size="small"
                  :bordered="true"
              />
              <NEmpty v-else description="暂无数据提取结果"/>
            </NTabPane>

            <!-- 断言结果（与 HTTP 控制器调试结果布局一致） -->
            <NTabPane name="assert" tab="断言结果">
              <NDataTable
                  v-if="assertValidatorsData.length > 0"
                  :columns="reportValidatorColumns"
                  :data="assertValidatorsData"
                  size="small"
                  :bordered="true"
              />
              <NEmpty v-else description="暂无断言结果"/>
            </NTabPane>

            <!-- 会话变量 -->
            <NTabPane name="variables" tab="会话变量" v-if="currentDetail.session_variables">
              <div v-if="isJsonSessionVariables">
                <MonacoEditor
                    :value="formatJson(currentDetail.session_variables)"
                    :options="monacoEditorOptions(true)"
                    style="min-height: 400px; height: auto;"
                />
              </div>
              <pre v-else style="white-space: pre-wrap; word-wrap: break-word;">{{
                  formatJson(currentDetail.session_variables)
                }}</pre>
            </NTabPane>
          </NTabs>
        </NCard>
        <NEmpty v-else description="暂无详情数据"/>
      </NDrawerContent>
    </NDrawer>

  </CommonPage>
</template>


<style scoped>
/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

/* 步骤信息两列布局 */
.step-info-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-info-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 16px;
  align-items: center;
}

.step-info-label {
  font-size: 14px;
  font-weight: bold;
  color: #666;
  flex-shrink: 0;
}

.step-info-value {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  word-break: break-all;
}

/* 顶层组头行 */
:deep(.report-group-row) {
  background-color: #f5f5f5;
}

/* 批次执行任务下按 batch_code 的子头行 */
:deep(.report-batch-row) {
  background-color: #fafafa;
}
</style>

