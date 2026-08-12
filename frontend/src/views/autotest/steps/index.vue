<template>
  <AppPage>
    <div ref="caseInfoWrapRef">
      <CaseInfoPanel
          ref="caseInfoPanelRef"
          :debug-loading="debugLoading"
          :save-loading="saveLoading"
          :tree-mode="treeMode"
          @case-type-change="onCaseTypeChange"
          @debug="handleDebug"
          @save="handleSaveAll"
          @history="openCaseHistory"
          @request-tree-mode-change="handleTreeModeChange"
      />
    </div>
    <div class="page-container">
      <StepSourceJsonPanel
          v-if="!treeMode"
          v-model="sourceJsonText"
          :apply-loading="sourceJsonApplyLoading"
          @reset="resetSourceJson"
          @apply="applySourceJsonFromEditor"
      />
      <div v-else class="steps-split-layout">
        <div
            v-show="!leftPanelCollapsed"
            class="left-column"
            :style="{ width: `${leftPanelWidth}px` }"
        >
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
            <div
                class="step-tree-container overlay-scroll"
                @dragover="handleDragOverOnRootSpace"
                @dragleave="handleDragLeaveOnRootSpace"
                @drop="handleDropOnRootSpace"
            >
              <template v-for="(step, index) in steps" :key="step.id">
                <div class="step-insert-indicator" :style="rootInsertIndicatorStyle(step.id, 'before')"></div>
                <div
                    class="step-item"
                    :class="{
                    'is-selected': selectedKeys.includes(step.id),
                    'is-skipped': !!step.step_is_skipped,
                    'is-skip-inherited': isStepSkipInherited(step.id),
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
                  <div class="step-item-distance" :class="{ 'has-children-guide': stepDefinitions[step.type]?.allowChildren && isStepExpanded(step.id) }">
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
                              :icon="isStepExpanded(step.id) ? 'gravity-ui:chevron-up' : 'gravity-ui:chevron-down'"
                              :size="14"
                          />
                        </template>
                      </n-button>
                      <n-button
                          text
                          size="tiny"
                          @click.stop="toggleSkipStep(step.id, $event)"
                          class="action-btn"
                          :title="step.step_is_skipped ? '取消注释(恢复执行)' : '注释(跳过执行)'"
                      >
                        <template #icon>
                          <TheIcon
                              :icon="step.step_is_skipped ? 'gravity-ui:eye' : 'gravity-ui:eye-slash'"
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
                          <TheIcon icon="gravity-ui:square-article" :size="14"/>
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
                        :depth="1"
                    />
                    <!-- 引用步骤：展示公共脚本内的步骤（只读、递归子级，不参与保存） -->
                    <div v-if="step.type === 'quote'" class="quote-inner-steps">
                      <div class="quote-inner-list">
                        <div
                            v-for="(item, idx) in getQuoteStepsFlattened(quoteStepsMap[step.id] || [])"
                            :key="'quote-' + step.id + '-' + idx + '-' + (item.step.id || '')"
                            class="step-item quote-inner-item"
                            :class="{
                              'is-selected': selectedKeys.includes(getQuoteInnerKey(step.id, idx)),
                              'is-skipped': !!item.step.step_is_skipped || !!step.step_is_skipped,
                            }"
                            :style="{ marginLeft: (item.depth * 16) + 'px' }"
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
                <div class="step-insert-indicator" :style="rootInsertIndicatorStyle(step.id, 'after')"></div>
              </template>
              <AddStepPopover
                  v-if="!isPublicApiCase || steps.length === 0"
                  :is-public-family-case="isPublicFamilyCase"
                  :is-public-api-case="isPublicApiCase"
                  @select="(key) => handleAddStep(key, null)"
              />
              <!-- 批量上传数据源：隐藏文件选择框，由「添加步骤-数据驱动」触发 -->
              <input
                  ref="batchUploadFileRef"
                  type="file"
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  style="display: none"
                  @change="onBatchUploadFileChange"
              />
            </div>
          </n-card>
        </div>
        <div
            v-show="!leftPanelCollapsed"
            class="steps-split-resizer"
            :class="{ 'is-resizing': leftPanelResizing }"
            role="separator"
            aria-orientation="vertical"
            aria-label="调整步骤树宽度"
            title="拖动调整宽度 · 双击折叠"
            @mousedown="startResizeLeftPanel"
            @dblclick.prevent="collapseLeftPanel"
        >
          <span class="steps-split-resizer__line" aria-hidden="true" />
          <span class="steps-split-resizer__handle" aria-hidden="true">
            <TheIcon icon="mdi:drag-vertical" :size="14" />
          </span>
        </div>
        <div class="right-column steps-split-main">
          <div class="config-panel overlay-scroll">
            <component
                v-if="currentStep"
                ref="activeStepEditorRef"
                :key="currentStep.id + (currentStep.isQuoteInner ? '-readonly' : '')"
                :is="editorComponent"
                v-bind="editorComponentProps"
                @update:config="(val) => { if (!currentStep?.isQuoteInner) updateStepConfig(currentStep.id, val) }"
            />
            <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
          </div>
        </div>
        <button
            v-if="leftPanelCollapsed"
            type="button"
            class="steps-split-expand"
            title="展开步骤树"
            @click="expandLeftPanel"
        >
          <TheIcon icon="line-md:chevron-right" :size="16" />
        </button>
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
        v-model:debug-loading="debugLoading"
    />

    <CaseHistoryDrawer
        v-model:show="historyDrawerVisible"
        :case-row="historyCaseRow"
        :single-dataset-only="true"
    />
  </AppPage>
</template>

<script setup>
/**
 * index.vue — API 自动化「步骤编辑」页编排层
 *
 * 本文件：左侧步骤树、右侧动态编辑器、步骤树 CRUD、前后端映射、保存/加载。
 * CaseInfoPanel：用例信息；ExecConfigModal：调试配置；ScriptSelectDrawer：选脚本；AddStepPopover：添加步骤菜单。
 */
defineOptions({ name: '步骤编辑' })
import {computed, h, nextTick, onActivated, onMounted, provide, ref, watch} from 'vue'
import {useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate} from 'vue-router'
import {useElementHover} from '@vueuse/core'
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
import StepSourceJsonPanel from './components/StepSourceJsonPanel.vue'
import CaseHistoryDrawer from '@/views/autotest/testcase/components/CaseHistoryDrawer.vue'
import ScriptSelectDrawer from './components/ScriptSelectDrawer.vue'
import ExecConfigModal from './components/ExecConfigModal.vue'
import AddStepPopover from './components/AddStepPopover.vue'
import RecursiveStepChildren from './components/RecursiveStepChildren.vue'
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiTcpEditor from "@/views/autotest/tcp_controller/index.vue";
import ApiDatabaseEditor from "@/views/autotest/database_controller/index.vue";
import ApiRedisEditor from "@/views/autotest/redis_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";
import ApiUserVariablesEditor from "@/views/autotest/user_variables_controller/index.vue";
import ApiQuoteEditor from "@/views/autotest/quote_controller/index.vue";
import ApiAssertEditor from "@/views/autotest/assert_controller/index.vue";
import api from "@/api";
import { mapBackendStep } from './utils/stepTreeMap'
import { resolveCaseIdFromSteps, toPositiveCaseId } from './utils/prepareCaseExecute'
import {
  stringifyStepTreePayload,
  stripIdentityFieldsForNewCase,
} from './utils/stepSourceJson'
import {useUserStore, useAutotestStore, useStepEditorStore, useTagsStore, useAppStore} from '@/store'
import { useDirtyCheck, useLeftPanelResize, useStepTreeValidation, getFixedBranchStepDisplayName, useStepTreeSerialization, assignStepNumbers, mergeStepTreeWithSuccessDetail, useStepDragDrop, useQuoteSteps, getQuoteInnerKey, getQuoteStepsFlattened, useSourceJsonMode, useDataSourceBatch } from '@/composables/step-editor'

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
  redis: {label: 'Redis请求', allowChildren: false, icon: 'ph:file-rs'},
  quote: {label: '引用公共脚本', allowChildren: false, icon: 'gravity-ui:link'},
  assert: {label: '断言', allowChildren: false, icon: 'material-symbols:rule'},
}

const {
  validateStepNames: validateStepNamesInSteps,
  validateHttpTcpStepsRequired,
  validateJsonBodyInSteps,
  validateXmlBodyInSteps,
  validateDatabaseSteps,
  validateRedisSteps,
  validateEmptyKeyInSteps,
  validateExtractAssertInSteps,
} = useStepTreeValidation({ stepDefinitions })

const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  tcp: ApiTcpEditor,
  http: ApiHttpEditor,
  database: ApiDatabaseEditor,
  redis: ApiRedisEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor,
  user_variables: ApiUserVariablesEditor,
  quote: ApiQuoteEditor,
  assert: ApiAssertEditor,
}

let seed = 1000
/** 生成前端步骤唯一 id（保存前无后端 step_code 时使用） */
const genId = () => `step-${seed++}`

const steps = ref([])
const selectedKeys = ref([])
const route = useRoute()
const router = useRouter()
const autotestStore = useAutotestStore()
const tagsStore = useTagsStore()
const appStore = useAppStore()
const caseId = computed(() => route.query.case_id || null)
const caseCode = computed(() => route.query.case_code || null)

/** 从页签 fullPath 解析 case_id / case_code */
function parseCaseFromTagPath(path) {
  try {
    const idx = String(path).indexOf('?')
    if (idx === -1) return { caseId: null, caseCode: null }
    const q = new URLSearchParams(String(path).slice(idx + 1))
    return { caseId: q.get('case_id'), caseCode: q.get('case_code') }
  } catch {
    return { caseId: null, caseCode: null }
  }
}

/** 关闭页签后：清内存缓存并标记下次进入强制拉接口 */
function markCaseNeedsFreshLoad(cid, ccode) {
  autotestStore.clearStepTreeCache(cid, ccode)
  autotestStore.markStepEditorFreshLoad(cid, ccode)
}

/**
 * 源数据「应用」带入的用例标识（路由可能尚无 case_id/case_code）。
 * 序列化 / 保存时优先路由，其次本字段，再次步骤树 original。
 */
const appliedCaseMeta = ref({ case_id: null, case_code: null })
/** 已加载内容对应的路由 case_info 快照：与 appliedCaseMeta 共同判断 keep-alive 重新激活时路由是否变化 */
const loadedCaseInfo = ref(undefined)

/** 用例信息子组件 ref：表单、校验、项目列表 */
const caseInfoPanelRef = ref(null)
/** 用例信息面板包裹容器 ref：用于检测鼠标是否悬停在面板区域 */
const caseInfoWrapRef = ref(null)
/** 鼠标是否悬停在「用例信息」面板区域 */
const hoveringCaseInfo = useElementHover(caseInfoWrapRef)
/** 当前步骤编辑器 ref：用于保存步骤树前先保存数据源 */
const activeStepEditorRef = ref(null)
/** 执行/调试环境配置弹窗 ref */
const execConfigModalRef = ref(null)
/** 引用/复制脚本抽屉 ref */
const scriptSelectDrawerRef = ref(null)

const {
  leftPanelWidth,
  leftPanelCollapsed,
  leftPanelResizing,
  loadLeftPanelWidth,
  startResizeLeftPanel,
  collapseLeftPanel,
  expandLeftPanel,
} = useLeftPanelResize()

const {
  resolveCaseMetaForPayload,
  convertStepToBackend,
  buildUpdateOrCreateTreePayload,
} = useStepTreeSerialization({ steps, caseId, caseCode, appliedCaseMeta, caseInfoPanelRef })

/** 右侧步骤编辑器使用的「所属应用」选项（来自 CaseInfoPanel） */
const editorProjectOptions = computed(() => {
  const p = caseInfoPanelRef.value?.projectOptions
  return p?.value ?? p ?? []
})
const editorProjectLoading = computed(() => {
  const p = caseInfoPanelRef.value?.projectLoading
  return p?.value ?? p ?? false
})

/** 当前用例是否属于「公共家族」（公共脚本/公共接口：禁用树内「引用公共脚本」入口、不支持数据源） */
const isPublicFamilyCase = computed(() => ['公共脚本', '公共接口'].includes(caseInfoPanelRef.value?.caseForm?.case_type))

/** 当前用例是否为「公共接口」（仅允许 1 个 HTTP/TCP 请求步骤） */
const isPublicApiCase = computed(() => caseInfoPanelRef.value?.caseForm?.case_type === '公共接口')


const scriptDrawerMode = ref('quote')
const quotePublicScriptDrawerVisible = ref(false)
const quotePublicScriptParentId = ref(null)
const quotePublicScriptReplaceStepId = ref(null)
// 复制模式：已选待复制的用例列表
const selectedForCopy = ref([])
const quotePublicScriptQueryItems = ref({
  case_name: '',
  case_type: '',
  created_user: ''
})

// 复制模式用例类型选项（支持全部、公共脚本、公共接口、用户脚本）
const caseTypeOptionsForCopy = [
  { label: '全部', value: '' },
  { label: '公共脚本', value: '公共脚本' },
  { label: '公共接口', value: '公共接口' },
  { label: '用户脚本', value: '用户脚本' }
]

// 请求前规范化入参：quote 模式查公共家族（公共脚本+公共接口）；copy 模式支持 case_type（全部/公共/用户），并排除当前用例（不可复制自己）
const getScriptListForDrawer = (params) => {
  const body = {...params}
  if (scriptDrawerMode.value === 'quote') {
    delete body.case_type
    body.case_types = ['公共脚本', '公共接口']
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
  quotePublicScriptQueryItems.value.case_type = ''
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


/** 用例类型切换（仅用户下拉触发）：公共家族时移除/暂存引用步骤与数据源，用户脚本时恢复；公共接口还需步骤树合规，不合规则阻断并回退选择 */
const onCaseTypeChange = ({ newType, oldType }) => {
  if (newType === '公共脚本') {
    const fromUserScript = oldType === '用户脚本'
    const toStash = fromUserScript ? collectQuoteStepsWithPosition() : []
    const removedCount = removeAllQuoteSteps()
    // 公共脚本不允许使用数据源：清空各 HTTP/TCP 步骤的数据源指针并暂存（保存时才真正解绑后端记录）
    stashedDataSourceWhenPublic.value = stashAndClearDataSourceBindings()
    if (removedCount > 0) {
      if (fromUserScript) {
        stashedQuoteStepsWhenPublic.value = toStash
        window.$message?.warning?.(`切换为公共脚本，已临时移除${removedCount}个引用公共脚本步骤，若误操作可切回用户脚本恢复`)
      } else {
        window.$message?.warning?.(`切换为公共脚本，已自动移除${removedCount}个引用公共脚本步骤，公共脚本不允许引用其他脚本`)
      }
    } else {
      window.$message?.info?.('已切换为公共脚本')
    }
  } else if (newType === '公共接口') {
    // 合规校验：至多 1 个根步骤且必须为 HTTP/TCP（容器/引用/变量等其他类型一律不合规），不合规则阻断切换并回退下拉选择
    const nonCompliant = steps.value.length > 1
        || (steps.value.length === 1 && !['http', 'tcp'].includes(steps.value[0].type))
    if (nonCompliant) {
      if (caseInfoPanelRef.value?.caseForm) {
        caseInfoPanelRef.value.caseForm.case_type = oldType
      }
      window.$message?.error?.('不允许切换为公共接口：公共接口有且仅允许 1 个 HTTP/TCP 请求步骤')
      return
    }
    // 与公共脚本一致：暂存并清空数据源绑定（引用步骤已被合规校验拦截，无需移除）
    stashedDataSourceWhenPublic.value = stashAndClearDataSourceBindings()
    window.$message?.info?.('已切换为公共接口')
  } else if (newType === '用户脚本') {
    const restoredCount = stashedQuoteStepsWhenPublic.value.length > 0 ? restoreStashedQuoteSteps() : 0
    restoreStashedDataSourceBindings()
    window.$message?.info?.(restoredCount > 0
        ? `已切换为用户脚本，并恢复${restoredCount}个引用公共脚本步骤`
        : '已切换为用户脚本')
  }
}

const debugLoading = ref(false)
const saveLoading = ref(false)

const historyDrawerVisible = ref(false)
const historyCaseRow = ref(null)

function openCaseHistory() {
  const id = caseId.value
  if (id == null || id === '') {
    window.$message?.warning?.('请先保存用例后再查看历史')
    return
  }
  historyCaseRow.value = { case_id: Number(id) }
  historyDrawerVisible.value = true
}

/** 与后端 AutoTestStepTreeExecute.case_id 一致：优先路由 case_id，否则已应用源数据，再从步骤树 original 递归解析 */
const resolveNumericCaseIdForExecuteApi = () => {
  const fromRoute = toPositiveCaseId(caseId.value)
  if (fromRoute != null) return fromRoute
  const fromApplied = toPositiveCaseId(appliedCaseMeta.value?.case_id)
  if (fromApplied != null) return fromApplied
  return resolveCaseIdFromSteps(steps.value, null)
}

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

// 条件分支单个分支(IF/ELIF/ELSE)的折叠状态，key = `${stepId}:${branchIndex}`，默认展开
const branchCollapseStates = ref(new Map())

const isBranchCollapsed = (stepId, branchIndex) => {
  return branchCollapseStates.value.get(`${stepId}:${branchIndex}`) ?? false
}

const toggleBranchCollapse = (stepId, branchIndex, event) => {
  event?.stopPropagation()
  const key = `${stepId}:${branchIndex}`
  branchCollapseStates.value.set(key, !isBranchCollapsed(stepId, branchIndex))
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

const {
  dragState,
  handleDragStart,
  handleDragOver,
  handleDragLeave,
  handleDragOverInChildrenArea,
  handleDragLeaveInChildrenArea,
  handleDragOverOnChild,
  handleDragLeaveOnChild,
  handleDragOverOnRootSpace,
  handleDragLeaveOnRootSpace,
  handleDropOnRootSpace,
  handleDrop,
} = useStepDragDrop({ steps, stepDefinitions, findStep })

const rootInsertIndicatorStyle = (targetId, position) => {
  const ds = dragState.value
  const show = ds.draggingId
      && ds.insertTargetId === targetId
      && ds.insertPosition === position
      && !ds.dragOverParent
  return { display: show ? 'block' : 'none' }
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

const {
  quoteStepsMap,
  stashedQuoteStepsWhenPublic,
  stashedDataSourceWhenPublic,
  forEachStepWithQuote,
  loadQuoteStepsForStep,
  loadQuoteStepsForAllQuoteSteps,
  loadQuoteStepsForAllQuoteStepsAsync,
  fillQuoteStepsMapFromRawData,
  getQuoteInnerStep,
  removeAllQuoteSteps,
  collectQuoteStepsWithPosition,
  restoreStashedQuoteSteps,
  stashAndClearDataSourceBindings,
  restoreStashedDataSourceBindings,
} = useQuoteSteps({
  steps,
  findStep,
  findStepParent,
  removeStep: (id) => removeStep(id),
  stepExpandStates,
  selectedKeys,
  updateStepDisplayNames: () => updateStepDisplayNames(),
})

/** 祖先是否被跳过（继承灰显；子开关可保留但不生效） */
const isStepSkipInherited = (id) => {
  let parent = findStepParent(id)
  while (parent) {
    if (parent.step_is_skipped) return true
    parent = findStepParent(parent.id)
  }
  return false
}

/** 切换步骤跳过/注释标记 */
const toggleSkipStep = (id, event) => {
  event?.stopPropagation?.()
  const step = findStep(id)
  if (!step) return
  step.step_is_skipped = !step.step_is_skipped
  if (step.original) step.original.step_is_skipped = step.step_is_skipped
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
  const redisOps = cfg.redis_operates ?? orig.redis_operates
  const redisList = !redisOps ? [] : Array.isArray(redisOps) ? redisOps : Object.values(redisOps)
  redisList.forEach((x) => {
    if (x && x.variable_name) names.push(String(x.variable_name).trim())
  })
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

const buildSourceJsonFromMemoryTree = () => stringifyStepTreePayload(buildUpdateOrCreateTreePayload())

const {
  treeMode,
  sourceJsonText,
  sourceJsonApplyLoading,
  isSourceJsonDirty,
  resetSourceJson,
  applySourceJsonFromEditor,
  handleTreeModeChange,
} = useSourceJsonMode({
  steps,
  caseId,
  caseCode,
  appliedCaseMeta,
  stepExpandStates,
  selectedKeys,
  caseInfoPanelRef,
  stepDefinitions,
  buildSourceJsonFromMemoryTree,
  updateStepDisplayNames: () => updateStepDisplayNames(),
  loadQuoteStepsForAllQuoteSteps,
  notifyError,
})

const { isDirty, markSaved: markDirtySaved, markLoaded: markDirtyLoaded, reset: resetDirty, confirmIfDirty } = useDirtyCheck(buildSourceJsonFromMemoryTree)

// 离开「步骤编辑」路由时拦截未保存改动。
// 注意：仅「切换标签」选离开时必须保活内存态，不可在此强制刷新/resetDirty，
// 否则回来后编辑内容会被接口数据覆盖；强制拉数只在「关闭页签」时由下方 watch 处理。
onBeforeRouteLeave(async () => {
  // 保存流程中会 replace query 写入 case_id，此时不应弹「未保存」确认
  if (saveLoading.value) return true
  return await confirmIfDirty()
})

// 同一路由内切换用例（多个「步骤编辑」标签页之间，仅 query 变化、组件复用）时，
// 触发的是 onBeforeRouteUpdate 而非 onBeforeRouteLeave，需同样拦截未保存改动
onBeforeRouteUpdate(async () => {
  if (saveLoading.value) return true
  return await confirmIfDirty()
})

/**
 * 关闭「步骤编辑」导航页签：清该用例缓存并标记强制刷新。
 * 若已无任何步骤编辑页签，重置 KeepAlive（组件名/路由名「步骤编辑」），避免共用 path key 的缓存实例残留。
 * 仅切换页签（页签仍在列表中）不会触发，保持保活。
 */
watch(
    () => tagsStore.tags.map((t) => ({ path: t.path, name: t.name })),
    (tagList, prevTagList) => {
      if (!Array.isArray(prevTagList)) return
      const paths = tagList.map((t) => t.path)
      const removed = prevTagList.filter(
          (t) => !paths.includes(t.path) && String(t.path).startsWith('/autotest/steps'),
      )
      if (!removed.length) return
      for (const t of removed) {
        const { caseId: cid, caseCode: ccode } = parseCaseFromTagPath(t.path)
        markCaseNeedsFreshLoad(cid, ccode)
      }
      const stepsTagLeft = paths.some((p) => String(p).startsWith('/autotest/steps'))
      if (!stepsTagLeft) {
        // 此时路由可能已切到其它页，不能用当前 route.name；与 defineOptions/菜单名对齐
        const aliveName = removed[0]?.name || '步骤编辑'
        appStore.setAliveKeys(aliveName, String(Date.now()))
      }
    },
)



/** 校验用例与步骤树后调用 updateOrCreateStepTree 保存 */
const handleSaveAll = async () => {
  if (!treeMode.value) {
    window.$message?.warning?.('源数据模式下不可直接保存，请先应用 JSON 并切回步骤树模式后再点击保存')
    return
  }
  if (saveLoading.value) return
  if (!steps.value?.length) {
    window.$message?.warning?.('请至少添加一个步骤后再点击保存')
    return
  }
  saveLoading.value = true
  try {
    // 等待步骤编辑器将表单防抖同步到 step.config（约 300ms），避免校验/落库读到过期提取断言配置
    await new Promise((resolve) => setTimeout(resolve, 320))

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

    // 公共接口：所属应用/步骤描述/步骤名称兜底同步（用户可能从未点开步骤子页面，watch未覆盖时在此强制对齐）；
    // 必须在 required 校验之前执行：应用变化需同步清空配置名称，由校验拦截强制用户重新选择
    if (isPublicApiCase.value && steps.value.length === 1 && ['http', 'tcp'].includes(steps.value[0]?.type)) {
      const casePid = caseInfoPanelRef.value?.caseForm?.case_project
      const caseDesc = caseInfoPanelRef.value?.caseForm?.case_desc ?? ''
      const caseName = caseInfoPanelRef.value?.caseForm?.case_name ?? ''
      const onlyStep = steps.value[0]
      const syncConfig = {}
      if (casePid != null && casePid !== '' && Number(onlyStep.config?.request_project_id) !== Number(casePid)) {
        syncConfig.request_project_id = Number(casePid)
        syncConfig.request_config_name = null
      }
      if ((onlyStep.config?.step_desc ?? '') !== caseDesc) {
        syncConfig.step_desc = caseDesc
      }
      if ((onlyStep.config?.step_name ?? '') !== caseName) {
        syncConfig.step_name = caseName
      }
      if (Object.keys(syncConfig).length) {
        updateStepConfig(onlyStep.id, syncConfig)
      }
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

    // 请求体为 xml 时校验 XML 语法，有错误则提示并阻止保存
    const xmlValidation = validateXmlBodyInSteps(steps.value)
    if (!xmlValidation.valid) {
      window.$message?.error?.(
          `步骤：${xmlValidation.stepName}，请求体XML格式错误，请修正后再保存`
      )
      return
    }

    const dbValidation = validateDatabaseSteps(steps.value)
    if (!dbValidation.valid) {
      window.$message?.error?.(dbValidation.message)
      return
    }

    const redisValidation = validateRedisSteps(steps.value)
    if (!redisValidation.valid) {
      window.$message?.error?.(redisValidation.message)
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

    const extractAssertValidation = validateExtractAssertInSteps(steps.value)
    if (!extractAssertValidation.valid) {
      notifyError(extractAssertValidation.message)
      return
    }

    // 公共接口约束（与后端 _validate_public_api_tree 对齐，前置拦截提升体验）：仅 1 步且为 HTTP/TCP
    if (isPublicApiCase.value) {
      const nonCompliant = steps.value.length !== 1 || !['http', 'tcp'].includes(steps.value[0]?.type)
      if (nonCompliant) {
        notifyError('公共接口用例有且仅允许 1 个 HTTP/TCP 请求步骤，请调整后再保存')
        return
      }
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
    const isNewCasePage = toPositiveCaseId(caseId.value) == null && !caseCode.value
    const casePayload = caseInfoPanelRef.value?.getCasePayload?.() ?? {}
    let caseInfo
    if (isNewCasePage) {
      caseInfo = {
        case_id: null,
        case_code: null,
        ...casePayload,
        case_steps: totalSteps,
        updated_user: currentUser,
      }
    } else {
      const caseMeta = resolveCaseMetaForPayload()
      caseInfo = {
        case_id: caseMeta.case_id,
        case_code: caseMeta.case_code,
        ...casePayload,
        case_steps: totalSteps,
        updated_user: currentUser,
      }
    }

    // 按照树的前序遍历顺序分配 step_no，确保唯一且按顺序递增
    const stepNoMap = assignStepNumbers(steps.value)

    // 转换步骤数据，使用分配好的 step_no，并保持树结构
    const backendSteps = steps.value.map((step) => {
      return convertStepToBackend(step, null, stepNoMap)
    })

    // 构建请求体（AutoTestStepTreeUpdateList 格式）；新建不传主键与 steps[].case
    let payload = {
      case: caseInfo,
      steps: backendSteps
    }
    if (isNewCasePage) {
      payload = stripIdentityFieldsForNewCase(payload)
    }

    // 调用后端接口前，先保存当前步骤编辑器中的数据源（如有未提交的编辑）
    // 复制的新步骤此时尚无 step_code，会返回 skipped，待步骤落库获得 step_code 后再补存
    const dataSourceSavedBefore = await activeStepEditorRef.value?.saveDataSource?.()

    // 调用新的后端接口
    const res = await api.updateOrCreateStepTree(payload)
    if (res?.code === '000000' || res?.code === 200 || res?.code === 0) {
      window.$message?.success?.(res?.message || '保存成功')

      // 将本次保存返回的 step_id/step_code 写回当前步骤树，避免重复点击保存时再次被当作新增
      const stepDetail = res?.data?.steps?.success_detail
      if (Array.isArray(stepDetail) && stepDetail.length > 0) {
        mergeStepTreeWithSuccessDetail(steps.value, stepDetail)
        // 复制的新步骤保存前无 step_code，数据源未保存；步骤落库获得 step_code 后再保存一次数据源（含用户在面板的修改）
        if (dataSourceSavedBefore?.skipped) {
          await nextTick()
          await activeStepEditorRef.value?.saveDataSource?.()
        }
      }

      // 先刷新脏检测基准，再改 URL：新建保存会 replace case_id，否则 onBeforeRouteUpdate 会误判未保存
      markDirtySaved()

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

      // 公共家族(公共脚本/公共接口)不允许使用数据源：树保存成功后真正解绑（清空步骤指针 + 软删数据源记录）。
      // 必须在树保存之后执行，否则树保存会用非空指针把已清空的列重新写回。
      if (isPublicFamilyCase.value) {
        const savedCaseId = toPositiveCaseId(caseId.value)
            ?? toPositiveCaseId(res?.data?.cases?.success_detail?.[0]?.case_id)
        if (savedCaseId) {
          try {
            await api.unbindCaseDataSource({ case_id: savedCaseId })
          } catch (e) {
            console.error('解绑公共脚本数据源失败', e)
            window.$message?.warning?.('保存成功，但解绑数据源失败，请重试或检查数据源面板')
          }
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

/** 调试：校验当前步骤树后打开调试配置弹窗 */
const handleDebug = async () => {
  if (!treeMode.value) {
    window.$message?.warning?.('源数据模式下不可调试，请先切回步骤树模式')
    return
  }
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
  const redisValidation = validateRedisSteps(steps.value)
  if (!redisValidation.valid) {
    window.$message?.error?.(redisValidation.message)
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
        execute_type: '调试执行',
        steps: backendSteps,
        initial_variables: [],
        steps_execute_config: step_exec_config_map || undefined,
        ...datasetPart,
      }
    },
  })
}

/**
 * 【用例管理「复制」】从路由 case_info 加载步骤树（不请求 DB）
 * @param {object} caseInfo - 含 is_copy、steps，及用例表单字段
 * @returns {boolean} 是否成功按复制模式加载
 */
const loadStepsFromCopy = (caseInfo) => {
  if (!caseInfo || caseInfo.is_copy !== true) return false

  quoteStepsMap.value = {}
  caseInfoPanelRef.value?.reloadFromRoute?.()

  const rawSteps = Array.isArray(caseInfo.steps) ? caseInfo.steps : []
  const mappedSteps = rawSteps.map(mapBackendStep).filter(Boolean)
  steps.value = mappedSteps
  selectedKeys.value = [mappedSteps[0]?.id].filter(Boolean)
  fillQuoteStepsMapFromRawData(rawSteps, mappedSteps)
  initializeStepExpandStates()
  updateStepDisplayNames()
  return true
}

const loadSteps = async ({ force = false } = {}) => {
  stepExpandStates.value = new Map()
  stashedQuoteStepsWhenPublic.value = []
  stashedDataSourceWhenPublic.value = []
  appliedCaseMeta.value = {
    case_id: toPositiveCaseId(caseId.value),
    case_code: caseCode.value ? String(caseCode.value) : null,
  }
  loadedCaseInfo.value = route.query.case_info
  if (!caseId.value && !caseCode.value) {
    // 检查是否为复制进入：case_info 含 is_copy 和 steps
    const caseInfoStr = route.query.case_info
    if (caseInfoStr) {
      try {
        const caseInfo = JSON.parse(caseInfoStr)
        if (loadStepsFromCopy(caseInfo)) {
          nextTick(() => markDirtyLoaded())
          return
        }
      } catch (_) {}
    }
    steps.value = []
    selectedKeys.value = []
    appliedCaseMeta.value = { case_id: null, case_code: null }
    caseInfoPanelRef.value?.hydrateFromStepTree?.([])
    // 新增页展开用例信息面板，便于填写（覆盖上一用例自动折叠后的收起状态）
    if (caseInfoPanelRef.value) caseInfoPanelRef.value.caseInfoCollapsed = false
    nextTick(() => markDirtyLoaded())
    return
  }
  // 关闭页签或外部标记 freshLoad 后强制走接口；普通切换页签仍可用缓存
  const forceRefresh = force || autotestStore.consumeStepEditorFreshLoad(caseId.value, caseCode.value)
  if (!forceRefresh) {
    const cached = autotestStore.getStepTreeCache(caseId.value, caseCode.value)
    if (cached) {
      caseInfoPanelRef.value?.hydrateFromStepTree?.(cached.rawData)
      steps.value = JSON.parse(JSON.stringify(cached.steps)).filter(Boolean)
      selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
      quoteStepsMap.value = {}
      fillQuoteStepsMapFromRawData(cached.rawData, steps.value)
      nextTick(() => markDirtyLoaded())
      return
    }
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
    nextTick(() => markDirtyLoaded())
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

/**
 * 自动折叠「用例信息」面板。
 * 四个条件需同时满足：用例信息已全部填写完成、用户已激活其他操作（选中了步骤/进入子页面）、
 * 鼠标不在用例信息面板区域、面板内没有展开的选择弹层（下拉菜单 teleport 到 body，
 * 鼠标移入菜单时会离开面板区域，若此时折叠会导致无法继续选择）。
 */
const tryAutoCollapseCaseInfo = () => {
  if (!caseInfoPanelRef.value) return
  const complete = caseInfoPanelRef.value.validateCaseForm?.().valid === true
  const activated = selectedKeys.value.length > 0
  const dropdownOpen = caseInfoPanelRef.value.anyDropdownOpen === true
  if (complete && activated && !hoveringCaseInfo.value && !dropdownOpen) {
    caseInfoPanelRef.value.caseInfoCollapsed = true
  }
}

/** 自动折叠延迟（毫秒）：避免鼠标短暂离开面板时立即折叠 */
const AUTO_COLLAPSE_DELAY = 500
let collapseTimer = null
const scheduleAutoCollapse = () => {
  if (collapseTimer) clearTimeout(collapseTimer)
  collapseTimer = setTimeout(() => {
    collapseTimer = null
    tryAutoCollapseCaseInfo()
  }, AUTO_COLLAPSE_DELAY)
}
const cancelScheduledCollapse = () => {
  if (collapseTimer) {
    clearTimeout(collapseTimer)
    collapseTimer = null
  }
}

/** 选中步骤变化（点击步骤树/进入子页面）时延时尝试自动折叠用例信息面板 */
watch(currentStep, () => {
  scheduleAutoCollapse()
})

/** 鼠标移出用例信息面板时延时尝试折叠；鼠标移回则取消（覆盖「先选中步骤、鼠标随后移出面板」的场景） */
watch(hoveringCaseInfo, (hovering) => {
  if (hovering) {
    cancelScheduledCollapse()
  } else {
    scheduleAutoCollapse()
  }
})

/** 选择弹层展开时取消折叠；关闭后延时补一次折叠判定（弹层展开期间鼠标已移出面板） */
watch(() => caseInfoPanelRef.value?.anyDropdownOpen, (open) => {
  if (open) {
    cancelScheduledCollapse()
  } else {
    scheduleAutoCollapse()
  }
})

const currentEditorNeedsProject = computed(() => {
  const t = currentStep.value?.type
  return t === 'http' || t === 'tcp' || t === 'database' || t === 'redis' || t === 'quote'
})

const currentEditorNeedsVarAssist = computed(() => {
  const t = currentStep.value?.type
  return t === 'http' || t === 'user_variables'
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
  if (step.type === 'http' || step.type === 'tcp') {
    props.hideDataSource = isPublicFamilyCase.value
    // 公共接口：Request 面板「所属应用」锁定为用例所属应用（只读），由父级监听强制同步
    props.lockProject = isPublicApiCase.value
    props.caseProjectId = isPublicApiCase.value ? (caseInfoPanelRef.value?.caseForm?.case_project ?? null) : null
    // 公共接口：Request 面板「步骤描述」锁定为用例描述（只读），由父级监听强制同步
    props.lockStepDesc = isPublicApiCase.value
    props.caseDesc = isPublicApiCase.value ? (caseInfoPanelRef.value?.caseForm?.case_desc ?? '') : null
    // 公共接口：Request 面板「步骤名称」锁定为用例名称（只读），由父级监听强制同步
    props.lockStepName = isPublicApiCase.value
    props.caseName = isPublicApiCase.value ? (caseInfoPanelRef.value?.caseForm?.case_name ?? '') : null
  }
  return props
})

/** 公共接口：请求步骤「所属应用/步骤描述/步骤名称」强制同步用例信息（新建/切换应用/编辑用例名/切换步骤时兜底） */
watch(
    [
      isPublicApiCase,
      () => caseInfoPanelRef.value?.caseForm?.case_project,
      () => caseInfoPanelRef.value?.caseForm?.case_desc,
      () => caseInfoPanelRef.value?.caseForm?.case_name,
      () => currentStep.value?.id,
    ],
    () => {
      if (!isPublicApiCase.value) return
      const step = currentStep.value
      if (!step || (step.type !== 'http' && step.type !== 'tcp')) return
      const casePid = caseInfoPanelRef.value?.caseForm?.case_project
      const caseDesc = caseInfoPanelRef.value?.caseForm?.case_desc ?? ''
      const caseName = caseInfoPanelRef.value?.caseForm?.case_name ?? ''
      const syncConfig = {}
      if (casePid != null && casePid !== '' && Number(step.config?.request_project_id) !== Number(casePid)) {
        // 应用变化后配置名称必然失效（配置按应用隔离），同步清空强制用户重新选择
        syncConfig.request_project_id = Number(casePid)
        syncConfig.request_config_name = null
      }
      if ((step.config?.step_desc ?? '') !== caseDesc) {
        syncConfig.step_desc = caseDesc
      }
      if ((step.config?.step_name ?? '') !== caseName) {
        syncConfig.step_name = caseName
      }
      if (Object.keys(syncConfig).length) {
        updateStepConfig(step.id, syncConfig)
      }
    },
    { immediate: true }
)

/** 在根或父步骤下插入新步骤节点 */
const insertStep = (parentId, type, index = null, extraConfig = null) => {
  const def = stepDefinitions[type]
  if (!def) return null

  const defaultConfig = type === 'loop'
      ? {loop_mode: '次数循环', loop_on_error: '中断循环', loop_maximums: '5'}
      : type === 'if'
          ? {branch_items: [{_key: genId(), branch_type: 'if', branch_conditions: {condition_expr: '', condition_compare: '非空', condition_value: ''}, branch_desc: ''}]}
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
                      : type === 'redis'
                          ? {
                            step_name: 'Redis请求',
                            step_desc: '',
                            redis_searched: false,
                            redis_operates: [],
                            extract_variables: [],
                            assert_validators: []
                          }
                          : type === 'assert'
                              ? {
                                step_name: '断言',
                                assert_validators: []
                              }
                              : {}
  const defaultName = type === 'loop'
      ? '循环结构(次数循环)'
      : type === 'if'
          ? '条件分支'
          : type === 'wait'
              ? '控制等待(2秒)'
              : type === 'user_variables'
                  ? '用户定义变量'
                  : type === 'database'
                      ? '数据库请求'
                      : type === 'redis'
                          ? 'Redis请求'
                          : type === 'assert'
                              ? '断言'
                              : type === 'quote' && extraConfig?.step_name
                                  ? extraConfig.step_name
                                  : `${def.label}`
  const config = extraConfig ? {...defaultConfig, ...extraConfig} : defaultConfig
  const newStep = {
    id: genId(),
    type,
    name: type === 'quote' && config.step_name ? config.step_name : defaultName,
    step_is_skipped: false,
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
    quotePublicScriptQueryItems.value.case_type = ''
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
  // 【数据驱动】批量上传数据源：选择 xlsx 后按 sheet 名匹配步骤批量创建
  if (type === 'batch_upload_datasource') {
    handleBatchUploadDatasource()
    return
  }
  // 【数据驱动】汇总下载数据源：导出该用例所有步骤的数据源
  if (type === 'summary_download_datasource') {
    void handleSummaryDownloadDatasource()
    return
  }
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    updateStepDisplayNames()
  }
}

const handleAddStepToBranch = (type, parentId, branchIndex) => {
  if (type === 'quote_public_script' || type === 'copy_steps' || type === 'batch_upload_datasource' || type === 'summary_download_datasource') {
    handleAddStep(type, parentId)
    return
  }
  const parent = findStep(parentId)
  if (!parent) return
  const created = insertStep(parentId, type)
  if (created) {
    created.branch_index = branchIndex
    const children = parent.children || []
    // 始终重定位到所属分支分组的正确位置（分支末尾；空分支则插入到后续分支之前），
    // 保持 children 数组按分支分组有序：保存时后端按分支序号分组返回 success_detail，
    // 前端回写 step_id/step_code 依赖两边遍历顺序一致，否则标识错配引发 branch_index 错乱
    children.splice(children.indexOf(created), 1)
    const branchChildren = children.filter(c => (c.branch_index ?? 0) === branchIndex)
    let insertIdx
    if (branchChildren.length > 0) {
      insertIdx = children.indexOf(branchChildren[branchChildren.length - 1]) + 1
    } else {
      const laterChild = children.find(c => (c.branch_index ?? 0) > branchIndex)
      insertIdx = laterChild ? children.indexOf(laterChild) : children.length
    }
    children.splice(insertIdx, 0, created)
    selectedKeys.value = [created.id]
    updateStepDisplayNames()
  }
}

const {
  batchUploadFileRef,
  batchUploadLoading,
  summaryDownloadLoading,
  handleBatchUploadDatasource,
  onBatchUploadFileChange,
  handleSummaryDownloadDatasource,
} = useDataSourceBatch({ caseId, loadSteps: () => loadSteps() })


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

/** 条件分支仅更新 branch_items 时：就地合并，避免整包替换 config 加剧响应式抖动 */
const isIfBranchesOnlyPatch = (step, config) => {
  if (!step || step.type !== 'if' || !config?.branch_items) return false
  if (!Array.isArray(config.branch_items)) return false
  return Object.keys(config).length === 1 && Object.keys(config)[0] === 'branch_items'
}

/**
 * 分支结构变化（新增ELIF插入/删除/上下移动）后，按分支稳定标识 _key 重映射子步骤 branch_index：
 * - 分支移动：子步骤跟随分支到新的序号
 * - 分支删除：其子步骤一并移除（否则会错误并入占用原序号的分支）
 * - 新旧任一侧缺少 _key 时跳过（保持原状，退化为按序号对齐）
 */
const remapBranchChildren = (step, oldItems, newItems) => {
  const children = step.children
  if (!Array.isArray(children) || children.length === 0) return
  if (!Array.isArray(oldItems) || !Array.isArray(newItems) || !newItems.length) return
  if (!oldItems.every(b => b?._key) || !newItems.every(b => b?._key)) return
  const newIndexByKey = new Map(newItems.map((b, i) => [b._key, i]))
  const groups = new Map()
  let changed = false
  for (const child of children) {
    const oldIndex = child.branch_index ?? 0
    const oldBranch = oldItems[oldIndex]
    const newIndex = oldBranch ? newIndexByKey.get(oldBranch._key) : undefined
    if (newIndex === undefined) {
      changed = true
      continue
    }
    if (newIndex !== oldIndex) changed = true
    if (!groups.has(newIndex)) groups.set(newIndex, [])
    groups.get(newIndex).push(newIndex === oldIndex ? child : {...child, branch_index: newIndex})
  }
  if (!changed) return
  step.children = [...groups.keys()].sort((a, b) => a - b).flatMap(k => groups.get(k))
}

/** 右侧编辑器更新步骤 config 并同步树展示名 */
const updateStepConfig = (id, config) => {
  const step = findStep(id)
  if (step) {
    if (isIfBranchesOnlyPatch(step, config)) {
      const oldBranchItems = Array.isArray(step.config?.branch_items) ? step.config.branch_items : []
      step.config = {...step.config, branch_items: config.branch_items}
      remapBranchChildren(step, oldBranchItems, config.branch_items)
    } else {
      step.config = {...step.config, ...config}
    }
    // 根据配置更新步骤名称
    const branchFixed = getFixedBranchStepDisplayName(step)
    if (branchFixed) {
      step.name = branchFixed
    } else if (step.type === 'http') {
      // 仅在显式携带 step_name 时同步树展示名；公共接口兜底同步 step_desc/request_project_id 等补丁不含该字段，不得覆盖已有名称
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || 'HTTP请求'
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
    } else if (step.type === 'assert') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '断言'
      }
    } else if (step.type === 'database') {
      if (config.step_name !== undefined && String(config.step_name).trim()) {
        step.name = String(config.step_name).trim()
      } else if (!String(step.name || '').trim()) {
        step.name = '数据库请求'
      }
    } else if (step.type === 'redis') {
      if (config.step_name !== undefined && String(config.step_name).trim()) {
        step.name = String(config.step_name).trim()
      } else if (!String(step.name || '').trim()) {
        step.name = 'Redis请求'
      }
    } else if (step.type === 'quote' || step.type === 'quote_public_script') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '引用公共脚本'
      }
    }
    // 条件分支仅改 branch_items 时左侧树展示名不变，跳过同步刷新减轻输入卡顿
    if (!isIfBranchesOnlyPatch(step, config)) {
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
    redis: 'icon-redis',
    assert: 'icon-assert',
    user_variables: 'icon-user_variables',
    quote: 'icon-quote',
    quote_public_script: 'icon-quote',
  }
  return classMap[type] || ''
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

// 当前路由的 case 上下文（case_id/case_code/case_info）与已加载内容是否不一致（需要重载）
const isRouteCaseStale = () => {
  const meta = appliedCaseMeta.value
  return toPositiveCaseId(caseId.value) !== meta.case_id
      || (caseCode.value ? String(caseCode.value) : null) !== meta.case_code
      || route.query.case_info !== loadedCaseInfo.value
}

// 同页切换用例（仅 query 变化、组件未销毁）时需重新解析 case_info 并拉步骤树；已加载则跳过，避免与 onActivated 重复重载
watch([() => caseId.value, () => caseCode.value, () => route.query.case_info], () => {
  if (!isRouteCaseStale()) return
  resetDirty()
  caseInfoPanelRef.value?.reloadFromRoute?.()
  loadSteps()
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

// keep-alive 重新激活：
// - 切换页签回来且用例未变：保活，不重载
// - 关闭页签后再打开 / 外部 markFreshLoad：hasFreshLoad → 强制拉接口
// - 路由 case 上下文变化：重载
onActivated(() => {
  const needFresh = autotestStore.hasStepEditorFreshLoad(caseId.value, caseCode.value)
  if (!needFresh && !isRouteCaseStale()) return
  if (isRouteCaseStale()) {
    resetDirty()
    caseInfoPanelRef.value?.reloadFromRoute?.()
  }
  loadSteps({ force: needFresh })
})

// 不在 onUpdated 中刷新展示名：每次子编辑器 emit 都会触发父组件 patch，导致输入卡顿/丢字

/**
 * 步骤树上下文：供递归子步骤组件 RecursiveStepChildren 通过 inject 使用。
 * 递归层级深、共享绑定多，用 provide/inject 替代逐层透传 22 个 props。
 */
provide('stepTreeContext', {
  stepDefinitions,
  isStepExpanded,
  toggleStepExpand,
  isBranchCollapsed,
  toggleBranchCollapse,
  selectedKeys,
  getStepIcon,
  getStepIconClass,
  getStepDisplayName,
  getStepNumber,
  handleSelect,
  handleDragStart,
  handleDragOverInChildrenArea,
  handleDragLeaveInChildrenArea,
  handleDragOverOnChild,
  handleDragLeaveOnChild,
  handleDrop,
  handleCopyStep,
  handleDeleteStep,
  toggleSkipStep,
  isStepSkipInherited,
  isPublicFamilyCase,
  handleAddStep,
  handleAddStepToBranch,
  dragState,
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
  position: relative;
  display: flex;
  flex: 1;
  align-items: stretch;
  height: 100%;
  min-height: 0;
  min-width: 0;
}

/* 左右分栏拖拽分隔条：扩大命中区，中间竖线 + 握柄 */
.steps-split-resizer {
  position: relative;
  flex-shrink: 0;
  width: 15px;
  margin: 0 0px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  user-select: none;
  z-index: 2;
  color: var(--n-text-color-3, #999);
}

/* 分隔条中线（常态细线，悬停/拖拽时加粗高亮） */
.steps-split-resizer__line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: var(--n-border-color, rgba(0, 0, 0, 0.08));
  transition: width 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
  pointer-events: none;
}

/* 分隔条中央握柄（悬停/拖拽时强化可见度） */
.steps-split-resizer__handle {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 28px;
  border-radius: 999px;
  background: var(--n-color, #fff);
  border: 1px solid var(--n-border-color, rgba(0, 0, 0, 0.1));
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  opacity: 0.55;
  transform: scale(0.92);
  transition:
    opacity 0.15s ease,
    transform 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease,
    background-color 0.15s ease,
    box-shadow 0.15s ease;
  pointer-events: none;
}

.steps-split-resizer:hover .steps-split-resizer__line,
.steps-split-resizer.is-resizing .steps-split-resizer__line {
  width: 2px;
  background: var(--n-primary-color, #F4511E);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--n-primary-color, #F4511E) 18%, transparent);
}

.steps-split-resizer:hover .steps-split-resizer__handle,
.steps-split-resizer.is-resizing .steps-split-resizer__handle {
  opacity: 1;
  transform: scale(1);
  color: var(--n-primary-color, #F4511E);
  border-color: color-mix(in srgb, var(--n-primary-color, #F4511E) 45%, transparent);
  background: color-mix(in srgb, var(--n-primary-color, #F4511E) 8%, var(--n-color, #fff));
  box-shadow: 0 2px 6px color-mix(in srgb, var(--n-primary-color, #F4511E) 16%, transparent);
}

/* 拖拽进行中：分隔条主题色 */
.steps-split-resizer.is-resizing {
  color: var(--n-primary-color, #F4511E);
}

/* 折叠后：不占布局宽度，浮在左侧边缘中间 */
.steps-split-expand {
  position: absolute;
  left: 0;
  top: 50%;
  z-index: 5;
  transform: translateY(-50%);
  width: 18px;
  height: 40px;
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 0 6px 6px 0;
  background: color-mix(in srgb, var(--n-text-color-3, #999) 12%, transparent);
  color: var(--n-text-color-3, #999);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.steps-split-expand:hover {
  color: var(--n-primary-color, #F4511E);
  background: color-mix(in srgb, var(--n-primary-color, #F4511E) 14%, transparent);
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

/* 右侧明细容器：仅布局滚动，不再套一层 n-card，子页自带红边卡片 */
.config-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  min-height: 0;
  font-size: var(--step-editor-font-size, 13px);
}

/* 步骤树 / 右侧明细：统一由 .overlay-scroll 控制滚动条观感 */
.step-tree-container,
.config-panel {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

.step-tree-container {
  padding: 4px 0;
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
  margin-bottom: 4px;
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

:deep(.step-item.is-skipped .step-name-text),
:deep(.step-item.is-skip-inherited .step-name-text) {
  /* 本步注释 或 祖先已注释：名称删除线弱化 */
  text-decoration: line-through;
  opacity: 0.55;
}

:deep(.step-item.is-skipped),
:deep(.step-item.is-skip-inherited) {
  opacity: 0.85;
}

/* 选中态：虚线框 + 淡橙底（仅作用于本行的名称药丸，子步骤不联动变色——外层边框已足够标注选中范围） */
:deep(.step-item.is-selected) {
  border: 1px dashed #F4511E;
}

:deep(.step-item.is-selected > .step-item-distance > .step-name),
:deep(.step-item.is-selected > .step-item-child > .step-name),
:deep(.quote-inner-item.is-selected > .step-name) {
  background-color: rgba(244, 81, 30, 0.1);
}

/* 所有 loop/if 步骤的普通高亮（拖拽时）：outline 不参与布局，避免行高变化引起整树抖动 */
:deep(.step-item.is-drag-target) {
  outline: 2px solid rgba(244, 81, 30, 0.3);
  outline-offset: -2px;
  background-color: rgba(244, 81, 30, 0.05);
}

/* 焦点高亮（拖拽进入目标区域时） */
:deep(.step-item.is-drag-over) {
  outline: 2px solid #F4511E;
  outline-offset: -2px;
  background-color: rgba(244, 81, 30, 0.15);
  box-shadow: 0 0 12px rgba(244, 81, 30, 0.4);
}

/* 插入位置指示器：零布局占位，可见线条由 ::before 绝对定位绘制，显示/隐藏不再推动相邻行位移 */
:deep(.step-insert-indicator) {
  height: 0;
  margin: 0;
  overflow: visible;
  position: relative;
}

:deep(.step-insert-indicator)::before {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  top: -1px;
  height: 2px;
  background-color: #F4511E;
  border-radius: 1px;
  box-shadow: 0 0 4px rgba(244, 81, 30, 0.6);
}

:deep(.step-item[draggable="true"]) {
  cursor: move;
}

/* 拖放目标区：1px 虚线与分支组框统一；背景色与步骤行同一灰色 token */
:deep(.step-drop-zone) {
  min-height: 28px;
  border: 1px dashed var(--n-border-color);
  border-radius: 8px;
  margin: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background-color: color-mix(in srgb, var(--n-border-color) 35%, transparent);
}

:deep(.step-drop-zone.is-drag-over) {
  border-color: #F4511E;
  background-color: rgba(244, 81, 30, 0.1);
  box-shadow: 0 0 8px rgba(244, 81, 30, 0.3);
}

:deep(.step-drop-zone-hint) {
  color: var(--n-text-color-3);
  font-size: 12px;
  font-weight: 400;
  padding: 4px;
}

:deep(.step-drop-zone.is-drag-over .step-drop-zone-hint) {
  color: #F4511E;
}

/* 层次缩进的唯一机制：每层 = margin-left 8px + padding-left 8px = 16px，全树统一 */
:deep(.step-item-child) {
  padding-left: 8px;
  margin-left: 8px;
  position: relative;
}

/* 缩进参考线：含展开子级的行在其父级缩进槽中央绘制 1px 竖线，贯穿整个子树高度，
   深层嵌套时可沿竖线追踪步骤归属（同级相邻行的线段自动首尾相接形成连续参考线） */
:deep(.step-item-child.has-children-guide)::before,
.step-item-distance.has-children-guide::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: color-mix(in srgb, var(--n-border-color) 45%, transparent);
  pointer-events: none;
}

:deep(.step-item-child.has-children-guide)::before {
  left: 0;
}

.step-item-distance {
  position: relative;
}

.step-item-distance.has-children-guide::before {
  left: 8px;
}

/* 名称药丸：浅灰底（全局唯一的浅灰面板 token），hover 文字+底色同时转主题色 */
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
  transition: background-color 0.2s;
}

:deep(.step-name:hover) {
  color: #F4511E;
  background-color: rgba(244, 81, 30, 0.08);
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

:deep(.step-icon.icon-redis) {
  color: #BA55D3;
}

:deep(.step-icon.icon-assert) {
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
  padding-top: 3px;
  padding-left: 8px;
}

/* 引用步骤内嵌树：与主步骤树共用 .step-item / .step-name 样式，仅保留结构缩进与左侧引导线 */
:deep(.quote-inner-steps) {
  margin: 3px 0 3px 8px;
  border-left: 2px solid #F4511E;
  border-radius: 8px;
  padding-left: 6px;
}

:deep(.quote-inner-list) {
  margin-top: 0;
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
  font-size: 12px;
  font-weight: 400;
  color: var(--n-text-color-3);
  padding: 4px 0;
}


</style>
