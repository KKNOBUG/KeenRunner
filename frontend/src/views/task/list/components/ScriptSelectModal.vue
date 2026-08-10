<script setup>
/**
 * 添加脚本面板（可折叠 Card，样式对齐步骤编辑 Request/Response）：展开后查询并勾选，勾选即添加
 */
import { computed, h, nextTick, ref, watch } from 'vue'
import {
  NCollapse,
  NCollapseItem,
  NInput,
  NList,
  NListItem,
  NPopover,
  NSelect,
  NTag,
  NTooltip,
} from 'naive-ui'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import { formatDateTime } from '@/utils'
import api from '@/api'

const props = defineProps({
  defaultProjectId: { type: [Number, String], default: null },
  projectOptions: { type: Array, default: () => [] },
  alreadySelectedIds: { type: Array, default: () => [] },
})

const emit = defineEmits(['add', 'remove'])

const expandedNames = ref([])
const tableRef = ref(null)
const checkedRowKeys = ref([])
const listPaginationMeta = ref({ page: 1, page_size: 10 })
/** 避免勾选回写时触发二次 emit */
let syncingCheckedKeys = false

const queryItems = ref({
  case_name: '',
  case_attr: null,
  case_type: '用户脚本',
  case_project: null,
  case_tags: [],
  created_user: '',
  updated_user: '',
  state: 0,
})

const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)
const inited = ref(false)

const caseAttrOptions = [
  { label: '正用例', value: '正用例' },
  { label: '反用例', value: '反用例' },
]

const isExpanded = computed(() => expandedNames.value.includes('add'))

const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach((tag) => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) groups[mode] = []
    groups[mode].push(tag)
  })
  return groups
})

const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: false,
  actionMode: 'split',
}

function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

async function loadTags(projectId = null) {
  try {
    tagLoading.value = true
    const res = await api.getTagList({
      page: 1,
      page_size: 1000,
      state: 0,
    })
    if (res?.data) {
      tagOptions.value = projectId
        ? res.data.filter((tag) => tag.tag_project === projectId)
        : res.data
      selectedTagMode.value = null
    } else {
      tagOptions.value = []
    }
  } catch (e) {
    console.error('加载标签失败', e)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

function handleTagSelect(tagId) {
  if (!Array.isArray(queryItems.value.case_tags)) queryItems.value.case_tags = []
  const index = queryItems.value.case_tags.indexOf(tagId)
  if (index > -1) queryItems.value.case_tags.splice(index, 1)
  else queryItems.value.case_tags.push(tagId)
}

function getSelectedTagNames() {
  const tags = queryItems.value.case_tags
  if (!Array.isArray(tags) || !tags.length) return ''
  return tags
    .map((tagId) => tagOptions.value.find((t) => t.tag_id === tagId)?.tag_name)
    .filter(Boolean)
    .join(', ')
}

function isTagSelected(tagId) {
  return Array.isArray(queryItems.value.case_tags) && queryItems.value.case_tags.includes(tagId)
}

function renderCaseTagsCompact(row) {
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
        minHeight: '22px',
      },
    },
    [
      h(NTag, { type: 'info', size: 'small', bordered: true }, { default: () => tags[0].tag_name }),
      tags.length > 1 ? h('span', { class: 'case-tags-more' }, `+${tags.length - 1}`) : null,
    ].filter(Boolean),
  )
  if (tags.length === 1) return trigger
  return h(NTooltip, { placement: 'top', trigger: 'hover', showArrow: true }, {
    trigger: () => trigger,
    default: () =>
      h(
        'div',
        { class: 'case-tags-tooltip-inner' },
        tags.map((tag) =>
          h(NTag, { type: 'info', size: 'small', bordered: true, style: { margin: '2px' } }, { default: () => tag.tag_name }),
        ),
      ),
  })
}

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    { type: 'selection', fixed: 'left', width: 48 },
    {
      title: '序号',
      key: '__seq',
      width: 64,
      align: 'center',
      fixed: 'left',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '用例类型',
      key: 'case_type',
      width: 100,
      align: 'center',
      render(row) {
        const typeColorMap = { '公共脚本': 'warning', '公共接口': 'success' }
        const mode = typeColorMap[row.case_type] || 'info'
        return h(NTag, { type: mode, round: true, bordered: true }, { default: () => row.case_type })
      },
    },
    {
      title: '用例名称',
      key: 'case_name',
      width: 220,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '用例属性',
      key: 'case_attr',
      width: 100,
      align: 'center',
      render(row) {
        const mode = row.case_attr === '反用例' ? 'primary' : 'success'
        return h(NTag, { type: mode, round: true, bordered: true }, { default: () => row.case_attr || '-' })
      },
    },
    {
      title: '所属应用',
      key: 'case_project',
      width: 120,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h('span', row.case_project?.project_name || '')
      },
    },
    {
      title: '所属标签',
      key: 'case_tags',
      width: 140,
      align: 'center',
      render(row) {
        return renderCaseTagsCompact(row)
      },
    },
    {
      title: '创建人员',
      key: 'created_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '更新时间',
      key: 'updated_time',
      width: 170,
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.updated_time) || '-')
      },
    },
  ]
})

watch(
  () => queryItems.value.case_project,
  (pid) => {
    if (isExpanded.value) loadTags(pid)
  },
)

/** 已选变化时同步勾选态（含从已选表删除） */
watch(
  () => props.alreadySelectedIds,
  (ids) => {
    syncingCheckedKeys = true
    checkedRowKeys.value = [...(ids || [])]
    nextTick(() => {
      syncingCheckedKeys = false
    })
  },
  { deep: true },
)

async function ensureInitAndSearch() {
  if (!inited.value) {
    queryItems.value = {
      case_name: '',
      case_attr: null,
      case_type: '用户脚本',
      case_project: props.defaultProjectId ?? null,
      case_tags: [],
      created_user: '',
      updated_user: '',
      state: 0,
    }
    syncingCheckedKeys = true
    checkedRowKeys.value = [...(props.alreadySelectedIds || [])]
    await loadTags(queryItems.value.case_project)
    inited.value = true
    await nextTick()
    syncingCheckedKeys = false
  }
  await nextTick()
  tableRef.value?.handleSearch?.()
}

watch(expandedNames, async (names, prev) => {
  const nowOpen = Array.isArray(names) && names.includes('add')
  const wasOpen = Array.isArray(prev) && prev.includes('add')
  if (nowOpen && !wasOpen) {
    await ensureInitAndSearch()
  }
})

const pageRowsCache = ref([])

function onTableDataChange(data) {
  pageRowsCache.value = Array.isArray(data) ? data : []
}

async function getData(params) {
  // 任务仅允许添加用户脚本，查询条件固定，不提供用例类型筛选
  return api.getApiTestcaseList({
    ...params,
    case_type: '用户脚本',
  })
}

function onCheckedKeysUpdate(keys) {
  if (syncingCheckedKeys) return
  const nextKeys = (keys || []).map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0)
  const prevKeys = (props.alreadySelectedIds || [])
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id) && id > 0)
  const prevSet = new Set(prevKeys)
  const nextSet = new Set(nextKeys)
  // 仅对当前页可见行判断取消勾选，避免远程分页误删其它页已选
  const pageIdSet = new Set(
    (pageRowsCache.value || []).map((r) => Number(r.case_id)).filter((id) => Number.isFinite(id) && id > 0),
  )

  const added = nextKeys.filter((id) => !prevSet.has(id))
  const removed = prevKeys.filter((id) => pageIdSet.has(id) && !nextSet.has(id))

  // 合并：保留非本页已选 + 本页新勾选
  const merged = [
    ...prevKeys.filter((id) => !pageIdSet.has(id) || nextSet.has(id)),
    ...added,
  ]
  const uniq = [...new Set(merged)]
  syncingCheckedKeys = true
  checkedRowKeys.value = uniq
  nextTick(() => {
    syncingCheckedKeys = false
  })

  if (added.length) resolveRowsAndEmitAdd(added)
  for (const id of removed) emit('remove', id)
}

async function resolveRowsAndEmitAdd(ids) {
  const idSet = new Set(ids.map(Number))
  const fromTable = (pageRowsCache.value || []).filter((r) => idSet.has(Number(r.case_id)))
  const found = new Map(fromTable.map((r) => [Number(r.case_id), r]))
  const missing = ids.filter((id) => !found.has(Number(id)))

  if (missing.length) {
    try {
      const res = await api.getApiTestcaseList({
        page: 1,
        page_size: Math.min(Math.max(missing.length * 2, 50), 200),
        state: 0,
      })
      ;(Array.isArray(res?.data) ? res.data : []).forEach((r) => {
        if (idSet.has(Number(r.case_id))) found.set(Number(r.case_id), r)
      })
    } catch (e) {
      console.error('补全脚本行失败', e)
    }
  }

  for (const id of ids) {
    const row = found.get(Number(id)) || { case_id: id, case_name: `用例 ${id}` }
    emit('add', row)
  }
}

function collapse() {
  expandedNames.value = []
}

defineExpose({ collapse })
</script>

<template>
  <NCollapse v-model:expanded-names="expandedNames" arrow-placement="left" class="task-script-collapse">
    <NCollapseItem name="add" title="添加脚本">
      <CrudTable
        v-if="isExpanded"
        ref="tableRef"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :columns="columns"
        :get-data="getData"
        :row-key="'case_id'"
        :scroll-x="1200"
        :single-line="true"
        @pagination-meta="onListPaginationMeta"
        @on-data-change="onTableDataChange"
        @update:checked-row-keys="onCheckedKeysUpdate"
      >
        <template #queryBar>
          <QueryBarItem label="用例名称：">
            <NInput
              v-model:value="queryItems.case_name"
              clearable
              placeholder="请输入用例名称"
              class="query-input"
              @keypress.enter="tableRef?.handleSearch()"
            />
          </QueryBarItem>
          <QueryBarItem label="用例属性：">
            <NSelect
              v-model:value="queryItems.case_attr"
              :options="caseAttrOptions"
              clearable
              placeholder="请选择用例属性"
              class="query-input"
            />
          </QueryBarItem>
          <QueryBarItem label="所属应用：">
            <NSelect
              v-model:value="queryItems.case_project"
              :options="projectOptions"
              clearable
              filterable
              placeholder="请选择所属应用"
              class="query-input"
            />
          </QueryBarItem>
          <QueryBarItem label="所属标签：">
            <NPopover
              v-model:show="tagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
            >
              <template #trigger>
                <NInput
                  :value="getSelectedTagNames()"
                  clearable
                  readonly
                  placeholder="请选择所属标签"
                  class="query-input"
                  @clear="queryItems.case_tags = []"
                  @click="tagPopoverShow = !tagPopoverShow"
                />
              </template>
              <div style="display: flex; height: 300px; width: 400px;">
                <div style="width: 45%; overflow-y: auto;">
                  <NList v-if="Object.keys(tagModeGroups).length > 0">
                    <NListItem
                      v-for="(tags, mode) in tagModeGroups"
                      :key="mode"
                      :class="{ 'tag-mode-selected': selectedTagMode === mode, 'tag-mode-item': true }"
                      @click="selectedTagMode = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="empty-hint">{{ tagLoading ? '加载中...' : '暂无标签数据' }}</div>
                </div>
                <div style="width: 50%; overflow-y: auto;">
                  <NList v-if="selectedTagMode && currentTagNames.length > 0">
                    <NListItem
                      v-for="tag in currentTagNames"
                      :key="tag.tag_id"
                      :class="{ 'tag-name-selected': isTagSelected(tag.tag_id) }"
                      class="tag-list-item"
                      @click="handleTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="empty-hint">
                    {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </NPopover>
          </QueryBarItem>
          <QueryBarItem label="创建人员：">
            <NInput
              v-model:value="queryItems.created_user"
              clearable
              placeholder="请输入创建人员"
              class="query-input"
              @keypress.enter="tableRef?.handleSearch()"
            />
          </QueryBarItem>
        </template>
      </CrudTable>
    </NCollapseItem>
  </NCollapse>
</template>

<style scoped>
.task-script-collapse :deep(.n-collapse-item__header) {
  padding: 10px 0;
  font-weight: 600;
  font-size: 14px;
}

.task-script-collapse :deep(.n-collapse-item__header-main) {
  cursor: pointer;
}

.query-input {
  width: 180px;
}

.tag-mode-selected,
.tag-name-selected {
  background-color: var(--n-color-primary-hover);
  font-weight: 500;
}

.tag-list-item,
.tag-mode-item {
  cursor: pointer;
  padding: 8px 12px;
}

.tag-checkbox {
  flex-shrink: 0;
  width: 16px;
  color: #18a058;
  font-weight: bold;
}

.tag-name-text,
.tag-mode-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-hint {
  padding: 12px;
  color: var(--n-text-color-3);
  font-size: 13px;
}

:deep(.case-tags-cell-trigger) {
  max-width: 100%;
}

:deep(.case-tags-more) {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-2);
}
</style>
