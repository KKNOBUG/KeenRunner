<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NInput, NPopconfirm, NSelect } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: '环境管理' })

const $table = ref(null)
const queryItems = ref({ project_id: null, env_name: '', env_host: '' })
const projectOptions = ref([])
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
  name: '环境',
  initForm: {
    project_id: null,
    env_name: '',
    env_host: '',
    env_port: '',
  },
  doCreate: (form) => {
    const payload = {
      project_id: form.project_id,
      env_name: form.env_name,
      env_host: form.env_host,
    }
    const port = form.env_port !== '' && form.env_port != null ? Number(form.env_port) : undefined
    if (port !== undefined && !Number.isNaN(port)) payload.env_port = port
    return api.createEnv(payload)
  },
  doDelete: (params) => api.deleteEnv(params),
  doUpdate: (form) => {
    const payload = {
      env_id: form.env_id,
      env_code: form.env_code,
      project_id: form.project_id,
      env_name: form.env_name,
      env_host: form.env_host,
    }
    const port = form.env_port !== '' && form.env_port != null ? Number(form.env_port) : undefined
    if (port !== undefined && !Number.isNaN(port)) payload.env_port = port
    return api.updateEnv(payload)
  },
  refresh: () => $table.value?.handleSearch(),
})

function buildSearchBody(overrides = {}) {
  return {
    state: 0,
    project_id: queryItems.value.project_id || undefined,
    env_name: queryItems.value.env_name || undefined,
    env_host: queryItems.value.env_host || undefined,
    ...overrides,
  }
}

onMounted(async () => {
  try {
    const res = await api.getProjectList({ page: 1, page_size: 9999, state: 0 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name || p.project_code, value: p.project_id }))
  } catch (_) {}
  // 进入页面不自动请求表格数据，由用户点击「搜索」按钮时再请求
  // $table.value?.handleSearch()
})

const columns = [
  { title: '环境ID', key: 'env_id', align: 'center' },
  { title: '环境代码', key: 'env_code', align: 'center', ellipsis: { tooltip: true } },
  { title: '所属应用', key: 'project_name', align: 'center', ellipsis: { tooltip: true } },
  { title: '环境名称', key: 'env_name', align: 'center', ellipsis: { tooltip: true } },
  { title: '主机地址', key: 'env_host', align: 'center', ellipsis: { tooltip: true } },
  { title: '端口', key: 'env_port', align: 'center' },
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
                  onClick: () => handleEdit(row),
                },
                { default: () => '编辑', icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NPopconfirm,
            { onPositiveClick: () => handleDelete({ env_id: row.env_id }, false) },
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
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="handleAdd">
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
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.project_id"
              :options="projectOptions"
              clearable
              placeholder="请选择应用"
              style="width: 180px"
          />
        </QueryBarItem>
        <QueryBarItem label="环境名称：">
          <NInput
              v-model:value="queryItems.env_name"
              clearable
              placeholder="请输入环境名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="主机地址：">
          <NInput
              v-model:value="queryItems.env_host"
              clearable
              placeholder="请输入主机地址"
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
          :label-width="100"
          :model="modalForm"
          :disabled="modalAction === 'view'"
      >
        <NFormItem v-if="modalAction === 'edit'" label="环境ID" path="env_id">
          <NInput v-model:value="modalForm.env_id" disabled />
        </NFormItem>
        <NFormItem
            label="所属应用"
            path="project_id"
            :rule="{ required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] }"
        >
          <NSelect
              v-model:value="modalForm.project_id"
              :options="projectOptions"
              placeholder="请选择应用"
              :disabled="modalAction === 'edit'"
          />
        </NFormItem>
        <NFormItem
            label="环境名称"
            path="env_name"
            :rule="{ required: true, message: '请输入环境名称', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.env_name" placeholder="如：UAT、SIT" />
        </NFormItem>
        <NFormItem
            label="主机地址"
            path="env_host"
            :rule="{ required: true, message: '请输入主机地址', trigger: ['input', 'blur'] }"
        >
          <NInput v-model:value="modalForm.env_host" placeholder="如：https://api.example.com" />
        </NFormItem>
        <NFormItem label="端口" path="env_port">
          <NInput v-model:value="modalForm.env_port" type="number" placeholder="选填，直接请求域名时可留空（如 www.baidu.com）" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
