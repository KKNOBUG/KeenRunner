<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {NButton, NForm, NFormItem, NInput, NInputNumber, NPopconfirm, NTag, NTreeSelect} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
// import { loginTypeMap, loginTypeOptions } from '@/constant/data'
import api from '@/api'

defineOptions({ name: '部门管理' })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

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
  name: 'API',
  initForm: { order: 0 },
  doCreate: api.createDept,
  doUpdate: api.updateDept,
  doDelete: api.deleteDept,
  refresh: () => $table.value?.handleSearch(),
})

const deptOption = ref([])
const isDisabled = ref(false)

onMounted(() => {
  $table.value?.handleSearch()
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

const columns = [
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
    width: 'auto',
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
              style: 'margin-left: 8px;',
              onClick: () => {
                console.log('row', row.parent_id)
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
                    size: 'small',
                    type: 'error',
                    style: 'margin-left: 8px;',
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
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer title="部门列表">
    <template #action>
      <div>
        <NButton
          v-permission="'post/api/v1/dept/create'"
          class="float-right mr-15"
          type="primary"
          @click="addDepts"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建部门
        </NButton>
      </div>
    </template>
    <!-- 表格 -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getDepts"
    >
      <!--   搜索狂   -->
      <template #queryBar>
        <QueryBarItem label="部门名称" :label-width="80">
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
