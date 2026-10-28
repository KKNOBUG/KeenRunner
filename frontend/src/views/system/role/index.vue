<script setup>
import {computed, h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {
  NAlert,
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTree,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {apiPermissionKey, formatDate, formatDateTime, renderIcon} from '@/utils'
import {useApiPermission, useCRUD} from '@/composables'
import {DATA_SCOPE_DEPT_AND_CHILD, DATA_SCOPE_OPTIONS, DATA_SCOPE_SELF, dataScopeLabel} from '@/constants/dataScope'
import api from '@/api'

defineOptions({name: '角色管理'})

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({ code: '', name: '', description: '' })
const vPermission = resolveDirective('permission')
const {hasApiPermission} = useApiPermission()
const ROLE_AUTHORIZED_PERM = apiPermissionKey('post', '/base/role/authorized')

/** 顶部新增/批量删除按钮同样按接口权限显隐，避免受限角色看到必然 403 的入口 */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: hasApiPermission('post', '/base/role/create'),
  addDelete: hasApiPermission('post', '/base/role/deletes'),
  actionMode: 'split',
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
  // 默认值与后端一致：可见本部门及下级、仅可写/可删本人数据
  initForm: {select_scope: DATA_SCOPE_DEPT_AND_CHILD, update_scope: DATA_SCOPE_SELF, delete_scope: DATA_SCOPE_SELF},
  doCreate: api.createRole,
  doDelete: api.deleteRole,
  doUpdate: api.updateRole,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
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
/** 角色按资源族标签的覆盖范围（空值表示按角色默认范围生效） */
const tagScopeRows = ref([])
/** 管理员角色固定全量权限，由后端 builtin_admin 标记，前端只展示说明不提供保存 */
const builtinAdmin = ref(false)
/** 当前权限页签，展开/折叠/反选只作用于当前页签的树 */
const activeTab = ref('menu')
/** 保存按钮等待接口响应 */
const saving = ref(false)
/** 两棵树的展开节点受控，支持一键展开/折叠 */
const menuExpandedKeys = ref([])
const apiExpandedKeys = ref([])

/**
 * 范围下拉只列具体枚举：未覆盖的行直接回显角色默认范围，消除“默认（X）”这类伪选项。
 * 空值仍表示未单独设置、继续跟随角色默认；用户选中具体值后才写入该标签的覆盖记录。
 */
function renderScopeSelect(row, field) {
  return h(NSelect, {
    value: row[field] || row[`default_${field}`],
    options: DATA_SCOPE_OPTIONS,
    size: 'small',
    consistentMenuWidth: false,
    style: {width: '100%'},
    onUpdateValue: (value) => {
      row[field] = value || null
    },
  })
}

const tagScopeColumns = [
  {
    title: '资源族',
    key: 'tag',
    ellipsis: {tooltip: true},
    render: (row) => {
      // 只标注显式覆盖过的行；未覆盖即按角色默认范围生效，不再重复标注避免干扰阅读
      const overridden = row.select_scope || row.update_scope || row.delete_scope
      if (!overridden) return row.tag
      return h(NSpace, {size: 6, align: 'center', wrap: false}, {
        default: () => [
          h('span', row.tag),
          h(NTag, {size: 'tiny', bordered: false, type: 'warning'}, {default: () => '已覆盖'}),
        ],
      })
    },
  },
  {
    title: '可见范围',
    key: 'select_scope',
    render: (row) => renderScopeSelect(row, 'select_scope'),
  },
  {
    title: '可写范围',
    key: 'update_scope',
    render: (row) => renderScopeSelect(row, 'update_scope'),
  },
  {
    title: '可删范围',
    key: 'delete_scope',
    render: (row) => renderScopeSelect(row, 'delete_scope'),
  },
]

/** 标签范围列表跟随抽屉顶部的筛选关键字 */
const filteredTagScopeRows = computed(() => {
  const keyword = pattern.value.trim()
  if (!keyword) return tagScopeRows.value
  return tagScopeRows.value.filter((row) => row.tag.includes(keyword))
})

function normalizeTagScopes(payload) {
  return (payload || []).map((row) => ({
    tag: row.tag,
    select_scope: row.select_scope || '',
    update_scope: row.update_scope || '',
    delete_scope: row.delete_scope || '',
    default_select_scope: row.default_select_scope,
    default_update_scope: row.default_update_scope,
    default_delete_scope: row.default_delete_scope,
  }))
}

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
      id: item['router_id'],
      path: item['path'],
      method: item['method'],
      summary: item['summary'],
      unique_id: unique_id,
    })
  })
  Object.values(groupedData).forEach((group) => {
    group.count = group.children.length
  })
  processedData.push(...Object.values(groupedData))
  return processedData
}

/** 接口方法标签配色，与列表页的请求方式配色保持一致 */
const API_METHOD_TAG_TYPE = {
  GET: 'success',
  POST: 'info',
  PUT: 'warning',
  PATCH: 'warning',
  DELETE: 'error',
}

/** 接口权限树标签：分组显示接口数量，叶子显示“方法 + 摘要 + 灰色路径” */
function renderApiLabel({option}) {
  if (option.children) {
    return h(NSpace, {size: 6, align: 'center', wrap: false}, {
      default: () => [
        h('span', option.summary),
        h(NText, {depth: 3, style: {fontSize: '12px'}}, {default: () => `${option.count} 项`}),
      ],
    })
  }
  return h('div', {class: 'role-auth-api-item'}, [
    h(
        NTag,
        {
          size: 'tiny',
          bordered: false,
          type: API_METHOD_TAG_TYPE[option.method] || 'default',
          class: 'role-auth-api-method',
        },
        {default: () => option.method}
    ),
    h('span', {class: 'role-auth-api-summary'}, option.summary || ''),
    h(NText, {depth: 3, class: 'role-auth-api-path'}, {default: () => option.path}),
  ])
}

/** 接口树搜索同时匹配摘要与路径，方便按 URL 定位接口 */
function filterApiNode(keyword, node) {
  const text = String(keyword || '').trim().toLowerCase()
  if (!text) return true
  return String(node.summary || '').toLowerCase().includes(text)
      || String(node.path || '').toLowerCase().includes(text)
}

/**
 * 收集树节点 key：默认取全部节点用于展开/折叠；leavesOnly 只取叶子，供接口树反选使用。
 * 菜单与接口树的 key 字段不同，统一由调用方传入。
 */
function collectNodeKeys(nodes, keyField, {leavesOnly = false} = {}) {
  const keys = []
  const walk = (list) => {
    ;(list || []).forEach((node) => {
      const hasChildren = Array.isArray(node.children) && node.children.length > 0
      if (hasChildren) walk(node.children)
      if (!leavesOnly || !hasChildren) keys.push(node[keyField])
    })
  }
  walk(nodes)
  return keys
}

const currentTreeConfig = computed(() => (
    activeTab.value === 'menu'
        ? {nodes: menuOption.value, keyField: 'menu_id'}
        : {nodes: apiOption.value, keyField: 'unique_id'}
))

/** 一键展开/折叠当前页签的树 */
function setCurrentExpanded(expanded) {
  const {nodes, keyField} = currentTreeConfig.value
  const keys = expanded ? collectNodeKeys(nodes, keyField) : []
  if (activeTab.value === 'menu') {
    menuExpandedKeys.value = keys
  } else {
    apiExpandedKeys.value = keys
  }
}

/**
 * 反选当前页签：叶子节点取补集；目录只在子节点全部选中时加入。
 * 级联树会把已选中的父节点扩散到全部后代，目录若按“有子选中”加入将造成整目录越权。
 */
function invertCurrentChecked() {
  const {nodes, keyField} = currentTreeConfig.value
  if (activeTab.value === 'menu') {
    // 与级联树的显示口径对齐：父节点已选中即视为其后代全部选中
    const checked = new Set(menu_ids.value)
    const expand = (list) => {
      ;(list || []).forEach((node) => {
        const hasChildren = Array.isArray(node.children) && node.children.length > 0
        if (!hasChildren || !checked.has(node[keyField])) return
        node.children.forEach((child) => checked.add(child[keyField]))
        expand(node.children)
      })
    }
    expand(nodes)
    const next = new Set()
    const invert = (list) => list.map((node) => {
      const hasChildren = Array.isArray(node.children) && node.children.length > 0
      if (!hasChildren) {
        if (checked.has(node[keyField])) return false
        next.add(node[keyField])
        return true
      }
      const allChecked = invert(node.children).every(Boolean)
      if (allChecked) next.add(node[keyField])
      return allChecked
    })
    invert(nodes)
    menu_ids.value = [...next]
  } else {
    const checked = new Set(api_ids.value)
    api_ids.value = collectNodeKeys(nodes, keyField, {leavesOnly: true}).filter((key) => !checked.has(key))
  }
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
      title: '数据可见范围',
      key: 'select_scope',
      width: 150,
      align: 'center',
      render(row) {
        return h(NTag, {type: 'success', bordered: false}, {default: () => dataScopeLabel(row.select_scope)})
      },
    },
    {
      title: '数据可写范围',
      key: 'update_scope',
      width: 150,
      align: 'center',
      render(row) {
        return h(NTag, {type: 'warning', bordered: false}, {default: () => dataScopeLabel(row.update_scope)})
      },
    },
    {
      title: '数据可删范围',
      key: 'delete_scope',
      width: 150,
      align: 'center',
      render(row) {
        return h(NTag, {type: 'error', bordered: false}, {default: () => dataScopeLabel(row.delete_scope)})
      },
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
      width: 180,
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.created_time))
      },
    },
    {
      title: '更新时间',
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
                    type: 'info',
                    onClick: () => {
                      handleEdit(row)
                      // RoleUpdate入参主键仍为id必填：行对象主键已改为role_id，提交前回填id
                      modalForm.value.id = row.role_id
                    },
                  },
                  {
                    default: () => '编辑',
                    icon: renderIcon('material-symbols:edit-outline', {size: 16}),
                  }
              ),
              [[vPermission, apiPermissionKey('post', '/base/role/update')]]
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
                          api.getRoleAuthorized({ id: row.role_id }),
                        ])

                        const authPayload = roleAuthorizedResponse.data || {}
                        // 后端 to_dict(m2m=True) 字段名为 menus / routers，不是 apis
                        menuOption.value = menusResponse.data || []
                        apiOption.value = buildApiTree(apisResponse.data || [])
                        menu_ids.value = (authPayload.menus || []).map((v) => v.menu_id)
                        api_ids.value = (authPayload.routers || []).map((v) => {
                          const m = String(v.method ?? '').toLowerCase()
                          const p = v.path ?? ''
                          return m + p
                        })
                        tagScopeRows.value = normalizeTagScopes(authPayload.tag_scopes)
                        builtinAdmin.value = !!authPayload.builtin_admin

                        // 切换角色时重置筛选与页签，并按全展开初始化两棵树
                        pattern.value = ''
                        activeTab.value = 'menu'
                        menuExpandedKeys.value = collectNodeKeys(menuOption.value, 'menu_id')
                        apiExpandedKeys.value = collectNodeKeys(apiOption.value, 'unique_id')

                        active.value = true
                        role_id.value = row.role_id
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
              [[vPermission, apiPermissionKey('get', '/base/role/authorized')]]

          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({role_id: row.role_id}, false),
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
                        [[vPermission, apiPermissionKey('delete', '/base/role/delete')]]
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
  saving.value = true
  try {
    // 空值统一转为 null，表示该范围按角色默认值生效
    const tag_scopes = tagScopeRows.value.map((row) => ({
      tag: row.tag,
      select_scope: row.select_scope || null,
      update_scope: row.update_scope || null,
      delete_scope: row.delete_scope || null,
    }))
    await api.updateRoleAuthorized({
      id: role_id.value,
      menu_ids: menu_ids.value,
      router_infos,
      tag_scopes,
    })
    $message?.success?.('保存成功')
    const result = await api.getRoleAuthorized({ id: role_id.value })
    const payload = result.data || {}
    menu_ids.value = (payload.menus || []).map((v) => v.menu_id)
    api_ids.value = (payload.routers || []).map((v) => {
      const m = String(v.method ?? '').toLowerCase()
      const p = v.path ?? ''
      return m + p
    })
    tagScopeRows.value = normalizeTagScopes(payload.tag_scopes)
  } catch (e) {
    $message?.error?.(e?.message || '保存失败')
  } finally {
    saving.value = false
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
        :get-data="api.searchRoleList"
        :single-line="true"
        :scroll-x="1780"
        row-key="role_id"
        @query-bar-create="handleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="角色代码：">
          <NInput
              v-model:value="queryItems.code"
              clearable
              type="text"
              placeholder="请输入角色代码"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="角色名称：">
          <NInput
              v-model:value="queryItems.name"
              clearable
              type="text"
              placeholder="请输入角色名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="角色描述：">
          <NInput
              v-model:value="queryItems.description"
              clearable
              type="text"
              placeholder="请输入角色描述"
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
        <NFormItem label="可见范围" path="select_scope">
          <NSelect v-model:value="modalForm.select_scope" :options="DATA_SCOPE_OPTIONS" placeholder="请选择数据可见范围"/>
        </NFormItem>
        <NFormItem label="可写范围" path="update_scope">
          <NSelect v-model:value="modalForm.update_scope" :options="DATA_SCOPE_OPTIONS" placeholder="请选择数据可写范围"/>
        </NFormItem>
        <NFormItem label="可删范围" path="delete_scope">
          <NSelect v-model:value="modalForm.delete_scope" :options="DATA_SCOPE_OPTIONS" placeholder="请选择数据可删范围"/>
        </NFormItem>
      </NForm>
    </CrudModal>

    <!--  设置权限抽屉  -->
    <NDrawer v-model:show="active" placement="right" width="min(900px, 92vw)">
      <NDrawerContent
          title="设置权限"
          body-style="padding: 0; overflow: hidden"
          body-content-style="height: 100%; min-height: 0; display: flex; flex-direction: column; padding: 12px 20px 16px"
      >
        <NAlert v-if="builtinAdmin" type="info" :bordered="false" title="管理员角色">
          该角色始终拥有全部菜单、接口与数据权限，无需配置，也不允许保存绑定。
        </NAlert>
        <template v-else>
          <div class="role-auth-toolbar">
            <NInput
                v-model:value="pattern"
                class="role-auth-search"
                type="text"
                clearable
                placeholder="筛选菜单名称(菜单权限)、筛选接口描述或地址(接口权限)"/>
            <div class="role-auth-actions">
              <template v-if="activeTab !== 'tagScope'">
                <NButton type="primary" @click="setCurrentExpanded(true)">展开</NButton>
                <NButton type="primary" @click="setCurrentExpanded(false)">折叠</NButton>
                <NButton type="primary" @click="invertCurrentChecked">反选</NButton>
              </template>
              <NButton
                  v-permission="ROLE_AUTHORIZED_PERM"
                  type="primary"
                  :loading="saving"
                  @click="updateRoleAuthorized">
                保存
              </NButton>
            </div>
          </div>

          <NTabs v-model:value="activeTab" class="role-auth-tabs">
            <NTabPane name="menu" tab="菜单权限" display-directive="show">
              <div class="role-auth-scroll">
                <NTree
                    v-model:expanded-keys="menuExpandedKeys"
                    :data="menuOption"
                    :checked-keys="menu_ids"
                    :pattern="pattern"
                    :show-irrelevant-nodes="false"
                    key-field="menu_id"
                    label-field="name"
                    checkable
                    cascade
                    :block-line="true"
                    :selectable="false"
                    @update:checked-keys="(v) => (menu_ids = v)"
                />
              </div>
            </NTabPane>
            <NTabPane name="resource" tab="接口权限" display-directive="show">
              <div class="role-auth-scroll">
                <NTree
                    ref="apiTreeRef"
                    v-model:expanded-keys="apiExpandedKeys"
                    :data="apiOption"
                    :checked-keys="api_ids"
                    :pattern="pattern"
                    :show-irrelevant-nodes="false"
                    key-field="unique_id"
                    label-field="summary"
                    checkable
                    :render-label="renderApiLabel"
                    :filter="filterApiNode"
                    :block-line="true"
                    :selectable="false"
                    cascade
                    @update:checked-keys="(v) => (api_ids = v)"
                />
              </div>
            </NTabPane>
            <NTabPane name="tagScope" tab="标签范围" display-directive="show">
              <NDataTable
                  class="role-auth-scope-table"
                  size="small"
                  flex-height
                  :columns="tagScopeColumns"
                  :data="filteredTagScopeRows"
                  :row-key="(row) => row.tag"
                  :virtual-scroll="false"
              />
            </NTabPane>
          </NTabs>
        </template>
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>

<style scoped>
/* 抽屉内容区固定为「工具栏 + 页签」两段，页签内容撑满剩余高度 */
.role-auth-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}

.role-auth-search {
  flex: 1;
  min-width: 0;
}

.role-auth-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.role-auth-tabs {
  flex: 1;
  min-height: 0;
  margin-top: 8px;
}

.role-auth-tabs :deep(.n-tabs-nav) {
  flex: none;
}

.role-auth-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
}

.role-auth-tabs :deep(.n-tab-pane) {
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
}

/* 树区域占满页签高度并独立滚动，避免长列表把整个抽屉撑出滚动条 */
.role-auth-scroll {
  height: 100%;
  overflow: auto;
  padding-right: 4px;
}

.role-auth-scroll :deep(.n-tree-node-content__text) {
  flex: 1;
  min-width: 0;
}

/* 树节点默认禁用文本选择，放开后可直接拖选复制菜单名称与接口地址 */
.role-auth-scroll :deep(.n-tree-node-content) {
  user-select: text;
}

.role-auth-scope-table {
  height: 100%;
}

/* 接口权限行：方法标签 + 摘要 + 灰色路径，路径过长省略；节点由 render 函数生成，需 :deep 命中 */
.role-auth-scroll :deep(.role-auth-api-item) {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.role-auth-scroll :deep(.role-auth-api-method) {
  flex: none;
  width: 56px;
  justify-content: center;
}

.role-auth-scroll :deep(.role-auth-api-summary) {
  flex: none;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-auth-scroll :deep(.role-auth-api-path) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}
</style>
