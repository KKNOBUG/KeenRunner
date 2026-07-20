<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm, NText } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, formatDate, renderIcon } from '@/utils'
import api from '@/api'
import EnvironmentEditDrawer from './EnvironmentEditDrawer.vue'

defineOptions({ name: '环境管理' })

/**
 * 环境 = 全局枚举（如 UAT/SIT）；明细配置（应用/库/Redis/文件）在抽屉内按应用挂载。
 * Redis「应用+配置名 → 库号」在抽屉 Redis 配置中维护。
 */

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  env_name: '',
  created_user: '',
  updated_user: '',
})
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

/** QueryBar：与表格工具栏一致的查询区操作（下拉合并为「操作」） */
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
    content: `确定删除选中的 ${ids.length} 条环境吗？删除后调试/执行将无法再选择这些环境。`,
    async confirm() {
      await api.deleteEnvBatch({ env_ids: ids })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

function buildSearchBody(overrides = {}) {
  const q = queryItems.value
  return {
    state: 0,
    ...overrides,
    env_name: (overrides.env_name ?? q.env_name) || undefined,
    created_user: (overrides.created_user ?? q.created_user) || undefined,
    updated_user: (overrides.updated_user ?? q.updated_user) || undefined,
  }
}

onMounted(async () => {
  try {
    const res = await api.getProjectList({ page: 1, page_size: 9999, state: 0 })
    projectOptions.value = (res?.data || []).map((p) => ({
      label: p.project_name || p.project_code,
      value: p.project_id,
    }))
  } catch (_) {
    projectOptions.value = []
  }
})

const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    { type: 'selection', fixed: 'left', width: 48 },
    {
      title: '序号',
      key: '__seq',
      width: 50,
      align: 'center',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '环境名称',
      key: 'env_name',
      minWidth: 150,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '环境描述',
      key: 'env_desc',
      minWidth: 200,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const d = String(row.env_desc ?? '').trim()
        return d || h(NText, { depth: 3 }, { default: () => '-' })
      },
    },
    {
      title: '环境代码',
      key: 'env_code',
      width: 400,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '更新时间',
      key: 'updated_time',
      width: 180,
      align: 'center',
      render(row) {
        return row.updated_time ? formatDate(row.updated_time, 'YYYY-MM-DD HH:mm:ss') : '-'
      },
    },
    {
      title: '更新人员',
      key: 'updated_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.updated_user || '-'
      },
    },
    {
      title: '创建时间',
      key: 'created_time',
      width: 180,
      align: 'center',
      render(row) {
        return row.created_time ? formatDate(row.created_time, 'YYYY-MM-DD HH:mm:ss') : '-'
      },
    },
    {
      title: '创建人员',
      key: 'created_user',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return row.created_user || '-'
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
                    onClick: () => openEdit(row),
                  },
                  {
                    default: () => '明细',
                    icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                  }
              ),
              [[vPermission, apiPermissionKey('post', '/autotest/env/update')]]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({ env_id: row.env_id }),
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
                        [[vPermission, apiPermissionKey('delete', '/autotest/env/delete')]]
                    ),
                default: () =>
                    h('div', {}, '确定删除该环境吗？删除后将无法在调试/执行中选择。'),
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
        :scroll-x="1400"
        :columns="columns"
        :get-data="(params) => api.getEnvList(buildSearchBody(params))"
        :single-line="true"
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
              placeholder="支持模糊搜索"
              style="width: 180px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              placeholder="创建人员"
              style="width: 140px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="更新人员：">
          <NInput
              v-model:value="queryItems.updated_user"
              clearable
              placeholder="更新人员"
              style="width: 140px"
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
