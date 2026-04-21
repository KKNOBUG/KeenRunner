<script setup>
import {computed, h, ref, resolveDirective, withDirectives} from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NGi,
  NGrid,
  NInput,
  NPopconfirm,
  NTabPane,
  NTabs,
  NTag,
  NTree,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDate, formatDateTime, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'

defineOptions({name: '角色管理'})

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
    $message.warning('请先勾选要删除的角色')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 个角色吗？`,
    async confirm() {
      await api.deleteRoleBatch({ role_ids: ids })
      $message.success('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

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
  name: '角色',
  initForm: {},
  doCreate: api.createRole,
  doDelete: api.deleteRole,
  doUpdate: api.updateRole,
  refresh: () => $table.value?.handleSearch(),
})

const pattern = ref('')
const menuOption = ref([]) // 菜单选项
const active = ref(false)
const menu_ids = ref([])
const role_id = ref(0)
const apiOption = ref([])
const api_ids = ref([])
/** 接口权限 NTree 实例，用于 getCheckedData */
const apiTreeRef = ref(null)

function buildApiTree(data) {
  const processedData = []
  const groupedData = {}

  data.forEach((item) => {
    const tags = item['tags'] || ''
    const pathParts = (item['path'] || '').split('/')
    const path = pathParts.slice(0, -1).join('/')
    const summary = tags ? tags.charAt(0).toUpperCase() + tags.slice(1) : (item['path'] || 'API')
    const unique_id = item['method'].toLowerCase() + item['path']
    if (!(path in groupedData)) {
      groupedData[path] = {unique_id: path, path: path, summary: summary, children: []}
    }

    groupedData[path].children.push({
      id: item['id'],
      path: item['path'],
      method: item['method'],
      summary: item['summary'],
      unique_id: unique_id,
    })
  })
  processedData.push(...Object.values(groupedData))
  return processedData
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
      title: '角色代码',
      key: 'code',
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        return h(NTag, {type: 'info'}, {default: () => row.code})
      },
    },
    {
      title: '角色名称',
      key: 'name',
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        return h(NTag, {type: 'info'}, {default: () => row.name})
      },
    },
    {
      title: '角色描述',
      key: 'description',
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '创建人员',
      key: 'created_user',
      align: 'center',
      ellipsis: {tooltip: true}
    },
    {
      title: '更新人员',
      key: 'updated_user',
      align: 'center',
      ellipsis: {tooltip: true}
    },
    {
      title: '创建时间',
      key: 'created_time',
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.created_time))
      },
    },
    {
      title: '更新时间',
      key: 'updated_time',
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.updated_time))
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
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
                    },
                  },
                  {
                    default: () => '编辑',
                    icon: renderIcon('material-symbols:edit-outline', {size: 16}),
                  }
              ),
              [[vPermission, 'post/api/v1/role/update']]
          ),
          withDirectives(
              h(
                  NButton,
                  {
                    size: 'tiny',
                    quaternary: true,
                    type: 'primary',
                    onClick: async () => {
                      try {
                        // 使用 Promise.all 来同时发送所有请求
                        const [menusResponse, apisResponse, roleAuthorizedResponse] = await Promise.all([
                          api.getMenus({ page: 1, page_size: 9999 }),
                          api.getRouters({ page: 1, page_size: 9999 }),
                          api.getRoleAuthorized({ id: row.id }),
                        ])

                        const authPayload = roleAuthorizedResponse.data || {}
                        // 后端 to_dict(m2m=True) 字段名为 menus / routers，不是 apis
                        menuOption.value = menusResponse.data || []
                        apiOption.value = buildApiTree(apisResponse.data || [])
                        menu_ids.value = (authPayload.menus || []).map((v) => v.id)
                        api_ids.value = (authPayload.routers || []).map((v) => {
                          const m = String(v.method ?? '').toLowerCase()
                          const p = v.path ?? ''
                          return m + p
                        })

                        active.value = true
                        role_id.value = row.id
                      } catch (error) {
                        console.error('Error loading data:', error)
                        $message?.error?.(error?.message || '加载权限数据失败')
                      }
                    },
                  },
                  {
                    default: () => '权限',
                    icon: renderIcon('material-symbols:edit-outline', {size: 16}),
                  }
              ),
              [[vPermission, 'get/api/v1/role/authorized']]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({role_id: row.id}, false),
                onNegativeClick: () => {
                },
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
                              icon: renderIcon('material-symbols:delete-outline', {size: 16}),
                            }
                        ),
                        [[vPermission, 'delete/api/v1/role/delete']]
                    ),
                default: () => h('div', {}, '确定删除该角色吗?'),
              }
          ),
        ]
      },
    },
  ]
})

async function updateRoleAuthorized() {
  const treeInst = apiTreeRef.value
  if (!treeInst?.getCheckedData) {
    $message?.warning?.('接口树未就绪，请稍后再试')
    return
  }
  const checkData = treeInst.getCheckedData()
  const router_infos = []
  checkData?.options?.forEach((item) => {
    if (!item.children) {
      router_infos.push({
        path: item.path,
        method: item.method,
      })
    }
  })
  try {
    await api.updateRoleAuthorized({
      id: role_id.value,
      menu_ids: menu_ids.value,
      router_infos,
    })
    $message?.success?.('设置成功')
    const result = await api.getRoleAuthorized({ id: role_id.value })
    const payload = result.data || {}
    menu_ids.value = (payload.menus || []).map((v) => v.id)
    api_ids.value = (payload.routers || []).map((v) => {
      const m = String(v.method ?? '').toLowerCase()
      const p = v.path ?? ''
      return m + p
    })
  } catch (e) {
    $message?.error?.(e?.message || '保存失败')
  }
}
</script>

<template>
  <CommonPage show-footer title="角色列表">
    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="api.getRoleList"
        :single-line="true"
        :scroll-x="1320"
        row-key="id"
        @query-bar-create="handleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="角色名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              type="text"
              placeholder="请输入角色名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>

    </CrudTable>

    <!--  新建&编辑角色弹窗  -->
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
          :disabled="modalAction === 'view'"
      >
        <NFormItem
            label="角色代码"
            path="code"
            :rule="{
            required: true,
            message: '请输入角色代码',
            trigger: ['input', 'blur'],
          }"
        >
          <NInput v-model:value="modalForm.code" placeholder="请输入角色代码"/>
        </NFormItem>
        <NFormItem
            label="角色名称"
            path="name"
            :rule="{
            required: true,
            message: '请输入角色名称',
            trigger: ['input', 'blur'],
          }"
        >
          <NInput v-model:value="modalForm.name" placeholder="请输入角色名称"/>
        </NFormItem>
        <NFormItem label="角色描述" path="description">
          <NInput v-model:value="modalForm.description" placeholder="请输入角色描述"/>
        </NFormItem>
      </NForm>
    </CrudModal>

    <!--  设置权限弹窗  -->
    <NDrawer v-model:show="active" placement="right" :width="500">
      <NDrawerContent>
        <NGrid x-gap="24" cols="12">
          <NGi span="8">
            <NInput
                v-model:value="pattern"
                type="text"
                placeholder="筛选"
                style="flex-grow: 1"/>
          </NGi>
          <NGi offset="2">
            <NButton
                v-permission="'post/api/v1/role/authorized'"
                type="info"
                @click="updateRoleAuthorized">
              确定
            </NButton>
          </NGi>
        </NGrid>
        <NTabs>
          <NTabPane name="menu" tab="菜单权限" display-directive="show">
            <NTree
                :data="menuOption"
                :checked-keys="menu_ids"
                :pattern="pattern"
                :show-irrelevant-nodes="false"
                key-field="id"
                label-field="name"
                checkable
                :default-expand-all="true"
                :block-line="true"
                :selectable="false"
                @update:checked-keys="(v) => (menu_ids = v)"
            />
          </NTabPane>
          <NTabPane name="resource" tab="接口权限" display-directive="show">
            <NTree
                ref="apiTreeRef"
                :data="apiOption"
                :checked-keys="api_ids"
                :pattern="pattern"
                :show-irrelevant-nodes="false"
                key-field="unique_id"
                label-field="summary"
                checkable
                :default-expand-all="true"
                :block-line="true"
                :selectable="false"
                cascade
                @update:checked-keys="(v) => (api_ids = v)"
            />
          </NTabPane>
        </NTabs>
        <template #header> 设置权限</template>
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>
