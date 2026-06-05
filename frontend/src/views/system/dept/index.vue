<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {NButton, NForm, NFormItem, NInput, NInputNumber, NPopconfirm, NTag, NTreeSelect} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, formatDateTime, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: '部门管理' })

const $table = ref(null)
const queryItems = ref({ name: '' })
const vPermission = resolveDirective('permission')

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

function fetchDeptList(params) {
  const p = { ...params }
  const nm = p.name != null ? String(p.name).trim() : ''
  if (nm) p.name = nm
  else delete p.name
  return api.getDepts(p).then((res) => {
    const list = res.data || []
    return {
      data: list,
      total: res.total ?? (Array.isArray(list) ? list.length : 0),
    }
  })
}

const initForm = {
  parent_id: 0,
  code: '',
  name: '',
  description: '',
  order: 0,
}

const {
  modalVisible,
  modalTitle,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: '部门',
  initForm,
  doCreate: api.createDept,
  doUpdate: api.updateDept,
  doDelete: api.deleteDept,
  refresh: () => {
    $table.value?.handleSearch()
    getTreeSelect()
  },
})

const deptTree = ref([])
const isDisabled = ref(false)

/** 父级下拉：仅允许选择根目录或顶级部门（最多两级） */
const parentDeptOptions = computed(() => {
  const root = { id: 0, name: '根目录', children: [] }
  root.children = (deptTree.value || []).map(({ id, name }) => ({ id, name }))
  return [root]
})

onMounted(() => {
  getTreeSelect()
  $table.value?.handleSearch()
})

const deptRules = {
  name: [
    {
      required: true,
      message: '请输入部门名称',
      trigger: ['input', 'blur', 'change'],
    },
  ],
}

function handleClickAdd() {
  isDisabled.value = true
  initForm.parent_id = 0
  handleAdd()
}

async function getTreeSelect() {
  const { data } = await api.getDepts()
  deptTree.value = data || []
}

const columns = [
  {
    title: 'ID',
    key: 'id',
    width: 100,
    ellipsis: { tooltip: true },
    align: 'center'
  },
  {
    title: '部门代码',
    key: 'code',
    width: 100,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return h(NTag, { type: 'info' }, { default: () => row.code })
    },
  },
  {
    title: '排序',
    key: 'order',
    width: 100,
    ellipsis: { tooltip: true },
    align: 'center'
  },
  {
    title: '部门名称',
    key: 'name',
    width: 200,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return h(NTag, { type: 'info' }, { default: () => row.name })
    },
  },
  {
    title: '部门描述',
    key: 'description',
    width: 300,
    ellipsis: { tooltip: true },
    align: 'center'
  },
  {
    title: '创建日期',
    key: 'created_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time))
    },
  },
  {
    title: '更新日期',
    key: 'updated_time',
    width: 180,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
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
                  type: 'primary',
                  style: `display: ${row.parent_id === 0 ? '' : 'none'};`,
                  onClick: () => {
                    initForm.parent_id = row.id
                    isDisabled.value = true
                    handleAdd()
                  },
                },
                { default: () => '子部门', icon: renderIcon('material-symbols:add', { size: 16 }) }
            ),
            [[vPermission, apiPermissionKey('post', '/dept/create')]]
        ),
        withDirectives(
            h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'info',
                  onClick: () => {
                    if (row.parent_id === 0) {
                      isDisabled.value = true
                    } else {
                      isDisabled.value = false
                    }
                    handleEdit(row)
                  },
                },
                {
                  default: () => '编辑',
                  icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                }
            ),
            [[vPermission, apiPermissionKey('post', '/dept/update')]]
        ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({ department_id: row.id }, false),
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
                            style: `display: ${row.children && row.children.length > 0 ? 'none' : ''};`,
                          },
                          {
                            default: () => '删除',
                            icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                          }
                      ),
                      [[vPermission, apiPermissionKey('delete', '/dept/delete')]]
                  ),
              default: () => h('div', {}, '确定删除该部门吗?'),
            }
        ),
      ]
    },
  },
]
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer title="部门列表">
    <!-- 表格 -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="fetchDeptList"
        :single-line="true"
        :scroll-x="1200"
        row-key="id"
        @query-bar-create="handleClickAdd"
    >
      <template #queryBar>
        <QueryBarItem label="部门名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              placeholder="请输入部门名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <!-- 新增/编辑 弹窗 -->
    <CrudModal
        v-model:visible="modalVisible"
        :title="modalTitle"
        :loading="modalLoading"
        @save="handleSave(getTreeSelect)"
    >
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="80"
          :model="modalForm"
          :rules="deptRules">
        <NFormItem label="父级部门" path="parent_id">
          <NTreeSelect
              v-model:value="modalForm.parent_id"
              :options="parentDeptOptions"
              key-field="id"
              label-field="name"
              placeholder="请选择父级部门"
              :default-expand-all="true"
              :disabled="isDisabled"/>
        </NFormItem>
        <NFormItem label="部门代码" path="code">
          <NInput v-model:value="modalForm.code" clearable placeholder="请输入部门名称" />
        </NFormItem>
        <NFormItem label="部门名称" path="name">
          <NInput v-model:value="modalForm.name" clearable placeholder="请输入部门名称" />
        </NFormItem>
        <NFormItem label="部门描述" path="description">
          <NInput v-model:value="modalForm.description" type="textarea" clearable />
        </NFormItem>
        <NFormItem label="排序权重" path="order">
          <NInputNumber v-model:value="modalForm.order" min="0"></NInputNumber>
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
