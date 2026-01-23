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
            <n-button type="success" :loading="runLoading" @click="handleRun">运行</n-button>
            <n-button type="primary" :loading="debugLoading" @click="handleDebug">调试</n-button>
            <n-button type="info" @click="handleSaveAll">保存</n-button>
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
                :key="currentStep.id"
                :is="editorComponent"
                :config="currentStep.config"
                :step="currentStep"
                @update:config="(val) => updateStepConfig(currentStep.id, val)"
            />
            <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
          </n-card>
        </n-gi>
      </n-grid>
    </div>
  </AppPage>
</template>

<script setup>
import {computed, defineComponent, h, nextTick, onMounted, onUpdated, reactive, ref, watch} from 'vue'
import {useRoute} from 'vue-router'
import {NButton, NCard, NDropdown, NEmpty, NGi, NGrid, NPopconfirm, NInput, NSpace, NSelect, NPopover, NList, NListItem} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {renderIcon} from '@/utils'
import AppPage from "@/components/page/AppPage.vue";
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";
import api from "@/api";

const stepDefinitions = {
  loop: {label: '循环结构', allowChildren: true, icon: 'streamline:arrow-reload-horizontal-2'},
  code: {label: '执行代码请求(Python)', allowChildren: false, icon: 'teenyicons:python-outline'},
  http: {label: 'HTTP请求', allowChildren: false, icon: 'streamline-freehand:worldwide-web-network-www'},
  if: {label: '分支条件', allowChildren: true, icon: 'tabler:arrow-loop-right-2'},
  wait: {label: '等待控制', allowChildren: false, icon: 'meteor-icons:alarm-clock'},
  database: {label: '数据库请求', allowChildren: false, icon: 'material-symbols:database-search-outline'}
}

const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  http: ApiHttpEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor
}

let seed = 1000
const genId = () => `step-${seed++}`

const steps = ref([])
const selectedKeys = ref([])
const route = useRoute()
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
  { label: '正用例', value: '正用例' },
  { label: '反用例', value: '反用例' }
]

// 用例类型选项
const caseTypeOptions = [
  { label: '用户脚本', value: '用户脚本' },
  { label: '公共脚本', value: '公共脚本' }
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
}, { immediate: true })
const runLoading = ref(false)
const debugLoading = ref(false)
const dragState = ref({
  draggingId: null,
  dragOverId: null, // 当前拖拽进入的 loop/if 步骤 ID（焦点高亮）
  dragOverParent: null,
  dragOverIndex: null,
  insertPosition: null, // 'before' | 'after' | null，用于指示插入位置
  insertTargetId: null // 插入目标步骤 ID（用于显示指示器）
})

const addOptions = Object.entries(stepDefinitions).map(([value, item]) => ({
  label: item.label,
  key: value,
  icon: renderIcon(item.icon, { size: 16 })
}))


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
    original: {
      ...step,
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
      params: step.request_params || {},
      data: step.request_body || {},
      headers: step.request_header || {},
      extract: step.extract_variables || {},
      validators: step.validators || {}
    }
  } else if (localType === 'if') {
    const parsed = parseJsonSafely(step.conditions) || {}
    base.config = {
      left: parsed.value || '',
      operator: parsed.operation || parsed.op || 'not_empty',
      remark: parsed.desc || ''
    }
    base.children = []
  } else if (localType === 'wait') {
    base.config = {
      seconds: step.wait || 0
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
    caseForm.case_tags = firstStepCase.case_tags || ''
    caseForm.case_desc = firstStepCase.case_desc || ''
  } else {
    caseForm.case_project = ''
    caseForm.case_name = ''
    caseForm.case_tags = ''
    caseForm.case_desc = ''
  }
}

// 将前端类型转换为后端类型
const localTypeToBackend = (localType) => {
  const typeMap = {
    'http': 'HTTP请求',
    'code': '执行代码请求(Python)',
    'if': '条件分支',
    'wait': '等待控制',
    'loop': '循环结构'
  }
  return typeMap[localType] || '执行代码请求(Python)'
}

// 将前端步骤格式转换为后端格式
const convertStepToBackend = (step, parentStepId = null, stepNo = 1) => {
  const original = step.original || {}
  const config = step.config || {}

  // 基础字段
  const backendStep = {
    step_id: original.id || null,
    step_code: original.step_code || step.id || null,
    step_name: step.name || original.step_name || '',
    step_desc: original.step_desc || '',
    step_type: localTypeToBackend(step.type),
    step_no: stepNo,
    case_id: original.case_id || caseId.value || null,
    parent_step_id: parentStepId,
    quote_case_id: original.quote_case_id || null
  }

  // 根据类型设置特定字段
  if (step.type === 'http') {
    backendStep.request_method = config.method || original.request_method || 'POST'
    backendStep.request_url = config.url || original.request_url || ''
    backendStep.request_header = config.headers || original.request_header || {}
    backendStep.request_body = config.data || original.request_body || {}
    backendStep.request_params = config.params ? (typeof config.params === 'string' ? config.params : JSON.stringify(config.params)) : original.request_params || null
    backendStep.request_form_data = config.form_data || original.request_form_data || null
    backendStep.request_form_urlencoded = config.form_urlencoded || original.request_form_urlencoded || null
    backendStep.extract_variables = config.extract_variables || original.extract_variables || null
    backendStep.assert_validators = config.assert_validators || original.assert_validators || null
    backendStep.defined_variables = config.defined_variables || original.defined_variables || null
  } else if (step.type === 'code') {
    backendStep.code = config.code !== undefined ? config.code : (original.code || '')
  } else if (step.type === 'loop') {
    // 循环模式必填
    backendStep.loop_mode = config.loop_mode || original.loop_mode || '次数循环'
    // 错误处理策略必填
    backendStep.loop_on_error = config.loop_on_error || original.loop_on_error || '继续下一次循环'
    // 循环间隔（所有模式都需要）
    backendStep.loop_interval = config.loop_interval !== undefined ? Number(config.loop_interval) : (original.loop_interval ? Number(original.loop_interval) : 0)

    // 根据循环模式设置特定字段
    if (backendStep.loop_mode === '次数循环') {
      backendStep.loop_maximums = config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original.loop_maximums ? Number(original.loop_maximums) : null)
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
      // 条件循环需要将条件对象转换为JSON字符串
      if (config.condition_value !== undefined || config.condition_operation !== undefined || config.condition_except_value !== undefined) {
        const conditionObj = {
          value: config.condition_value || '',
          operation: config.condition_operation || 'not_empty',
          except_value: config.condition_except_value || ''
        }
        backendStep.conditions = JSON.stringify(conditionObj)
      } else if (original.conditions) {
        backendStep.conditions = typeof original.conditions === 'string' ? original.conditions : JSON.stringify(original.conditions)
      } else {
        backendStep.conditions = null
      }
      backendStep.loop_timeout = config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original.loop_timeout ? Number(original.loop_timeout) : 0)
    }
  } else if (step.type === 'if') {
    const conditions = [{
      value: config.left || '',
      operation: config.operator || 'not_empty',
      desc: config.remark || ''
    }]
    backendStep.conditions = conditions
  } else if (step.type === 'wait') {
    backendStep.wait = config.seconds || original.wait || 0
  }

  // 处理子步骤
  if (step.children && step.children.length > 0) {
    backendStep.children = step.children.map((child, index) => {
      const childStepId = child.original?.id || null
      return convertStepToBackend(child, childStepId, index + 1)
    })
  }

  return backendStep
}

const handleSaveAll = async () => {
  try {
    // 构建用例信息
    const caseInfo = {
      ...caseForm
    }

    // 根据是否有caseId或caseCode判断是新增还是更新
    if (caseId.value || caseCode.value) {
      // 更新操作：添加case_id和case_code
      if (caseId.value) {
        caseInfo.case_id = caseId.value
      }
      if (caseCode.value) {
        caseInfo.case_code = caseCode.value
      } else {
        // 如果只有case_id没有case_code，尝试从步骤数据中获取
        const firstStep = steps.value[0]
        if (firstStep?.original?.case?.case_code) {
          caseInfo.case_code = firstStep.original.case.case_code
        }
      }
    } else {
      // 新增操作：case_id和case_code必须为null（schema要求必填但可以为null）
      caseInfo.case_id = null
      caseInfo.case_code = null
    }

    // 转换步骤数据
    const backendSteps = steps.value.map((step, index) => {
      const stepId = step.original?.id || null
      return convertStepToBackend(step, null, index + 1)
    })

    const payload = {
      case: caseInfo,
      steps: backendSteps
    }

    const res = await api.updateStepTree(payload)
    if (res?.code === '000000' || res?.code === 200 || res?.code === 0) {
      window.$message?.success?.(res?.message || '保存成功')
      // 重新加载数据
      await loadSteps()
    } else {
      window.$message?.error?.(res?.message || '保存失败')
    }
  } catch (error) {
    console.error('Failed to save step tree', error)
    window.$message?.error?.(error?.response?.data?.message || error?.message || '保存失败')
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
      case_id: caseId.value,
      initial_variables: {}
    })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      const stats = res.data?.statistics || {}
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

const handleDebug = async () => {
  if (!steps.value || steps.value.length === 0) {
    window.$message?.warning?.('请先添加测试步骤')
    return
  }
  debugLoading.value = true
  try {
    const res = await api.executeStepTree({
      case_id: caseId.value || 0,
      case_info: {...caseForm},
      steps: steps.value,
      initial_variables: {}
    })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      const stats = res.data?.statistics || {}
      const msg = `调试完成，总步骤: ${stats.total_steps}, 成功: ${stats.success_steps}, 失败: ${stats.failed_steps}, 成功率: ${stats.pass_ratio}%`
      window.$message?.success?.(msg)
    } else {
      window.$message?.error?.(res?.message || '调试失败')
    }
  } catch (error) {
    console.error('Failed to debug step tree', error)
    window.$message?.error?.(error?.message || '调试失败')
  } finally {
    debugLoading.value = false
  }
}

const loadSteps = async () => {
  stepExpandStates.value = new Map()
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
  } catch (error) {
    console.error('Failed to load step tree', error)
    steps.value = []
    selectedKeys.value = []
    hydrateCaseInfo([])
  }
}

const handleSelect = (keys) => {
  selectedKeys.value = keys
}

const currentStep = computed(() => {
  const key = selectedKeys.value?.[0]
  if (!key) return null
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
  // return ''
  if (!currentStep.value) return '步骤配置'
  return stepDefinitions[currentStep.value.type]?.label || '步骤配置'
})

const insertStep = (parentId, type, index = null) => {
  const def = stepDefinitions[type]
  if (!def) return null

  // 创建新步骤，遵循结构规范
  const newStep = {
    id: genId(),
    type,
    name: `${def.label}-${new Date().getTime()}`,
    config: {}
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
  // 如果parentId存在，说明是要添加到某个父步骤的子级
  // 如果parentId为null，说明是要添加到根级别
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    // 更新显示名称
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

const handleCopyStep = (id) => {
  const step = findStep(id)
  if (!step) return
  const copiedStep = JSON.parse(JSON.stringify(step))
  copiedStep.id = genId()
  copiedStep.name = `${copiedStep.name}(copy)`

  // 确保结构规范：非 loop/if 类型不应该有 children 字段
  const def = stepDefinitions[copiedStep.type]
  if (def && !def.allowChildren && copiedStep.children !== undefined) {
    // 删除不应该存在的 children 字段
    delete copiedStep.children
  } else if (def && def.allowChildren && !copiedStep.children) {
    // 确保 loop/if 类型有 children 字段（即使是空数组）
    copiedStep.children = []
  }

  // 递归更新子步骤ID，并确保子步骤结构规范
  const updateIds = (node) => {
    node.id = genId()
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
      const method = config.method || 'POST'
      const name = config.name || 'HTTP请求'
      step.name = `API ${method} ${name}`
    } else if (step.type === 'if') {
      const left = config.left || ''
      const operator = config.operator || 'not_empty'
      const operatorMap = {
        'not_empty': 'not_none',
        'empty': 'is_none',
        'eq': '==',
        'ne': '!='
      }
      step.name = `If ${left} ${operatorMap[operator] || operator}`
    } else if (step.type === 'wait') {
      step.name = `等待控制(${config.seconds || 0}秒)`
    } else if (step.type === 'code') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined) {
        step.name = config.step_name
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
    wait: 'icon-wait'
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

onMounted(() => {
  // 加载项目列表和标签列表（复用用例管理页面的数据源）
  loadProjects()
  loadTags()
  // 先从路由参数中初始化用例信息
  initCaseInfoFromRoute()
  // 然后加载步骤树数据
  loadSteps()
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
            options: capturedAddOptions,
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
