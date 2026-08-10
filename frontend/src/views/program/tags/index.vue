<script setup>
import { computed, h, onMounted, ref, resolveDirective, watch, withDirectives } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NText,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: '标签管理' })

/**
 * 标签心智模型（仅供用户脚本打标）：
 * 应用 × 大类(tag_mode) × 名称(tag_name)
 * 唯一约束同后端 unique_together。
 */

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  tag_project: null,
  tag_mode: null,
  tag_name: '',
})
const projectOptions = ref([])
const projectLoading = ref(false)
/** 查询区「大类」下拉（随应用变化） */
const queryModeOptions = ref([])
/** 表单「大类」下拉（可新建，随应用变化） */
const formModeOptions = ref([])
const modeOptionsLoading = ref(false)
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

/** QueryBar：左搜索+右更多（分裂按钮） */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'split',
}

function projectLabel(projectId) {
  const opt = projectOptions.value.find((p) => p.value === projectId)
  return opt?.label ?? (projectId != null ? String(projectId) : '-')
}

/**
 * 拉取某应用下已有大类，供查询/表单复用，减少「冒烟 / 冒烟测试」分裂。
 */
async function loadModeOptions({ projectId, target }) {
  if (!projectId) {
    if (target === 'query' || target === 'both') queryModeOptions.value = []
    if (target === 'form' || target === 'both') formModeOptions.value = []
    return
  }
  modeOptionsLoading.value = true
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
    const opts = modes.map((m) => ({ label: m, value: m }))
    if (target === 'query' || target === 'both') queryModeOptions.value = opts
    if (target === 'form' || target === 'both') formModeOptions.value = opts
  } catch (_) {
    if (target === 'query' || target === 'both') queryModeOptions.value = []
    if (target === 'form' || target === 'both') formModeOptions.value = []
  } finally {
    modeOptionsLoading.value = false
  }
}

async function handleBatchDelete() {
  const ids = checkedRowKeys.value || []
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的标签')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条标签吗？删除后用例上已关联的标签将失效，请谨慎操作。`,
    async confirm() {
      await api.deleteTagBatch({ tag_ids: ids })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
      // 大类选项可能变化
      if (queryItems.value.tag_project) {
        loadModeOptions({
          projectId: queryItems.value.tag_project,
          target: 'query',
        })
      }
    },
  })
}

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    tag_project: queryItems.value.tag_project || undefined,
    tag_mode: queryItems.value.tag_mode || undefined,
    tag_name: queryItems.value.tag_name || undefined,
    ...overrides,
  }
}

function onQueryProjectChange(projectId) {
  queryItems.value.tag_mode = null
  loadModeOptions({
    projectId,
    target: 'query',
  })
}

function customHandleAdd() {
  handleAdd()
  // 若查询区已选应用，新增时默认带上，减少重复选择
  if (queryItems.value.tag_project) {
    modalForm.value.tag_project = queryItems.value.tag_project
  }
  if (queryItems.value.tag_mode) {
    modalForm.value.tag_mode = queryItems.value.tag_mode
  }
}

function customHandleEdit(row) {
  handleEdit(row)
}

watch(
    () => [modalVisible.value, modalForm.value.tag_project],
    ([visible, projectId]) => {
      if (!visible) return
      loadModeOptions({ projectId, target: 'form' })
    }
)

const originalHandleSave = handleSave
function customHandleSave(...args) {
  originalHandleSave(...args, () => {
    if (queryItems.value.tag_project) {
      loadModeOptions({
        projectId: queryItems.value.tag_project,
        target: 'query',
      })
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
  // 进入页面不自动请求表格数据，由用户点击「搜索」按钮时再请求
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
        return projectLabel(row.tag_project)
      },
    },
    {
      title: '标签大类',
      key: 'tag_mode',
      width: 100,
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
          h(
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
          ),
        ]
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
        <QueryBarItem label="标签大类：">
          <NSelect
              v-model:value="queryItems.tag_mode"
              :options="queryModeOptions"
              :loading="modeOptionsLoading"
              :disabled="!queryItems.tag_project"
              clearable
              filterable
              placeholder="先选应用后可选"
              style="width: 140px"
          />
        </QueryBarItem>
        <QueryBarItem label="标签名称：">
          <NInput
              v-model:value="queryItems.tag_name"
              clearable
              placeholder="支持模糊搜索"
              style="width: 160px"
              @keypress.enter="$table?.handleSearch()"
          />
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
              :loading="modeOptionsLoading"
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
