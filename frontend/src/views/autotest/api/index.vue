<template>
  <AppPage>
    <n-card size="small" class="case-info-card" title="用例信息">
      <div class="case-info-fields">
        <div class="case-field">
          <span class="case-field-label case-field-required">所属应用</span>
          <n-select
              v-model:value="caseForm.case_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="所属应用"
              size="small"
              class="case-field-input"
          />
        </div>

        <div class="case-field">
          <span class="case-field-label case-field-required">用例名称</span>
          <n-input
              v-model:value="caseForm.case_name"
              size="small"
              placeholder="请输入用例名称"
              class="case-field-input"
          />
        </div>

        <div class="case-field">
          <span class="case-field-label case-field-required">所属标签</span>
          <n-popover
              v-model:show="tagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
          >
            <template #trigger>
              <n-input
                  :value="getSelectedTagNames()"
                  clearable
                  readonly
                  placeholder="请选择所属标签"
                  size="small"
                  class="case-field-input"
                  @clear="caseForm.case_tags = []"
                  @click="tagPopoverShow = !tagPopoverShow"
              />
            </template>
            <template #default>
              <div style="display: flex; height: 300px; width: 400px;">
                <div style="width: 45%; overflow-y: auto;">
                  <n-list v-if="Object.keys(tagModeGroups).length > 0">
                    <n-list-item
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': selectedTagMode === mode, 'tag-mode-item': true }"
                        @click="selectedTagMode = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                    </n-list-item>
                  </n-list>
                  <div v-else style="padding: 20px; text-align: center; color: #999;">
                    {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                  </div>
                </div>
                <div style="width: 50%; overflow-y: auto;">
                  <n-list v-if="selectedTagMode && currentTagNames.length > 0">
                    <n-list-item
                        v-for="tag in currentTagNames"
                        :key="tag.tag_id"
                        :class="{ 'tag-name-selected': isTagSelected(tag.tag_id) }"
                        class="tag-list-item"
                        @click="handleTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                    </n-list-item>
                  </n-list>
                  <div v-else style="padding: 20px; text-align: center; color: #999;">
                    {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </template>
          </n-popover>
        </div>

        <div class="case-field">
          <span class="case-field-label case-field-required">用例属性</span>
          <n-select
              v-model:value="caseForm.case_attr"
              :options="caseAttrOptions"
              clearable
              placeholder="请选择用例属性"
              size="small"
              class="case-field-input"
          />
        </div>

        <div class="case-field">
          <span class="case-field-label case-field-required">用例类型</span>
          <n-select
              v-model:value="caseForm.case_type"
              :options="caseTypeOptions"
              clearable
              placeholder="请选择用例类型"
              size="small"
              class="case-field-input"
          />
        </div>

        <div class="case-field case-field-full">
          <span class="case-field-label">用例描述</span>
          <n-input
              v-model:value="caseForm.case_desc"
              size="small"
              type="textarea"
              placeholder="请输入用例描述"
          />
        </div>

        <!-- 按钮放在表单内部 -->
        <div class="case-field case-field-full case-field-buttons">
          <n-space justify="end">
            <n-button type="info" :loading="runLoading" @click="handleRun">执行</n-button>
            <n-button type="primary" :loading="debugLoading" @click="handleDebug">调试</n-button>
            <n-button type="success" :loading="saveLoading" @click="handleSaveAll">保存</n-button>
          </n-space>
        </div>
      </div>
    </n-card>
    <div class="page-container">
      <n-grid :cols="24" :x-gap="16" class="grid-container">
        <n-gi :span="7" class="left-column">
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
                        :size="18"
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
                              :size="16"
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
                          <TheIcon icon="material-symbols:content-copy" :size="16"/>
                        </template>
                      </n-button>
                      <n-popconfirm @positive-click="handleDeleteStep(step.id)" @click.stop>
                        <template #trigger>
                          <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                            <template #icon>
                              <TheIcon icon="material-symbols:delete" :size="16"/>
                            </template>
                          </n-button>
                        </template>
                        确认删除该步骤?
                      </n-popconfirm>
                    </span>
                  </span>
                    <div v-if="stepDefinitions[step.type]?.allowChildren">
                      <div
                          v-show="isStepExpanded(step.id)"
                          @dragover.prevent="handleDragOverInChildrenArea($event, step.id)"
                          @dragleave="handleDragLeaveInChildrenArea($event, step.id)"
                      >
                        <!-- 无子女时显示空的拖拽区域 -->
                        <div
                            v-if="!step.children || step.children.length === 0"
                            class="step-drop-zone"
                            :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
                            @drop="handleDrop($event, step.id, step.id, 0)"
                        >
                          <div class="step-drop-zone-hint">拖拽步骤到这里</div>
                        </div>
                        <template v-for="(child, childIndex) in (step.children || [])" :key="child.id">
                          <!-- 插入位置指示器：在子步骤之前 -->
                          <div
                              v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === child.id && dragState.insertPosition === 'before'"
                              class="step-insert-indicator"
                          ></div>
                          <div
                              class="step-item"
                              :class="{ 'is-selected': selectedKeys.includes(child.id) }"
                              :draggable="true"
                              @dragstart.stop="handleDragStart($event, child.id, step.id, childIndex)"
                              @dragover.prevent.stop="handleDragOverOnChild($event, child.id, step.id, childIndex)"
                              @dragleave.stop="handleDragLeaveOnChild($event, child.id)"
                              @drop.stop="handleDrop($event, child.id, step.id, childIndex)"
                              @click.stop="handleSelect([child.id])"
                          >
                            <div class="step-item-child">
                            <span class="step-name" :title="child.name">
                              <TheIcon
                                  :icon="getStepIcon(child.type)"
                                  :size="18"
                                  class="step-icon"
                                  :class="getStepIconClass(child.type)"
                              />
                              <!-- 子级步骤名称 -->
                              <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
                              <span class="step-actions">
                                <span class="step-number">#{{ getStepNumber(child.id) }}</span>
                                <n-button
                                    v-if="stepDefinitions[child.type]?.allowChildren"
                                    text
                                    size="tiny"
                                    @click.stop="toggleStepExpand(child.id, $event)"
                                    class="action-btn"
                                    :title="!isStepExpanded(step.id) ? '折叠当前步骤' : '展开当前步骤'"
                                >
                                  <template #icon>
                                    <TheIcon
                                        :icon="isStepExpanded(child.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"
                                        :size="16"
                                    />
                                  </template>
                                </n-button>
                                <n-button text size="tiny" @click.stop="handleCopyStep(child.id)" class="action-btn"
                                          title="复制当前步骤">
                                  <template #icon>
                                    <TheIcon icon="material-symbols:content-copy" :size="16"/>
                                  </template>
                                </n-button>
                                <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
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
                              <!-- 使用递归组件渲染子步骤 -->
                              <RecursiveStepChildren
                                  v-if="stepDefinitions[child.type]?.allowChildren"
                                  :step="child"
                                  :parent-id="step.id"
                              />
                            </div>
                          </div>
                          <!-- 插入位置指示器：在子步骤之后 -->
                          <div
                              v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === child.id && dragState.insertPosition === 'after'"
                              class="step-insert-indicator"
                          ></div>
                        </template>
                        <!-- 插入位置指示器：在最后一个子步骤之后（无子女时显示在空拖拽区域） -->
                        <div
                            v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === null && dragState.insertPosition === 'after' && step.children && step.children.length > 0"
                            class="step-insert-indicator"
                        ></div>
                        <div class="step-add-btn">
                          <n-dropdown
                              trigger="click"
                              :options="addOptions"
                              :render-label="renderDropdownLabel"
                              @select="(key) => handleAddStep(key, step.id)"
                          >
                            <n-button dashed size="small" class="add-step-btn" @click.stop>添加步骤</n-button>
                          </n-dropdown>
                        </div>
                      </div>
                    </div>
                    <!-- 引用步骤：展示公共脚本内的步骤（只读、递归子级，不参与保存） -->
                    <div v-if="step.type === 'quote'" class="quote-inner-steps">
                      <div class="quote-inner-list">
                        <div
                            v-for="(item, idx) in getQuoteStepsFlattened(quoteStepsMap[step.id] || [])"
                            :key="'quote-' + step.id + '-' + idx + '-' + (item.step.id || '')"
                            class="step-item quote-inner-item"
                            :class="{ 'is-selected': selectedKeys.includes(getQuoteInnerKey(step.id, idx)) }"
                            :style="{ marginLeft: (item.depth * 14) + 'px' }"
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
              <n-dropdown
                  trigger="click"
                  :options="addOptions"
                  :render-label="renderDropdownLabel"
                  @select="(key) => handleAddStep(key, null)"
              >
                <n-button dashed size="small" class="add-step-btn">添加步骤</n-button>
              </n-dropdown>
            </div>
          </n-card>
        </n-gi>
        <n-gi :span="17" class="right-column">
          <n-card :title="currentStepTitle" size="small" hoverable class="config-card">
            <!--
              数据传递说明：
              1. :config="currentStep.config" - 传递步骤的配置数据（从 mapBackendStep 中提取的配置对象）
              2. :step="currentStep" - 传递完整的步骤对象，包含：
                 - id: 步骤ID（step_code）
                 - type: 步骤类型（http/loop/code/if/wait）
                 - name: 步骤名称（step_name）
                 - config: 配置数据对象
                 - original: 完整的原始后端步骤数据，包含所有字段：
                   * step_code, step_name, step_desc, step_type
                   * request_method, request_url, request_header, request_body
                   * extract_variables, validators, defined_variables
                   * id, case_id, parent_step_id 等所有后端返回的字段
              3. 所有编辑器组件（HTTP控制器、循环控制器、条件控制器等）都可以通过 props.step.original 访问完整的原始数据
            -->
            <component
                v-if="currentStep"
                :key="currentStep.id + (currentStep.isQuoteInner ? '-readonly' : '')"
                :is="editorComponent"
                :config="currentStep.config"
                :step="currentStep"
                :project-options="currentStep?.type === 'http' ? projectOptions : []"
                :project-loading="currentStep?.type === 'http' ? projectLoading : false"
                :available-variable-list="availableVariableList"
                :assist-functions="assistFunctionsList"
                :on-reselect="currentStep?.isQuoteInner ? undefined : handleQuoteReselect"
                :readonly="!!currentStep?.isQuoteInner"
                @update:config="(val) => { if (!currentStep?.isQuoteInner) updateStepConfig(currentStep.id, val) }"
            />
            <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
          </n-card>
        </n-gi>
      </n-grid>
    </div>

    <!-- 引用公共脚本抽屉：宽度约 60%，内容同测试用例管理，请求时 case_type=公共脚本 -->
    <n-drawer
        v-model:show="quotePublicScriptDrawerVisible"
        :width="'61%'"
        placement="right"
        :trap-focus="false"
        block-scroll
    >
      <n-drawer-content title="选择公共脚本" closable>
        <CrudTable
            ref="quotePublicScriptTableRef"
            v-model:query-items="quotePublicScriptQueryItems"
            :is-pagination="true"
            :columns="quotePublicScriptColumns"
            :get-data="getPublicScriptList"
            :row-key="'case_id'"
        >
          <template #queryBar>
            <QueryBarItem label="用例名称：" :label-width="90">
              <n-input
                  v-model:value="quotePublicScriptQueryItems.case_name"
                  clearable
                  placeholder="请输入用例名称"
                  class="query-input"
                  @keypress.enter="quotePublicScriptTableRef?.handleSearch?.()"
              />
            </QueryBarItem>
            <QueryBarItem label="创建人员：" :label-width="90">
              <n-input
                  v-model:value="quotePublicScriptQueryItems.created_user"
                  clearable
                  placeholder="请输入创建人员"
                  class="query-input"
                  @keypress.enter="quotePublicScriptTableRef?.handleSearch?.()"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </n-drawer-content>
    </n-drawer>
  </AppPage>
</template>

<script setup>
import {computed, defineComponent, h, nextTick, onMounted, onUpdated, reactive, ref, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {
  NButton,
  NCard,
  NDrawer,
  NDropdown,
  NEmpty,
  NGi,
  NGrid,
  NInput,
  NList,
  NListItem,
  NPopconfirm,
  NPopover,
  NSelect,
  NSpace,
  NTag
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {formatDateTime, renderIcon} from '@/utils'
import AppPage from "@/components/page/AppPage.vue";
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";
import ApiUserVariablesEditor from "@/views/autotest/user_variables_controller/index.vue";
import ApiQuoteEditor from "@/views/autotest/quote_controller/index.vue";
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from "@/api";
import {useUserStore} from '@/store';

const stepDefinitions = {
  loop: {label: '循环结构', allowChildren: true, icon: 'streamline:arrow-reload-horizontal-2'},
  code: {label: '执行代码请求(Python)', allowChildren: false, icon: 'teenyicons:python-outline'},
  http: {label: 'HTTP请求', allowChildren: false, icon: 'streamline-freehand:worldwide-web-network-www'},
  if: {label: '分支条件', allowChildren: true, icon: 'tabler:arrow-loop-right-2'},
  wait: {label: '等待控制', allowChildren: false, icon: 'meteor-icons:alarm-clock'},
  database: {label: '数据库请求', allowChildren: false, icon: 'material-symbols:database-search-outline'},
  user_variables: {label: '用户变量', allowChildren: false, icon: 'gravity-ui:magic-wand'},
  quote: {label: '引用公共用例', allowChildren: false, icon: 'material-symbols:link'},
}

const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  http: ApiHttpEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor,
  user_variables: ApiUserVariablesEditor,
  quote: ApiQuoteEditor,
}

let seed = 1000
const genId = () => `step-${seed++}`

const steps = ref([])
const selectedKeys = ref([])
const route = useRoute()
const router = useRouter()
const caseId = computed(() => route.query.case_id || null)
const caseCode = computed(() => route.query.case_code || null)

// 从路由参数中解析用例信息并填充表单
const initCaseInfoFromRoute = () => {
  if (route.query.case_info) {
    try {
      const caseInfo = JSON.parse(route.query.case_info)
      // 填充表单数据
      // case_project 是对象，提取 project_id
      if (caseInfo.case_project) {
        caseForm.case_project = typeof caseInfo.case_project === 'object'
            ? caseInfo.case_project.project_id
            : caseInfo.case_project
      }
      caseForm.case_name = caseInfo.case_name || ''
      // case_tags 是对象数组，提取 tag_id 数组
      if (Array.isArray(caseInfo.case_tags) && caseInfo.case_tags.length > 0) {
        caseForm.case_tags = caseInfo.case_tags.map(tag => {
          return typeof tag === 'object' ? tag.tag_id : tag
        }).filter(id => id !== undefined && id !== null)
      } else {
        caseForm.case_tags = []
      }
      caseForm.case_desc = caseInfo.case_desc || ''
      caseForm.case_attr = caseInfo.case_attr || ''
      caseForm.case_type = caseInfo.case_type || ''
    } catch (error) {
      console.error('解析用例信息失败:', error)
    }
  }
}

const caseForm = reactive({
  case_project: '',
  case_name: '',
  case_tags: [],
  case_desc: '',
  case_attr: '',
  case_type: ''
})

// 项目列表（复用用例管理页面的数据源）
const projectOptions = ref([])
const projectLoading = ref(false)

// 标签相关（复用用例管理页面的数据源）
const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

// 用例属性选项（复用用例管理页面的数据源）
const caseAttrOptions = [
  {label: '正用例', value: '正用例'},
  {label: '反用例', value: '反用例'}
]

// 用例类型选项
const caseTypeOptions = [
  {label: '用户脚本', value: '用户脚本'},
  {label: '公共脚本', value: '公共脚本'}
]

// 引用公共脚本抽屉（新增步骤时 parentId 有值；重新选择时 replaceStepId 有值）
const quotePublicScriptDrawerVisible = ref(false)
const quotePublicScriptParentId = ref(null)
const quotePublicScriptReplaceStepId = ref(null)
const quotePublicScriptTableRef = ref(null)
// 引用步骤内展示的公共脚本步骤（仅展示，不参与保存）：quoteStepId -> 前端树节点数组
const quoteStepsMap = ref({})
// 从「用户脚本」切到「公共脚本」时暂存的引用步骤，切回「用户脚本」时可恢复
const stashedQuoteStepsWhenPublic = ref([])
const quotePublicScriptQueryItems = ref({
  case_name: '',
  case_type: '公共脚本',
  created_user: ''
})

// 请求前规范化入参：仅传用例名称、创建人员及固定 case_type
const getPublicScriptList = (params) => {
  const body = {...params, case_type: '公共脚本'}
  if (body.case_name === '') delete body.case_name
  if (body.created_user === '') delete body.created_user
  return api.getApiTestcaseList(body)
}
const onSelectPublicScript = (row) => {
  const replaceId = quotePublicScriptReplaceStepId.value
  const config = { quote_case_id: row.case_id, step_name: row.case_name || '引用公共脚本' }
  if (replaceId) {
    updateStepConfig(replaceId, config)
    const updated = findStep(replaceId)
    if (updated) loadQuoteStepsForStep(updated)
    quotePublicScriptReplaceStepId.value = null
  } else {
    const parentId = quotePublicScriptParentId.value
    const created = insertStep(parentId, 'quote', null, config)
    if (created) {
      selectedKeys.value = [created.id]
      updateStepDisplayNames()
      loadQuoteStepsForStep(created)
    }
    quotePublicScriptParentId.value = null
  }
  quotePublicScriptDrawerVisible.value = false
}

const handleQuoteReselect = () => {
  if (!currentStep.value?.id) return
  quotePublicScriptReplaceStepId.value = currentStep.value.id
  quotePublicScriptParentId.value = null
  quotePublicScriptDrawerVisible.value = true
}

watch(quotePublicScriptDrawerVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      quotePublicScriptTableRef.value?.handleSearch?.()
    })
  }
})

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
      // case_tags 现在是对象数组，使用NTag展示，每个标签换行
      if (Array.isArray(row.case_tags) && row.case_tags.length > 0) {
        return h('div', {class: 'tag-container'},
            row.case_tags
                .filter(tag => tag.tag_name)
                .map(tag =>
                    h(NTag, {
                      type: 'info',
                      style: 'margin: 2px 4px 2px 0;'
                    }, {default: () => tag.tag_name})
                )
        )
      }
      return h('span', '')
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
    width: 80,
    fixed: 'right',
    render: (row) => h(NButton, {
      size: 'small',
      type: 'primary',
      onClick: () => onSelectPublicScript(row)
    }, {default: () => '选择'})
  }
]

// 标签按模式分组
const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach(tag => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) {
      groups[mode] = []
    }
    groups[mode].push(tag)
  })
  return groups
})

// 当前选中模式下的标签列表
const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

// 加载项目列表（复用用例管理页面的数据源）
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

// 加载标签列表（复用用例管理页面的数据源）
const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getApiTagList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      // 如果选择了项目，则过滤该项目的标签；否则显示所有标签
      if (projectId) {
        tagOptions.value = res.data.filter(tag => tag.tag_project === projectId)
      } else {
        tagOptions.value = res.data
      }
      selectedTagMode.value = null
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

// 获取选中的标签名称（用于显示）
const getSelectedTagNames = () => {
  const tags = caseForm.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  const names = tags
      .map(tagId => tagOptions.value.find(t => t.tag_id === tagId)?.tag_name)
      .filter(name => name)
  return names.join(', ')
}

// 判断标签是否被选中
const isTagSelected = (tagId) => {
  const tags = caseForm.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

// 选择标签（支持多选）
const handleTagSelect = (tagId) => {
  if (!Array.isArray(caseForm.case_tags)) {
    caseForm.case_tags = []
  }
  const index = caseForm.case_tags.indexOf(tagId)
  if (index > -1) {
    // 如果已选中，则取消选择
    caseForm.case_tags.splice(index, 1)
  } else {
    // 如果未选中，则添加
    caseForm.case_tags.push(tagId)
  }
}

// 监听项目选择变化，重新加载标签
watch(() => caseForm.case_project, (newVal) => {
  loadTags(newVal)
})

// 确保 case_tags 始终是数组
watch(() => caseForm.case_tags, (newVal) => {
  if (!Array.isArray(newVal)) {
    caseForm.case_tags = []
  }
}, {immediate: true})

// 当用例类型改为「公共脚本」时，自动移除步骤树中所有「引用公共脚本」步骤；若从「用户脚本」切来则暂存，切回「用户脚本」时可恢复
watch(() => caseForm.case_type, (newType, oldType) => {
  if (newType === '公共脚本') {
    const fromUserScript = oldType === '用户脚本'
    if (fromUserScript) {
      const toStash = collectQuoteStepsWithPosition()
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        stashedQuoteStepsWhenPublic.value = toStash
        window.$message?.warning?.(`切换为公共脚本，已临时移除 ${removedCount} 个「引用公共脚本」步骤（若误操作，可切回用户脚本恢复）`)
      }
    } else {
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        window.$message?.warning?.(`切换为公共脚本，已自动移除 ${removedCount} 个「引用公共脚本」步骤（公共脚本不可引用其他脚本）`)
      }
    }
  } else if (newType === '用户脚本' && stashedQuoteStepsWhenPublic.value.length > 0) {
    const restoredCount = restoreStashedQuoteSteps()
    if (restoredCount > 0) {
      window.$message?.info?.(`已恢复 ${restoredCount} 个「引用公共脚本」步骤。`)
    }
  }
})

const runLoading = ref(false)
const debugLoading = ref(false)
const saveLoading = ref(false)
const debugResult = ref(null)
const dragState = ref({
  draggingId: null,
  dragOverId: null, // 当前拖拽进入的 loop/if 步骤 ID（焦点高亮）
  dragOverParent: null,
  dragOverIndex: null,
  insertPosition: null, // 'before' | 'after' | null，用于指示插入位置
  insertTargetId: null // 插入目标步骤 ID（用于显示指示器）
})

// 下拉只展示“引用公共脚本”（不展示“引用公共用例”）；quote 仅用于后端步骤类型与展示
// 当用例类型为“公共脚本”时，“引用公共脚本”置灰，防止循环引用
const addOptions = computed(() => {
  const isPublicScript = caseForm.case_type === '公共脚本'
  return [
    ...Object.entries(stepDefinitions)
        .filter(([key]) => key !== 'quote')
        .map(([value, item]) => ({
          label: item.label,
          key: value,
          icon: renderIcon(item.icon, {size: 16})
        })),
    {
      label: '引用公共脚本',
      key: 'quote_public_script',
      icon: renderIcon('material-symbols:library-books-outline', {size: 16}),
      disabled: isPublicScript
    }
  ]
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

/** 前序遍历步骤树，对每个步骤执行 fn（不包含引用步骤内加载的虚拟子步骤） */
const forEachStep = (list, fn) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children && step.children.length) forEachStep(step.children, fn)
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
const getQuoteInnerKey = (quoteStepId, flatIndex) => `${QUOTE_INNER_PREFIX}${quoteStepId}:${flatIndex}`
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

const backendTypeToLocal = (step_type) => {
  switch (step_type) {
    case 'HTTP请求':
      return 'http'
    case '执行代码请求(Python)':
      return 'code'
    case '条件分支':
      return 'if'
    case '等待控制':
      return 'wait'
    case '循环结构':
      return 'loop'
    case '用户变量':
      return 'user_variables'
    case '引用公共用例':
      return 'quote'
    default:
      return 'code'
  }
}

const parseJsonSafely = (val) => {
  if (!val) return null
  if (typeof val === 'object') return val
  try {
    return JSON.parse(val)
  } catch (e) {
    return null
  }
}

/**
 * 将后端返回的步骤数据转换为前端使用的格式
 *
 * 数据传递流程：
 * 1. 后端 API (getStepTree) 返回完整的步骤数据，包含所有字段：
 *    - step_code, step_name, step_desc, step_type
 *    - request_method, request_url, request_header, request_body, request_params
 *    - extract_variables, validators, defined_variables
 *    - id, case_id, parent_step_id, children 等
 *
 * 2. mapBackendStep 函数将后端数据转换为前端格式：
 *    - base.id: 使用 step_code 作为唯一标识
 *    - base.type: 转换为前端类型（http/loop/code/if/wait）
 *    - base.name: 使用 step_name
 *    - base.config: 提取配置数据（根据类型不同提取不同字段）
 *    - base.original: 保留完整的原始后端数据（所有字段）
 *
 * 3. 传递给编辑器组件时：
 *    - :config="currentStep.config" - 传递配置数据
 *    - :step="currentStep" - 传递完整步骤对象（包含 original）
 *
 * 4. 编辑器组件中可以通过 props.step.original 访问所有原始数据：
 *    - props.step.original.step_name - 步骤名称
 *    - props.step.original.step_desc - 步骤描述
 *    - props.step.original.step_code - 步骤代码
 *    - props.step.original.request_method - 请求方法
 *    - 等等所有后端返回的字段
 */
const mapBackendStep = (step) => {
  if (!step || !step.step_type) return null
  const localType = backendTypeToLocal(step.step_type)
  const base = {
    id: step.step_code || `step-${step.id || genId()}`,
    type: localType,
    name: step.step_name || step.step_type || '步骤',
    config: {},
    // 保留完整的原始后端步骤数据，供编辑器组件使用
    // 这样编辑器组件可以通过 props.step.original 访问所有原始字段
    // 注意：后端返回的 step_id 对应数据库主键，需要映射到 original.id（用于更新时传递 step_id）
    original: {
      ...step,
      // 确保 id 字段被正确映射（后端返回的 step_id 对应数据库主键，用于更新时的 step_id）
      // 后端使用 replace_fields={"id": "step_id"}，所以返回的是 step_id 而不是 id
      id: step.step_id || step.id || null, // 数据库主键，用于更新（优先使用 step_id）
      step_code: step.step_code || null, // 步骤代码，用于更新
      // 确保 children 和 quote_steps 也被保留（但需要递归处理）
      children: undefined, // 先设为 undefined，后面单独处理
      quote_steps: step.quote_steps || []
    }
  }

  if (localType === 'loop') {
    // 根据后端数据构建循环配置
    base.config = {
      loop_mode: step.loop_mode || '次数循环',
      loop_on_error: step.loop_on_error || '继续下一次循环',
      loop_maximums: step.loop_maximums ? Number(step.loop_maximums) : null,
      loop_interval: step.loop_interval ? Number(step.loop_interval) : 0,
      loop_iterable: step.loop_iterable || '',
      loop_iter_idx: step.loop_iter_idx || '',
      loop_iter_key: step.loop_iter_key || '',
      loop_iter_val: step.loop_iter_val || '',
      loop_timeout: step.loop_timeout ? Number(step.loop_timeout) : 0
    }
    // 解析条件循环的conditions
    if (step.conditions) {
      try {
        const condition = typeof step.conditions === 'string'
            ? JSON.parse(step.conditions)
            : step.conditions
        base.config.condition_value = condition.value || ''
        base.config.condition_operation = condition.operation || 'not_empty'
        base.config.condition_except_value = condition.except_value || ''
      } catch (e) {
        console.error('解析循环条件失败:', e)
        base.config.condition_value = ''
        base.config.condition_operation = 'not_empty'
        base.config.condition_except_value = ''
      }
    } else {
      base.config.condition_value = ''
      base.config.condition_operation = 'not_empty'
      base.config.condition_except_value = ''
    }
    base.children = []
  } else if (localType === 'code') {
    base.config = {
      step_name: step.step_name || '',
      script: step.code || ''
    }
  } else if (localType === 'http') {
    base.config = {
      method: step.request_method || 'POST',
      url: step.request_url || '',
      request_args_type: step.request_args_type || 'none',
      request_project_id: step.request_project_id ?? null,
      params: Array.isArray(step.request_params) ? step.request_params : [],
      data: step.request_body || {},
      headers: Array.isArray(step.request_header) ? step.request_header : [],
      form_data: Array.isArray(step.request_form_data) ? step.request_form_data : [],
      form_urlencoded: Array.isArray(step.request_form_urlencoded) ? step.request_form_urlencoded : [],
      request_text: step.request_text || null,
      extract: step.extract_variables || {},
      validators: step.validators || {}
    }
  } else if (localType === 'if') {
    const parsed = parseJsonSafely(step.conditions) || {}
    // 处理数组格式（后端可能返回数组）
    const condition = Array.isArray(parsed) && parsed.length > 0 ? parsed[0] : parsed
    base.config = {
      value: condition.value || '',
      operation: condition.operation || '非空',
      except_value: condition.except_value || '',
      desc: condition.desc || ''
    }
    base.children = []
  } else if (localType === 'wait') {
    base.config = {
      seconds: step.wait || 0
    }
  } else if (localType === 'user_variables') {
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      session_variables: Array.isArray(step.session_variables) ? step.session_variables : []
    }
  } else if (localType === 'quote') {
    base.config = {
      quote_case_id: step.quote_case_id ?? null,
      step_name: step.step_name || (step.quote_case?.case_name || '引用公共用例')
    }
  }

  if (step.children && step.children.length && stepDefinitions[localType]?.allowChildren) {
    base.children = step.children.map(mapBackendStep).filter(Boolean)
    // 保留原始 children 数据到 original 中
    base.original.children = step.children
  }

  if (!stepDefinitions[localType]?.allowChildren) {
    delete base.children
    base.original.children = step.children || []
  } else if (!base.children) {
    base.children = []
    base.original.children = []
  }

  return base
}

const hydrateCaseInfo = (data) => {
  const firstStepCase = data?.[0]?.case
  if (firstStepCase) {
    caseForm.case_project = firstStepCase.case_project || ''
    caseForm.case_name = firstStepCase.case_name || ''
    caseForm.case_tags = firstStepCase.case_tags ?? (Array.isArray(firstStepCase.case_tags) ? firstStepCase.case_tags : [])
    caseForm.case_desc = firstStepCase.case_desc || ''
    caseForm.case_attr = firstStepCase.case_attr || ''
    caseForm.case_type = firstStepCase.case_type || ''
  } else if (Array.isArray(data) && data.length > 0) {
    // 有步骤但首条无 case 信息时才清空（例如接口返回异常）
    caseForm.case_project = ''
    caseForm.case_name = ''
    caseForm.case_tags = []
    caseForm.case_desc = ''
    caseForm.case_attr = ''
    caseForm.case_type = ''
  }
  // 当 data 为空（如新增用例保存后尚未有步骤）时保留当前 caseForm，不清空用户刚填写的内容
}

// 将前端类型转换为后端类型
const localTypeToBackend = (localType) => {
  const typeMap = {
    'http': 'HTTP请求',
    'code': '执行代码请求(Python)',
    'if': '条件分支',
    'wait': '等待控制',
    'loop': '循环结构',
    'user_variables': '用户变量',
    'quote': '引用公共用例'
  }
  return typeMap[localType] || '执行代码请求(Python)'
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

  // 调试日志：帮助排查问题
  if (process.env.NODE_ENV === 'development') {
    console.log(`[convertStepToBackend] Step ${step.name}:`, {
      hasStepId,
      hasStepCode,
      isUpdate,
      originalId: original.id,
      originalStepCode: original.step_code,
      stepNo
    })
  }

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
    case_type: caseForm.case_type || original.case_type || '用户脚本'
  }

  // 只有更新时才传递 step_id 和 step_code（两个都必须存在）
  // 新增时不传递这两个字段（设置为undefined，让后端排除）
  if (isUpdate) {
    backendStep.step_id = original.id
    backendStep.step_code = original.step_code
  }
  // 新增时不设置 step_id 和 step_code，让它们为 undefined，后端会自动排除

  // 根据类型设置特定字段
  if (step.type === 'http') {
    backendStep.request_method = config.method || original.request_method || 'POST'
    backendStep.request_url = config.url || original.request_url || ''
    backendStep.request_args_type = config.request_args_type ?? original.request_args_type ?? 'none'
    backendStep.request_text = config.request_text ?? original.request_text ?? null
    backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
    backendStep.request_header = filterKeyValueList(Array.isArray(config.headers) ? config.headers : (Array.isArray(original.request_header) ? original.request_header : []))
    backendStep.request_params = filterKeyValueList(Array.isArray(config.params) ? config.params : (Array.isArray(original.request_params) ? original.request_params : []))
    backendStep.request_form_data = filterKeyValueList(Array.isArray(config.form_data) ? config.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : []))
    backendStep.request_form_urlencoded = filterKeyValueList(Array.isArray(config.form_urlencoded) ? config.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : []))
    backendStep.request_body = config.data || original.request_body || {}

    // extract_variables 和 assert_validators 应该是列表格式（List[Dict[str, Any]]）
    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : (config.extract_variables ? [config.extract_variables] : null)
    } else if (original.extract_variables) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : (original.extract_variables ? [original.extract_variables] : null)
    } else {
      backendStep.extract_variables = null
    }

    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : (config.assert_validators ? [config.assert_validators] : null)
    } else if (original.assert_validators) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : (original.assert_validators ? [original.assert_validators] : null)
    } else {
      backendStep.assert_validators = null
    }

    // defined_variables 必须是列表格式，每个元素包含 key、value、desc；Key 为空的项不保存
    backendStep.defined_variables = filterKeyValueList(Array.isArray(config.defined_variables) ? config.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : []))
  } else if (step.type === 'code') {
    backendStep.code = config.code !== undefined ? config.code : (original.code || '')
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
    } else if (backendStep.loop_mode === '对象循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
      backendStep.loop_iter_idx = config.loop_iter_idx !== undefined ? config.loop_iter_idx : (original.loop_iter_idx || '')
      backendStep.loop_iter_val = config.loop_iter_val !== undefined ? config.loop_iter_val : (original.loop_iter_val || '')
    } else if (backendStep.loop_mode === '字典循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
      backendStep.loop_iter_idx = config.loop_iter_idx !== undefined ? config.loop_iter_idx : (original.loop_iter_idx || '')
      backendStep.loop_iter_key = config.loop_iter_key !== undefined ? config.loop_iter_key : (original.loop_iter_key || '')
      backendStep.loop_iter_val = config.loop_iter_val !== undefined ? config.loop_iter_val : (original.loop_iter_val || '')
    } else if (backendStep.loop_mode === '条件循环') {
      // 条件循环需要将条件对象转换为列表格式（后端期望 List[Dict[str, Any]]）
      if (config.condition_value !== undefined || config.condition_operation !== undefined || config.condition_except_value !== undefined) {
        const conditionObj = {
          value: config.condition_value || '',
          operation: config.condition_operation || 'not_empty',
          except_value: config.condition_except_value || ''
        }
        backendStep.conditions = [conditionObj]
      } else if (original.conditions) {
        // 如果原始数据是字符串，先解析；如果是对象，转换为列表；如果已经是列表，直接使用
        if (typeof original.conditions === 'string') {
          try {
            const parsed = JSON.parse(original.conditions)
            backendStep.conditions = Array.isArray(parsed) ? parsed : [parsed]
          } catch (e) {
            backendStep.conditions = null
          }
        } else if (Array.isArray(original.conditions)) {
          backendStep.conditions = original.conditions
        } else if (typeof original.conditions === 'object') {
          backendStep.conditions = [original.conditions]
        } else {
          backendStep.conditions = null
        }
      } else {
        backendStep.conditions = null
      }
      backendStep.loop_timeout = config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original.loop_timeout ? Number(original.loop_timeout) : 0)
    }
  } else if (step.type === 'if') {
    // 根据后端 ConditionStepExecutor 的要求，conditions 应该是列表格式（List[Dict[str, Any]]）
    const conditionObj = {
      value: config.value || '',
      operation: config.operation || '非空',
      except_value: config.except_value || '',
      desc: config.desc || ''
    }
    // 后端期望 conditions 是列表格式
    backendStep.conditions = [conditionObj]
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
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共用例')
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
  // 如果 original.case 存在，使用它；否则从 caseForm 构建
  if (original.case) {
    backendStep.case = original.case
  } else {
    // 从 caseForm 构建 case 信息
    backendStep.case = {
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      case_name: caseForm.case_name || '',
      case_project: caseForm.case_project || null,
      case_tags: Array.isArray(caseForm.case_tags) ? caseForm.case_tags : [],
      case_type: caseForm.case_type || null,
      case_attr: caseForm.case_attr || null,
      case_desc: caseForm.case_desc || null
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

// 校验用例信息必填项（所属应用、用例名称、所属标签、用例属性、用例类型）
const validateCaseForm = () => {
  if (!caseForm.case_project) {
    return {valid: false, message: '请选择所属应用'}
  }
  if (!caseForm.case_name || !String(caseForm.case_name).trim()) {
    return {valid: false, message: '请输入用例名称'}
  }
  if (!Array.isArray(caseForm.case_tags) || caseForm.case_tags.length === 0) {
    return {valid: false, message: '请选择所属标签'}
  }
  if (!caseForm.case_attr) {
    return {valid: false, message: '请选择用例属性'}
  }
  if (!caseForm.case_type) {
    return {valid: false, message: '请选择用例类型'}
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

const handleSaveAll = async () => {
  if (saveLoading.value) return
  saveLoading.value = true
  try {
    // 用例信息必填项校验
    const caseValidation = validateCaseForm()
    if (!caseValidation.valid) {
      window.$message?.error?.(caseValidation.message)
      return
    }

    // 请求体为 json 时校验 JSON 语法，有错误则提示并阻止保存
    const jsonValidation = validateJsonBodyInSteps(steps.value)
    if (!jsonValidation.valid) {
      window.$message?.error?.(
          `步骤「${jsonValidation.stepName}」请求体 JSON 格式错误，请修正后再保存。}`
      )
      return
    }


    // 键值对去空校验：存在 Key 为空的项时不允许保存
    const emptyKeyValidation = validateEmptyKeyInSteps(steps.value)
    if (!emptyKeyValidation.valid) {
      window.$message?.error?.(
          `步骤 [${emptyKeyValidation.stepName}] : [${emptyKeyValidation.listName}] 存在键为空的项，请填写或删除后再保存。`
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
    const caseInfo = {
      // 根据是否有caseId或caseCode判断是新增还是更新
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      case_name: caseForm.case_name || '',
      case_project: caseForm.case_project || null,
      case_tags: Array.isArray(caseForm.case_tags) ? caseForm.case_tags : [],
      case_type: caseForm.case_type || null,
      case_attr: caseForm.case_attr || null,
      case_desc: caseForm.case_desc || null,
      case_steps: totalSteps, // 用例步骤数量(含所有子级步骤)
      session_variables: null, // 如果需要可以从其他地方获取
      updated_user: currentUser
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

      // 重新加载数据（URL 已更新，loadSteps 会带上 case_id；若无步骤，hydrateCaseInfo 会保留当前 caseForm）
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

const handleRun = async () => {
  if (!caseId.value) {
    window.$message?.warning?.('请先选择或创建测试用例')
    return
  }
  runLoading.value = true
  try {
    const res = await api.executeStepTree({
      case_id: caseId.value ? Number(caseId.value) : null,
      // initial_variables 必须是列表格式，每个元素包含 key、value、desc
      initial_variables: []
    })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      const stats = res.data || {}
      const msg = `执行完成，总步骤: ${stats.total_steps}, 成功: ${stats.success_steps}, 失败: ${stats.failed_steps}, 成功率: ${stats.pass_ratio}%`
      window.$message?.success?.(msg)
    } else {
      window.$message?.error?.(res?.message || '执行失败')
    }
  } catch (error) {
    console.error('Failed to run step tree', error)
    window.$message?.error?.(error?.message || '执行失败')
  } finally {
    runLoading.value = false
  }
}

// 格式化调试结果树
const formatDebugResult = (results, indent = 0) => {
  if (!results || !Array.isArray(results)) return ''
  let output = ''
  const prefix = '  '.repeat(indent)
  for (const result of results) {
    const status = result.success ? '✓' : '✗'
    output += `${prefix}${status} [${result.step_no || '-'}] ${result.step_name || result.step_type || '未知步骤'}\n`
    if (result.message) {
      output += `${prefix}  消息: ${result.message}\n`
    }
    if (result.error) {
      output += `${prefix}  错误: ${result.error}\n`
    }
    if (result.elapsed !== undefined && result.elapsed !== null) {
      output += `${prefix}  耗时: ${result.elapsed}ms\n`
    }
    if (result.extract_variables && result.extract_variables.length > 0) {
      output += `${prefix}  提取变量: ${JSON.stringify(result.extract_variables, null, 2)}\n`
    }
    if (result.assert_validators && result.assert_validators.length > 0) {
      output += `${prefix}  断言结果: ${JSON.stringify(result.assert_validators, null, 2)}\n`
    }
    if (result.children && result.children.length > 0) {
      output += formatDebugResult(result.children, indent + 1)
    }
  }
  return output
}

// 格式化调试日志
const formatDebugLogs = (logs) => {
  if (!logs || typeof logs !== 'object') return ''
  let output = ''
  for (const [stepCode, logList] of Object.entries(logs)) {
    if (Array.isArray(logList) && logList.length > 0) {
      output += `步骤 ${stepCode}:\n`
      for (const log of logList) {
        output += `  ${log}\n`
      }
      output += '\n'
    }
  }
  return output || '暂无日志'
}

const handleDebug = async () => {
  if (!steps.value || steps.value.length === 0) {
    window.$message?.warning?.('请先添加测试步骤')
    return
  }
  if (!caseId.value) {
    window.$message?.warning?.('请先保存用例或选择已有用例')
    return
  }
  debugLoading.value = true
  debugResult.value = null
  try {
    // 调试模式：传递 case_id 和 steps
    // 按照树的前序遍历顺序分配 step_no，确保唯一且按顺序递增
    const stepNoMap = assignStepNumbers(steps.value)

    // 转换步骤数据，使用分配好的 step_no，并保持树结构
    const backendSteps = steps.value.map((step) => {
      return convertStepToBackend(step, null, stepNoMap)
    })

    const res = await api.executeStepTree({
      // 调试模式：传递 case_id 和 steps
      case_id: caseId.value ? Number(caseId.value) : null,
      steps: backendSteps,
      // initial_variables 必须是列表格式，每个元素包含 key、value、desc
      initial_variables: []
    })
    if (res?.code === '000000') {
      const stats = res.data || {}
      const msg = `调试完成，总步骤: ${stats.total_steps}, 成功: ${stats.success_steps}, 失败: ${stats.failed_steps}, 成功率: ${stats.pass_ratio}%`
      window.$message?.success?.(msg)

      // 保存调试结果用于展示
      debugResult.value = res.data
    } else {
      window.$message?.error?.(res?.message || '调试失败')
      debugResult.value = null
    }
  } catch (error) {
    console.error('Failed to debug step tree', error)
    window.$message?.error?.(error?.message || '调试失败')
    debugResult.value = null
  } finally {
    debugLoading.value = false
  }
}

const loadSteps = async () => {
  stepExpandStates.value = new Map()
  stashedQuoteStepsWhenPublic.value = []
  if (!caseId.value && !caseCode.value) {
    steps.value = []
    selectedKeys.value = []
    hydrateCaseInfo([])
    return
  }
  try {
    const params = {}
    if (caseId.value) params.case_id = caseId.value
    if (caseCode.value) params.case_code = caseCode.value
    const res = await api.getAutoTestStepTree(params)
    const data = Array.isArray(res?.data) ? res.data : []
    hydrateCaseInfo(data)
    steps.value = data.map(mapBackendStep).filter(Boolean)
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
    loadQuoteStepsForAllQuoteSteps()
  } catch (error) {
    console.error('Failed to load step tree', error)
    steps.value = []
    selectedKeys.value = []
    hydrateCaseInfo([])
    quoteStepsMap.value = {}
  }
}

const handleSelect = (keys) => {
  selectedKeys.value = keys
}

const currentStep = computed(() => {
  const key = selectedKeys.value?.[0]
  if (!key) return null
  const quoteInner = getQuoteInnerStep(key)
  if (quoteInner) return quoteInner
  return findStep(key)
})

watch(
    () => currentStep.value,
    (step) => {
      if (step) {
        console.log('========== 步骤编辑页面 - 传递给控制器组件 ==========')
        console.log('完整的 Step 对象:', step)
        console.log('Step 对象的所有 key:', Object.keys(step))
        console.log('Step.config (配置数据):', step.config)
        console.log('Step.original (原始后端数据):', step.original)
        if (step.original) {
          console.log('Step.original 的所有 key:', Object.keys(step.original))
          console.log('Step.original.step_code:', step.original.step_code)
          console.log('Step.original.step_name:', step.original.step_name)
          console.log('Step.original.step_desc:', step.original.step_desc)
          console.log('Step.original.step_type:', step.original.step_type)
        }
        console.log('==================================================')
      }
    },
    {immediate: true}
)

const editorComponent = computed(() => {
  const step = currentStep.value
  if (!step) return null
  return editorMap[step.type] || null
})

const currentStepTitle = computed(() => {
  if (!currentStep.value) return '步骤配置'
  const label = stepDefinitions[currentStep.value.type]?.label || '步骤配置'
  return currentStep.value.isQuoteInner ? `${label}（只读）` : label
})

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
                  ? {quote_case_id: null, step_name: '引用公共用例'}
                  : {}
  const defaultName = type === 'loop'
      ? '循环结构(次数循环)'
      : type === 'wait'
          ? '控制等待(2秒)'
          : type === 'user_variables'
              ? '用户定义变量'
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

const handleAddStep = (type, parentId) => {
  if (type === 'quote_public_script') {
    quotePublicScriptParentId.value = parentId
    quotePublicScriptDrawerVisible.value = true
    return
  }
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    updateStepDisplayNames()
  }
}

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

const handleCopyStep = (id) => {
  const step = findStep(id)
  if (!step) return
  const copiedStep = JSON.parse(JSON.stringify(step))
  copiedStep.id = genId()
  copiedStep.name = `${copiedStep.name}(copy)`

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

const updateStepConfig = (id, config) => {
  const step = findStep(id)
  if (step) {
    step.config = {...step.config, ...config}
    // 根据配置更新步骤名称
    if (step.type === 'loop') {
      if (config.loop_mode === '次数循环') {
        step.name = `循环结构(次数循环)`
      } else if (config.loop_mode === '对象循环') {
        step.name = `循环结构(对象循环)`
      } else if (config.loop_mode === '字典循环') {
        step.name = `循环结构(字典循环)`
      } else if (config.loop_mode === '条件循环') {
        step.name = `循环结构-(条件循环)`
      } else {
        step.name = `循环结构`
      }
    } else if (step.type === 'http') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined && config.step_name.length > 0) {
        step.name = String(config.step_name).trim() || 'HTTP请求(发送请求并验证响应数据)'
      } else {
        // 否则自动生成步骤名称
        step.name = `HTTP请求(发送请求并验证响应数据)`
      }
    } else if (step.type === 'if') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined && config.step_name.length > 0) {
        step.name = config.step_name
      } else {
        step.name = `条件分支(根据判断结果, 执行不同的路径)`
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
        step.name = String(config.step_name).trim() || '执行代码请求(Python)'
      }
    } else if (step.type === 'quote' || step.type === 'quote_public_script') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '引用公共脚本'
      }
    }
    // 更新显示名称
    updateStepDisplayNames()
  }
}

const getStepIcon = (type) => {
  return stepDefinitions[type]?.icon || 'material-symbols:code'
}

const getStepIconClass = (type) => {
  const classMap = {
    loop: 'icon-loop',
    code: 'icon-code',
    http: 'icon-http',
    if: 'icon-if',
    wait: 'icon-wait',
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

// 监听steps变化，更新显示名称和展开状态
watch(() => steps.value, () => {
  updateStepDisplayNames()
  initializeStepExpandStates()
}, {deep: true})

watch([() => caseId.value, () => caseCode.value], () => {
  loadSteps()
})

onMounted(async () => {
  // 加载项目列表和标签列表（复用用例管理页面的数据源）
  loadProjects()
  loadTags()
  // 先从路由参数中初始化用例信息
  initCaseInfoFromRoute()
  // 然后加载步骤树数据
  loadSteps()
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

onUpdated(() => {
  // 组件更新后重新计算显示名称
  updateStepDisplayNames()
})

const renderDropdownLabel = (option) => {
  const iconClass = getStepIconClass(option.key)
  return h('div', {style: {display: 'flex', alignItems: 'center', gap: '8px'}}, [
    h('span', option.label)
  ])
}

// 递归子步骤组件
const RecursiveStepChildren = defineComponent({
  name: 'RecursiveStepChildren',
  props: {
    step: {
      type: Object,
      required: true
    },
    parentId: {
      type: String,
      default: null
    }
  },
  setup(props) {
    // 捕获所有需要的变量和函数，确保能够通过闭包访问
    const capturedStepDefinitions = stepDefinitions
    const capturedIsAllExpanded = isAllExpanded
    const capturedIsStepExpanded = isStepExpanded
    const capturedToggleStepExpand = toggleStepExpand
    const capturedSelectedKeys = selectedKeys
    const capturedGetStepIcon = getStepIcon
    const capturedGetStepIconClass = getStepIconClass
    const capturedGetStepDisplayName = getStepDisplayName
    const capturedGetStepNumber = getStepNumber
    const capturedHandleSelect = handleSelect
    const capturedHandleDragStart = handleDragStart
    const capturedHandleDragOver = handleDragOver
    const capturedHandleDragLeave = handleDragLeave
    const capturedHandleDragOverInChildrenArea = handleDragOverInChildrenArea
    const capturedHandleDragLeaveInChildrenArea = handleDragLeaveInChildrenArea
    const capturedHandleDragOverOnChild = handleDragOverOnChild
    const capturedHandleDragLeaveOnChild = handleDragLeaveOnChild
    const capturedHandleDrop = handleDrop
    const capturedHandleCopyStep = handleCopyStep
    const capturedHandleDeleteStep = handleDeleteStep
    const capturedAddOptions = addOptions
    const capturedRenderDropdownLabel = renderDropdownLabel
    const capturedHandleAddStep = handleAddStep
    const capturedDragState = dragState

    return () => {
      const {step, parentId} = props
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
                  size: 18,
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
                      size: 16
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
                      size: 16,
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
                step: child,
                parentId: step.id
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
          h(NDropdown, {
            trigger: 'click',
            options: capturedAddOptions.value,
            renderLabel: capturedRenderDropdownLabel,
            onSelect: (key) => {
              capturedHandleAddStep(key, step.id)
            }
          }, {
            default: () => h(NButton, {
              dashed: true,
              size: 'small',
              class: 'add-step-btn',
              onClick: (e) => e.stopPropagation()
            }, {
              default: () => '添加步骤'
            })
          })
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

.case-info-card {
  margin-bottom: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.case-info-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px 24px;
}

.case-field {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
}

.case-field-full {
  grid-column: 1 / -1;
}

.case-field-full.case-field-buttons {
  justify-content: flex-end;
}

.case-field-label {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  min-width: 70px;
  flex-shrink: 0;
}

.case-field-required::before {
  content: '*';
  color: #F4511E;
  margin-right: 4px;
}

.case-field-input {
  flex: 1;
  transition: border-color 0.3s ease;
}

.case-field-input:hover {
  border-color: #F4511E;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .case-info-fields {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .case-field {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .case-field-label {
    font-size: 13px;
    min-width: auto;
  }

  .case-field-input {
    width: 100%;
  }
}

@media (min-width: 1200px) {
  .case-info-fields {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/* Grid 容器：使用 flex 布局，占满可用高度 */
.grid-container {
  height: 100%;
  flex: 1;
  min-height: 0; /* 重要：允许 flex 子元素缩小 */
}

/* 确保 n-grid 内部元素正确布局 */
.grid-container :deep(.n-grid) {
  height: 100%;
}

.grid-container :deep(.n-grid-item) {
  height: 100%;
}

/* 左侧列：使用 flex 布局 */
.left-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 右侧列：使用 flex 布局 */
.right-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
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

/* 配置卡片内容区域：允许滚动 */
.config-card :deep(.n-card__content) {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

/* 步骤树容器：固定高度，超出时滚动 */
.step-tree-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0; /* 重要：允许 flex 子元素缩小 */
  padding: 8px 0;
}

/* 自定义滚动条样式（可选，提升用户体验） */
.step-tree-container::-webkit-scrollbar {
  width: 4px;
}

.step-tree-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 5px;
}

.step-tree-container::-webkit-scrollbar-thumb {
  background: #a8a8a8;
  border-radius: 5px;
}

.step-tree-container::-webkit-scrollbar-thumb:hover {
  background: #F4511E;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
  flex-shrink: 0; /* 防止 header 被压缩 */
}

.step-count {
  font-weight: 600;
  font-size: 14px;
}

/* 下拉菜单中的图标样式 */
:deep(.n-dropdown-menu .step-icon) {
  flex-shrink: 0;
}

.add-step-btn {
  width: 100%;
  margin-bottom: 10px;
  border-radius: 10px;
}

/* 样式穿透：确保递归组件中所有嵌套层级的样式都能正确应用 */
:deep(.step-item) {
  border: 1px solid transparent;
  border-radius: 10px;
  transition: all .2s;
  cursor: pointer;
  padding-top: 5px;
  padding-bottom: 5px;
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
  margin: 4px 12px;
  border-radius: 1px;
  box-shadow: 0 0 4px rgba(244, 81, 30, 0.6);
}

:deep(.step-item[draggable="true"]) {
  cursor: move;
}

:deep(.step-drop-zone) {
  min-height: 40px;
  border: 2px dashed #ccc;
  border-radius: 8px;
  margin: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background-color: #fafafa;
}

:deep(.step-drop-zone.is-drag-over) {
  border-color: #F4511E;
  background-color: rgba(244, 81, 30, 0.1);
  box-shadow: 0 0 8px rgba(244, 81, 30, 0.3);
}

:deep(.step-drop-zone-hint) {
  color: #999;
  font-size: 12px;
  padding: 8px;
}

:deep(.step-drop-zone.is-drag-over .step-drop-zone-hint) {
  color: #F4511E;
  font-weight: 500;
}

:deep(.step-item-child) {
  padding-left: 12px;
}

:deep(.step-name) {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  font-size: 14px;
  font-weight: 300;
  background-color: rgba(222, 222, 222, 0.20);
  padding: 8px 8px;
  border-radius: 10px;
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
  padding-right: 8px;
  display: inline-block;
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
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-right: 4px;
}

:deep(.step-icon) {
  font-size: 18px;
  flex-shrink: 0;
  align-items: center;
}

:deep(.step-icon.icon-loop) {
  color: #F4511E;
}

:deep(.step-icon.icon-code) {
  color: #3363e0;
}

:deep(.step-icon.icon-http) {
  color: #3363e0;
}

:deep(.step-icon.icon-if) {
  color: #F4511E;
}

:deep(.step-icon.icon-wait) {
  color: #48d024;
}

:deep(.step-icon.icon-user_variables) {
  color: #FF69B4;
}

:deep(.step-icon.icon-quote) {
  color: #18a058;
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
  padding-left: 12px;
}

/* 引用步骤：脚本内步骤展示（只读，含递归子级） */
:deep(.quote-inner-steps) {
  margin-top: 6px;
  margin-left: 12px;
  border-left: 2px solid #18a058;
  padding-left: 8px;
}
:deep(.quote-inner-list) {
  margin-top: 6px;
}
:deep(.quote-inner-item) {
  padding: 4px 8px;
  margin-bottom: 2px;
  background: rgba(24, 160, 88, 0.06);
  border-radius: 6px;
  cursor: pointer;
  border: none;
}
:deep(.quote-inner-item:hover) {
  background: rgba(24, 160, 88, 0.12);
}
:deep(.quote-inner-item .step-name) {
  display: flex;
  align-items: center;
  gap: 6px;
}
:deep(.quote-inner-item .step-number) {
  margin-left: auto;
}
:deep(.quote-inner-empty) {
  font-size: 12px;
  color: #999;
  padding: 6px 0;
}

:deep(.add-step-btn) {
  width: 100%;
  margin-bottom: 10px;
}

/* 标签选择器样式 */
.tag-mode-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

.tag-name-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

.tag-mode-item {
  cursor: pointer;
  padding: 8px 12px;
}

.tag-mode-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.tag-list-item {
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-checkbox {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  color: #18a058;
  font-weight: bold;
}

.tag-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.n-list-item) {
  transition: background-color 0.2s;
}

:deep(.n-list-item:hover) {
  background-color: #f5f5f5;
}

</style>
