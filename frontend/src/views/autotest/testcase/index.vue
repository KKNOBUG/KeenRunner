<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives} from 'vue'
import {useRouter} from 'vue-router'
import {NButton, NInput, NPopconfirm} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDateTime, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({name: '测试用例'})

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
  name: '用例',
  doCreate: api.createApiTestcaseList,
  doDelete: api.deleteApiTestcaseList,
  doUpdate: api.updateApiTestcaseList,
  refresh: () => $table.value?.handleSearch(),
})

const pattern = ref('')
const active = ref(false)
const ownerOption = ref([])
const router = useRouter()

onMounted(() => {
  $table.value?.handleSearch()
  api.getApiTestcaseList().then((res) => (ownerOption.value = res.data))
})


// 重置逻辑（在handleAdd中处理）
const customHandleAdd = () => {
  router.push({path: '/autotest/api'})
}


const columns = [
  {
    title: '所属应用',
    key: 'case_project',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例步骤',
    key: 'case_steps',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例版本',
    key: 'case_version',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例标签',
    key: 'case_tags',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例属性',
    key: 'case_attr',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例类型',
    key: 'case_type',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例描述',
    key: 'case_desc',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例状态',
    key: 'state',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 150,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time))
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 150,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
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
                  onClick: () => router.push({path: '/autotest/api', query: {case_id: row.id}}),
                },
                {
                  default: () => '编辑',
                  icon: renderIcon('material-symbols:edit-outline', {size: 16}),
                }
            ),
            [[vPermission, 'post/api/v1/role/update']]
        ),
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({case_id: row.id}, false),
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
              default: () => h('div', {}, '确定删除该用例吗?'),
            }
        ),
      ]
    },
  },
]


</script>

<template>
  <CommonPage show-footer title="测试用例">
    <template #action>
      <NButton v-permission="'post/api/v1/project/create'" type="primary" @click="customHandleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5"/>
        新增测试用例
      </NButton>
    </template>

    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="false"
        :columns="columns"
        :get-data="api.getApiTestcaseList"
        :single-line="true"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="所属应用：">
          <NInput
              v-model:value="queryItems.case_project"
              clearable
              type="text"
              placeholder="请输入应用名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例名称：">
          <NInput
              v-model:value="queryItems.case_name"
              clearable
              type="text"
              placeholder="请输入用例名称"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例标签：">
          <NInput
              v-model:value="queryItems.case_tags"
              clearable
              type="text"
              placeholder="请输入用例标签"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例属性：">
          <NInput
              v-model:value="queryItems.case_attr"
              clearable
              type="text"
              placeholder="请输入用例属性"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例类型：">
          <NInput
              v-model:value="queryItems.case_type"
              clearable
              type="text"
              placeholder="请输入用例类型"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              type="text"
              placeholder="请输入创建人员"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>

    </CrudTable>


  </CommonPage>
</template>


<style scoped>
.env-fields {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.field {
  width: 100%;
}

:deep(.n-collapse-item__header) {
  padding: 12px;
}

</style>
