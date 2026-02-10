<template>
  <!-- 报告明细抽屉（右侧 40%） -->
  <NDrawer v-model:show="listDrawerVisible" placement="right" width="40%">
    <NDrawerContent :title="title">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: flex-end; width: 100%;">
          <NCheckbox v-model:checked="onlyShowFailed">仅看失败步骤</NCheckbox>
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

  <!-- 步骤详情抽屉（左侧 60%） -->
  <NDrawer v-model:show="detailDrawerVisible" placement="left" width="60%">
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

              <NCard v-if="currentDetail.step_type === '循环结构'" title="循环结构配置" size="small" :bordered="false">
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

              <NCard v-if="currentDetail.step_type === '条件分支'" title="条件分支配置" size="small" :bordered="false">
                <div v-if="stepInfo.conditions && Array.isArray(stepInfo.conditions) && stepInfo.conditions.length > 0">
                  <MonacoEditor
                      :value="formatJson(stepInfo.conditions)"
                      :options="monacoEditorOptions(true)"
                      style="min-height: 200px; height: auto;"
                  />
                </div>
              </NCard>

              <NCard v-if="currentDetail.step_type === '等待控制'" title="等待控制配置" size="small" :bordered="false">
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
              <NCollapse
                  :default-expanded-names="['requestBasic', 'requestHeaders', 'requestParams', 'requestBody', 'requestCode']"
                  arrow-placement="right"
              >
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
                  <pre
                      v-else
                      style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;"
                  >{{ formatRequestHeadersText() }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Params" name="requestParams" v-if="requestParams && Object.keys(requestParams).length > 0">
                  <div v-if="isJsonRequestParams">
                    <MonacoEditor
                        :value="formatJson(requestParams)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 200px; height: auto;"
                    />
                  </div>
                  <pre
                      v-else
                      style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;"
                  >{{ formatJson(requestParams) }}</pre>
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
                      :columns="[{ title: 'Key', key: 'key' }, { title: 'Value', key: 'value' }]"
                      :data="requestFormDataTable"
                      size="small"
                      :bordered="true"
                  />
                  <pre
                      v-else
                      style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;"
                  >{{ requestBodyText }}</pre>
                </NCollapseItem>
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
                  <pre style="white-space: pre-wrap; word-wrap: break-word;">{{ formatJson(currentDetail.response_header) }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Cookies" name="responseCookies" v-if="currentDetail.response_cookie">
                  <pre style="white-space: pre-wrap; word-wrap: break-word;">{{ formatJson(currentDetail.response_cookie) }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Body" name="responseBody">
                  <div v-if="isJsonResponse">
                    <MonacoEditor
                        :value="formatJson(currentDetail.response_body)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 400px; height: auto;"
                    />
                  </div>
                  <NCode v-else :code="formatResponseText()" :language="responseLanguage" show-line-numbers />
                </NCollapseItem>
              </NCollapse>
            </NSpace>
          </NTabPane>

          <!-- 数据提取 -->
          <NTabPane name="extract" tab="数据提取">
            <NDataTable
                v-if="extractVariablesData.length > 0"
                :columns="reportExtractColumns"
                :data="extractVariablesData"
                size="small"
                :bordered="true"
            />
            <NEmpty v-else description="暂无数据提取结果" />
          </NTabPane>

          <!-- 断言结果 -->
          <NTabPane name="assert" tab="断言结果">
            <NDataTable
                v-if="assertValidatorsData.length > 0"
                :columns="reportValidatorColumns"
                :data="assertValidatorsData"
                size="small"
                :bordered="true"
            />
            <NEmpty v-else description="暂无断言结果" />
          </NTabPane>

          <!-- 会话变量 -->
          <NTabPane name="variables" tab="会话变量" v-if="currentDetail.session_variables">
            <div v-if="isJsonSessionVariables">
              <MonacoEditor
                  :value="formatJson(currentDetail.session_variables)"
                  :options="monacoEditorOptions(true)"
                  style="min-height: 500px; height: auto;"
              />
            </div>
            <pre v-else style="white-space: pre-wrap; word-wrap: break-word;">{{
                formatJson(currentDetail.session_variables)
              }}</pre>
          </NTabPane>
        </NTabs>
      </NCard>
      <NEmpty v-else description="暂无详情数据" />
    </NDrawerContent>
  </NDrawer>
</template>

<script setup>
import { computed, h, ref, watch } from 'vue'
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
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import MonacoEditor from '@/components/monaco/index.vue'
import api from '@/api'

const props = defineProps({
  /** v-model 控制报告明细抽屉（右侧）的显示 */
  show: { type: Boolean, default: false },
  /** 当前选中的报告行，需包含 case_id、report_code，用于请求步骤明细 */
  reportRow: { type: Object, default: null },
  /** 抽屉标题 */
  title: { type: String, default: '报告明细' },
})

const emit = defineEmits(['update:show'])

const router = useRouter()

const listDrawerVisible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const detailList = ref([])
const loading = ref(false)
const onlyShowFailed = ref(false)
const detailDrawerVisible = ref(false)
const currentDetail = ref(null)

const stepInfo = computed(() => currentDetail.value?.step || {})

const filteredDetailList = computed(() => {
  if (!onlyShowFailed.value) return detailList.value
  return detailList.value.filter((item) => item.step_state === false || item.step_state === 'false')
})

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

const isJsonResponse = computed(() => {
  if (!currentDetail.value?.response_body) return false
  try {
    const body = currentDetail.value.response_body
    if (typeof body === 'string') JSON.parse(body)
    else if (typeof body === 'object') return true
    return false
  } catch {
    return false
  }
})

const responseLanguage = computed(() => {
  if (!currentDetail.value?.response_header) return 'text'
  const headers = currentDetail.value.response_header
  if (typeof headers === 'object') {
    const ct = headers['content-type'] || headers['Content-Type'] || ''
    if (ct.includes('json')) return 'json'
    if (ct.includes('xml')) return 'xml'
    if (ct.includes('html')) return 'html'
  }
  return 'text'
})

const formatResponseText = () => {
  if (!currentDetail.value) return ''
  if (currentDetail.value.response_text) return currentDetail.value.response_text
  if (currentDetail.value.response_body) return formatJson(currentDetail.value.response_body)
  return ''
}

const monacoEditorOptions = (readOnly = false, language = 'json') => ({
  readOnly,
  language,
  theme: 'vs',
  automaticLayout: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  formatOnPaste: true,
  formatOnType: true,
})

const extractVariablesData = computed(() => {
  if (!currentDetail.value?.extract_variables) return []
  const vars = currentDetail.value.extract_variables
  if (typeof vars === 'object' && !Array.isArray(vars)) {
    return Object.entries(vars).map(([name, value]) => ({
      name,
      source: '-',
      range: '-',
      expr: '-',
      extracted_value: value,
      success: true,
      error: '-',
    }))
  }
  if (Array.isArray(vars)) {
    return vars.map((item) => ({
      name: item.name ?? item.key ?? '-',
      source: item.source ?? '-',
      range: item.range ?? '-',
      expr: item.expr ?? '-',
      extracted_value: item.extracted_value ?? item.value ?? '-',
      success: item.success !== false,
      error: item.error ?? '-',
    }))
  }
  return []
})

const assertValidatorsData = computed(() => {
  if (!currentDetail.value?.assert_validators) return []
  const validators = currentDetail.value.assert_validators
  if (Array.isArray(validators)) {
    return validators.map((v) => ({
      name: v.name ?? '-',
      source: v.source ?? '-',
      expr: v.expr ?? '-',
      actual_value: v.actual_value ?? '-',
      operation: v.operation ?? '-',
      except_value: v.except_value ?? v.expect_value ?? '-',
      success: v.success !== false,
      error: v.error ?? '-',
    }))
  }
  return []
})

const isJsonSessionVariables = computed(() => {
  if (!currentDetail.value?.session_variables) return false
  return typeof currentDetail.value.session_variables === 'object'
})

const reportExtractColumns = [
  { title: '变量名', key: 'name', width: 120 },
  {
    title: '提取来源',
    key: 'source',
    width: 120,
    render: (row) => {
      const map = { 'Response Json': 'Response Json', 'Response Text': 'Response Text', 'Response XML': 'Response XML', 'Response Header': 'Response Header', 'Response Cookie': 'Response Cookie' }
      return map[row.source] || row.source
    },
  },
  { title: '提取范围', key: 'range', width: 120, render: (row) => (row.range === 'ALL' ? '全部提取' : (row.range || '-')) },
  { title: '提取路径', key: 'expr', width: 120, ellipsis: { tooltip: true } },
  {
    title: '提取值',
    key: 'extracted_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.extracted_value === null || row.extracted_value === undefined) return '-'
      const value = typeof row.extracted_value === 'object' ? JSON.stringify(row.extracted_value) : String(row.extracted_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    },
  },
  {
    title: '提取结果',
    key: 'success',
    width: 120,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', round: true, size: 'small' }, { default: () => (row.success ? 'pass' : 'fail') }),
  },
  { title: '错误信息', key: 'error', width: 120, ellipsis: { tooltip: true }, render: (row) => row.error || '-' },
]

const reportValidatorColumns = [
  { title: '断言名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => {
      const map = { 'Response Json': 'responseJson', 'Response Text': 'responseText', 'Response XML': 'responseXml', 'Response Header': 'responseHeader', 'Response Cookie': 'responseCookie', '变量池': '变量池' }
      return map[row.source] || row.source
    },
  },
  { title: '断言路径', key: 'expr', width: 130, ellipsis: { tooltip: true } },
  { title: '结果值', key: 'actual_value', width: 150, ellipsis: { tooltip: true }, render: (row) => (row.actual_value != null ? String(row.actual_value) : '-') },
  { title: '断言方式', key: 'operation', width: 100 },
  { title: '期望值', key: 'expect_value', width: 120, ellipsis: { tooltip: true }, render: (row) => { const v = row.except_value ?? row.expect_value; return v != null ? String(v) : '-'; } },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', round: true, size: 'small' }, { default: () => (row.success ? 'pass' : 'fail') }),
  },
  { title: '错误信息', key: 'error', ellipsis: { tooltip: true }, render: (row) => row.error || '-' },
]

const requestMethod = computed(() => stepInfo.value.request_method || '-')
const requestUrl = computed(() => stepInfo.value.request_url || '-')
const requestHeaders = computed(() => stepInfo.value.request_header)
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
const requestBody = computed(() => stepInfo.value.request_body)
const requestFormData = computed(() => stepInfo.value.request_form_data)
const requestFormUrlencoded = computed(() => stepInfo.value.request_form_urlencoded)
const requestText = computed(() => stepInfo.value.request_text)
const run_code = computed(() => stepInfo.value.code)

const hasResponseInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false
  const hasResponseData =
      !!(currentDetail.value?.response_body) ||
      !!(currentDetail.value?.response_header) ||
      !!(currentDetail.value?.response_text) ||
      !!(currentDetail.value?.response_cookie)
  return isRequestStep && hasResponseData
})

const hasRequestInfo = computed(() => {
  const isRequestStep = stepInfo.value?.step_type?.includes('请求') ?? false
  const hasRequestData =
      !!(requestMethod.value && requestMethod.value !== '-') ||
      !!(requestUrl.value && requestUrl.value !== '-') ||
      !!requestHeaders.value ||
      !!requestBody.value ||
      !!requestFormData.value ||
      !!requestFormUrlencoded.value ||
      !!requestText.value ||
      !!run_code.value
  return isRequestStep && hasRequestData
})

const hasRequestBody = computed(() => !!(requestBody.value || requestFormData.value || requestFormUrlencoded.value || requestText.value))

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
          .map(([k, v]) => `${k}=${v}`)
          .join('&')
    }
    return String(requestFormUrlencoded.value)
  }
  return ''
})

const isJsonRequestHeaders = computed(() => requestHeaders.value && typeof requestHeaders.value === 'object')
const isJsonRequestParams = computed(() => requestParams.value && typeof requestParams.value === 'object' && Object.keys(requestParams.value).length > 0)
const isJsonRequestBody = computed(() => requestBody.value && typeof requestBody.value === 'object')

const requestFormDataTable = computed(() => {
  if (!requestFormData.value) return []
  if (typeof requestFormData.value === 'object') {
    return Object.entries(requestFormData.value).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value),
    }))
  }
  return []
})

const formatRequestHeadersText = () => {
  if (!requestHeaders.value) return ''
  if (typeof requestHeaders.value === 'object') {
    return Object.entries(requestHeaders.value)
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n')
  }
  return String(requestHeaders.value)
}

const getMethodTagType = (method) => {
  if (!method || method === '-') return 'default'
  const u = method.toUpperCase()
  if (u === 'GET') return 'info'
  if (u === 'POST') return 'success'
  if (u === 'PUT') return 'warning'
  if (u === 'DELETE') return 'error'
  return 'default'
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
    width: 100,
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

watch(
    () => [props.show, props.reportRow],
    async ([show, row]) => {
      if (!show || !row?.case_id || !row?.report_code) {
        if (!show) {
          detailList.value = []
          currentDetail.value = null
          detailDrawerVisible.value = false
        }
        return
      }
      loading.value = true
      try {
        const res = await api.getApiDetailList({
          case_id: row.case_id,
          report_code: row.report_code,
          page: 1,
          page_size: 1000,
          state: 0,
        })
        detailList.value = res?.data ?? []
      } catch (e) {
        window.$message?.error?.(e?.message || e?.data?.message || '查询明细失败')
        detailList.value = []
      } finally {
        loading.value = false
      }
    },
    { immediate: true }
)
</script>

<style scoped>
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
