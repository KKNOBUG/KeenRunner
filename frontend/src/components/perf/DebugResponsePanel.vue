<!--
  调试响应面板（可复用）— 对齐 autotest http_controller / tcp_controller Response 卡布局。
  协议模式：
    HTTP → 完整面板（Status/Time/Size/Type 标签 + Headers/Cookies + 4-way Body + 7 列提取 + 8 列断言）
    TCP  → 精简面板（无 Status/Headers/Cookies + 单 Monaco Body + 6 源提取 + 7 列断言）
  数据源：接受 perf 调试接口返回结构（status_code/elapsed_ms/response_data/extracts/assertions …），
  内部归一化后渲染；logs 字段目前后端始终为空数组，面板保留占位。
-->
<template>
  <n-card
      :bordered="false"
      style="width: 100%; margin-top: 8px;"
      :class="['step-editor-card', { 'is-collapsed': collapsed }]"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="collapsed = !collapsed"
            @keydown.enter.prevent="collapsed = !collapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="collapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">Response</div>
        </div>
        <div class="card-header-actions">
          <n-space align="center" :wrap="false">
            <n-space v-if="hasResult && !loading" align="center" :wrap="false" class="header-tags">
              <n-tag v-if="isHttp" :type="statusTagType" round size="small">
                Status: {{ debugResult.status_code ?? '-' }}
              </n-tag>
              <n-tag :type="durationTagType" round size="small">
                Time: {{ elapsedSeconds }}s
              </n-tag>
              <n-tag v-if="debugResult.response_size != null" :type="sizeTagType" round size="small">
                Size: {{ formattedSize }}
              </n-tag>
              <n-tag round size="small">Type: {{ displayContentType }}</n-tag>
            </n-space>
            <n-tag v-if="loading" type="info" round size="small">
              <template #icon>
                <n-spin size="small" />
              </template>
              请求中...
            </n-tag>
          </n-space>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!collapsed">
      <div v-if="loading" class="debug-loading">
        <n-spin size="large" description="正在发送请求，请稍候..." />
      </div>

      <n-tabs v-else type="line" animated>
        <!-- ==================== 请求信息 ==================== -->
        <n-tab-pane name="requestInfo" tab="请求信息">
          <n-space vertical :size="16" v-if="hasResult">
            <n-collapse :default-expanded-names="defaultRequestExpanded">
              <n-collapse-item title="Basic" name="requestBasic">
                <n-descriptions bordered :column="2" size="small">
                  <n-descriptions-item label="方法">
                    <n-tag :style="{ color: methodColor, borderColor: methodColor }">
                      {{ debugResult.request_info?.method || (isHttp ? '-' : 'TCP') }}
                    </n-tag>
                  </n-descriptions-item>
                  <n-descriptions-item :label="isHttp ? 'URL' : '目标地址'">
                    <n-text copyable>{{ debugResult.request_info?.url || '-' }}</n-text>
                  </n-descriptions-item>
                </n-descriptions>
              </n-collapse-item>

              <n-collapse-item v-if="isHttp" title="Headers" name="requestHeaders">
                <CopyablePre :content="requestHeadersText" empty-text="无请求头" />
              </n-collapse-item>

              <n-collapse-item v-if="isHttp" title="Cookies" name="requestCookies">
                <CopyablePre :content="requestCookiesText" empty-text="无请求 Cookie" />
              </n-collapse-item>

              <n-collapse-item :title="`Body (${requestBodyTypeLabel})`" name="requestBody">
                <div v-if="isRawRequestBody" class="request-raw-body">
                  <pre>{{ requestBodyText || '(空)' }}</pre>
                </div>
                <div v-else-if="isXmlRequestBody">
                  <monaco-editor
                      :value="requestBodyText"
                      lang="xml"
                      :options="monacoReadonlyOptions"
                      class="response-editor"
                  />
                </div>
                <div v-else-if="isJsonRequestBody">
                  <monaco-editor
                      :value="formattedRequestJson"
                      lang="json"
                      :options="monacoReadonlyOptions"
                      class="response-editor"
                  />
                </div>
                <div v-else>
                  <CopyablePre :content="requestBodyText" empty-text="(空)" />
                </div>
              </n-collapse-item>
            </n-collapse>
          </n-space>
          <n-empty v-else description="暂无请求信息" />
        </n-tab-pane>

        <!-- ==================== 响应信息 ==================== -->
        <n-tab-pane name="responseInfo" tab="响应信息">
          <n-space vertical :size="16" v-if="hasResult">
            <n-text v-if="debugResult.transport_error" type="error">
              传输异常：{{ debugResult.transport_error }}
            </n-text>
            <n-collapse :default-expanded-names="defaultResponseExpanded" arrow-placement="right">
              <n-collapse-item v-if="isHttp" title="Headers" name="responseHeaders">
                <CopyablePre :content="responseHeadersText" empty-text="无响应头" />
              </n-collapse-item>

              <n-collapse-item v-if="isHttp" title="Cookies" name="responseCookies">
                <CopyablePre :content="responseCookiesText" empty-text="无响应 Cookie" />
              </n-collapse-item>

              <n-collapse-item :title="`Body (${displayContentType})`" name="responseBody">
                <div v-if="isJsonResponse">
                  <monaco-editor
                      :value="parsedResponseJson"
                      lang="json"
                      :options="monacoReadonlyOptions"
                      class="response-editor"
                  />
                </div>
                <div v-else-if="isXmlResponse">
                  <monaco-editor
                      :value="responseTextData"
                      lang="xml"
                      :options="monacoReadonlyOptions"
                      class="response-editor"
                  />
                </div>
                <n-code
                    v-else
                    :code="responseTextData"
                    :language="responseLanguage"
                    show-line-numbers
                    class="response-code overlay-scroll"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
          <n-empty v-else description="暂无响应信息" />
        </n-tab-pane>

        <!-- ==================== 数据提取 ==================== -->
        <n-tab-pane name="extracts" tab="数据提取">
          <n-data-table
              v-if="hasResult && normalizedExtracts.length > 0"
              :columns="extractColumns"
              :data="normalizedExtracts"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无数据提取结果" />
        </n-tab-pane>

        <!-- ==================== 断言结果 ==================== -->
        <n-tab-pane name="assertions" tab="断言结果">
          <n-data-table
              v-if="hasResult && normalizedAssertions.length > 0"
              :columns="assertColumns"
              :data="normalizedAssertions"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无断言结果" />
        </n-tab-pane>

        <!-- ==================== 执行日志 ==================== -->
        <n-tab-pane name="logs" tab="执行日志">
          <n-space vertical :size="12" v-if="hasResult && (debugResult.logs || []).length > 0">
            <pre
                v-for="(log, index) in debugResult.logs"
                :key="index"
                class="log-item"
            >{{ log }}</pre>
          </n-space>
          <n-empty v-else description="暂无执行日志" />
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import {
  NCard, NCode, NCollapse, NCollapseItem, NCollapseTransition, NDataTable, NDescriptions,
  NDescriptionsItem, NEmpty, NSpace, NSpin, NTabPane, NTabs, NTag, NText,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import CopyablePre from '@/components/common/CopyablePre.vue'

const props = defineProps({
  /** 协议类型：'HTTP请求' | 'TCP请求'（与 form.step_type 取值一致） */
  protocol: { type: String, default: 'HTTP请求' },
  /** 调试结果（perf 调试接口返回结构） */
  debugResult: { type: Object, default: null },
  /** 是否正在加载 */
  loading: { type: Boolean, default: false },
})

const isHttp = computed(() => props.protocol === 'HTTP请求')
const hasResult = computed(() => !!props.debugResult)
const collapsed = ref(false)

// =================== Monaco 只读配置 ===================
const monacoReadonlyOptions = {
  readOnly: true,
  theme: 'vs-dark',
  fontSize: 14,
  tabSize: 4,
  automaticLayout: true,
  minimap: { enabled: true },
  lineNumbers: 'on',
  wordWrap: 'on',
  scrollBeyondLastLine: false,
  folding: true,
  foldingStrategy: 'auto',
}

// =================== 来源显示映射（后端存小写，展示转 Title Case） ===================
const sourceDisplayMap = {
  'response json': 'Response Json',
  'request json': 'Request Json',
  'response text': 'Response Text',
  'request text': 'Request Text',
  'response xml': 'Response XML',
  'request xml': 'Request XML',
  'response headers': 'Response Headers',
  'request headers': 'Request Headers',
  'response cookie': 'Response Cookie',
  'request cookie': 'Request Cookie',
  'request form-data': 'Request Form-Data',
  '变量池': '变量池',
}

function displaySource(raw) {
  if (!raw) return '-'
  return sourceDisplayMap[raw] || sourceDisplayMap[raw.toLowerCase()] || raw
}

// HTTP 断言对象显示映射（小写 → 驼峰）
const assertSourceDisplayMapHttp = {
  'response json': 'responseJson',
  'request json': 'requestJson',
  'response text': 'responseText',
  'request text': 'requestText',
  'response xml': 'responseXml',
  'request xml': 'requestXml',
  'response headers': 'responseHeaders',
  'request headers': 'requestHeaders',
  'response cookie': 'responseCookie',
  'request cookie': 'requestCookie',
  'request form-data': 'requestFormData',
  '变量池': '变量池',
}

// TCP 断言对象显示映射（无 Headers/Cookie/Form-Data）
const assertSourceDisplayMapTcp = {
  'response json': 'responseJson',
  'request json': 'requestJson',
  'response text': 'responseText',
  'request text': 'requestText',
  'response xml': 'responseXml',
  'request xml': 'requestXml',
  '变量池': '变量池',
}

function displayAssertSource(raw) {
  if (!raw) return '-'
  const map = isHttp.value ? assertSourceDisplayMapHttp : assertSourceDisplayMapTcp
  return map[raw] || map[raw.toLowerCase()] || raw
}

// =================== 响应内容类型 ===================
const responseContentType = computed(() => {
  if (!props.debugResult) return 'text/plain'
  if (isHttp.value) {
    const ct = props.debugResult.content_type || ''
    return ct.split(';')[0].trim() || 'text/plain'
  }
  const data = props.debugResult.response_data
  if (data === null || data === undefined) return 'text/plain'
  if (typeof data === 'object') return 'application/json'
  if (typeof data === 'string') {
    const trimmed = data.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) return 'application/json'
    if (trimmed.startsWith('<') && trimmed.endsWith('>')) return 'application/xml'
  }
  return 'text/plain'
})

const displayContentType = computed(() => responseContentType.value || 'text/plain')

const isJsonResponse = computed(() => responseContentType.value.includes('json'))
const isXmlResponse = computed(() => responseContentType.value.toLowerCase().includes('xml'))

const responseLanguage = computed(() => {
  const ct = responseContentType.value.toLowerCase()
  if (ct.includes('json')) return 'json'
  if (ct.includes('xml')) return 'xml'
  if (ct.includes('html')) return 'html'
  return 'text'
})

// =================== 响应体数据 ===================
const responseTextData = computed(() => {
  const data = props.debugResult?.response_data
  if (data === null || data === undefined) return ''
  if (typeof data === 'object') return JSON.stringify(data, null, 2)
  return String(data)
})

const parsedResponseJson = computed(() => {
  const data = props.debugResult?.response_data
  if (data === null || data === undefined) return ''
  if (typeof data === 'object') return JSON.stringify(data, null, 2)
  try {
    return JSON.stringify(JSON.parse(data), null, 2)
  } catch {
    return String(data)
  }
})

// =================== 请求头/Cookie 文本 ===================
const requestHeadersText = computed(() =>
    Object.entries(props.debugResult?.request_info?.headers || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n'),
)

const requestCookiesText = computed(() => {
  const cookies = props.debugResult?.request_info?.cookies
  if (!cookies || typeof cookies !== 'object') return ''
  return Object.entries(cookies).map(([k, v]) => `${k}: ${v}`).join('\n')
})

const responseHeadersText = computed(() =>
    Object.entries(props.debugResult?.response_headers || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n'),
)

const responseCookiesText = computed(() =>
    Object.entries(props.debugResult?.response_cookies || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n'),
)

// =================== 请求体 ===================
const requestBodyTypeLabel = computed(() => {
  const bt = props.debugResult?.request_info?.body_type || 'none'
  const map = {
    'none': 'None', 'params': 'Params', 'form-data': 'Form Data',
    'x-www-form-urlencoded': 'Form URL Encoded',
    'json': 'JSON', 'xml': 'XML', 'raw': 'Raw',
  }
  return map[bt] || bt
})

const requestBodyText = computed(() => {
  const body = props.debugResult?.request_info?.body
  if (body === null || body === undefined) return ''
  if (typeof body === 'object') return JSON.stringify(body, null, 2)
  return String(body)
})

const isJsonRequestBody = computed(() => {
  const bt = (props.debugResult?.request_info?.body_type || '').toLowerCase()
  return bt === 'json'
})

const isXmlRequestBody = computed(() => {
  const bt = (props.debugResult?.request_info?.body_type || '').toLowerCase()
  return bt === 'xml'
})

const isRawRequestBody = computed(() => {
  const bt = (props.debugResult?.request_info?.body_type || '').toLowerCase()
  return bt === 'raw' || bt === 'text'
})

const formattedRequestJson = computed(() => {
  const body = props.debugResult?.request_info?.body
  if (body === null || body === undefined) return ''
  if (typeof body === 'object') return JSON.stringify(body, null, 4)
  try {
    return JSON.stringify(JSON.parse(body), null, 4)
  } catch {
    return String(body)
  }
})

// =================== 折叠默认展开项 ===================
const defaultRequestExpanded = computed(() => {
  const names = ['requestBasic', 'requestBody']
  if (isHttp.value) names.push('requestHeaders')
  return names
})

const defaultResponseExpanded = computed(() => {
  const names = ['responseBody']
  if (isHttp.value) names.push('responseHeaders', 'responseCookies')
  return names
})

// =================== 状态标签 ===================
const elapsedSeconds = computed(() => {
  const ms = props.debugResult?.elapsed_ms
  if (ms == null) return '-'
  return (ms / 1000).toFixed(2)
})

const formattedSize = computed(() => {
  const bytes = props.debugResult?.response_size
  if (bytes == null) return '-'
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(2)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${bytes} B`
})

const statusTagType = computed(() => {
  const code = props.debugResult?.status_code
  if (code == null) return 'default'
  return code === 200 ? 'success' : 'error'
})

const durationTagType = computed(() => {
  const ms = props.debugResult?.elapsed_ms
  if (ms == null) return 'default'
  return ms >= 500 ? 'warning' : 'success'
})

const sizeTagType = computed(() => {
  const bytes = props.debugResult?.response_size
  if (bytes == null) return 'default'
  return bytes >= 102400 ? 'warning' : 'success'
})

/** 方法标签颜色对齐 Request 面板请求方式下拉（methodOptions 四色口径） */
const methodColor = computed(() => {
  const method = (props.debugResult?.request_info?.method || '').toUpperCase()
  return { GET: '#2080F0', POST: '#18A058', PUT: '#FCA130', DELETE: '#F4511E' }[method] || '#999'
})

// =================== 归一化提取/断言数据 ===================
const normalizedExtracts = computed(() => {
  const list = props.debugResult?.extracts || []
  return list.map((item) => ({
    name: item.name,
    source: displaySource(item.source),
    scope: item.scope || 'ALL',
    expr: item.expr,
    extract_value: item.extract_value,
    success: item.success,
    error: item.error,
  }))
})

const normalizedAssertions = computed(() => {
  const list = props.debugResult?.assertions || []
  return list.map((item) => ({
    name: item.name,
    source: displayAssertSource(item.source),
    expr: item.expr,
    actual_value: item.actual_value,
    operation: item.operation,
    expect_value: item.except_value ?? item.expect_value,
    success: item.success,
    error: item.error,
  }))
})

// =================== 数据提取列（7 列，对齐 HTTP/TCP 控制器） ===================
const extractColumns = [
  { title: '变量名', key: 'name', width: 120, ellipsis: { tooltip: true } },
  { title: '提取来源', key: 'source', width: 120 },
  {
    title: '提取范围', key: 'scope', width: 120,
    render: (row) => (row.scope === 'ALL' ? '全部提取' : '部分提取'),
  },
  { title: '提取路径', key: 'expr', width: 120, ellipsis: { tooltip: true } },
  {
    title: '提取值', key: 'extract_value', width: 120, ellipsis: { tooltip: true },
    render: (row) => {
      if (row.extract_value === null || row.extract_value === undefined) return '-'
      const v = typeof row.extract_value === 'object'
          ? JSON.stringify(row.extract_value)
          : String(row.extract_value)
      return v.length > 100 ? v.substring(0, 100) + '...' : v
    },
  },
  {
    title: '提取结果', key: 'success', width: 120,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error', round: true, size: 'small',
    }, { default: () => row.success ? 'pass' : 'fail' }),
  },
  {
    title: '错误信息', key: 'error', width: 120, ellipsis: { tooltip: true },
    render: (row) => row.error || '-',
  },
]

// =================== 断言结果列（HTTP 8 列 / TCP 7 列，对齐控制器） ===================
const assertColumns = computed(() => {
  const cols = [
    { title: '断言名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
    { title: '断言对象', key: 'source', width: 120 },
    { title: '断言路径', key: 'expr', width: 130, ellipsis: { tooltip: true } },
    {
      title: '结果值', key: 'actual_value', width: 150, ellipsis: { tooltip: true },
      render: (row) => {
        if (row.actual_value === null || row.actual_value === undefined) return '-'
        const v = typeof row.actual_value === 'object'
            ? JSON.stringify(row.actual_value)
            : String(row.actual_value)
        return v.length > 100 ? v.substring(0, 100) + '...' : v
      },
    },
  ]
  if (isHttp.value) {
    cols.push({ title: '断言方式', key: 'operation', width: 100 })
  }
  cols.push({
    title: '期望值', key: 'expect_value', width: 150, ellipsis: { tooltip: true },
    render: (row) => {
      if (row.expect_value === null || row.expect_value === undefined) return '-'
      const v = typeof row.expect_value === 'object'
          ? JSON.stringify(row.expect_value)
          : String(row.expect_value)
      return v.length > 100 ? v.substring(0, 100) + '...' : v
    },
  })
  cols.push({
    title: '断言结果', key: 'success', width: 120,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error', round: true, size: 'small',
    }, { default: () => row.success ? 'pass' : 'fail' }),
  })
  cols.push({
    title: '错误信息', key: 'error', width: 120, ellipsis: { tooltip: true },
    render: (row) => row.error || '-',
  })
  return cols
})

</script>

<style scoped>
.header-tags {
  gap: 8px;
}

.response-editor {
  min-height: 400px;
  height: auto;
  border-radius: 8px;
  overflow: hidden;
}

.request-raw-body pre {
  margin: 0;
  padding: 8px 12px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--n-action-color, rgba(128, 128, 128, 0.08));
  border-radius: 6px;
}

.log-item {
  margin: 0;
  padding: 6px 12px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--n-action-color, rgba(128, 128, 128, 0.08));
  border-radius: 4px;
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}
</style>
