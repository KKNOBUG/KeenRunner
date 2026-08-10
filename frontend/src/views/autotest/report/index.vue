<script setup>
/**
 * 测试报告页 = 全部用例的执行历史（对齐「测试用例 → 历史」）：
 * - 一行 = 一次用例执行（按 batch_code 聚合）
 * - 不含任务调度（task_code）产生的报告
 * - 多数据源 → 左抽屉「执行报告」→ 右抽屉步骤明细
 */
import { computed, h, onMounted, reactive, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NInput,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'
import { apiPermissionKey, formatDateTime, renderIcon } from '@/utils'
import api from '@/api'
import {
  buildBatchRows,
  filterCaseOnlyReports,
  isCaseSuccess,
} from '@/views/autotest/utils/reportBatchRows'

defineOptions({ name: '测试报告' })

const queryItems = ref({})
const vPermission = resolveDirective('permission')

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'split',
}

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

const tableLoading = ref(false)
const batchRows = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 次执行`
  },
})

const pagedBatchRows = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return batchRows.value.slice(start, start + pagination.pageSize)
})

const datasetDrawerVisible = ref(false)
const activeBatch = ref(null)
const detailDrawerVisible = ref(false)
const detailReportRow = ref(null)

const reportTypeOptions = [
  { label: '调试执行', value: '调试执行' },
  { label: '同步执行', value: '同步执行' },
  { label: '异步执行', value: '异步执行' },
  { label: '定时执行', value: '定时执行' },
]

const caseStateOptions = [
  { label: '成功', value: true },
  { label: '失败', value: false },
]

function dashText(val) {
  if (val == null || String(val).trim() === '') {
    return h('span', { style: { color: 'var(--n-text-color-3)' } }, '-')
  }
  return h('span', String(val))
}

function renderResultTag(ok) {
  return h(
    NTag,
    { type: ok ? 'success' : 'error', size: 'small', round: true },
    { default: () => (ok ? '成功' : '失败') },
  )
}

function buildQueryParams() {
  const queryParams = {
    ...queryItems.value,
    exclude_task_code: true,
    order: ['-case_st_time'],
  }
  if (queryParams.case_id === '' || queryParams.case_id === undefined) {
    queryParams.case_id = null
  } else if (queryParams.case_id !== null) {
    queryParams.case_id = Number(queryParams.case_id)
  }
  return queryParams
}

/** 按筛选条件拉取全部用例报告，再按 batch_code 聚合成「一次执行」 */
async function fetchAllCaseReports() {
  const base = buildQueryParams()
  const pageSize = 200
  let page = 1
  let total = Infinity
  const collected = []
  while (collected.length < total) {
    const res = await api.getApiReportList({
      ...base,
      page,
      page_size: pageSize,
    })
    const chunk = Array.isArray(res?.data) ? res.data : []
    total = Number(res?.total) || chunk.length
    collected.push(...chunk)
    if (!chunk.length || chunk.length < pageSize) break
    page += 1
    if (page > 50) break
  }
  return filterCaseOnlyReports(collected)
}

async function handleQuery() {
  tableLoading.value = true
  datasetDrawerVisible.value = false
  activeBatch.value = null
  try {
    const reports = await fetchAllCaseReports()
    batchRows.value = buildBatchRows(reports)
    pagination.itemCount = batchRows.value.length
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行历史失败')
    batchRows.value = []
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
  dateRange.value = getTodayRange()
  handleDateRangeChange(dateRange.value)
  pagination.page = 1
  handleQuery()
}

function onPageChange(page) {
  pagination.page = page
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
}

function openDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  detailDrawerVisible.value = true
}

function openBatchDetail(batchRow) {
  if (!batchRow?.runs?.length) return
  if (!batchRow.has_multi_dataset) {
    openDetailDrawer(batchRow.runs[0])
    return
  }
  activeBatch.value = batchRow
  datasetDrawerVisible.value = true
  detailDrawerVisible.value = false
  detailReportRow.value = null
}

async function deleteReports(reportIds) {
  const ids = (reportIds || []).filter((id) => id != null && id !== '')
  if (!ids.length) {
    window.$message?.warning?.('无可删除的报告')
    return
  }
  await Promise.all(ids.map((report_id) => api.deleteApiReport({ report_id })))
  window.$message?.success?.('删除成功')
  detailDrawerVisible.value = false
  detailReportRow.value = null
  if (activeBatch.value) {
    const idSet = new Set(ids.map((id) => String(id)))
    const remain = (activeBatch.value.runs || []).filter(
      (r) => !idSet.has(String(r.report_id)),
    )
    if (!remain.length) {
      datasetDrawerVisible.value = false
      activeBatch.value = null
    } else {
      activeBatch.value = {
        ...activeBatch.value,
        runs: remain,
        report_count: remain.length,
        has_multi_dataset: remain.length > 1,
      }
    }
  }
  await handleQuery()
}

function deleteBatchRow(batchRow) {
  const ids = (batchRow?.runs || []).map((r) => r.report_id).filter((id) => id != null)
  return deleteReports(ids)
}

function deleteReportRow(reportRow) {
  return deleteReports([reportRow?.report_id])
}

onMounted(() => {
  if (queryItems.value.date_from == null && dateRange.value) {
    handleDateRangeChange(dateRange.value)
  }
  handleQuery()
})

const batchColumns = computed(() => [
  {
    title: '序号',
    key: '_index',
    width: 50,
    align: 'center',
    render: (_, index) => (pagination.page - 1) * pagination.pageSize + index + 1,
  },
  {
    title: '用例ID',
    key: 'case_id',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.case_id)
    },
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 300,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.case_name)
    },
  },
  {
    title: '报告类型',
    key: 'report_type',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.report_type)
    },
  },
  {
    title: '执行结果',
    key: 'execute_result',
    width: 100,
    align: 'center',
    render(row) {
      if (row.report_count <= 0) return h('span', '-')
      return renderResultTag(!!row.execute_result)
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
    width: 180,
    align: 'center',
    render(row) {
      return h('span', row.execute_time ? formatDateTime(row.execute_time) : '-')
    },
  },
  {
    title: '执行耗时',
    key: 'elapsed_display',
    width: 100,
    align: 'center',
  },
  {
    title: '批次标识',
    key: 'batch_code',
    width: 400,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.batch_code)
    },
  },
  {
    title: '报告标识',
    key: 'report_code',
    width: 400,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.report_code)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render(row) {
      const multi = !!row.has_multi_dataset
      return h(NSpace, { size: 4, justify: 'center' }, [
        h(
          NButton,
          {
            size: 'tiny',
            type: 'info',
            quaternary: true,
            onClick: () => openBatchDetail(row),
          },
          {
            default: () => (multi ? '报告' : '详情'),
            icon: renderIcon(
              multi
                ? 'material-symbols:list-alt-outline'
                : 'material-symbols:visibility-outline',
              { size: 16 },
            ),
          },
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => deleteBatchRow(row),
          },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  { size: 'tiny', type: 'error', quaternary: true },
                  {
                    default: () => '删除',
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  },
                ),
                [[vPermission, apiPermissionKey('delete', '/autotest/report/delete')]],
              ),
            default: () =>
              h(
                'div',
                {},
                multi
                  ? `确定删除该次执行下的 ${row.report_count} 条报告吗？`
                  : '确定删除该报告吗？',
              ),
          },
        ),
      ])
    },
  },
])

const datasetColumns = [
  {
    title: '序号',
    key: 'run_index',
    width: 50,
    align: 'center',
  },
  {
    title: '数据源',
    key: 'dataset_display',
    width: 200,
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
    width: 100,
    align: 'center',
    render(row) {
      if (
        row.case_state === true ||
        row.case_state === 'true' ||
        row.case_state === false ||
        row.case_state === 'false'
      ) {
        return renderResultTag(isCaseSuccess(row.case_state))
      }
      return h('span', '-')
    },
  },
  {
    title: '执行人员',
    key: 'created_user',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.created_user)
    },
  },
  {
    title: '执行时间',
    key: 'case_st_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', row.case_st_time ? formatDateTime(row.case_st_time) : '-')
    },
  },
  {
    title: '执行耗时',
    key: 'case_elapsed',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '批次标识',
    key: 'batch_code',
    width: 400,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.batch_code)
    },
  },
  {
    title: '报告标识',
    key: 'report_code',
    width: 400,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return dashText(row.report_code)
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, { size: 4, justify: 'center' }, [
        h(
          NButton,
          {
            size: 'tiny',
            type: 'info',
            quaternary: true,
            onClick: () => openDetailDrawer(row),
          },
          {
            default: () => '详情',
            icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
          },
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => deleteReportRow(row),
          },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  { size: 'tiny', type: 'error', quaternary: true },
                  {
                    default: () => '删除',
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  },
                ),
                [[vPermission, apiPermissionKey('delete', '/autotest/report/delete')]],
              ),
            default: () => h('div', {}, '确定删除该报告吗？'),
          },
        ),
      ])
    },
  },
]
</script>

<template>
  <CommonPage show-footer title="测试报告">
    <div flex flex-col gap-30>
      <QueryBar
        v-bind="queryBarProps"
        @search="handleSearch"
        @reset="handleReset"
      >
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
        <QueryBarItem label="用例名称：">
          <NInput
            v-model:value="queryItems.case_name"
            clearable
            type="text"
            placeholder="请输入用例名称"
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
        <QueryBarItem label="执行结果：">
          <NSelect
            v-model:value="queryItems.case_state"
            :options="caseStateOptions"
            clearable
            placeholder="请选择执行结果"
            class="query-input"
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
        <QueryBarItem label="执行人员：">
          <NInput
            v-model:value="queryItems.created_user"
            clearable
            type="text"
            placeholder="请输入执行人员"
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
        <QueryBarItem label="报告标识：">
          <NInput
            v-model:value="queryItems.report_code"
            clearable
            type="text"
            placeholder="请输入报告标识"
            class="query-input"
            @keypress.enter="handleSearch"
          />
        </QueryBarItem>
      </QueryBar>

      <div min-w-0>
        <NDataTable
          :loading="tableLoading"
          :columns="batchColumns"
          :data="pagedBatchRows"
          :row-key="(r) => r._key"
          :scroll-x="2000"
          :single-line="true"
          striped
        />
      </div>
    </div>

    <div v-if="pagination.itemCount > 0" class="report-pagination mt-4 flex justify-end">
      <NPagination
        v-model:page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :item-count="pagination.itemCount"
        :page-sizes="pagination.pageSizes"
        show-size-picker
        :prefix="pagination.prefix"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      />
    </div>

    <NDrawer
      v-model:show="datasetDrawerVisible"
      placement="left"
      :width="'60%'"
      :trap-focus="false"
    >
      <NDrawerContent title="执行报告" closable :native-scrollbar="false">
        <NDataTable
          v-if="activeBatch?.runs?.length"
          :columns="datasetColumns"
          :data="activeBatch.runs"
          :row-key="(r) => r.report_code || r.report_id || r.id"
          :scroll-x="1800"
          :single-line="true"
          size="small"
          striped
        />
        <div v-else class="report-empty">该次执行暂无报告</div>
      </NDrawerContent>
    </NDrawer>

    <ReportDetailDrawer
      v-model:show="detailDrawerVisible"
      :report-row="detailReportRow"
      title="报告明细"
    />
  </CommonPage>
</template>

<style scoped>
.query-input {
  width: 200px;
}

.report-empty {
  padding: 48px 16px;
  text-align: center;
  color: var(--n-text-color-3);
}
</style>
