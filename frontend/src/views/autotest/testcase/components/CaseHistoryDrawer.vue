<script setup>
/**
 * 用例历史记录（仅用例页手动/定时执行产生的报告，不含任务调度 task_code）：
 * 1) 左抽屉「历史记录」：一行 = 一次执行（后端回填 has_multiple_dataset 标识是否多数据源执行）
 * 2) 多数据源报告 → 按批次标识再查同批次报告列表（左抽屉「执行报告」）
 * 3) 右抽屉 ReportDetailDrawer：步骤执行明细
 */
import { computed, h, reactive, ref, watch } from 'vue'
import {
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NPagination,
  NSpin,
  NTag,
  NTooltip,
} from 'naive-ui'
import ReportDetailDrawer from '@/components/autotest/ReportDetailDrawer.vue'
import { formatDateTime, renderIcon } from '@/utils'
import api from '@/api'
import { isCaseSuccess } from '@/views/autotest/utils/reportBatchRows'

const HISTORY_TIP =
  '- 无数据源：执行一次（一个批次标识对应一个报告标识）可以直接查看步骤执行详情\n- 多数据源：执行多次（一个批次标识对应多个报告标识）通过报告查看步骤执行详情'

const HISTORY_TIP_SINGLE =
  '- 当前用例的执行/调试历史记录（调试仅支持无/单数据源）\n- 点击「详情」可直接查看步骤执行详情'

const props = defineProps({
  show: { type: Boolean, default: false },
  /** 用例行：需含 case_id */
  caseRow: { type: Object, default: null },
  /**
   * 步骤编辑页：不进入「执行报告」多数据源层，批次内始终直接打开报告详情
   * （调试只允许选一条数据源）
   */
  singleDatasetOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:show'])

const drawerVisible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const caseId = computed(() => props.caseRow?.case_id ?? null)

const loading = ref(false)
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

function dashText(val) {
  if (val == null || String(val).trim() === '') {
    return h('span', { style: { color: 'var(--n-text-color-3)' } }, '-')
  }
  return h('span', String(val))
}

/** 行级查询报告列表（后端固定排除任务调度报告，每行自带 has_multiple_dataset 标识） */
async function loadHistory() {
  const id = caseId.value
  if (id == null || id === '') {
    reportRows.value = []
    pagination.itemCount = 0
    return
  }
  loading.value = true
  try {
    const res = await api.getApiReportList({
      case_id: Number(id),
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    reportRows.value = Array.isArray(res?.data) ? res.data : []
    pagination.itemCount = Number(res?.total) || reportRows.value.length
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载历史记录失败')
    reportRows.value = []
    pagination.itemCount = 0
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      datasetDrawerVisible.value = false
      activeBatchCode.value = null
      batchReports.value = []
      batchPagination.page = 1
      batchPagination.itemCount = 0
      detailDrawerVisible.value = false
      detailReportRow.value = null
      pagination.page = 1
      loadHistory()
    } else {
      datasetDrawerVisible.value = false
      activeBatchCode.value = null
      batchReports.value = []
      batchPagination.page = 1
      batchPagination.itemCount = 0
      detailDrawerVisible.value = false
      detailReportRow.value = null
      reportRows.value = []
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

function openDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  detailDrawerVisible.value = true
}

/** 多数据源报告 → 按批次标识分页查同批次报告列表（左抽屉「执行报告」）；单报告（含步骤页调试场景）→ 直接看步骤明细 */
async function openBatchDetail(row) {
  if (!row?.has_multiple_dataset || props.singleDatasetOnly) {
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

function renderResultTag(ok) {
  return h(
    NTag,
    { type: ok ? 'success' : 'error', size: 'small', round: true },
    { default: () => (ok ? '成功' : '失败') },
  )
}

const batchColumns = computed(() => [
  {
    title: '序号',
    key: '_index',
    width: 50,
    align: 'center',
    render: (_, index) => (pagination.page - 1) * pagination.pageSize + index + 1,
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
      const multi = !props.singleDatasetOnly && row.has_multiple_dataset
      return h(
        NButton,
        {
          size: 'small',
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
      )
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
      return h(
        NButton,
        {
          size: 'small',
          type: 'info',
          quaternary: true,
          onClick: () => openDetailDrawer(row),
        },
        {
          default: () => '详情',
          icon: renderIcon('material-symbols:visibility-outline', { size: 16 }),
        },
      )
    },
  },
]
</script>

<template>
  <!-- ① 历史记录：一次「执行」一行 -->
  <NDrawer
    v-model:show="drawerVisible"
    placement="left"
    :width="'60%'"
    :trap-focus="false"
  >
    <NDrawerContent closable :native-scrollbar="false">
      <template #header>
        <div class="drawer-title-row">
          <span class="drawer-title">历史记录</span>
          <NTooltip placement="bottom" trigger="hover">
            <template #trigger>
              <span class="drawer-tip-icon">
                <component :is="renderIcon('material-symbols:help-outline', { size: 18 })" />
              </span>
            </template>
            <div class="drawer-tip-content">{{ singleDatasetOnly ? HISTORY_TIP_SINGLE : HISTORY_TIP }}</div>
          </NTooltip>
        </div>
      </template>

      <NSpin :show="loading">
        <div v-if="reportRows.length || loading" class="case-history-table-wrap">
          <NDataTable
            :columns="batchColumns"
            :data="reportRows"
            :row-key="(r) => r.report_code || r.report_id"
            :scroll-x="1800"
            :single-line="true"
            size="small"
            striped
          />
        </div>
        <div v-else class="case-history-empty">暂无历史记录</div>
        <div v-if="pagination.itemCount > 0" class="case-history-pagination">
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
      </NSpin>
    </NDrawerContent>
  </NDrawer>

  <!-- ② 执行报告：多数据源报告按批次标识查出的同批次报告列表（步骤页 singleDatasetOnly 时不使用） -->
  <NDrawer
    v-if="!singleDatasetOnly"
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
        <div v-else class="case-history-empty">该次执行暂无报告</div>
        <div v-if="batchPagination.itemCount > 0" class="case-history-pagination">
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
  />
</template>

<style scoped>
.drawer-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.drawer-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
}
.drawer-tip-icon {
  display: inline-flex;
  align-items: center;
  color: var(--n-text-color-3);
  cursor: help;
}
.drawer-tip-content {
  white-space: pre;
  line-height: 1.7;
}
.case-history-table-wrap {
  overflow-x: auto;
}
.case-history-empty {
  padding: 48px 16px;
  text-align: center;
  color: var(--n-text-color-3);
}
.case-history-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
