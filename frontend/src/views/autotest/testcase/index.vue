<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives, computed, watch} from 'vue'
import {useRouter} from 'vue-router'
import {NButton, NInput, NPopconfirm, NSelect, NPopover, NList, NListItem} from 'naive-ui'

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

// 项目列表
const projectOptions = ref([])
const projectLoading = ref(false)

// 标签相关
const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach(tag => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) {
      groups[mode] = []
    }
    groups[mode].push(tag)
  })
  return groups
})
const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

// 选择标签后关闭 Popover
const handleTagSelect = (tagId) => {
  queryItems.value.case_tags = tagId
  tagPopoverShow.value = false
}

// 加载项目列表
const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getApiProjectList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      projectOptions.value = res.data.map(item => ({
        label: item.project_name,
        value: item.project_id
      }))
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  } finally {
    projectLoading.value = false
  }
}

// 加载标签列表
const loadTags = async (projectId) => {
  if (!projectId) {
    tagOptions.value = []
    selectedTagMode.value = null
    return
  }
  try {
    tagLoading.value = true
    const res = await api.getApiTagList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      // 根据 tag_project 过滤标签
      tagOptions.value = res.data.filter(tag => tag.tag_project === projectId)
      selectedTagMode.value = null
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

// 监听项目选择变化
watch(() => queryItems.value.case_project, (newVal) => {
  if (newVal) {
    loadTags(newVal)
  } else {
    tagOptions.value = []
    selectedTagMode.value = null
    queryItems.value.case_tags = null
  }
})

onMounted(() => {
  $table.value?.handleSearch()
  loadProjects()
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
    render(row) {
      // case_project 现在是对象，显示 project_name
      return h('span', row.case_project?.project_name || '')
    },
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
    render(row) {
      // case_tags 现在是对象数组，显示所有标签名称，用逗号分隔
      if (Array.isArray(row.case_tags) && row.case_tags.length > 0) {
        const tagNames = row.case_tags.map(tag => tag.tag_name || '').filter(name => name).join(', ')
        return h('span', tagNames)
      }
      return h('span', '')
    },
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
                  onClick: () => {
                    const query = {case_id: row.case_id}
                    if (row.case_code) {
                      query.case_code = row.case_code
                    }
                    router.push({path: '/autotest/api', query})
                  },
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
              onPositiveClick: () => handleDelete({case_id: row.case_id}, false),
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
          <NSelect
              v-model:value="queryItems.case_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择应用"
              style="width: 200px"
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
          <NPopover
              v-model:show="tagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :disabled="!queryItems.case_project"
              :style="{ width: '400px' }"
          >
            <template #trigger>
              <NInput
                  :value="queryItems.case_tags ? tagOptions.find(t => t.tag_id === queryItems.case_tags)?.tag_name : ''"
                  clearable
                  readonly
                  placeholder="请先选择应用，再选择标签"
                  style="width: 200px"
                  @clear="queryItems.case_tags = null"
                  @click="queryItems.case_project && (tagPopoverShow = !tagPopoverShow)"
              />
            </template>
            <template #default>
              <div style="display: flex; height: 300px; width: 400px;">
                <div style="width: 50%; border-right: 1px solid #e0e0e0; overflow-y: auto;">
                  <NList v-if="Object.keys(tagModeGroups).length > 0">
                    <NListItem
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': selectedTagMode === mode }"
                        style="cursor: pointer; padding: 8px 12px;"
                        @click="selectedTagMode = mode"
                    >
                      {{ mode }}
                    </NListItem>
                  </NList>
                  <div v-else style="padding: 20px; text-align: center; color: #999;">
                    {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                  </div>
                </div>
                <div style="width: 50%; overflow-y: auto;">
                  <NList v-if="selectedTagMode && currentTagNames.length > 0">
                    <NListItem
                        v-for="tag in currentTagNames"
                        :key="tag.tag_id"
                        :class="{ 'tag-name-selected': queryItems.case_tags === tag.tag_id }"
                        style="cursor: pointer; padding: 8px 12px;"
                        @click="handleTagSelect(tag.tag_id)"
                    >
                      {{ tag.tag_name }}
                    </NListItem>
                  </NList>
                  <div v-else style="padding: 20px; text-align: center; color: #999;">
                    {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </template>
          </NPopover>
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

.tag-mode-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

.tag-name-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

:deep(.n-list-item) {
  transition: background-color 0.2s;
}

:deep(.n-list-item:hover) {
  background-color: #f5f5f5;
}

</style>
