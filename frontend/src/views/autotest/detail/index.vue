<template>
  <CommonPage show-footer title="执行明细">
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :remote="true"
        :columns="columns"
        :get-data="getDetailList"
        :scroll-x="2400"
        :single-line="true"
        row-key="detail_id"
        @query-bar-delete="handleBatchDelete"
        @pagination-meta="onPaginationMeta"
    >
      <template #queryBar>
        <QueryBarItem label="用例ID：">
          <NInput
              v-model:value="queryItems.case_id"
              clearable
              type="text"
              placeholder="请输入用例ID"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例编码：">
          <NInput
              v-model:value="queryItems.case_code"
              clearable
              type="text"
              placeholder="请输入用例编码"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="报告标识：">
          <NInput
              v-model:value="queryItems.report_code"
              clearable
              type="text"
              placeholder="请输入报告标识"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="步骤类型：">
          <NSelect
              v-model:value="queryItems.step_type"
              :options="stepTypeOptions"
              clearable
              placeholder="请选择步骤类型"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="执行状态：">
          <NSelect
              v-model:value="queryItems.step_state"
              :options="stepStateOptions"
              clearable
              placeholder="请选择执行状态"
              class="query-input"
          />
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
      </template>
    </CrudTable>
  </CommonPage>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { NInput, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import api from '@/api'
import { useApiPermission, useBatchDeleteGuard } from '@/composables'
import { formatDateTime } from '@/utils'

defineOptions({ name: '执行明细' })

const $table = ref(null)
const queryItems = ref({})
const checkedRowKeys = ref([])
const { hasApiPermission } = useApiPermission()
const { pickDeletableIds } = useBatchDeleteGuard()

/** 批量删除入口按接口权限下发，与行内删除同一归属口径 */
const queryBarProps = computed(() => ({
  addReset: true,
  addSearch: true,
  addCreate: false,
  addDelete: hasApiPermission('post', '/autotest/detail/deletes'),
  actionMode: 'split',
}))

/** 分页元数据：渲染跨页「序号」列 */
const pageMeta = ref({ page: 1, page_size: 10 })
const onPaginationMeta = (meta) => {
  pageMeta.value = meta
}

/** 步骤类型选项：与后端 AutoTestStepType 枚举取值一致 */
const stepTypeOptions = [
  '用户变量', '条件分支', '等待控制', '循环结构', 'TCP请求', 'HTTP请求',
  '代码请求(Python)', '数据库请求', 'Redis请求', '引用公共脚本', '引用公共接口',
  '报文比对', '断言', '提取',
].map((value) => ({ label: value, value }))

const stepStateOptions = [
  { label: '成功', value: true },
  { label: '失败', value: false },
]

/** 用例ID查询项为字符串输入，请求前转为数值以匹配后端 int 校验 */
const getDetailList = (params = {}) => {
  const caseId = params.case_id
  const body = { ...params }
  if (caseId != null && String(caseId).trim() !== '') {
    const parsed = Number(caseId)
    body.case_id = Number.isNaN(parsed) ? undefined : parsed
  } else {
    delete body.case_id
  }
  return api.getApiDetailList(body)
}

async function handleBatchDelete() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选执行明细')
    return
  }
  // 先剔除不在可删范围的明细，避免整批请求被后端删除权限整体拒绝
  const deletableIds = pickDeletableIds({
    ids,
    rows: $table.value?.tableData || [],
    keyField: 'detail_id',
    label: '执行明细',
  })
  if (!deletableIds.length) {
    window.$message?.warning?.('选中的执行明细均不在可删范围，无法删除')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${deletableIds.length} 条执行明细吗？删除后不可恢复`,
    async confirm() {
      await api.deleteApiDetailBatch({ detail_ids: deletableIds })
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

const renderStepState = (row) => {
  if (row.step_state === true) {
    return h(NTag, { type: 'success', size: 'small', round: true }, () => '成功')
  }
  if (row.step_state === false) {
    return h(NTag, { type: 'error', size: 'small', round: true }, () => '失败')
  }
  return h('span', '-')
}

const renderElapsed = (row) => {
  const elapsed = parseFloat(row.step_elapsed)
  return h('span', Number.isNaN(elapsed) ? '-' : elapsed.toFixed(2))
}

const columns = [
  { type: 'selection', fixed: 'left', width: 48 },
  {
    title: '序号',
    key: 'index',
    width: 60,
    align: 'center',
    render: (row, index) => (pageMeta.value.page - 1) * pageMeta.value.page_size + index + 1,
  },
  { title: '用例ID', key: 'case_id', width: 90, align: 'center' },
  { title: '用例编码', key: 'case_code', width: 200, align: 'center', ellipsis: { tooltip: true } },
  { title: '报告标识', key: 'report_code', width: 200, align: 'center', ellipsis: { tooltip: true } },
  { title: '步骤序号', key: 'step_no', width: 90, align: 'center' },
  { title: '步骤名称', key: 'step_name', width: 220, align: 'center', ellipsis: { tooltip: true } },
  { title: '步骤类型', key: 'step_type', width: 140, align: 'center', ellipsis: { tooltip: true } },
  { title: '执行状态', key: 'step_state', width: 90, align: 'center', render: renderStepState },
  { title: '执行耗时(s)', key: 'step_elapsed', width: 100, align: 'center', render: renderElapsed },
  { title: '错误信息', key: 'step_exec_except', width: 240, align: 'center', ellipsis: { tooltip: true } },
  { title: '数据集', key: 'dataset_name', width: 140, align: 'center', ellipsis: { tooltip: true } },
  { title: '执行环境', key: 'request_env_name', width: 140, align: 'center', ellipsis: { tooltip: true } },
  { title: '环境配置', key: 'request_config_name', width: 140, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '执行时间',
    key: 'step_st_time',
    width: 180,
    align: 'center',
    render: (row) => h('span', row.step_st_time ? formatDateTime(row.step_st_time) : '-'),
  },
  { title: '创建人员', key: 'created_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
]
</script>

<style scoped>
.query-input {
  width: 200px;
}
</style>