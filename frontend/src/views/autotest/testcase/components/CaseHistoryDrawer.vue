<script setup>
/**
 * 用例历史记录（仅用例页手动/定时执行产生的报告，不含任务调度 task_code）：
 * 1) 左抽屉「历史记录」：一行 = 点一次「执行」（按 batch_code）
 * 2) 同次多条报告（多数据源）→ 再开左抽屉「执行报告」
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
import {
  buildBatchRows,
  filterCaseOnlyReports,
  isCaseSuccess,
} from '@/views/autotest/utils/reportBatchRows'

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

function dashText(val) {
  if (val == null || String(val).trim() === '') {
    return h('span', { style: { color: 'var(--n-text-color-3)' } }, '-')
  }
  return h('span', String(val))
}

async function fetchAllReportsByCaseId(id) {
  if (id == null || id === '') return []
  const pageSize = 200
  let page = 1
  let total = Infinity
  const collected = []
  while (collected.length < total) {
    const res = await api.getApiReportList({
      case_id: Number(id),
      page,
      page_size: pageSize,
      order: ['-case_st_time'],
      exclude_task_code: true,
    })
    const chunk = Array.isArray(res?.data) ? res.data : []
    total = Number(res?.total) || chunk.length
    collected.push(...chunk)
    if (!chunk.length || chunk.length < pageSize) break
    page += 1
    if (page > 50) break
  }
  // 兜底：客户端再过滤一次任务调度报告
  return filterCaseOnlyReports(collected)
}

async function loadHistory() {
  const id = caseId.value
  if (id == null || id === '') {
    batchRows.value = []
    pagination.itemCount = 0
    return
  }
  loading.value = true
  try {
    const reports = await fetchAllReportsByCaseId(id)
    batchRows.value = buildBatchRows(reports)
    pagination.itemCount = batchRows.value.length
    pagination.page = 1
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '加载历史记录失败')
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
      datasetDrawerVisible.value = false
      activeBatch.value = null
      detailDrawerVisible.value = false
      detailReportRow.value = null
      loadHistory()
    } else {
      datasetDrawerVisible.value = false
      activeBatch.value = null
      detailDrawerVisible.value = false
      detailReportRow.value = null
      batchRows.value = []
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

function openDetailDrawer(reportRow) {
  detailReportRow.value = reportRow
  detailDrawerVisible.value = true
}

/** 仅 1 条报告 → 直接看步骤；多数据源 → 先看执行报告（步骤页 singleDatasetOnly 时始终直达详情） */
function openBatchDetail(batchRow) {
  if (!batchRow?.runs?.length) return
  if (props.singleDatasetOnly || !batchRow.has_multi_dataset) {
    openDetailDrawer(batchRow.runs[0])
    return
  }
  activeBatch.value = batchRow
  datasetDrawerVisible.value = true
  detailDrawerVisible.value = false
  detailReportRow.value = null
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
      if (props.singleDatasetOnly && row.has_multi_dataset && row.runs?.[0]) {
        return dashText(row.runs[0].report_code)
      }
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
      const multi = !props.singleDatasetOnly && row.has_multi_dataset
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
        <div v-if="pagedBatchRows.length || loading" class="case-history-table-wrap">
          <NDataTable
            :columns="batchColumns"
            :data="pagedBatchRows"
            :row-key="(r) => r._key"
            :scroll-x="1500"
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

  <!-- ② 执行报告：同一次执行下，每个数据源一条（步骤页 singleDatasetOnly 时不使用） -->
  <NDrawer
    v-if="!singleDatasetOnly"
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
      <div v-else class="case-history-empty">该次执行暂无报告</div>
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
