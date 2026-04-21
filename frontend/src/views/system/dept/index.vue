<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {NButton, NForm, NFormItem, NInput, NInputNumber, NPopconfirm, NTag, NTreeSelect} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
// import { loginTypeMap, loginTypeOptions } from '@/constant/data'
import api from '@/api'

defineOptions({ name: '部门管理' })

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({ name: '' })
const vPermission = resolveDirective('permission')

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
    $message.warning('请先勾选要删除的部门')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 个部门吗？`,
    async confirm() {
      await api.deleteDeptBatch({ department_ids: ids })
      $message.success('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
      api.getDepts().then((res) => (deptOption.value = res.data))
    },
  })
}

function buildDeptSearch(overrides = {}) {
  const q = queryItems.value
  return {
    ...overrides,
    name: (overrides.name ?? q.name) || undefined,
    order: overrides.order?.length ? overrides.order : ['id'],
  }
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
  initForm: {
    parent_id: 0,
    code: '',
    name: '',
    description: '',
    order: 0,
  },
  doCreate: api.createDept,
  doUpdate: api.updateDept,
  doDelete: api.deleteDept,
  refresh: () => {
    $table.value?.handleSearch()
    api.getDepts().then((res) => (deptOption.value = res.data))
  },
})

const deptOption = ref([])
const isDisabled = ref(false)

onMounted(() => {
  // 仅加载父级下拉树数据；表格列表等用户点击「搜索」后再请求
  // $table.value?.handleSearch()
  api.getDepts().then((res) => (deptOption.value = res.data))
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

async function addDepts() {
  isDisabled.value = false
  handleAdd()
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
      title: '部门代码',
      key: 'code',
      width: 'auto',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h(
            NTag,
            {type: 'info', style: {margin: '2px 3px'}},
            {default: () => row.code}
        )
      },
    },
    {
      title: '部门名称',
      key: 'name',
      width: 'auto',
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return h(
            NTag,
            {type: 'info', style: {margin: '2px 3px'}},
            {default: () => row.name}
        )
      },
    },
    {
      title: '部门描述',
      key: 'description',
      align: 'center',
      width: 'auto',
      ellipsis: { tooltip: true },
    },
    {
      title: '创建时间',
      key: 'created_time',
      align: 'center',
      width: 'auto',
      ellipsis: { tooltip: true },
    },
    {
      title: '维护时间',
      key: 'updated_time',
      align: 'center',
      width: 'auto',
      ellipsis: { tooltip: true },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
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
                    icon: renderIcon('material-symbols:edit', { size: 16 }),
                  }
              ),
              [[vPermission, 'post/api/v1/dept/update']]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({ department_id: row.id }, false),
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
                        [[vPermission, 'delete/api/v1/dept/delete']]
                    ),
                default: () => h('div', {}, '确定删除该部门吗?'),
              }
          ),
        ]
      },
    },
  ]
})
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer title="部门列表">
    <!-- 表格 -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="(params) => api.searchDeptList(buildDeptSearch(params))"
        :scroll-x="1100"
        row-key="id"
        @query-bar-create="addDepts"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <!--   搜索狂   -->
      <template #queryBar>
        <QueryBarItem label="部门名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              type="text"
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
        @save="handleSave"
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
              :options="deptOption"
              key-field="id"
              label-field="name"
              placeholder="请选择父级部门"
              clearable
              default-expand-all
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
