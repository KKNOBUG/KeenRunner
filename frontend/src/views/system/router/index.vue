<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
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

const checkedRowKeys = ref([])
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'dropdown',
}

async function handleBatchDelete() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    $message.warning('请先勾选要删除的 API')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条 API 吗？`,
    async confirm() {
      await Promise.all(ids.map((router_id) => api.deleteRouter({ router_id })))
      $message.success('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
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
      title: '路由所属模块',
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
      title: '路由作用简介',
      key: 'summary',
      width: 'auto',
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '路由请求路径',
      key: 'path',
      width: 'auto',
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '路由请求方式',
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
      title: '路由功能描述',
      key: 'description',
      width: 'auto',
      align: 'center',
      ellipsis: { tooltip: true },
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
                    onClick: () => {
                      handleEdit(row)
                      modalForm.value.roles = (row.roles || []).map((e) => (typeof e === 'object' && e != null ? e.id : e))
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
                onPositiveClick: () => handleDelete({ router_id: row.id }),
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
                        [[vPermission, 'delete/api/v1/router/delete']]
                    ),
                default: () => h('div', {}, '确定删除该API吗?'),
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
  <CommonPage show-footer title="API列表">
    <!-- 表格 -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :single-line="true"
        :scroll-x="1620"
        :columns="columns"
        :get-data="api.getRouters"
        row-key="id"
        @query-bar-create="handleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="API简介：">
          <NInput
              v-model:value="queryItems.summary"
              clearable
              type="text"
              placeholder="请输入API简介"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="API路径：">
          <NInput
              v-model:value="queryItems.path"
              clearable
              type="text"
              placeholder="请输入API路径"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="API标签：">
          <NInput
              v-model:value="queryItems.tags"
              clearable
              type="text"
              placeholder="请输入API标签"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
      <!-- 与 QueryBar「操作」下拉同一行，紧跟其后 -->
      <template #queryBarAfterActions>
        <NButton
            v-permission="'post/api/v1/router/refresh'"
            size="small"
            type="warning"
            secondary
            @click="handleRefreshRouter"
        >
          <TheIcon icon="material-symbols:refresh" :size="16" class="mr-5" />刷新API
        </NButton>
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
