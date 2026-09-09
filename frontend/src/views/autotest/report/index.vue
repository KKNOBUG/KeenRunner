<script setup>
/**
 * 测试报告页 = 全部用例的手动/定时执行报告列表（对齐「测试用例 → 历史」）：
 * - 一行 = 一次执行（后端回填 has_multiple_dataset 标识是否多数据源执行）
 * - 不含任务调度（task_code）产生的报告
 * - 多数据源报告 → 左抽屉「执行报告」按批次查同批次列表 → 右抽屉步骤明细
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
  NSpin,
  NTag,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBar from '@/components/query-bar/QueryBar.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'
import { apiPermissionKey, formatDateTime, renderIcon } from '@/utils'
import api from '@/api'
import { isCaseSuccess } from '@/views/autotest/utils/reportBatchRows'

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
const reportRows = ref([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条记录`
  },
})

const datasetDrawerVisible = ref(false)
const activeBatchCode = ref(null)
const batchReports = ref([])
const batchLoading = ref(false)
const batchPagination = reactive({
  page: 1,
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  itemCount: 0,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条记录`
  },
})
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
  // 排序由后端固定按执行时间倒序, 无需传 order
  const queryParams = {
    ...queryItems.value,
  }
  if (queryParams.case_id === '' || queryParams.case_id === undefined) {
    queryParams.case_id = null
  } else if (queryParams.case_id !== null) {
    queryParams.case_id = Number(queryParams.case_id)
  }
  return queryParams
}

/** 行级查询报告列表（每行自带 后端回填的 has_multiple_dataset 标识） */
async function handleQuery() {
  tableLoading.value = true
  datasetDrawerVisible.value = false
  activeBatchCode.value = null
  batchReports.value = []
  batchPagination.itemCount = 0
  try {
    const res = await api.getApiReportList({
      ...buildQueryParams(),
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    reportRows.value = Array.isArray(res?.data) ? res.data : []
    pagination.itemCount = Number(res?.total) || reportRows.value.length
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行历史失败')
    reportRows.value = []
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
  handleQuery()
}

function onPageSizeChange(pageSize) {
  pagination.pageSize = pageSize
  pagination.page = 1
  handleQuery()
}

function openDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  detailDrawerVisible.value = true
}

/** 多数据源报告 → 按批次标识分页查同批次报告列表（「执行报告」抽屉）；单报告 → 直接看步骤明细 */
async function openBatchDetail(row) {
  if (!row?.has_multiple_dataset) {
    openDetailDrawer(row)
    return
  }
  activeBatchCode.value = row.batch_code
  batchPagination.page = 1
  datasetDrawerVisible.value = true
  detailDrawerVisible.value = false
  detailReportRow.value = null
  await loadBatchReports()
}

/** 行级查询批次报告列表（batch_code 精确匹配，服务端按 case_st_time 升序分页返回） */
async function loadBatchReports() {
  if (!activeBatchCode.value) {
    batchReports.value = []
    batchPagination.itemCount = 0
    return
  }
  batchLoading.value = true
  try {
    const res = await api.getApiReportBatchReports({
      batch_code: activeBatchCode.value,
      page: batchPagination.page,
      page_size: batchPagination.pageSize,
    })
    batchReports.value = Array.isArray(res?.data) ? res.data : []
    batchPagination.itemCount = Number(res?.total) || batchReports.value.length
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载执行报告失败')
    batchReports.value = []
    batchPagination.itemCount = 0
  } finally {
    batchLoading.value = false
  }
}

function onBatchPageChange(page) {
  batchPagination.page = page
  loadBatchReports()
}

function onBatchPageSizeChange(pageSize) {
  batchPagination.pageSize = pageSize
  batchPagination.page = 1
  loadBatchReports()
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
  // handleQuery 会关闭执行报告抽屉并刷新主列表，与删除后状态保持一致
  await handleQuery()
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
    key: 'case_state',
    width: 100,
    align: 'center',
    render(row) {
      if (row.case_state === true || row.case_state === 'true' || row.case_state === false || row.case_state === 'false') {
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
    title: '数据源',
    key: 'dataset_name',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      // 批次代表行: 展示批内数据场景数而非单一场景名
      if (row.has_multiple_dataset) {
        return h(NTag, { size: 'small', type: 'success', bordered: false }, { default: () => `${row.dataset_count} 个数据场景` })
      }
      if (!row.dataset_name) {
        return h('span', { style: { color: 'var(--n-text-color-3)' } }, '未使用数据源')
      }
      return h(NTag, { size: 'small', type: 'warning', bordered: false }, { default: () => row.dataset_name })
    },
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
      const multi = !!row.has_multiple_dataset
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
])

const datasetColumns = [
  {
    title: '序号',
    key: '_index',
    width: 50,
    align: 'center',
    render: (_, index) => index + 1,
  },
  {
    title: '数据源',
    key: 'dataset_name',
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
          :data="reportRows"
          :row-key="(r) => r.report_code || r.report_id"
          :scroll-x="2200"
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
        <NSpin :show="batchLoading">
          <NDataTable
            v-if="batchReports.length"
            :columns="datasetColumns"
            :data="batchReports"
            :row-key="(r) => r.report_code || r.report_id"
            :scroll-x="1800"
            :single-line="true"
            size="small"
            striped
          />
          <div v-else class="report-empty">该次执行暂无报告</div>
          <div v-if="batchPagination.itemCount > 0" class="report-pagination mt-4 flex justify-end">
            <NPagination
              v-model:page="batchPagination.page"
              v-model:page-size="batchPagination.pageSize"
              :item-count="batchPagination.itemCount"
              :page-sizes="batchPagination.pageSizes"
              show-size-picker
              :prefix="batchPagination.prefix"
              @update:page="onBatchPageChange"
              @update:page-size="onBatchPageSizeChange"
            />
          </div>
        </NSpin>
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
