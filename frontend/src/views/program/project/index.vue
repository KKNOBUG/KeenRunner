<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NInput, NPopconfirm, NTag, NTooltip } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { formatDate, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '项目管理' })

const $table = ref(null)
const queryItems = ref({ project_code: '', project_state: '' })
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
    const payload = {
      project_id: form.project_id,
      project_code: form.project_code || undefined,
      project_name: form.project_name,
      project_desc: form.project_desc || undefined,
      project_state: form.project_state || undefined,
      project_phase: form.project_phase || undefined,
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

onMounted(() => {
  $table.value?.handleSearch()
})

function buildSearchBody() {
  return {
    page: 1,
    page_size: 9999,
    state: 0,
    project_code: queryItems.value.project_code || undefined,
    project_state: queryItems.value.project_state || undefined,
  }
}

const columns = [
  {
    title: '应用代码',
    key: 'project_code',
    width: 120,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '应用名称',
    key: 'project_name',
    width: 150,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '应用状态',
    key: 'project_state',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '应用阶段',
    key: 'project_phase',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '开发组长',
    key: 'project_dev_owners',
    width: 120,
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
    width: 120,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const v = row.project_developers
      if (!v || !v.length) return '-'
      return Array.isArray(v) ? v.join(', ') : String(v)
    },
  },
  {
    title: '测试组长',
    key: 'project_test_owners',
    width: 120,
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
    width: 120,
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
    width: 160,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
            h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  style: 'margin-right: 8px;',
                  onClick: () => customHandleEdit(row),
                },
                { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({ project_id: row.project_id }, false),
            },
            {
              trigger: () =>
                  withDirectives(
                      h(NButton, { size: 'small', type: 'error', style: 'margin-right: 8px;' }, {
                        default: () => '删除',
                        icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                      }),
                      [[vPermission, 'delete/api/v1/role/delete']]
                  ),
              default: () => h('div', {}, '确定删除该应用吗?'),
            }
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage show-footer title="应用列表">
    <template #action>
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="handleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新建应用
      </NButton>
    </template>

    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="false"
        :columns="columns"
        :get-data="(params) => api.getProjectList(buildSearchBody())"
        :single-line="true"
        row-key="project_id"
    >
      <template #queryBar>
        <QueryBarItem label="应用代码：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_code"
              clearable
              placeholder="请输入应用代码"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="应用状态：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_state"
              clearable
              placeholder="请输入应用状态"
              style="width: 160px"
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
          <NInput v-model:value="modalForm.project_dev_owners" placeholder="多人用英文逗号分隔" />
        </NFormItem>
        <NFormItem label="测试负责人" path="project_test_owners">
          <NInput v-model:value="modalForm.project_test_owners" placeholder="多人用英文逗号分隔" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
