<script setup>
import {computed, h, ref, resolveDirective, withDirectives} from 'vue'
import {
  NButton,
  NCard,
  NCheckbox,
  NCode,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText
} from 'naive-ui'
import {useRouter} from 'vue-router'
import MonacoEditor from '@/components/monaco/index.vue'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'

defineOptions({name: '测试报告'})

const router = useRouter()

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

// 抽屉相关状态
const drawerVisible = ref(false)
const detailList = ref([])
const loading = ref(false)
const onlyShowFailed = ref(false)
const currentReport = ref(null)

// 详情抽屉相关状态
const detailDrawerVisible = ref(false)
const currentDetail = ref(null)

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

// 格式化JSON
const formatJson = (data) => {
  if (!data) return ''
  if (typeof data === 'string') {
    try {
      return JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      return data
    }
  }
  return JSON.stringify(data, null, 2)
}

// 判断响应是否为JSON
const isJsonResponse = computed(() => {
  if (!currentDetail.value?.response_body) return false
  try {
    const body = currentDetail.value.response_body
    if (typeof body === 'string') {
      JSON.parse(body)
    } else if (typeof body === 'object') {
      return true
    }
    return false
  } catch {
    return false
  }
})

// 响应语言类型
const responseLanguage = computed(() => {
  if (!currentDetail.value?.response_header) return 'text'
  const headers = currentDetail.value.response_header
  if (typeof headers === 'object') {
    const contentType = headers['content-type'] || headers['Content-Type'] || ''
    if (contentType.includes('json')) return 'json'
    if (contentType.includes('xml')) return 'xml'
    if (contentType.includes('html')) return 'html'
  }
  return 'text'
})

// 格式化响应文本
const formatResponseText = () => {
  if (!currentDetail.value) return ''
  if (currentDetail.value.response_text) {
    return currentDetail.value.response_text
  }
  if (currentDetail.value.response_body) {
    return formatJson(currentDetail.value.response_body)
  }
  return ''
}

// Monaco编辑器配置
const monacoEditorOptions = (readOnly = false, language = 'json') => ({
  readOnly,
  language,
  theme: 'vs',
  automaticLayout: true,
  minimap: {enabled: false},
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  formatOnPaste: true,
  formatOnType: true
})

// 提取变量数据
const extractVariablesData = computed(() => {
  if (!currentDetail.value?.extract_variables) return []
  const vars = currentDetail.value.extract_variables
  if (typeof vars === 'object' && !Array.isArray(vars)) {
    return Object.entries(vars).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
    }))
  }
  return []
})

// 断言验证器数据
const assertValidatorsData = computed(() => {
  if (!currentDetail.value?.assert_validators) return []
  const validators = currentDetail.value.assert_validators
  if (Array.isArray(validators)) {
    return validators.map((v, index) => ({
      key: `断言 ${index + 1}`,
      value: typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)
    }))
  }
  return []
})

// 判断会话变量是否为JSON
const isJsonSessionVariables = computed(() => {
  if (!currentDetail.value?.session_variables) return false
  return typeof currentDetail.value.session_variables === 'object'
})

// 请求信息相关计算属性
const stepInfo = computed(() => {
  return currentDetail.value?.step || {}
})

const requestMethod = computed(() => {
  return stepInfo.value.request_method || '-'
})

const requestUrl = computed(() => {
  return stepInfo.value.request_url || '-'
})

const requestHeaders = computed(() => {
  return stepInfo.value.request_header
})

const requestParams = computed(() => {
  const params = stepInfo.value.request_params
  if (typeof params === 'string') {
    try {
      return JSON.parse(params)
    } catch {
      return {}
    }
  }
  return params || {}
})

const requestBody = computed(() => {
  return stepInfo.value.request_body
})

const requestFormData = computed(() => {
  return stepInfo.value.request_form_data
})

const requestFormUrlencoded = computed(() => {
  return stepInfo.value.request_form_urlencoded
})

const requestText = computed(() => {
  return stepInfo.value.request_text
})

const run_code = computed(() => {
  return stepInfo.value.code
})

const hasResponseInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false;
  const hasResponseData = !!(currentDetail.value?.response_body) ||
      !!(currentDetail.value?.response_header) ||
      !!(currentDetail.value?.response_text) ||
      !!(currentDetail.value?.response_cookie)
  return isRequestStep && hasResponseData;
})

const hasRequestInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false;
  const hasRequestData = !!(requestMethod.value && requestMethod.value !== '-') ||
      !!(requestUrl.value && requestUrl.value !== '-') ||
      !!requestHeaders.value ||
      !!requestBody.value ||
      !!requestFormData.value ||
      !!requestFormUrlencoded.value ||
      !!requestText.value ||
      !!run_code.value;
  return isRequestStep && hasRequestData;
})

const hasRequestBody = computed(() => {
  return !!(requestBody.value || requestFormData.value || requestFormUrlencoded.value || requestText.value)
})

const requestBodyType = computed(() => {
  if (requestBody.value) return 'JSON'
  if (requestFormData.value) return 'Form Data'
  if (requestFormUrlencoded.value) return 'x-www-form-urlencoded'
  if (requestText.value) return 'Text'
  return 'None'
})

const requestBodyText = computed(() => {
  if (requestText.value) return requestText.value
  if (requestFormUrlencoded.value) {
    if (typeof requestFormUrlencoded.value === 'object') {
      return Object.entries(requestFormUrlencoded.value)
          .map(([key, value]) => `${key}=${value}`)
          .join('&')
    }
    return String(requestFormUrlencoded.value)
  }
  return ''
})

const isJsonRequestHeaders = computed(() => {
  return requestHeaders.value && typeof requestHeaders.value === 'object'
})

const isJsonRequestParams = computed(() => {
  return requestParams.value && typeof requestParams.value === 'object' && Object.keys(requestParams.value).length > 0
})

const isJsonRequestBody = computed(() => {
  return requestBody.value && typeof requestBody.value === 'object'
})

const requestFormDataTable = computed(() => {
  if (!requestFormData.value) return []
  if (typeof requestFormData.value === 'object') {
    return Object.entries(requestFormData.value).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }))
  }
  return []
})

const formatRequestHeadersText = () => {
  if (!requestHeaders.value) return ''
  if (typeof requestHeaders.value === 'object') {
    return Object.entries(requestHeaders.value)
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n')
  }
  return String(requestHeaders.value)
}

const getMethodTagType = (method) => {
  if (!method || method === '-') return 'default'
  const upperMethod = method.toUpperCase()
  if (upperMethod === 'GET') return 'info'
  if (upperMethod === 'POST') return 'success'
  if (upperMethod === 'PUT') return 'warning'
  if (upperMethod === 'DELETE') return 'error'
  return 'default'
}

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
    title: '步骤序号',
    key: 'step_no',
    width: 40,
    align: 'center',
  },
  {
    title: '步骤名称',
    key: 'step_name',
    width: 100,
    ellipsis: {tooltip: true},
  },
  {
    title: '步骤类型',
    key: 'step_type',
    width: 60,
    align: 'center',
  },
  {
    title: '步骤状态',
    key: 'step_state',
    width: 40,
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
    title: '步骤消耗时间',
    key: 'step_elapsed',
    width: 60,
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
    width: 200,
    ellipsis: {tooltip: true},
    render(row) {
      return h('span', row.step_exec_except || '-')
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 30,
    align: 'center',
    fixed: 'right',
    render(row) {
      return h(NSpace, {size: 'small'}, [
        h(NButton, {
          size: 'small',
          type: 'primary',
          onClick: () => {
            currentDetail.value = row
            detailDrawerVisible.value = true
          }
        }, {default: () => '详情'}),
        h(NButton, {
          size: 'small',
          type: 'warning',
          onClick: () => {
            router.push({
              path: '/autotest/api',
              query: {
                case_id: row.case_id
              }
            })
          }
        }, {default: () => '跳转'})
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
    <NDrawer v-model:show="drawerVisible" placement="right" width="50%">
      <NDrawerContent>
        <template #header>
          <div style="display: flex; align-items: center; justify-content: flex-end; width: 100%;">
            <NCheckbox v-model:checked="onlyShowFailed">
              仅看失败步骤
            </NCheckbox>
          </div>
        </template>
        <NDataTable
            :columns="detailColumns"
            :data="filteredDetailList"
            :loading="loading"
            :scroll-x="1200"
            :single-line="false"
            striped
        />
      </NDrawerContent>
    </NDrawer>

    <!-- 详情抽屉 -->
    <NDrawer v-model:show="detailDrawerVisible" placement="left" width="50%">
      <NDrawerContent>
        <NCard v-if="currentDetail" :bordered="false" style="width: 100%;">
          <template #header-extra>
            <NSpace align="center">
              <NTag :type="currentDetail.step_state ? 'success' : 'error'" round size="small">
                {{ currentDetail.step_state ? '成功' : '失败' }}
              </NTag>
              <NTag round size="small">类型: {{ currentDetail.step_type }}</NTag>
              <NTag round size="small">耗时: {{ currentDetail.step_elapsed || '-' }}s</NTag>
            </NSpace>
          </template>
          <NTabs type="line" animated>
            <!-- 基本信息 -->
            <NTabPane name="basic" tab="基本信息">
              <NSpace vertical :size="16">
                <NCard title="步骤信息" size="small" :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">用例ID：</div>
                      <div class="step-info-value">{{ currentDetail.case_id || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">用例标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.case_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">报告标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.report_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤标识：</div>
                      <div class="step-info-value">
                        <NText copyable>{{ currentDetail.step_code || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤序号：</div>
                      <div class="step-info-value">{{ currentDetail.step_no || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤状态：</div>
                      <div class="step-info-value">
                        <NTag :type="currentDetail.step_state ? 'success' : 'error'">
                          {{ currentDetail.step_state ? '成功' : '失败' }}
                        </NTag>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤名称：</div>
                      <div class="step-info-value">
                        <NText strong>{{ currentDetail.step_name || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">步骤类型：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ currentDetail.step_type || '-' }}</NTag>
                      </div>
                    </div>
                    <div class="step-info-row" v-if="currentDetail.num_cycles">
                      <div class="step-info-label">循环次数：</div>
                      <div class="step-info-value">
                        <NTag type="warning">第 {{ currentDetail.num_cycles }} 次循环</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <!-- 循环结构额外信息 -->
                <NCard v-if="currentDetail.step_type === '循环结构'" title="循环结构配置" size="small"
                       :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">最大循环次数：</div>
                      <div class="step-info-value">{{ stepInfo.loop_maximums || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环间隔时间：</div>
                      <div class="step-info-value">{{ stepInfo.loop_interval ? `${stepInfo.loop_interval}s` : '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环对象来源：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iterable || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">索引变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_idx || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">键的变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_key || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">数据变量名称：</div>
                      <div class="step-info-value">{{ stepInfo.loop_iter_val || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">错误处理策略：</div>
                      <div class="step-info-value">
                        <NTag type="warning">{{ stepInfo.loop_on_error || '-' }}</NTag>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">循环超时时间：</div>
                      <div class="step-info-value">{{ stepInfo.loop_timeout ? `${stepInfo.loop_timeout}s` : '-' }}</div>
                    </div>
                  </div>
                </NCard>

                <!-- 条件分支额外信息 -->
                <NCard v-if="currentDetail.step_type === '条件分支'" title="条件分支配置" size="small"
                       :bordered="false">
                      <div
                          v-if="stepInfo.conditions && Array.isArray(stepInfo.conditions) && stepInfo.conditions.length > 0">
                        <MonacoEditor
                            :value="formatJson(stepInfo.conditions)"
                            :options="monacoEditorOptions(true)"
                            style="min-height: 200px; height: auto;"
                        />
                      </div>
                </NCard>

                <!-- 等待控制额外信息 -->
                <NCard v-if="currentDetail.step_type === '等待控制'" title="等待控制配置" size="small"
                       :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">等待时间：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ stepInfo.wait ? `${stepInfo.wait}s` : '-' }}</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <NCard title="执行时间" size="small" :bordered="false">
                  <div class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">开始时间：</div>
                      <div class="step-info-value">{{ currentDetail.step_st_time || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">结束时间：</div>
                      <div class="step-info-value">{{ currentDetail.step_ed_time || '-' }}</div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">消耗时间：</div>
                      <div class="step-info-value">
                        <NTag type="info">{{ currentDetail.step_elapsed ? `${currentDetail.step_elapsed}s` : '-' }}</NTag>
                      </div>
                    </div>
                  </div>
                </NCard>

                <NCard title="执行日志" size="small" :bordered="false">
                <NCollapse :default-expanded-names="['errorInfo', 'execLogger']" arrow-placement="right">
                  <NCollapseItem title="错误日志" name="errorInfo" v-if="currentDetail.step_exec_except">
                      <pre
                          style="white-space: pre-wrap; word-wrap: break-word; color: #d03050; background: #fff5f5; padding: 12px; border-radius: 4px; border: 1px solid #ffccc7;">{{
                          currentDetail.step_exec_except
                        }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="普通日志" name="execLogger" v-if="currentDetail.step_exec_logger">
                      <pre
                          style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0;">{{
                          currentDetail.step_exec_logger
                        }}</pre>
                  </NCollapseItem>
                </NCollapse>
                </NCard>
              </NSpace>

            </NTabPane>

            <!-- 请求信息 -->
            <NTabPane name="request" tab="请求信息" v-if="hasRequestInfo">
              <NSpace vertical :size="16">
                <NCollapse :default-expanded-names="['requestBasic', 'requestHeaders', 'requestBody']"
                           arrow-placement="right">
                  <NCollapseItem title="Basic" name="requestBasic">
                    <NDescriptions bordered :column="2" size="small">
                      <NDescriptionsItem label="请求方法">
                        <NTag :type="getMethodTagType(requestMethod)" size="small">{{ requestMethod || '-' }}</NTag>
                      </NDescriptionsItem>
                      <NDescriptionsItem label="请求URL">
                        <NText copyable style="font-family: monospace; font-size: 12px;">{{ requestUrl || '-' }}</NText>
                      </NDescriptionsItem>
                    </NDescriptions>
                  </NCollapseItem>
                  <NCollapseItem title="Headers" name="requestHeaders" v-if="requestHeaders">
                    <div v-if="isJsonRequestHeaders">
                      <MonacoEditor
                          :value="formatJson(requestHeaders)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 200px; height: auto;"
                      />
                    </div>
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        formatRequestHeadersText()
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Params" name="requestParams"
                                 v-if="requestParams && Object.keys(requestParams).length > 0">
                    <div v-if="isJsonRequestParams">
                      <MonacoEditor
                          :value="formatJson(requestParams)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 200px; height: auto;"
                      />
                    </div>
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        formatJson(requestParams)
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem :title="`Body (${requestBodyType})`" name="requestBody" v-if="hasRequestBody">
                    <div v-if="isJsonRequestBody">
                      <MonacoEditor
                          :value="formatJson(requestBody)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 400px; height: auto;"
                      />
                    </div>
                    <NDataTable
                        v-else-if="requestFormData"
                        :columns="[{title: 'Key', key: 'key'}, {title: 'Value', key: 'value'}]"
                        :data="requestFormDataTable"
                        size="small"
                        :bordered="true"
                    />
                    <pre v-else
                         style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;">{{
                        requestBodyText
                      }}</pre>
                  </NCollapseItem>
                  <!-- Python代码 -->
                  <NCollapseItem title="Code (Python)" name="requestCode"
                                 v-if="currentDetail.step_type === '执行代码请求(Python)' && stepInfo.code">
                    <MonacoEditor
                        :value="stepInfo.code"
                        :options="monacoEditorOptions(true, 'python')"
                        style="min-height: 400px; height: auto;"
                    />
                  </NCollapseItem>
                </NCollapse>
              </NSpace>
            </NTabPane>

            <!-- 响应信息 -->
            <NTabPane name="response" tab="响应信息" v-if="hasResponseInfo">
              <NSpace vertical :size="16">
                <NCollapse :default-expanded-names="['responseHeaders', 'responseBody']" arrow-placement="right">
                  <NCollapseItem title="Headers" name="responseHeaders" v-if="currentDetail.response_header">
                      <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
                          formatJson(currentDetail.response_header)
                        }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Cookies" name="responseCookies" v-if="currentDetail.response_cookie">
                    <pre style="white-space: pre-wrap; word-wrap: break-word;">{{
                        formatJson(currentDetail.response_header)
                      }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="Body" name="responseBody">
                    <div v-if="isJsonResponse">
                      <MonacoEditor
                          :value="formatJson(currentDetail.response_body)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 400px; height: auto;"
                      />
                    </div>
                    <NCode
                        v-else
                        :code="formatResponseText()"
                        :language="responseLanguage"
                        show-line-numbers
                    />
                  </NCollapseItem>
                </NCollapse>
              </NSpace>
            </NTabPane>

            <!-- 数据提取 -->
            <NTabPane name="extract" tab="数据提取" v-if="currentDetail.extract_variables">
              <NDataTable
                  v-if="extractVariablesData.length > 0"
                  :columns="[{title: '变量名', key: 'key'}, {title: '值', key: 'value'}]"
                  :data="extractVariablesData"
                  size="small"
                  :bordered="true"
              />
              <NEmpty v-else description="暂无数据提取结果"/>
            </NTabPane>

            <!-- 断言结果 -->
            <NTabPane name="assert" tab="断言结果" v-if="currentDetail.assert_validators">
              <NDataTable
                  v-if="assertValidatorsData.length > 0"
                  :columns="[{title: '断言项', key: 'key', width: 150}, {title: '结果', key: 'value'}]"
                  :data="assertValidatorsData"
                  size="small"
                  :bordered="true"
              />
              <NEmpty v-else description="暂无断言结果"/>
            </NTabPane>

            <!-- 会话变量 -->
            <NTabPane name="variables" tab="会话变量" v-if="currentDetail.session_variables">
              <div v-if="isJsonSessionVariables">
                <MonacoEditor
                    :value="formatJson(currentDetail.session_variables)"
                    :options="monacoEditorOptions(true)"
                    style="min-height: 400px; height: auto;"
                />
              </div>
              <pre v-else style="white-space: pre-wrap; word-wrap: break-word;">{{
                  formatJson(currentDetail.session_variables)
                }}</pre>
            </NTabPane>
          </NTabs>
        </NCard>
        <NEmpty v-else description="暂无详情数据"/>
      </NDrawerContent>
    </NDrawer>

  </CommonPage>
</template>


<style scoped>
/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

/* 步骤信息两列布局 */
.step-info-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-info-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 16px;
  align-items: center;
}

.step-info-label {
  font-size: 14px;
  font-weight: bold;
  color: #666;
  flex-shrink: 0;
}

.step-info-value {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  word-break: break-all;
}

</style>

