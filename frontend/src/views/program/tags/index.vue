<script setup>
import { computed, h, onMounted, ref, resolveDirective, watch, withDirectives } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NList,
  NListItem,
  NPopconfirm,
  NPopover,
  NSelect,
  NText,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, formatDateTime, renderIcon } from '@/utils'
import { useApiPermission, useBatchDeleteGuard, useCRUD } from '@/composables'
import { useUserStore } from '@/store'
import api from '@/api'

defineOptions({ name: '标签管理' })

/**
 * 标签心智模型（仅供用户脚本打标）：
 * 应用 × 大类(tag_mode) × 名称(tag_name)
 * 唯一约束同后端 unique_together。
 */

const $table = ref(null)
const userStore = useUserStore()
const { hasApiPermission } = useApiPermission()
const { pickDeletableIds } = useBatchDeleteGuard()
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  tag_project: null,
  tag_ids: [],
})
const projectOptions = ref([])
const projectLoading = ref(false)
/** 查询区标签二级选择 */
const tagQueryPopoverShow = ref(false)
const projectTags = ref([])
const selectedTagModeForQuery = ref(null)
/** 表单「大类」下拉（可新建，随应用变化） */
const formModeOptions = ref([])
const vPermission = resolveDirective('permission')

const {
  modalVisible,
  modalAction,
  modalTitle,
  modalLoading,
  handleAdd,
  handleDelete,
  handleEdit,
  handleSave,
  modalForm,
  modalFormRef,
} = useCRUD({
  name: '标签',
  initForm: {
    tag_project: null,
    tag_mode: null,
    tag_name: '',
    tag_desc: '',
  },
  doCreate: (form) =>
      api.createTag({
        tag_project: form.tag_project,
        tag_mode: String(form.tag_mode ?? '').trim(),
        tag_name: String(form.tag_name ?? '').trim(),
        tag_desc: form.tag_desc?.trim?.() || form.tag_desc || undefined,
      }),
  doDelete: (params) => api.deleteTag(params),
  doUpdate: (form) =>
      api.updateTag({
        tag_id: form.tag_id,
        tag_code: form.tag_code,
        tag_project: form.tag_project,
        tag_mode: String(form.tag_mode ?? '').trim(),
        tag_name: String(form.tag_name ?? '').trim(),
        tag_desc: form.tag_desc?.trim?.() || form.tag_desc || undefined,
      }),
  refresh: () => $table.value?.handleSearch(),
})

/** QueryBar：左搜索+右更多（分裂按钮）；无接口权限的入口不下发 */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: hasApiPermission('post', '/autotest/tag/create'),
  addDelete: hasApiPermission('post', '/autotest/tag/delete'),
  actionMode: 'split',
}

function projectLabel(projectId) {
  const opt = projectOptions.value.find((p) => p.value === projectId)
  return opt?.label ?? (projectId != null ? String(projectId) : '-')
}

/**
 * 拉取某应用下已有大类，供表单复用，减少「冒烟 / 冒烟测试」分裂。
 */
async function loadModeOptions({ projectId }) {
  if (!projectId) {
    formModeOptions.value = []
    return
  }
  try {
    const res = await api.getTagList({
      page: 1,
      page_size: 9999,
      state: 0,
      tag_project: projectId,
    })
    const modes = [
      ...new Set(
          (res?.data || [])
              .map((t) => String(t.tag_mode ?? '').trim())
              .filter(Boolean)
      ),
    ].sort((a, b) => a.localeCompare(b, 'zh-CN'))
    formModeOptions.value = modes.map((m) => ({ label: m, value: m }))
  } catch (_) {
    formModeOptions.value = []
  }
}

/** 查询区：按 tag_mode 分组当前应用的标签 */
const tagModeGroups = computed(() => {
  const groups = {}
  for (const t of projectTags.value) {
    const mode = String(t.tag_mode ?? '').trim() || '未分类'
    ;(groups[mode] ||= []).push(t)
  }
  return groups
})

/** 查询区：当前选中大类下的标签列表 */
const currentQueryTagNames = computed(() => {
  if (!selectedTagModeForQuery.value) return []
  return tagModeGroups.value[selectedTagModeForQuery.value] || []
})

/** 查询区：已选标签名称拼接展示 */
function getQuerySelectedTagNames() {
  const ids = queryItems.value.tag_ids || []
  if (!ids.length) return ''
  const names = ids
      .map((id) => projectTags.value.find((t) => t.tag_id === id)?.tag_name)
      .filter(Boolean)
  return names.length <= 2 ? names.join('、') : `${names[0]}、${names[1]} 等${names.length}个`
}

/** 查询区：切换标签选中状态 */
function handleQueryTagSelect(tagId) {
  const ids = queryItems.value.tag_ids || []
  const idx = ids.indexOf(tagId)
  if (idx === -1) ids.push(tagId)
  else ids.splice(idx, 1)
  queryItems.value.tag_ids = [...ids]
}

function isQueryTagSelected(tagId) {
  return (queryItems.value.tag_ids || []).includes(tagId)
}

async function handleBatchDelete() {
  const ids = checkedRowKeys.value || []
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的标签')
    return
  }
  // 先剔除不在可删范围的标签，避免整批请求被后端删除权限整体拒绝
  const deletableIds = pickDeletableIds({
    ids,
    rows: $table.value?.tableData || [],
    keyField: 'tag_id',
    label: '标签',
  })
  if (!deletableIds.length) {
    window.$message?.warning?.('选中的标签均不在可删范围，无法删除')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${deletableIds.length} 条标签吗？删除后用例上已关联的标签将失效，请谨慎操作。`,
    async confirm() {
      await api.deleteTagBatch({ tag_ids: deletableIds })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
      // 标签选项可能变化
      if (queryItems.value.tag_project) {
        loadProjectTags(queryItems.value.tag_project)
      }
    },
  })
}

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    tag_project: queryItems.value.tag_project || undefined,
    tag_ids: queryItems.value.tag_ids?.length ? queryItems.value.tag_ids : undefined,
    ...overrides,
  }
}

/**
 * 加载某应用下的标签列表，供查询区二级选择使用。
 */
async function loadProjectTags(projectId) {
  if (!projectId) {
    projectTags.value = []
    return
  }
  try {
    const res = await api.getTagList({
      page: 1,
      page_size: 9999,
      state: 0,
      tag_project: projectId,
    })
    projectTags.value = res?.data || []
    // 自动选中第一个大类
    const modes = [...new Set(projectTags.value.map((t) => String(t.tag_mode ?? '').trim()).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'zh-CN'))
    selectedTagModeForQuery.value = modes[0] || null
  } catch (_) {
    projectTags.value = []
    selectedTagModeForQuery.value = null
  }
}

function onQueryProjectChange(projectId) {
  queryItems.value.tag_ids = []
  selectedTagModeForQuery.value = null
  projectTags.value = []
  loadProjectTags(projectId)
}

function customHandleAdd() {
  handleAdd()
  // 若查询区已选应用，新增时默认带上，减少重复选择
  if (queryItems.value.tag_project) {
    modalForm.value.tag_project = queryItems.value.tag_project
  }
}

function customHandleEdit(row) {
  handleEdit(row)
}

watch(
    () => [modalVisible.value, modalForm.value.tag_project],
    ([visible, projectId]) => {
      if (!visible) return
      loadModeOptions({ projectId })
    }
)

const originalHandleSave = handleSave
function customHandleSave(...args) {
  originalHandleSave(...args, () => {
    if (queryItems.value.tag_project) {
      loadProjectTags(queryItems.value.tag_project)
    }
  })
}

onMounted(async () => {
  projectLoading.value = true
  try {
    const res = await api.getProjectList({ page: 1, page_size: 9999, state: 0 })
    projectOptions.value = (res.data || []).map((p) => ({
      label: p.project_name || p.project_code,
      value: p.project_id,
    }))
  } catch (_) {
    projectOptions.value = []
  } finally {
    projectLoading.value = false
  }
  // 标签列表由 CrudTable 首次挂载自动查询
})

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    { type: 'selection', fixed: 'left', width: 48 },
    {
      title: '序号',
      key: '__seq',
      width: 50,
      align: 'center',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '所属应用',
      key: 'tag_project',
      minWidth: 150,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.tag_project_name || projectLabel(row.tag_project)
      },
    },
    {
      title: '标签大类',
      key: 'tag_mode',
      width: 150,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const mode = String(row.tag_mode ?? '').trim()
        if (!mode) return h(NText, { depth: 3 }, { default: () => '未分类' })
        return mode
      },
    },
    {
      title: '标签名称',
      key: 'tag_name',
      minWidth: 150,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const name = String(row.tag_name ?? '').trim()
        return name || '-'
      },
    },
    {
      title: '标签描述',
      key: 'tag_desc',
      minWidth: 150,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const d = String(row.tag_desc ?? '').trim()
        return d || h(NText, { depth: 3 }, { default: () => '-' })
      },
    },
    {
      title: '更新时间',
      key: 'updated_time',
      width: 180,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.updated_time ? formatDateTime(row.updated_time) : '-'
      },
    },
    {
      title: '创建人员',
      key: 'created_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.created_user || '-'
      },
    },
    {
      title: '维护人员',
      key: 'updated_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.updated_user || '-'
      },
    },
    {
      title: '标签代码',
      key: 'tag_code',
      width: 400,
      align: 'center',
      ellipsis: { tooltip: true }
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      align: 'center',
      fixed: 'right',
      render(row) {
        // 编辑全员可用；删除按后端行级 can_delete（含角色删除范围），再叠加接口权限指令
        const deletable = userStore.canDeleteData(row.created_user, row.can_delete)
        return [
          withDirectives(
              h(
                  NButton,
                  {
                    size: 'tiny',
                    quaternary: true,
                    type: 'info',
                    onClick: () => customHandleEdit(row),
                  },
                  {
                    default: () => '编辑',
                    icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                  }
              ),
              [[vPermission, apiPermissionKey('post', '/autotest/tag/update')]]
          ),
          deletable
              ? h(
                  NPopconfirm,
                  {
                    onPositiveClick: () => handleDelete({ tag_id: row.tag_id }, false),
                    onNegativeClick: () => {},
                  },
                  {
                    trigger: () =>
                        withDirectives(
                            h(
                                NButton,
                                {
                                  size: 'tiny',
                                  quaternary: true,
                                  type: 'error',
                                },
                                {
                                  default: () => '删除',
                                  icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                                }
                            ),
                            [[vPermission, apiPermissionKey('delete', '/autotest/tag/delete')]]
                        ),
                    default: () => h('div', {}, '确定删除该标签吗？用例上已关联的引用将失效。'),
                  }
              )
              : null,
        ].filter(Boolean)
      },
    },
  ]
})
</script>

<template>
  <CommonPage show-footer title="标签列表">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :scroll-x="2000"
        :columns="columns"
        :get-data="(params) => api.getTagList(buildSearchBody(params))"
        :single-line="true"
        row-key="tag_id"
        @query-bar-create="customHandleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.tag_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择应用"
              style="width: 180px"
              @update:value="onQueryProjectChange"
          />
        </QueryBarItem>
        <QueryBarItem label="标签名称：">
          <n-popover
              v-model:show="tagQueryPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
              :disabled="!queryItems.tag_project"
          >
            <template #trigger>
              <n-input
                  :value="getQuerySelectedTagNames()"
                  readonly
                  :clearable="queryItems.tag_ids?.length > 0"
                  :disabled="!queryItems.tag_project"
                  placeholder="先选应用后可选"
                  style="width: 240px"
                  @click="queryItems.tag_project && (tagQueryPopoverShow = !tagQueryPopoverShow)"
                  @clear="queryItems.tag_ids = []"
              />
            </template>
            <template #default>
              <div class="tag-picker-panel">
                <div class="tag-picker-col overlay-scroll">
                  <n-list v-if="Object.keys(tagModeGroups).length > 0">
                    <n-list-item
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': selectedTagModeForQuery === mode, 'tag-mode-item': true }"
                        @click="selectedTagModeForQuery = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                    </n-list-item>
                  </n-list>
                  <div v-else class="autotest-empty-hint">暂无标签数据</div>
                </div>
                <div class="tag-picker-col tag-picker-col--names overlay-scroll">
                  <n-list v-if="selectedTagModeForQuery && currentQueryTagNames.length > 0">
                    <n-list-item
                        v-for="tag in currentQueryTagNames"
                        :key="tag.tag_id"
                        :class="{ 'tag-name-selected': isQueryTagSelected(tag.tag_id) }"
                        class="tag-list-item"
                        @click="handleQueryTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isQueryTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                    </n-list-item>
                  </n-list>
                  <div v-else class="autotest-empty-hint">
                    {{ selectedTagModeForQuery ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </template>
          </n-popover>
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
        v-model:visible="modalVisible"
        :title="modalTitle"
        :loading="modalLoading"
        @save="customHandleSave"
    >
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="100"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem v-if="modalAction === 'edit'" label="标签代码" path="tag_code">
          <NInput :value="modalForm.tag_code" disabled placeholder="系统自动生成" />
        </NFormItem>
        <NFormItem
            label="所属应用"
            path="tag_project"
            :rule="{ required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] }"
        >
          <NSelect
              v-model:value="modalForm.tag_project"
              :options="projectOptions"
              :loading="projectLoading"
              filterable
              placeholder="请选择应用"
              :disabled="modalAction === 'edit'"
          />
        </NFormItem>
        <NFormItem
            label="标签大类"
            path="tag_mode"
            :rule="{ required: true, message: '请选择或输入标签大类', trigger: ['change', 'blur'] }"
        >
          <NSelect
              v-model:value="modalForm.tag_mode"
              :options="formModeOptions"
              :disabled="!modalForm.tag_project"
              filterable
              tag
              clearable
              placeholder="如：冒烟、回归；可输入新建"
          />
        </NFormItem>
        <NFormItem
            label="标签名称"
            path="tag_name"
            :rule="{ required: true, message: '请输入标签名称', trigger: ['input', 'blur'] }"
        >
          <NInput
              v-model:value="modalForm.tag_name"
              maxlength="64"
              show-count
              clearable
              placeholder="用例选标时展示的名称"
          />
        </NFormItem>
        <NFormItem label="标签描述" path="tag_desc">
          <NInput
              v-model:value="modalForm.tag_desc"
              type="textarea"
              maxlength="2048"
              show-count
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="可选：说明该标签适用场景"
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<style scoped>
.tag-mode-selected {
  background-color: rgba(244, 81, 30, 0.1);
  font-weight: 500;
}

/* 标签二级选择面板（左分类 / 右标签名） */
.tag-picker-panel {
  display: flex;
  height: 300px;
  width: 400px;
}

/* 左侧分类列 */
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

:deep(.n-list.item) {
  transition: background-color 0.2s;
}

:deep(.n-list.item:hover) {
  background-color: rgba(244, 81, 30, 0.1);
}
</style>
