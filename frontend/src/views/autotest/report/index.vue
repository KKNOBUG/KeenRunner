<script setup>
import {computed, h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NInput,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  NText,
  NTooltip
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'

import {renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'

defineOptions({name: '测试报告'})

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

// 报告明细抽屉：由 ReportDetailDrawer 组件负责展示步骤列表与步骤详情
const drawerVisible = ref(false)
const currentReport = ref(null)

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
    const groupExpanded = expandedKeys.value[taskCode] !== false
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
      const batchExpanded = expandedKeys.value[batchKey] !== false
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

// 切换展开/折叠：computed 中 expanded = (expandedKeys[key] !== false)，故取反为 expandedKeys[key] === false
function toggleExpand(groupKey) {
  expandedKeys.value = { ...expandedKeys.value, [groupKey]: expandedKeys.value[groupKey] === false }
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
    pagination.itemCount = total
  } catch (e) {
    rawReportList.value = []
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
  // 报告类型默认「定时执行」；执行日期默认最近三天，需同步到 queryItems
  if (queryItems.value.report_type == null) queryItems.value.report_type = '定时执行'
  if (queryItems.value.date_from == null && dateRange.value) handleDateRangeChange(dateRange.value)
  handleQuery()
})

// 查看明细：打开报告明细抽屉，由 ReportDetailDrawer 内部根据 reportRow 请求步骤列表并展示
const handleViewDetails = (row) => {
  currentReport.value = row
  drawerVisible.value = true
}

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
    title: '报告类型',
    key: 'report_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例ID',
    key: 'case_id',
    width: 80,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 220,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '成功步骤',
    key: 'step_pass_count',
    width: 80,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '失败步骤',
    key: 'step_fail_count',
    width: 80,
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
    title: '总步骤数',
    key: 'step_total',
    width: 80,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '执行状态',
    key: 'case_state',
    width: 80,
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
    width: 80,
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
    width: 80,
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
          :scroll-x="2000"
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

    <!-- 报告明细 + 步骤详情：共用组件，右侧步骤列表、左侧步骤详情（含请求/响应/提取/断言/会话变量等） -->
    <ReportDetailDrawer
        v-model:show="drawerVisible"
        :report-row="currentReport"
        title="报告明细"
    />

  </CommonPage>
</template>


<style scoped>
/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
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

