<script setup>
import {computed, h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NForm,
  NFormItem,
  NInput,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NPopconfirm,
  NSpace,
  NSwitch,
  NTag,
  NTree,
  NTreeSelect,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDate, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
// import { loginTypeMap, loginTypeOptions } from '@/constant/data'
import api from '@/api'
import {useUserStore} from '@/store'

defineOptions({name: '用户管理'})

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({ username: '', alias: '', email: '' })
const vPermission = resolveDirective('permission')

/** QueryBar：操作合并为下拉 */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: true,
  actionMode: 'dropdown',
}

async function handleBatchDelete() {
  let ids = [...(checkedRowKeys.value || [])]
  const userStore = useUserStore()
  const myId = userStore.userId
  const originalLen = ids.length
  ids = ids.filter((id) => id !== myId)
  if (!ids.length) {
    $message.warning('请先勾选要删除的用户，且不能仅包含当前登录账号')
    return
  }
  if (ids.length < originalLen) {
    $message.info('已自动排除当前登录用户')
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 个用户吗？`,
    async confirm() {
      await api.deleteUserBatch({ user_ids: ids })
      $message.success('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

const {
  modalVisible,
  modalTitle,
  modalAction,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: '用户',
  initForm: {},
  doCreate: api.createUser,
  doUpdate: api.updateUser,
  doDelete: api.deleteUser,
  refresh: () => $table.value?.handleSearch(),
})

const roleOption = ref([])
const deptOption = ref([])

onMounted(() => {
  api.getRoleList({page: 1, page_size: 9999}).then((res) => (roleOption.value = res.data))
  api.getDepts().then((res) => (deptOption.value = res.data))
})

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
      title: '用户账号',
      key: 'username',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '用户名称',
      key: 'alias',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '电子邮箱',
      key: 'email',
      width: 200,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '用户角色',
      key: 'role',
      width: 100,
      align: 'center',
      render(row) {
        const roles = row.roles ?? []
        const group = []
        for (let i = 0; i < roles.length; i++)
          group.push(
              h(NTag, {type: 'info', style: {margin: '2px 3px'}}, {default: () => roles[i].name})
          )
        return h('span', group)
      },
    },
    {
      title: '所属部门',
      key: 'dept.name',
      align: 'center',
      width: 100,
      ellipsis: {tooltip: true},
    },
    {
      title: '超级用户',
      key: 'is_superuser',
      align: 'center',
      width: 100,
      render(row) {
        return h(
            NTag,
            {type: 'info', style: {margin: '2px 3px'}},
            {default: () => (row.is_superuser ? '是' : '否')}
        )
      },
    },
    {
      title: '用户状态',
      key: 'state',
      align: 'center',
      width: 100,
      render(row) {
        return h(
            NTag,
            {type: 'info', style: {margin: '2px 3px'}},
            {default: () => row.state})
      },
    },
    {
      title: '是否禁用',
      key: 'is_active',
      width: 100,
      align: 'center',
      render(row) {
        return h(NSwitch, {
          size: 'small',
          rubberBand: false,
          value: row.is_active,
          loading: !!row.publishing,
          checkedValue: false,
          uncheckedValue: true,
          onUpdateValue: () => handleUpdateDisable(row),
        })
      },
    },
    {
      title: '上次登录时间',
      key: 'last_login',
      align: 'center',
      width: 200,
      ellipsis: {tooltip: true},
      render(row) {
        return h(
            NButton,
            {size: 'small', type: 'text', ghost: true},
            {
              default: () => (row.last_login !== null ? formatDate(row.last_login) : null),
              icon: renderIcon('mdi:update', {size: 16}),
            }
        )
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
                    type: 'info',
                    onClick: () => {
                      handleEdit(row)
                      modalForm.value.dept_id = row.dept?.id
                      modalForm.value.role_ids = row.roles.map((e) => (e = e.id))
                      delete modalForm.value.dept
                    },
                  },
                  {
                    default: () => '编辑',
                    icon: renderIcon('material-symbols:edit', {size: 16}),
                  }
              ),
              [[vPermission, 'post/api/v1/user/update']]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({user_id: row.id}, false),
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
                        [[vPermission, 'delete/api/v1/user/delete']]
                    ),
                default: () => h('div', {}, '确定删除该用户吗?'),
              }
          ),
          !row.is_superuser && h(
              NPopconfirm,
              {
                onPositiveClick: async () => {
                  try {
                    await api.resetPassword({user_id: row.id});
                    $message.success('密码已成功重置为123456');
                    await $table.value?.handleSearch();
                  } catch (error) {
                    $message.error('重置密码失败: ' + error.message);
                  }
                },
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
                              type: 'warning',
                            },
                            {
                              default: () => '重置',
                              icon: renderIcon('material-symbols:lock-reset', {size: 16}),
                            }
                        ),
                        [[vPermission, 'post/api/v1/user/reset_password']]
                    ),
                default: () => h('div', {}, '确定重置用户密码为123456吗?'),
              }
          ),
        ]
      },
    },
  ]
})

// 修改用户禁用状态
async function handleUpdateDisable(row) {
  if (!row.id) return
  const userStore = useUserStore()
  if (userStore.userId === row.id) {
    $message.error('当前登录用户不可禁用！')
    return
  }
  row.publishing = true
  row.is_active = row.is_active === false
  row.publishing = false
  const role_ids = []
  row.roles.forEach((e) => {
    role_ids.push(e.id)
  })
  row.role_ids = role_ids
  row.dept_id = row.dept?.id
  try {
    await api.updateUser(row)
    $message?.success(row.is_active ? '已取消禁用该用户' : '已禁用该用户')
    $table.value?.handleSearch()
  } catch (err) {
    // 有异常恢复原来的状态
    row.is_active = row.is_active === false
  } finally {
    row.publishing = false
  }
}

let lastClickedNodeId = null

const nodeProps = ({option}) => {
  return {
    onClick() {
      if (lastClickedNodeId === option.id) {
        $table.value?.handleSearch()
        lastClickedNodeId = null
      } else {
        api.getUserList({dept_id: option.id}).then((res) => {
          $table.value.tableData = res.data
          lastClickedNodeId = option.id
        })
      }
    },
  }
}

const validateAddUser = {
  username: [
    {
      required: true,
      message: '请输入名称',
      trigger: ['input', 'blur'],
    },
  ],
  email: [
    {
      required: true,
      message: '请输入邮箱地址',
      trigger: ['input', 'change'],
    },
    {
      trigger: ['blur'],
      validator: (rule, value, callback) => {
        const re = /^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$/
        if (!re.test(modalForm.value.email)) {
          callback('邮箱格式错误')
          return
        }
        callback()
      },
    },
  ],
  password: [
    {
      required: true,
      message: '请输入密码',
      trigger: ['input', 'blur', 'change'],
    },
  ],
  confirmPassword: [
    {
      required: true,
      message: '请再次输入密码',
      trigger: ['input'],
    },
    {
      trigger: ['blur'],
      validator: (rule, value, callback) => {
        if (value !== modalForm.value.password) {
          callback('两次密码输入不一致')
          return
        }
        callback()
      },
    },
  ],
  roles: [
    {
      type: 'array',
      required: true,
      message: '请至少选择一个角色',
      trigger: ['blur', 'change'],
    },
  ],
}
</script>

<template>
  <NLayout has-sider wh-full>

    <!--  部门树  -->
    <NLayoutSider
        bordered
        content-style="padding: 24px;"
        :collapsed-width="0"
        :width="240"
        show-trigger="arrow-circle"
    >
      <h1>部门列表</h1>
      <br/>
      <NTree
          block-line
          :data="deptOption"
          key-field="id"
          label-field="name"
          default-expand-all
          :node-props="nodeProps"
      >
      </NTree>
    </NLayoutSider>

    <!--  用户列表  -->
    <NLayoutContent>
      <CommonPage show-footer title="用户列表">

        <!-- 表格 -->
        <CrudTable
            ref="$table"
            v-model:query-items="queryItems"
            v-model:checked-row-keys="checkedRowKeys"
            :query-bar-props="queryBarProps"
            :is-pagination="true"
            :remote="true"
            :columns="columns"
            :get-data="api.getUserList"
            :single-line="true"
            :scroll-x="1500"
            row-key="id"
            @query-bar-create="handleAdd"
            @query-bar-delete="handleBatchDelete"
            @pagination-meta="onListPaginationMeta"
        >

          <!--  搜索行  -->
          <template #queryBar>
            <QueryBarItem label="用户账号：">
              <NInput
                  v-model:value="queryItems.username"
                  clearable
                  type="text"
                  placeholder="请输入用户账号"
                  @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="用户名称：">
              <NInput
                  v-model:value="queryItems.alias"
                  clearable
                  type="text"
                  placeholder="请输入用户名称"
                  @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="电子邮箱：">
              <NInput
                  v-model:value="queryItems.email"
                  clearable
                  type="text"
                  placeholder="请输入邮箱"
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
              :rules="validateAddUser">
            <NFormItem label="用户账号" path="username">
              <NInput v-model:value="modalForm.username" clearable placeholder="请输入用户名称"/>
            </NFormItem>
            <NFormItem v-if="modalAction === 'add'" label="用户密码" path="password">
              <NInput
                  v-model:value="modalForm.password"
                  show-password-on="mousedown"
                  type="password"
                  clearable
                  placeholder="请输入密码"/>
            </NFormItem>
            <NFormItem v-if="modalAction === 'add'" label="确认密码" path="confirmPassword">
              <NInput
                  v-model:value="modalForm.confirmPassword"
                  show-password-on="mousedown"
                  type="password"
                  clearable
                  placeholder="请确认密码"/>
            </NFormItem>
            <NFormItem label="用户名称" path="alias">
              <NInput v-model:value="modalForm.alias" clearable placeholder="请输入用户名称"/>
            </NFormItem>
            <NFormItem label="电子邮箱" path="email">
              <NInput v-model:value="modalForm.email" clearable placeholder="请输入电子邮箱"/>
            </NFormItem>
            <NFormItem label="手机号码" path="phone">
              <NInput v-model:value="modalForm.phone" clearable placeholder="请输入手机号码"/>
            </NFormItem>
            <NFormItem label="用户角色" path="role_ids">
              <NCheckboxGroup v-model:value="modalForm.role_ids">
                <NSpace item-style="display: flex;">
                  <NCheckbox
                      v-for="item in roleOption"
                      :key="item.id"
                      :value="item.id"
                      :label="item.name"/>
                </NSpace>
              </NCheckboxGroup>
            </NFormItem>
            <NFormItem label="超级用户" path="is_superuser">
              <NSwitch
                  v-model:value="modalForm.is_superuser"
                  size="small"
                  :checked-value="true"
                  :unchecked-value="false"/>
            </NFormItem>
            <NFormItem label="是否禁用" path="is_active">
              <NSwitch
                  v-model:value="modalForm.is_active"
                  :checked-value="false"
                  :unchecked-value="true"
                  :default-value="true"/>
            </NFormItem>
            <NFormItem label="所属部门" path="dept_id">
              <NTreeSelect
                  v-model:value="modalForm.dept_id"
                  :options="deptOption"
                  key-field="id"
                  label-field="name"
                  placeholder="请选择部门"
                  clearable
                  default-expand-all/>
            </NFormItem>
          </NForm>
        </CrudModal>
      </CommonPage>
    </NLayoutContent>
  </NLayout>
</template>
