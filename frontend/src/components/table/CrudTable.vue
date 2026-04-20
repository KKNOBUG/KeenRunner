<template>
  <div v-bind="$attrs">
    <QueryBar
        v-if="$slots.queryBar"
        mb-30
        v-bind="queryBarProps"
        @search="handleSearch"
        @reset="handleReset"
        @create="emit('queryBarCreate')"
        @delete="emit('queryBarDelete')"
    >
      <slot name="queryBar" />
    </QueryBar>

    <n-data-table
        :remote="remote"
        :loading="loading"
        :columns="columns"
        :data="tableData"
        :scroll-x="scrollX"
        :row-key="(row) => row[rowKey]"
        :checked-row-keys="hasRowSelection ? mergedCheckedRowKeys : undefined"
        :pagination="isPagination ? pagination : false"
        @update:checked-row-keys="onCheckedRowKeysUpdate"
        @update:page="onPageChange"
    />
  </div>
</template>

<script setup>
import QueryBar from "@/components/query-bar/QueryBar.vue";

const props = defineProps({
  /**
   * @remote true: 后端分页  false： 前端分页
   */
  remote: {
    type: Boolean,
    default: true,
  },
  /**
   * @remote 是否分页
   */
  isPagination: {
    type: Boolean,
    default: true,
  },
  scrollX: {
    type: Number,
    default: 450,
  },
  rowKey: {
    type: String,
    default: 'id',
  },
  columns: {
    type: Array,
    required: true,
  },
  /** queryBar中的参数 */
  queryItems: {
    type: Object,
    default() {
      return {}
    },
  },
  /** 补充参数（可选） */
  extraParams: {
    type: Object,
    default() {
      return {}
    },
  },
  /**
   * ! 约定接口入参出参
   * * 分页模式需约定分页接口入参
   *    @page_size 分页参数：一页展示多少条，默认10
   *    @page   分页参数：页码，默认1
   */
  getData: {
    type: Function,
    required: true,
  },
  /** 透传给 QueryBar 的 props（如 addReset、addSearch、actionMode 等） */
  queryBarProps: {
    type: Object,
    default: () => ({}),
  },
  /** 勾选行主键（与 row-key 一致）；不传则由表格内部状态管理 */
  checkedRowKeys: {
    type: Array,
    default: undefined,
  },
})

const emit = defineEmits([
  'update:queryItems',
  'onChecked',
  'onDataChange',
  'queryBarCreate',
  'queryBarDelete',
  'update:checkedRowKeys',
  /** 远程分页数据加载完成后发出，便于父组件渲染跨页「序号」列 */
  'paginationMeta',
])
const loading = ref(false)
const localCheckedRowKeys = ref([])
const initQuery = { ...props.queryItems }
const tableData = ref([])

const mergedCheckedRowKeys = computed(() =>
    props.checkedRowKeys !== undefined ? props.checkedRowKeys : localCheckedRowKeys.value
)

const hasRowSelection = computed(() => props.columns.some((item) => item.type === 'selection'))
const pagination = reactive({
  page: 1,
  /** 与 Naive Pagination 字段一致；请求接口时映射为 page_size */
  pageSize: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
  onChange: (page) => {
    pagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    handleQuery()
  },
})

async function handleQuery() {
  try {
    loading.value = true
    let paginationParams = {}
    // 如果非分页模式或者使用前端分页,则无需传分页参数
    if (props.isPagination && props.remote) {
      paginationParams = { page: pagination.page, page_size: pagination.pageSize }
    }
    const { data, total } = await props.getData({
      ...props.queryItems,
      ...props.extraParams,
      ...paginationParams,
    })
    tableData.value = data
    pagination.itemCount = total || 0
  } catch (error) {
    tableData.value = []
    pagination.itemCount = 0
  } finally {
    emit('onDataChange', tableData.value)
    if (props.isPagination && props.remote) {
      emit('paginationMeta', { page: pagination.page, page_size: pagination.pageSize })
    }
    loading.value = false
  }
}
function handleSearch() {
  pagination.page = 1
  handleQuery()
}
async function handleReset() {
  const queryItems = { ...props.queryItems }
  for (const key in queryItems) {
    queryItems[key] = null
  }
  emit('update:queryItems', { ...queryItems, ...initQuery })
  await nextTick()
  pagination.page = 1
  if (props.checkedRowKeys !== undefined) {
    emit('update:checkedRowKeys', [])
  } else {
    localCheckedRowKeys.value = []
  }
  await handleQuery()
}
function onPageChange(currentPage) {
  pagination.page = currentPage
  if (props.remote) {
    handleQuery()
  }
}
function onChecked(rowKeys) {
  if (props.columns.some((item) => item.type === 'selection')) {
    emit('onChecked', rowKeys)
  }
}

function updateCheckedRowKeys(rowKeys) {
  if (props.checkedRowKeys !== undefined) {
    emit('update:checkedRowKeys', rowKeys)
  } else {
    localCheckedRowKeys.value = rowKeys
  }
  onChecked(rowKeys)
}

function onCheckedRowKeysUpdate(rowKeys) {
  if (!hasRowSelection.value) return
  updateCheckedRowKeys(rowKeys)
}

defineExpose({
  handleSearch,
  handleReset,
  tableData,
  pagination,
})
</script>
