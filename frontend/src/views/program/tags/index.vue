<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NInput, NPopconfirm, NSelect } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '标签管理' })

const $table = ref(null)
const queryItems = ref({ tag_project: null, tag_name: '', tag_type: null })
const projectOptions = ref([])
const tagTypeOptions = [
  { label: '接口', value: '接口' },
  { label: '脚本', value: '脚本' },
]
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
    tag_type: '脚本',
    tag_project: null,
    tag_mode: '',
    tag_name: '',
    tag_desc: '',
  },
  doCreate: (form) => api.createTag({
    tag_type: form.tag_type,
    tag_project: form.tag_project,
    tag_mode: form.tag_mode,
    tag_name: form.tag_name,
    tag_desc: form.tag_desc || undefined,
  }),
  doDelete: (params) => api.deleteTag(params),
  doUpdate: (form) => api.updateTag({
    tag_id: form.tag_id,
    tag_code: form.tag_code,
    tag_type: form.tag_type,
    tag_project: form.tag_project,
    tag_mode: form.tag_mode,
    tag_name: form.tag_name,
    tag_desc: form.tag_desc || undefined,
  }),
  refresh: () => $table.value?.handleSearch(),
})

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    tag_project: queryItems.value.tag_project || undefined,
    tag_name: queryItems.value.tag_name || undefined,
    tag_type: queryItems.value.tag_type || undefined,
    ...overrides,
  }
}

onMounted(async () => {
  try {
    const res = await api.getProjectList({ page: 1, page_size: 9999, state: 0 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name || p.project_code, value: p.project_id }))
  } catch (_) {}
  // 进入页面不自动请求表格数据，由用户点击「搜索」按钮时再请求
  // $table.value?.handleSearch()
})

const columns = [
  { title: '标签ID', key: 'tag_id', width: 80, align: 'center' },
  { title: '标签代码', key: 'tag_code', align: 'center', ellipsis: { tooltip: true } },
  { title: '标签类型', key: 'tag_type', align: 'center' },
  { title: '所属应用', key: 'tag_project', align: 'center' },
  { title: '标签大类', key: 'tag_mode', align: 'center', ellipsis: { tooltip: true } },
  { title: '标签名称', key: 'tag_name', align: 'center', ellipsis: { tooltip: true } },
  { title: '标签描述', key: 'tag_desc', align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 100,
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
                  onClick: () => handleEdit(row),
                },
                { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NPopconfirm,
            { onPositiveClick: () => handleDelete({ tag_id: row.tag_id }, false) },
            {
              trigger: () =>
                  withDirectives(
                      h(NButton, { size: 'small', type: 'error', style: 'margin-right: 8px;' }, {
                        default: () => '删除',
                        icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                      }),
                      [[vPermission, 'delete/api/v1/role/delete']]
                  ),
              default: () => h('div', {}, '确定删除该标签吗?'),
            }
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage show-footer title="标签列表">
    <template #action>
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="handleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新建标签
      </NButton>
    </template>

    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="true"
        :remote="true"
        :scroll-x="1200"
        :columns="columns"
        :get-data="(params) => api.getTagList(buildSearchBody(params))"
        row-key="tag_id"
    >
      <template #queryBar>
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.tag_project"
              :options="projectOptions"
              clearable
              placeholder="请选择应用"
              style="width: 180px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="标签类型：">
          <NSelect
              v-model:value="queryItems.tag_type"
              :options="tagTypeOptions"
              clearable
              placeholder="请选择类型"
              style="width: 120px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="标签名称：">
          <NInput
              v-model:value="queryItems.tag_name"
              clearable
              placeholder="请输入标签名称"
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
          :label-width="100"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem v-if="modalAction === 'edit'" label="标签ID" path="tag_id">
          <NInput v-model:value="modalForm.tag_id" disabled />
        </NFormItem>
        <NFormItem
            label="标签类型"
            path="tag_type"
            :rule="{ required: true, message: '请选择标签类型', trigger: ['change', 'blur'] }"
        >
          <NSelect v-model:value="modalForm.tag_type" :options="tagTypeOptions" placeholder="请选择类型" />
        </NFormItem>
        <NFormItem
            label="所属应用"
            path="tag_project"
            :rule="{ required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] }"
        >
          <NSelect
              v-model:value="modalForm.tag_project"
              :options="projectOptions"
              placeholder="请选择应用"
              :disabled="modalAction === 'edit'"
          />
        </NFormItem>
        <NFormItem
            label="标签大类"
            path="tag_mode"
            :rule="{ required: true, message: '请输入标签大类', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.tag_mode" placeholder="如：冒烟、回归" />
        </NFormItem>
        <NFormItem
            label="标签名称"
            path="tag_name"
            :rule="{ required: true, message: '请输入标签名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.tag_name" placeholder="请输入标签名称" />
        </NFormItem>
        <NFormItem label="标签描述" path="tag_desc">
          <NInput v-model:value="modalForm.tag_desc" type="textarea" placeholder="请输入标签描述" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
