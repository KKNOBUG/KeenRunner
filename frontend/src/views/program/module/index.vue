<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {NButton, NForm, NFormItem, NInput, NPopconfirm, NTag, NTooltip, NTreeSelect} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDate, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({name: '模块管理'})

const $table = ref(null)
const queryItems = ref({})
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
  name: '模块',
  initForm: {},
  doCreate: api.createModule,
  doDelete: api.deleteModule,
  doUpdate: api.updateModule,
  refresh: () => $table.value?.handleSearch(),
})

const pattern = ref('')
const active = ref(false)
const ownerOption = ref([])

onMounted(() => {
  $table.value?.handleSearch()
  api.getUserList().then((res) => (ownerOption.value = res.data))

})

const columns = [
  {
    title: '项目名称',
    key: 'project.name',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '项目状态',
    key: 'state',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(NTag, {type: 'primary'}, {
            default: () => {
              if (row.project.state === 1) {
                return '开发'
              } else if (row.project.state === 2) {
                return '延期'
              } else if (row.project.state === 3) {
                return '交付'
              } else if (row.project.state === 4) {
                return '完成'
              }
            }
          }
      )
    },
  },
  {
    title: '模块代码',
    key: 'code',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '模块名称',
    key: 'name',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '模块开发负责人',
    key: 'dev_owner',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(
          NTooltip,
          {trigger: "hover"},
          {
            trigger: () => h(
                'span',
                {style: {margin: '2px 3px', cursor: 'pointer'}},
                row.dev_owner.alias
            ),
            default: () => `工号: ${row.dev_owner.username}, 名称: ${row.dev_owner.alias}, 电话: ${row.dev_owner.phone}, 邮箱: ${row.test_owner.email}`
          },
      )
    },
  },
  {
    title: '模块测试负责人',
    key: 'test_owner',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(
          NTooltip,
          {trigger: "hover"},
          {
            trigger: () => h(
                'span',
                {style: {margin: '2px 3px', cursor: 'pointer'}},
                row.test_owner.alias
            ),
            default: () => `工号: ${row.test_owner.username}, 名称: ${row.test_owner.alias}, 电话: ${row.test_owner.phone}, 邮箱: ${row.test_owner.email}`
          },
      )
    },
  },
  {
    title: '模块描述',
    key: 'description',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 150,
    align: 'center',
    render(row) {
      return h('span', formatDate(row.created_time))
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 150,
    align: 'center',
    render(row) {
      return h('span', formatDate(row.updated_time))
    },
  },
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
                  onClick: () => {
                    handleEdit(row)
                    modalForm.value.test_owner = row.test_owner?.id
                    modalForm.value.dev_owner = row.dev_owner?.id
                    modalForm.value.project = row.project?.id
                    modalForm.value.state = row.state
                  },
                },
                {
                  default: () => '编辑',
                  icon: renderIcon('material-symbols:edit-outline', {size: 16}),
                }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({module_id: row.id}, false),
              onNegativeClick: () => {
              },
            },
            {
              trigger: () =>
                  withDirectives(
                      h(
                          NButton,
                          {
                            size: 'small',
                            type: 'error',
                            style: 'margin-right: 8px;',
                          },
                          {
                            default: () => '删除',
                            icon: renderIcon('material-symbols:delete-outline', {size: 16}),
                          }
                      ),
                      [[vPermission, 'delete/api/v1/role/delete']]
                  ),
              default: () => h('div', {}, '确定删除该项目吗?'),
            }
        ),
      ]
    },
  },
]

const stateOptions = [
  {label: '开发', value: 1},
  {label: '延期', value: 2},
  {label: '交付', value: 3},
  {label: '完成', value: 4},
]

const renderOptionLabel = (option) => {
  const innerOption = option.option
  return `工号: ${innerOption.username}, 名称: ${innerOption.alias}, 电话: ${innerOption.phone}, 邮箱: ${innerOption.email}`
}

</script>

<template>
  <CommonPage show-footer title="模块列表">
    <template #action>
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="handleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5"/>
        新建模块
      </NButton>
    </template>

    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="false"
        :columns="columns"
        :get-data="api.getModuleList"
        :single-line="true"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="项目名称：" :label-width="100">
          <NInput
              v-model:value="queryItems.project_name"
              clearable
              type="text"
              placeholder="请输入项目名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="项目状态：" :label-width="100">
          <NSelect
              v-model:value="queryItems.project_state"
              :options="stateOptions"
              clearable
              placeholder="请选择项目状态"
              style="width: 200px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="模块名称：" :label-width="100">
          <NInput
              v-model:value="queryItems.name"
              clearable
              type="text"
              placeholder="请输入项目名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="模块开发人：" :label-width="100">
          <NInput
              v-model:value="queryItems.dev_owner_name"
              clearable
              type="text"
              placeholder="请输入模块开发负责人"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="模块测试人：" :label-width="100">
          <NInput
              v-model:value="queryItems.test_owner_name"
              clearable
              type="text"
              placeholder="请输入模块测试负责人"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>

    </CrudTable>

    <!--  新建&编辑项目弹窗  -->
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
          :label-width="100"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem
            label="模块代码"
            path="code"
            :rule="{
            required: true,
            message: '请输入模块代码',
            trigger: ['input', 'blur'],
          }"
        >
          <NInput v-model:value="modalForm.code" placeholder="请输入模块代码"/>
        </NFormItem>
        <NFormItem
            label="模块名称"
            path="name"
            :rule="{
            required: true,
            message: '请输入模块名称',
            trigger: ['input', 'blur'],
          }"
        >
          <NInput v-model:value="modalForm.name" placeholder="请输入模块名称"/>
        </NFormItem>


        <NFormItem label="模块描述" path="description">
          <NInput v-model:value="modalForm.description" type="textarea" placeholder="请输入模块描述"/>
        </NFormItem>

        <NFormItem
            label="模块开发人"
            path="dev_owner"
            :rule="{
              required: true,
              type: 'number',
              message: '请选择模块开发负责人',
              trigger: ['input', 'blur'],
            }"
        >
          <NTreeSelect
              v-model:value="modalForm.dev_owner"
              :options="ownerOption"
              key-field="id"
              label-field="alias"
              value-field="id"
              :render-label="renderOptionLabel"
              placeholder="请选择模块开发负责人"
              clearable
              filterable
          />
        </NFormItem>
        <NFormItem
            label="模块测试人"
            path="test_owner"
            :rule="{
                required: true,
                type: 'number',
                message: '请选择模块测试负责人',
                trigger: ['input', 'blur', 'change'],
              }"
        >
          <NTreeSelect
              v-model:value="modalForm.test_owner"
              :options="ownerOption"
              key-field="id"
              label-field="alias"
              value-field="id"
              :render-label="renderOptionLabel"
              placeholder="请选择模块测试负责人"
              clearable
              filterable
          />
        </NFormItem>
      </NForm>
    </CrudModal>

  </CommonPage>
</template>


<style scoped>
.env-fields {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.field {
  width: 100%;
}

:deep(.n-collapse-item__header) {
  padding: 12px;
}

</style>
