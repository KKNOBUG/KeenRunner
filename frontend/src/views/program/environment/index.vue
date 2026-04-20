<script setup>
import { computed, h, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import api from '@/api'
import EnvironmentEditDrawer from './EnvironmentEditDrawer.vue'

defineOptions({ name: '环境管理' })

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({ env_name: '' })
const projectOptions = ref([])
const vPermission = resolveDirective('permission')

const drawerShow = ref(false)
const editingEnvId = ref(undefined)
const editingEnvRow = ref(null)

function openCreate() {
  editingEnvId.value = undefined
  editingEnvRow.value = null
  drawerShow.value = true
}

function openEdit(row) {
  editingEnvId.value = row?.env_id
  editingEnvRow.value = row || null
  drawerShow.value = true
}

async function handleDelete(params) {
  await api.deleteEnv(params)
  window.$message?.success?.('删除成功')
  $table.value?.handleSearch?.()
}

/** QueryBar：与表格工具栏一致的查询区操作（下拉合并为「更多」） */
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
    window.$message?.warning?.('请先勾选要删除的环境')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条环境吗？`,
    async confirm() {
      await api.deleteEnvBatch({ env_ids: ids })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    env_name: queryItems.value.env_name || undefined,
    ...overrides,
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
    { title: '环境名称', key: 'env_name', align: 'center', ellipsis: { tooltip: true } },
    { title: '环境代码', key: 'env_code', align: 'center', ellipsis: { tooltip: true } },
    { title: '创建人员', key: 'created_user', align: 'center', ellipsis: { tooltip: true } },
    { title: '更新人员', key: 'updated_user', align: 'center', ellipsis: { tooltip: true } },
    { title: '创建时间', key: 'created_time', align: 'center', ellipsis: { tooltip: true } },
    { title: '维护时间', key: 'updated_time', align: 'center', ellipsis: { tooltip: true } },
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
                    onClick: () => openEdit(row),
                  },
                  { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
              ),
              [[vPermission, 'post/api/v1/role/update']]
          ),
          h(
              NPopconfirm,
              { onPositiveClick: () => handleDelete({ env_id: row.env_id }) },
              {
                trigger: () =>
                    withDirectives(
                        h(NButton, { size: 'small', type: 'error', style: 'margin-right: 8px;' }, {
                          default: () => '删除',
                          icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                        }),
                        [[vPermission, 'delete/api/v1/role/delete']]
                    ),
                default: () => h('div', {}, '确定删除该环境吗?'),
              }
          ),
        ]
      },
    },
  ]
})

</script>

<template>
  <CommonPage show-footer title="环境列表">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :scroll-x="1200"
        :columns="columns"
        :get-data="(params) => api.getEnvList(buildSearchBody(params))"
        row-key="env_id"
        @query-bar-create="openCreate"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="环境名称：">
          <NInput
              v-model:value="queryItems.env_name"
              clearable
              placeholder="请输入环境名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <EnvironmentEditDrawer
        v-model:show="drawerShow"
        :env-id="editingEnvId"
        :env-row="editingEnvRow"
        :default-project-id="undefined"
        :project-options="projectOptions"
        @saved="$table?.handleSearch()"
    />
  </CommonPage>
</template>
