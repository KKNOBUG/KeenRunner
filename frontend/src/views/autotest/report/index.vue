<script setup>
import {h, ref, resolveDirective, withDirectives, computed} from 'vue'
import {NButton, NInput, NPopconfirm, NSelect, NTag, NDrawer, NDrawerContent, NDataTable, NCheckbox, NSpace} from 'naive-ui'

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

// 抽屉相关状态
const drawerVisible = ref(false)
const detailList = ref([])
const loading = ref(false)
const onlyShowFailed = ref(false)
const currentReport = ref(null)

const {
  handleDelete,
} = useCRUD({
  name: '报告',
  doDelete: api.deleteApiReport,
  refresh: () => $table.value?.handleSearch(),
})

// 查看明细
const handleViewDetails = async (row) => {
  currentReport.value = row
  drawerVisible.value = true
  loading.value = true
  try {
    const res = await api.getApiDetailList({
      case_id: row.case_id,
      report_code: row.report_code,
      page: 1,
      page_size: 1000, // 获取所有明细
      state: 0
    })
    if (res?.data) {
      detailList.value = res.data
    } else {
      detailList.value = []
    }
  } catch (error) {
    window.$message?.error?.('查询明细失败')
    detailList.value = []
  } finally {
    loading.value = false
  }
}

// 过滤后的明细列表
const filteredDetailList = computed(() => {
  if (!onlyShowFailed.value) {
    return detailList.value
  }
  return detailList.value.filter(item => item.step_state === false || item.step_state === 'false')
})

// 获取HTTP状态码
const getHttpCode = (item) => {
  if (item.response_body && typeof item.response_body === 'object') {
    return item.response_body.status_code || item.response_body.code || item.response_body.status || '-'
  }
  return '-'
}

// 获取HTTP状态码显示样式
const getHttpCodeTag = (code) => {
  if (!code || code === '-') return {type: 'default', text: '-'}
  const codeNum = parseInt(code)
  if (codeNum >= 200 && codeNum < 300) {
    return {type: 'success', text: `${code} OK`}
  } else if (codeNum >= 400 && codeNum < 500) {
    return {type: 'warning', text: `${code}`}
  } else if (codeNum >= 500) {
    return {type: 'error', text: `${code}`}
  }
  return {type: 'default', text: `${code}`}
}

// 获取请求方法
const getRequestMethod = (item) => {
  // 尝试从 session_variables 中获取（可能存储了请求信息）
  if (item.session_variables && typeof item.session_variables === 'object') {
    if (item.session_variables.request_method) {
      return item.session_variables.request_method
    }
  }
  // 尝试从 response_body 中获取
  if (item.response_body && typeof item.response_body === 'object') {
    if (item.response_body.request_info && item.response_body.request_info.method) {
      return item.response_body.request_info.method
    }
    if (item.response_body.method) {
      return item.response_body.method
    }
  }
  // 如果步骤类型是 api/http，可能需要从其他字段获取
  if (item.step_type === 'api' || item.step_type === 'http') {
    // 默认返回 POST，实际应该从数据中获取
    return 'POST'
  }
  return '-'
}

// 获取URL
const getUrl = (item) => {
  // 尝试从 session_variables 中获取
  if (item.session_variables && typeof item.session_variables === 'object') {
    if (item.session_variables.request_url) {
      return item.session_variables.request_url
    }
  }
  // 尝试从 response_body 中获取
  if (item.response_body && typeof item.response_body === 'object') {
    if (item.response_body.request_info && item.response_body.request_info.url) {
      return item.response_body.request_info.url
    }
    if (item.response_body.url || item.response_body.request_url) {
      return item.response_body.url || item.response_body.request_url
    }
  }
  return '-'
}

// 明细表格列定义
const detailColumns = [
  {
    title: '用例ID',
    key: 'case_id',
    width: 100,
    align: 'center',
  },
  {
    title: '步骤序号',
    key: 'step_no',
    width: 100,
    align: 'center',
  },
  {
    title: '步骤名称',
    key: 'step_name',
    width: 200,
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤标识',
    key: 'step_code',
    width: 200,
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤类型',
    key: 'step_type',
    width: 120,
    align: 'center',
  },
  {
    title: '步骤执行时间',
    key: 'step_st_time',
    width: 180,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤结束时间',
    key: 'step_ed_time',
    width: 180,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤消耗时间',
    key: 'step_elapsed',
    width: 130,
    align: 'center',
    render(row) {
      const elapsed = row.step_elapsed
      if (elapsed) {
        const elapsedNum = parseFloat(elapsed)
        if (!isNaN(elapsedNum)) {
          return h('span', elapsedNum.toFixed(3))
        }
      }
      return h('span', '-')
    },
  },
  {
    title: '步骤错误信息',
    key: 'step_exec_except',
    width: 300,
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.step_exec_except || '-')
    },
  },
  {
    title: '步骤状态',
    key: 'step_state',
    width: 100,
    align: 'center',
    render(row) {
      if (row.step_state === true || row.step_state === 'true') {
        return h(NTag, {type: 'success'}, {default: () => '成功'})
      } else if (row.step_state === false || row.step_state === 'false') {
        return h(NTag, {type: 'error'}, {default: () => '失败'})
      }
      return h('span', '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, {size: 'small'}, [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => {
            // TODO: 实现详情功能
            window.$message?.info?.('详情功能待实现')
          }
        }, {default: () => '详情'}),
        h(NButton, {
          size: 'small',
          type: 'warning',
          onClick: () => {
            // TODO: 实现跳转功能
            window.$message?.info?.('跳转功能待实现')
          }
        }, {
          default: () => '跳转',
          icon: renderIcon('material-symbols:send', {size: 16})
        })
      ])
    },
  },
]

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
    width: 150,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, {size: 'small'}, [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => handleViewDetails(row)
        }, {
          default: () => '查看',
          icon: renderIcon('material-symbols:visibility-outline', {size: 16})
        }),
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
      ])
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

    <!-- 明细抽屉 -->
    <NDrawer v-model:show="drawerVisible" placement="right" :width="1200">
      <NDrawerContent>
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
            <span>报告明细</span>
            <NCheckbox v-model:checked="onlyShowFailed">
              只看错误/失败步骤
            </NCheckbox>
          </div>
        </template>
        <NDataTable
            :columns="detailColumns"
            :data="filteredDetailList"
            :loading="loading"
            :scroll-x="1800"
            :single-line="false"
            striped
        />
      </NDrawerContent>
    </NDrawer>

  </CommonPage>
</template>


<style scoped>
/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

</style>
