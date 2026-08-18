<!--
  CaseInfoPanel — 步骤编辑页顶部「用例信息」区

  与步骤子页（HTTP/TCP Request 等）同一实现：n-card + 左侧红边卡片样式。
  职责：维护 caseForm；调试/保存/历史/模式切换通过 emit 交给 index.vue。
-->
<template>
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="['step-editor-card', 'case-info-card', { 'is-collapsed': caseInfoCollapsed }]"
  >
    <template #header>
      <div class="card-header-row">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="caseInfoCollapsed = !caseInfoCollapsed"
            @keydown.enter.prevent="caseInfoCollapsed = !caseInfoCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="caseInfoCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">用例信息</div>
        </div>
        <div class="card-header-actions" @click.stop>
          <n-space :size="8" align="center" class="case-info-header-actions">
            <n-button
                type="primary"
                size="small"
                :loading="debugLoading"
                :disabled="sourceMode"
                @click="emit('debug')"
            >
              调试
            </n-button>
            <n-button
                type="info"
                size="small"
                :loading="saveLoading"
                :disabled="sourceMode"
                @click="emit('save')"
            >
              保存
            </n-button>
            <n-button type="success" size="small" @click="emit('history')">历史</n-button>
            <div class="case-mode-switch-box">
              <n-switch
                  class="case-mode-switch"
                  size="medium"
                  :round="false"
                  :value="!treeMode"
                  @update:value="onSourceModeSwitch"
              />
              <span
                  class="case-mode-switch-text"
                  :class="treeMode ? 'is-tree' : 'is-source'"
              >
                {{ treeMode ? '步骤树模式' : '源数据模式' }}
              </span>
            </div>
          </n-space>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!caseInfoCollapsed">
      <n-form
          :model="caseForm"
          class="step-editor-form case-info-form"
          label-placement="left"
          label-width="80px"
          size="small"
      >
        <div class="case-info-fields">
          <div class="case-field case-field-name">
            <n-form-item label="用例名称" path="case_name" required :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_name"
                  size="small"
                  placeholder="请输入用例名称"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field case-field-desc">
            <n-form-item label="用例描述" path="case_desc" :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_desc"
                  size="small"
                  type="textarea"
                  :resizable="false"
                  :autosize="{ minRows: 1, maxRows: 1 }"
                  placeholder="请输入用例描述"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例类型" path="case_type" required :show-feedback="false">
              <n-select
                  :value="caseForm.case_type"
                  v-model:show="caseTypeSelectShow"
                  :options="caseTypeOptions"
                  clearable
                  placeholder="请选择用例类型"
                  size="small"
                  class="case-field-input"
                  @update:value="onCaseTypeSelectChange"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例属性" path="case_attr" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_attr"
                  v-model:show="caseAttrSelectShow"
                  :options="caseAttrOptions"
                  clearable
                  placeholder="请选择用例属性"
                  size="small"
                  class="case-field-input"
                  :disabled="caseForm.case_type === '公共接口'"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="所属应用" path="case_project" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_project"
                  v-model:show="caseProjectSelectShow"
                  :options="projectOptions"
                  :loading="projectLoading"
                  clearable
                  filterable
                  placeholder="所属应用"
                  size="small"
                  class="case-field-input"
                  @update:value="onCaseProjectUserChange"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item
                label="所属标签"
                path="case_tags"
                :required="caseForm.case_type === '用户脚本'"
                :show-feedback="false"
            >
              <n-popover
                  v-model:show="tagPopoverShow"
                  trigger="click"
                  placement="bottom-start"
                  :style="{ width: '400px' }"
                  :disabled="isPublicFamilyCase"
              >
                <template #trigger>
                  <n-input
                      :value="getSelectedTagNames()"
                      :clearable="!isPublicFamilyCase"
                      readonly
                      :placeholder="isPublicFamilyCase ? '' : '请选择所属标签'"
                      size="small"
                      class="case-field-input"
                      :disabled="isPublicFamilyCase"
                      @clear="caseForm.case_tags = []"
                      @click="!isPublicFamilyCase && (tagPopoverShow = !tagPopoverShow)"
                  />
                </template>
                <template #default>
                  <div class="tag-picker-panel">
                    <div class="tag-picker-col overlay-scroll">
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
                      <div v-else class="autotest-empty-hint">
                        {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                      </div>
                    </div>
                    <div class="tag-picker-col tag-picker-col--names overlay-scroll">
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
                      <div v-else class="autotest-empty-hint">
                        {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                      </div>
                    </div>
                  </div>
                </template>
              </n-popover>
            </n-form-item>
          </div>
        </div>
      </n-form>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
/**
 * CaseInfoPanel.vue
 *
 * defineProps: debugLoading / saveLoading / treeMode
 * defineEmits: debug / save / history / case-type-change / update:treeMode / request-tree-mode-change
 * defineExpose: caseForm, getCasePayload, validateCaseForm, hydrateFromCasePayload,
 *               hydrateFromStepTree, reloadFromRoute, projectOptions, projectLoading
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NList,
  NListItem,
  NPopover,
  NSelect,
  NSpace,
  NSwitch,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const props = defineProps({
  debugLoading: { type: Boolean, default: false },
  saveLoading: { type: Boolean, default: false },
  /** true=步骤树模式，false=源数据模式 */
  treeMode: { type: Boolean, default: true },
})

const emit = defineEmits(['debug', 'save', 'history', 'case-type-change', 'update:treeMode', 'request-tree-mode-change'])

const sourceMode = computed(() => !props.treeMode)

const onSourceModeSwitch = (sourceOn) => {
  // switch 开启=源数据模式(右)，关闭=步骤树模式(左)
  emit('request-tree-mode-change', !sourceOn)
}

// 仅用户在下拉框切换用例类型时通知父级（程序化 hydrate 直接写 caseForm.case_type，不触发此回调，避免加载/应用 JSON 时误触发移除与提示）
const onCaseTypeSelectChange = (newType) => {
  const oldType = caseForm.case_type
  caseForm.case_type = newType
  emit('case-type-change', { newType, oldType })
}

const route = useRoute()

/** 与步骤子页 Request 卡片一致的收起状态 */
const caseInfoCollapsed = ref(false)

const caseForm = reactive({
  case_project: '',
  case_name: '',
  case_tags: [],
  case_desc: '',
  case_attr: '',
  case_type: '',
})

/** 公共脚本/公共接口：不允许打标签，仅用户脚本需要所属标签 */
const isPublicFamilyCase = computed(() => ['公共脚本', '公共接口'].includes(caseForm.case_type))

const projectOptions = ref([])
const projectLoading = ref(false)

const tagOptions = ref([])
/** 全量标签（不按应用过滤）：用于已选标签的名称解析与跨应用归属判定，保证显示与落库一致 */
const allTagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

/** 三个下拉框的菜单展开状态：菜单 teleport 到 body，鼠标移入菜单即离开面板区域，需据此抑制面板自动折叠 */
const caseTypeSelectShow = ref(false)
const caseAttrSelectShow = ref(false)
const caseProjectSelectShow = ref(false)

/** 任一选择弹层（用例类型/用例属性/所属应用/所属标签）处于展开状态 */
const anyDropdownOpen = computed(() =>
    caseTypeSelectShow.value || caseAttrSelectShow.value || caseProjectSelectShow.value || tagPopoverShow.value
)

const caseAttrOptions = [
  { label: '正案例', value: '正案例' },
  { label: '反案例', value: '反案例' },
]

const caseTypeOptions = [
  { label: '用户脚本', value: '用户脚本' },
  { label: '公共脚本', value: '公共脚本' },
  { label: '公共接口', value: '公共接口' },
]

const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach((tag) => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) {
      groups[mode] = []
    }
    groups[mode].push(tag)
  })
  return groups
})

const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

const initCaseInfoFromRoute = () => {
  if (!route.query.case_info) return
  try {
    const caseInfo = JSON.parse(route.query.case_info)
    if (caseInfo.case_project) {
      caseForm.case_project = typeof caseInfo.case_project === 'object'
          ? caseInfo.case_project.project_id
          : caseInfo.case_project
    }
    caseForm.case_name = caseInfo.case_name || ''
    if (Array.isArray(caseInfo.case_tags) && caseInfo.case_tags.length > 0) {
      caseForm.case_tags = caseInfo.case_tags
          .map((tag) => (typeof tag === 'object' ? tag.tag_id : tag))
          .filter((id) => id !== undefined && id !== null)
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

const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getProjectList({
      page: 1,
      page_size: 1000,
      state: 0,
    })
    if (res?.data) {
      projectOptions.value = res.data.map((item) => ({
        label: item.project_name,
        value: item.project_id,
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
    const res = await api.getTagList({
      page: 1,
      page_size: 1000,
      state: 0,
    })
    if (res?.data) {
      allTagOptions.value = res.data
      if (projectId) {
        tagOptions.value = res.data.filter((tag) => tag.tag_project === projectId)
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

const getSelectedTagNames = () => {
  const tags = caseForm.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  // 用全量标签解析名称：跨应用的已选标签（历史残留）也要如实显示，不做"显示为空但仍携带落库"
  const names = tags
      .map((tagId) => allTagOptions.value.find((t) => t.tag_id === tagId)?.tag_name)
      .filter((name) => name)
  return names.join(', ')
}

/** 用户在下拉框切换所属应用（水化赋值不触发）：剔除不属于新应用的已选标签，避免跨应用残留静默落库 */
const onCaseProjectUserChange = (newProjectId) => {
  if (newProjectId == null || newProjectId === '') return
  if (!Array.isArray(caseForm.case_tags) || caseForm.case_tags.length === 0) return
  const pid = Number(newProjectId)
  caseForm.case_tags = caseForm.case_tags.filter((tagId) => {
    const tag = allTagOptions.value.find((t) => t.tag_id === tagId)
    // 标签不在全量清单中（已停用等）时保留，不做无法判定的剔除
    return tag ? tag.tag_project === pid : true
  })
}

const isTagSelected = (tagId) => {
  const tags = caseForm.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

const handleTagSelect = (tagId) => {
  if (!Array.isArray(caseForm.case_tags)) {
    caseForm.case_tags = []
  }
  const index = caseForm.case_tags.indexOf(tagId)
  if (index > -1) {
    caseForm.case_tags.splice(index, 1)
  } else {
    caseForm.case_tags.push(tagId)
  }
}

const validateCaseForm = () => {
  if (!caseForm.case_project) {
    return { valid: false, message: '请选择所属应用' }
  }
  if (!caseForm.case_name || !String(caseForm.case_name).trim()) {
    return { valid: false, message: '请输入用例名称' }
  }
  // 所属标签：仅用户脚本必填；公共脚本/公共接口禁止打标
  if (caseForm.case_type === '用户脚本' && (!Array.isArray(caseForm.case_tags) || caseForm.case_tags.length === 0)) {
    return { valid: false, message: '请选择所属标签' }
  }
  if (!caseForm.case_attr) {
    return { valid: false, message: '请选择用例属性' }
  }
  if (!caseForm.case_type) {
    return { valid: false, message: '请选择用例类型' }
  }
  return { valid: true }
}

const hydrateFromStepTree = (data) => {
  const firstStepCase = data?.[0]?.case
  if (firstStepCase) {
    caseForm.case_project = firstStepCase.case_project || ''
    caseForm.case_name = firstStepCase.case_name || ''
    caseForm.case_tags = firstStepCase.case_tags ?? []
    caseForm.case_desc = firstStepCase.case_desc || ''
    caseForm.case_attr = firstStepCase.case_attr || ''
    caseForm.case_type = firstStepCase.case_type || ''
  } else {
    // 无用例信息（新增页传入空数组等）：清空表单，避免 keep-alive 复用时残留上一用例数据
    caseForm.case_project = ''
    caseForm.case_name = ''
    caseForm.case_tags = []
    caseForm.case_desc = ''
    caseForm.case_attr = ''
    caseForm.case_type = ''
  }
}

const hydrateFromCasePayload = (caseInfo) => {
  if (!caseInfo || typeof caseInfo !== 'object') return
  if (caseInfo.case_project != null) {
    caseForm.case_project = typeof caseInfo.case_project === 'object'
        ? caseInfo.case_project.project_id
        : caseInfo.case_project
  }
  if (caseInfo.case_name != null) caseForm.case_name = caseInfo.case_name || ''
  if (caseInfo.case_tags != null) {
    caseForm.case_tags = Array.isArray(caseInfo.case_tags)
        ? caseInfo.case_tags.map((tag) => (typeof tag === 'object' ? tag.tag_id : tag)).filter((id) => id != null)
        : []
  }
  if (caseInfo.case_desc != null) caseForm.case_desc = caseInfo.case_desc || ''
  if (caseInfo.case_attr != null) caseForm.case_attr = caseInfo.case_attr || ''
  if (caseInfo.case_type != null) caseForm.case_type = caseInfo.case_type || ''
}

const getCasePayload = () => ({
  case_name: caseForm.case_name || '',
  case_project: caseForm.case_project || null,
  // 公共类型强制不传标签；用户脚本快照拷贝（payload 构建到 axios 序列化之间存在 await 窗口）
  case_tags: isPublicFamilyCase.value
      ? null
      : (Array.isArray(caseForm.case_tags) ? [...caseForm.case_tags] : []),
  case_type: caseForm.case_type || null,
  case_attr: caseForm.case_attr || null,
  case_desc: caseForm.case_desc ?? '',
})

initCaseInfoFromRoute()

watch(
    () => caseForm.case_project,
    (newVal) => {
      loadTags(newVal || null)
    },
    { immediate: true },
)

watch(
    () => caseForm.case_tags,
    (newVal) => {
      if (!Array.isArray(newVal)) {
        caseForm.case_tags = []
      }
    },
    { immediate: true },
)

// 公共接口：锁定正案例；公共脚本/公共接口：清空标签（与后端口径一致）
watch(
    () => caseForm.case_type,
    (caseType) => {
      if (caseType === '公共接口') {
        caseForm.case_attr = '正案例'
      }
      if (['公共脚本', '公共接口'].includes(caseType)) {
        caseForm.case_tags = []
        tagPopoverShow.value = false
      }
    },
)

onMounted(() => {
  loadProjects()
})

defineExpose({
  caseForm,
  getCasePayload,
  validateCaseForm,
  hydrateFromCasePayload,
  hydrateFromStepTree,
  reloadFromRoute: initCaseInfoFromRoute,
  projectOptions,
  projectLoading,
  caseInfoCollapsed,
  anyDropdownOpen,
})
</script>

<style scoped>
/* 卡片壳 / 标题 / 折叠见 styles/autotest-theme.scss .step-editor-card */

.case-info-card {
  margin-bottom: 16px;
}

.card-header-row {
  padding-right: 360px;
}

.case-info-header-actions :deep(.n-button) {
  font-size: var(--step-editor-font-size, 13px);
}

/* 方形开关：文案固定叠在轨道内（滑块旁），避免 checked/unchecked 插槽切换动画错位 */
.case-mode-switch-box {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 28px;
  vertical-align: middle;
}

.case-mode-switch {
  height: 28px;
}

.case-mode-switch :deep(.n-switch__rail) {
  height: 28px;
  min-width: 108px;
  border-radius: 2px;
  box-sizing: border-box;
}

.case-mode-switch :deep(.n-switch__button) {
  border-radius: 2px;
  width: 22px;
  height: 22px;
  top: 3px;
}

.case-mode-switch-text {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  pointer-events: none;
  user-select: none;
}

/* 步骤树模式：滑块在左，文案在右 */
.case-mode-switch-text.is-tree {
  left: 26px;
  right: 8px;
  color: var(--n-text-color-2);
}

/* 源数据模式：滑块在右，文案在左（轨道主色） */
.case-mode-switch-text.is-source {
  left: 8px;
  right: 26px;
  color: #fff;
}

.case-info-form {
  width: 100%;
}

.case-info-fields {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 8px 16px;
}

.case-field {
  min-width: 0;
  grid-column: span 3;
}

.case-field :deep(.n-form-item) {
  width: 100%;
}

.case-field-desc {
  grid-column: span 9;
}

.case-field-desc :deep(textarea) {
  resize: none;
}

.case-field-input {
  width: 100%;
  transition: border-color 0.3s ease;
}

.case-field-input:hover {
  border-color: #F4511E;
}

@media (max-width: 768px) {
  .case-info-fields {
    grid-template-columns: 1fr;
  }

  .case-field,
  .case-field-desc {
    grid-column: 1 / -1;
  }

  .card-header-row {
    padding-right: 0;
  }

  .card-header-actions {
    position: static;
    transform: none;
    margin-left: auto;
  }
}

.tag-mode-selected {
  background-color: rgba(244, 81, 30, 0.1);
  font-weight: 500;
}

/* 用例标签二级选择面板（左分类 / 右标签名） */
.tag-picker-panel {
  display: flex;
  height: 300px;
  width: 400px;
}

/* 左侧分类列（配合 .overlay-scroll） */
.tag-picker-col {
  width: 45%;
  overflow-x: hidden;
  overflow-y: auto;
}

/* 右侧标签名列 */
.tag-picker-col--names {
  width: 50%;
}

.tag-name-selected {
  background-color: rgba(244, 81, 30, 0.1);
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
  color: #F4511E;
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
  background-color: rgba(244, 81, 30, 0.1);
}
</style>
