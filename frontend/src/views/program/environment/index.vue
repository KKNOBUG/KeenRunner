<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, renderIcon } from '@/utils'
import api from '@/api'
import EnvironmentEditDrawer from './EnvironmentEditDrawer.vue'

defineOptions({ name: '环境管理' })

/**
 * 环境管理（主子表）。
 * 主表：环境枚举（应用 + 环境名称 + 节点类型），来自 GET /autotest/env/page（含 project_name/is_delete）。
 * 子表：环境配置（APP/FILE/DB/Redis），在抽屉内按应用 + 环境名维护。
 * Redis 配置挂在同名 APP 环境枚举下。
 */

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  project_id: null,
  env_name: '',
  env_type: null,
  ip: '',
})
const projectOptions = ref([])
const vPermission = resolveDirective('permission')

const ENV_TYPE_OPTIONS = [
  { label: 'APP', value: 1 },
  { label: 'FILE', value: 2 },
  { label: 'DB', value: 3 },
]
const ENV_TYPE_TAG = { 1: 'success', 2: 'warning', 3: 'info' }
const ENV_TYPE_LABEL = { 1: 'APP', 2: 'FILE', 3: 'DB' }

const drawerShow = ref(false)
const editingEnvRow = ref(null)

function openCreate() {
  editingEnvRow.value = null
  drawerShow.value = true
}

function openEdit(row) {
  editingEnvRow.value = row || null
  drawerShow.value = true
}

async function handleDelete(row) {
  await api.deleteEnv({ env_id: Number(row.id) })
  window.$message?.success?.('删除成功')
  $table.value?.handleSearch?.()
}

/** QueryBar：与表格工具栏一致的查询区操作（下拉合并为「操作」） */
const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'dropdown',
}

function buildSearchParams(overrides = {}) {
  const q = queryItems.value
  return {
    ...overrides,
    project_id: (overrides.project_id ?? q.project_id) || undefined,
    env_name: (overrides.env_name ?? q.env_name) || undefined,
    env_type: (overrides.env_type ?? q.env_type) ?? undefined,
    ip: (overrides.ip ?? q.ip) || undefined,
  }
}

async function fetchEnvPage(params) {
  const res = await api.getEnvPage(buildSearchParams(params))
  return { data: res?.data || [], total: res?.total || 0 }
}

onMounted(async () => {
  try {
    const res = await api.getAllApps({ page: 1, page_size: 10000 })
    projectOptions.value = (res?.data || []).map((p) => ({
      label: p.project_name || p.project_mark,
      value: p.id,
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
      title: '应用名称',
      key: 'project_name',
      minWidth: 160,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '环境名称',
      key: 'env_name',
      minWidth: 140,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '节点类型',
      key: 'env_type',
      width: 110,
      align: 'center',
      render(row) {
        const t = Number(row.env_type)
        return h(NTag, { type: ENV_TYPE_TAG[t] || 'default', size: 'small' }, { default: () => ENV_TYPE_LABEL[t] || row.env_type })
      },
    },
    {
      title: '更新时间',
      key: 'updated_time',
      width: 180,
      align: 'center',
      render(row) {
        return row.updated_time || '-'
      },
    },
    {
      title: '创建时间',
      key: 'created_time',
      width: 180,
      align: 'center',
      render(row) {
        return row.created_time || '-'
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      align: 'center',
      fixed: 'right',
      render(row) {
        const btns = [
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
                    default: () => '配置明细',
                    icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                  }
              ),
              [[vPermission, apiPermissionKey('post', '/autotest/env/update')]]
          ),
        ]
        if (row.is_delete) {
          btns.push(
              h(
                  NPopconfirm,
                  {
                    onPositiveClick: () => handleDelete(row),
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
                        h('div', {}, '该环境下已无子表配置，确定删除吗？'),
                  }
              )
          )
        }
        return btns
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
        :get-data="fetchEnvPage"
        :single-line="true"
        row-key="id"
        @query-bar-create="openCreate"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="应用名称：">
          <NSelect
              v-model:value="queryItems.project_id"
              :options="projectOptions"
              clearable
              filterable
              placeholder="应用名称"
              style="width: 180px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="环境名称：">
          <NInput
              v-model:value="queryItems.env_name"
              clearable
              placeholder="支持模糊搜索"
              style="width: 160px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="节点类型：">
          <NSelect
              v-model:value="queryItems.env_type"
              :options="ENV_TYPE_OPTIONS"
              clearable
              placeholder="节点类型"
              style="width: 130px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="IP地址：">
          <NInput
              v-model:value="queryItems.ip"
              clearable
              placeholder="按子表主机IP过滤"
              style="width: 150px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <EnvironmentEditDrawer
        v-model:show="drawerShow"
        :env-row="editingEnvRow"
        :project-options="projectOptions"
        @saved="$table?.handleSearch()"
    />
  </CommonPage>
</template>
