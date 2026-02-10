<script setup>
import {h, onMounted, ref, resolveDirective, withDirectives, computed, watch} from 'vue'
import {useRouter} from 'vue-router'
import {NButton, NInput, NPopconfirm, NSelect, NPopover, NList, NListItem, NTag} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {formatDateTime, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({name: '测试用例'})

const $table = ref(null)
const queryItems = ref({
  case_tags: [] // 初始化为空数组
})
const vPermission = resolveDirective('permission')

const {
  handleDelete,
} = useCRUD({
  name: '用例',
  doCreate: api.createApiTestcaseList,
  doDelete: api.deleteApiTestcaseList,
  doUpdate: api.updateApiTestcaseList,
  refresh: () => $table.value?.handleSearch(),
})

const router = useRouter()

// 运行用例：以运行模式调用 execute_or_debugging，仅传 case_id，不传 steps。仅当前行的「运行」按钮显示 loading
const runningCaseId = ref(null)
const handleRunCase = async (row) => {
  runningCaseId.value = row.case_id ?? null
  try {
    const res = await api.executeStepTree({
      case_id: row.case_id ? Number(row.case_id) : null,
      initial_variables: [],
    })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      const stats = res.data || {}
      const msg = `执行完成，总步骤: ${stats.total_steps ?? '-'}, 成功: ${stats.success_steps ?? '-'}, 失败: ${stats.failed_steps ?? '-'}, 成功率: ${stats.pass_ratio ?? '-'}%`
      window.$message?.success?.(msg)
      $table.value?.handleSearch?.()
    } else {
      window.$message?.error?.(res?.message || '执行失败')
    }
  } catch (error) {
    console.error('运行用例失败', error)
    window.$message?.error?.(error?.message || error?.data?.message || '执行失败')
  } finally {
    runningCaseId.value = null
  }
}

// 项目列表
const projectOptions = ref([])
const projectLoading = ref(false)
// 用例属性选项
const caseAttrOptions = [
  { label: '正用例', value: '正用例' },
  { label: '反用例', value: '反用例' }
]
// 用例类型选项（与后端 AutoTestCaseType 一致）
const caseTypeOptions = [
  { label: '公共脚本', value: '公共脚本' },
  { label: '用户脚本', value: '用户脚本' }
]
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

// 选择标签（支持多选）
const handleTagSelect = (tagId) => {
  if (!Array.isArray(queryItems.value.case_tags)) {
    queryItems.value.case_tags = []
  }
  const index = queryItems.value.case_tags.indexOf(tagId)
  if (index > -1) {
    // 如果已选中，则取消选择
    queryItems.value.case_tags.splice(index, 1)
  } else {
    // 如果未选中，则添加
    queryItems.value.case_tags.push(tagId)
  }
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
const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getApiTagList({
      page: 1,
      page_size: 1000,
      tag_type: "脚本",
      state: 0
    })
    if (res?.data) {
      // 如果选择了项目，则过滤该项目的标签；否则显示所有标签
      if (projectId) {
        tagOptions.value = res.data.filter(tag => tag.tag_project === projectId)
      } else {
        tagOptions.value = res.data
      }
      selectedTagMode.value = null
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

// 获取选中的标签名称（用于显示）
const getSelectedTagNames = () => {
  const tags = queryItems.value.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  const names = tags
      .map(tagId => tagOptions.value.find(t => t.tag_id === tagId)?.tag_name)
      .filter(name => name)
  return names.join(', ')
}

// 判断标签是否被选中
const isTagSelected = (tagId) => {
  const tags = queryItems.value.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

// 确保 case_tags 始终是数组
watch(() => queryItems.value.case_tags, (newVal) => {
  if (newVal !== null && newVal !== undefined && !Array.isArray(newVal)) {
    queryItems.value.case_tags = []
  }
}, { immediate: true })

// 监听项目选择变化，重新加载标签
watch(() => queryItems.value.case_project, (newVal) => {
  loadTags(newVal)
})

onMounted(() => {
  // 所属应用、所属标签：进入页面时默认加载，供搜索条件使用
  loadProjects()
  loadTags()
  // 用例列表：不默认查询，由用户点击「搜索」按钮触发
})


// 重置逻辑（在handleAdd中处理）
const customHandleAdd = () => {
  router.push({path: '/autotest/api'})
}

// 使用 computed 使 columns 依赖 runLoading，点击运行后表格会重新渲染以显示按钮 loading 状态
const columns = computed(() => [
  {
    title: '用例名称',
    key: 'case_name',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例属性',
    key: 'case_attr',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例类型',
    key: 'case_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例步骤',
    key: 'case_steps',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
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
    title: '所属标签',
    key: 'case_tags',
    width: 150,
    align: 'center',
    render(row) {
      // case_tags 现在是对象数组，使用NTag展示，每个标签换行
      if (Array.isArray(row.case_tags) && row.case_tags.length > 0) {
        return h('div', { class: 'tag-container' },
            row.case_tags
                .filter(tag => tag.tag_name)
                .map(tag =>
                    h(NTag, {
                      type: 'info',
                      style: 'margin: 2px 4px 2px 0;'
                    }, { default: () => tag.tag_name })
                )
        )
      }
      return h('span', '')
    },
  },
  {
    title: '用例版本',
    key: 'case_version',
    width: 100,
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
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time))
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        h(
            NButton,
            {
              size: 'small',
              type: 'info',
              style: 'margin-right: 6px;',
              loading: runningCaseId.value === (row.case_id ?? null),
              disabled: runningCaseId.value != null,
              onClick: () => handleRunCase(row),
            },
            {
              default: () => '执行',
              icon: renderIcon('material-symbols:play-arrow', {size: 16}),
            }
        ),
        withDirectives(
            h(
                NButton,
                {
                  size: 'small',
                  type: 'primary',
                  style: 'margin-right: 8px;',
                  onClick: () => {
                    // 将完整的用例信息通过query传递（使用JSON字符串）
                    const query = {
                      case_id: row.case_id,
                      case_info: JSON.stringify(row) // 将整条用例信息对象转换为JSON字符串
                    }
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
])


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
        :is-pagination="true"
        :columns="columns"
        :get-data="api.getApiTestcaseList"
        :row-key="'case_id'"
        :scroll-x="2000"
        :single-line="true"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="用例名称：">
          <NInput
              v-model:value="queryItems.case_name"
              clearable
              type="text"
              placeholder="请输入用例名称"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例属性：">
          <NSelect
              v-model:value="queryItems.case_attr"
              :options="caseAttrOptions"
              clearable
              placeholder="请选择用例属性"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="用例类型：">
          <NSelect
              v-model:value="queryItems.case_type"
              :options="caseTypeOptions"
              clearable
              placeholder="请选择用例类型"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.case_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择所属应用"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="所属标签：">
          <NPopover
              v-model:show="tagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
          >
            <template #trigger>
              <NInput
                  :value="getSelectedTagNames()"
                  clearable
                  readonly
                  placeholder="请选择所属标签"
                  class="query-input"
                  @clear="queryItems.case_tags = []"
                  @click="tagPopoverShow = !tagPopoverShow"
              />
            </template>
            <template #default>
              <div style="display: flex; height: 300px; width: 400px;">
                <div style="width: 45%; overflow-y: auto;">
                  <NList v-if="Object.keys(tagModeGroups).length > 0">
                    <NListItem
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': selectedTagMode === mode, 'tag-mode-item': true }"
                        @click="selectedTagMode = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
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
                        :class="{ 'tag-name-selected': isTagSelected(tag.tag_id) }"
                        class="tag-list-item"
                        @click="handleTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
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
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              type="text"
              placeholder="请输入创建人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="更新人员：">
          <NInput
              v-model:value="queryItems.updated_user"
              clearable
              type="text"
              placeholder="请输入更新人员"
              class="query-input"
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

/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

/* 标签容器样式 - 每个标签换行展示 */
.tag-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: flex-start;
  justify-content: flex-start;
}

/* 标签列表项样式 */
.tag-list-item {
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-checkbox {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  color: #18a058;
  font-weight: bold;
}

.tag-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 标签分类列表项样式 */
.tag-mode-item {
  cursor: pointer;
  padding: 8px 12px;
}

.tag-mode-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

</style>
