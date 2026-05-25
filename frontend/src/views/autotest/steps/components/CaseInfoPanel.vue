<!--
  CaseInfoPanel — 步骤编辑页顶部「用例信息」区

  职责：维护 caseForm（项目/名称/标签/描述/属性/类型），加载项目与标签选项；
        提供执行/调试/保存按钮（通过 emit 交给 index.vue 处理）。

  与 index.vue 协作：
  - 父通过 ref 调用 getCaseForm / getCasePayload / validateCaseForm / hydrateFromStepTree
  - case_type 变化时 emit case-type-change，父级负责步骤树里「引用公共脚本」的移除/恢复
-->
<template>
  <n-collapse
      v-model:expanded-names="caseInfoExpandedNames"
      class="case-info-collapse"
      arrow-placement="right"
      :trigger-areas="['main', 'arrow']"
  >
    <n-collapse-item name="caseInfo">
      <template #header>
        <span class="case-info-collapse-title">用例信息</span>
      </template>
      <template #header-extra>
        <n-space :size="8" class="case-info-header-actions" @click.stop>
          <n-button type="info" size="small" :loading="runLoading" @click="emit('run')">执行</n-button>
          <n-button type="primary" size="small" :loading="debugLoading" @click="emit('debug')">调试</n-button>
          <n-button type="success" size="small" :loading="saveLoading" @click="emit('save')">保存</n-button>
        </n-space>
      </template>
      <n-form
          :model="caseForm"
          label-placement="left"
          label-width="80px"
          class="case-info-form"
      >
        <div class="case-info-fields">
          <div class="case-field">
            <n-form-item label="所属应用" path="case_project" required :show-feedback="false">
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
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例名称" path="case_name" required :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_name"
                  size="small"
                  placeholder="请输入用例名称"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="所属标签" path="case_tags" required :show-feedback="false">
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
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例属性" path="case_attr" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_attr"
                  :options="caseAttrOptions"
                  clearable
                  placeholder="请选择用例属性"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例类型" path="case_type" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_type"
                  :options="caseTypeOptions"
                  clearable
                  placeholder="请选择用例类型"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field case-field-full">
            <n-form-item label="用例描述" path="case_desc" :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_desc"
                  size="small"
                  type="textarea"
                  placeholder="请输入用例描述"
              />
            </n-form-item>
          </div>
        </div>
      </n-form>
    </n-collapse-item>
  </n-collapse>
</template>

<script setup>
/**
 * CaseInfoPanel.vue
 *
 * defineProps: runLoading / debugLoading / saveLoading — 按钮 loading，由父 v-model 或单向传入
 * defineEmits:
 *   - run / debug / save → index.vue 的 handleRun / handleDebug / handleSaveAll
 *   - case-type-change({ newType, oldType }) → index.vue 的 onCaseTypeChange
 *
 * defineExpose（父组件 caseInfoPanelRef）：
 *   - caseForm, getCaseForm, getCasePayload, validateCaseForm
 *   - hydrateFromStepTree(data) — loadSteps 后用步骤树接口首条 case 回填表单
 *   - reloadFromRoute — 解析 route.query.case_info（从用例管理复制进入）
 *   - projectOptions, projectLoading — 供右侧 HTTP/TCP/DB 编辑器选「所属应用」
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NInput,
  NList,
  NListItem,
  NPopover,
  NSelect,
  NSpace,
} from 'naive-ui'
import api from '@/api'

defineProps({
  runLoading: { type: Boolean, default: false },
  debugLoading: { type: Boolean, default: false },
  saveLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['run', 'debug', 'save', 'case-type-change'])

const route = useRoute()

/** 用例信息折叠面板展开项，默认展开 */
const caseInfoExpandedNames = ref(['caseInfo'])

/** 用例基本信息，保存时由 getCasePayload() 交给 index 拼进 updateOrCreateStepTree */
const caseForm = reactive({
  case_project: '',
  case_name: '',
  case_tags: [],
  case_desc: '',
  case_attr: '',
  case_type: '',
})

const projectOptions = ref([])
const projectLoading = ref(false)

const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

const caseAttrOptions = [
  { label: '正用例', value: '正用例' },
  { label: '反用例', value: '反用例' },
]

const caseTypeOptions = [
  { label: '用户脚本', value: '用户脚本' },
  { label: '公共脚本', value: '公共脚本' },
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

/** 从路由 query.case_info（JSON）初始化表单，用于用例管理「复制」新开页签 */
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
  const names = tags
      .map((tagId) => tagOptions.value.find((t) => t.tag_id === tagId)?.tag_name)
      .filter((name) => name)
  return names.join(', ')
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

/** 保存前必填校验，index.vue handleSaveAll 首步调用 */
const validateCaseForm = () => {
  if (!caseForm.case_project) {
    return { valid: false, message: '请选择所属应用' }
  }
  if (!caseForm.case_name || !String(caseForm.case_name).trim()) {
    return { valid: false, message: '请输入用例名称' }
  }
  if (!Array.isArray(caseForm.case_tags) || caseForm.case_tags.length === 0) {
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

/** 从步骤树接口数据回填用例信息（loadSteps / 复制进入时由父组件调用） */
const hydrateFromStepTree = (data) => {
  const firstStepCase = data?.[0]?.case
  if (firstStepCase) {
    caseForm.case_project = firstStepCase.case_project || ''
    caseForm.case_name = firstStepCase.case_name || ''
    caseForm.case_tags = firstStepCase.case_tags ?? (Array.isArray(firstStepCase.case_tags) ? firstStepCase.case_tags : [])
    caseForm.case_desc = firstStepCase.case_desc || ''
    caseForm.case_attr = firstStepCase.case_attr || ''
    caseForm.case_type = firstStepCase.case_type || ''
  } else if (Array.isArray(data) && data.length > 0) {
    caseForm.case_project = ''
    caseForm.case_name = ''
    caseForm.case_tags = []
    caseForm.case_desc = ''
    caseForm.case_attr = ''
    caseForm.case_type = ''
  }
}

const getCasePayload = () => ({
  case_name: caseForm.case_name || '',
  case_project: caseForm.case_project || null,
  case_tags: Array.isArray(caseForm.case_tags) ? caseForm.case_tags : [],
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

/** 用例类型变更通知父页面（引用步骤增删逻辑在 index，不在本组件） */
watch(
    () => caseForm.case_type,
    (newType, oldType) => {
      emit('case-type-change', { newType, oldType })
    },
)

onMounted(() => {
  loadProjects()
})

/** 对外 API，供 index.vue 通过 caseInfoPanelRef 访问 */
defineExpose({
  caseForm,
  getCaseForm: () => caseForm,
  getCasePayload,
  validateCaseForm,
  hydrateFromStepTree,
  reloadFromRoute: initCaseInfoFromRoute,
  projectOptions,
  projectLoading,
})
</script>

<style scoped>
.case-info-collapse {
  --n-title-font-size: 13px;
  --n-font-size: 13px;
  --n-title-font-weight: 400;
  margin-bottom: 16px;
  font-size: 13px;
}

.case-info-collapse-title {
  font-size: 14px;
  font-weight: 500;
  line-height: 1.15;
}

.case-info-collapse :deep(.n-collapse-item) {
  border-radius: 12px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.5);
  border-left: 3px solid #F4511E;
  background: var(--n-color);
}

.case-info-collapse :deep(.n-collapse-item__header) {
  display: flex;
  align-items: center;
  padding: 10px 12px !important;
  font-size: 13px !important;
  font-weight: 400;
  min-height: 40px;
  box-sizing: border-box;
}

.case-info-collapse :deep(.n-collapse-item__header-main) {
  display: flex;
  align-items: center;
  font-size: 13px !important;
  font-weight: 400 !important;
  line-height: 1.15;
}

.case-info-collapse :deep(.n-collapse-item__header-extra) {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  margin-left: 12px;
}

.case-info-header-actions :deep(.n-button) {
  font-size: 13px;
}

.case-info-collapse :deep(.n-collapse-item__content-inner) {
  padding: 0 12px 16px;
}

.case-info-collapse :deep(.n-form-item-label) {
  font-size: 13px;
}

.case-info-form {
  width: 100%;
  font-size: 13px;
}

.case-info-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 8px 24px;
}

.case-field {
  min-width: 0;
}

.case-field :deep(.n-form-item) {
  width: 100%;
}

.case-field-full {
  grid-column: 1 / -1;
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
    gap: 10px;
  }
}

@media (min-width: 1200px) {
  .case-info-fields {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.tag-mode-selected {
  background-color: rgba(244, 81, 30, 0.1);
  font-weight: 500;
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
