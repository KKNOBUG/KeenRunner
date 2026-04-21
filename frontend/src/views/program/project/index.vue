<script setup>
import { computed, h, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NInput, NPopconfirm, NTag, NTooltip } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDate, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: '项目管理' })

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  project_name: '',
  project_code: '',
  project_state: '',
  project_dev_owners: '',
  project_test_owners: '',
})
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
  name: '应用',
  initForm: {
    project_name: '',
    project_code: '',
    project_desc: '',
    project_state: '',
    project_phase: '',
    project_dev_owners: '',
    project_test_owners: '',
  },
  doCreate: (form) => {
    const toList = (v) => (Array.isArray(v) ? v : (v || '').replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean))
    const payload = {
      project_name: form.project_name,
      project_desc: form.project_desc || undefined,
      project_state: form.project_state || undefined,
      project_phase: form.project_phase || undefined,
      project_dev_owners: toList(form.project_dev_owners),
      project_test_owners: toList(form.project_test_owners),
    }
    return api.createProject(payload)
  },
  doDelete: (params) => api.deleteProject(params),
  doUpdate: (form) => {
    const toList = (v) => (Array.isArray(v) ? v : (v || '').replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean))
    // 可清空字段必须传当前值（含 ''），否则后端 exclude_unset 会忽略未传字段，导致无法清空
    const payload = {
      project_id: form.project_id,
      project_code: form.project_code ?? undefined,
      project_name: form.project_name,
      project_desc: form.project_desc ?? undefined,
      project_state: form.project_state === undefined ? undefined : (form.project_state ?? ''),
      project_phase: form.project_phase === undefined ? undefined : (form.project_phase ?? ''),
      project_dev_owners: toList(form.project_dev_owners),
      project_test_owners: toList(form.project_test_owners),
    }
    return api.updateProject(payload)
  },
  refresh: () => $table.value?.handleSearch(),
})

function customHandleEdit(row) {
  handleEdit({
    ...row,
    project_dev_owners: Array.isArray(row.project_dev_owners) ? row.project_dev_owners.join(', ') : (row.project_dev_owners || ''),
    project_test_owners: Array.isArray(row.project_test_owners) ? row.project_test_owners.join(', ') : (row.project_test_owners || ''),
  })
}

// 进入页面不自动请求表格数据，由用户点击「搜索」按钮时再请求
// onMounted(() => {
//   $table.value?.handleSearch()
// })

/** 将用户输入的字符串转为后端要求的 List[str]，多人可用逗号分隔 */
function toOwnerList(v) {
  if (v == null || v === '') return undefined
  if (Array.isArray(v)) return v.length ? v : undefined
  const list = String(v)
      .replace(/，/g, ',')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  return list.length ? list : undefined
}

/** QueryBar：与表格工具栏一致的查询区操作（下拉合并为「操作」） */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'dropdown',
}

async function handleBatchDelete() {
  const ids = checkedRowKeys.value || []
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的应用')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条应用吗？`,
    async confirm() {
      await api.deleteProjectBatch({ project_ids: ids })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

function buildSearchBody(overrides = {}) {
  const q = queryItems.value
  return {
    state: 0,
    ...overrides,
    project_code: (overrides.project_code ?? q.project_code) || undefined,
    project_state: (overrides.project_state ?? q.project_state) || undefined,
    // 后端要求 List[str]，将输入字符串转为数组（多人逗号分隔）
    project_dev_owners: toOwnerList(overrides.project_dev_owners ?? q.project_dev_owners),
    project_test_owners: toOwnerList(overrides.project_test_owners ?? q.project_test_owners),
  }
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
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '应用名称',
      key: 'project_name',
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '应用状态',
      key: 'project_state',
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '应用阶段',
      key: 'project_phase',
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '开发负责人',
      key: 'project_dev_owners',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const v = row.project_dev_owners
        if (!v || !v.length) return '-'
        return Array.isArray(v) ? v.join(', ') : String(v)
      },
    },
    {
      title: '开发人员',
      key: 'project_developers',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const v = row.project_developers
        if (!v || !v.length) return '-'
        return Array.isArray(v) ? v.join(', ') : String(v)
      },
    },
    {
      title: '测试负责人',
      key: 'project_test_owners',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const v = row.project_test_owners
        if (!v || !v.length) return '-'
        return Array.isArray(v) ? v.join(', ') : String(v)
      },
    },
    {
      title: '测试人员',
      key: 'project_testers',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const v = row.project_testers
        if (!v || !v.length) return '-'
        return Array.isArray(v) ? v.join(', ') : String(v)
      },
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
              [[vPermission, 'post/api/v1/role/update']]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({ project_id: row.project_id }, false),
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
                        [[vPermission, 'delete/api/v1/role/delete']]
                    ),
                default: () => h('div', {}, '确定删除该应用吗?'),
              }
          ),
        ]
      },
    },
  ]
})
</script>

<template>
  <CommonPage show-footer title="应用列表">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :scroll-x="1520"
        :columns="columns"
        :get-data="(params) => api.getProjectList(buildSearchBody(params))"
        :single-line="true"
        row-key="project_id"
        @query-bar-create="handleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="应用名称：">
          <NInput
              v-model:value="queryItems.project_name"
              clearable
              placeholder="请输入应用名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="应用状态：">
          <NInput
              v-model:value="queryItems.project_state"
              clearable
              placeholder="请输入应用状态"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="开发负责人：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_dev_owners"
              clearable
              placeholder="多人用逗号分隔"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="测试负责人：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_test_owners"
              clearable
              placeholder="多人用逗号分隔"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal v-model:visible="modalVisible" :title="modalTitle" :loading="modalLoading" @save="handleSave">
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="110"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem
            v-if="modalAction === 'edit'"
            label="应用ID"
            path="project_id"
        >
          <NInput v-model:value="modalForm.project_id" disabled />
        </NFormItem>
        <NFormItem
            label="应用名称"
            path="project_name"
            :rule="{ required: true, message: '请输入应用名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.project_name" placeholder="请输入应用名称" />
        </NFormItem>
        <NFormItem v-if="modalAction === 'edit'" label="应用代码" path="project_code">
          <NInput v-model:value="modalForm.project_code" placeholder="应用代码（只读）" disabled />
        </NFormItem>
        <NFormItem label="应用状态" path="project_state">
          <NInput v-model:value="modalForm.project_state" placeholder="如：开发中、已上线" />
        </NFormItem>
        <NFormItem label="应用阶段" path="project_phase">
          <NInput v-model:value="modalForm.project_phase" placeholder="如：迭代1" />
        </NFormItem>
        <NFormItem label="应用描述" path="project_desc">
          <NInput v-model:value="modalForm.project_desc" type="textarea" placeholder="请输入应用描述" />
        </NFormItem>
        <NFormItem label="开发负责人" path="project_dev_owners">
          <NInput v-model:value="modalForm.project_dev_owners" type="textarea" placeholder="请输入负责人名，多人时请用英文逗号分隔" />
        </NFormItem>
        <NFormItem label="测试负责人" path="project_test_owners">
          <NInput v-model:value="modalForm.project_test_owners" type="textarea" placeholder="请输入负责人名，多人时请用英文逗号分隔" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
