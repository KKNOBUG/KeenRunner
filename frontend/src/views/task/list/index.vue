<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NDropdown,
  NInput,
  NModal,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpin,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TextPreviewModal from '@/components/common/TextPreviewModal.vue'
import TaskFormModal from '@/views/task/list/components/TaskFormModal.vue'
import TaskHistoryModal from '@/views/task/list/components/TaskHistoryModal.vue'

import {formatDateTime, formatJsonBrief, renderIcon, resultPayloadOf} from '@/utils'
import {
  buildScheduleTags,
  formatFireTime,
  WEEK_LABELS,
  PERIODIC_ONLY_ONCE,
  CYCLE_WEEK,
  CYCLE_MONTH,
} from '@/utils/common/schedule'
import { useCRUD, useTaskRecordLogModal } from '@/composables'
import api from '@/api'

defineOptions({ name: '任务列表' }) // 与菜单名一致，供 KeepAlive include 匹配

const TASK_STATUS_MAP = {
  等待执行: '等待执行',
  正在执行: '正在执行',
  成功: '成功',
  失败: '失败',
  部分成功: '部分成功',
}

const $table = ref(null)
const queryItems = ref({})

/** 列表分页元数据（用于序号列） */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
const onPaginationMeta = (meta) => {
  listPaginationMeta.value = meta
}

/** 任务表多选 */
const taskTableCheckedRowKeys = ref([])

/** 新增/编辑任务四步向导 */
const taskFormVisible = ref(false)
const taskFormEditId = ref(null)
const taskFormEditRow = ref(null)

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'split',
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

// 历史：弹窗按批次汇总 → 左侧抽屉脚本报告 → 右侧步骤明细（TaskHistoryModal）
const historyModalVisible = ref(false)
const historyTaskRow = ref(null)

const openHistory = (row) => {
  historyTaskRow.value = row || null
  historyModalVisible.value = true
}

// 日志（执行记录）弹框：数据来源与任务记录页面一致，按 task_id 请求，弹框大小与新增/编辑任务一致
const {
  logModalVisible,
  logTaskName,
  logRecordList,
  logRecordLoading,
  logPage,
  logPageSize,
  logTotal,
  openLog,
  onLogPageChange,
  onLogPageSizeChange,
} = useTaskRecordLogModal()
const logPageSizes = [10, 20, 50, 100]
const logTableScrollX = 2000
const logRecordColumns = [
  { title: '记录ID', key: 'record_id', width: 80, align: 'center', ellipsis: { tooltip: true }, render: (row) => h('span', row.record_id ?? row.id ?? '-') },
  { title: '任务标识', key: 'task_code', width: 160, ellipsis: { tooltip: true } },
  { title: '任务名称', key: 'task_name', width: 160, ellipsis: { tooltip: true } },
  {
    title: '触发来源',
    key: 'trigger_type',
    width: 100,
    align: 'center',
    render: (row) => {
      const typeMap = { 手动执行: 'info', 定时执行: 'warning' }
      return h(NTag, { type: typeMap[row.trigger_type] || 'default', size: 'small', round: true }, () => row.trigger_type || '-')
    },
  },
  { title: '批次码', key: 'batch_code', width: 160, ellipsis: { tooltip: true } },
  {
    title: '用例IDs',
    key: 'case_ids',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { title: Array.isArray(row.case_ids) ? row.case_ids.join(', ') : '' }, Array.isArray(row.case_ids) && row.case_ids.length ? row.case_ids.join(', ') : '-'),
  },
  {
    title: '执行参数',
    key: 'exec_snapshot',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { title: row.exec_snapshot ? JSON.stringify(row.exec_snapshot) : '' }, formatJsonBrief(row.exec_snapshot, 40)),
  },
  {
    title: '执行结果',
    key: 'task_summary',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => {
      const payload = resultPayloadOf(row.task_summary)
      return h('span', { title: payload ? JSON.stringify(payload) : '' }, formatJsonBrief(payload, 40))
    },
  },
  {
    title: '执行状态',
    key: 'celery_status',
    width: 100,
    align: 'center',
    render: (row) => {
      const typeMap = { 等待执行: 'default', 正在执行: 'warning', 成功: 'success', 失败: 'error', 部分成功: 'warning' }
      return h(NTag, { type: typeMap[row.celery_status] || 'default', size: 'small', round: true }, () => row.celery_status || '-')
    },
  },
  { title: '错误信息', key: 'task_error', width: 180, ellipsis: { tooltip: true }, render: (row) => (row.task_error ? (row.task_error.length > 50 ? row.task_error.slice(0, 50) + '...' : row.task_error) : '-') },
  { title: '调度ID', key: 'celery_id', width: 200, ellipsis: { tooltip: true } },
  { title: '开始时间', key: 'celery_start_time', width: 170, align: 'center', render: (row) => h('span', formatDateTime(row.celery_start_time) || '-') },
  { title: '结束时间', key: 'celery_end_time', width: 170, align: 'center', render: (row) => h('span', formatDateTime(row.celery_end_time) || '-') },
  { title: '耗时', key: 'celery_duration', width: 80, align: 'center', ellipsis: { tooltip: true } },
]

// 历史/日志弹窗样式
const taskModalStyle = {
  width: '80%',
  marginLeft: '10%',
  marginRight: '10%',
  marginTop: '5vh',
  marginBottom: '5vh',
  boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
  borderRadius: '8px'
}

const openAdd = () => {
  taskFormEditId.value = null
  taskFormEditRow.value = null
  taskFormVisible.value = true
}

const openEdit = (row) => {
  taskFormEditId.value = row?.task_id ?? null
  taskFormEditRow.value = row || null
  taskFormVisible.value = true
}

/** 立即执行任务（下发 Celery，不改变调度启停状态） */
async function handleRunTask(row) {
  const taskId = row?.task_id
  if (taskId == null) {
    window.$message?.warning?.('缺少任务 ID')
    return
  }
  try {
    const res = await api.runApiTask({ task_id: taskId })
    window.$message?.success?.(res?.message || '已下发执行')
    $table.value?.handleSearch?.()
  } catch (_) {
    /* 错误由 http 拦截器提示 */
  }
}

/** 启动调度（task_enabled=true） */
async function handleStartTask(row) {
  const taskId = row?.task_id
  if (taskId == null) {
    window.$message?.warning?.('缺少任务 ID')
    return
  }
  try {
    const res = await api.startApiTask({ task_id: taskId })
    window.$message?.success?.(res?.message || '任务已启动')
    $table.value?.handleSearch?.()
  } catch (_) {
    /* 错误由 http 拦截器提示 */
  }
}

/** 停止调度（task_enabled=false） */
async function handleStopTask(row) {
  const taskId = row?.task_id
  if (taskId == null) {
    window.$message?.warning?.('缺少任务 ID')
    return
  }
  try {
    const res = await api.stopApiTask({ task_id: taskId })
    window.$message?.success?.(res?.message || '任务已停止')
    $table.value?.handleSearch?.()
  } catch (_) {
    /* 错误由 http 拦截器提示 */
  }
}

const onTaskFormSuccess = () => {
  $table.value?.handleSearch?.()
}

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

/** 执行环境下拉：与环境配置弹框同源(listEnvNames聚合)，按环境名称去重；有应用时仅该应用下已配置的环境 */
const loadEnvOptions = async (projectId = null) => {
  try {
    envLoading.value = true
    // { project_id: { app|file|database|redis: env_name[] } }：类型键摊平去重，value/label均为环境名称
    const res = await api.listEnvNames({ project_id: projectId != null ? [Number(projectId)] : [] })
    const byProject = res?.data || {}
    const names = new Set()
    Object.values(byProject).forEach((byType) => {
      if (!byType || typeof byType !== 'object') return
      Object.values(byType).forEach((arr) => {
        if (Array.isArray(arr)) arr.forEach((n) => { if (n != null && String(n).trim() !== '') names.add(String(n)) })
      })
    })
    envOptions.value = [...names]
        .sort((a, b) => a.localeCompare(b, 'zh-CN'))
        .map((n) => ({ label: n, value: n }))
    // 当前选中环境不在新选项中时清空
    const cur = queryItems.value.env_name
    if (cur != null && !envOptions.value.some((o) => o.value === cur)) {
      queryItems.value.env_name = null
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

/** 定时配置弹框状态：触发点多时单元格摘要无法完整阅读，点击弹框查看明细（对齐执行记录页“执行参数”交互） */
/** 定时配置明细查看弹框（共用 TextPreviewModal） */
const previewShow = ref(false)
const previewContent = ref('')

/** 结构化定时表达式 → 多行明细文本：触发点逐行列出，便于大量触发点时阅读 */
function buildScheduleDetailText(periodic, expr) {
  if (!periodic || !expr || typeof expr !== 'object') return ''
  const lines = [`执行时效：${periodic}`]
  if (periodic === PERIODIC_ONLY_ONCE) {
    const dates = Array.isArray(expr.trigger_dates) ? expr.trigger_dates : []
    lines.push(`触发日期时间（共 ${dates.length} 个）：`)
    dates.forEach((d) => lines.push(`  ${formatFireTime(d)}`))
    return lines.join('\n')
  }
  const cycle = expr.trigger_cycle
  if (!cycle) return ''
  lines.push(`周期类型：${cycle}`)
  if (cycle === CYCLE_WEEK) {
    const weeks = (expr.trigger_weeks || []).map((w) => WEEK_LABELS[w] || w).join('、')
    lines.push(`触发星期：${weeks || '-'}`)
  } else if (cycle === CYCLE_MONTH) {
    const days = (expr.trigger_month || []).map((d) => `${d}号`).join('、')
    lines.push(`触发日期：${days || '-'}`)
  }
  const times = Array.isArray(expr.trigger_times) ? expr.trigger_times : []
  lines.push(`触发时间点（共 ${times.length} 个）：`)
  times.forEach((t) => lines.push(`  ${t}`))
  return lines.join('\n')
}

const openScheduleModal = (row) => {
  const text = buildScheduleDetailText(row.task_periodic_expr, row.task_schedule_expr)
  if (!text) {
    window.$message?.warning?.('暂无定时配置')
    return
  }
  previewContent.value = text
  previewShow.value = true
}

/** 定时配置单元格：标签流展示（周期=信息色/数值=橙色，对齐需求截图），点击弹框查看明细 */
function renderScheduleCell(row) {
  const tags = buildScheduleTags(row.task_periodic_expr, row.task_schedule_expr)
  if (!tags.length) return h('span', '-')
  return h(
    'div',
    {
      class: 'schedule-cell-tags',
      title: '点击查看定时配置明细',
      onClick: () => openScheduleModal(row),
    },
    tags.map((tag) =>
      h(
        NTag,
        {
          type: tag.kind === 'cycle' ? 'info' : tag.kind === 'value' ? 'warning' : 'default',
          size: 'small',
          bordered: true,
        },
        { default: () => tag.label },
      ),
    ),
  )
}

/** 任务级涉及环境紧凑展示：首个环境 + N，悬停展示全部 */
function renderTaskInvolveEnvs(row) {
  const envs = Array.isArray(row.task_involve_envs) ? row.task_involve_envs.filter((e) => e) : []
  if (!envs.length) return h('span', '-')
  const trigger = h(
    'div',
    {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '4px',
        maxWidth: '100%',
        minHeight: '22px',
      },
    },
    [
      h(NTag, { type: 'success', size: 'small', bordered: true }, { default: () => envs[0] }),
      envs.length > 1 ? h('span', null, `+${envs.length - 1}`) : null,
    ].filter(Boolean),
  )
  if (envs.length === 1) return trigger
  return h(NTooltip, { placement: 'top', trigger: 'hover', showArrow: true }, {
    trigger: () => trigger,
    default: () =>
      h(
        'div',
        { style: { display: 'flex', flexWrap: 'wrap', gap: '2px' } },
        envs.map((env) =>
          h(NTag, { type: 'success', size: 'small', bordered: true, style: { margin: '2px' } }, { default: () => env }),
        ),
      ),
  })
}

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
  { type: 'selection', fixed: 'left', width: 48 },
  {
    title: '序号',
    key: '__seq',
    width: 50,
    align: 'center',
    fixed: 'left',
    render(_row, rowIndex) {
      return seqBase + rowIndex + 1
    },
  },
  {
    title: '任务名称',
    key: 'task_name',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
    // 任务名称超链接：点击直接进入编辑（对齐测试用例页面样式）
    render(row) {
      const name = row.task_name || ''
      return h(
          'a',
          {
            href: 'javascript:void(0)',
            title: name,
            style: {
              display: 'inline-block',
              maxWidth: '100%',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: '#2080f0',
              textDecoration: 'underline',
              cursor: 'pointer',
            },
            onClick: (e) => {
              e.preventDefault()
              openEdit(row)
            },
          },
          name
      )
    },
  },
  {
    title: '任务描述',
    key: 'task_desc',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.task_desc || '-')
    },
  },
  {
    title: '所属应用',
    key: 'task_project',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      const opt = projectOptions.value.find(p => p.value === row.task_project)
      return h('span', opt?.label ?? row.task_project ?? '')
    },
  },
  {
    title: '启动状态',
    key: 'task_enabled',
    width: 100,
    align: 'center',
    render(row) {
      return h('span', {class: row.task_enabled ? 'text-success' : 'text-secondary'}, row.task_enabled ? '已启动' : '未启动')
    },
  },
  {
    title: '定时配置',
    key: 'task_schedule_expr',
    width: 260,
    align: 'center',
    render(row) {
      return renderScheduleCell(row)
    },
  },
  {
    title: '关联用例数',
    key: 'task_case_ids',
    width: 100,
    align: 'center',
    render(row) {
      const ids = row.task_case_ids
      const count = Array.isArray(ids) ? ids.length : 0
      return h('span', `${count} 个`)
    },
  },
  {
    title: '任务涉及环境',
    key: 'task_involve_envs',
    width: 130,
    align: 'center',
    render(row) {
      return renderTaskInvolveEnvs(row)
    },
  },
  {
    title: '最后执行结果',
    key: 'last_execute_state',
    width: 100,
    align: 'center',
    render(row) {
      const v = row.last_execute_state
      if (v == null || v === '') return h('span', '-')
      const label = TASK_STATUS_MAP[v] || v
      const typeMap = {
        等待执行: 'default',
        正在执行: 'warning',
        成功: 'success',
        失败: 'error',
        部分成功: 'warning',
      }
      return h(
        NTag,
        { type: typeMap[label] || 'default', size: 'small', round: true },
        { default: () => label },
      )
    },
  },
    {
      title: '最后执行时间',
      key: 'last_execute_time',
      width: 180,
      align: 'center',
      render(row) {
        const val = row.last_execute_time
        if (val == null || val === '') return h('span', '-')
        const formatted = formatDateTime(val)
        return h('span', formatted || '-')
      },
    },
  {
    title: '最后执行人',
    key: 'last_execute_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.last_execute_user || '-')
    },
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.updated_user || '-')
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time) || '-')
    },
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.created_user || '-')
    },
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time) || '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    align: 'center',
    fixed: 'right',
    render(row) {
      const dropdownOptions = [
        row.task_enabled
          ? {
              label: '停止',
              key: 'stop',
              icon: renderIcon('material-symbols:stop-circle-outline', {size: 16}),
              onClick: () => handleStopTask(row),
            }
          : {
              label: '启动',
              key: 'start',
              icon: renderIcon('material-symbols:play-circle-outline', {size: 16}),
              onClick: () => handleStartTask(row),
            },
        {
          label: '编辑',
          key: 'edit',
          icon: renderIcon('material-symbols:edit-outline', {size: 16}),
          onClick: () => openEdit(row),
        },
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
      ]
      // 删除：NPopconfirm（对齐用户管理 / 测试用例），独立按钮触发，不放在「更多」内
      const actions = [
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
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({task_id: row.task_id}),
              onNegativeClick: () => {},
            },
            {
              trigger: () =>
                  h(
                      NButton,
                      {
                        size: 'tiny',
                        quaternary: true,
                        type: 'error',
                      },
                      {
                        default: () => '删除',
                        icon: renderIcon('material-symbols:delete-outline', {size: 16}),
                      },
                  ),
              default: () => h('div', {}, '确定删除该任务吗?'),
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
      return actions
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
        :scroll-x="2360"
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
              v-model:value="queryItems.env_name"
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

    <TaskFormModal
        v-model:show="taskFormVisible"
        :task-id="taskFormEditId"
        :task-row="taskFormEditRow"
        :project-options="projectOptions"
        :project-loading="projectLoading"
        @success="onTaskFormSuccess"
    />

    <TaskHistoryModal
        v-model:show="historyModalVisible"
        :task-row="historyTaskRow"
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

    <!-- 定时配置明细弹框：触发点逐行列出，共用 TextPreviewModal（monaco 只读 + 复制） -->
    <TextPreviewModal
        v-model:show="previewShow"
        title="定时配置明细"
        :content="previewContent"
        lang="plaintext"
        width="min(560px, 92vw)"
    />
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

/* 定时配置单元格：标签流布局，整格可点击查看明细（对齐执行记录页“执行参数”交互） */
.schedule-cell-tags {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
}
</style>
