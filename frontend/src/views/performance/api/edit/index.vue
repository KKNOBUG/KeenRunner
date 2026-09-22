<!--
  压测接口编辑子页 — 新增/编辑/导入草稿确认共用（隐藏菜单，query 传 api_id）

  栏目结构对齐 autotest 步骤编辑页「HTTP/TCP请求」类型子页面（无 api_project，接口名称全局唯一）：
  DataSource（参数化数据集，PerfApiDatasetPanel）→
  Request（接口类型 + 请求方式/地址 + 接口名称/所属应用/配置 + 接口描述 + 请求头/请求体/变量/提取/断言）→
  Response（点击调试后出现）。
  调试走页内「选择调试环境」弹窗（对齐 http_controller 调试链路），结论回写 debug_state；
  请求块字段与 krun_autotest_step 逐字对齐（从功能资产导入退化为纯字段搬运）。
  提取/断言复用 autotest StepExtractPanel/StepAssertPanel（perf 小写 source 与面板大写
  object 的双向映射见 utils/perfExtractAssert.js）；变量 tab 对应 perf_api.defined_variables。
  导入草稿队列经 sessionStorage 传递（key=perf_api_draft_queue），保存成功自动进入下一条。
-->
<template>
  <AppPage>
    <n-space vertical :size="8">
      <!-- ========== 栏目一：DataSource 数据源 ========== -->
      <PerfApiDatasetPanel :api-row="apiRow" />

      <!-- ========== 栏目二：Request 请求配置 ========== -->
      <n-card
          :bordered="false"
          style="width: 100%;"
          :class="['step-editor-card', { 'is-collapsed': requestCardCollapsed }]"
      >
        <template #header>
          <div class="card-header-row">
            <div
                class="panel-title-wrap"
                role="button"
                tabindex="0"
                @click="requestCardCollapsed = !requestCardCollapsed"
                @keydown.enter.prevent="requestCardCollapsed = !requestCardCollapsed"
            >
              <TheIcon
                  class="panel-collapse-icon"
                  :icon="requestCardCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
                  :size="20"
              />
              <div class="panel-title">Request</div>
            </div>
          </div>
        </template>

        <n-collapse-transition :show="!requestCardCollapsed">
          <n-form
              ref="requestFormRef"
              :model="form"
              label-placement="left"
              label-width="80px"
              size="small"
          >
            <!-- 第一行：接口类型（左） + 调试/保存按钮（右） -->
            <div class="request-row">
              <n-form-item
                  label="接口类型"
                  path="step_type"
                  :rule="{ required: true, message: '请选择接口类型' }"
                  class="request-field-type"
              >
                <n-radio-group :value="form.step_type" @update:value="handleStepTypeChange" name="step_type">
                  <!-- 值与后端 AutoTestStepType 中文枚举一致, 英文缩写会被 schema 校验拒绝 -->
                  <n-radio value="HTTP请求">HTTP</n-radio>
                  <n-radio value="TCP请求">TCP</n-radio>
                </n-radio-group>
              </n-form-item>
              <div class="request-field-spacer"></div>
              <div class="request-field-actions">
                <n-button type="primary" size="small" @click="openDebugModal" :loading="debugLoading">
                  调试
                </n-button>
                <n-button type="info" size="small" :loading="saving" @click="handleSave">
                  保存
                </n-button>
              </div>
            </div>

            <!-- HTTP 第二行：请求方式 + 请求地址 -->
            <div v-if="isHttp" class="request-row request-row-bottom">
              <n-form-item
                  label="请求方式"
                  path="request_method"
                  :rule="{ required: true, message: '必选' }"
                  class="request-field-method"
              >
                <n-select
                    v-model:value="form.request_method"
                    :options="methodOptions"
                    :render-label="renderMethodLabel"
                    placeholder="方式"
                />
              </n-form-item>
              <n-form-item
                  label="请求地址"
                  path="request_url"
                  :rule="{ required: true, message: '请输入请求地址', trigger: ['blur', 'change'] }"
                  class="request-field-url"
              >
                <n-input v-model:value="form.request_url" placeholder="支持相对路径与 ${} 占位符" clearable />
              </n-form-item>
            </div>

            <!-- 三字段同行：接口名称 + 所属应用 + 配置名称（无端口：施压目标 host/port 全由施压环境解析） -->
            <div class="request-row">
              <n-form-item
                  label="接口名称"
                  path="api_name"
                  :rule="{ required: true, message: '请输入接口名称', trigger: ['blur', 'input'] }"
                  class="request-field-third"
              >
                <n-input v-model:value="form.api_name" placeholder="请输入接口名称（全局唯一）" clearable />
              </n-form-item>
              <n-form-item label="所属应用" path="request_project_id" class="request-field-third">
                <n-select
                    v-model:value="form.request_project_id"
                    :options="projectOptions"
                    placeholder="缺省随任务施压环境"
                    clearable
                    filterable
                />
              </n-form-item>
              <n-form-item label="配置名称" path="request_config_name" class="request-field-third">
                <n-input v-model:value="form.request_config_name" placeholder="APP节点配置名（缺省随任务）" clearable />
              </n-form-item>
            </div>

            <!-- 接口描述（对齐 http_controller 步骤描述行位置） -->
            <n-form-item label="接口描述" path="api_desc">
              <n-input
                  type="textarea"
                  v-model:value="form.api_desc"
                  placeholder="接口描述（可选）"
                  :autosize="{ minRows: 1 }"
                  style="width: 100%;"
              />
            </n-form-item>

            <n-alert v-if="!isHttp" :bordered="false" type="warning" style="margin-bottom: 8px;">
              当前引擎仅支持 HTTP 施压：TCP 接口允许保存与编排，执行前闸门会拒绝下发。
            </n-alert>
          </n-form>

          <!-- 请求配置 tabs（受控 activeTab；:key 随类型重挂载：请求头 pane 动态移除后 naive 墨线按旧索引定位会错位） -->
          <n-tabs v-model:value="activeTab" :key="form.step_type" type="line" animated style="margin-top: 16px;">
            <n-tab-pane v-if="isHttp" name="headers" tab="请求头">
              <template #tab>
                <n-badge :value="form.request_header.length" :max="99" show-zero>
                  <span>请求头</span>
                </n-badge>
              </template>
              <KeyValueEditor v-model:items="form.request_header" :body-type="'none'" :is-for-body="false" />
            </n-tab-pane>

            <n-tab-pane name="params" tab="请求体">
              <template #tab>
                <n-badge :value="getBodyCount" :max="99" show-zero>
                  <span>请求体</span>
                </n-badge>
              </template>
              <n-radio-group v-model:value="bodyType" name="bodyType">
                <n-space>
                  <template v-if="isHttp">
                    <n-radio value="none">none</n-radio>
                    <n-radio value="params">params</n-radio>
                    <n-radio value="form-data">form-data</n-radio>
                    <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
                    <n-radio value="json">json</n-radio>
                    <n-radio value="xml">xml</n-radio>
                    <n-radio value="raw">raw</n-radio>
                  </template>
                  <template v-else>
                    <n-radio value="xml">xml</n-radio>
                    <n-radio value="json">json</n-radio>
                    <n-radio value="raw">raw</n-radio>
                  </template>
                </n-space>
              </n-radio-group>
              <div v-if="bodyType === 'params'" class="body-editor">
                <KeyValueEditor v-model:items="form.request_params" :body-type="'none'" :is-for-body="true" />
              </div>
              <div v-if="bodyType === 'form-data'" class="body-editor">
                <KeyValueEditor v-model:items="form.request_form_data" :body-type="'form-data'" :is-for-body="true" />
              </div>
              <div v-if="bodyType === 'x-www-form-urlencoded'" class="body-editor">
                <KeyValueEditor
                    v-model:items="form.request_form_urlencoded"
                    :body-type="'x-www-form-urlencoded'"
                    :is-for-body="true"
                />
              </div>
              <monaco-editor
                  v-if="bodyType === 'json'"
                  v-model:value="jsonBodyText"
                  lang="json"
                  :options="monacoBodyOptions"
                  class="body-editor"
                  style="min-height: 400px"
              />
              <monaco-editor
                  v-if="bodyType === 'xml'"
                  v-model:value="form.request_text"
                  lang="xml"
                  :options="monacoBodyOptions"
                  class="body-editor"
                  style="min-height: 400px"
              />
              <n-input
                  v-if="bodyType === 'raw'"
                  v-model:value="form.request_text"
                  type="textarea"
                  placeholder="请输入 raw 请求体文本"
                  :rows="12"
                  class="body-editor"
              />
            </n-tab-pane>

            <n-tab-pane name="defined_variables" tab="变量">
              <template #tab>
                <n-badge :value="form.defined_variables.length" :max="99" show-zero>
                  <span>变量</span>
                </n-badge>
              </template>
              <KeyValueEditor v-model:items="form.defined_variables" :body-type="'none'" :is-for-body="false" />
            </n-tab-pane>

            <n-tab-pane name="extract_variables" tab="提取">
              <template #tab>
                <n-badge :value="extractCount" :max="99" show-zero>
                  <span>提取</span>
                </n-badge>
              </template>
              <StepExtractPanel v-model="form.extract_variables" mode="response" />
            </n-tab-pane>

            <n-tab-pane name="assert_validators" tab="断言">
              <template #tab>
                <n-badge :value="validatorsCount" :max="99" show-zero>
                  <span>断言</span>
                </n-badge>
              </template>
              <StepAssertPanel v-model="form.assert_validators" mode="response" />
            </n-tab-pane>
          </n-tabs>
        </n-collapse-transition>
      </n-card>

      <!-- ========== 栏目四：Response 调试回显（点击调试后出现） ========== -->
      <n-card
          v-if="debugLoading || debugResult"
          :bordered="false"
          style="width: 100%;"
          class="step-editor-card"
      >
        <template #header>
          <div class="card-header-row card-header-row--with-actions">
            <div class="panel-title-wrap">
              <div class="panel-title">Response</div>
            </div>
            <div class="card-header-actions">
              <n-space align="center" :wrap="false">
                <template v-if="debugResult && !debugLoading">
                  <n-tag :type="debugResult.success ? 'success' : 'error'" round size="small">
                    {{ debugResult.success ? '调试通过' : '调试未通过' }}
                  </n-tag>
                  <n-tag :type="responseStatusTagType" round size="small">
                    Status: {{ debugResult.status_code ?? '-' }}
                  </n-tag>
                  <n-tag round size="small">
                    Time: {{ debugResult.elapsed_ms != null ? `${debugResult.elapsed_ms}ms` : '-' }}
                  </n-tag>
                  <n-tag v-if="debugResult.response_size != null" round size="small">
                    Size: {{ debugResult.response_size }}
                  </n-tag>
                </template>
                <n-tag v-if="debugLoading" type="info" round size="small">
                  <template #icon>
                    <n-spin size="small" />
                  </template>
                  请求中...
                </n-tag>
              </n-space>
            </div>
          </div>
        </template>

        <div v-if="debugLoading" class="debug-loading">
          <n-spin size="large" description="正在发送请求，请稍候..." />
        </div>
        <n-tabs v-else type="line" animated>
          <!-- 请求信息 -->
          <n-tab-pane name="requestInfo" tab="请求信息">
            <n-space vertical :size="16" v-if="debugResult?.request_info">
              <n-collapse :default-expanded-names="['requestBasic', 'requestHeaders', 'requestBody']">
                <n-collapse-item title="Basic" name="requestBasic">
                  <n-descriptions bordered :column="2" size="small">
                    <n-descriptions-item label="方法">
                      <n-tag type="info">{{ debugResult.request_info.method || '-' }}</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item label="URL">
                      <n-text copyable>{{ debugResult.request_info.url || '-' }}</n-text>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-collapse-item>
                <n-collapse-item title="Headers" name="requestHeaders">
                  <pre v-if="requestHeadersText" class="headers-pre" @click="copyText(requestHeadersText)">{{ requestHeadersText }}</pre>
                  <n-empty v-else description="无请求头" />
                </n-collapse-item>
                <n-collapse-item :title="`Body (${debugResult.request_info.body_type || 'none'})`" name="requestBody">
                  <pre class="headers-pre">{{ debugResult.request_info.body || '(空)' }}</pre>
                </n-collapse-item>
              </n-collapse>
            </n-space>
            <n-empty v-else description="暂无请求信息" />
          </n-tab-pane>
          <!-- 响应信息 -->
          <n-tab-pane name="responseInfo" tab="响应信息">
            <n-space vertical :size="16" v-if="debugResult">
              <n-text v-if="debugResult.transport_error" type="error">
                传输异常：{{ debugResult.transport_error }}
              </n-text>
              <n-collapse :default-expanded-names="['responseHeaders', 'responseBody']" arrow-placement="right">
                <n-collapse-item title="Headers" name="responseHeaders">
                  <pre v-if="responseHeadersText" class="headers-pre" @click="copyText(responseHeadersText)">{{ responseHeadersText }}</pre>
                  <n-empty v-else description="无响应头" />
                </n-collapse-item>
                <n-collapse-item :title="`Body (${debugResult.content_type || '未知类型'})`" name="responseBody">
                  <monaco-editor
                      v-if="responseJsonFormatted != null"
                      :value="responseJsonFormatted"
                      lang="json"
                      :options="monacoReadonlyOptions"
                      class="response-editor"
                  />
                  <n-input
                      v-else
                      :value="debugResult.response_data || ''"
                      type="textarea"
                      readonly
                      :rows="10"
                      class="response-text"
                  />
                </n-collapse-item>
              </n-collapse>
            </n-space>
            <n-empty v-else description="暂无响应信息" />
          </n-tab-pane>
          <!-- 数据提取 -->
          <n-tab-pane name="extracts" tab="数据提取">
            <n-data-table
                v-if="(debugResult?.extracts || []).length > 0"
                :columns="extractColumns"
                :data="debugResult.extracts"
                size="small"
                :bordered="true"
            />
            <n-empty v-else description="暂无数据提取结果" />
          </n-tab-pane>
          <!-- 断言结果 -->
          <n-tab-pane name="assertions" tab="断言结果">
            <n-data-table
                v-if="(debugResult?.assertions || []).length > 0"
                :columns="assertColumns"
                :data="debugResult.assertions"
                size="small"
                :bordered="true"
            />
            <n-empty v-else description="暂无断言结果" />
          </n-tab-pane>
          <!-- 执行日志 -->
          <n-tab-pane name="logs" tab="执行日志">
            <n-space vertical :size="12" v-if="(debugResult?.logs || []).length > 0">
              <pre v-for="(log, index) in debugResult.logs" :key="index" class="headers-pre">{{ log }}</pre>
            </n-space>
            <n-empty v-else description="暂无执行日志" />
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </n-space>

    <!-- 调试前选择执行环境与数据源取数（对齐 autotest 设计：一个接口绑定一个数据源） -->
    <n-modal
        v-model:show="debugModalVisible"
        preset="dialog"
        title="选择调试环境"
        positive-text="确定"
        negative-text="取消"
        :loading="debugLoading"
        @positive-click="confirmDebug"
    >
      <div style="padding: 8px 0; display: flex; flex-direction: column; gap: 12px;">
        <div>
          <div style="margin-bottom: 8px;">调试环境：</div>
          <n-select
              v-model:value="debugForm.envName"
              :options="debugEnvOptions"
              :loading="debugEnvLoading"
              placeholder="请选择调试环境（绝对地址可留空）"
              clearable
              filterable
              style="width: 100%;"
          />
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="margin-bottom: 0;">启用数据源：</div>
          <n-switch v-model:value="debugForm.enableDataSource" @update:value="onDebugEnableDataSourceChange" />
        </div>
        <div v-if="debugForm.enableDataSource">
          <div style="margin-bottom: 8px;">场景名称：</div>
          <n-select
              v-model:value="debugForm.sceneName"
              :options="debugSceneOptions"
              :loading="debugSceneLoading"
              :disabled="!debugForm.enableDataSource"
              placeholder="选择场景（调试只可选一个）"
              clearable
              filterable
              style="width: 100%;"
          />
        </div>
      </div>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAlert, NBadge, NButton, NCard, NCollapse, NCollapseItem, NCollapseTransition, NDataTable, NDescriptions,
  NDescriptionsItem, NEmpty, NForm, NFormItem, NInput, NModal,
  NRadio, NRadioGroup, NSelect, NSpace, NSpin, NSwitch, NTabPane, NTabs, NTag, NText,
} from 'naive-ui'

import AppPage from '@/components/page/AppPage.vue'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import PerfApiDatasetPanel from '../components/PerfApiDatasetPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'

import { countDictKeys, validateAssertList, validateExtractList } from '@/utils/autotestExtractAssert'
import {
  buildPerfAssertListFromDict,
  buildPerfExtractListFromDict,
  hydratePerfAssertDict,
  hydratePerfExtractDict,
} from '@/utils/perfExtractAssert'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测接口编辑' })

const route = useRoute()
const router = useRouter()

/** 导入草稿队列在 sessionStorage 的键（列表页导入后写入，本页逐条消费） */
const DRAFT_QUEUE_KEY = 'perf_api_draft_queue'

const requestFormRef = ref(null)
const saving = ref(false)
const projectOptions = ref([])

/** 编辑中的接口详情（含 api_id，DataSource 卡与调试取数据此加载） */
const apiRow = ref(null)

/** 与后端 AutoTestReqArgsType / HTTPMethod 取值一致（方式下拉沿用 http_controller 四色口径） */
const methodOptions = [
  { label: 'GET', value: 'GET', color: '#2080F0' },
  { label: 'POST', value: 'POST', color: '#18A058' },
  { label: 'PUT', value: 'PUT', color: '#FCA130' },
  { label: 'DELETE', value: 'DELETE', color: '#F4511E' },
]
const monacoBodyOptions = {
  minimap: { enabled: false },
  fontSize: 13,
  automaticLayout: true,
  tabSize: 2,
  scrollBeyondLastLine: false,
}
const monacoReadonlyOptions = {
  readOnly: true,
  minimap: { enabled: false },
  fontSize: 13,
  automaticLayout: true,
  scrollBeyondLastLine: false,
}

const emptyForm = () => ({
  api_id: null,
  api_code: null,
  api_name: null,
  api_desc: null,
  step_type: 'HTTP请求',
  request_url: null,
  request_port: null,
  request_method: 'GET',
  request_header: [],
  request_params: [],
  request_form_data: [],
  request_form_urlencoded: [],
  request_text: '',
  request_body: null,
  request_args_type: 'none',
  request_project_id: null,
  request_config_name: null,
  defined_variables: [],
  // 提取/断言在表单内为面板字典形态（key=序号），保存时经 perfExtractAssert 转回存储列表
  extract_variables: {},
  assert_validators: {},
})

const form = reactive(emptyForm())

/** 请求体编辑形态与 request_args_type 一一对应；json/xml/raw 的载体字段见 buildPayload */
const bodyType = ref('none')
const jsonBodyText = ref('')
/** 切 TCP 时不被支持的 bodyType 暂存（回切 HTTP 时恢复，请求体内容跨类型共享不清空） */
const httpBodyTypeBackup = ref(null)

/** 请求配置 tabs 激活项（受控：类型切换移除/恢复请求头 pane 时同步修正，避免激活态错乱） */
const activeTab = ref('headers')

const isHttp = computed(() => form.step_type === 'HTTP请求')
const isEdit = computed(() => form.api_id != null)

/** 用户切换接口类型：修正 tabs 激活态 + 请求体类型回落到协议支持集合；
 *  不清空任何请求体载体（HTTP/TCP 共享同一份编辑态）；applyDetail 等程序性赋值不走本函数 */
function handleStepTypeChange(type) {
  // 同值不切换
  if (type === form.step_type) {
    return
  }
  form.step_type = type
  if (type === 'TCP请求') {
    // TCP 请求体仅 xml/json/raw（对齐 tcp_controller）：不支持的类型暂存，回切 HTTP 时恢复
    if (!['xml', 'json', 'raw'].includes(bodyType.value)) {
      httpBodyTypeBackup.value = bodyType.value
      bodyType.value = 'xml'
    }
    // 请求头 tab 仅 HTTP 存在：若停留在请求头则回落到请求体
    if (activeTab.value === 'headers') {
      activeTab.value = 'params'
    }
  } else if (httpBodyTypeBackup.value) {
    bodyType.value = httpBodyTypeBackup.value
    httpBodyTypeBackup.value = null
  }
}

/** tabs 徽标数（口径对齐 http_controller：请求头/变量=length，请求体按载体，提取/断言=字典键数） */
const extractCount = computed(() => countDictKeys(form.extract_variables))
const validatorsCount = computed(() => countDictKeys(form.assert_validators))
const getBodyCount = computed(() => {
  switch (bodyType.value) {
    case 'params':
      return form.request_params.length
    case 'form-data':
      return form.request_form_data.length
    case 'x-www-form-urlencoded':
      return form.request_form_urlencoded.length
    case 'json':
      return jsonBodyText.value.trim() ? 1 : 0
    case 'xml':
    case 'raw':
      return (form.request_text || '').trim() ? 1 : 0
    default:
      return 0
  }
})

/** Request 卡折叠交互（对齐 http_controller） */
const requestCardCollapsed = ref(false)

function renderMethodLabel(option) {
  return h('span', { style: { color: option.color, fontWeight: '600' } }, option.label)
}

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 后端详情/导入草稿 → 表单形态（请求体对象转 JSON 文本，提取/断言转面板字典，容器 null 归空数组） */
function applyDetail(detail) {
  Object.assign(form, emptyForm(), {
    ...detail,
    request_header: detail.request_header || [],
    request_params: detail.request_params || [],
    request_form_data: detail.request_form_data || [],
    request_form_urlencoded: detail.request_form_urlencoded || [],
    request_text: detail.request_text || '',
    defined_variables: detail.defined_variables || [],
    extract_variables: hydratePerfExtractDict(detail.extract_variables),
    assert_validators: hydratePerfAssertDict(detail.assert_validators),
  })
  const argsType = detail.request_args_type || 'none'
  bodyType.value = argsType === 'none' && detail.request_body ? 'json' : argsType
  // 加载新详情后作废旧的类型暂存，避免跨接口串态
  httpBodyTypeBackup.value = null
  jsonBodyText.value = detail.request_body ? JSON.stringify(detail.request_body, null, 2) : ''
  // TCP 无请求头 pane：加载 TCP 接口时若激活项停留在请求头则回落到请求体
  if (detail.step_type === 'TCP请求' && activeTab.value === 'headers') {
    activeTab.value = 'params'
  }
}

async function loadApi(apiId) {
  try {
    const res = await api.getPerfApi({ api_id: apiId })
    applyDetail(res.data || {})
    apiRow.value = res.data || {}
    // 刷新地址栏，刷新页面后仍能回到本接口（同 autotest 步骤编辑页约定）
    router.replace({ path: route.path, query: { api_id: String(apiId) } })
  } catch (e) {
    handleBack()
  }
}

/** 从队列弹出下一条导入草稿（无剩余返回 null） */
function shiftDraft() {
  let queue = []
  try {
    queue = JSON.parse(sessionStorage.getItem(DRAFT_QUEUE_KEY) || '[]')
  } catch (e) {
    queue = []
  }
  const draft = queue.shift() || null
  sessionStorage.setItem(DRAFT_QUEUE_KEY, JSON.stringify(queue))
  return draft
}

function remainDraftCount() {
  try {
    return (JSON.parse(sessionStorage.getItem(DRAFT_QUEUE_KEY) || '[]')).length
  } catch (e) {
    return 0
  }
}

async function initFromRoute() {
  const apiId = route.query.api_id ? Number(route.query.api_id) : null
  if (apiId) {
    await loadApi(apiId)
    return
  }
  if (route.query.draft) {
    const draft = shiftDraft()
    if (draft) {
      // 导入草稿：结构与详情同构，但无 id/code，用户补全名称后走 create
      applyDetail(draft)
      return
    }
  }
}

onMounted(() => {
  loadProjects()
  initFromRoute()
})

/** 表单形态 → PerfApiCreate/Update payload（按 bodyType 归位载体字段，提取/断言转回存储列表） */
function buildPayload() {
  const payload = {
    ...form,
    request_args_type: bodyType.value,
    api_source: form.api_source || 'manual',
    extract_variables: buildPerfExtractListFromDict(form.extract_variables),
    assert_validators: buildPerfAssertListFromDict(form.assert_validators),
  }
  switch (bodyType.value) {
    case 'none':
      payload.request_body = null
      payload.request_text = null
      break
    case 'json':
      payload.request_body = JSON.parse(jsonBodyText.value)
      payload.request_text = null
      break
    case 'xml':
    case 'raw':
      payload.request_body = null
      break
    default:
      payload.request_body = null
      payload.request_text = null
  }
  delete payload.api_code
  delete payload.created_time
  delete payload.updated_time
  delete payload.created_user
  delete payload.updated_user
  delete payload.debug_state
  delete payload.debug_time
  delete payload.version
  if (!isEdit.value) delete payload.api_id
  return payload
}

/** 保存成功后的去向：草稿队列还有剩余则弹窗进入下一条，否则留在本页继续编辑（页内保存不跳走） */
function afterSaved() {
  if (remainDraftCount() <= 0) {
    return
  }
  window.$dialog?.info({
    title: '继续下一条草稿',
    content: `还有 ${remainDraftCount()} 条导入草稿待确认保存`,
    positiveText: '继 续',
    negativeText: '稍后(留在本页)',
    onPositiveClick: () => {
      const draft = shiftDraft()
      if (draft) {
        apiRow.value = null
        debugResult.value = null
        applyDetail(draft)
      }
    },
  })
}

async function handleSave() {
  try {
    await requestFormRef.value?.validate()
  } catch (e) {
    return
  }
  if (bodyType.value === 'json') {
    try {
      JSON.parse(jsonBodyText.value)
    } catch (e) {
      window.$message?.error('请求体 JSON 格式不合法，请修正后再保存')
      return
    }
  }
  // 提取/断言以面板字典转换后的存储列表做完整性校验（口径对齐 http_controller 保存链路）
  const extractCheck = validateExtractList(buildPerfExtractListFromDict(form.extract_variables))
  if (!extractCheck.valid) {
    window.$message?.error(extractCheck.message)
    return
  }
  const assertCheck = validateAssertList(buildPerfAssertListFromDict(form.assert_validators))
  if (!assertCheck.valid) {
    window.$message?.error(assertCheck.message)
    return
  }
  try {
    saving.value = true
    const payload = buildPayload()
    if (isEdit.value) {
      await api.updatePerfApi(payload)
      window.$message?.success('保存成功')
    } else {
      const res = await api.createPerfApi(payload)
      window.$message?.success('保存成功')
      // 新增落库后补 api_id，DataSource 卡与调试随即解锁
      await loadApi(res.data?.api_id || payload.api_id)
    }
    afterSaved()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

function handleBack() {
  const remain = remainDraftCount()
  if (remain > 0) {
    window.$dialog?.warning({
      title: '放弃剩余草稿',
      content: `还有 ${remain} 条导入草稿未确认保存，返回列表将放弃这些草稿`,
      positiveText: '放弃并返回',
      negativeText: '留在本页',
      onPositiveClick: () => {
        sessionStorage.removeItem(DRAFT_QUEUE_KEY)
        router.replace('/performance/api')
      },
    })
    return
  }
  router.replace('/performance/api')
}

// ---------- 调试链路（对齐 http_controller：弹窗选环境 → 页内 Response 卡回显） ----------

const debugModalVisible = ref(false)
const debugLoading = ref(false)
const debugResult = ref(null)

const debugForm = reactive({ envName: null, enableDataSource: false, sceneName: null })
const debugEnvOptions = ref([])
const debugEnvLoading = ref(false)
const debugSceneOptions = ref([])
const debugSceneLoading = ref(false)

/** Response 卡头部状态 tag：状态码 < 400 视为成功色 */
const responseStatusTagType = computed(() => ((debugResult.value?.status_code ?? 500) < 400 ? 'success' : 'error'))

const extractColumns = [
  { title: '变量名', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '提取值', key: 'extract_value', minWidth: 200, ellipsis: { tooltip: true } },
  {
    title: '结果', key: 'success', width: 80,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', size: 'small' },
        { default: () => (row.success ? '成功' : '失败') }),
  },
  { title: '错误', key: 'error', minWidth: 140, ellipsis: { tooltip: true } },
]

const assertColumns = [
  { title: '断言', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '实际值', key: 'actual_value', minWidth: 140, ellipsis: { tooltip: true } },
  {
    title: '结果', key: 'success', width: 80,
    render: (row) => h(NTag, { type: row.success ? 'success' : 'error', size: 'small' },
        { default: () => (row.success ? '通过' : '失败') }),
  },
  { title: '错误', key: 'error', minWidth: 140, ellipsis: { tooltip: true } },
]

const requestHeadersText = computed(() =>
    Object.entries(debugResult.value?.request_info?.headers || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n'),
)

const responseHeadersText = computed(() =>
    Object.entries(debugResult.value?.response_headers || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n'),
)

/** 响应体 JSON 自动美化（非 JSON 回落纯文本展示） */
const responseJsonFormatted = computed(() => {
  const text = String(debugResult.value?.response_data || '')
  if (!text) return ''
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch (e) {
    return null
  }
})

function copyText(text) {
  navigator.clipboard?.writeText(text).then(() => {
    window.$message?.success('已复制')
  }).catch(() => {})
}

/** 打开调试弹窗并预载环境候选 */
function openDebugModal() {
  if (!isEdit.value) {
    window.$message?.warning('请先保存接口后再调试')
    return
  }
  debugForm.envName = null
  debugForm.enableDataSource = false
  debugForm.sceneName = null
  debugEnvOptions.value = []
  debugSceneOptions.value = []
  debugModalVisible.value = true
  loadDebugEnvs()
}

async function loadDebugEnvs() {
  debugEnvLoading.value = true
  try {
    // 使用 request_project_id(所属应用)查询环境，与施压环境解析口径一致
    const projectId = form.request_project_id
    if (!projectId) {
      debugEnvOptions.value = []
      return
    }
    const res = await api.queryAssignConfigEnvs({ project_id: projectId, env_type: 'app' })
    debugEnvOptions.value = (Array.isArray(res?.data) ? res.data : []).map((name) => ({ label: name, value: name }))
  } catch (e) {
    debugEnvOptions.value = []
  } finally {
    debugEnvLoading.value = false
  }
}

/** 加载接口绑定的数据源场景列表（一个接口只能有一个数据源） */
async function loadDebugScenes() {
  if (!form.api_id) {
    debugSceneOptions.value = []
    return
  }
  debugSceneLoading.value = true
  try {
    const res = await api.listPerfDatasetsForApi({ api_id: form.api_id })
    const rows = (res.data || []).filter((row) => row.bind_api_id === form.api_id)
    // 一个接口只能有一个数据源，取第一条
    const dsRow = rows.length > 0 ? rows[0] : null
    if (dsRow) {
      debugSceneOptions.value = (dsRow.dataset_names || []).map((name) => ({ label: name, value: name }))
    } else {
      debugSceneOptions.value = []
    }
  } catch (e) {
    debugSceneOptions.value = []
  } finally {
    debugSceneLoading.value = false
  }
}

/** 启用数据源开关变化时加载场景列表 */
function onDebugEnableDataSourceChange(enabled) {
  if (enabled) {
    loadDebugScenes()
  } else {
    debugForm.sceneName = null
    debugSceneOptions.value = []
  }
}

async function confirmDebug() {
  // 启用数据源时必须选择场景
  if (debugForm.enableDataSource && !debugForm.sceneName) {
    window.$message?.warning('启用数据源时请选择场景名称')
    return
  }
  debugLoading.value = true
  debugResult.value = null
  try {
    const res = await api.debugPerfApi({
      api_id: form.api_id,
      env_name: debugForm.envName,
      // 对齐 autotest 设计：一个接口绑定一个数据源，调试时选择是否启用 + 场景名称
      enable_data_source: debugForm.enableDataSource,
      scene_name: debugForm.enableDataSource ? debugForm.sceneName : null,
    })
    debugResult.value = res.data
    debugModalVisible.value = false
    if (res.data?.success) {
      window.$message?.success('调试通过')
    } else {
      window.$message?.warning('调试未通过，请查看 Response 详情')
    }
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    debugLoading.value = false
  }
}
</script>

<style scoped>
/* 卡片壳 / 标题 / 折叠见 styles/autotest-theme.scss .step-editor-card */

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header-row--with-actions {
  padding-right: 220px; /* 预留右侧 status / 结论 tag 空间 */
}

.panel-title-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  user-select: none;
}

.panel-collapse-icon {
  cursor: pointer;
}

/* Request 表单行：flex 多列（对齐 http_controller 行式布局） */
.request-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.request-field-type {
  flex: 0 0 auto;
  min-width: 0;
}

/* 占位撑开：将调试/保存按钮推到行尾右侧 */
.request-field-spacer {
  flex: 1;
  min-width: 0;
}

.request-field-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  padding-top: 4px;
}

.request-field-method {
  flex: 0 0 18%;
  min-width: 0;
}

.request-field-url {
  flex: 1;
  min-width: 0;
}

.request-field-third {
  flex: 1;
  min-width: 0;
}

.body-editor {
  margin-top: 12px;
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}

.headers-pre {
  margin: 0;
  padding: 8px 12px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--n-action-color, rgba(128, 128, 128, 0.08));
  border-radius: 6px;
  cursor: copy;
}

.response-editor {
  min-height: 320px;
  border-radius: 8px;
  overflow: hidden;
}

.response-text :deep(textarea) {
  font-family: 'Fira Code', monospace;
}
</style>
