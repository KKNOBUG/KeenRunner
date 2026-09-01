<script setup>
/**
 * 新增/编辑任务 — 三步向导
 * 0 任务与调度信息配置 → 1 脚本与执行次数配置 → 2 环境与数据源信息配置
 */
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCollapseTransition,
  NDrawer,
  NDrawerContent,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NStep,
  NSteps,
  NTooltip,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useUserStore } from '@/store'
import api from '@/api'
import {
  CYCLE_MONTH,
  CYCLE_WEEK,
  PERIODIC_ONLY_ONCE,
  buildSchedulePayload,
  createEmptyScheduleState,
  hasScheduleConfig,
  scheduleStateFromExpr,
} from '@/utils/common/schedule'
import ExecConfigModal from '@/views/autotest/steps/components/ExecConfigModal.vue'
import ScheduleConfig from './ScheduleConfig.vue'
import ScriptSelectModal from './ScriptSelectModal.vue'
import SelectedScriptTable from './SelectedScriptTable.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  /** null=新增；传 task_id 则编辑 */
  taskId: { type: [Number, String], default: null },
  projectOptions: { type: Array, default: () => [] },
  projectLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:show', 'success'])

const userStore = useUserStore()
const modalLoading = ref(false)
const currentStep = ref(0)
const isEdit = computed(() => props.taskId != null && props.taskId !== '')

const STEP_TITLES = ['任务与调度信息配置', '脚本与执行次数配置', '环境与数据源信息配置']
const LAST_STEP = STEP_TITLES.length - 1

const EXEC_MODE_OPTIONS = [
  { label: '并行执行', value: '并行执行' },
  { label: '串行执行', value: '串行执行' },
]
const EXEC_MODE_TIP =
  '并行执行：多个脚本同时执行；串行执行：按照任务中脚本的序号依次执行，前一个脚本完成后才会执行下一个'

const taskForm = ref(createEmptyForm())
const basicCollapsed = ref(false)
const scheduleState = ref(createEmptyScheduleState())
const scheduleOpen = ref(true)

const selectedScripts = ref([]) // row objects
const casesExecuteConfig = ref({})
const scriptPickerRef = ref(null)

function createEmptyForm() {
  return {
    task_id: null,
    task_code: null,
    task_name: '',
    task_desc: '',
    task_type: 'autotest_api',
    task_project: null,
    task_notify: null,
    task_notifier: [],
    task_kwargs: {},
    execute_mode: '并行执行',
  }
}

const selectedCaseIds = computed(() =>
  (selectedScripts.value || [])
    .map((r) => Number(r.case_id))
    .filter((id) => Number.isFinite(id) && id > 0),
)

watch(selectedCaseIds, (ids) => {
  const cfg = { ...casesExecuteConfig.value }
  const idSet = new Set(ids.map(String))
  for (const key of Object.keys(cfg)) {
    if (!idSet.has(key)) delete cfg[key]
  }
  casesExecuteConfig.value = cfg
})

watch(currentStep, (step) => {
  if (step !== 1) scriptPickerRef.value?.collapse?.()
})

/** 定时设置校验：周期模式恒有默认值；无任何实质配置允许通过，已配置则各必输项齐全 */
function validateSchedule() {
  const st = scheduleState.value
  const hasDays = (st.monthDays || []).length
  const hasWeeks = (st.weeks || []).length
  const times = st.times || []
  const hasTimes = times.some((t) => t)
  if (!hasDays && !hasWeeks && !hasTimes && !st.cycle) return true
  if (st.periodic === PERIODIC_ONLY_ONCE) {
    if (!hasDays) {
      window.$message?.warning?.('请选择触发日期')
      return false
    }
  } else {
    if (!st.cycle) {
      window.$message?.warning?.('请选择周期类型')
      return false
    }
    if (st.cycle === CYCLE_WEEK && !hasWeeks) {
      window.$message?.warning?.('请选择触发星期')
      return false
    }
    if (st.cycle === CYCLE_MONTH && !hasDays) {
      window.$message?.warning?.('请选择触发日期')
      return false
    }
  }
  if (!times.length || times.some((t) => !t) || !buildSchedulePayload(st)) {
    window.$message?.warning?.('请完善定时设置的触发时间')
    return false
  }
  return true
}

async function checkTaskNameUnique() {
  const name = taskForm.value.task_name?.trim()
  const projectId = taskForm.value.task_project
  if (!name || projectId == null) return true
  try {
    const res = await api.getApiTaskList({
      page: 1,
      page_size: 10,
      state: 0,
      task_name: name,
      task_project: projectId,
    })
    const list = Array.isArray(res?.data) ? res.data : []
    const conflict = list.find(
      (t) =>
        t.task_name === name &&
        Number(t.task_project) === Number(projectId) &&
        (!isEdit.value || Number(t.task_id) !== Number(taskForm.value.task_id)),
    )
    if (conflict) {
      window.$message?.warning?.('同一应用下任务名称已存在，请更换名称')
      return false
    }
  } catch (e) {
    console.error('校验任务名称失败', e)
  }
  return true
}

/** 步骤 0：基础信息 + 调度 */
async function validateStep0() {
  if (!taskForm.value.task_name?.trim()) {
    window.$message?.warning?.('请输入任务名称')
    return false
  }
  if (taskForm.value.task_project == null) {
    window.$message?.warning?.('请选择所属应用')
    return false
  }
  if (!(await checkTaskNameUnique())) return false
  return validateSchedule()
}

function validateStep1() {
  if (!selectedCaseIds.value.length) {
    window.$message?.warning?.('请至少添加一个脚本')
    return false
  }
  return true
}

function validateStep2() {
  for (const cid of selectedCaseIds.value) {
    const cfg = casesExecuteConfig.value[String(cid)]
    if (!cfg?.global_env_id || !cfg?.steps_execute_config) {
      window.$message?.warning?.('请完善环境与数据源配置（全局环境与步骤配置）')
      return false
    }
  }
  return true
}

async function goNext() {
  if (currentStep.value === 0) {
    if (!(await validateStep0())) return
  } else if (currentStep.value === 1) {
    if (!validateStep1()) return
  }
  if (currentStep.value < LAST_STEP) currentStep.value += 1
}

function goPrev() {
  if (currentStep.value > 0) currentStep.value -= 1
}

function onCasesExecConfigsUpdate(configsMap) {
  if (!configsMap || typeof configsMap !== 'object') return
  const next = { ...casesExecuteConfig.value }
  for (const [key, cfg] of Object.entries(configsMap)) {
    const prev = next[key] || {}
    const script = selectedScripts.value.find((r) => Number(r.case_id) === Number(key))
    const executeCount = normalizeExecuteCount(
      script?.execute_count ?? prev.execute_count ?? cfg?.execute_count ?? 1,
    )
    next[key] = {
      ...cfg,
      execute_count: executeCount,
    }
  }
  casesExecuteConfig.value = next
}

function normalizeExecuteCount(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n < 1) return 1
  return Math.min(Math.floor(n), 9999)
}

function onScriptAdd(row) {
  if (!row?.case_id) return
  const id = Number(row.case_id)
  if (selectedScripts.value.some((r) => Number(r.case_id) === id)) return
  selectedScripts.value = [...selectedScripts.value, { ...row, execute_count: 1 }]
}

function onScriptExecuteCountUpdate({ caseId, executeCount }) {
  // 仅更新页面内存中的已选脚本，不调用保存接口；点「确定」才落库
  const next = normalizeExecuteCount(executeCount)
  selectedScripts.value = selectedScripts.value.map((r) =>
    Number(r.case_id) === Number(caseId) ? { ...r, execute_count: next } : r,
  )
}

function removeScript(caseId) {
  selectedScripts.value = selectedScripts.value.filter((r) => Number(r.case_id) !== Number(caseId))
}

function resetState() {
  currentStep.value = 0
  taskForm.value = createEmptyForm()
  basicCollapsed.value = false
  scheduleState.value = createEmptyScheduleState()
  scheduleOpen.value = true
  selectedScripts.value = []
  casesExecuteConfig.value = {}
  scriptPickerRef.value?.collapse?.()
}

async function loadTaskDetail(taskId) {
  modalLoading.value = true
  try {
    const res = await api.getApiTask({ task_id: taskId })
    const d = res?.data || {}
    const taskKwargs = d.task_kwargs && typeof d.task_kwargs === 'object' ? d.task_kwargs : {}
    const caseIds = Array.isArray(taskKwargs.case_ids) ? taskKwargs.case_ids : []

    const topCfg = d.cases_execute_config
    const nestedCfg = taskKwargs.cases_execute_config
    const rawCfg =
      topCfg && typeof topCfg === 'object' && Object.keys(topCfg).length
        ? topCfg
        : nestedCfg && typeof nestedCfg === 'object'
          ? nestedCfg
          : {}
    casesExecuteConfig.value = { ...rawCfg }

    taskForm.value = {
      task_id: d.task_id,
      task_code: d.task_code || null,
      task_name: d.task_name || '',
      task_desc: d.task_desc || '',
      task_type: d.task_type || 'autotest_api',
      task_project: d.task_project ?? null,
      task_notify: Array.isArray(d.task_notify) ? d.task_notify : null,
      task_notifier: Array.isArray(d.task_notifier) ? d.task_notifier : [],
      task_kwargs: {
        case_ids: caseIds,
        ...(Array.isArray(taskKwargs.initial_variables)
          ? { initial_variables: taskKwargs.initial_variables }
          : {}),
      },
      execute_mode: taskKwargs.execute_mode === '串行执行' ? '串行执行' : '并行执行',
    }

    // 定时设置回显：已有定时信息默认展开，否则收起
    scheduleState.value = scheduleStateFromExpr(d.task_periodic_expr, d.task_schedule_expr)
    scheduleOpen.value = hasScheduleConfig(scheduleState.value)

    if (caseIds.length) {
      try {
        const listRes = await api.getApiTestcaseList({
          page: 1,
          page_size: Math.min(Math.max(caseIds.length * 2, 50), 500),
          state: 0,
        })
        const idSet = new Set(caseIds.map(Number))
        const found = (Array.isArray(listRes?.data) ? listRes.data : []).filter((r) =>
          idSet.has(Number(r.case_id)),
        )
        const map = {}
        found.forEach((r) => {
          map[String(r.case_id)] = r
        })
        selectedScripts.value = caseIds.map((id) => {
          const row = map[String(id)] || { case_id: id, case_name: `用例 ${id}` }
          const cfg = casesExecuteConfig.value[String(id)] || {}
          return {
            ...row,
            execute_count: normalizeExecuteCount(cfg.execute_count ?? row.execute_count ?? 1),
          }
        })
      } catch (e) {
        console.error('加载已选脚本失败', e)
        selectedScripts.value = caseIds.map((id) => {
          const cfg = casesExecuteConfig.value[String(id)] || {}
          return {
            case_id: id,
            case_name: `用例 ${id}`,
            execute_count: normalizeExecuteCount(cfg.execute_count ?? 1),
          }
        })
      }
    } else {
      selectedScripts.value = []
    }
  } catch (error) {
    console.error('加载任务详情失败:', error)
    window.$message?.error?.('加载任务详情失败')
    emit('update:show', false)
  } finally {
    modalLoading.value = false
  }
}

watch(
  () => props.show,
  async (visible) => {
    if (!visible) {
      resetState()
      return
    }
    resetState()
    if (props.taskId != null && props.taskId !== '') {
      await loadTaskDetail(props.taskId)
    }
  },
)

async function handleSubmit() {
  if (!(await validateStep0())) {
    currentStep.value = 0
    return
  }
  if (!validateStep1()) {
    currentStep.value = 1
    return
  }
  if (!validateStep2()) {
    currentStep.value = 2
    return
  }

  const caseIds = selectedCaseIds.value
  const casesCfgPayload = {}
  for (const cid of caseIds) {
    const key = String(cid)
    const base = casesExecuteConfig.value[key]
    const script = selectedScripts.value.find((r) => Number(r.case_id) === Number(cid))
    casesCfgPayload[key] = {
      ...(base && typeof base === 'object' ? base : {}),
      execute_count: normalizeExecuteCount(script?.execute_count ?? base?.execute_count ?? 1),
    }
  }

  modalLoading.value = true
  try {
    const prevKwargs =
      taskForm.value.task_kwargs && typeof taskForm.value.task_kwargs === 'object'
        ? taskForm.value.task_kwargs
        : {}
    const taskKwargsPayload = {
      case_ids: caseIds,
      execute_mode: taskForm.value.execute_mode || '并行执行',
    }
    if (Array.isArray(prevKwargs.initial_variables)) {
      taskKwargsPayload.initial_variables = prevKwargs.initial_variables
    }

    const schedulePayload = buildSchedulePayload(scheduleState.value)
    const payload = {
      task_name: taskForm.value.task_name.trim(),
      task_desc: taskForm.value.task_desc || null,
      task_type: taskForm.value.task_type || 'autotest_api',
      task_project: taskForm.value.task_project,
      task_notify: Array.isArray(taskForm.value.task_notify) ? taskForm.value.task_notify : null,
      task_notifier: Array.isArray(taskForm.value.task_notifier) ? taskForm.value.task_notifier : null,
      task_kwargs: taskKwargsPayload,
      cases_execute_config: casesCfgPayload,
      task_periodic_expr: schedulePayload?.periodic ?? null,
      task_schedule_expr: schedulePayload?.schedule ?? null,
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
    emit('update:show', false)
    emit('success')
  } catch (error) {
    window.$message?.error?.(error?.message || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

function handleClose() {
  emit('update:show', false)
}

const modalTitle = computed(() => (isEdit.value ? '编辑任务' : '新增任务'))
</script>

<template>
  <NDrawer
    :show="show"
    placement="right"
    :width="'60%'"
    :trap-focus="false"
    class="task-form-wizard-drawer"
    @update:show="(v) => emit('update:show', v)"
  >
    <NDrawerContent :title="modalTitle" closable :native-scrollbar="false" class="task-form-drawer-content">
      <div class="task-wizard">
        <div class="task-wizard-header">
          <NSteps :current="currentStep + 1" size="small" class="task-wizard-steps">
            <NStep
              v-for="(title, idx) in STEP_TITLES"
              :key="idx"
              :title="title"
              :status="idx < currentStep ? 'finish' : idx === currentStep ? 'process' : 'wait'"
            />
          </NSteps>
        </div>

        <div class="task-wizard-main">
          <!-- Step 0: 任务与调度信息配置 -->
          <div v-show="currentStep === 0" class="task-wizard-pane task-wizard-merged">
            <NCard :bordered="false" class="step-editor-card basic-card" :class="{ 'is-collapsed': basicCollapsed }">
              <template #header>
                <div class="card-header-row">
                  <div
                    class="panel-title panel-title-wrap"
                    role="button"
                    tabindex="0"
                    @click="basicCollapsed = !basicCollapsed"
                    @keydown.enter.prevent="basicCollapsed = !basicCollapsed"
                  >
                    <TheIcon
                      class="panel-collapse-icon"
                      :icon="basicCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
                      :size="20"
                    />
                    基本信息
                  </div>
                  <div class="card-header-actions">
                    <NButton text size="tiny" class="collapse-tiny-btn" @click="basicCollapsed = !basicCollapsed">
                      <template #icon>
                        <TheIcon
                          :icon="basicCollapsed ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                          :size="18"
                        />
                      </template>
                      {{ basicCollapsed ? '展开' : '收起' }}
                    </NButton>
                  </div>
                </div>
              </template>
              <NCollapseTransition :show="!basicCollapsed">
                <NForm class="step-editor-form basic-form" label-placement="left" label-width="80px" size="small">
                  <div class="basic-field-rows">
                    <div class="basic-field-row basic-field-row--cols3">
                      <NFormItem label="任务名称" required class="basic-fi-fill">
                        <NInput v-model:value="taskForm.task_name" placeholder="请输入任务名称" clearable />
                      </NFormItem>
                      <NFormItem label="所属应用" required class="basic-fi-fill">
                        <NSelect
                          v-model:value="taskForm.task_project"
                          :options="projectOptions"
                          :loading="projectLoading"
                          clearable
                          filterable
                          placeholder="请选择所属应用"
                        />
                      </NFormItem>
                      <NFormItem label="执行方式" required class="basic-fi-fill">
                        <NTooltip trigger="hover" :delay="300">
                          <template #trigger>
                            <NSelect
                              v-model:value="taskForm.execute_mode"
                              :options="EXEC_MODE_OPTIONS"
                              placeholder="请选择执行方式"
                            />
                          </template>
                          {{ EXEC_MODE_TIP }}
                        </NTooltip>
                      </NFormItem>
                    </div>
                    <div class="basic-field-row basic-field-row--cols1">
                      <NFormItem label="任务描述" class="basic-fi-fill">
                        <NInput
                          v-model:value="taskForm.task_desc"
                          type="textarea"
                          :autosize="{ minRows: 1, maxRows: 4 }"
                          placeholder="请输入任务描述（可选）"
                        />
                      </NFormItem>
                    </div>
                    <div class="basic-field-row basic-field-row--cols1">
                      <NFormItem label="任务通知" class="basic-fi-fill">
                        <NDynamicTags v-model:value="taskForm.task_notifier" />
                      </NFormItem>
                    </div>
                  </div>
                </NForm>
              </NCollapseTransition>
            </NCard>

            <ScheduleConfig v-model="scheduleState" v-model:open="scheduleOpen" />
          </div>

          <!-- Step 1: 添加脚本 -->
          <div v-show="currentStep === 1" class="task-wizard-pane task-wizard-script">
            <ScriptSelectModal
              ref="scriptPickerRef"
              :default-project-id="taskForm.task_project"
              :project-options="projectOptions"
              :already-selected-ids="selectedCaseIds"
              @add="onScriptAdd"
              @remove="removeScript"
            />
            <SelectedScriptTable
              :scripts="selectedScripts"
              @remove="removeScript"
              @update:execute-count="onScriptExecuteCountUpdate"
            />
          </div>

          <!-- Step 2: 环境与数据源信息配置（跨脚本聚合，统一全局环境与数据源） -->
          <div v-show="currentStep === 2" class="task-wizard-pane task-wizard-exec">
            <div v-if="!selectedCaseIds.length" class="exec-empty">请先在「脚本与执行次数配置」步骤选择至少一个脚本</div>
            <div v-else class="exec-config-wrap">
              <ExecConfigModal
                :key="selectedCaseIds.join(',')"
                embedded
                :case-ids="selectedCaseIds"
                :project-options="projectOptions"
                :saved-configs="casesExecuteConfig"
                @update:configs="onCasesExecConfigsUpdate"
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="task-wizard-footer">
          <NButton @click="handleClose">取消</NButton>
          <NSpace>
            <NButton v-if="currentStep > 0" @click="goPrev">上一步</NButton>
            <NButton v-if="currentStep < LAST_STEP" type="primary" @click="goNext">下一步</NButton>
            <NButton
              v-if="currentStep === LAST_STEP"
              type="primary"
              :loading="modalLoading"
              @click="handleSubmit"
            >
              确定
            </NButton>
          </NSpace>
        </div>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped>
.task-wizard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 160px);
}

.task-wizard-header {
  flex-shrink: 0;
  width: 100%;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--n-border-color);
}

/* Steps 根节点即 .n-steps，占满抽屉内容区宽度 */
.task-wizard-steps {
  width: 100% !important;
  display: flex !important;
  box-sizing: border-box;
}

/* 前两步拉伸，连接线吃掉中间空白 */
.task-wizard-steps :deep(.n-step) {
  flex: 1 1 0 !important;
  min-width: 0;
}

/* 最后一步按内容宽度贴右，消除标题后的空白 */
.task-wizard-steps :deep(.n-step:last-child) {
  flex: 0 0 auto !important;
  justify-content: flex-end;
}

.task-wizard-steps :deep(.n-step-content-header__title) {
  white-space: normal;
  line-height: 1.35;
}

.task-wizard-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.task-wizard-pane {
  min-height: 320px;
}

.task-wizard-merged {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 基本信息折叠卡片：行高/间距对齐「数据库请求」步骤页配置项（.db-op-* 同款） */
.basic-card :deep(.n-card__content) {
  padding: 12px 16px;
}

.basic-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.basic-form :deep(.n-form-item-label) {
  padding-bottom: 0;
  white-space: nowrap;
}

.basic-field-rows {
  display: flex;
  flex-direction: column;
}

.basic-field-row {
  width: 100%;
}

.basic-field-row--cols3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.basic-field-row--cols1 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  align-items: start;
}

.basic-field-rows .basic-field-row + .basic-field-row {
  margin-top: 12px;
}

.basic-field-row :deep(.n-form-item) {
  min-width: 0;
}

.basic-fi-fill :deep(.n-input),
.basic-fi-fill :deep(.n-select) {
  width: 100%;
}

.task-wizard-script {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.task-wizard-script :deep(.task-script-collapse + .task-script-collapse) {
  margin-top: 8px;
}

.task-wizard-exec {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.exec-config-wrap {
  min-height: 280px;
}

.exec-empty {
  padding: 40px;
  text-align: center;
  color: var(--n-text-color-3);
}

.task-wizard-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

@media (max-width: 860px) {
  .basic-field-row--cols3 {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.task-form-drawer-content .n-drawer-body-content-wrapper {
  padding-bottom: 8px;
}
</style>
