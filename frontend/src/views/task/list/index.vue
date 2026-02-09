<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives, computed, watch} from 'vue'
import {
  NButton,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NModal,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NTabs,
  NTabPane,
  NDataTable,
  NDynamicTags,
  NDatePicker,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDateTime, renderIcon} from '@/utils'
import {getCronNextRunTimes} from '@/utils/common/cron'
import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat'
import {useCRUD} from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

dayjs.extend(customParseFormat)
defineOptions({name: '任务管理'})

// 与后端 autotest_enum.py 一致
const TASK_SCHEDULER_OPTIONS = [
  { label: 'Crontab', value: 'cron' },
  { label: '间隔', value: 'interval' },
  { label: '指定时间', value: 'datetime' },
]
const TASK_STATUS_MAP = {
  '等待执行': '等待执行',
  '正在执行': '正在执行',
  '成功': '成功',
  '失败': '失败',
}

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

const {
  handleDelete,
} = useCRUD({
  name: '任务',
  doCreate: api.createApiTaskList,
  doDelete: api.deleteApiTaskList,
  doUpdate: api.updateApiTaskList,
  refresh: () => $table.value?.handleSearch(),
})

const projectOptions = ref([])
const projectLoading = ref(false)
const tagOptions = ref([])
const tagLoading = ref(false)
const caseListFull = ref([])
const caseLoading = ref(false)
const casePage = ref(1)
const casePageSize = ref(10)
const caseTotal = ref(0)
const filterCaseName = ref('')
const filterCaseTags = ref([])
const checkedRowKeys = ref([])
const cronNextRunTimes = ref([])
const cronNextRunVisible = ref(false)

// 新增/编辑弹窗：卡片居中，左右各 15% 留白
const taskModalStyle = { width: '70%', marginLeft: '15%', marginRight: '15%', marginTop: '5vh', marginBottom: '5vh', boxShadow: '0 4px 20px rgba(0,0,0,0.15)', borderRadius: '8px' }
const modalVisible = ref(false)
const modalLoading = ref(false)
const isEdit = ref(false)
const schedulerTab = ref('cron')
const intervalUnit = ref('hours')
const intervalValue = ref(1)
const datetimePickerValue = ref(null)
const INTERVAL_UNITS = [
  { label: 'days', value: 'days' },
  { label: 'hours', value: 'hours' },
  { label: 'minutes', value: 'minutes' },
  { label: 'seconds', value: 'seconds' },
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
  task_kwargs: { env_name: '' },
  task_scheduler: 'cron',
  task_interval_expr: null,
  task_datetime_expr: '',
  task_crontabs_expr: '',
})

// 右侧：仅当所属项目变化时更新标签选项，不自动请求用例列表（用例列表由用户点击「查询」触发）
watch(() => taskForm.value.task_project, (projectId) => {
  if (projectId == null) {
    caseListFull.value = []
    caseTotal.value = 0
    checkedRowKeys.value = []
    tagOptions.value = []
    return
  }
  loadTags(projectId)
}, { immediate: false })

const tagOptionsForFilter = computed(() =>
    tagOptions.value.map(t => ({ label: t.tag_name ?? t.tag_id, value: t.tag_id }))
)

const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getApiProjectList({
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

const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getApiTagList({
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
  const projectId = taskForm.value.task_project
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
      case_name: filterCaseName.value || undefined,
      case_tags: filterCaseTags.value?.length ? filterCaseTags.value : undefined,
    })
    if (res?.data) {
      caseListFull.value = res.data
      caseTotal.value = res.total ?? res.data.length ?? 0
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

const onCasePageChange = (page) => {
  casePage.value = page
  loadCases()
}
const onCasePageSizeChange = (pageSize) => {
  casePageSize.value = pageSize
  casePage.value = 1
  loadCases()
}
const onCaseFilter = () => {
  casePage.value = 1
  loadCases()
}

const casePagination = computed(() => ({
  page: casePage.value,
  pageSize: casePageSize.value,
  itemCount: caseTotal.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  onUpdatePage: onCasePageChange,
  onUpdatePageSize: onCasePageSizeChange,
}))

const openAdd = () => {
  isEdit.value = false
  schedulerTab.value = 'cron'
  intervalUnit.value = 'hours'
  intervalValue.value = 1
  datetimePickerValue.value = null
  filterCaseName.value = ''
  filterCaseTags.value = []
  taskForm.value = {
    task_id: null,
    task_code: null,
    task_name: '',
    task_desc: '',
    task_type: '',
    task_project: null,
    task_notify: null,
    task_notifier: [],
    task_kwargs: { env_name: '' },
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
  try {
    const res = await api.getApiTask({ task_id: row.task_id })
    const d = res?.data || {}
    const taskKwargs = d.task_kwargs && typeof d.task_kwargs === 'object' ? d.task_kwargs : {}
    const caseIds = Array.isArray(taskKwargs.case_ids) ? taskKwargs.case_ids : []
    taskForm.value = {
      task_id: d.task_id,
      task_code: d.task_code || null,
      task_name: d.task_name || '',
      task_desc: d.task_desc || '',
      task_type: d.task_type || '',
      task_project: d.task_project ?? null,
      task_notify: Array.isArray(d.task_notify) ? d.task_notify : null,
      task_notifier: Array.isArray(d.task_notifier) ? d.task_notifier : [],
      task_kwargs: { ...taskKwargs, case_ids: caseIds, env_name: taskKwargs.env_name ?? '' },
      task_scheduler: d.task_scheduler || 'cron',
      task_interval_expr: d.task_interval_expr ?? null,
      task_datetime_expr: d.task_datetime_expr || '',
      task_crontabs_expr: d.task_crontabs_expr || '',
    }
    schedulerTab.value = d.task_scheduler || 'cron'
    if (d.task_scheduler === 'interval' && d.task_interval_expr != null) {
      const { value, unit } = secondsToInterval(d.task_interval_expr)
      intervalValue.value = value
      intervalUnit.value = unit
    } else {
      intervalUnit.value = 'hours'
      intervalValue.value = 1
    }
    checkedRowKeys.value = [...caseIds]
    await loadTags(d.task_project)
    await loadCases()
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
  { type: 'selection', disabled: () => false },
  { title: '序号', key: '_idx', width: 64, align: 'center', render: (row, index) => (casePage.value - 1) * casePageSize.value + index + 1 },
  { title: '用例名称', key: 'case_name', ellipsis: { tooltip: true }, minWidth: 120 },
  { title: '用例描述', key: 'case_desc', ellipsis: { tooltip: true }, render: row => row.case_desc || '-', minWidth: 100 },
  { title: '创建时间', key: 'created_time', width: 160, render: row => formatDateTime(row.created_time) || '-' },
  { title: '创建人', key: 'created_user', width: 90 },
]

const handleSubmit = async () => {
  if (!taskForm.value.task_name?.trim()) {
    window.$message?.warning?.('请输入任务名称')
    return
  }
  if (taskForm.value.task_project == null || taskForm.value.task_project === '') {
    window.$message?.warning?.('请选择所属项目')
    return
  }
  const caseIds = checkedRowKeys.value
  if (caseIds.length === 0) {
    window.$message?.warning?.('请至少勾选一个用例')
    return
  }
  const executeEnvironment = taskForm.value.task_kwargs?.env_name?.trim?.() || ''
  if (!executeEnvironment) {
    window.$message?.warning?.('请在任务参数中填写执行环境')
    return
  }
  modalLoading.value = true
  try {
    // 任务参数字典：case_ids、env_name 等，后端与 Celery 从 task_kwargs 读取
    const taskKwargsPayload = {
      ...(taskForm.value.task_kwargs && typeof taskForm.value.task_kwargs === 'object' ? taskForm.value.task_kwargs : {}),
      case_ids: caseIds,
      env_name: executeEnvironment,
    }
    const payload = {
      task_name: taskForm.value.task_name.trim(),
      task_desc: taskForm.value.task_desc || null,
      task_type: taskForm.value.task_type || null,
      task_project: taskForm.value.task_project,
      task_notify: Array.isArray(taskForm.value.task_notify) ? taskForm.value.task_notify : null,
      task_notifier: Array.isArray(taskForm.value.task_notifier) ? taskForm.value.task_notifier : null,
      task_kwargs: taskKwargsPayload,
      task_scheduler: taskForm.value.task_scheduler || null,
      task_interval_expr: taskForm.value.task_scheduler === 'interval' ? intervalToSeconds(intervalValue.value, intervalUnit.value) : null,
      task_datetime_expr: taskForm.value.task_scheduler === 'datetime' ? (datetimePickerValue.value ? dayjs(datetimePickerValue.value).format('YYYY-MM-DD HH:mm:ss') : null) : null,
      task_crontabs_expr: taskForm.value.task_scheduler === 'cron' ? taskForm.value.task_crontabs_expr || null : null,
    }
    if (isEdit.value) {
      payload.task_id = taskForm.value.task_id
      await api.updateApiTaskList(payload)
      window.$message?.success?.('更新成功')
    } else {
      await api.createApiTaskList(payload)
      window.$message?.success?.('新增成功')
    }
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
    await api.runApiTask({ task_id: row.task_id })
    window.$message?.success?.(`已下发执行：${row.task_name}，请稍后在报告中查看结果`)
    $table.value?.handleSearch?.()
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '执行失败')
  }
}

/** 启动任务（启用调度，task_enabled=true） */
const handleStartTask = async (row) => {
  try {
    await api.startApiTask({ task_id: row.task_id })
    window.$message?.success?.(`已启动：${row.task_name}，将按调度执行`)
    $table.value?.handleSearch?.()
  } catch (e) {
    window.$message?.error?.(e?.message || e?.data?.message || '启动失败')
  }
}

/** 停止任务（关闭调度，task_enabled=false） */
const handleStopTask = async (row) => {
  try {
    await api.stopApiTask({ task_id: row.task_id })
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
  if (totalSeconds == null || totalSeconds <= 0) return { value: 1, unit: 'hours' }
  const s = Number(totalSeconds)
  if (s % 86400 === 0) return { value: s / 86400, unit: 'days' }
  if (s % 3600 === 0) return { value: s / 3600, unit: 'hours' }
  if (s % 60 === 0) return { value: s / 60, unit: 'minutes' }
  return { value: s, unit: 'seconds' }
}

const columns = [
  {
    title: '任务ID',
    key: 'task_id',
    width: 90,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '执行环境',
    key: 'task_kwargs',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const env = row.task_kwargs?.env_name ?? ''
      return h('span', env || '-')
    },
  },
  {
    title: '任务名称',
    key: 'task_name',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '所属应用',
    key: 'task_project',
    width: 120,
    align: 'center',
    ellipsis: { tooltip: true },
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
    ellipsis: { tooltip: true },
  },
  {
    title: '启动状态',
    key: 'task_enabled',
    width: 90,
    align: 'center',
    render(row) {
      return h('span', { class: row.task_enabled ? 'text-success' : 'text-secondary' }, row.task_enabled ? '已启动' : '未启动')
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
    title: '最后执行状态',
    key: 'last_execute_state',
    width: 110,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const v = row.last_execute_state
      return h('span', v ? (TASK_STATUS_MAP[v] || v) : '-')
    },
  },
  {
    title: '任务标识',
    key: 'task_code',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
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
    title: '最后更新时间',
    key: 'updated_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
    },
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 400,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
            h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  style: 'margin-right: 6px;',
                  onClick: () => openEdit(row),
                },
                {
                  default: () => '编辑',
                  icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NButton,
            {
              size: 'small',
              type: 'info',
              style: 'margin-right: 6px;',
              onClick: () => handleRunTask(row),
            },
            {
              default: () => '执行',
              icon: renderIcon('material-symbols:play-arrow', { size: 16 }),
            }
        ),
        row.task_enabled
            ? h(
                NButton,
                {
                  size: 'small',
                  type: 'warning',
                  style: 'margin-right: 6px;',
                  onClick: () => handleStopTask(row),
                },
                {
                  default: () => '停止',
                  icon: renderIcon('material-symbols:stop-circle-outline', { size: 16 }),
                }
            )
            : h(
                NButton,
                {
                  size: 'small',
                  type: 'success',
                  style: 'margin-right: 6px;',
                  onClick: () => handleStartTask(row),
                },
                {
                  default: () => '启动',
                  icon: renderIcon('material-symbols:rocket-launch', { size: 16 }),
                }
            ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({ task_id: row.task_id }, false),
            },
            {
              trigger: () =>
                  withDirectives(
                      h(
                          NButton,
                          { size: 'small', type: 'error' },
                          {
                            default: () => '删除',
                            icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                          }
                      ),
                      [[vPermission, 'delete/api/v1/role/delete']]
                  ),
              default: () => h('div', {}, '确定删除该任务吗？'),
            }
        ),
      ]
    },
  },
]

onMounted(() => {
  loadProjects()
})
</script>

<template>
  <CommonPage show-footer title="任务管理">
    <template #action>
      <NButton type="primary" @click="openAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5"/>
        新增任务
      </NButton>
    </template>

    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :remote="true"
        :is-pagination="true"
        :columns="columns"
        :get-data="api.getApiTaskList"
        :row-key="'task_id'"
        :single-line="true"
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
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              placeholder="请输入创建人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="更新人员：">
          <NInput
              v-model:value="queryItems.updated_user"
              clearable
              placeholder="请输入更新人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <NModal
        v-model:show="modalVisible"
        :title="isEdit ? '编辑任务' : '新增'"
        preset="card"
        class="task-modal"
        :style="taskModalStyle"
        :loading="modalLoading"
        @close="modalVisible = false"
    >
      <NGrid :cols="24" :x-gap="16" class="task-modal-grid">
        <NGi :span="10" class="task-modal-left">
          <NForm label-placement="left" label-width="100px" size="small">
            <NFormItem label="执行环境" required>
              <NInput
                  v-model:value="taskForm.task_kwargs.env_name"
                  placeholder="请输入执行环境（存入 task_kwargs）"
                  clearable
              />
            </NFormItem>
            <NFormItem label="任务名称" required>
              <NInput
                  v-model:value="taskForm.task_name"
                  placeholder="请输入任务名"
                  clearable
              />
            </NFormItem>
            <NFormItem label="任务类型">
              <NInput
                  v-model:value="taskForm.task_type"
                  placeholder="任务类型"
                  clearable
              />
            </NFormItem>
            <NFormItem label="所属应用" required>
              <NSelect
                  v-model:value="taskForm.task_project"
                  :options="projectOptions"
                  :loading="projectLoading"
                  clearable
                  filterable
                  placeholder="选择所属应用"
              />
            </NFormItem>
            <NFormItem label="任务通知">
              <NDynamicTags
                  v-model:value="taskForm.task_notifier"
                  placeholder="通知人员，回车添加"
              />
            </NFormItem>
            <NFormItem label="任务描述">
              <NInput
                  v-model:value="taskForm.task_desc"
                  type="textarea"
                  placeholder="任务描述"
                  :rows="2"
              />
            </NFormItem>
            <NFormItem label="调度模式">
              <NTabs v-model:value="schedulerTab" type="line" size="small" class="scheduler-tabs" @update:value="onSchedulerTabChange">
                <NTabPane name="cron" tab="Crontab">
                  <div class="cron-block">
                    <label class="cron-label">crontab</label>
                    <div class="cron-input-row">
                      <NInput
                          v-model:value="taskForm.task_crontabs_expr"
                          placeholder="crontab表达式 例如: 11 * * * *"
                          clearable
                          class="cron-input"
                      />
                      <NButton size="small" tertiary type="primary" class="cron-view-btn" @click="showCronNextRun">查看执行时间</NButton>
                    </div>
                    <div class="cron-desc-block">
                      <div class="cron-desc-title">Crontab表达式说明:</div>
                      <div class="cron-desc-fields">
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>分钟(0-59)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>小时(0-23)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>日(1-31)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>月(1-12)</span></div>
                        <div class="cron-desc-item"><span class="cron-asterisk">*</span><span>周(0-7)</span></div>
                      </div>
                    </div>
                  </div>
                </NTabPane>
                <NTabPane name="interval" tab="Interval">
                  <div class="interval-block">
                    <NTabs v-model:value="intervalUnit" type="line" size="small" class="interval-unit-tabs">
                      <NTabPane v-for="u in INTERVAL_UNITS" :key="u.value" :name="u.value" :tab="u.label" />
                    </NTabs>
                    <div class="interval-input-wrap">
                      <NInputNumber
                          v-model:value="intervalValue"
                          :min="1"
                          placeholder=""
                          style="width: 100%;"
                      />
                    </div>
                  </div>
                </NTabPane>
                <NTabPane name="datetime" tab="Datetime">
                  <NDatePicker
                      v-model:value="datetimePickerValue"
                      type="datetime"
                      clearable
                      style="width: 100%;"
                  />
                </NTabPane>
              </NTabs>
            </NFormItem>
          </NForm>
        </NGi>
        <NGi :span="14" class="task-modal-right">
          <div class="case-section">
            <div class="case-toolbar">
              <NInput
                  v-model:value="filterCaseName"
                  placeholder="用例名称"
                  clearable
                  style="width: 160px;"
                  @keyup.enter="onCaseFilter"
              />
              <NSelect
                  v-model:value="filterCaseTags"
                  :options="tagOptionsForFilter"
                  placeholder="所属标签"
                  clearable
                  filterable
                  multiple
                  style="width: 180px;"
              />
              <NButton type="primary" size="small" @click="onCaseFilter">
                查询
              </NButton>
            </div>
            <p class="case-table-hint">根据左侧所属项目加载用例，可按用例名称、所属标签筛选；勾选需要的用例后点击保存。</p>
            <NDataTable
                v-model:checked-row-keys="checkedRowKeys"
                :columns="caseColumns"
                :data="caseListFull"
                :row-key="row => row.case_id"
                :loading="caseLoading"
                :pagination="casePagination"
                size="small"
                max-height="360"
                class="case-table"
            />
          </div>
        </NGi>
      </NGrid>
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
  </CommonPage>
</template>

<style scoped>
.query-input {
  width: 200px;
}

/* 弹窗卡片：居中，左右各 15% 留白（70% 宽度） */
.task-modal :deep(.n-card),
.task-modal :deep(.n-modal-body-wrapper) {
  width: 70% !important;
  margin-left: 15% !important;
  margin-right: 15% !important;
  margin-top: 5vh !important;
  margin-bottom: 5vh !important;
  max-width: none;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
}
.task-modal :deep(.n-card__content) {
  padding: 20px;
}
.task-modal-grid {
  min-height: 420px;
}
.task-modal-left {
  border-right: 1px solid #e0e0e0;
  padding-right: 16px;
}
.task-modal-right {
  padding-left: 8px;
}
.case-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.scheduler-tabs {
  width: 100%;
}
.cron-block {
  width: 100%;
}
.cron-label {
  display: block;
  font-size: 14px;
  color: #000;
  margin-bottom: 8px;
}
.cron-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.cron-input-row .cron-input {
  flex: 1;
}
.cron-view-btn {
  flex-shrink: 0;
}
.cron-desc-block {
  margin-top: 12px;
}
.cron-desc-title {
  font-size: 12px;
  color: #000;
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
  font-size: 12px;
  color: #000;
}
.cron-asterisk {
  font-size: 14px;
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
.cron-desc {
  font-size: 12px;
  color: #999999;
  margin-top: 8px;
  line-height: 1.4;
}
.case-table {
  margin-top: 8px;
}
.case-section .case-table-hint {
  font-size: 12px;
  color: #999999;
  margin: 0 0 8px 0;
  line-height: 1.5;
}
.cron-times-list {
  max-height: 320px;
  overflow-y: auto;
}
.cron-time-item {
  padding: 6px 0;
  border-bottom: 1px solid #e0e0e0;
}
.cron-times-empty {
  color: #999999;
}
</style>
