<template>
  <AppPage>
    <CaseInfoPanel
        ref="caseInfoPanelRef"
        :run-loading="runLoading"
        :debug-loading="debugLoading"
        :save-loading="saveLoading"
        @case-type-change="onCaseTypeChange"
        @run="handleRun"
        @debug="handleDebug"
        @save="handleSaveAll"
    />
    <div class="page-container">
      <div class="steps-split-layout">
        <div class="left-column" :style="{ width: `${leftPanelWidth}px` }">
          <n-card size="small" hoverable class="step-card">
            <template #header>
              <div class="step-header">
                <span class="step-count">{{ totalStepsCount }}个步骤</span>
                <n-button
                    text
                    size="small"
                    @click="toggleAllExpand"
                    :title="isAllExpanded ? '折叠所有步骤' : '展开所有步骤'"
                >
                  <template #icon>
                    <TheIcon
                        :icon="isAllExpanded ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"/>
                  </template>
                </n-button>
              </div>
            </template>
            <div class="step-tree-container">
              <template v-for="(step, index) in steps" :key="step.id">
                <div
                    class="step-item"
                    :class="{
                    'is-selected': selectedKeys.includes(step.id),
                    'is-drag-target': dragState.draggingId && stepDefinitions[step.type]?.allowChildren, // 所有 loop/if 步骤的普通高亮
                    'is-drag-over': dragState.dragOverId === step.id && stepDefinitions[step.type]?.allowChildren // 焦点高亮
                  }"
                    :draggable="true"
                    @dragstart="handleDragStart($event, step.id, null, index)"
                    @dragover.prevent="handleDragOver($event, step.id, null)"
                    @dragleave="handleDragLeave($event, step.id)"
                    @drop="handleDrop($event, step.id, null, index)"
                    @click="handleSelect([step.id])"
                >
                  <div class="step-item-distance">
                    <!-- 父级步骤名称-->
                    <span class="step-name" :title="step.name">
                    <TheIcon
                        :icon="getStepIcon(step.type)"
                        :size="16"
                        class="step-icon"
                        :class="getStepIconClass(step.type)"
                    />
                    <span class="step-name-text">{{ getStepDisplayName(step.name, step.id) }}</span>
                    <span class="step-actions">
                      <span class="step-number">#{{ getStepNumber(step.id) }}</span>
                      <n-button
                          v-if="stepDefinitions[step.type]?.allowChildren"
                          text
                          size="tiny"
                          @click.stop="toggleStepExpand(step.id, $event)"
                          class="action-btn"
                          :title="isStepExpanded(step.id) ? '折叠当前步骤' : '展开当前步骤'"
                      >
                        <template #icon>
                          <TheIcon
                              :icon="isStepExpanded(step.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"
                              :size="14"
                          />
                        </template>
                      </n-button>
                      <n-button
                          text
                          size="tiny"
                          @click.stop="handleCopyStep(step.id)"
                          class="action-btn"
                          title="复制当前步骤"
                      >
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="14"/>
                        </template>
                      </n-button>
                      <n-popconfirm @positive-click="handleDeleteStep(step.id)" @click.stop>
                        <template #trigger>
                          <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                            <template #icon>
                              <TheIcon icon="material-symbols:delete" :size="14"/>
                            </template>
                          </n-button>
                        </template>
                        确认删除该步骤?
                      </n-popconfirm>
                    </span>
                  </span>
                    <RecursiveStepChildren
                        v-if="stepDefinitions[step.type]?.allowChildren"
                        :step="step"
                    />
                    <!-- 引用步骤：展示公共脚本内的步骤（只读、递归子级，不参与保存） -->
                    <div v-if="step.type === 'quote'" class="quote-inner-steps">
                      <div class="quote-inner-list">
                        <div
                            v-for="(item, idx) in getQuoteStepsFlattened(quoteStepsMap[step.id] || [])"
                            :key="'quote-' + step.id + '-' + idx + '-' + (item.step.id || '')"
                            class="step-item quote-inner-item"
                            :class="{ 'is-selected': selectedKeys.includes(getQuoteInnerKey(step.id, idx)) }"
                            :style="{ marginLeft: (item.depth * 10) + 'px' }"
                            @click.stop="handleSelect([getQuoteInnerKey(step.id, idx)])"
                        >
                          <span class="step-name">
                            <TheIcon
                                :icon="getStepIcon(item.step.type)"
                                :size="16"
                                class="step-icon"
                                :class="getStepIconClass(item.step.type)"
                            />
                            <span class="step-name-text">{{ item.step.name || '步骤' }}</span>
                            <span class="step-number">#{{ idx + 1 }}</span>
                          </span>
                        </div>
                        <div v-if="!getQuoteStepsFlattened(quoteStepsMap[step.id] || []).length" class="quote-inner-empty">暂无步骤</div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
              <AddStepPopover
                  :is-public-script-case="isPublicScriptCase"
                  @select="(key) => handleAddStep(key, null)"
              />
            </div>
          </n-card>
        </div>
        <div
            class="steps-split-resizer"
            title="拖动调整步骤树宽度"
            @mousedown="startResizeLeftPanel"
        />
        <div class="right-column steps-split-main">
          <n-card size="small" hoverable class="config-card">
            <component
                v-if="currentStep"
                :key="currentStep.id + (currentStep.isQuoteInner ? '-readonly' : '')"
                :is="editorComponent"
                v-bind="editorComponentProps"
                @update:config="(val) => { if (!currentStep?.isQuoteInner) updateStepConfig(currentStep.id, val) }"
            />
            <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
          </n-card>
        </div>
      </div>
    </div>

    <ScriptSelectDrawer
        ref="scriptSelectDrawerRef"
        v-model:show="quotePublicScriptDrawerVisible"
        v-model:query-items="quotePublicScriptQueryItems"
        :script-drawer-mode="scriptDrawerMode"
        :columns="quotePublicScriptColumns"
        :get-data="getScriptListForDrawer"
        :case-type-options-for-copy="caseTypeOptionsForCopy"
        :selected-for-copy="selectedForCopy"
        @confirm-copy="confirmCopySteps"
    />

    <ExecConfigModal
        ref="execConfigModalRef"
        v-model:run-loading="runLoading"
        v-model:debug-loading="debugLoading"
    />
  </AppPage>
</template>

<script setup>
/**
 * index.vue — API 自动化「步骤编辑」页编排层
 *
 * 本文件：左侧步骤树、右侧动态编辑器、步骤树 CRUD、前后端映射、保存/加载。
 * CaseInfoPanel：用例信息；ExecConfigModal：执行/调试配置；ScriptSelectDrawer：选脚本；AddStepPopover：添加步骤菜单。
 */
defineOptions({ name: '步骤编辑' })
import {computed, defineComponent, h, nextTick, onMounted, onUnmounted, ref, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {
  NButton,
  NCard,
  NCheckbox,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NSpin,
  NTag,
  NTooltip,
  useMessage
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {formatDateTime, renderIcon} from '@/utils'
import AppPage from "@/components/page/AppPage.vue";
import CaseInfoPanel from './components/CaseInfoPanel.vue'
import ScriptSelectDrawer from './components/ScriptSelectDrawer.vue'
import ExecConfigModal from './components/ExecConfigModal.vue'
import AddStepPopover from './components/AddStepPopover.vue'
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiTcpEditor from "@/views/autotest/tcp_controller/index.vue";
import ApiDatabaseEditor from "@/views/autotest/database_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";
import ApiUserVariablesEditor from "@/views/autotest/user_variables_controller/index.vue";
import ApiQuoteEditor from "@/views/autotest/quote_controller/index.vue";
import api from "@/api";
import { mapBackendStep, forEachStep } from './utils/stepTreeMap'
import { resolveCaseIdFromSteps, toPositiveCaseId } from './utils/prepareCaseExecute'
import { useAutotestSavedCaseRun } from '@/composables/useAutotestSavedCaseRun'
import {useUserStore, useAutotestStore} from '@/store';

const message = useMessage()
/** 统一错误提示：优先全局 $message，否则 naive useMessage */
const notifyError = (msg) => {
  if (typeof window !== 'undefined' && typeof window.$message?.error === 'function') {
    window.$message.error(msg)
  } else {
    message.error(msg)
  }
}

// 顺序与 backend/enums/autotest_enum.py AutoTestStepType 一致
const stepDefinitions = {
  user_variables: {label: '用户变量', allowChildren: false, icon: 'gravity-ui:magic-wand'},
  if: {label: '条件分支', allowChildren: true, icon: 'gravity-ui:shuffle'},
  wait: {label: '等待控制', allowChildren: false, icon: 'gravity-ui:stopwatch'},
  loop: {label: '循环结构', allowChildren: true, icon: 'gravity-ui:arrows-rotate-right'},
  tcp: {label: 'TCP请求', allowChildren: false, icon: 'streamline-freehand:server-api-cloud'},
  http: {label: 'HTTP请求', allowChildren: false, icon: 'streamline-freehand:server-api-cloud'},
  code: {label: '代码请求(Python)', allowChildren: false, icon: 'ph:file-py'},
  database: {label: '数据库请求', allowChildren: false, icon: 'ph:file-sql'},
  quote: {label: '引用公共脚本', allowChildren: false, icon: 'gravity-ui:link'},
}

const STEP_ICON = {
  user_variables: 'gravity-ui:magic-wand',
  http: 'streamline-freehand-color:server-api-cloud',
  tcp: 'streamline-freehand-color:server-api-cloud',
  code: 'ph:file-py',
  database: 'ph:file-sql',
  wait: 'gravity-ui:stopwatch',
  if: 'gravity-ui:shuffle',
  loop: 'gravity-ui:arrows-rotate-right',
  quote_public_script: 'gravity-ui:link',
}
const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  tcp: ApiTcpEditor,
  http: ApiHttpEditor,
  database: ApiDatabaseEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor,
  user_variables: ApiUserVariablesEditor,
  quote: ApiQuoteEditor,
}

let seed = 1000
/** 生成前端步骤唯一 id（保存前无后端 step_code 时使用） */
const genId = () => `step-${seed++}`

const steps = ref([])
const selectedKeys = ref([])
const route = useRoute()
const router = useRouter()
const autotestStore = useAutotestStore()
const caseId = computed(() => route.query.case_id || null)
const caseCode = computed(() => route.query.case_code || null)

/** 用例信息子组件 ref：表单、校验、项目列表 */
const caseInfoPanelRef = ref(null)
/** 执行/调试环境配置弹窗 ref */
const execConfigModalRef = ref(null)
/** 引用/复制脚本抽屉 ref */
const scriptSelectDrawerRef = ref(null)

/** 左侧步骤树面板宽度（可拖拽调整，持久化到 localStorage） */
const LEFT_PANEL_WIDTH_STORAGE_KEY = 'autotest-steps-left-panel-width'
const LEFT_PANEL_WIDTH_DEFAULT = 350
const LEFT_PANEL_WIDTH_MIN = 200
const LEFT_PANEL_WIDTH_MAX = 600

const leftPanelWidth = ref(LEFT_PANEL_WIDTH_DEFAULT)

function clampLeftPanelWidth(width) {
  return Math.min(LEFT_PANEL_WIDTH_MAX, Math.max(LEFT_PANEL_WIDTH_MIN, width))
}

function loadLeftPanelWidth() {
  try {
    const raw = localStorage.getItem(LEFT_PANEL_WIDTH_STORAGE_KEY)
    if (raw == null) return
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) return
    leftPanelWidth.value = clampLeftPanelWidth(parsed)
  } catch {
    /* ignore */
  }
}

function saveLeftPanelWidth() {
  try {
    localStorage.setItem(LEFT_PANEL_WIDTH_STORAGE_KEY, String(leftPanelWidth.value))
  } catch {
    /* ignore */
  }
}

let resizeLeftPanelStartX = 0
let resizeLeftPanelStartWidth = LEFT_PANEL_WIDTH_DEFAULT

function onResizeLeftPanelMove(event) {
  leftPanelWidth.value = clampLeftPanelWidth(
      resizeLeftPanelStartWidth + event.clientX - resizeLeftPanelStartX
  )
}

function stopResizeLeftPanel() {
  saveLeftPanelWidth()
  document.removeEventListener('mousemove', onResizeLeftPanelMove)
  document.removeEventListener('mouseup', stopResizeLeftPanel)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

function startResizeLeftPanel(event) {
  if (event.button !== 0) return
  resizeLeftPanelStartX = event.clientX
  resizeLeftPanelStartWidth = leftPanelWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onResizeLeftPanelMove)
  document.addEventListener('mouseup', stopResizeLeftPanel)
}

/** 右侧步骤编辑器使用的「所属应用」选项（来自 CaseInfoPanel） */
const editorProjectOptions = computed(() => {
  const p = caseInfoPanelRef.value?.projectOptions
  return p?.value ?? p ?? []
})
const editorProjectLoading = computed(() => {
  const p = caseInfoPanelRef.value?.projectLoading
  return p?.value ?? p ?? false
})

/** 当前用例是否为「公共脚本」（禁用树内「引用公共脚本」入口） */
const isPublicScriptCase = computed(() => caseInfoPanelRef.value?.getCaseForm?.()?.case_type === '公共脚本')


const scriptDrawerMode = ref('quote')
const quotePublicScriptDrawerVisible = ref(false)
const quotePublicScriptParentId = ref(null)
const quotePublicScriptReplaceStepId = ref(null)
// 引用步骤内展示的公共脚本步骤（仅展示，不参与保存）：quoteStepId -> 前端树节点数组
const quoteStepsMap = ref({})
// 从「用户脚本」切到「公共脚本」时暂存的引用步骤，切回「用户脚本」时可恢复
const stashedQuoteStepsWhenPublic = ref([])
// 复制模式：已选待复制的用例列表
const selectedForCopy = ref([])
const quotePublicScriptQueryItems = ref({
  case_name: '',
  case_type: '公共脚本',
  created_user: ''
})

// 复制模式用例类型选项（支持全部、公共脚本、用户脚本）
const caseTypeOptionsForCopy = [
  { label: '全部', value: '' },
  { label: '公共脚本', value: '公共脚本' },
  { label: '用户脚本', value: '用户脚本' }
]

// 请求前规范化入参：quote 模式仅查公共脚本；copy 模式支持 case_type（全部/公共/用户），并排除当前用例（不可复制自己）
const getScriptListForDrawer = (params) => {
  const body = {...params}
  if (scriptDrawerMode.value === 'quote') {
    body.case_type = '公共脚本'
  }
  if (scriptDrawerMode.value === 'copy' && caseId.value) {
    body.exclude_case_id = Number(caseId.value)
  }
  if (body.case_name === '') delete body.case_name
  if (body.created_user === '') delete body.created_user
  if (body.case_type === '') delete body.case_type
  return api.getApiTestcaseList(body)
}
/** 从脚本选择抽屉行构造引用脚本用例快照，供右侧「用例信息」只读展示（与步骤树接口 quote_case 字段对齐） */
const snapshotQuoteCaseFromScriptRow = (row) => {
  if (!row || row.case_id == null) return null
  return {
    case_id: row.case_id,
    case_code: row.case_code,
    case_name: row.case_name || '',
    case_project: row.case_project,
    case_tags: row.case_tags,
    case_desc: row.case_desc || '',
    case_attr: row.case_attr || '',
    case_type: row.case_type || ''
  }
}

/** 引用模式：选中公共脚本后插入或替换 quote 步骤 */
const onSelectPublicScript = (row) => {
  const replaceId = quotePublicScriptReplaceStepId.value
  const quoteCaseSnapshot = snapshotQuoteCaseFromScriptRow(row)
  const config = { quote_case_id: row.case_id, step_name: row.case_name || '引用公共脚本' }
  if (replaceId) {
    updateStepConfig(replaceId, config)
    const updated = findStep(replaceId)
    if (updated) {
      updated.original = { ...(updated.original || {}), quote_case: quoteCaseSnapshot }
      loadQuoteStepsForStep(updated)
    }
    quotePublicScriptReplaceStepId.value = null
  } else {
    const parentId = quotePublicScriptParentId.value
    const created = insertStep(parentId, 'quote', null, config)
    if (created) {
      created.original = { ...(created.original || {}), quote_case: quoteCaseSnapshot }
      selectedKeys.value = [created.id]
      updateStepDisplayNames()
      loadQuoteStepsForStep(created)
    }
    quotePublicScriptParentId.value = null
  }
  quotePublicScriptDrawerVisible.value = false
}

// 复制模式：将用例加入待复制列表
const addToCopySelection = (row) => {
  if (selectedForCopy.value.some((r) => r.case_id === row.case_id)) return
  selectedForCopy.value = [...selectedForCopy.value, row]
}

// 复制模式：从待复制列表移除
const removeFromCopySelection = (row) => {
  selectedForCopy.value = selectedForCopy.value.filter((r) => r.case_id !== row.case_id)
}

/**
 * 【步骤明细「复制指定脚本」】确认复制：调用 copyCaseStepTree 获取 steps 并插入当前用例步骤树
 *
 * 与用例管理「复制」的区别：
 *   - 本功能：仅使用 steps，将步骤插入当前正在编辑的用例步骤树中（多选可插入多个脚本的步骤）
 *   - 用例管理「复制」：使用 case + steps，创建新用例编辑页（路由跳转）
 *
 * 实现原理：
 * 1. 对每个选中的脚本调用 copyCaseStepTree(case_id)（与用例管理「复制」共用同一后端接口）
 * 2. 仅使用返回的 steps，忽略 case（用例信息来自当前编辑页）
 * 3. mapBackendStep 将后端步骤转为前端树节点格式
 * 4. insertStepFromMapped 将步骤插入到 parentId 下或根级
 */
const confirmCopySteps = async () => {
  const rows = selectedForCopy.value
  if (!rows.length) {
    window.$message?.warning?.('请至少选择一个脚本')
    return
  }
  const parentId = quotePublicScriptParentId.value
  let insertedCount = 0
  let lastInsertedId = null
  try {
    for (const row of rows) {
      const res = await api.copyCaseStepTree({ case_id: row.case_id })
      const stepsData = res?.data?.steps || res?.steps || []
      const mapped = stepsData.map(mapBackendStep).filter(Boolean)
      for (const step of mapped) {
        insertStepFromMapped(parentId, step)
        lastInsertedId = step.id
        insertedCount++
      }
    }
    if (insertedCount > 0) {
      updateStepDisplayNames()
      loadQuoteStepsForAllQuoteSteps()
      if (lastInsertedId) selectedKeys.value = [lastInsertedId]
      window.$message?.success?.(`已复制${insertedCount}个步骤`)
    }
    quotePublicScriptDrawerVisible.value = false
    selectedForCopy.value = []
  } catch (error) {
    console.error('复制步骤失败', error)
    window.$message?.error?.(error?.message || error?.data?.message || '复制失败')
  }
}

/**
 * 将 mapBackendStep 后的步骤插入当前用例的步骤树（含子步骤、展开状态）
 * 用于「复制指定脚本」：将后端 strip 后的步骤转为前端格式后插入
 */
const insertStepFromMapped = (parentId, mappedStep) => {
  if (stepDefinitions[mappedStep.type]?.allowChildren) {
    stepExpandStates.value.set(mappedStep.id, true)
  }
  if (parentId) {
    const parent = findStep(parentId)
    if (parent && stepDefinitions[parent.type]?.allowChildren) {
      parent.children = parent.children || []
      parent.children.push(mappedStep)
    }
  } else {
    steps.value.push(mappedStep)
  }
}

/** 引用步骤「重新选择」：打开公共脚本抽屉并记录待替换步骤 id */
const handleQuoteReselect = () => {
  if (!currentStep.value?.id) return
  scriptDrawerMode.value = 'quote'
  quotePublicScriptReplaceStepId.value = currentStep.value.id
  quotePublicScriptParentId.value = null
  quotePublicScriptQueryItems.value.case_type = '公共脚本'
  quotePublicScriptDrawerVisible.value = true
}

watch(quotePublicScriptDrawerVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      scriptSelectDrawerRef.value?.handleSearch?.()
    })
  }
})

/** 选择公共脚本 / 复制脚本 抽屉表格「所属标签」：单行展示，悬停看全部 */
const renderQuoteDrawerCaseTagsCompact = (row) => {
  const tags = Array.isArray(row.case_tags) ? row.case_tags.filter((t) => t && t.tag_name) : []
  if (!tags.length) return h('span', '')
  const trigger = h(
      'div',
      {
        class: 'case-tags-cell-trigger',
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          maxWidth: '100%',
          minHeight: '22px'
        }
      },
      [
        h(NTag, {type: 'info', size: 'small', bordered: true}, {default: () => tags[0].tag_name}),
        tags.length > 1
            ? h('span', {class: 'case-tags-more'}, `+${tags.length - 1}`)
            : null
      ].filter(Boolean)
  )
  if (tags.length === 1) return trigger
  return h(NTooltip, {placement: 'top', trigger: 'hover', showArrow: true}, {
    trigger: () => trigger,
    default: () =>
        h(
            'div',
            {class: 'case-tags-tooltip-inner'},
            tags.map((tag) =>
                h(NTag, {type: 'info', size: 'small', bordered: true, style: {margin: '2px'}}, {default: () => tag.tag_name})
            )
        )
  })
}

const quotePublicScriptColumns = [
  {
    title: '所属应用',
    key: 'case_project',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      // case_project 现在是对象，显示 project_name
      return h('span', row.case_project?.project_name || '')
    },
  },
  {
    title: '所属标签',
    key: 'case_tags',
    width: 150,
    align: 'center',
    render(row) {
      return renderQuoteDrawerCaseTagsCompact(row)
    },
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例属性',
    key: 'case_attr',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例类型',
    key: 'case_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例步骤',
    key: 'case_steps',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例版本',
    key: 'case_version',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time))
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render: (row) => {
      if (scriptDrawerMode.value === 'copy') {
        const isSelected = selectedForCopy.value.some((r) => r.case_id === row.case_id)
        return h(NButton, {
          size: 'small',
          type: isSelected ? 'default' : 'primary',
          onClick: () => isSelected ? removeFromCopySelection(row) : addToCopySelection(row)
        }, {default: () => isSelected ? '移除' : '加入'})
      }
      return h(NButton, {
        size: 'small',
        type: 'primary',
        onClick: () => onSelectPublicScript(row)
      }, {default: () => '选择'})
    }
  }
]


/** 用例类型切换：公共脚本时处理引用步骤的移除/暂存/恢复（与步骤树耦合，保留在编排层） */
const onCaseTypeChange = ({ newType, oldType }) => {
  if (newType === '公共脚本') {
    const fromUserScript = oldType === '用户脚本'
    if (fromUserScript) {
      const toStash = collectQuoteStepsWithPosition()
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        stashedQuoteStepsWhenPublic.value = toStash
        window.$message?.warning?.(`切换为公共脚本，已临时移除${removedCount}个引用公共脚本步骤，若误操作可切回用户脚本恢复`)
      }
    } else {
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        window.$message?.warning?.(`切换为公共脚本，已自动移除${removedCount}个引用公共脚本步骤，公共脚本不允许引用其他脚本`)
      }
    }
  } else if (newType === '用户脚本' && stashedQuoteStepsWhenPublic.value.length > 0) {
    const restoredCount = restoreStashedQuoteSteps()
    if (restoredCount > 0) {
      window.$message?.info?.(`已恢复${restoredCount}个引用公共脚本步骤`)
    }
  }
}

const runLoading = ref(false)
const debugLoading = ref(false)
const saveLoading = ref(false)
const { runSavedCase } = useAutotestSavedCaseRun(execConfigModalRef, runLoading)

/** 与后端 AutoTestStepTreeExecute.case_id 一致：优先路由 case_id，否则从步骤树 original 递归解析 */
const resolveNumericCaseIdForExecuteApi = () => {
  const fromRoute = toPositiveCaseId(caseId.value)
  if (fromRoute != null) return fromRoute
  return resolveCaseIdFromSteps(steps.value, null)
}

const dragState = ref({
  draggingId: null,
  dragOverId: null, // 当前拖拽进入的 loop/if 步骤 ID（焦点高亮）
  dragOverParent: null,
  dragOverIndex: null,
  insertPosition: null, // 'before' | 'after' | null，用于指示插入位置
  insertTargetId: null // 插入目标步骤 ID（用于显示指示器）
})

// 计算总步骤数（包括子步骤）
const totalStepsCount = computed(() => {
  const countSteps = (list) => {
    let count = 0
    for (const step of list) {
      count++
      if (step.children && step.children.length) {
        count += countSteps(step.children)
      }
    }
    return count
  }
  return countSteps(steps.value)
})

// 判断是否全部展开（简化处理，这里假设总是展开的）
const isAllExpanded = ref(true)

/** 展开/折叠全部可展开步骤 */
const toggleAllExpand = () => {
  // 切换全局展开/折叠状态
  isAllExpanded.value = !isAllExpanded.value

  // 批量设置所有步骤的展开状态为全局状态
  const setAllStepsExpandState = (list, state) => {
    for (const step of list) {
      if (stepDefinitions[step.type]?.allowChildren) {
        stepExpandStates.value.set(step.id, state)
        if (step.children && step.children.length) {
          setAllStepsExpandState(step.children, state)
        }
      }
    }
  }

  setAllStepsExpandState(steps.value, isAllExpanded.value)
}

// 存储每个步骤的展开/折叠状态
const stepExpandStates = ref(new Map())

// 获取步骤的展开状态（默认为true，即展开）
const isStepExpanded = (stepId) => {
  if (!stepExpandStates.value.has(stepId)) {
    // 如果还没有设置过，默认展开
    stepExpandStates.value.set(stepId, true)
  }
  return stepExpandStates.value.get(stepId)
}

// 切换单个步骤的展开/折叠状态
const toggleStepExpand = (stepId, event) => {
  event?.stopPropagation()
  const currentState = stepExpandStates.value.get(stepId) ?? true
  stepExpandStates.value.set(stepId, !currentState)
}

// 初始化所有允许子步骤的步骤的展开状态（默认为展开）
const initializeStepExpandStates = () => {
  const initializeStates = (list) => {
    for (const step of list) {
      if (stepDefinitions[step.type]?.allowChildren) {
        if (!stepExpandStates.value.has(step.id)) {
          stepExpandStates.value.set(step.id, true)
        }
        if (step.children && step.children.length) {
          initializeStates(step.children)
        }
      }
    }
  }
  initializeStates(steps.value)
}

/** 在步骤树中按 id 查找步骤（含 children 递归） */
const findStep = (id, list = steps.value) => {
  for (const step of list) {
    if (step.id === id) return step
    if (step.children && step.children.length) {
      const found = findStep(id, step.children)
      if (found) return found
    }
  }
  return null
}

/** 查找步骤的父节点；根级步骤返回 null */
const findStepParent = (id, list = steps.value, parent = null) => {
  for (const step of list) {
    if (step.id === id) return parent
    if (step.children && step.children.length) {
      const found = findStepParent(id, step.children, step)
      if (found !== null) return found
    }
  }
  return null
}

/**
 * 前序遍历步骤树，对每个步骤执行 fn（可选：包含「引用公共脚本」加载的内部步骤）。
 * 说明：
 * - 引用脚本内部步骤来自 quoteStepsMap，仅用于聚合/展示，不写入当前用例
 * - 为避免嵌套引用导致循环，这里默认不继续展开「被引用脚本」内部的 quote 步骤
 */
const forEachStepWithQuote = (list, fn, { includeQuoteInner = true } = {}) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children && step.children.length) forEachStepWithQuote(step.children, fn, { includeQuoteInner })
    if (includeQuoteInner && step?.type === 'quote') {
      const inner = quoteStepsMap.value?.[step.id] || []
      if (Array.isArray(inner) && inner.length) {
        // 被引用脚本内部：不再展开其 quote，避免循环引用
        forEachStepWithQuote(inner, fn, { includeQuoteInner: false })
      }
    }
  }
}

/** 加载单个引用步骤对应的公共脚本步骤树（仅用于展示，不写入当前用例） */
const loadQuoteStepsForStep = async (step) => {
  if (step.type !== 'quote' || !step.config?.quote_case_id) {
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
    return
  }
  try {
    const res = await api.getAutoTestStepTree({ case_id: step.config.quote_case_id })
    const data = Array.isArray(res?.data) ? res.data : []
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: data.map(mapBackendStep).filter(Boolean) }
  } catch (e) {
    console.error('加载引用脚本步骤失败', e)
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
  }
}

/** 加载所有引用步骤的公共脚本步骤 */
const loadQuoteStepsForAllQuoteSteps = () => {
  forEachStep(steps.value, (step) => {
    if (step.type === 'quote') loadQuoteStepsForStep(step)
  })
}

/**
 * 等待当前页步骤树中所有「引用公共脚本」的内部步骤加载完成（写入 quoteStepsMap）。
 * 脚本执行配置聚合依赖 quoteStepsMap；若不 await，collectDebugRows 会在引用步骤仍为空的时机执行，导致配置名/IP 等缺失。
 */
const loadQuoteStepsForAllQuoteStepsAsync = async () => {
  const quoteSteps = []
  forEachStep(steps.value, (s) => {
    if (s?.type === 'quote' && s?.config?.quote_case_id) quoteSteps.push(s)
  })
  if (!quoteSteps.length) return
  await Promise.all(quoteSteps.map((s) => loadQuoteStepsForStep(s)))
}

/**
 * 从缓存的 rawData 中提取 quote_steps 填充 quoteStepsMap，避免为每个引用步骤重复请求
 * 用于切换页签使用缓存时，不再调用 loadQuoteStepsForAllQuoteSteps（会触发接口）
 */
const fillQuoteStepsMapFromRawData = (rawList, mappedList) => {
  if (!rawList?.length || !mappedList?.length) return
  for (let i = 0; i < rawList.length; i++) {
    const raw = rawList[i]
    const mapped = mappedList[i]
    if (!raw || !mapped) continue
    if (raw.quote_steps?.length) {
      quoteStepsMap.value = {
        ...quoteStepsMap.value,
        [mapped.id]: raw.quote_steps.map(mapBackendStep).filter(Boolean)
      }
    }
    if (raw.children?.length && mapped.children?.length) {
      fillQuoteStepsMapFromRawData(raw.children, mapped.children)
    }
  }
}

/** 将引用脚本步骤树前序扁平化，得到带层级的列表（用于只读展示，含递归子级） */
const getQuoteStepsFlattened = (list, depth = 0, out = []) => {
  if (!list || !Array.isArray(list)) return out
  for (const step of list) {
    out.push({ step, depth })
    if (step.children && step.children.length) {
      getQuoteStepsFlattened(step.children, depth + 1, out)
    }
  }
  return out
}

const QUOTE_INNER_PREFIX = 'quote-inner:'
/** 生成引用内嵌步骤的虚拟选中 key（quote-inner:...） */
const getQuoteInnerKey = (quoteStepId, flatIndex) => `${QUOTE_INNER_PREFIX}${quoteStepId}:${flatIndex}`
/** 解析虚拟选中 key 为 quoteStepId 与 flatIndex */
const parseQuoteInnerKey = (key) => {
  if (!key || typeof key !== 'string' || !key.startsWith(QUOTE_INNER_PREFIX)) return null
  const rest = key.slice(QUOTE_INNER_PREFIX.length)
  const colon = rest.indexOf(':')
  if (colon === -1) return null
  const quoteStepId = rest.slice(0, colon)
  const flatIndex = parseInt(rest.slice(colon + 1), 10)
  if (Number.isNaN(flatIndex)) return null
  return { quoteStepId, flatIndex }
}

/** 根据 quote-inner key 解析出对应的步骤对象（用于右侧只读展示） */
const getQuoteInnerStep = (key) => {
  const parsed = parseQuoteInnerKey(key)
  if (!parsed) return null
  const list = quoteStepsMap.value[parsed.quoteStepId] || []
  const flat = getQuoteStepsFlattened(list)
  const item = flat[parsed.flatIndex]
  if (!item) return null
  return { ...item.step, isQuoteInner: true }
}

/** 前序遍历步骤树，得到扁平列表（用于计算当前步骤之前的可用变量） */
const flattenStepsPreOrder = (list, out = []) => {
  if (!list || !list.length) return out
  for (const step of list) {
    out.push(step)
    if (step.children && step.children.length) {
      flattenStepsPreOrder(step.children, out)
    }
  }
  return out
}

/** 从单个步骤中收集变量名：session_variables.key、defined_variables.key、extract_variables.name */
const collectVariableNamesFromStep = (step) => {
  const names = []
  if (!step) return names
  const cfg = step.config || {}
  const orig = step.original || {}
  const sv = cfg.session_variables ?? orig.session_variables
  const dv = cfg.defined_variables ?? orig.defined_variables
  const ev = cfg.extract_variables ?? orig.extract_variables
  if (Array.isArray(sv)) {
    sv.forEach((x) => {
      if (x && x.key) names.push(String(x.key).trim())
    })
  }
  if (Array.isArray(dv)) {
    dv.forEach((x) => {
      if (x && x.key) names.push(String(x.key).trim())
    })
  }
  if (Array.isArray(ev)) {
    ev.forEach((x) => {
      if (x && x.name) names.push(String(x.name).trim())
    })
  } else if (ev && typeof ev === 'object') {
    Object.values(ev).forEach((x) => {
      if (x && x.name) names.push(String(x.name).trim())
    })
  }
  const dbOps = cfg.database_operates ?? orig.database_operates
  if (Array.isArray(dbOps)) {
    dbOps.forEach((x) => {
      if (x && x.variable_name) names.push(String(x.variable_name).trim())
    })
  }
  return names
}

const flattenedSteps = computed(() => flattenStepsPreOrder(steps.value))

const currentStepIndex = computed(() => {
  const step = currentStep.value
  if (!step) return -1
  const list = flattenedSteps.value
  const idx = list.findIndex((s) => s.id === step.id)
  return idx
})

/** 当前步骤之前所有步骤中的可用变量名（去重，保持顺序） */
const availableVariableList = computed(() => {
  const list = flattenedSteps.value
  const idx = currentStepIndex.value
  if (idx <= 0) return []
  const seen = new Set()
  const result = []
  for (let i = 0; i < idx; i++) {
    collectVariableNamesFromStep(list[i]).forEach((name) => {
      if (name && !seen.has(name)) {
        seen.add(name)
        result.push(name)
      }
    })
  }
  return result
})

const assistFunctionsList = ref([])

// 将前端类型转换为后端类型
const localTypeToBackend = (localType) => {
  const typeMap = {
    'user_variables': '用户变量',
    'tcp': 'TCP请求',
    'http': 'HTTP请求',
    'code': '代码请求(Python)',
    'if': '条件分支',
    'loop': '循环结构',
    'wait': '等待控制',
    'quote': '引用公共脚本',
    'database': '数据库请求'
  }
  return typeMap[localType] || '代码请求(Python)'
}

// 按照树的前序遍历顺序分配 step_no（确保唯一且按顺序递增）
// 返回一个 Map<step对象, stepNo>，用于在转换时获取正确的 step_no
const assignStepNumbers = (steps) => {
  const stepNoMap = new Map()
  let stepNoCounter = 1

  // 前序遍历函数：先访问节点，再递归访问子节点
  const traverse = (step) => {
    // 访问当前节点，分配 step_no
    stepNoMap.set(step, stepNoCounter++)

    // 递归访问子节点
    if (step.children && step.children.length > 0) {
      step.children.forEach(child => {
        traverse(child)
      })
    }
  }

  // 遍历所有根步骤
  steps.forEach(step => {
    traverse(step)
  })

  return stepNoMap
}

// 键值对列表去空：只保留 key 非空（trim 后）的项，避免 Key 为空时被保存
const filterKeyValueList = (list) => {
  if (!Array.isArray(list)) return []
  return list.filter((item) => item && String(item.key ?? '').trim() !== '')
}

// 将前端步骤格式转换为后端格式
// stepNoMap: Map<step对象, stepNo>，用于获取正确的 step_no
const convertStepToBackend = (step, parentStepId = null, stepNoMap = null) => {
  // 从 stepNoMap 获取 step_no，如果没有则使用默认值
  const stepNo = stepNoMap ? (stepNoMap.get(step) || 1) : 1
  const original = step.original || {}
  const config = step.config || {}

  // 判断是新增还是更新：根据后端逻辑
  // 如果 original.id 和 original.step_code 都存在，则是更新；否则是新增
  // 注意：original.id 对应后端的 step_id（数据库主键），original.step_code 对应后端的 step_code
  const hasStepId = original.id !== undefined && original.id !== null
  const hasStepCode = original.step_code !== undefined && original.step_code !== null && original.step_code !== ''
  const isUpdate = hasStepId && hasStepCode

  // 基础字段（step_desc 优先用 config，来自 HTTP 等编辑器的 emit）
  const backendStep = {
    step_name: step.name || original.step_name || '',
    step_desc: config.step_desc !== undefined ? (config.step_desc ?? '') : (original.step_desc || ''),
    step_type: localTypeToBackend(step.type),
    step_no: stepNo,
    case_id: original.case_id || caseId.value || null,
    parent_step_id: parentStepId,
    quote_case_id: original.quote_case_id || null,
    // case_type 从用例信息中获取，必填字段（新增步骤时）
    case_type: (caseInfoPanelRef.value?.getCaseForm?.()?.case_type) || original.case_type || '用户脚本'
  }

  // 只有更新时才传递 step_id 和 step_code（两个都必须存在）
  // 新增时不传递这两个字段（设置为undefined，让后端排除）
  if (isUpdate) {
    backendStep.step_id = original.id
    backendStep.step_code = original.step_code
  }
  // 新增时不设置 step_id 和 step_code，让它们为 undefined，后端会自动排除

  // 根据类型设置特定字段
  if (step.type === 'tcp') {
    // TCP：应用 + 配置名 + 请求体落库；host/port 由执行/调试时环境配置解析，与 tcp_controller 一致不写 request_url/request_port
    backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
    backendStep.request_config_name = config.request_config_name !== undefined
        ? (config.request_config_name || null)
        : (original.request_config_name || null)
    backendStep.request_url = null
    backendStep.request_port = null

    const payloadRaw = config.request_text != null && String(config.request_text).trim() !== ''
        ? config.request_text
        : (config.request_payload ?? null)
    const payloadTrimmed = payloadRaw != null ? String(payloadRaw).trim() : ''
    backendStep.request_args_type = 'raw'
    backendStep.request_text = payloadTrimmed !== '' ? payloadRaw : null
    backendStep.request_body = null

    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }

    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  }
  if (step.type === 'http') {
    backendStep.request_method = config.method || original.request_method || 'POST'
    backendStep.request_url = config.url || original.request_url || ''
    backendStep.request_args_type = config.request_args_type ?? original.request_args_type ?? 'none'
    backendStep.request_text = config.request_text ?? original.request_text ?? null
    backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
    backendStep.request_config_name = config.request_config_name !== undefined
        ? (config.request_config_name || null)
        : (original.request_config_name || null)
    backendStep.request_header = filterKeyValueList(Array.isArray(config.headers) ? config.headers : (Array.isArray(original.request_header) ? original.request_header : []))
    backendStep.request_params = filterKeyValueList(Array.isArray(config.params) ? config.params : (Array.isArray(original.request_params) ? original.request_params : []))
    backendStep.request_form_data = filterKeyValueList(Array.isArray(config.form_data) ? config.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : []))
    backendStep.request_form_urlencoded = filterKeyValueList(Array.isArray(config.form_urlencoded) ? config.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : []))
    backendStep.request_body = config.data || original.request_body || {}
    backendStep.data_source_name = config.data_source_name !== undefined
        ? (config.data_source_name || null)
        : (original.data_source_name || null)
    backendStep.data_source_desc = config.data_source_desc !== undefined
        ? (config.data_source_desc || null)
        : (original.data_source_desc || null)

    // extract_variables、assert_validators 须为数组，否则为 null
    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }

    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }

    // defined_variables 必须是列表格式，每个元素包含 key、value、desc；Key 为空的项不保存
    backendStep.defined_variables = filterKeyValueList(Array.isArray(config.defined_variables) ? config.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : []))
  } else if (step.type === 'code') {
    backendStep.code = config.code !== undefined ? config.code : (original.code || '')
    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  } else if (step.type === 'loop') {
    // 循环模式必填（与 loop_controller 默认一致）
    backendStep.loop_mode = config.loop_mode || original.loop_mode || '次数循环'
    // 错误处理策略必填（默认与 loop_controller 一致：中断循环）
    backendStep.loop_on_error = config.loop_on_error || original.loop_on_error || '中断循环'
    // 循环间隔（所有模式都需要）
    backendStep.loop_interval = config.loop_interval !== undefined ? Number(config.loop_interval) : (original.loop_interval ? Number(original.loop_interval) : 0)

    // 根据循环模式设置特定字段
    if (backendStep.loop_mode === '次数循环') {
      // 最大循环次数默认 5，与 loop_controller 一致
      backendStep.loop_maximums = config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original.loop_maximums != null ? Number(original.loop_maximums) : 5)
    } else if (backendStep.loop_mode === '列表循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
    } else if (backendStep.loop_mode === '字典循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
    } else if (backendStep.loop_mode === '条件循环') {
      const fromConfigDict = config.conditions && typeof config.conditions === 'object' && !Array.isArray(config.conditions)
          ? config.conditions
          : null
      if (fromConfigDict) {
        backendStep.conditions = {
          condition_expr: fromConfigDict.condition_expr != null ? String(fromConfigDict.condition_expr) : '',
          condition_compare: fromConfigDict.condition_compare || '非空',
          condition_value: fromConfigDict.condition_value != null ? String(fromConfigDict.condition_value) : ''
        }
      } else if (
          config.condition_expr !== undefined ||
          config.condition_compare !== undefined ||
          config.condition_value !== undefined
      ) {
        backendStep.conditions = {
          condition_expr: config.condition_expr != null ? String(config.condition_expr) : '',
          condition_compare: config.condition_compare || '非空',
          condition_value: config.condition_value != null ? String(config.condition_value) : ''
        }
      } else if (original.conditions && typeof original.conditions === 'object' && !Array.isArray(original.conditions)) {
        const oc = original.conditions
        backendStep.conditions = {
          condition_expr: oc.condition_expr != null ? String(oc.condition_expr) : '',
          condition_compare: oc.condition_compare || '非空',
          condition_value: oc.condition_value != null ? String(oc.condition_value) : ''
        }
      } else {
        backendStep.conditions = null
      }
      backendStep.loop_timeout = config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original.loop_timeout ? Number(original.loop_timeout) : 0)
    }
  } else if (step.type === 'if') {
    const fromConfig = config.conditions && typeof config.conditions === 'object' && !Array.isArray(config.conditions)
        ? config.conditions
        : null
    const fromOriginal = original.conditions && typeof original.conditions === 'object' && !Array.isArray(original.conditions)
        ? original.conditions
        : null
    const conditionObj = fromConfig || fromOriginal
    backendStep.conditions = conditionObj
        ? {
          condition_expr: conditionObj.condition_expr != null ? String(conditionObj.condition_expr) : '',
          condition_compare: conditionObj.condition_compare || '非空',
          condition_value: conditionObj.condition_value != null ? String(conditionObj.condition_value) : '',
          condition_desc: conditionObj.condition_desc != null ? String(conditionObj.condition_desc) : ''
        }
        : {
          condition_expr: '',
          condition_compare: '非空',
          condition_value: '',
          condition_desc: ''
        }
  } else if (step.type === 'wait') {
    backendStep.wait = config.seconds || original.wait || 0
  } else if (step.type === 'user_variables') {
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || '')
    backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
    const sv = config.session_variables ?? original.session_variables
    const list = Array.isArray(sv) ? sv : []
    backendStep.session_variables = filterKeyValueList(list.map(item => ({
      key: item.key || '',
      value: item.value ?? '',
      desc: item.desc ?? item.description ?? ''
    })))
  } else if (step.type === 'quote') {
    backendStep.quote_case_id = config.quote_case_id ?? original.quote_case_id ?? null
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
  } else if (step.type === 'database') {
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
    backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
    backendStep.database_searched = !!(config.database_searched ?? original.database_searched)
    const ops = config.database_operates ?? original.database_operates
    backendStep.database_operates = Array.isArray(ops) ? ops : null
    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }
    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  }

  // 处理子步骤（递归处理）
  if (step.children && step.children.length > 0) {
    // 如果是更新，使用当前步骤的id作为父步骤id；如果是新增，先传null，后端会处理
    const parentIdForChildren = isUpdate ? original.id : null
    // 递归转换子步骤，传递 stepNoMap 以获取正确的 step_no
    backendStep.children = step.children.map((child) => {
      return convertStepToBackend(child, parentIdForChildren, stepNoMap)
    })
  }

  // 添加 case 信息（每个步骤都需要包含 case 信息）
  if (original.case) {
    backendStep.case = original.case
  } else {
    const casePayload = caseInfoPanelRef.value?.getCasePayload?.() ?? {}
    backendStep.case = {
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      ...casePayload,
    }
  }

  // 清理字段：确保新增时不传递step_id和step_code，更新时必须同时传递
  // 根据后端逻辑：如果step_id和step_code都不存在，则是新增；如果都存在，则是更新；如果只存在一个，会报错
  const cleanedStep = {}
  for (const key in backendStep) {
    const value = backendStep[key]
    // 如果是新增步骤，完全排除step_id和step_code字段（不添加到cleanedStep中）
    if (!isUpdate && (key === 'step_id' || key === 'step_code')) {
      continue
    }
    // 如果是更新步骤，必须同时有step_id和step_code
    if (isUpdate && (key === 'step_id' || key === 'step_code')) {
      if (value === undefined || value === null) {
        // 更新时如果step_id或step_code为空，跳过（不应该发生）
        continue
      }
    }
    // 保留所有非undefined的值（包括null，因为null可能是有意义的）
    if (value !== undefined) {
      cleanedStep[key] = value
    }
  }

  return cleanedStep
}


// 检查键值对列表中是否存在 key 为空（trim 后）的项
const hasEmptyKeyInList = (list) => {
  if (!Array.isArray(list)) return false
  return list.some((item) => item != null && String(item.key ?? '').trim() === '' && String(item.value ?? '').trim() !== '')
}

/** 与 database_controller 一致：database_operates 可为数组或「序号→行」对象 */
const normalizeDatabaseOperatesList = (ops) => {
  if (ops == null) return []
  if (Array.isArray(ops)) return ops
  if (typeof ops === 'object') {
    const keys = Object.keys(ops).map((k) => parseInt(k, 10)).filter((n) => !isNaN(n)).sort((a, b) => a - b)
    return keys.map((k) => ops[k])
  }
  return []
}

/** 校验数据库步骤配置完整性 */
const validateDatabaseSteps = (stepList) => {
  for (const step of stepList) {
    if (step.type === 'database') {
      const config = step.config || {}
      const original = step.original || {}
      const rawOps = config.database_operates ?? original.database_operates
      const stepName = step.name || original.step_name || '未命名步骤'

      if (rawOps != null && typeof rawOps !== 'object') {
        return {valid: false, message: `步骤：${stepName}，请求配置格式无效，请重新打开步骤编辑或删除后添加`}
      }

      const list = normalizeDatabaseOperatesList(rawOps)
      if (!list.length) {
        return {
          valid: false,
          message: `步骤：${stepName}：请至少添加一条数据库操作`
        }
      }

      for (let i = 0; i < list.length; i++) {
        const o = list[i] || {}
        const idxLabel = `第${i + 1}条`
        const pid = o.project_id
        const hasApp =
            String(o.project_name ?? '').trim() !== ''
            || (pid != null && pid !== '' && String(pid).trim() !== '')
        if (!hasApp) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请选择所属应用`
          }
        }
        if (!String(o.config_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写配置名称`
          }
        }
        if (!String(o.database_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写数据库名称`
          }
        }
        if (!String(o.expr ?? '').trim()) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写SQL语句`
          }
        }
        if (!String(o.variable_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写存储变量`
          }
        }
        const opDisplayName = String(o.name ?? '').trim()
        if (!opDisplayName) {
          return {
            valid: false,
            message: `步骤：${stepName}，${idxLabel}请求配置未完成：请填写操作名称`
          }
        }
      }

      const firstNameIndex = new Map()
      for (let j = 0; j < list.length; j++) {
        const nm = String((list[j] || {}).name ?? '').trim()
        if (firstNameIndex.has(nm)) {
          return {
            valid: false,
            message: `步骤：${stepName}，操作名称不允许重复，请修改后再保存或调试`
          }
        }
        firstNameIndex.set(nm, j)
      }
    }
    if (step.children && step.children.length > 0) {
      const child = validateDatabaseSteps(step.children)
      if (!child.valid) return child
    }
  }
  return {valid: true}
}

/** HTTP：所属应用、配置名称、请求地址必填；TCP：所属应用、配置名称必填（地址端口由环境/脚本配置解析） */
const validateHttpTcpStepsRequired = (stepList) => {
  const walk = (list) => {
    if (!Array.isArray(list)) return {valid: true}
    for (const step of list) {
      const stepLabel = step.name || step.original?.step_name || '未命名步骤'
      const config = step.config || {}
      const original = step.original || {}

      if (step.type === 'http') {
        const projectId = config.request_project_id ?? original.request_project_id ?? null
        const emptyProject = projectId === null || projectId === undefined || projectId === ''

        let cfgName = ''
        if (config.request_config_name !== undefined) {
          cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
        } else {
          cfgName = String(original.request_config_name ?? '').trim()
        }

        const url = String(config.url ?? original.request_url ?? '').trim()

        if (emptyProject) {
          return {valid: false, message: `步骤：${stepLabel}，请选择所属应用后再保存`}
        }
        if (!cfgName) {
          return {valid: false, message: `步骤：${stepLabel}，请填写配置名称后再保存`}
        }
        if (!url) {
          return {valid: false, message: `步骤：${stepLabel}，请填写请求地址后再保存`}
        }
      }

      if (step.type === 'tcp') {
        const projectId = config.request_project_id ?? original.request_project_id ?? null
        const emptyProject = projectId === null || projectId === undefined || projectId === ''

        let cfgName = ''
        if (config.request_config_name !== undefined) {
          cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
        } else {
          cfgName = String(original.request_config_name ?? '').trim()
        }

        if (emptyProject) {
          return {valid: false, message: `步骤：${stepLabel}，请选择所属应用后再保存`}
        }
        if (!cfgName) {
          return {valid: false, message: `步骤：${stepLabel}，请填写配置名称后再保存`}
        }
      }

      if (step.children && step.children.length > 0) {
        const child = walk(step.children)
        if (!child.valid) return child
      }
    }
    return {valid: true}
  }
  return walk(stepList)
}

// 递归校验步骤树中是否存在“键为空”的键值对（请求头/请求体/变量/用户变量等），若存在则不允许保存
const validateEmptyKeyInSteps = (stepList) => {
  for (const step of stepList) {
    const config = step.config || {}
    const original = step.original || {}
    const getList = (key) => (Array.isArray(config[key]) ? config[key] : Array.isArray(original[key]) ? original[key] : [])
    let listName = ''
    if (step.type === 'http') {
      if (hasEmptyKeyInList(getList('headers')) || hasEmptyKeyInList(getList('request_header'))) listName = '请求头'
      else if (hasEmptyKeyInList(getList('params')) || hasEmptyKeyInList(getList('request_params'))) listName = '请求体 params'
      else if (hasEmptyKeyInList(getList('form_data')) || hasEmptyKeyInList(getList('request_form_data'))) listName = '请求体 form-data'
      else if (hasEmptyKeyInList(getList('form_urlencoded')) || hasEmptyKeyInList(getList('request_form_urlencoded'))) listName = '请求体 x-www-form-urlencoded'
      else if (hasEmptyKeyInList(getList('defined_variables'))) listName = '变量'
    } else if (step.type === 'user_variables') {
      if (hasEmptyKeyInList(getList('session_variables'))) listName = '用户变量'
    }
    if (listName) {
      return {valid: false, stepName: step.name || step.original?.step_name || '未命名步骤', listName}
    }
    if (step.children && step.children.length > 0) {
      const childResult = validateEmptyKeyInSteps(step.children)
      if (!childResult.valid) return childResult
    }
  }
  return {valid: true}
}

// 递归校验步骤树中所有 HTTP 步骤：若请求体为 json，则校验 JSON 语法
const validateJsonBodyInSteps = (stepList) => {
  for (const step of stepList) {
    if (step.type === 'http') {
      const config = step.config || {}
      const requestArgsType = config.request_args_type ?? 'none'
      if (requestArgsType === 'json') {
        const raw = config.jsonBodyText ?? (config.data != null ? JSON.stringify(config.data) : '')
        const trimmed = (raw || '').trim()
        if (trimmed !== '') {
          try {
            JSON.parse(trimmed)
          } catch (e) {
            const stepName = step.name || config.step_name || '未命名步骤'
            return {valid: false, message: e.message || 'JSON 格式错误', stepName}
          }
        }
      }
    }
    if (step.children && step.children.length > 0) {
      const childResult = validateJsonBodyInSteps(step.children)
      if (!childResult.valid) return childResult
    }
  }
  return {valid: true}
}

// 将后端返回的 success_detail（前序顺序）写回步骤树，使下次保存走更新而非新增，避免重复保存产生重复步骤
const mergeStepTreeWithSuccessDetail = (stepList, detailList) => {
  if (!Array.isArray(detailList) || detailList.length === 0) return
  let idx = 0
  const traverse = (list) => {
    if (!Array.isArray(list)) return
    for (const step of list) {
      const detail = detailList[idx]
      if (detail && (detail.step_id != null || detail.step_code != null)) {
        if (!step.original) step.original = {}
        if (detail.step_id != null) step.original.id = detail.step_id
        if (detail.step_code != null) step.original.step_code = detail.step_code
      }
      idx += 1
      if (step.children && step.children.length > 0) traverse(step.children)
    }
  }
  traverse(stepList)
}

/** 校验用例与步骤树后调用 updateOrCreateStepTree 保存 */
const handleSaveAll = async () => {
  if (saveLoading.value) return
  if (!steps.value?.length) {
    window.$message?.warning?.('请至少添加一个步骤后再点击保存')
    return
  }
  saveLoading.value = true
  try {
    // 用例信息必填项校验
    const caseValidation = caseInfoPanelRef.value?.validateCaseForm?.() ?? { valid: false, message: '用例信息未就绪' }
    if (!caseValidation.valid) {
      window.$message?.error?.(caseValidation.message)
      return
    }

    const stepNameValidation = validateStepNamesInSteps(steps.value)
    if (!stepNameValidation.valid) {
      notifyError(stepNameValidation.message)
      return
    }

    const httpTcpRequired = validateHttpTcpStepsRequired(steps.value)
    if (!httpTcpRequired.valid) {
      notifyError(httpTcpRequired.message)
      return
    }

    // 请求体为 json 时校验 JSON 语法，有错误则提示并阻止保存
    const jsonValidation = validateJsonBodyInSteps(steps.value)
    if (!jsonValidation.valid) {
      window.$message?.error?.(
          `步骤：${jsonValidation.stepName}，请求体JSON格式错误，请修正后再保存`
      )
      return
    }

    const dbValidation = validateDatabaseSteps(steps.value)
    if (!dbValidation.valid) {
      window.$message?.error?.(dbValidation.message)
      return
    }

    // 键值对去空校验：存在 Key 为空的项时不允许保存
    const emptyKeyValidation = validateEmptyKeyInSteps(steps.value)
    if (!emptyKeyValidation.valid) {
      window.$message?.error?.(
          `步骤：${emptyKeyValidation.stepName}，${emptyKeyValidation.listName}存在键为空的项，请填写或删除后再保存`
      )
      return
    }

    // 获取当前用户信息（用于 updated_user 字段）
    const userStore = useUserStore()
    const currentUser = userStore.username || ''

    // 计算总步骤数（包括子步骤）
    const countTotalSteps = (stepList) => {
      let count = 0
      for (const step of stepList) {
        count++
        if (step.children && step.children.length > 0) {
          count += countTotalSteps(step.children)
        }
      }
      return count
    }
    const totalSteps = countTotalSteps(steps.value)

    // 构建用例信息（AutoTestApiCaseUpdate 格式）
    const casePayload = caseInfoPanelRef.value?.getCasePayload?.() ?? {}
    const caseInfo = {
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      ...casePayload,
      case_steps: totalSteps,
      session_variables: null,
      updated_user: currentUser,
    }

    // 按照树的前序遍历顺序分配 step_no，确保唯一且按顺序递增
    const stepNoMap = assignStepNumbers(steps.value)

    // 转换步骤数据，使用分配好的 step_no，并保持树结构
    const backendSteps = steps.value.map((step) => {
      return convertStepToBackend(step, null, stepNoMap)
    })

    // 构建请求体（AutoTestStepTreeUpdateList 格式）
    const payload = {
      case: caseInfo,
      steps: backendSteps
    }

    // 调用新的后端接口
    const res = await api.updateOrCreateStepTree(payload)
    if (res?.code === '000000' || res?.code === 200 || res?.code === 0) {
      window.$message?.success?.(res?.message || '保存成功')

      // 将本次保存返回的 step_id/step_code 写回当前步骤树，避免重复点击保存时再次被当作新增
      const stepDetail = res?.data?.steps?.success_detail
      if (Array.isArray(stepDetail) && stepDetail.length > 0) {
        mergeStepTreeWithSuccessDetail(steps.value, stepDetail)
      }

      // 新增用例保存成功后，将 case_id / case_code 写入 URL，以便后续加载和刷新保留
      if (res?.data?.cases?.success_detail && res.data.cases.success_detail.length > 0) {
        const savedCase = res.data.cases.success_detail[0]
        if (savedCase.case_id && !caseId.value) {
          await router.replace({
            path: route.path,
            query: {...route.query, case_id: String(savedCase.case_id), case_code: savedCase.case_code || ''}
          })
        }
      }

      // 保存成功后清除缓存，确保下次加载获取最新数据
      autotestStore.clearStepTreeCache(caseId.value, caseCode.value)
      // 重新加载数据（URL 已更新，loadSteps 会带上 case_id；若无步骤，CaseInfoPanel 保留当前表单）
      await loadSteps()
    } else {
      window.$message?.error?.(res?.message || '保存失败')
    }
  } catch (error) {
    console.error('Failed to save step tree', error)
    window.$message?.error?.(error?.response?.data?.message || error?.message || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

/** 执行：拉取已保存步骤树，打开执行配置弹窗（与用例列表「执行」共用逻辑） */
const handleRun = async () => {
  if (!caseId.value && !caseCode.value) {
    window.$message?.warning?.('请先选择或创建测试用例')
    return
  }
  await runSavedCase({
    caseId: caseId.value,
    caseCode: caseCode.value,
    projectOptions: editorProjectOptions.value,
  })
}

/** 调试：校验当前步骤树后打开调试配置弹窗 */
const handleDebug = async () => {
  if (!steps.value?.length) {
    window.$message?.warning?.('请先添加测试步骤')
    return
  }
  if (resolveNumericCaseIdForExecuteApi() == null) {
    window.$message?.warning?.('缺少用例 ID（case_id），请先保存用例后再调试')
    return
  }
  const dbValidation = validateDatabaseSteps(steps.value)
  if (!dbValidation.valid) {
    window.$message?.error?.(dbValidation.message)
    return
  }
  await execConfigModalRef.value?.openDebug({
    sourceSteps: steps.value,
    quoteStepsMap: { ...quoteStepsMap.value },
    caseId: caseId.value,
    projectOptions: editorProjectOptions.value,
    ensureQuoteStepsLoaded: loadQuoteStepsForAllQuoteStepsAsync,
    findStep,
    resolveCaseId: resolveNumericCaseIdForExecuteApi,
    buildDebugExecutePayload: (step_exec_config_map, datasetPart) => {
      const stepNoMap = assignStepNumbers(steps.value)
      const backendSteps = steps.value.map((step) => convertStepToBackend(step, null, stepNoMap))
      return {
        case_id: resolveNumericCaseIdForExecuteApi(),
        steps: backendSteps,
        initial_variables: [],
        steps_execute_config: step_exec_config_map || undefined,
        ...datasetPart,
      }
    },
  })
}

const loadSteps = async () => {
  stepExpandStates.value = new Map()
  stashedQuoteStepsWhenPublic.value = []
  if (!caseId.value && !caseCode.value) {
    // 检查是否为复制进入：case_info 含 is_copy 和 steps
    const caseInfoStr = route.query.case_info
    if (caseInfoStr) {
      try {
        const caseInfo = JSON.parse(caseInfoStr)
        if (loadStepsFromCopy(caseInfo)) return
      } catch (_) {}
    }
    steps.value = []
    selectedKeys.value = []
    caseInfoPanelRef.value?.hydrateFromStepTree?.([])
    return
  }
  // 缓存：切换页签时使用缓存，不重复请求；从用例管理「编辑」新建页签时需请求
  const cached = autotestStore.getStepTreeCache(caseId.value, caseCode.value)
  if (cached) {
    caseInfoPanelRef.value?.hydrateFromStepTree?.(cached.rawData)
    steps.value = JSON.parse(JSON.stringify(cached.steps)).filter(Boolean)
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
    quoteStepsMap.value = {}
    fillQuoteStepsMapFromRawData(cached.rawData, steps.value)
    return
  }
  try {
    const params = {}
    if (caseId.value) params.case_id = caseId.value
    if (caseCode.value) params.case_code = caseCode.value
    const res = await api.getAutoTestStepTree(params)
    const data = Array.isArray(res?.data) ? res.data : []
    caseInfoPanelRef.value?.hydrateFromStepTree?.(data)
    const mappedSteps = data.map(mapBackendStep).filter(Boolean)
    steps.value = mappedSteps
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
    loadQuoteStepsForAllQuoteSteps()
    autotestStore.setStepTreeCache(caseId.value, caseCode.value, { rawData: data, steps: mappedSteps })
  } catch (error) {
    console.error('Failed to load step tree', error)
    steps.value = []
    selectedKeys.value = []
    caseInfoPanelRef.value?.hydrateFromStepTree?.([])
    quoteStepsMap.value = {}
  }
}

/** 左侧树选中步骤，驱动右侧编辑器 */
const handleSelect = (keys) => {
  selectedKeys.value = keys
}

/** 当前选中步骤（含引用内嵌只读步骤） */
const currentStep = computed(() => {
  const key = selectedKeys.value?.[0]
  if (!key) return null
  const quoteInner = getQuoteInnerStep(key)
  if (quoteInner) return quoteInner
  return findStep(key)
})

/** 当前步骤类型对应的右侧编辑器组件 */
const editorComponent = computed(() => {
  const step = currentStep.value
  if (!step) return null
  return editorMap[step.type] || null
})

const currentEditorNeedsProject = computed(() => {
  const t = currentStep.value?.type
  return t === 'http' || t === 'tcp' || t === 'database' || t === 'quote'
})

const currentEditorNeedsVarAssist = computed(() => {
  const t = currentStep.value?.type
  return t === 'http' || t === 'tcp' || t === 'user_variables'
})

/** 右侧动态编辑器 props（引用步骤才传 reselectHandler，避免 HTTP 等多根节点组件透传警告） */
const editorComponentProps = computed(() => {
  const step = currentStep.value
  if (!step) return {}
  const props = {
    config: step.config,
    step,
    projectOptions: currentEditorNeedsProject.value ? editorProjectOptions.value : [],
    projectLoading: currentEditorNeedsProject.value ? editorProjectLoading.value : false,
    availableVariableList: currentEditorNeedsVarAssist.value ? availableVariableList.value : [],
    assistFunctions: currentEditorNeedsVarAssist.value ? assistFunctionsList.value : [],
    readonly: !!step.isQuoteInner,
  }
  if (step.type === 'quote' && !step.isQuoteInner) {
    props.reselectHandler = handleQuoteReselect
  }
  return props
})

/** 在根或父步骤下插入新步骤节点 */
const insertStep = (parentId, type, index = null, extraConfig = null) => {
  const def = stepDefinitions[type]
  if (!def) return null

  const defaultConfig = type === 'loop'
      ? {loop_mode: '次数循环', loop_on_error: '中断循环', loop_maximums: 5}
      : type === 'wait'
          ? {seconds: 2}
          : type === 'user_variables'
              ? {step_name: '用户定义变量'}
              : type === 'quote'
                  ? {quote_case_id: null, step_name: '引用公共脚本'}
                  : type === 'database'
                      ? {
                        step_name: '数据库请求',
                        step_desc: '',
                        database_searched: false,
                        database_operates: [],
                        extract_variables: [],
                        assert_validators: []
                      }
                      : {}
  const defaultName = type === 'loop'
      ? '循环结构(次数循环)'
      : type === 'wait'
          ? '控制等待(2秒)'
          : type === 'user_variables'
              ? '用户定义变量'
              : type === 'database'
                  ? '数据库请求'
                  : type === 'quote' && extraConfig?.step_name
                      ? extraConfig.step_name
                      : `${def.label}`
  const config = extraConfig ? {...defaultConfig, ...extraConfig} : defaultConfig
  const newStep = {
    id: genId(),
    type,
    name: type === 'quote' && config.step_name ? config.step_name : defaultName,
    config
  }
  if (type === 'quote') {
    newStep.original = {
      quote_case_id: newStep.config.quote_case_id ?? null,
      step_name: newStep.config.step_name || newStep.name,
      step_code: null,
      id: null
    }
  }

  // 只有 loop/if 类型才有 children 字段（即使是空数组）
  if (def.allowChildren) {
    newStep.children = []
    // 如果新步骤允许有子步骤，初始化展开状态为true
    stepExpandStates.value.set(newStep.id, true)
  }
  // 非 loop/if 类型不设置 children 字段

  if (!parentId) {
    // 添加到根级别
    if (index !== null) {
      steps.value.splice(index, 0, newStep)
    } else {
      steps.value.push(newStep)
    }
    return newStep
  }
  // 添加到父步骤的子级
  const parent = findStep(parentId)
  if (parent && stepDefinitions[parent.type]?.allowChildren) {
    // 父步骤允许有子步骤，添加到其children中
    parent.children = parent.children || []
    if (index !== null) {
      parent.children.splice(index, 0, newStep)
    } else {
      parent.children.push(newStep)
    }
    return newStep
  }
  return null
}

/** 添加步骤：普通类型直接插入；引用/复制打开抽屉 */
const handleAddStep = (type, parentId) => {
  if (type === 'quote_public_script') {
    scriptDrawerMode.value = 'quote'
    quotePublicScriptParentId.value = parentId
    quotePublicScriptReplaceStepId.value = null
    quotePublicScriptQueryItems.value.case_type = '公共脚本'
    quotePublicScriptDrawerVisible.value = true
    return
  }
  // 【复制指定脚本】打开抽屉：多选脚本，确定复制后调用 copyCaseStepTree 获取 steps 并插入当前步骤树
  if (type === 'copy_steps') {
    scriptDrawerMode.value = 'copy'
    quotePublicScriptParentId.value = parentId
    quotePublicScriptReplaceStepId.value = null
    selectedForCopy.value = []
    quotePublicScriptQueryItems.value.case_type = ''
    quotePublicScriptDrawerVisible.value = true
    return
  }
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    updateStepDisplayNames()
  }
}

/** 从树中递归删除指定 id 的步骤 */
const removeStep = (id, list = steps.value) => {
  const idx = list.findIndex(item => item.id === id)
  if (idx !== -1) {
    list.splice(idx, 1)
    return true
  }
  for (const item of list) {
    if (item.children && item.children.length) {
      const removed = removeStep(id, item.children)
      if (removed) return true
    }
  }
  return false
}

/** 删除步骤并清理展开态与选中态 */
const handleDeleteStep = (id) => {
  // 清理被删除步骤及其子步骤的展开状态
  const step = findStep(id)
  if (step) {
    const cleanupExpandStates = (stepId) => {
      stepExpandStates.value.delete(stepId)
      const stepToClean = findStep(stepId)
      if (stepToClean?.children) {
        stepToClean.children.forEach(child => cleanupExpandStates(child.id))
      }
    }
    cleanupExpandStates(id)
  }

  removeStep(id)
  if (selectedKeys.value[0] === id) {
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  }
}

/** 当用例类型改为「公共脚本」时，移除步骤树中所有「引用公共脚本」步骤，防止循环引用。返回被移除的步骤数量。 */
const removeAllQuoteSteps = () => {
  const quoteIds = []
  forEachStep(steps.value, (step) => {
    if (step.type === 'quote' || step.type === 'quote_public_script') {
      quoteIds.push(step.id)
    }
  })
  if (quoteIds.length === 0) return 0
  quoteIds.forEach((id) => {
    const step = findStep(id)
    if (step) {
      stepExpandStates.value.delete(id)
      removeStep(id)
    }
  })
  quoteIds.forEach((id) => {
    quoteStepsMap.value = { ...quoteStepsMap.value, [id]: [] }
  })
  if (quoteIds.includes(selectedKeys.value?.[0])) {
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  }
  updateStepDisplayNames()
  return quoteIds.length
}

/** 收集所有「引用公共脚本」步骤及其位置（用于暂存，切回用户脚本时可恢复） */
const collectQuoteStepsWithPosition = () => {
  const list = []
  forEachStep(steps.value, (step) => {
    if (step.type !== 'quote' && step.type !== 'quote_public_script') return
    const parent = findStepParent(step.id)
    const parentId = parent?.id ?? null
    const siblings = parentId === null ? steps.value : (parent?.children || [])
    const index = siblings.findIndex((s) => s.id === step.id)
    if (index === -1) return
    list.push({
      step: JSON.parse(JSON.stringify(step)),
      parentId,
      index
    })
  })
  return list
}

/** 将暂存的引用步骤恢复回步骤树 */
const restoreStashedQuoteSteps = () => {
  const stashed = stashedQuoteStepsWhenPublic.value
  if (!stashed || stashed.length === 0) return 0
  const sorted = [...stashed].sort((a, b) => {
    const pa = a.parentId ?? ''
    const pb = b.parentId ?? ''
    if (pa !== pb) return String(pa).localeCompare(String(pb))
    return a.index - b.index
  })
  for (const { step, parentId, index } of sorted) {
    const list = parentId === null ? steps.value : (findStep(parentId)?.children || null)
    if (!list) continue
    const safeIndex = Math.min(index, list.length)
    list.splice(safeIndex, 0, step)
  }
  stashedQuoteStepsWhenPublic.value = []
  updateStepDisplayNames()
  loadQuoteStepsForAllQuoteSteps()
  return sorted.length
}

/** 条件分支 / 循环结构在步骤树上的固定展示名（与 updateStepConfig 规则一致）；其它类型返回 null */
const getFixedBranchStepDisplayName = (step) => {
  if (!step?.type) return null
  if (step.type === 'if') {
    return '条件分支(满足条件时执行)'
  }
  if (step.type === 'loop') {
    const mode = (step.config && step.config.loop_mode) || '次数循环'
    if (mode === '次数循环') return '循环结构(次数循环)'
    if (mode === '列表循环') return '循环结构(列表循环)'
    if (mode === '字典循环') return '循环结构(字典循环)'
    if (mode === '条件循环') return '循环结构-(条件循环)'
    return '循环结构'
  }
  return null
}

/** 与 convertStepToBackend 写入后端的 step_name 一致，用于保存前校验重复 */
const getStepNameAsWillPersist = (step) => {
  const original = step.original || {}
  const config = step.config || {}
  const fixed = getFixedBranchStepDisplayName(step)
  if (fixed) return String(fixed).trim()

  if (step.type === 'user_variables') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || '')
    return String(v ?? '').trim()
  }
  if (step.type === 'quote' || step.type === 'quote_public_script') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
    return String(v ?? '').trim()
  }
  if (step.type === 'database') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
    return String(v ?? '').trim()
  }

  return String(step.name || original.step_name || '').trim()
}

/** 编辑器已向 config 写入 step_name 且用户清空时视为未填写（HTTP/TCP/代码等） */
const isStepNameExplicitlyEmptyInEditor = (step) => {
  const config = step.config || {}
  if (!Object.prototype.hasOwnProperty.call(config, 'step_name')) return false
  return String(config.step_name ?? '').trim() === ''
}

/** 步骤名称必填；除 loop / if 外全局不可重复（前序遍历） */
const validateStepNamesInSteps = (stepList) => {
  const usedNames = new Map()

  const walk = (list) => {
    if (!Array.isArray(list)) return {valid: true}
    for (const step of list) {
      const typeLabel = stepDefinitions[step.type]?.label
          || (step.type === 'quote_public_script' ? '引用公共脚本' : (step.type || '步骤'))

      if (isStepNameExplicitlyEmptyInEditor(step)) {
        return {
          valid: false,
          message: `${typeLabel}：步骤名称不能为空，请填写后再保存`
        }
      }

      const name = getStepNameAsWillPersist(step)
      if (!name) {
        return {
          valid: false,
          message: `${typeLabel}：步骤名称不能为空，请填写后再保存`
        }
      }

      const exemptDuplicate = step.type === 'loop' || step.type === 'if'
      if (!exemptDuplicate) {
        if (usedNames.has(name)) {
          return {
            valid: false,
            message: `步骤名称重复：${name}，除循环结构、条件分支外步骤名称不可重复，请修改后再保存`
          }
        }
        usedNames.set(name, true)
      }
      if (step.children && step.children.length > 0) {
        const child = walk(step.children)
        if (!child.valid) return child
      }
    }
    return {valid: true}
  }

  return walk(stepList)
}

/** 复制步骤（含子树）并插入到同级下一位置 */
const handleCopyStep = (id) => {
  const step = findStep(id)
  if (!step) return
  const copiedStep = JSON.parse(JSON.stringify(step))
  copiedStep.id = genId()
  const fixedName = getFixedBranchStepDisplayName(copiedStep)
  copiedStep.name = fixedName ?? `${copiedStep.name}(copy)`

  // 复制的步骤是新增的，需要删除 original 中的 id 和 step_code
  // 这样 convertStepToBackend 会将其识别为新增步骤
  if (copiedStep.original) {
    delete copiedStep.original.id
    delete copiedStep.original.step_code
    // 保留其他 original 字段（如 case_id, step_type 等），但清除标识字段
  }

  // 确保结构规范：非 loop/if 类型不应该有 children 字段
  const def = stepDefinitions[copiedStep.type]
  if (def && !def.allowChildren && copiedStep.children !== undefined) {
    // 删除不应该存在的 children 字段
    delete copiedStep.children
  } else if (def && def.allowChildren && !copiedStep.children) {
    // 确保 loop/if 类型有 children 字段（即使是空数组）
    copiedStep.children = []
  }

  // 递归更新子步骤ID，并确保子步骤结构规范，同时删除子步骤的 original.id 和 original.step_code
  const updateIds = (node) => {
    node.id = genId()
    // 删除子步骤的 original.id 和 original.step_code（复制的子步骤也是新增的）
    if (node.original) {
      delete node.original.id
      delete node.original.step_code
    }
    const nodeDef = stepDefinitions[node.type]
    // 确保每个子步骤的结构规范
    if (nodeDef && !nodeDef.allowChildren && node.children !== undefined) {
      delete node.children
    } else if (nodeDef && nodeDef.allowChildren && !node.children) {
      node.children = []
    }
    if (node.children && node.children.length) {
      node.children.forEach(updateIds)
    }
  }
  updateIds(copiedStep)

  // 如果复制的步骤允许有子步骤，初始化展开状态
  if (def && def.allowChildren) {
    stepExpandStates.value.set(copiedStep.id, true)
  }

  const parent = findStepParent(id)
  if (parent) {
    const parentStep = findStep(parent.id)
    if (parentStep && parentStep.children) {
      const index = parentStep.children.findIndex(s => s.id === id)
      parentStep.children.splice(index + 1, 0, copiedStep)
    }
  } else {
    const index = steps.value.findIndex(s => s.id === id)
    steps.value.splice(index + 1, 0, copiedStep)
  }
  selectedKeys.value = [copiedStep.id]
}

/** 条件分支仅更新 conditions 时：就地合并，避免整包替换 config 加剧响应式抖动 */
const isIfConditionsOnlyPatch = (step, config) => {
  if (!step || step.type !== 'if' || !config?.conditions) return false
  if (typeof config.conditions !== 'object' || Array.isArray(config.conditions)) return false
  return Object.keys(config).length === 1 && Object.keys(config)[0] === 'conditions'
}

/** 右侧编辑器更新步骤 config 并同步树展示名 */
const updateStepConfig = (id, config) => {
  const step = findStep(id)
  if (step) {
    if (isIfConditionsOnlyPatch(step, config)) {
      const prev = step.config?.conditions
      if (prev && typeof prev === 'object' && !Array.isArray(prev)) {
        Object.assign(prev, config.conditions)
      } else {
        step.config = {...step.config, conditions: {...config.conditions}}
      }
    } else {
      step.config = {...step.config, ...config}
    }
    // 根据配置更新步骤名称
    const branchFixed = getFixedBranchStepDisplayName(step)
    if (branchFixed) {
      step.name = branchFixed
    } else if (step.type === 'http') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined && config.step_name.length > 0) {
        step.name = String(config.step_name).trim() || 'HTTP请求(发送请求并验证响应数据)'
      } else {
        // 否则自动生成步骤名称
        step.name = `HTTP请求(发送请求并验证响应数据)`
      }
    } else if (step.type === 'tcp') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || 'TCP请求'
      }
    } else if (step.type === 'wait') {
      step.name = `控制等待(${config.seconds ?? 2}秒)`
    } else if (step.type === 'user_variables') {
      // 用户变量：步骤名称必填，修改时同步到步骤树（与等待控制一致）
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '用户定义变量'
      }
    } else if (step.type === 'code') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined) {
        step.name = String(config.step_name).trim() || '代码请求(Python)'
      }
    } else if (step.type === 'database') {
      if (config.step_name !== undefined && String(config.step_name).trim()) {
        step.name = String(config.step_name).trim()
      } else if (!String(step.name || '').trim()) {
        step.name = '数据库请求'
      }
    } else if (step.type === 'quote' || step.type === 'quote_public_script') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '引用公共脚本'
      }
    }
    // 条件分支仅改 conditions 时左侧树展示名不变，跳过同步刷新减轻输入卡顿
    if (!isIfConditionsOnlyPatch(step, config)) {
      updateStepDisplayNames()
    }
  }
}

/** 步骤类型对应的图标名 */
const getStepIcon = (type) => {
  return stepDefinitions[type]?.icon || 'material-symbols:code'
}

/** 步骤类型对应的图标 CSS 类名 */
const getStepIconClass = (type) => {
  const classMap = {
    loop: 'icon-loop',
    code: 'icon-code',
    tcp: 'icon-tcp',
    http: 'icon-http',
    if: 'icon-if',
    wait: 'icon-wait',
    database: 'icon-database',
    user_variables: 'icon-user_variables',
    quote: 'icon-quote',
    quote_public_script: 'icon-quote',
  }
  return classMap[type] || ''
}

// 拖拽相关
const handleDragStart = (event, stepId, parentId, index) => {
  dragState.value.draggingId = stepId
  dragState.value.dragOverParent = parentId
  dragState.value.dragOverIndex = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', stepId)
}

/** 根级步骤拖拽经过 */
const handleDragOver = (event, targetId, targetParentId) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  // 如果正在拖拽，检查目标步骤是否为 if/loop 类型
  if (dragState.value.draggingId && targetId) {
    const targetStep = findStep(targetId)
    if (targetStep && stepDefinitions[targetStep.type]?.allowChildren) {
      // 如果是 if 或 loop 类型，设置 dragOverId 用于焦点高亮
      dragState.value.dragOverId = targetId
      dragState.value.dragOverParent = targetParentId
    }
  }
}

// 处理在 if/loop 步骤的子步骤区域内的拖拽
const handleDragOverInChildrenArea = (event, parentId) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  if (!dragState.value.draggingId || !parentId) {
    return
  }

  const parentStep = findStep(parentId)
  if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) {
    return
  }

  // 设置焦点高亮
  dragState.value.dragOverId = parentId
  dragState.value.dragOverParent = parentId

  // 如果子步骤区域为空，设置插入位置为第一个位置
  if (!parentStep.children || parentStep.children.length === 0) {
    dragState.value.insertTargetId = null
    dragState.value.insertPosition = 'before'
    dragState.value.dragOverIndex = 0
    return
  }

  // 如果子步骤区域不为空，让子步骤的 dragover 事件来处理
  // 这里不做任何处理，让事件继续传播到子步骤
}

/** 离开 loop/if 子区域 */
const handleDragLeaveInChildrenArea = (event, parentId) => {
  // 当离开子步骤区域时，清除插入位置指示器
  if (dragState.value.dragOverId === parentId) {
    setTimeout(() => {
      // 检查是否真的离开了该区域
      if (dragState.value.dragOverId === parentId) {
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
        dragState.value.dragOverIndex = null
      }
    }, 50)
  }
}

// 处理在子步骤上的拖拽
const handleDragOverOnChild = (event, childId, parentId, childIndex) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  if (!dragState.value.draggingId || !parentId) {
    return
  }

  const parentStep = findStep(parentId)
  if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) {
    return
  }

  // 设置焦点高亮
  dragState.value.dragOverId = parentId
  dragState.value.dragOverParent = parentId

  // 计算鼠标在子步骤中的相对位置，判断是插入到之前还是之后
  const rect = event.currentTarget.getBoundingClientRect()
  const mouseY = event.clientY
  const stepCenterY = rect.top + rect.height / 2

  // 如果鼠标在步骤的上半部分，插入到之前；否则插入到之后
  const position = mouseY < stepCenterY ? 'before' : 'after'

  dragState.value.insertTargetId = childId
  dragState.value.insertPosition = position
  dragState.value.dragOverIndex = position === 'before' ? childIndex : childIndex + 1
}

/** 离开子步骤拖拽目标 */
const handleDragLeaveOnChild = (event, childId) => {
  // 当离开子步骤时，清除插入位置指示器（延迟清除，避免快速移动时闪烁）
  if (dragState.value.insertTargetId === childId) {
    setTimeout(() => {
      if (dragState.value.insertTargetId === childId) {
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
      }
    }, 3000)
  }
}

/** 离开拖拽目标 */
const handleDragLeave = (event, targetId) => {
  // 当离开拖拽目标时，清除焦点高亮（延迟清除，避免快速移动时闪烁）
  if (dragState.value.dragOverId === targetId) {
    // 使用 setTimeout 延迟清除，避免在移动到子元素时误清除
    setTimeout(() => {
      if (dragState.value.dragOverId === targetId) {
        dragState.value.dragOverId = null
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
        dragState.value.dragOverIndex = null
      }
    }, 50)
  }
}

/** 放置步骤完成移动 */
const handleDrop = (event, targetId, targetParentId, targetIndex) => {
  event.preventDefault()
  const draggingId = dragState.value.draggingId
  if (!draggingId || draggingId === targetId) {
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  const draggingStep = findStep(draggingId)
  if (!draggingStep) {
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  // 从原位置移除
  const removeFromList = (list, id) => {
    const idx = list.findIndex(item => item.id === id)
    if (idx !== -1) {
      list.splice(idx, 1)
      return true
    }
    for (const item of list) {
      if (item.children && item.children.length) {
        if (removeFromList(item.children, id)) return true
      }
    }
    return false
  }
  removeFromList(steps.value, draggingId)

  // 如果 dragOverId 存在且是 if/loop 类型，说明是拖拽到 if/loop 步骤的子步骤区域
  if (dragState.value.dragOverId) {
    const parentStep = findStep(dragState.value.dragOverId)
    if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
      // 确保 children 数组存在
      if (!parentStep.children) {
        parentStep.children = []
      }

      // 使用 dragState 中的插入位置信息
      const insertIndex = dragState.value.dragOverIndex !== null ? dragState.value.dragOverIndex : parentStep.children.length
      parentStep.children.splice(insertIndex, 0, draggingStep)
      dragState.value = {
        draggingId: null,
        dragOverId: null,
        dragOverParent: null,
        dragOverIndex: null,
        insertPosition: null,
        insertTargetId: null
      }
      return
    }
  }

  // 原有的拖拽逻辑：拖拽到其他步骤的位置
  const targetStep = findStep(targetId)
  // 如果目标是 if/loop 类型且允许子步骤，且是拖拽到步骤本身的空区域（targetId === targetParentId）
  if (targetStep && stepDefinitions[targetStep.type]?.allowChildren && targetId === targetParentId) {
    // 确保 children 数组存在
    if (!targetStep.children) {
      targetStep.children = []
    }
    // 添加到目标步骤的 children 中
    targetStep.children.push(draggingStep)
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  // 如果 targetParentId 是 if/loop 类型，说明是拖拽到 if/loop 步骤的子步骤位置
  if (targetParentId) {
    const parentStep = findStep(targetParentId)
    if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
      // 确保 children 数组存在
      if (!parentStep.children) {
        parentStep.children = []
      }
      // 插入到指定位置
      const insertIndex = targetIndex !== null ? targetIndex : parentStep.children.length
      parentStep.children.splice(insertIndex, 0, draggingStep)
      dragState.value = {
        draggingId: null,
        dragOverId: null,
        dragOverParent: null,
        dragOverIndex: null,
        insertPosition: null,
        insertTargetId: null
      }
      return
    }
  }

  // 插入到新位置（根级别）
  const insertIndex = targetIndex !== null ? targetIndex : steps.value.length
  steps.value.splice(insertIndex, 0, draggingStep)
  dragState.value = {
    draggingId: null,
    dragOverId: null,
    dragOverParent: null,
    dragOverIndex: null,
    insertPosition: null,
    insertTargetId: null
  }
}

// 计算步骤编号（按深度优先遍历）
const stepNumberMap = computed(() => {
  const map = new Map()
  let counter = 0

  const traverse = (list) => {
    for (const step of list) {
      counter++
      map.set(step.id, counter)
      if (step.children && step.children.length) {
        traverse(step.children)
      }
    }
  }

  traverse(steps.value)
  return map
})

/** 获取步骤前序序号（#N） */
const getStepNumber = (stepId) => {
  return stepNumberMap.value.get(stepId) || 0
}

// 存储每个步骤的显示名称（用于中间省略）
const stepDisplayNames = ref(new Map())

// 计算文本中间省略（保留开头和结尾）
const truncateTextMiddle = (text, maxChars = 20) => {
  if (!text || text.length <= maxChars) return text
  // 计算开头和结尾的长度（为省略号留出空间）
  const halfLen = Math.floor((maxChars - 3) / 2)
  const start = text.substring(0, halfLen)
  const end = text.substring(text.length - halfLen)
  return `${start}...${end}`
}

// 获取步骤显示名称（中间省略）
const getStepDisplayName = (name, stepId) => {
  if (!name) return ''
  // 如果已经计算过，返回计算后的名称
  if (stepDisplayNames.value.has(stepId)) {
    return stepDisplayNames.value.get(stepId)
  }
  // 如果还没有计算过，先进行简单处理
  const maxDisplayLength = 22
  if (name.length > maxDisplayLength) {
    return truncateTextMiddle(name, maxDisplayLength)
  }
  return name
}

// 更新步骤显示名称（根据容器宽度动态计算）
const updateStepDisplayNames = () => {
  nextTick(() => {
    const nameMap = new Map()
    // 考虑到操作按钮的宽度（步骤编号 + 复制 + 删除按钮），设置合理的文本长度限制
    // 操作按钮大约需要 80-100px，文本区域大约可以显示 20-25 个字符
    const maxDisplayLength = 22

    const updateNames = (list) => {
      for (const step of list) {
        const stepName = step.name || ''
        // 根据步骤名称长度决定是否需要中间省略
        if (stepName.length > maxDisplayLength) {
          nameMap.set(step.id, truncateTextMiddle(stepName, maxDisplayLength))
        } else {
          nameMap.set(step.id, stepName)
        }
        if (step.children && step.children.length) {
          updateNames(step.children)
        }
      }
    }
    updateNames(steps.value)
    stepDisplayNames.value = nameMap
  })
}

// 监听 steps 变化：防抖刷新左侧树展示名（避免条件分支等编辑器逐字 emit 时整树重算导致输入卡顿）
let stepTreeLayoutTimer = null
watch(() => steps.value, () => {
  if (stepTreeLayoutTimer) {
    clearTimeout(stepTreeLayoutTimer)
  }
  stepTreeLayoutTimer = setTimeout(() => {
    updateStepDisplayNames()
    initializeStepExpandStates()
    stepTreeLayoutTimer = null
  }, 80)
}, {deep: true})

// 同页切换用例（仅 query 变化、组件未销毁）时需重新解析 case_info 并拉步骤树
watch([() => caseId.value, () => caseCode.value], () => {
  caseInfoPanelRef.value?.reloadFromRoute?.()
  loadSteps()
})

onUnmounted(() => {
  stopResizeLeftPanel()
})

onMounted(async () => {
  loadLeftPanelWidth()
  await loadSteps()
  // 辅助函数列表（用于用户变量/关联数据）
  try {
    const res = await api.getAssistFuncList()
    const data = res?.data ?? res
    assistFunctionsList.value = Array.isArray(data) ? data : (data?.data ?? [])
  } catch (e) {
    console.warn('获取辅助函数列表失败', e)
    assistFunctionsList.value = []
  }
})

// 不在 onUpdated 中刷新展示名：每次子编辑器 emit 都会触发父组件 patch，导致输入卡顿/丢字

// 递归子步骤组件
const RecursiveStepChildren = defineComponent({
  name: 'RecursiveStepChildren',
  props: {
    step: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    // 捕获所有需要的变量和函数，确保能够通过闭包访问
    const capturedStepDefinitions = stepDefinitions
    const capturedIsStepExpanded = isStepExpanded
    const capturedToggleStepExpand = toggleStepExpand
    const capturedSelectedKeys = selectedKeys
    const capturedGetStepIcon = getStepIcon
    const capturedGetStepIconClass = getStepIconClass
    const capturedGetStepDisplayName = getStepDisplayName
    const capturedGetStepNumber = getStepNumber
    const capturedHandleSelect = handleSelect
    const capturedHandleDragStart = handleDragStart
    const capturedHandleDragOverInChildrenArea = handleDragOverInChildrenArea
    const capturedHandleDragLeaveInChildrenArea = handleDragLeaveInChildrenArea
    const capturedHandleDragOverOnChild = handleDragOverOnChild
    const capturedHandleDragLeaveOnChild = handleDragLeaveOnChild
    const capturedHandleDrop = handleDrop
    const capturedHandleCopyStep = handleCopyStep
    const capturedHandleDeleteStep = handleDeleteStep
    const capturedIsPublicScriptCase = isPublicScriptCase
    const capturedHandleAddStep = handleAddStep
    const capturedDragState = dragState

    return () => {
      const {step} = props
      if (!capturedStepDefinitions[step.type]?.allowChildren) return null

      // 局部展开优先于全局状态：如果步骤被局部展开，就显示，不管全局状态如何
      const shouldShow = capturedIsStepExpanded(step.id)
      if (!shouldShow) return null

      return h('div', {
        onDragover: (e) => {
          e.preventDefault()
          e.stopPropagation()
          capturedHandleDragOverInChildrenArea(e, step.id)
        },
        onDragleave: (e) => {
          e.stopPropagation()
          capturedHandleDragLeaveInChildrenArea(e, step.id)
        }
      }, [
        // 无子女时显示空的拖拽区域
        (!step.children || step.children.length === 0) ? h('div', {
          class: ['step-drop-zone', {'is-drag-over': capturedDragState.value.dragOverId === step.id}],
          onDrop: (e) => {
            e.stopPropagation()
            capturedHandleDrop(e, step.id, step.id, 0)
          }
        }, [
          h('div', {
            class: 'step-drop-zone-hint'
          }, '拖拽步骤到这里')
        ]) : null,
        ...(step.children || []).map((child, childIndex) => [
          // 插入位置指示器：在子步骤之前
          h('div', {
            key: `indicator-before-${child.id}`,
            class: 'step-insert-indicator',
            style: {
              display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === child.id && capturedDragState.value.insertPosition === 'before' ? 'block' : 'none'
            }
          }),
          h('div', {
            key: child.id,
            class: [
              'step-item',
              {
                'is-selected': capturedSelectedKeys.value.includes(child.id),
                'is-drag-target': capturedDragState.value.draggingId && capturedStepDefinitions[child.type]?.allowChildren
              }
            ],
            draggable: true,
            onClick: (e) => {
              e.stopPropagation()
              capturedHandleSelect([child.id])
            },
            onDragstart: (e) => {
              e.stopPropagation()
              capturedHandleDragStart(e, child.id, step.id, childIndex)
            },
            onDragover: (e) => {
              e.preventDefault()
              e.stopPropagation()
              capturedHandleDragOverOnChild(e, child.id, step.id, childIndex)
            },
            onDragleave: (e) => {
              e.stopPropagation()
              capturedHandleDragLeaveOnChild(e, child.id)
            },
            onDrop: (e) => {
              e.stopPropagation()
              capturedHandleDrop(e, child.id, step.id, childIndex)
            }
          }, [
            h('div', {
              class: 'step-item-child'
            }, [
              h('span', {
                class: 'step-name',
                title: child.name
              }, [
                h(TheIcon, {
                  icon: capturedGetStepIcon(child.type),
                  size: 16,
                  class: ['step-icon', capturedGetStepIconClass(child.type)]
                }),
                h('span', {
                  class: 'step-name-text'
                }, capturedGetStepDisplayName(child.name, child.id)),
                h('span', {
                  class: 'step-actions'
                }, [
                  h('span', {
                    class: 'step-number'
                  }, `#${capturedGetStepNumber(child.id)}`),
                  capturedStepDefinitions[child.type]?.allowChildren ? h(NButton, {
                    text: true,
                    size: 'tiny',
                    class: 'action-btn',
                    onClick: (e) => {
                      e.stopPropagation()
                      capturedToggleStepExpand(child.id, e)
                    }
                  }, {
                    icon: () => h(TheIcon, {
                      icon: capturedIsStepExpanded(child.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down',
                      size: 14
                    })
                  }) : null,
                  h(NButton, {
                    text: true,
                    size: 'tiny',
                    class: 'action-btn',
                    title: '复制当前步骤',
                    onClick: (e) => {
                      e.stopPropagation()
                      capturedHandleCopyStep(child.id)
                    }
                  }, {
                    icon: () => h(TheIcon, {
                      icon: 'material-symbols:content-copy',
                      size: 14,
                    })
                  }),
                  h(NPopconfirm, {
                    onPositiveClick: () => capturedHandleDeleteStep(child.id),
                    onClick: (e) => e.stopPropagation()
                  }, {
                    trigger: () => h(NButton, {
                      text: true,
                      size: 'tiny',
                      type: 'error',
                      title: '删除当前步骤',
                      class: 'action-btn'
                    }, {
                      icon: () => h(TheIcon, {
                        icon: 'material-symbols:delete',
                        size: 14
                      })
                    }),
                    default: () => '确认删除该步骤?'
                  })
                ])
              ]),
              // 递归渲染子步骤（只有当子步骤允许有子步骤时才渲染）
              capturedStepDefinitions[child.type]?.allowChildren ? h(RecursiveStepChildren, {
                step: child
              }) : null
            ])
          ]),
          // 插入位置指示器：在子步骤之后
          h('div', {
            key: `indicator-after-${child.id}`,
            class: 'step-insert-indicator',
            style: {
              display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === child.id && capturedDragState.value.insertPosition === 'after' ? 'block' : 'none'
            }
          })
        ]).flat(),
        // 插入位置指示器：在最后一个子步骤之后
        h('div', {
          class: 'step-insert-indicator',
          style: {
            display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === null && capturedDragState.value.insertPosition === 'after' && step.children && step.children.length > 0 ? 'block' : 'none'
          }
        }),
        h('div', {
          class: 'step-add-btn'
        }, [
          h(AddStepPopover, {
            isPublicScriptCase: capturedIsPublicScriptCase.value,
            onSelect: (key) => capturedHandleAddStep(key, step.id),
          }),
        ])
      ])
    }
  }
})
</script>

<style scoped>
/* 页面容器：限制最大高度为视口高度 */
.page-container {
  height: 100%;
  max-height: calc(100vh - 100px); /* 减去 AppPage 的 padding 和其他空间，可根据实际情况调整 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0; /* 允许容器缩小 */
}


.steps-split-layout {
  display: flex;
  flex: 1;
  align-items: stretch;
  height: 100%;
  min-height: 0;
  min-width: 0;
}

.steps-split-resizer {
  flex-shrink: 0;
  width: 3px;
  margin: 0 3px;
  cursor: col-resize;
  background: transparent;
}

/* 左侧列：步骤树统一字号与字重 */
.left-column {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  min-width: 0;
  font-size: 13px;
  font-weight: 400;
}

/* 右侧列：使用 flex 布局，占据剩余空间 */
.right-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.steps-split-main {
  flex: 1;
  min-width: 0;
}

/* 步骤卡片：使用 flex 布局，占满可用高度 */
.step-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

/* 步骤卡片 header：固定不滚动 */
.step-card :deep(.n-card__header) {
  flex-shrink: 0;
}

/* 步骤卡片内容区域：可滚动 */
.step-card :deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

/* 配置卡片：使用 flex 布局，占满可用高度 */
.config-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

/* 步骤树 / 右侧明细：统一滚动条（默认隐藏，悬停且溢出时显示细条） */
.step-tree-container,
.config-card :deep(.n-card__content) {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  scrollbar-width: none;
}

.step-tree-container {
  padding: 4px 0;
}

.step-tree-container:hover,
.config-card :deep(.n-card__content):hover {
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--n-border-color) 75%, transparent) transparent;
}

.step-tree-container::-webkit-scrollbar,
.config-card :deep(.n-card__content)::-webkit-scrollbar {
  width: 0;
}

.step-tree-container:hover::-webkit-scrollbar,
.config-card :deep(.n-card__content):hover::-webkit-scrollbar {
  width: 4px;
}

.step-tree-container:hover::-webkit-scrollbar-track,
.config-card :deep(.n-card__content):hover::-webkit-scrollbar-track {
  background: transparent;
}

.step-tree-container:hover::-webkit-scrollbar-thumb,
.config-card :deep(.n-card__content):hover::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--n-border-color) 75%, transparent);
  border-radius: 4px;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
  flex-shrink: 0; /* 防止 header 被压缩 */
}

.step-count {
  font-size: 14px;
  font-weight: 600;
}

/* 下拉菜单中的图标样式 */
:deep(.n-dropdown-menu .step-icon) {
  flex-shrink: 0;
}

:deep(.step-add-btn .add-step-trigger-btn) {
  width: 99%;
  margin-bottom: 5px;
  border-radius: 8px;
}

/* 样式穿透：根步骤 / 子步骤 / 引用内步骤统一间距 */
:deep(.step-item) {
  border: 1px solid transparent;
  border-radius: 8px;
  transition: all .2s;
  cursor: pointer;
  padding: 3px 0;
  margin: 0;
}

:deep(.step-item.is-selected) {
  border: 1px dashed #F4511E;
}

/* 所有 loop/if 步骤的普通高亮（拖拽时） */
:deep(.step-item.is-drag-target) {
  border: 2px solid rgba(244, 81, 30, 0.3);
  background-color: rgba(244, 81, 30, 0.05);
}

/* 焦点高亮（拖拽进入目标区域时） */
:deep(.step-item.is-drag-over) {
  border: 2px solid #F4511E;
  background-color: rgba(244, 81, 30, 0.15);
  box-shadow: 0 0 12px rgba(244, 81, 30, 0.4);
}

/* 插入位置指示器 */
:deep(.step-insert-indicator) {
  height: 2px;
  background-color: #F4511E;
  margin: 2px 8px;
  border-radius: 1px;
  box-shadow: 0 0 4px rgba(244, 81, 30, 0.6);
}

:deep(.step-item[draggable="true"]) {
  cursor: move;
}

:deep(.step-drop-zone) {
  min-height: 28px;
  border: 2px dashed var(--n-border-color);
  border-radius: 8px;
  margin: 4px 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background-color: var(--n-color-embedded);
}

:deep(.step-drop-zone.is-drag-over) {
  border-color: #F4511E;
  background-color: rgba(244, 81, 30, 0.1);
  box-shadow: 0 0 8px rgba(244, 81, 30, 0.3);
}

:deep(.step-drop-zone-hint) {
  color: var(--n-text-color-3);
  font-size: 13px;
  font-weight: 400;
  padding: 4px;
}

:deep(.step-drop-zone.is-drag-over .step-drop-zone-hint) {
  color: #F4511E;
}

:deep(.step-item-child) {
  padding-left: 8px;
  margin-left: 8px;
}

:deep(.step-name) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  font-size: 13px;
  font-weight: 400;
  background-color: color-mix(in srgb, var(--n-border-color) 35%, transparent);
  padding: 4px 6px;
  border-radius: 8px;
  box-sizing: border-box;
  position: relative;
  min-width: 0;
}

:deep(.step-name:hover) {
  color: #F4511E;
}

:deep(.step-name-text) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  margin-right: auto;
  padding-right: 4px;
  display: inline-block;
  font-size: inherit;
  font-weight: inherit;
}

:deep(.step-actions) {
  display: none;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  margin-left: auto;
  padding-left: 8px;
}

:deep(.step-name:hover .step-actions) {
  display: flex;
}

:deep(.step-number) {
  font-size: 13px;
  color: var(--n-text-color-2);
  font-weight: 400;
  margin-right: 2px;
}

:deep(.step-icon) {
  font-size: 16px;
  flex-shrink: 0;
  align-items: center;
}

:deep(.step-icon.icon-user_variables) {
  color: #FF69B4;
}

:deep(.step-icon.icon-code) {
  color: #BA55D3;
}

:deep(.step-icon.icon-database) {
  color: #BA55D3;
}

:deep(.step-icon.icon-tcp) {
  color: #2080F0;
}

:deep(.step-icon.icon-http) {
  color: #2080F0;
}

:deep(.step-icon.icon-loop) {
  color: #F4511E;
}

:deep(.step-icon.icon-if) {
  color: #F4511E;
}

:deep(.step-icon.icon-wait) {
  color: #F4511E;
}

:deep(.step-icon.icon-quote) {
  color: #F4511E;
}

:deep(.action-btn) {
  padding: 2px 1px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

:deep(.action-btn:hover) {
  opacity: 1;
}

:deep(.step-add-btn) {
  padding-top: 5px;
  padding-left: 8px;
}

/* 引用步骤内嵌树：与主步骤树共用 .step-item / .step-name 样式，仅保留结构缩进 */
:deep(.quote-inner-steps) {
  margin: 2px 0 2px 8px;
  border-left: 2px solid #F4511E;
  border-radius: 12px;
  padding-left: 6px;
}

:deep(.quote-inner-list) {
  margin-top: 2px;
}

:deep(.quote-inner-item) {
  padding: 3px 0;
  margin: 0;
  border: 1px solid transparent;
  border-radius: 8px;
}

:deep(.quote-inner-item.is-selected) {
  border: 1px dashed #F4511E;
}

:deep(.quote-inner-empty) {
  font-size: 13px;
  font-weight: 400;
  color: var(--n-text-color-3);
  padding: 4px 0;
}


</style>
