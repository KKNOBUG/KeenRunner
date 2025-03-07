<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {NButton, NForm, NFormItem, NInput, NPopconfirm, NTag} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
// import { loginTypeMap, loginTypeOptions } from '@/constant/data'
import api from '@/api'

defineOptions({ name: 'API管理' })

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
  initForm: {},
  doCreate: api.createRouter,
  doUpdate: api.updateRouter,
  doDelete: api.deleteRouter,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
})

async function handleRefreshRouter() {
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: '此操作会根据后端 app.routes 进行路由更新，确定继续刷新 API 操作？',
    async confirm() {
      await api.refreshRouter()
      $message.success('刷新完成')
      $table.value?.handleSearch()
    },
  })
}

const addAPIRules = {
  path: [
    {
      required: true,
      message: '请输入API路径',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  method: [
    {
      required: true,
      message: '请输入方式',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  summary: [
    {
      required: true,
      message: '请输入API简介',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  tags: [
    {
      required: true,
      message: '请输入API标签',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  description: [
    {
      required: false,
      message: '请输入API描述',
      trigger: ['input', 'blur', 'change'],
    },
  ],
}

const columns = [
  {
    title: 'API简介',
    key: 'summary',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: 'API路径',
    key: 'path',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: 'API方式',
    key: 'method',
    align: 'center',
    width: 'auto',
    ellipsis: { tooltip: true },
    render(row) {
      return h(
          NTag,
          {type: 'info', style: {margin: '2px 3px'}},
          {default: () => row.method}
      )
    },
  },
  {
    title: 'API标签',
    key: 'tags',
    width: 'auto',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return h(
          NTag,
          {type: 'info', style: {margin: '2px 3px'}},
          {default: () => row.tags}
      )
    },
  },
  {
    title: 'API描述',
    key: 'description',
    width: 'auto',
    align: 'center',
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
              style: 'margin-right: 8px;',
              onClick: () => {
                handleEdit(row)
                modalForm.value.roles = row.roles.map((e) => (e = e.id))
              },
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit', { size: 16 }),
            }
          ),
          [[vPermission, 'post/api/v1/router/update']]
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete({ api_id: row.id }, false),
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
                    style: 'margin-right: 8px;',
                  },
                  {
                    default: () => '删除',
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  }
                ),
                [[vPermission, 'delete/api/v1/router/delete']]
              ),
            default: () => h('div', {}, '确定删除该API吗?'),
          }
        ),
      ]
    },
  },
]
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer title="API列表">
    <template #action>
      <div>
        <NButton
          v-permission="'post/api/v1/router/create'"
          class="float-right mr-15"
          type="primary"
          @click="handleAdd"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建API
        </NButton>
        <NButton
          v-permission="'post/api/v1/router/refresh'"
          class="float-right mr-15"
          type="warning"
          @click="handleRefreshRouter"
        >
          <TheIcon icon="material-symbols:refresh" :size="18" class="mr-5" />刷新API
        </NButton>
      </div>
    </template>
    <!-- 表格 -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getRouters"
    >
      <template #queryBar>
        <QueryBarItem label="API简介" :label-width="auto">
          <NInput
              v-model:value="queryItems.summary"
              clearable
              type="text"
              placeholder="请输入API简介"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="API路径" :label-width="auto">
          <NInput
            v-model:value="queryItems.path"
            clearable
            type="text"
            placeholder="请输入API路径"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="API标签" :label-width="auto">
          <NInput
            v-model:value="queryItems.tags"
            clearable
            type="text"
            placeholder="请输入API标签"
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
      @save="handleSave">
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="80"
        :model="modalForm"
        :rules="addAPIRules">
        <NFormItem label="API简介" path="summary">
          <NInput v-model:value="modalForm.summary" clearable placeholder="请输入API简介" />
        </NFormItem>
        <NFormItem label="API路径" path="path">
          <NInput v-model:value="modalForm.path" clearable placeholder="请输入API路径" />
        </NFormItem>
        <NFormItem label="API方式" path="method">
          <NInput v-model:value="modalForm.method" clearable placeholder="请输入API请求方式" />
        </NFormItem>
        <NFormItem label="API标签" path="tags">
          <NInput v-model:value="modalForm.tags" clearable placeholder="请输入API标签" />
        </NFormItem>
        <NFormItem label="API描述" path="description">
          <NInput v-model:value="modalForm.description" clearable placeholder="请输入API描述" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
