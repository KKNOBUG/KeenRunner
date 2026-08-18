<!--
  引用公共脚本 — 只读「用例信息」
  布局/样式与 CaseInfoPanel 保持一致；字段只读，右侧提供「重新选择」。
-->
<template>
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="['step-editor-card', { 'is-collapsed': caseInfoCollapsed }]"
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
          <n-button
              v-if="reselectHandler"
              type="primary"
              size="small"
              @click="reselectHandler"
          >
            <template #icon>
              <TheIcon icon="material-symbols:refresh" :size="14"/>
            </template>
            重新选择
          </n-button>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!caseInfoCollapsed">
      <div v-if="!quoteCasePayload" class="quote-case-hint">
        <n-text depth="3">
          暂无脚本详情，请在「选择公共脚本」中选定脚本；若已选过仍无内容，请保存并重新打开用例或点击「重新选择」。
        </n-text>
      </div>

      <n-form
          v-else
          :model="readonlyForm"
          label-placement="left"
          label-width="80px"
          size="small"
          class="step-editor-form case-info-form"
      >
        <div class="case-info-fields">
          <div class="case-field case-field-name">
            <n-form-item label="用例名称" path="case_name" required :show-feedback="false">
              <n-input
                  :value="readonlyForm.case_name"
                  disabled
                  size="small"
                  placeholder="请输入用例名称"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field case-field-desc">
            <n-form-item label="用例描述" path="case_desc" :show-feedback="false">
              <n-input
                  :value="readonlyForm.case_desc"
                  disabled
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
                  :value="readonlyForm.case_type"
                  :options="caseTypeOptions"
                  disabled
                  placeholder="请选择用例类型"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例属性" path="case_attr" required :show-feedback="false">
              <n-select
                  :value="readonlyForm.case_attr"
                  :options="caseAttrOptions"
                  disabled
                  placeholder="请选择用例属性"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="所属应用" path="case_project" required :show-feedback="false">
              <n-select
                  :value="readonlyForm.case_project"
                  :options="projectOptions"
                  disabled
                  filterable
                  placeholder="所属应用"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="所属标签" path="case_tags" required :show-feedback="false">
              <n-input
                  :value="displayTags"
                  disabled
                  size="small"
                  placeholder="请选择所属标签"
                  class="case-field-input"
              />
            </n-form-item>
          </div>
        </div>
      </n-form>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NText,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/index.js'

/** 与 CaseInfoPanel 选项顺序一致 */
const caseAttrOptions = [
  { label: '正案例', value: '正案例' },
  { label: '反案例', value: '反案例' },
]

const caseTypeOptions = [
  { label: '用户脚本', value: '用户脚本' },
  { label: '公共脚本', value: '公共脚本' },
  { label: '公共接口', value: '公共接口' },
]

let tagIdToNameCache = null
let tagIdToNameLoading = null

async function ensureTagIdNameMap() {
  if (tagIdToNameCache) return tagIdToNameCache
  if (tagIdToNameLoading) return tagIdToNameLoading
  tagIdToNameLoading = api.getTagList({ page: 1, page_size: 5000, state: 0 }).then((res) => {
    const map = {}
    for (const t of res?.data || []) {
      if (t && t.tag_id != null) map[t.tag_id] = t.tag_name || ''
    }
    tagIdToNameCache = map
    return map
  }).finally(() => {
    tagIdToNameLoading = null
  })
  return tagIdToNameLoading
}

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  step: { type: Object, default: () => ({}) },
  /** 重新选择公共脚本（勿用 onXxx 命名，Vue 会当成事件监听器） */
  reselectHandler: { type: Function, default: null },
  projectOptions: { type: Array, default: () => [] },
})

const caseInfoCollapsed = ref(false)

const quoteCasePayload = computed(() => props.step?.original?.quote_case ?? null)

const readonlyForm = computed(() => {
  const qc = quoteCasePayload.value
  if (!qc) {
    return {
      case_name: '',
      case_desc: '',
      case_type: null,
      case_attr: null,
      case_project: null,
    }
  }
  const cp = qc.case_project
  let case_project = null
  if (cp && typeof cp === 'object') {
    const id = cp.project_id
    case_project = id != null ? Number(id) : null
  } else if (cp != null && cp !== '') {
    const n = Number(cp)
    case_project = Number.isNaN(n) ? null : n
  }
  return {
    case_name: qc.case_name || '',
    case_desc: qc.case_desc || '',
    case_type: qc.case_type != null && qc.case_type !== '' ? String(qc.case_type) : null,
    case_attr: qc.case_attr != null && qc.case_attr !== '' ? String(qc.case_attr) : null,
    case_project,
  }
})

const displayTags = ref('')

const formatTagsSync = (qc) => {
  if (!qc) return ''
  const tags = qc.case_tags
  if (!Array.isArray(tags) || tags.length === 0) return ''
  if (tags[0] && typeof tags[0] === 'object' && ('tag_name' in tags[0] || tags[0].tag_name != null)) {
    return tags.map((t) => t.tag_name).filter(Boolean).join('、')
  }
  if (tags.every((t) => typeof t === 'number' || (typeof t === 'string' && /^\d+$/.test(String(t))))) {
    return null
  }
  return String(tags[0])
}

watch(
    () => quoteCasePayload.value,
    async () => {
      const qc = quoteCasePayload.value
      if (!qc) {
        displayTags.value = ''
        return
      }
      const sync = formatTagsSync(qc)
      if (sync != null) {
        displayTags.value = sync
        return
      }
      const tags = qc.case_tags
      if (!Array.isArray(tags) || !tags.length) {
        displayTags.value = ''
        return
      }
      const ids = tags.map((t) => Number(t)).filter((n) => !Number.isNaN(n))
      if (!ids.length) {
        displayTags.value = ''
        return
      }
      try {
        const map = await ensureTagIdNameMap()
        displayTags.value = ids.map((id) => map[id] || `#${id}`).join('、')
      } catch {
        displayTags.value = ids.map((id) => `#${id}`).join('、')
      }
    },
    { immediate: true, deep: true },
)
</script>

<style scoped>
/* 卡片壳 / 标题 / 折叠见 styles/autotest-theme.scss .step-editor-card */

.card-header-row {
  padding-right: 140px;
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
}

.quote-case-hint {
  padding: 8px 0;
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
</style>
