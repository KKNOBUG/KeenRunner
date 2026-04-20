<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import EnvironmentEditDrawer from './EnvironmentEditDrawer.vue'

defineOptions({ name: '环境管理' })

const $table = ref(null)
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

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    env_name: queryItems.value.env_name || undefined,
    ...overrides,
  }
}

const columns = [
  { title: '环境ID', key: 'env_id', width: 80, align: 'center' },
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

</script>

<template>
  <CommonPage show-footer title="环境列表">
    <template #action>
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="openCreate">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />
        新建环境
      </NButton>
    </template>

    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="true"
        :remote="true"
        :scroll-x="1200"
        :columns="columns"
        :get-data="(params) => api.getEnvList(buildSearchBody(params))"
        row-key="env_id"
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
