<script setup>
/**
 * 已选脚本面板：Collapse 折叠，分页规则与查询列表一致（CrudTable 远程分页模式 + 本地切片）
 * 执行次数默认 1，双击单元格可编辑
 */
import { computed, h, nextTick, onMounted, ref, watch } from 'vue'
import { NButton, NCollapse, NCollapseItem, NInputNumber, NTag, NTooltip } from 'naive-ui'
import CrudTable from '@/components/table/CrudTable.vue'
import { formatDateTime, renderIcon } from '@/utils'

const props = defineProps({
  scripts: { type: Array, default: () => [] },
})

const emit = defineEmits(['remove', 'update:execute-count'])

const tableRef = ref(null)
const expandedNames = ref(['selected'])
const listPaginationMeta = ref({ page: 1, page_size: 10 })
/** 正在双击编辑执行次数的 case_id */
const editingCaseId = ref(null)
const editingValue = ref(1)

const isExpanded = computed(() => expandedNames.value.includes('selected'))

async function refreshTable() {
  await nextTick()
  tableRef.value?.handleSearch?.()
}

const queryBarProps = {
  addReset: false,
  addSearch: false,
  addCreate: false,
  addDelete: false,
}

function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

async function getData(params) {
  const list = props.scripts || []
  const page = Number(params?.page) || 1
  const pageSize = Number(params?.page_size) || 10
  const start = (page - 1) * pageSize
  return {
    data: list.slice(start, start + pageSize),
    total: list.length,
  }
}

watch(
  () => props.scripts,
  () => {
    if (isExpanded.value) {
      refreshTable()
    }
  },
  { deep: true },
)

watch(expandedNames, async (names, prev) => {
  const nowOpen = Array.isArray(names) && names.includes('selected')
  const wasOpen = Array.isArray(prev) && prev.includes('selected')
  if (nowOpen && !wasOpen) {
    await refreshTable()
  }
})

onMounted(() => {
  if (isExpanded.value) {
    refreshTable()
  }
})

function normalizeExecuteCount(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n < 1) return 1
  return Math.min(Math.floor(n), 9999)
}

function startEditExecuteCount(row) {
  editingCaseId.value = Number(row.case_id)
  editingValue.value = normalizeExecuteCount(row.execute_count)
}

function commitEditExecuteCount(row) {
  if (editingCaseId.value == null) return
  const caseId = Number(row.case_id)
  if (Number(editingCaseId.value) !== caseId) return
  const next = normalizeExecuteCount(editingValue.value)
  editingCaseId.value = null
  emit('update:execute-count', { caseId, executeCount: next })
}

function cancelEditExecuteCount() {
  editingCaseId.value = null
}

function renderCaseTagsCompact(row) {
  const tags = Array.isArray(row.case_tags) ? row.case_tags.filter((t) => t && t.tag_name) : []
  if (!tags.length) return h('span', '-')
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

function renderExecuteCount(row) {
  const caseId = Number(row.case_id)
  const isEditing = Number(editingCaseId.value) === caseId
  if (isEditing) {
    return h(NInputNumber, {
      value: editingValue.value,
      min: 1,
      max: 9999,
      size: 'tiny',
      showButton: false,
      style: { width: '72px' },
      'onUpdate:value': (v) => {
        editingValue.value = v
      },
      onBlur: () => commitEditExecuteCount(row),
      onKeydown: (e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          commitEditExecuteCount(row)
        } else if (e.key === 'Escape') {
          e.preventDefault()
          cancelEditExecuteCount()
        }
      },
      // 自动聚焦
      onVnodeMounted: (vnode) => {
        nextTick(() => {
          const el = vnode.el?.querySelector?.('input')
          el?.focus?.()
          el?.select?.()
        })
      },
    })
  }
  return h(
    'span',
    {
      class: 'execute-count-cell',
      title: '双击编辑执行次数',
      onDblclick: (e) => {
        e.stopPropagation()
        startEditExecuteCount(row)
      },
    },
    String(normalizeExecuteCount(row.execute_count)),
  )
}

const columns = computed(() => {
  // 依赖编辑态，保证双击切换输入框与数值变更可刷新
  void editingCaseId.value
  void editingValue.value
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    {
      title: '序号',
      key: '__seq',
      width: 64,
      align: 'center',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '脚本名称',
      key: 'case_name',
      minWidth: 140,
      ellipsis: { tooltip: true },
    },
    {
      title: '所属应用',
      key: 'case_project',
      width: 120,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h('span', row.case_project?.project_name || row.project_name || '-')
      },
    },
    {
      title: '脚本标签',
      key: 'case_tags',
      width: 140,
      align: 'center',
      render(row) {
        return renderCaseTagsCompact(row)
      },
    },
    {
      title() {
        return h(
          'span',
          { class: 'execute-count-title' },
          [
            '执行次数',
            h(
              NTooltip,
              { trigger: 'hover', placement: 'top' },
              {
                trigger: () =>
                  h(
                    'span',
                    {
                      class: 'execute-count-help',
                      onClick: (e) => e.stopPropagation(),
                    },
                    [
                      renderIcon('material-symbols:help-outline', { size: 14 })(),
                    ],
                  ),
                default: () => '配置脚本的执行次数，如果开启数据源时，则是执行次数 * 数据源数量',
              },
            ),
          ],
        )
      },
      key: 'execute_count',
      width: 110,
      align: 'center',
      render(row) {
        return renderExecuteCount(row)
      },
    },
    {
      title: '脚本描述',
      key: 'case_desc',
      minWidth: 120,
      ellipsis: { tooltip: true },
      render(row) {
        return h('span', row.case_desc || '-')
      },
    },
    {
      title: '所属人',
      key: 'created_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h('span', row.created_user || '-')
      },
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
    {
      title: '操作',
      key: 'actions',
      width: 80,
      align: 'center',
      fixed: 'right',
      render(row) {
        return h(
          NButton,
          {
            size: 'tiny',
            quaternary: true,
            type: 'error',
            onClick: () => emit('remove', row.case_id),
          },
          {
            default: () => '删除',
            icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
          },
        )
      },
    },
  ]
})
</script>

<template>
  <NCollapse
    v-model:expanded-names="expandedNames"
    arrow-placement="left"
    display-directive="show"
    class="task-script-collapse"
  >
    <NCollapseItem name="selected" title="已选脚本">
      <CrudTable
        ref="tableRef"
        :remote="true"
        :is-pagination="true"
        :columns="columns"
        :get-data="getData"
        :query-bar-props="queryBarProps"
        :row-key="'case_id'"
        :scroll-x="1200"
        :single-line="true"
        @pagination-meta="onListPaginationMeta"
      />
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

:deep(.case-tags-cell-trigger) {
  max-width: 100%;
}

:deep(.case-tags-more) {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-2);
}

:deep(.case-tags-tooltip-inner) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 320px;
  justify-content: flex-start;
}

:deep(.execute-count-title) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

:deep(.execute-count-help) {
  display: inline-flex;
  align-items: center;
  color: var(--n-text-color-3);
  cursor: help;
  vertical-align: middle;
}

:deep(.execute-count-help:hover) {
  color: #18a058;
}

:deep(.execute-count-cell) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  user-select: none;
}

:deep(.execute-count-cell:hover) {
  background: rgba(24, 160, 88, 0.1);
  color: #18a058;
}
</style>
