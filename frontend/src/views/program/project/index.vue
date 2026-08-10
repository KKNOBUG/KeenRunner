<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NDynamicTags,
  NForm,
  NFormItem,
  NInput,
  NPopconfirm,
  NSelect,
  NTag,
  NText,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { apiPermissionKey, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: '项目管理' })

const $table = ref(null)
/** 与 CrudTable 分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

const checkedRowKeys = ref([])
const queryItems = ref({
  project_name: '',
  project_state: null,
  project_phase: null,
  project_dev_owners: '',
  project_test_owners: '',
})
const vPermission = resolveDirective('permission')

/** 常用状态预设 + 历史值聚合，减少自由文本分裂 */
const STATE_PRESETS = ['规划中', '开发中', '测试中', '已上线', '维护中', '已下线']
const PHASE_PRESETS = ['需求', '设计', '开发', '联调', '测试', '验收', '上线', '运维']
const stateOptions = ref(STATE_PRESETS.map((v) => ({ label: v, value: v })))
const phaseOptions = ref(PHASE_PRESETS.map((v) => ({ label: v, value: v })))
const envOptions = ref([])

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
  name: '应用',
  initForm: {
    project_name: '',
    project_code: '',
    project_desc: '',
    project_state: null,
    project_phase: null,
    project_dev_owners: [],
    project_developers: [],
    project_test_owners: [],
    project_testers: [],
    project_current_month_env: null,
  },
  doCreate: (form) => {
    const payload = {
      project_name: String(form.project_name ?? '').trim(),
      project_desc: trimOrUndef(form.project_desc),
      project_state: trimOrUndef(form.project_state),
      project_phase: trimOrUndef(form.project_phase),
      project_dev_owners: toOwnerList(form.project_dev_owners) ?? [],
      project_developers: toOwnerList(form.project_developers) ?? [],
      project_test_owners: toOwnerList(form.project_test_owners) ?? [],
      project_testers: toOwnerList(form.project_testers) ?? [],
      project_current_month_env: trimOrUndef(form.project_current_month_env),
    }
    return api.createProject(payload)
  },
  doDelete: (params) => api.deleteProject(params),
  doUpdate: (form) => {
    // 可清空字段必须传当前值（含 '' / []），否则后端 exclude_unset 会忽略未传字段
    const payload = {
      project_id: form.project_id,
      project_code: form.project_code ?? undefined,
      project_name: String(form.project_name ?? '').trim(),
      project_desc: form.project_desc ?? '',
      project_state: form.project_state ?? '',
      project_phase: form.project_phase ?? '',
      project_dev_owners: toOwnerList(form.project_dev_owners) ?? [],
      project_developers: toOwnerList(form.project_developers) ?? [],
      project_test_owners: toOwnerList(form.project_test_owners) ?? [],
      project_testers: toOwnerList(form.project_testers) ?? [],
      project_current_month_env: form.project_current_month_env ?? '',
    }
    return api.updateProject(payload)
  },
  refresh: () => {
    $table.value?.handleSearch()
    refreshMetaOptions()
  },
})

function trimOrUndef(v) {
  const s = String(v ?? '').trim()
  return s || undefined
}

/** 将人员字段转为后端 List[str]；支持数组或逗号分隔字符串 */
function toOwnerList(v) {
  if (v == null || v === '') return undefined
  if (Array.isArray(v)) {
    const list = v.map((s) => String(s).trim()).filter(Boolean)
    return list.length ? list : undefined
  }
  const list = String(v)
      .replace(/，/g, ',')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  return list.length ? list : undefined
}

function normalizePeople(v) {
  if (Array.isArray(v)) return v.map((s) => String(s).trim()).filter(Boolean)
  if (v == null || v === '') return []
  return String(v)
      .replace(/，/g, ',')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
}

function formatPeople(v) {
  const list = normalizePeople(v)
  return list.length ? list.join(', ') : '-'
}

function stateTagType(state) {
  const s = String(state ?? '').trim()
  if (!s) return 'default'
  if (s.includes('上线')) return 'success'
  if (s.includes('测试')) return 'info'
  if (s.includes('开发') || s.includes('规划')) return 'warning'
  if (s.includes('下线') || s.includes('停用')) return 'error'
  if (s.includes('维护')) return 'default'
  return 'default'
}

function customHandleEdit(row) {
  handleEdit({
    ...row,
    project_state: row.project_state || null,
    project_phase: row.project_phase || null,
    project_dev_owners: normalizePeople(row.project_dev_owners),
    project_developers: normalizePeople(row.project_developers),
    project_test_owners: normalizePeople(row.project_test_owners),
    project_testers: normalizePeople(row.project_testers),
    project_current_month_env: row.project_current_month_env || null,
  })
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
    window.$message?.warning?.('请先勾选要删除的应用')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条应用吗？若应用下仍有用例、标签或环境配置将无法删除。`,
    async confirm() {
      await api.deleteProjectBatch({ project_ids: ids })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
      refreshMetaOptions()
    },
  })
}

function buildSearchBody(overrides = {}) {
  const q = queryItems.value
  return {
    state: 0,
    ...overrides,
    project_name: (overrides.project_name ?? q.project_name) || undefined,
    project_state: (overrides.project_state ?? q.project_state) || undefined,
    project_phase: (overrides.project_phase ?? q.project_phase) || undefined,
    project_dev_owners: toOwnerList(overrides.project_dev_owners ?? q.project_dev_owners),
    project_test_owners: toOwnerList(overrides.project_test_owners ?? q.project_test_owners),
  }
}

/** 从现有应用聚合状态/阶段选项，供查询与表单复用 */
async function refreshMetaOptions() {
  try {
    const res = await api.getProjectList({ page: 1, page_size: 9999, state: 0 })
    const rows = res?.data || []
    const states = new Set(STATE_PRESETS)
    const phases = new Set(PHASE_PRESETS)
    for (const row of rows) {
      const st = String(row.project_state ?? '').trim()
      const ph = String(row.project_phase ?? '').trim()
      if (st) states.add(st)
      if (ph) phases.add(ph)
    }
    stateOptions.value = [...states].map((v) => ({ label: v, value: v }))
    phaseOptions.value = [...phases]
        .sort((a, b) => a.localeCompare(b, 'zh-CN'))
        .map((v) => ({ label: v, value: v }))
  } catch (_) {
    /* 保留预设 */
  }
}

async function loadEnvOptions() {
  try {
    const res = await api.getEnvList()
    const list = res?.data ?? []
    envOptions.value = list
        .map((row) => {
          const name = row.env_name != null ? String(row.env_name) : ''
          return name ? { label: name, value: name } : null
        })
        .filter(Boolean)
  } catch (_) {
    envOptions.value = []
  }
}

onMounted(() => {
  refreshMetaOptions()
  loadEnvOptions()
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
      minWidth: 150,
      align: 'center',
      ellipsis: { tooltip: true },
    },
    {
      title: '应用状态',
      key: 'project_state',
      width: 100,
      align: 'center',
      render(row) {
        const s = String(row.project_state ?? '').trim()
        if (!s) return h(NText, { depth: 3 }, { default: () => '-' })
        return h(
            NTag,
            { size: 'small', type: stateTagType(s), bordered: false },
            { default: () => s }
        )
      },
    },
    {
      title: '应用阶段',
      key: 'project_phase',
      width: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const p = String(row.project_phase ?? '').trim()
        return p || h(NText, { depth: 3 }, { default: () => '-' })
      },
    },
    {
      title: '开发负责人',
      key: 'project_dev_owners',
      minWidth: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return formatPeople(row.project_dev_owners)
      },
    },
    {
      title: '开发人员',
      key: 'project_developers',
      minWidth: 200,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return formatPeople(row.project_developers)
      },
    },
    {
      title: '测试负责人',
      key: 'project_test_owners',
      minWidth: 100,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return formatPeople(row.project_test_owners)
      },
    },
    {
      title: '测试人员',
      key: 'project_testers',
      minWidth: 200,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        return formatPeople(row.project_testers)
      },
    },
    {
      title: '应用描述',
      key: 'project_desc',
      minWidth: 200,
      align: 'center',
      ellipsis: { tooltip: true },
      render(row) {
        const d = String(row.project_desc ?? '').trim()
        return d || h(NText, { depth: 3 }, { default: () => '-' })
      },
    },
    {
      title: '应用代码',
      key: 'project_code',
      width: 400,
      align: 'center',
      ellipsis: { tooltip: true }
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
                    onClick: () => customHandleEdit(row),
                  },
                  {
                    default: () => '编辑',
                    icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
                  }
              ),
              [[vPermission, apiPermissionKey('post', '/autotest/project/update')]]
          ),
          h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete({ project_id: row.project_id }, false),
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
                        [[vPermission, apiPermissionKey('delete', '/autotest/project/delete')]]
                    ),
                default: () =>
                    h('div', {}, '确定删除该应用吗？若仍有关联用例/标签/环境配置将删除失败。'),
              }
          ),
        ]
      },
    },
  ]
})
</script>

<template>
  <CommonPage show-footer title="应用列表">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :scroll-x="2300"
        :columns="columns"
        :get-data="(params) => api.getProjectList(buildSearchBody(params))"
        :single-line="true"
        row-key="project_id"
        @query-bar-create="handleAdd"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onListPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="应用名称：">
          <NInput
              v-model:value="queryItems.project_name"
              clearable
              placeholder="支持模糊搜索"
              style="width: 160px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="应用状态：">
          <NSelect
              v-model:value="queryItems.project_state"
              :options="stateOptions"
              clearable
              filterable
              tag
              placeholder="全部状态"
              style="width: 140px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="应用阶段：">
          <NSelect
              v-model:value="queryItems.project_phase"
              :options="phaseOptions"
              clearable
              filterable
              tag
              placeholder="全部阶段"
              style="width: 140px"
              @update:value="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="开发负责人：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_dev_owners"
              clearable
              placeholder="多人用逗号分隔"
              style="width: 160px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="测试负责人：" :label-width="90">
          <NInput
              v-model:value="queryItems.project_test_owners"
              clearable
              placeholder="多人用逗号分隔"
              style="width: 160px"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal v-model:visible="modalVisible" :title="modalTitle" :loading="modalLoading" @save="handleSave">
      <NForm
          ref="modalFormRef"
          label-placement="left"
          label-align="left"
          :label-width="120"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem v-if="modalAction === 'edit'" label="应用代码" path="project_code">
          <NInput :value="modalForm.project_code" disabled placeholder="系统自动生成" />
        </NFormItem>
        <NFormItem
            label="应用名称"
            path="project_name"
            :rule="{ required: true, message: '请输入应用名称', trigger: ['input', 'blur'] }"
        >
          <NInput
              v-model:value="modalForm.project_name"
              maxlength="128"
              show-count
              clearable
              placeholder="全局唯一"
          />
        </NFormItem>
        <NFormItem label="应用状态" path="project_state">
          <NSelect
              v-model:value="modalForm.project_state"
              :options="stateOptions"
              clearable
              filterable
              tag
              placeholder="选择或输入状态"
          />
        </NFormItem>
        <NFormItem label="应用阶段" path="project_phase">
          <NSelect
              v-model:value="modalForm.project_phase"
              :options="phaseOptions"
              clearable
              filterable
              tag
              placeholder="选择或输入阶段，如迭代1"
          />
        </NFormItem>
        <NFormItem label="当前月版环境" path="project_current_month_env">
          <NSelect
              v-model:value="modalForm.project_current_month_env"
              :options="envOptions"
              clearable
              filterable
              tag
              placeholder="选择或输入环境名称"
          />
        </NFormItem>
        <NFormItem label="应用描述" path="project_desc">
          <NInput
              v-model:value="modalForm.project_desc"
              type="textarea"
              maxlength="2048"
              show-count
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="可选"
          />
        </NFormItem>
        <NFormItem label="开发负责人" path="project_dev_owners">
          <NDynamicTags v-model:value="modalForm.project_dev_owners" />
        </NFormItem>
        <NFormItem label="开发人员" path="project_developers">
          <NDynamicTags v-model:value="modalForm.project_developers" />
        </NFormItem>
        <NFormItem label="测试负责人" path="project_test_owners">
          <NDynamicTags v-model:value="modalForm.project_test_owners" />
        </NFormItem>
        <NFormItem label="测试人员" path="project_testers">
          <NDynamicTags v-model:value="modalForm.project_testers" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
