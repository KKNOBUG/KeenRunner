<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
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

import {formatDate, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({name: '角色管理'})

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
const apiTree = ref([])

function buildApiTree(data) {
  const processedData = []
  const groupedData = {}

  data.forEach((item) => {
    const tags = item['tags']
    const pathParts = item['path'].split('/')
    const path = pathParts.slice(0, -1).join('/')
    const summary = tags.charAt(0).toUpperCase() + tags.slice(1)
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

onMounted(() => {
  $table.value?.handleSearch()
})

const columns = [
  {
    title: '角色代码',
    key: 'code',
    width: 80,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(NTag, {type: 'info'}, {default: () => row.code})
    },
  },
  {
    title: '角色名称',
    key: 'name',
    width: 80,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(NTag, {type: 'info'}, {default: () => row.name})
    },
  },
  {
    title: '角色描述',
    key: 'description',
    width: 200,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      return h(NTag, {type: 'info'}, {default: () => row.description})
    },
  },
  {
    title: '创建日期',
    key: 'created_time',
    width: 80,
    align: 'center',
    render(row) {
      return h('span', formatDate(row.created_time))
    },
  },
  {
    title: '更新日期',
    key: 'updated_time',
    width: 80,
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
                  size: 'small',
                  type: 'primary',
                  style: 'margin-right: 8px;',
                  onClick: async () => {
                    try {
                      // 使用 Promise.all 来同时发送所有请求
                      const [menusResponse, apisResponse, roleAuthorizedResponse] = await Promise.all([
                        api.getMenus({page: 1, page_size: 9999}),
                        api.getApis({page: 1, page_size: 9999}),
                        api.getRoleAuthorized({id: row.id}),
                      ])

                      // 处理每个请求的响应
                      menuOption.value = menusResponse.data
                      apiOption.value = buildApiTree(apisResponse.data)
                      menu_ids.value = roleAuthorizedResponse.data.menus.map((v) => v.id)
                      api_ids.value = roleAuthorizedResponse.data.apis.map(
                          (v) => v.method.toLowerCase() + v.path
                      )

                      active.value = true
                      role_id.value = row.id
                    } catch (error) {
                      // 错误处理
                      console.error('Error loading data:', error)
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
              default: () => h('div', {}, '确定删除该角色吗?'),
            }
        ),
      ]
    },
  },
]

async function updateRoleAuthorized() {
  const checkData = apiTree.value.getCheckedData()
  const apiInfos = []
  checkData &&
  checkData.options.forEach((item) => {
    if (!item.children) {
      apiInfos.push({
        path: item.path,
        method: item.method,
      })
    }
  })
  const {code, msg} = await api.updateRoleAuthorized({
    id: role_id.value,
    menu_ids: menu_ids.value,
    api_infos: apiInfos,
  })
  if (code === 200) {
    $message?.success('设置成功')
  } else {
    $message?.error(msg)
  }

  const result = await api.getRoleAuthorized({id: role_id.value})
  menu_ids.value = result.data.menus.map((v) => {
    return v.id
  })
}
</script>

<template>
  <CommonPage show-footer title="角色列表">
    <template #action>
      <NButton v-permission="'post/api/v1/role/create'" type="primary" @click="handleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5"/>
        新建角色
      </NButton>
    </template>

    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="false"
        :columns="columns"
        :get-data="api.getRoleList"
        :single-line="true"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="角色名称：" :label-width="80">
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
                ref="apiTree"
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
