<script setup>
/**
 * 新增/编辑任务 — 三步向导
 * 0 任务与调度信息配置 → 1 脚本与执行次数配置 → 2 环境与数据源信息配置
 */
import { computed, nextTick, ref, watch } from 'vue'
import {
  NButton,
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
} from 'naive-ui'
import { useUserStore } from '@/store'
import api from '@/api'
import ExecConfigModal from '@/views/autotest/steps/components/ExecConfigModal.vue'
import CronGenerator from './CronGenerator.vue'
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

const taskForm = ref(createEmptyForm())
const cronRunMode = ref('once')
const cronGeneratorRef = ref(null)

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
    task_crontabs_expr: '',
    task_periodic_expr: '执行1次',
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

function onCronGeneratorChange(result) {
  if (!result?.ok) return
  taskForm.value.task_crontabs_expr = result.task_crontabs_expr || ''
  if (result.task_periodic_expr) {
    taskForm.value.task_periodic_expr = result.task_periodic_expr
  }
  if (result.runMode) cronRunMode.value = result.runMode
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

  const resolved = cronGeneratorRef.value?.resolveSchedule?.()
  if (resolved?.ok) {
    taskForm.value.task_crontabs_expr = resolved.task_crontabs_expr || ''
    if (resolved.task_periodic_expr) {
      taskForm.value.task_periodic_expr = resolved.task_periodic_expr
    }
    if (resolved.runMode) cronRunMode.value = resolved.runMode
    return true
  }
  if (!taskForm.value.task_crontabs_expr?.trim()) {
    window.$message?.warning?.(resolved?.error || '请配置 Crontab 表达式')
    return false
  }
  return true
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
  cronRunMode.value = 'once'
  selectedScripts.value = []
  casesExecuteConfig.value = {}
  scriptPickerRef.value?.collapse?.()
  cronGeneratorRef.value?.reset?.()
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
      task_crontabs_expr: d.task_crontabs_expr || '',
      task_periodic_expr: d.task_periodic_expr || '执行N次',
    }

    if (d.task_periodic_expr === '执行1次') {
      cronRunMode.value = 'once'
    } else if (d.task_periodic_expr === '执行N次') {
      cronRunMode.value = 'repeat'
    } else {
      // 兼容旧数据：曾用 datetime 表示执行1次
      cronRunMode.value = d.task_scheduler === 'datetime' ? 'once' : 'repeat'
      taskForm.value.task_periodic_expr =
        cronRunMode.value === 'once' ? '执行1次' : '执行N次'
    }
    if (d.task_crontabs_expr) {
      await nextTick()
      cronGeneratorRef.value?.applyFromExpr?.(d.task_crontabs_expr)
    }

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
    }
    if (Array.isArray(prevKwargs.initial_variables)) {
      taskKwargsPayload.initial_variables = prevKwargs.initial_variables
    }

    const payload = {
      task_name: taskForm.value.task_name.trim(),
      task_desc: taskForm.value.task_desc || null,
      task_type: taskForm.value.task_type || 'autotest_api',
      task_project: taskForm.value.task_project,
      task_notify: Array.isArray(taskForm.value.task_notify) ? taskForm.value.task_notify : null,
      task_notifier: Array.isArray(taskForm.value.task_notifier) ? taskForm.value.task_notifier : null,
      task_kwargs: taskKwargsPayload,
      cases_execute_config: casesCfgPayload,
      task_crontabs_expr: taskForm.value.task_crontabs_expr || null,
      task_periodic_expr: taskForm.value.task_periodic_expr || '执行N次',
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
            <section class="merge-section">
              <header class="merge-section-head">
                <span class="merge-section-title">基本信息</span>
              </header>
              <div class="merge-section-body">
                <NForm label-placement="left" label-width="88" size="small" class="basic-form">
                  <div class="basic-form-grid">
                    <NFormItem label="任务名称" required class="basic-form-item">
                      <NInput
                        v-model:value="taskForm.task_name"
                        placeholder="请输入任务名称"
                        clearable
                      />
                    </NFormItem>
                    <NFormItem label="所属应用" required class="basic-form-item">
                      <NSelect
                        v-model:value="taskForm.task_project"
                        :options="projectOptions"
                        :loading="projectLoading"
                        clearable
                        filterable
                        placeholder="请选择所属应用"
                      />
                    </NFormItem>
                  </div>
                  <div class="basic-form-grid">
                    <NFormItem label="任务描述" class="basic-form-item">
                      <NInput
                        v-model:value="taskForm.task_desc"
                        placeholder="请输入任务描述（可选）"
                        clearable
                      />
                    </NFormItem>
                    <NFormItem label="任务通知" class="basic-form-item">
                      <NDynamicTags v-model:value="taskForm.task_notifier" />
                    </NFormItem>
                  </div>
                </NForm>
              </div>
            </section>

            <section class="merge-section merge-section--schedule">
              <header class="merge-section-head">
                <span class="merge-section-title">调度配置</span>
              </header>
              <div class="merge-section-body merge-section-body--cron">
                <CronGenerator
                  ref="cronGeneratorRef"
                  v-model="taskForm.task_crontabs_expr"
                  v-model:run-mode="cronRunMode"
                  @change="onCronGeneratorChange"
                />
              </div>
            </section>
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

.merge-section {
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color);
  overflow: hidden;
}

.merge-section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid var(--n-border-color);
}

.merge-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.merge-section-body {
  padding: 12px 14px 4px;
}

.merge-section--schedule {
  border: none;
  background: transparent;
  overflow: visible;
}

.merge-section--schedule .merge-section-head {
  padding: 2px 2px 8px;
  background: transparent;
  border-bottom: none;
}

.merge-section-body--cron {
  padding: 0;
}

.basic-form :deep(.n-form-item) {
  margin-bottom: 12px;
}

.basic-form :deep(.n-form-item-label) {
  white-space: nowrap;
}

.basic-form :deep(.n-form-item-label__text) {
  white-space: nowrap;
}

.basic-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.basic-form-item {
  min-width: 0;
}

.basic-form-item :deep(.n-form-item-blank) {
  min-width: 0;
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
  .basic-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.task-form-drawer-content .n-drawer-body-content-wrapper {
  padding-bottom: 8px;
}
</style>
