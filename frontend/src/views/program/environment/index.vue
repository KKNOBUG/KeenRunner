<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm, NSelect, NSpace, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, renderIcon } from '@/utils'
import api from '@/api'
import EnvBindModal from './EnvBindModal.vue'
import EnvConfigModal from './EnvConfigModal.vue'
import EnvConfigExpandTable from './EnvConfigExpandTable.vue'
import {
  CREATE_CONFIG_PERM,
  ENV_TYPE,
  ENV_TYPE_LABEL,
  ENV_TYPE_OPTIONS,
  ENV_TYPE_TAG,
} from './envType'

defineOptions({ name: '环境管理' })

/**
 * 环境管理（主子表）。
 * 主表：环境绑定（应用 + 环境名称 + 节点类型 API/FILE/DB/REDIS）。
 * 子表：展开后按节点类型展示对应配置。
 * 新增/编辑主表与配置均使用独立弹窗。
 */

const $table = ref(null)
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

const bindModalShow = ref(false)
const editingEnvRow = ref(null)

const configModalShow = ref(false)
const configModalMode = ref('create')
const configModalType = ref(ENV_TYPE.API)
const configEnvRow = ref(null)
/** 递增后通知已展开的子表重新拉取配置，避免必须手动折叠再展开 */
const expandRefreshKey = ref(0)

function openCreateBind() {
  editingEnvRow.value = null
  bindModalShow.value = true
}

function openEditBind(row) {
  editingEnvRow.value = row || null
  bindModalShow.value = true
}

function openAddConfig(row) {
  configEnvRow.value = row
  configModalType.value = row.env_type || ENV_TYPE.API
  configModalMode.value = 'create'
  configModalShow.value = true
}

async function onConfigSaved() {
  expandRefreshKey.value += 1
  // 同步刷新主表行状态（如 is_delete），不重置页码
  await $table.value?.handleQuery?.()
}

async function handleDelete(row) {
  await api.deleteEnv({ env_id: Number(row.env_id) })
  window.$message?.success?.('删除成功')
  $table.value?.handleSearch?.()
}

const queryBarProps = {
  addReset: true,
  addSearch: true,
  addCreate: true,
  addDelete: false,
  actionMode: 'split',
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
  const refreshKey = expandRefreshKey.value
  return [
    {
      type: 'expand',
      width: 40,
      renderExpand: (row) =>
          h(EnvConfigExpandTable, {
            key: String(row.env_id),
            envRow: row,
            refreshKey,
          }),
    },
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
        const t = row.env_type
        return h(NTag, { type: ENV_TYPE_TAG[t] || 'default', size: 'small' }, { default: () => ENV_TYPE_LABEL[t] || row.env_type })
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
      title: '更新时间',
      key: 'updated_time',
      width: 180,
      align: 'center',
      render(row) {
        return row.updated_time || '-'
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      align: 'center',
      fixed: 'right',
      render(row) {
        return h(NSpace, { size: 2, justify: 'center' }, {
          default: () => [
            withDirectives(
                h(
                    NButton,
                    {
                      size: 'tiny',
                      quaternary: true,
                      type: 'primary',
                      title: '添加配置',
                      onClick: () => openAddConfig(row),
                    },
                    { icon: renderIcon('material-symbols:add', { size: 16 }) }
                ),
                [[vPermission, apiPermissionKey('post', CREATE_CONFIG_PERM[row.env_type] || CREATE_CONFIG_PERM[ENV_TYPE.API])]]
            ),
            withDirectives(
                h(
                    NButton,
                    {
                      size: 'tiny',
                      quaternary: true,
                      type: 'info',
                      title: '编辑',
                      onClick: () => openEditBind(row),
                    },
                    { icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
                ),
                [[vPermission, apiPermissionKey('post', '/autotest/env/update')]]
            ),
            h(
                NPopconfirm,
                { onPositiveClick: () => handleDelete(row) },
                {
                  trigger: () =>
                      withDirectives(
                          h(
                              NButton,
                              {
                                size: 'tiny',
                                quaternary: true,
                                type: 'error',
                                title: '删除',
                              },
                              { icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }
                          ),
                          [[vPermission, apiPermissionKey('delete', '/autotest/env/delete')]]
                      ),
                  default: () =>
                      h(
                          'div',
                          {},
                          row.is_delete
                              ? '该环境下已无子表配置，确定删除吗？'
                              : '确定删除该环境绑定吗？'
                      ),
                }
            ),
          ],
        })
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
        row-key="env_id"
        @query-bar-create="openCreateBind"
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

    <EnvBindModal
        v-model:show="bindModalShow"
        :env-row="editingEnvRow"
        :project-options="projectOptions"
        @saved="$table?.handleSearch()"
    />

    <EnvConfigModal
        v-if="configEnvRow"
        v-model:show="configModalShow"
        :mode="configModalMode"
        :config-type="configModalType"
        :env-row="configEnvRow"
        @saved="onConfigSaved"
    />
  </CommonPage>
</template>
