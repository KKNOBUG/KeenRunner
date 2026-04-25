<template>
  <n-card
      size="small"
      class="case-info-card quote-script-case-card"
      title="用例信息"
  >
    <template #header-extra>
      <n-button
          v-if="onReselect"
          type="primary"
          quaternary
          size="small"
          @click="onReselect"
      >
        <template #icon>
          <TheIcon icon="material-symbols:refresh" :size="14"/>
        </template>
        重新选择
      </n-button>
    </template>

    <div v-if="!quoteCasePayload" class="quote-case-hint">
      <n-text depth="3">暂无脚本详情，请在「选择公共脚本」中选定脚本；若已选过仍无内容，请保存并重新打开用例或点击「重新选择」。</n-text>
    </div>

    <div
        v-else
        class="case-info-fields quote-case-readonly"
    >
      <div class="case-field">
        <span class="case-field-label case-field-required">所属应用</span>
        <n-select
            :value="readonlyProjectId"
            :options="projectOptions"
            disabled
            filterable
            placeholder="所属应用"
            size="small"
            class="case-field-input"
        />
      </div>

      <div class="case-field">
        <span class="case-field-label case-field-required">用例名称</span>
        <n-input
            :value="quoteCasePayload.case_name || ''"
            disabled
            size="small"
            placeholder="请输入用例名称"
            class="case-field-input"
        />
      </div>

      <div class="case-field">
        <span class="case-field-label case-field-required">所属标签</span>
        <n-input
            :value="displayTags"
            disabled
            size="small"
            placeholder="请选择所属标签"
            class="case-field-input"
        />
      </div>

      <div class="case-field">
        <span class="case-field-label case-field-required">用例属性</span>
        <n-select
            :value="readonlyCaseAttr"
            :options="caseAttrOptions"
            disabled
            placeholder="请选择用例属性"
            size="small"
            class="case-field-input"
        />
      </div>

      <div class="case-field">
        <span class="case-field-label case-field-required">用例类型</span>
        <n-select
            :value="readonlyCaseType"
            :options="caseTypeOptions"
            disabled
            placeholder="请选择用例类型"
            size="small"
            class="case-field-input"
        />
      </div>

      <div class="case-field case-field-full">
        <span class="case-field-label">用例描述</span>
        <n-input
            :value="quoteCasePayload.case_desc || ''"
            disabled
            size="small"
            type="textarea"
            placeholder="请输入用例描述"
        />
      </div>
    </div>
  </n-card>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { NCard, NText, NButton, NInput, NSelect } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api/index.js'

/** 与步骤编辑页 `steps/index.vue`「用例信息」、用例管理表单选项一致（testcase 列表页无该卡片） */
const caseAttrOptions = [
  { label: '正用例', value: '正用例' },
  { label: '反用例', value: '反用例' }
]

const caseTypeOptions = [
  { label: '公共脚本', value: '公共脚本' },
  { label: '用户脚本', value: '用户脚本' }
]

let tagIdToNameCache = null
let tagIdToNameLoading = null

async function ensureTagIdNameMap() {
  if (tagIdToNameCache) return tagIdToNameCache
  if (tagIdToNameLoading) return tagIdToNameLoading
  tagIdToNameLoading = api.getApiTagList({ page: 1, page_size: 5000, state: 0 }).then((res) => {
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
  onReselect: { type: Function, default: null },
  projectOptions: { type: Array, default: () => [] }
})

const quoteCasePayload = computed(() => props.step?.original?.quote_case ?? null)

const readonlyProjectId = computed(() => {
  const qc = quoteCasePayload.value
  if (!qc) return null
  const cp = qc.case_project
  if (cp && typeof cp === 'object') {
    const id = cp.project_id
    return id != null ? Number(id) : null
  }
  if (cp != null && cp !== '') {
    const n = Number(cp)
    return Number.isNaN(n) ? null : n
  }
  return null
})

const readonlyCaseAttr = computed(() => {
  const v = quoteCasePayload.value?.case_attr
  return v != null && v !== '' ? String(v) : null
})

const readonlyCaseType = computed(() => {
  const v = quoteCasePayload.value?.case_type
  return v != null && v !== '' ? String(v) : null
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
    () => [quoteCasePayload.value, props.projectOptions],
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
    { immediate: true, deep: true }
)
</script>

<style scoped>
/* 与 steps/index.vue 顶部「用例信息」卡片一致 */
.case-info-card {
  margin-bottom: 0;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.quote-script-case-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #f4511e;
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
  align-items: flex-start;
}

.case-field-full :deep(.n-input) {
  flex: 1;
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
  color: #f4511e;
  margin-right: 4px;
}

.case-field-input {
  flex: 1;
  transition: border-color 0.3s ease;
}

.quote-case-hint {
  padding: 8px 0;
}

/* 引用脚本用例信息不允许修改：整体置灰（仅表单区域，不影响右上角「重新选择」） */
.quote-case-readonly {
  opacity: 0.72;
}

.quote-case-readonly :deep(.n-input),
.quote-case-readonly :deep(.n-base-selection) {
  cursor: not-allowed;
}

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
</style>
