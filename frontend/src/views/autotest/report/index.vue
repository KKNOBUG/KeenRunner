<script setup>
import {h, ref, resolveDirective, withDirectives} from 'vue'
import {NButton, NInput, NPopconfirm, NSelect, NTag} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'

defineOptions({name: '测试报告'})

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

const {
  handleDelete,
} = useCRUD({
  name: '报告',
  doDelete: api.deleteApiReport,
  refresh: () => $table.value?.handleSearch(),
})

// 包装 API 调用，默认过滤掉"调试执行"类型的报告
const getReportList = async (params = {}) => {
  const queryParams = {...params}
  // 处理 case_id：空字符串转换为 null
  if (queryParams.case_id === '' || queryParams.case_id === undefined) {
    queryParams.case_id = null
  } else if (queryParams.case_id !== null) {
    // 确保 case_id 是数字类型
    queryParams.case_id = Number(queryParams.case_id)
  }

  // 调用后端 API
  const res = await api.getApiReportList(queryParams)

  // 如果用户没有明确选择报告类型，则过滤掉"调试执行"类型的报告
  // 如果用户明确选择了报告类型（包括"调试执行"），则显示用户选择的结果
  if (!queryParams.report_type && res?.data) {
    const originalTotal = res.total || 0
    res.data = res.data.filter(item => item.report_type !== '调试执行')
    // 更新总数（过滤后的数量）
    res.total = res.data.length
  }

  return res
}

// 报告类型选项
const reportTypeOptions = [
  {label: '调试执行', value: '调试执行'},
  {label: '同步执行', value: '同步执行'},
  {label: '异步执行', value: '异步执行'},
  {label: '定时执行', value: '定时执行'}
]

// 执行状态选项
const caseStateOptions = [
  {label: '成功', value: true},
  {label: '失败', value: false}
]

const columns = [
  {
    title: '用例ID',
    key: 'case_id',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '报告类型',
    key: 'report_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '总步骤数',
    key: 'step_total',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '成功步骤',
    key: 'step_pass_count',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '失败步骤',
    key: 'step_fill_count',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '成功率',
    key: 'step_pass_ratio',
    width: 180,
    align: 'center',
    render(row) {
      const ratio = row.step_pass_ratio
      if (ratio === null || ratio === undefined) {
        return h('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '50%'
          }
        }, [
          h('span', {
            style: {
              fontSize: '10px',
            }
          }, '-')
        ])
      }

      // 转换为数字
      const ratioNum = typeof ratio === 'number' ? ratio : parseFloat(ratio)
      if (isNaN(ratioNum)) {
        return h('div', {
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '100%'
          }
        }, [
          h('span', {
            style: {
              fontSize: '14px',
            }
          }, '-')
        ])
      }

      // 确保比率在 0-100 之间
      const passRatio = Math.max(0, Math.min(100, ratioNum))
      const failRatio = 100 - passRatio

      // 格式化显示文本
      const ratioStr = passRatio.toFixed(2)

      // 构建进度条的子元素
      const progressBarChildren = []

      // 绿色部分（通过）- 只有当 passRatio > 0 时才显示
      if (passRatio > 0) {
        progressBarChildren.push(
            h('div', {
              style: {
                height: '100%',
                width: `${passRatio}%`,
                backgroundColor: '#18a058',
                transition: 'width 0.3s ease',
                minWidth: passRatio > 0 ? '1px' : '0'
              }
            })
        )
      }
      // 红色部分（失败）- 只有当 failRatio > 0 时才显示
      if (failRatio > 0) {
        progressBarChildren.push(
            h('div', {
              style: {
                height: '100%',
                width: `${failRatio}%`,
                backgroundColor: '#F4511E',
                transition: 'width 0.3s ease',
                minWidth: failRatio > 0 ? '1px' : '0'
              }
            })
        )
      }
      return h('div', {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          justifyContent: 'flex-start'
        }
      }, [
        h('div', {
          style: {
            display: 'flex',
            width: '100px',
            height: '8px',
            borderRadius: '10px',
            overflow: 'hidden',
            backgroundColor: '#F4511E',
            flexShrink: 0,
          }
        }, progressBarChildren),
        h('span', {
          style: {
            fontSize: '14px',
            whiteSpace: 'nowrap',
            minWidth: '60px',
            textAlign: 'left',
            fontWeight: '500'
          }
        }, `${ratioStr}%`)
      ])
    },
  },
  {
    title: '执行状态',
    key: 'case_state',
    width: 100,
    align: 'center',
    render(row) {
      if (row.case_state === true || row.case_state === 'true') {
        return h(NTag, {type: 'success'}, {default: () => '成功'})
      } else if (row.case_state === false || row.case_state === 'false') {
        return h(NTag, {type: 'error'}, {default: () => '失败'})
      }
      return h('span', '-')
    },
  },
  {
    title: '执行时间',
    key: 'case_st_time',
    width: 180,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '消耗时间',
    key: 'case_elapsed',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '任务代码',
    key: 'task_code',
    width: 200,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete({report_id: row.report_id}, false),
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
              default: () => h('div', {}, '确定删除该报告吗?'),
            }
        ),
      ]
    },
  },
]

</script>

<template>
  <CommonPage show-footer title="测试报告">
    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :is-pagination="false"
        :columns="columns"
        :get-data="getReportList"
        :single-line="true"
    >

      <!--  搜索  -->
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
        <QueryBarItem label="报告类型：">
          <NSelect
              v-model:value="queryItems.report_type"
              :options="reportTypeOptions"
              clearable
              placeholder="请选择报告类型"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="执行状态：">
          <NSelect
              v-model:value="queryItems.case_state"
              :options="caseStateOptions"
              clearable
              placeholder="请选择执行状态"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="成功率：">
          <NInput
              v-model:value="queryItems.step_pass_ratio"
              clearable
              type="text"
              placeholder="请输入成功率"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="任务代码：">
          <NInput
              v-model:value="queryItems.task_code"
              clearable
              type="text"
              placeholder="请输入任务代码"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
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


<style scoped>
/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

</style>
