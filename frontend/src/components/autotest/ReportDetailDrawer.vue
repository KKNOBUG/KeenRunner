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
                    <div class="step-info-value">{{ currentDetail.loop_maximums || '-' }}</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环间隔时间：</div>
                    <div class="step-info-value">{{ currentDetail.loop_interval ? `${currentDetail.loop_interval}s` : '-' }}</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环对象来源：</div>
                    <div class="step-info-value">{{ currentDetail.loop_iterable || '-' }}</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环索引（固定）：</div>
                    <div class="step-info-value">loop_index</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环键名（固定，字典循环）：</div>
                    <div class="step-info-value">loop_key</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环数据（固定）：</div>
                    <div class="step-info-value">loop_value</div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">错误处理策略：</div>
                    <div class="step-info-value">
                      <NTag type="warning">{{ currentDetail.loop_on_error || '-' }}</NTag>
                    </div>
                  </div>
                  <div class="step-info-row">
                    <div class="step-info-label">循环超时时间：</div>
                    <div class="step-info-value">{{ currentDetail.loop_timeout ? `${currentDetail.loop_timeout}s` : '-' }}</div>
                  </div>
                </div>
              </NCard>

              <NCard v-if="currentDetail.step_type === '条件分支'" title="条件分支配置" size="small" :bordered="false">
                <div v-if="detailConditionsSnapshot">
                  <MonacoEditor
                      :value="formatJson(detailConditionsSnapshot)"
                      :options="monacoEditorOptions(true)"
                      style="min-height: 200px; height: auto;"
                  />
                </div>
                <NEmpty v-else description="本步明细未记录 conditions 快照" size="small" />
              </NCard>

              <NCard v-if="currentDetail.step_type === '等待控制'" title="等待控制配置" size="small" :bordered="false">
                <div class="step-info-grid">
                  <div class="step-info-row">
                    <div class="step-info-label">等待时间：</div>
                    <div class="step-info-value">
                      <NTag type="info">{{ currentDetail.wait != null ? `${currentDetail.wait}s` : '-' }}</NTag>
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
                  <div class="step-info-row" v-if="currentDetail.response_elapsed != null && currentDetail.response_elapsed !== ''">
                    <div class="step-info-label">响应耗时：</div>
                    <div class="step-info-value">
                      <NTag type="info">{{ currentDetail.response_elapsed }}s</NTag>
                    </div>
                  </div>
                </div>
              </NCard>

              <NCard v-if="currentDetail.dataset_name" title="参数化驱动" size="small" :bordered="false">
                <div class="step-info-grid">
                  <div class="step-info-row">
                    <div class="step-info-label">数据集名称：</div>
                    <div class="step-info-value">{{ currentDetail.dataset_name }}</div>
                  </div>
                  <div class="step-info-row" v-if="currentDetail.dataset_snapshot && typeof currentDetail.dataset_snapshot === 'object'">
                    <div class="step-info-label">数据快照：</div>
                    <div class="step-info-value" style="width: 100%;">
                      <MonacoEditor
                          :value="formatJson(currentDetail.dataset_snapshot)"
                          :options="monacoEditorOptions(true)"
                          style="min-height: 120px; height: auto;"
                      />
                    </div>
                  </div>
                </div>
              </NCard>

              <NCard title="执行日志" size="small" :bordered="false">
                <template v-if="!hasAnyExecutionLogLines">
                  <NEmpty description="暂无执行日志" />
                </template>
                <NCollapse
                    v-else
                    :default-expanded-names="['errorInfo', 'execLogger']"
                    arrow-placement="right"
                >
                  <NCollapseItem title="错误日志" name="errorInfo" v-if="currentDetail.step_exec_except">
                    <pre
                        style="white-space: pre-wrap; word-wrap: break-word; color: #d03050; background: #fff5f5; padding: 12px; border-radius: 4px; border: 1px solid #ffccc7;"
                    >{{ currentDetail.step_exec_except }}</pre>
                  </NCollapseItem>
                  <NCollapseItem title="普通日志" name="execLogger" v-if="executionNormalLines.length">
                    <NSpace vertical :size="12">
                      <pre
                          v-for="(log, index) in executionNormalLines"
                          :key="'exec-logger-' + index"
                          class="log-item"
                      >{{ log }}</pre>
                    </NSpace>
                  </NCollapseItem>
                </NCollapse>
              </NCard>
            </NSpace>
          </NTabPane>

          <!-- 请求信息（优先展示明细中的实际请求，与后端一致） -->
          <NTabPane name="request" tab="请求信息" v-if="hasRequestInfo">
            <NSpace vertical :size="16">
              <NCollapse
                  :default-expanded-names="['requestBasic', 'requestHeaders', 'requestParams', 'requestBody', 'requestFormFile', 'requestCode', 'requestDatabase']"
                  arrow-placement="right"
              >
                <NCollapseItem
                    title="Basic"
                    name="requestBasic"
                    v-if="isReportHttpStep || isReportTcpStep || isReportDatabaseStep"
                >
                  <div v-if="isReportHttpStep" class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">请求方法：</div>
                      <div class="step-info-value">
                        <NTag :type="getMethodTagType(requestMethod)" size="small">{{ requestMethod || '-' }}</NTag>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">请求URL：</div>
                      <div class="step-info-value">
                        <NText copyable style="font-family: monospace; font-size: 12px;">{{ requestUrl || '-' }}</NText>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="isReportTcpStep" class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">请求地址：</div>
                      <div class="step-info-value">
                        <NText copyable style="font-family: monospace; font-size: 12px;">{{ requestUrl || '-' }}</NText>
                      </div>
                    </div>
                    <div class="step-info-row">
                      <div class="step-info-label">请求端口：</div>
                      <div class="step-info-value">
                        <NTag type="info" size="small">{{ requestPort || '-' }}</NTag>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="isReportDatabaseStep" class="step-info-grid">
                    <div class="step-info-row">
                      <div class="step-info-label">查到即止：</div>
                      <div class="step-info-value">
                        <NTag :type="databaseSearchedForReport === true ? 'success' : 'default'" size="small">
                          {{ databaseSearchedLabel }}
                        </NTag>
                      </div>
                    </div>
                  </div>
                </NCollapseItem>
                <NCollapseItem title="Headers" name="requestHeaders" v-if="normalizedRequestHeaders != null">
                  <div v-if="isObjectRequestHeaders">
                    <MonacoEditor
                        :value="formatJson(normalizedRequestHeaders)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 200px; height: auto;"
                    />
                  </div>
                  <pre
                      v-else
                      style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;"
                  >{{ formatRequestHeadersText() }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Params" name="requestParams" v-if="normalizedRequestParams && Object.keys(normalizedRequestParams).length > 0">
                  <div v-if="isObjectRequestParams">
                    <MonacoEditor
                        :value="formatJson(normalizedRequestParams)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 200px; height: auto;"
                    />
                  </div>
                  <pre
                      v-else
                      style="white-space: pre-wrap; word-wrap: break-word; background: #f5f5f5; padding: 12px; border-radius: 4px;"
                  >{{ formatJson(normalizedRequestParams) }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Form File" name="requestFormFile" v-if="requestFormFileTable.length > 0">
                  <NDataTable
                      :columns="[{ title: 'Key', key: 'key' }, { title: 'Value', key: 'value' }]"
                      :data="requestFormFileTable"
                      size="small"
                      :bordered="true"
                  />
                </NCollapseItem>
                <NCollapseItem :title="`Body (${requestBodyType})`" name="requestBody" v-if="hasRequestBody">
                  <div v-if="isJsonRequestBody">
                    <MonacoEditor
                        :value="formatJson(requestBody)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 500px; height: auto;"
                    />
                  </div>
                  <NDataTable
                      v-else-if="requestFormDataTable.length > 0"
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

                <NCollapseItem title="Code (Python)" name="requestCode" v-if="isReportPythonStep && reportPythonCodeFromDetail">
                  <MonacoEditor
                      :value="reportPythonCodeFromDetail"
                      :options="monacoEditorOptions(true, 'python')"
                      style="min-height: 500px; height: auto;"
                  />
                </NCollapseItem>
                <NCollapseItem title="Database" name="requestDatabase" v-if="databaseOperatesForReport?.length">
                  <MonacoEditor
                      :value="formatJson(databaseOperatesForReport)"
                      :options="monacoEditorOptions(true)"
                      style="min-height: 500px; height: auto;"
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
                  <MonacoEditor
                      :value="formatJson(currentDetail.response_header)"
                      :options="monacoEditorOptions(true)"
                      style="min-height: 200px; height: auto;"
                  />
                </NCollapseItem>
                <NCollapseItem title="Cookies" name="responseCookies" v-if="currentDetail.response_cookie">
                  <pre style="white-space: pre-wrap; word-wrap: break-word;">{{ formatJson(currentDetail.response_cookie) }}</pre>
                </NCollapseItem>
                <NCollapseItem title="Body" name="responseBody">
                  <div v-if="isJsonResponse">
                    <MonacoEditor
                        :value="formatJson(currentDetail.response_body)"
                        :options="monacoEditorOptions(true)"
                        style="min-height: 500px; height: auto;"
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
                :scroll-x="2000"
                :bordered="false"
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
                :scroll-x="2000"
                :bordered="false"
            />
            <NEmpty v-else description="暂无断言结果" />
          </NTabPane>

          <!-- 会话变量 -->
          <NTabPane name="variables" tab="会话变量" v-if="currentDetail.session_variables">
            <div v-if="isJsonSessionVariables">
              <MonacoEditor
                  :value="formatJson(currentDetail.session_variables)"
                  :options="monacoEditorOptions(true)"
                  style="min-height: 700px; height: auto;"
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

/** 明细表 code：本次执行使用的 Python 代码快照（krun_autotest_api_details.code） */
const reportPythonCodeFromDetail = computed(() => {
  const c = currentDetail.value?.code
  if (c == null) return ''
  const s = String(c).trim()
  return s
})

/** 本步执行快照中的 conditions（明细表 krun_autotest_api_details），非步骤定义表 */
const detailConditionsSnapshot = computed(() => {
  const c = currentDetail.value?.conditions
  if (c && typeof c === 'object' && !Array.isArray(c)) return c
  return null
})

/** 普通执行日志：后端为 list[str]，与 HTTP 调试「执行日志」Tab 一致逐条 pre.log-item 展示 */
const normalizeLoggerLines = (raw) => {
  if (raw == null || !Array.isArray(raw)) return []
  return raw.map((x) => String(x)).filter((line) => line.length > 0)
}

const executionNormalLines = computed(() =>
    normalizeLoggerLines(currentDetail.value?.step_exec_logger)
)

const hasAnyExecutionLogLines = computed(
    () =>
        !!(currentDetail.value?.step_exec_except && String(currentDetail.value.step_exec_except).trim()) ||
        executionNormalLines.value.length > 0
)

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
      scope: '-',
      expr: '-',
      extract_value: value,
      success: true,
      error: '-',
    }))
  }
  if (Array.isArray(vars)) {
    return vars.map((item) => {
      const s = item.scope
      return {
        name: item.name ?? item.key ?? '-',
        source: item.source ?? '-',
        scope: s !== undefined && s !== null && s !== '' ? s : '-',
        expr: item.expr ?? '-',
        extract_value: item.extract_value ?? item.value ?? '-',
        success: item.success !== false,
        error: item.error ?? '-',
      }
    })
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
  { title: '变量名', key: 'name'},
  {
    title: '提取来源',
    key: 'source',
    render: (row) => {
      const map = { 'Response Json': 'Response Json', 'Response Text': 'Response Text', 'Response XML': 'Response XML', 'Response Header': 'Response Header', 'Response Cookie': 'Response Cookie' }
      return map[row.source] || row.source
    },
  },
  { title: '提取范围', key: 'scope', render: (row) => {
      const s = row.scope
      return s === 'ALL' ? '全部提取' : (s && s !== '-' ? s : '-')
    } },
  { title: '提取路径', key: 'expr',  ellipsis: { tooltip: true } },
  {
    title: '提取值',
    key: 'extract_value',
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.extract_value === null || row.extract_value === undefined) return '-'
      const value = typeof row.extract_value === 'object' ? JSON.stringify(row.extract_value) : String(row.extract_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    },
  },
  {
    title: '提取结果',
    key: 'success',
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', round: true, size: 'small' }, { default: () => (row.success ? 'pass' : 'fail') }),
  },
  { title: '错误信息', key: 'error', ellipsis: { tooltip: true }, render: (row) => row.error || '-' },
]

const reportValidatorColumns = [
  { title: '断言名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '断言对象',
    key: 'source',
    render: (row) => {
      const map = { 'Response Json': 'responseJson', 'Response Text': 'responseText', 'Response XML': 'responseXml', 'Response Header': 'responseHeader', 'Response Cookie': 'responseCookie', '变量池': '变量池' }
      return map[row.source] || row.source
    },
  },
  { title: '断言路径', key: 'expr', ellipsis: { tooltip: true } },
  { title: '实际值', key: 'actual_value', ellipsis: { tooltip: true }, render: (row) => (row.actual_value != null ? String(row.actual_value) : '-') },
  { title: '断言方式', key: 'operation', },
  { title: '期望值', key: 'expect_value', ellipsis: { tooltip: true }, render: (row) => { const v = row.except_value ?? row.expect_value; return v != null ? String(v) : '-'; } },
  {
    title: '断言结果',
    key: 'success',
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', round: true, size: 'small' }, { default: () => (row.success ? 'pass' : 'fail') }),
  },
  { title: '错误信息', key: 'error', ellipsis: { tooltip: true }, render: (row) => row.error || '-' },
]

// 报告页仅展示明细表中的「实际发出的请求」字段，不回退到步骤定义表。
function normalizeRequestField (val) {
  if (val == null) return null
  if (Array.isArray(val)) {
    const obj = {}
    for (const item of val) {
      if (item && typeof item === 'object' && item.key !== undefined) {
        obj[item.key] = item.value
      }
    }
    return Object.keys(obj).length ? obj : null
  }
  if (typeof val === 'string') {
    try {
      const parsed = JSON.parse(val)
      return normalizeRequestField(parsed)
    } catch {
      return null
    }
  }
  return typeof val === 'object' ? val : null
}

const databaseOperatesForReport = computed(() => {
  const d = currentDetail.value
  if (!d) return null
  const fromDetail = d.database_operates
  if (Array.isArray(fromDetail) && fromDetail.length) return fromDetail
  return null
})

const databaseSearchedForReport = computed(() => {
  const d = currentDetail.value
  if (!d) return null
  if (d.database_searched != null) return !!d.database_searched
  return null
})

const databaseSearchedLabel = computed(() => {
  const v = databaseSearchedForReport.value
  if (v === null || v === undefined) return '-'
  return v ? '是' : '否'
})

const reportStepType = computed(() => currentDetail.value?.step_type || '')
const isReportHttpStep = computed(() => reportStepType.value === 'HTTP请求')
const isReportTcpStep = computed(() => reportStepType.value === 'TCP请求')
const isReportDatabaseStep = computed(() => reportStepType.value === '数据库请求')
const isReportPythonStep = computed(() => {
  const t = reportStepType.value
  return t === '代码请求(Python)'
})

const requestMethod = computed(() => {
  const d = currentDetail.value
  const m = d?.request_method
  if (m != null && String(m).trim() !== '') return m
  return '-'
})
const requestUrl = computed(() => {
  const d = currentDetail.value
  const u = d?.request_url
  if (u != null && String(u).trim() !== '') return u
  return '-'
})
const requestPort = computed(() => {
  const d = currentDetail.value
  const p = d?.request_port
  if (p != null && String(p).trim() !== '') return p
  return '-'
})

const requestHeadersRaw = computed(() => currentDetail.value?.request_header ?? null)
const requestParamsRaw = computed(() => {
  const p = currentDetail.value?.request_params
  if (p == null) return {}
  if (typeof p === 'string') {
    try {
      return JSON.parse(p)
    } catch {
      return {}
    }
  }
  return p || {}
})
const requestBodyRaw = computed(() => currentDetail.value?.request_body ?? null)
const requestFormDataRaw = computed(() => currentDetail.value?.request_form_data ?? null)
const requestFormUrlencodedRaw = computed(() => currentDetail.value?.request_form_urlencoded ?? null)
const requestFormFileRaw = computed(() => currentDetail.value?.request_form_file ?? null)
const requestTextRaw = computed(() => currentDetail.value?.request_text ?? null)

const normalizedRequestHeaders = computed(() => normalizeRequestField(requestHeadersRaw.value))
const normalizedRequestParams = computed(() => {
  const p = requestParamsRaw.value
  const normalized = normalizeRequestField(p)
  return normalized && typeof normalized === 'object' && !Array.isArray(normalized) ? normalized : {}
})
const requestBody = computed(() => {
  const b = requestBodyRaw.value
  if (b != null && typeof b === 'object') return b
  if (typeof b === 'string') {
    try {
      return JSON.parse(b)
    } catch {
      return null
    }
  }
  return b
})
const requestFormData = computed(() => normalizeRequestField(requestFormDataRaw.value))
const requestFormUrlencoded = computed(() => normalizeRequestField(requestFormUrlencodedRaw.value))
const requestFormFile = computed(() => normalizeRequestField(requestFormFileRaw.value))
const requestText = computed(() => (requestTextRaw.value != null && requestTextRaw.value !== '') ? requestTextRaw.value : null)
const run_code = computed(() => {
  const s = reportPythonCodeFromDetail.value
  return s || null
})

const hasResponseInfo = computed(() => {
  const isRequestStep = (reportStepType.value || '').includes('请求')
  const hasResponseData =
      !!(currentDetail.value?.response_body) ||
      !!(currentDetail.value?.response_header) ||
      !!(currentDetail.value?.response_text) ||
      !!(currentDetail.value?.response_cookie)
  return isRequestStep && hasResponseData
})

const hasRequestInfo = computed(() => {
  const isRequestStep = (reportStepType.value || '').includes('请求')
  if (!isRequestStep) return false
  if (databaseOperatesForReport.value?.length) return true
  const hasRequestData =
      (requestMethod.value && requestMethod.value !== '-') ||
      (requestUrl.value && requestUrl.value !== '-') ||
      normalizedRequestHeaders.value != null ||
      (normalizedRequestParams.value && Object.keys(normalizedRequestParams.value).length > 0) ||
      requestBody.value != null ||
      requestFormData.value != null ||
      requestFormUrlencoded.value != null ||
      requestFormFile.value != null ||
      requestText.value != null ||
      run_code.value != null
  return hasRequestData
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
  if (requestFormUrlencoded.value && typeof requestFormUrlencoded.value === 'object') {
    return Object.entries(requestFormUrlencoded.value)
        .map(([k, v]) => `${k}=${v}`)
        .join('&')
  }
  if (requestFormUrlencoded.value != null) return String(requestFormUrlencoded.value)
  return ''
})

const isObjectRequestHeaders = computed(() => normalizedRequestHeaders.value != null && typeof normalizedRequestHeaders.value === 'object' && !Array.isArray(normalizedRequestHeaders.value))
const isObjectRequestParams = computed(() => normalizedRequestParams.value && typeof normalizedRequestParams.value === 'object' && Object.keys(normalizedRequestParams.value).length > 0)
const isJsonRequestBody = computed(() => requestBody.value != null && typeof requestBody.value === 'object')

const requestFormDataTable = computed(() => {
  if (!requestFormData.value || typeof requestFormData.value !== 'object') return []
  return Object.entries(requestFormData.value).map(([key, value]) => ({
    key,
    value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? ''),
  }))
})

const requestFormFileTable = computed(() => {
  if (!requestFormFile.value || typeof requestFormFile.value !== 'object') return []
  return Object.entries(requestFormFile.value).map(([key, value]) => ({
    key,
    value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? ''),
  }))
})

const formatRequestHeadersText = () => {
  const h = normalizedRequestHeaders.value
  if (!h) return ''
  if (typeof h === 'object' && !Array.isArray(h)) {
    return Object.entries(h)
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n')
  }
  return String(h)
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
              path: '/autotest/steps',
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

/* 与 http_controller 执行日志 Tab 中 .log-item 一致 */
.log-item {
  background-color: var(--pre-bg-color);
  color: var(--pre-text-color);
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
