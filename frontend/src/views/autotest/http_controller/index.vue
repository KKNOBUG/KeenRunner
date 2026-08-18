<template>
  <StepDataSourcePanel
      v-if="!props.hideDataSource"
      ref="dataSourcePanelRef"
      :step="props.step"
      :readonly="props.readonly"
      :step-name="state.form.step_name"
      step-type-label="HTTP请求"
      v-model:data-source-id="state.form.data_source_id"
      v-model:data-source-name="state.form.data_source_name"
      v-model:data-source-desc="state.form.data_source_desc"
  />

  <n-card :bordered="false" style="width: 100%;" :class="['step-editor-card', { 'is-collapsed': requestCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleRequestCardCollapsed"
            @keydown.enter.prevent="toggleRequestCardCollapsed"
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
          :rules="rules"
          :model="state.form"
          label-placement="left"
          class="step-editor-form"
          label-width="80px"
          size="small"
          ref="formRef"
      >
        <!-- 第一行：请求方式20% + 请求地址（与调试同栏无缝）；第二行：步骤名称、所属应用、配置名称 -->
        <div class="http-request-rows">
          <div class="http-request-row http-request-row-bottom">
            <n-form-item label="请求方式" path="method" required class="http-field-method">
              <n-select
                  v-model:value="state.form.method"
                  placeholder="请选择请求方式"
                  :options="methodOptions"
                  :render-label="renderMethodLabel"
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
            <div class="http-url-debug-slot">
              <n-form-item
                  v-if="!props.readonly"
                  label="请求地址"
                  path="url"
                  required
                  class="http-field-url"
              >
                <div class="http-url-debug-inline">
                  <n-input
                      v-model:value="state.form.url"
                      placeholder="请输入请求地址"
                      clearable
                      class="request-toolbar-input-fill"
                      :disabled="props.readonly"
                  />
                  <n-button type="primary" size="small" class="http-debug-btn" @click="debugging" :loading="debugLoading">
                    调试
                  </n-button>
                </div>
              </n-form-item>
              <n-form-item
                  v-else
                  label="请求地址"
                  path="url"
                  required
                  class="http-field-url"
              >
                <n-input
                    v-model:value="state.form.url"
                    placeholder="请输入请求地址"
                    clearable
                    class="request-toolbar-input-fill"
                    :disabled="props.readonly"
                />
              </n-form-item>
            </div>
          </div>
          <div class="http-request-row http-request-row-top">
            <n-form-item label="步骤名称" path="step_name" required class="http-field-step-name">
              <n-input
                  v-model:value="state.form.step_name"
                  :placeholder="props.lockStepName ? '公共接口：与用例名称保持一致' : '请输入步骤名称'"
                  :clearable="!props.lockStepName"
                  class="request-step-name-input"
                  :disabled="props.readonly || props.lockStepName"
              />
            </n-form-item>
            <n-form-item label="所属应用" path="request_project_id" required class="http-field-project">
              <n-select
                  v-model:value="state.form.request_project_id"
                  placeholder="所属应用"
                  :options="projectOptions"
                  :loading="projectLoading"
                  clearable
                  filterable
                  class="request-toolbar-select"
                  :disabled="props.readonly || props.lockProject"
              />
            </n-form-item>
            <n-form-item label="配置名称" path="request_config_name" required class="http-field-config">
              <n-select
                  v-model:value="state.form.request_config_name"
                  placeholder="配置名称"
                  :options="httpConfigNameOptions"
                  :loading="httpConfigNameLoading"
                  clearable
                  filterable
                  tag
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
          </div>
        </div>

        <!-- 步骤描述（公共接口：锁定为用例描述） -->
        <n-form-item label="步骤描述" path="description">
          <n-input
              type="textarea"
              v-model:value="state.form.description"
              :placeholder="props.lockStepDesc ? '公共接口：与用例描述保持一致' : '请输入步骤描述'"
              :clearable="!props.lockStepDesc"
              :autosize="{ minRows: 1 }"
              style="width: 100%;"
              :disabled="props.readonly || props.lockStepDesc"
          />
        </n-form-item>
      </n-form>

      <!-- 请求配置 -->
      <n-tabs type="line" animated style="margin-top: 16px;">
        <n-tab-pane name="headers" tab="请求头">
          <template #tab>
            <n-badge :value="state.form.headers.length" :max="99" show-zero>
              <span>请求头</span>
            </n-badge>
          </template>
          <KeyValueEditor
              v-model:items="state.form.headers"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="params" tab="请求体">
          <template #tab>
            <n-badge :value="getBodyCount" :max="99" show-zero>
              <span>请求体</span>
            </n-badge>
          </template>
          <n-radio-group v-model:value="state.form.bodyType" name="bodyType" :disabled="props.readonly">
            <n-space>
              <n-radio value="none">none</n-radio>
              <n-radio value="params">params</n-radio>
              <n-radio value="form-data">form-data</n-radio>
              <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
              <n-radio value="json">json</n-radio>
              <n-radio value="xml">xml</n-radio>
              <n-radio value="raw">raw</n-radio>
            </n-space>
          </n-radio-group>
          <div v-if="state.form.bodyType === 'params'">
            <KeyValueEditor
                v-model:items="state.form.params"
                :body-type="'none'"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'form-data'">
            <KeyValueEditor
                v-model:items="state.form.bodyParams"
                :body-type="state.form.bodyType"
                :enableFile="true"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'x-www-form-urlencoded'">
            <KeyValueEditor
                v-model:items="state.form.bodyForm"
                :body-type="state.form.bodyType"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'json'">
            <monaco-editor
                v-model:value="state.form.jsonBody"
                lang="json"
                :options="monacoEditorOptionsForBody()"
                :read-only="props.readonly"
                class="json-editor"
                style="min-height: 400px; height: auto; margin-top: 12px;"
            />
          </div>
          <div v-if="state.form.bodyType === 'xml'">
            <monaco-editor
                v-model:value="state.form.xmlBody"
                lang="xml"
                :options="monacoEditorOptionsForBody()"
                :read-only="props.readonly"
                class="json-editor"
                style="min-height: 400px; height: auto; margin-top: 12px;"
            />
          </div>
          <div v-if="state.form.bodyType === 'raw'">
            <n-input
                v-model:value="state.form.rawBody"
                type="textarea"
                placeholder="请输入 raw 请求体文本"
                :rows="12"
                style="margin-top: 12px;"
                :disabled="props.readonly"
            />
          </div>

        </n-tab-pane>
        <n-tab-pane name="defined_variables" tab="变量">
          <template #tab>
            <n-badge :value="state.form.defined_variables.length" :max="99" show-zero>
              <span>变量</span>
            </n-badge>
          </template>
          <KeyValueEditor
              v-model:items="state.form.defined_variables"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="extract_variables" tab="提取">
          <template #tab>
            <n-badge :value="extractCount" :max="99" show-zero>
              <span>提取</span>
            </n-badge>
          </template>
          <StepExtractPanel
              v-model="state.form.extract_variables"
              mode="response"
              :readonly="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="assert_validators" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <StepAssertPanel
              v-model="state.form.assert_validators"
              mode="response"
              :readonly="props.readonly"
          />
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <!-- 响应结果卡片：在加载中或有响应数据时展示 -->
  <n-card
      v-if="response || debugLoading"
      :bordered="false"
      style="width: 100%; margin-top: 8px;"
      :class="['step-editor-card', { 'is-collapsed': responseCardCollapsed }]"
      ref="debugResultRef"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleResponseCardCollapsed"
            @keydown.enter.prevent="toggleResponseCardCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="responseCardCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">Response</div>
        </div>
        <div class="card-header-actions">
          <n-space align="center" :wrap="false">
            <n-space v-if="response && !debugLoading" align="center" :wrap="false">
              <n-tag :type="responseStatusType" round size="small">Status: {{ response.status }}</n-tag>
              <n-tag :type="durationTagType" round size="small">Time: {{ response.duration }}ms</n-tag>
              <n-tag :type="sizeTagType" round size="small">Size: {{ response.size }}</n-tag>
              <n-tag round>Type: {{ contentType }}</n-tag>
            </n-space>
            <n-tag v-if="debugLoading" type="info" round size="small">
              <template #icon>
                <n-spin size="small"/>
              </template>
              请求中...
            </n-tag>
          </n-space>
        </div>
      </div>
    </template>
    <n-collapse-transition :show="!responseCardCollapsed">
      <!-- 加载状态 -->
      <div v-if="debugLoading" class="debug-loading">
        <n-spin size="large" description="正在发送请求，请稍候..."/>
      </div>
      <!-- 响应内容 -->
      <n-tabs v-else type="line" animated>
        <!-- 请求信息 -->
        <n-tab-pane name="requestInfo" tab="请求信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['requestBasic', 'requestHeaders', 'requestBody']">
              <n-collapse-item title="Basic" name="requestBasic">
                <n-space vertical :size="12">
                  <n-descriptions bordered :column="2" size="small">
                    <n-descriptions-item label="方法">
                      <n-tag :type="methodTagType">{{ requestInfo.method }}</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item label="URL">
                      <n-text copyable>{{ requestInfo.url }}</n-text>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Headers" name="requestHeaders">
                <n-space vertical :size="12">
                      <pre v-if="requestHeadersText"
                           @click="copyTextContent(requestHeadersText)">{{ requestHeadersText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Cookies" name="requestCookies">
                <n-space vertical :size="12">
                      <pre v-if="requestCookiesText"
                           @click="copyTextContent(requestCookiesText)">{{ requestCookiesText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item :title="`Body (${requestBodyType})`" name="requestBody">
                <div v-if="isRawRequest" class="request-raw-body">
                  <pre>{{ requestInfo.rawBody || '(空)' }}</pre>
                </div>
                <div v-else-if="isXmlRequest">
                  <monaco-editor
                      v-model:value="requestInfo.rawBody"
                      lang="xml"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <div v-else-if="isJsonRequest">
                  <monaco-editor
                      v-model:value="formattedRequestJson"
                      lang="json"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <n-data-table
                    v-else
                    :columns="[{title:'Key',key:'key'}, {title:'Value',key:'value'}]"
                    :data="requestBodyData"
                    size="small"
                />
              </n-collapse-item>
            </n-collapse>

          </n-space>

        </n-tab-pane>
        <!-- 响应信息 -->
        <n-tab-pane name="responseInfo" tab="响应信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['responseHeaders', 'responseCookies', 'responseBody']"
                        arrow-placement="right">
              <n-collapse-item title="Headers" name="responseHeaders">
                <n-space vertical :size="12">
                      <pre v-if="responseHeadersText"
                           @click="copyTextContent(responseHeadersText)">{{ responseHeadersText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Cookies" name="responseCookies">
                <n-space vertical :size="12">
                      <pre v-if="responseCookiesText"
                           @click="copyTextContent(responseCookiesText)">{{ responseCookiesText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item :title="`Body (${contentType})`" name="responseBody">
                <div v-if="isJsonResponse">
                  <monaco-editor
                      v-model:value="formattedResponse"
                      lang="json"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <div v-else-if="isXmlResponse">
                  <monaco-editor
                      v-model:value="formattedResponseXml"
                      lang="xml"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <n-code
                    v-else
                    :code="typeof response.data === 'object'? JSON.stringify(response.data, null, 2) : response.data || ''"
                    :language="responseLanguage"
                    show-line-numbers
                    class="response-code overlay-scroll"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
        </n-tab-pane>
        <!-- 数据提取 -->
        <n-tab-pane name="extract_variables" tab="数据提取">
          <n-data-table
              v-if="response && response.extract_results && response.extract_results.length > 0"
              :columns="extractColumns"
              :data="response.extract_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无数据提取结果"/>
        </n-tab-pane>
        <!-- 断言结果 -->
        <n-tab-pane name="assert" tab="断言结果">
          <n-data-table
              v-if="response && response.validator_results && response.validator_results.length > 0"
              :columns="validatorColumns"
              :data="response.validator_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无断言结果"/>
        </n-tab-pane>
        <!-- 执行日志 -->
        <n-tab-pane name="logs" tab="执行日志">
          <n-space vertical :size="12" v-if="response && response.logs && response.logs.length > 0">
                <pre
                    v-for="(log, index) in response.logs"
                    :key="index"
                    class="log-item"
                >{{ log }}</pre>
          </n-space>
          <n-empty v-else description="暂无执行日志"/>
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <!-- 调试前选择执行环境 -->
  <n-modal
      v-model:show="debugModalVisible"
      preset="dialog"
      title="选择调试环境"
      positive-text="确定"
      negative-text="取消"
      @positive-click="confirmDebugModal"
  >
    <div style="padding: 8px 0;">
      <div style="margin-bottom: 8px;">执行环境：</div>
      <n-select
          v-model:value="selectedDebugEnvName"
          :options="envOptions"
          :loading="envLoading"
          placeholder="请选择执行环境"
          clearable
          filterable
          style="width: 100%;"
      />
    </div>
  </n-modal>
</template>

<script setup>
import {computed, h, nextTick, ref, watch} from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCode,
  NCollapse,
  NCollapseItem,
  NCollapseTransition,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  NText,
} from 'naive-ui'
import api from "@/api";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";
import MonacoEditor from "@/components/monaco/index.vue";
import TheIcon from "@/components/icon/TheIcon.vue";
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import StepDataSourcePanel from '@/components/autotest/StepDataSourcePanel.vue'
import {
  ASSERT_MODE_RESPONSE,
  buildAssertListFromDict,
  buildExtractListFromDict,
  countDictKeys,
  EXTRACT_MODE_RESPONSE,
  hydrateAssertDictFromBackend,
  hydrateExtractDictFromBackend,
  normalizeBackendList,
  validateAssertList,
  validateExtractList,
} from '@/utils/autotestExtractAssert'
import { useStepEditorForm } from '@/composables/step-editor'
import {useUserStore} from '@/store';
import {useRoute} from 'vue-router'

/**
 * HTTP 控制器组件 Props
 *
 * 数据接收说明：
 * 1. config: 从步骤树传递的配置数据（step.config），包含：
 *    - method, url, headers, params
 *    - data (JSON body), form_data, form_urlencoded
 *    - extract_variables, assert_validators, defined_variables
 *
 * 2. step: 完整的步骤对象，包含：
 *    - step.id: 步骤ID（step_code）
 *    - step.type: 步骤类型（'http'）
 *    - step.name: 步骤名称（step_name）
 *    - step.config: 配置数据（同 props.config）
 *    - step.original: 完整的原始后端步骤数据，包含所有字段：
 *      * step_code, step_name, step_desc, step_type
 *      * request_method, request_url, request_header, request_body, request_params
 *      * extract_variables, assert_validators, defined_variables
 *      * id, case_id, parent_step_id, children 等所有后端返回的字段
 *
 * 使用方式：
 * - 访问配置数据：props.config.method, props.config.url
 * - 访问原始数据：props.step.original.step_name, props.step.original.step_desc
 * - 访问步骤信息：props.step.name, props.step.id
 */
const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  },
  projectOptions: {
    type: Array,
    default: () => []
  },
  projectLoading: {
    type: Boolean,
    default: false
  },
  availableVariableList: {
    type: Array,
    default: () => []
  },
  assistFunctions: {
    type: Array,
    default: () => []
  },
  readonly: {type: Boolean, default: false},
  hideDataSource: {type: Boolean, default: false},
  /** 公共接口用例：Request 面板「所属应用」锁定（只读），值为用例所属应用 */
  lockProject: {type: Boolean, default: false},
  caseProjectId: {type: [Number, String], default: null},
  /** 公共接口用例：Request 面板「步骤描述」锁定（只读），值为用例描述 */
  lockStepDesc: {type: Boolean, default: false},
  caseDesc: {type: String, default: null},
  /** 公共接口用例：Request 面板「步骤名称」锁定（只读），值为用例名称 */
  lockStepName: {type: Boolean, default: false},
  caseName: {type: String, default: null}
})

const emit = defineEmits(['update:config'])

const formRef = ref(null);
const route = useRoute()

const requestCardCollapsed = ref(false)
const responseCardCollapsed = ref(false)
const toggleRequestCardCollapsed = () => {
  requestCardCollapsed.value = !requestCardCollapsed.value
}
const toggleResponseCardCollapsed = () => {
  responseCardCollapsed.value = !responseCardCollapsed.value
}

// 请求方式下拉框
const methodOptions = [
  {label: 'GET', value: 'GET', color: '#2080F0'},
  {label: 'POST', value: 'POST', color: '#18A058'},
  {label: 'PUT', value: 'PUT', color: '#FCA130'},
  {label: 'DELETE', value: 'DELETE', color: '#F4511E'}
]
const renderMethodLabel = (option) => {
  return h(
      'span',
      {style: {color: option.color, fontWeight: '600'}},
      option.label
  )
}
// 表单验证规则
const rules = {
  method: [
    {
      required: true,
      message: '请选择请求方式',
      trigger: 'change'
    }
  ],
  url: [
    {
      required: true,
      message: '请输入请求地址',
      trigger: 'blur'
    }
  ],
  request_project_id: [
    {
      validator(_rule, value) {
        if (value === null || value === undefined || value === '') {
          return new Error('请选择所属应用')
        }
        return true
      },
      trigger: ['change', 'blur']
    }
  ],
  request_config_name: [
    {
      validator(_rule, value) {
        if (value === null || value === undefined || String(value).trim() === '') {
          return new Error('请填写或选择配置名称')
        }
        return true
      },
      trigger: ['change', 'blur']
    }
  ],
  step_name: [
    {
      required: true,
      message: '请输入步骤名称',
      trigger: 'blur'
    }
  ]
}

// 注意：不再使用 kvObjectToList 和 kvListToObject，所有字段都必须是列表格式

/** 从 props 合并出表单值（config 优先、original 兜底）；纯函数，供 useStepEditorForm 灌入 */
const hydrateHttpForm = (p) => {
  const cfg = p.config || {}
  const step = p.step || {}
  const original = step.original || {}

  // 请求体类型（与后端 request_args_type 枚举一致：none, params, form-data, x-www-form-urlencoded, json, raw）
  const requestArgsType = cfg.request_args_type ?? original.request_args_type
  let bodyType
  if (requestArgsType) {
    bodyType = requestArgsType
  } else if (cfg.data) {
    bodyType = 'json'
  } else if (cfg.form_data) {
    bodyType = 'form-data'
  } else if (cfg.form_urlencoded) {
    bodyType = 'x-www-form-urlencoded'
  } else if (cfg.request_text != null && cfg.request_text !== '') {
    bodyType = 'raw'
  } else {
    bodyType = 'none'
  }

  const requestText = cfg.request_text ?? original.request_text ?? ''
  let xmlBody
  let rawBody
  if (bodyType === 'xml') {
    xmlBody = requestText
    rawBody = ''
  } else if (bodyType === 'raw') {
    rawBody = requestText
    xmlBody = ''
  } else {
    // 其它类型（json、form-data 等）下报文暂存于 request_text，同时回填 xml 与 raw，避免切换类型后数据丢失
    xmlBody = requestText
    rawBody = requestText
  }

  // form_data、form_urlencoded 必须是列表格式，每个元素包含 key、value、desc、type（form-data 需 type 供 KeyValueEditor 显示「数据」列）
  const bodyParamsRaw = Array.isArray(cfg.form_data) ? cfg.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : [])
  const bodyParams = bodyParamsRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))
  const bodyFormRaw = Array.isArray(cfg.form_urlencoded) ? cfg.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : [])
  const bodyForm = bodyFormRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))

  // JSON 请求体：优先使用配置中的原始文本，避免格式错误时被清空
  let jsonBody
  const jsonBodyText = cfg.jsonBodyText
  if (jsonBodyText !== undefined && jsonBodyText !== null) {
    jsonBody = String(jsonBodyText)
  } else {
    try {
      const body = cfg.data ?? original.request_body
      if (body === null || body === undefined) {
        jsonBody = ''
      } else if (typeof body === 'string') {
        jsonBody = body
      } else {
        jsonBody = Object.keys(body).length ? JSON.stringify(body, null, 2) : ''
      }
    } catch {
      jsonBody = ''
    }
  }

  return {
    url: cfg.url || original.request_url || '',
    method: cfg.method || original.request_method || 'GET',
    // headers、params 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
    headers: Array.isArray(cfg.headers) ? cfg.headers : (Array.isArray(original.request_header) ? original.request_header : []),
    bodyType,
    params: Array.isArray(cfg.params) ? cfg.params : (Array.isArray(original.request_params) ? original.request_params : []),
    bodyParams,
    bodyForm,
    jsonBody,
    xmlBody,
    rawBody,
    // 步骤名称优先 config（含 emit 回写），再回退 step.name / original，避免失焦时被旧 original 覆盖
    step_name: cfg.step_name !== undefined ? cfg.step_name : (step.name || original.step_name || ''),
    description: cfg.step_desc !== undefined ? (cfg.step_desc ?? '') : (original.step_desc || ''),
    request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
    request_config_name: cfg.request_config_name ?? original.request_config_name ?? null,
    data_source_id: cfg.data_source_id ?? original.data_source_id ?? null,
    data_source_name: cfg.data_source_name ?? original.data_source_name ?? '',
    data_source_desc: cfg.data_source_desc ?? original.data_source_desc ?? '',
    // defined_variables 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
    defined_variables: Array.isArray(cfg.defined_variables) ? cfg.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : []),
    extract_variables: hydrateExtractDictFromBackend(
        normalizeBackendList(cfg.extract_variables ?? original.extract_variables),
        EXTRACT_MODE_RESPONSE
    ),
    assert_validators: hydrateAssertDictFromBackend(
        normalizeBackendList(cfg.assert_validators ?? original.assert_validators),
        ASSERT_MODE_RESPONSE
    ),
  }
}

const { form, isExternalUpdate, syncFromExternal } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({
    url: '',
    method: 'GET',
    headers: [],
    bodyType: 'none',
    params: [],
    bodyParams: [],
    bodyForm: [],
    jsonBody: '',
    xmlBody: '',
    rawBody: '',
    step_name: '',
    description: '',
    request_project_id: null,
    request_config_name: null,
    data_source_id: null,
    data_source_name: '',
    data_source_desc: '',
    defined_variables: [],
    extract_variables: {},
    assert_validators: {},
  }),
  hydrate: hydrateHttpForm,
  buildConfig: () => buildConfigFromState(),
  watchFields: (f) => [
    f.step_name, f.description, f.method,
    f.url, f.headers, f.params,
    f.bodyType, f.bodyParams, f.bodyForm,
    f.jsonBody, f.xmlBody, f.rawBody, f.request_project_id,
    f.request_config_name,
    f.data_source_id, f.data_source_name, f.data_source_desc,
    f.defined_variables, f.extract_variables, f.assert_validators
  ],
  debounceMs: 300,
})

/** 模板与各 helper 沿用 state.form 访问方式 */
const state = { form }

// 公共接口（lockProject）：所属应用锁定为用例所属应用，外部变化时静默回填（不触发 emit 回写循环）
watch(
    () => props.caseProjectId,
    (pid) => {
      if (!props.lockProject || pid == null || pid === '') return
      if (Number(state.form.request_project_id) !== Number(pid)) {
        syncFromExternal(() => {
          state.form.request_project_id = Number(pid)
        })
      }
    },
)

// 公共接口（lockStepDesc）：步骤描述锁定为用例描述，外部变化时静默回填（不触发 emit 回写循环）
watch(
    () => props.caseDesc,
    (desc) => {
      if (!props.lockStepDesc || desc == null) return
      if ((state.form.description ?? '') !== desc) {
        syncFromExternal(() => {
          state.form.description = desc
        })
      }
    },
)

// 公共接口（lockStepName）：步骤名称锁定为用例名称，外部变化时静默回填（不触发 emit 回写循环）
watch(
    () => props.caseName,
    (name) => {
      if (!props.lockStepName || name == null) return
      if ((state.form.step_name ?? '') !== name) {
        syncFromExternal(() => {
          state.form.step_name = name
        })
      }
    },
)

const httpConfigNameOptions = ref([])
const httpConfigNameLoading = ref(false)
const loadHttpConfigNames = async (projectId) => {
  const pid = projectId != null && projectId !== '' ? Number(projectId) : null
  if (!pid) {
    httpConfigNameOptions.value = []
    return
  }
  httpConfigNameLoading.value = true
  try {
    const res = await api.getEnvConfigNameList({ project_id: pid, env_type: 'api' })
    const list = Array.isArray(res?.data) ? res.data : []
    httpConfigNameOptions.value = list.map((name) => ({ label: name, value: name }))
  } catch (e) {
    console.error('加载配置名称列表失败', e)
    httpConfigNameOptions.value = []
  } finally {
    httpConfigNameLoading.value = false
  }
}
watch(
    () => state.form.request_project_id,
    (pid, prev) => {
      void loadHttpConfigNames(pid)
      if (pid == null || pid === '') {
        state.form.request_config_name = null
      } else if (prev != null && Number(pid) !== Number(prev)) {
        state.form.request_config_name = null
      }
    },
    { immediate: true }
)


// 父级切换用例类型时会暂存/恢复 data_source 指针并直接改写 step.config；此处把外部对
// config.data_source_* 的改动同步进表单，保证当前编辑器与步骤树一致。相等性判断 + syncFromExternal
// 共同抑制防抖 emit 回写循环（即便偶发一次 emit，回写的也是与 config 相同的值，自然收敛）。
watch(
    () => [props.config?.data_source_id, props.config?.data_source_name, props.config?.data_source_desc],
    ([dsId, dsName, dsDesc]) => {
      if (isExternalUpdate()) return
      if (state.form.data_source_id === dsId
          && state.form.data_source_name === dsName
          && state.form.data_source_desc === dsDesc) return
      syncFromExternal(() => {
        state.form.data_source_id = dsId ?? null
        state.form.data_source_name = dsName ?? ''
        state.form.data_source_desc = dsDesc ?? ''
      })
    },
)

const buildExtractForBackend = () =>
    buildExtractListFromDict(state.form.extract_variables, EXTRACT_MODE_RESPONSE)

const buildValidatorsForBackend = () =>
    buildAssertListFromDict(state.form.assert_validators, ASSERT_MODE_RESPONSE)

const buildConfigFromState = () => {
  // 列表格式：每个元素包含 key、value、desc
  // 确保 headers、params、form_data、form_urlencoded、defined_variables 都是列表格式
  const headersList = Array.isArray(state.form.headers) ? state.form.headers : []
  const paramsList = Array.isArray(state.form.params) ? state.form.params : []
  const variablesList = Array.isArray(state.form.defined_variables) ? state.form.defined_variables : []

  // 确保每个元素都有 key、value、desc 字段；form-data 需保留 type 以便 re-init 后 Text/File 选择不丢失
  const normalizeList = (list) => {
    return list.map(item => ({
      key: item.key || '',
      value: item.value || '',
      desc: item.desc || ''
    }))
  }
  const normalizeBodyParams = (list) => {
    return (Array.isArray(list) ? list : []).map(item => ({
      key: item.key || '',
      value: item.value ?? '',
      desc: item.desc || '',
      type: item.type || 'text'
    }))
  }

  let data = null
  let request_text = null

  // 始终从当前表单带出 form_data / form_urlencoded，避免切到 none 再切回时被 initFromConfig 清空
  const form_data = normalizeBodyParams(state.form.bodyParams)
  const form_urlencoded = Array.isArray(state.form.bodyForm) ? normalizeList(state.form.bodyForm) : []

  // JSON 报文：无论当前请求体类型为何都尽量保留，避免切换类型后保存导致 JSON 数据丢失
  // 空文本/纯空白归一为null：只有用户显式输入的JSON（含"{}"）才会落库
  let jsonBodyText = state.form.jsonBody ?? ''
  if (state.form.jsonBody && state.form.jsonBody.trim()) {
    try {
      data = JSON.parse(state.form.jsonBody)
    } catch {
      data = {}
    }
  }

  // XML / raw 报文：当前类型优先；切换到其它类型（json、form-data 等）时保留已填写的报文，避免保存后丢失
  if (state.form.bodyType === 'xml') {
    request_text = state.form.xmlBody ?? ''
  } else if (state.form.bodyType === 'raw') {
    request_text = state.form.rawBody ?? ''
  } else {
    request_text = state.form.xmlBody || state.form.rawBody || null
  }

  return {
    step_name: state.form.step_name || '',
    step_desc: state.form.description ?? '',
    method: state.form.method,
    url: state.form.url,
    headers: normalizeList(headersList),
    params: normalizeList(paramsList),
    request_args_type: state.form.bodyType,
    request_project_id: state.form.request_project_id ?? null,
    request_config_name: state.form.request_config_name != null && String(state.form.request_config_name).trim() !== ''
        ? String(state.form.request_config_name).trim()
        : null,
    data_source_id: state.form.data_source_id ?? null,
    data_source_name: state.form.data_source_name || '',
    data_source_desc: state.form.data_source_desc || '',
    data,
    jsonBodyText,
    form_data,
    form_urlencoded,
    request_text,
    extract_variables: buildExtractForBackend(),
    assert_validators: buildValidatorsForBackend(),
    defined_variables: normalizeList(variablesList)
  }
}


/* ======================================= */
/* =============== Request =============== */
/*  ====================================== */
/* 请求体数量计算 */
const getBodyCount = computed(() => {
  switch (state.form.bodyType) {
    case 'params':
    case 'x-www-form-urlencoded':
      return state.form.bodyForm.length
    case 'form-data':
      return state.form.bodyParams.length
    case 'json':
      return state.form.jsonBody.trim() ? 1 : 0
    case 'xml':
      return state.form.xmlBody.trim() ? 1 : 0
    case 'raw':
      return state.form.rawBody.trim() ? 1 : 0
    default:
      return 0
  }
})

watch(
    () => state.form.jsonBody,
    (newVal) => {
      if (newVal?.trim() && !['json'].includes(state.form.bodyType)) {
        state.form.bodyType = 'json'
      }
    },
    {deep: true}
)

const monacoEditorOptions = (readOnly) => {
  const options = {
    // 基础配置
    theme: 'vs-dark',
    fontSize: 14,
    tabSize: 4,
    // 布局与外观
    automaticLayout: true,
    minimap: {
      enabled: true
    },
    lineNumbers: 'on',
    renderLineHighlight: 'line',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    // 其他
    folding: true,
    foldingStrategy: 'auto',
    roundedSelection: false,
    cursorStyle: 'line',
  }
  if (readOnly) {
    options.readOnly = true
  }

  return options
}

// 请求体 JSON 编辑器：黑色背景 + JSON 语法校验（红色波浪线）
const monacoEditorOptionsForBody = () => {
  return {
    ...monacoEditorOptions(!!props.readonly),
  }
}

/* ======================================== */
/* =============== Response =============== */
/*  ======================================= */
const response = ref(null) // 存储调试响应结果
const debugLoading = ref(false) // 调试加载状态
const requestInfo = ref({  // 存储请求的详细信息
  url: '',
  method: '',
  headers: {},
  bodyType: 'none',
  jsonBody: ''
})

// 请求类型（不区分大小写匹配 Content-Type）
const contentType = computed(() => {
  const headers = response.value?.headers || {}
  // 不区分大小写地查找 content-type
  const contentTypeKey = Object.keys(headers).find(key => key.toLowerCase() === 'content-type')
  if (contentTypeKey) {
    return headers[contentTypeKey]?.split(';')[0] || 'text/plain'
  }
  return 'text/plain'
})

// 响应类型
const isJsonResponse = computed(() => {
  return contentType.value.includes('json')
})
const isXmlResponse = computed(() => {
  return contentType.value.toLowerCase().includes('xml')
})

const responseLanguage = computed(() => {
  const ct = contentType.value.toLowerCase()
  if (ct.includes('json')) return 'json'
  if (ct.includes('xml')) return 'xml'
  if (ct.includes('html')) return 'html'
  return 'text'
})
// 响应格式化
const formattedResponse = computed(() => {
  try {
    return JSON.stringify(response.value.data, null, 4)
  } catch {
    return response.value.data
  }
})
const formattedResponseXml = computed(() => {
  const data = response.value?.data
  if (data == null) return ''
  return typeof data === 'string' ? data : JSON.stringify(data, null, 2)
})

const responseHeadersText = computed(() => {
  return Object.entries(response.value?.headers || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const responseCookiesText = computed(() => {
  return Object.entries(response.value?.cookies || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const requestHeadersText = computed(() => {
  return Object.entries(requestInfo.value.headers || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const requestCookiesText = computed(() => {
  return Object.entries(requestInfo.value.cookies || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const copyTextContent = (text) => {
  navigator.clipboard.writeText(text).then(() => {
    $message.success('复制成功');
  }).catch((err) => {
    $message.error(`复制失败: ${err.message}`);
  });
}

const responseStatusType = computed(() => {
  if (!response.value) return 'default'
  if (response.value.status === 200) {
    return formattedResponse.value?.status === '000000' ? 'success' : 'error';
  }
  return response.value.status >= 400 ? 'error' : 'success'
})

const durationTagType = computed(() => {
  if (!response.value) return 'default'
  return response.value.duration > 1000 ? 'warning' : 'success'
})

const sizeTagType = computed(() => {
  if (!response.value) return 'default'
  return parseFloat(response.value.size) > 100 ? 'warning' : 'success'
})

// 响应-请求信息相关
const methodTagType = computed(() => {
  const method = requestInfo.value.method?.toUpperCase()
  return {
    GET: 'success',
    POST: 'warning',
    PUT: 'info',
    DELETE: 'error'
  }[method] || 'default'
})


const requestBodyType = computed(() => {
  const typeMap = {
    'none': 'None',
    'params': 'Params',
    'form-data': 'Form Data',
    'x-www-form-urlencoded': 'Form URL Encoded',
    'json': 'JSON',
    'xml': 'XML',
    'raw': 'Raw'
  }
  return typeMap[requestInfo.value.bodyType] || 'Params'
})

const isJsonRequest = computed(() => requestInfo.value.bodyType === 'json')
const isXmlRequest = computed(() => requestInfo.value.bodyType === 'xml')
const isRawRequest = computed(() => requestInfo.value.bodyType === 'raw')

const formattedRequestJson = computed(() => {
  try {
    return JSON.stringify(JSON.parse(requestInfo.value.jsonBody), null, 4)
  } catch {
    return requestInfo.value.jsonBody
  }
})

const requestBodyData = computed(() => {
  switch (requestInfo.value.bodyType) {
    case 'form-data':
      // 优先使用后端返回的处理后数据
      if (requestInfo.value.formData && typeof requestInfo.value.formData === 'object') {
        return Object.entries(requestInfo.value.formData).map(([key, value]) => ({key, value}))
      }
      return state.form.bodyParams.filter(item => item.key)
    case 'params':
    case 'x-www-form-urlencoded':
      // 优先使用后端返回的处理后数据
      if (requestInfo.value.formUrlencoded && typeof requestInfo.value.formUrlencoded === 'object') {
        return Object.entries(requestInfo.value.formUrlencoded).map(([key, value]) => ({key, value}))
      }
      return state.form.bodyForm.filter(item => item.key)
    default:
      return []
  }
})


const debugResultRef = ref(null)

const debugModalVisible = ref(false)
const envOptions = ref([])
const envLoading = ref(false)
/** 调试所选环境名称（与 /autotest/env/list、后端 schema 的 env_name 对应） */
const selectedDebugEnvName = ref(null)

const loadEnvNames = async () => {
  const pid = Number(state.form.request_project_id)
  if (!pid) {
    envOptions.value = []
    selectedDebugEnvName.value = null
    return
  }
  envLoading.value = true
  try {
    // { project_id: { api|file|database|redis: env_name[] } }
    const res = await api.listEnvNames({ project_id: [pid] })
    const byProject = res?.data || {}
    const byType = byProject[pid] || byProject[String(pid)] || {}
    const names = Array.isArray(byType.api) ? byType.api : []
    envOptions.value = names
        .filter((n) => n != null && String(n).trim() !== '')
        .map((n) => ({ label: String(n), value: String(n) }))
    if (envOptions.value.length > 0 && selectedDebugEnvName.value == null) {
      selectedDebugEnvName.value = envOptions.value[0].value
    }
  } catch (e) {
    console.error('加载环境列表失败', e)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

const openDebugModal = () => {
  const pid = Number(state.form.request_project_id)
  if (!pid) {
    $message.warning('请先选择所属应用')
    return
  }
  selectedDebugEnvName.value = null
  debugModalVisible.value = true
  loadEnvNames()
}

const confirmDebugModal = () => {
  const envName = selectedDebugEnvName.value
  if (!envName || !String(envName).trim()) {
    $message.warning('请选择执行环境')
    return false
  }
  debugModalVisible.value = false
  doDebugRequest(String(envName).trim())
}

/* 调试方法：先选环境再发请求 */
const debugging = async () => {
  try {
    await formRef.value?.validate?.()
  } catch (_) {
    $message.warning("请填写必填字段")
    return
  }
  openDebugModal()
}

const doDebugRequest = async (env_name) => {
  const extractCheck = validateExtractList(buildExtractForBackend())
  if (!extractCheck.valid) {
    $message.error(extractCheck.message)
    return
  }
  const assertCheck = validateAssertList(buildValidatorsForBackend())
  if (!assertCheck.valid) {
    $message.error(assertCheck.message)
    return
  }

  const userStore = useUserStore()
  const currentUser = userStore.username
  debugLoading.value = true
  response.value = null

  try {
    const cfg = buildConfigFromState()

    const headersObj = cfg.headers.reduce((acc, {key, value}) => {
      if (key) acc[key] = value
      return acc
    }, {})
    const paramsObj = cfg.params.reduce((acc, {key, value}) => {
      if (key) acc[key] = value
      return acc
    }, {})

    requestInfo.value = {
      method: cfg.method,
      url: cfg.url,
      headers: headersObj,
      bodyType: cfg.request_args_type ?? 'none',
      jsonBody: state.form.jsonBody,
      rawBody: state.form.bodyType === 'xml' ? (state.form.xmlBody ?? '') : (state.form.rawBody ?? ''),
      formData: state.form.bodyType === 'form-data' ? state.form.bodyParams : null,
      formUrlencoded: state.form.bodyType === 'x-www-form-urlencoded' ? state.form.bodyForm : null
    }

    const caseId = route.query.case_id ? Number(route.query.case_id) : null
    const original = props.step?.original || {}

    const debugPayload = {
      env_name: String(env_name || '').trim(),
      case_id: caseId,
      step_type: original.step_type || 'HTTP/HTTPS协议网络请求',
      step_name: state.form.step_name || original.step_name || 'HTTP 调试',
      request_url: cfg.url,
      request_method: cfg.method,
      request_args_type: cfg.request_args_type ?? original.request_args_type ?? 'none',
      request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
      request_config_name:
          cfg.request_config_name != null && String(cfg.request_config_name).trim() !== ''
              ? String(cfg.request_config_name).trim()
              : (original.request_config_name != null && String(original.request_config_name).trim() !== ''
                  ? String(original.request_config_name).trim()
                  : ''),
      request_params: Array.isArray(cfg.params) && cfg.params.length > 0 ? cfg.params : null,
      request_body: cfg.data,
      request_form_data: Array.isArray(cfg.form_data) && cfg.form_data.length > 0 ? cfg.form_data : null,
      request_form_urlencoded: Array.isArray(cfg.form_urlencoded) && cfg.form_urlencoded.length > 0 ? cfg.form_urlencoded : null,
      request_text: cfg.request_text ?? null,
      request_header: Array.isArray(cfg.headers) && cfg.headers.length > 0 ? cfg.headers : null,
      defined_variables: Array.isArray(cfg.defined_variables) && cfg.defined_variables.length > 0 ? cfg.defined_variables : null,
      session_variables: Array.isArray(cfg.session_variables) && cfg.session_variables.length > 0 ? cfg.session_variables : null,
      extract_variables: buildExtractForBackend(),
      assert_validators: buildValidatorsForBackend(),
      created_user: currentUser,
      updated_user: currentUser
    }

    const responseData = await api.httpRequestDebugging(debugPayload);

    if (responseData.code === '000000') {
      response.value = responseData.data;
      // 确保 extract_results、validator_results、logs 等字段被正确保留
      if (responseData.data.extract_results) {
        response.value.extract_results = responseData.data.extract_results
      }
      if (responseData.data.validator_results) {
        response.value.validator_results = responseData.data.validator_results
      }
      if (responseData.data.logs) {
        response.value.logs = responseData.data.logs
      }
      // 从后端响应中获取处理后的请求信息（变量替换后的实际报文）
      if (responseData.data.request_info) {
        const reqInfo = responseData.data.request_info
        requestInfo.value = {
          method: reqInfo.method,
          url: reqInfo.url,
          headers: reqInfo.headers || {},
          cookies: reqInfo.cookies || {},
          bodyType: reqInfo.body_type || 'none',
          jsonBody: reqInfo.body_type === 'json' && reqInfo.body ? JSON.stringify(reqInfo.body, null, 2) : '',
          formData: reqInfo.body_type === 'form-data' ? reqInfo.body : null,
          formUrlencoded: reqInfo.body_type === 'x-www-form-urlencoded' ? reqInfo.body : null,
          rawBody: (reqInfo.body_type === 'raw' || reqInfo.body_type === 'xml') && reqInfo.request_text != null ? reqInfo.request_text : (requestInfo.value.rawBody ?? '')
        }
      }
      $message.success('调试成功');
      // 滚动到调试结果区域
      nextTick(() => {
        debugResultRef.value?.$el?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      })
    } else {
      $message.error(`请求失败：${responseData.message}`);
    }
  } catch (error) {
    $message.error(`调试失败：${error.message}`);
  } finally {
    // 关闭加载状态
    debugLoading.value = false
  }
};

const extractCount = computed(() => countDictKeys(state.form.extract_variables))
const validatorsCount = computed(() => countDictKeys(state.form.assert_validators))

// 数据提取结果表格列定义
const extractColumns = [
  {
    title: '变量名',
    key: 'name',
    width: 120
  },
  {
    title: '提取来源',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Request Json': 'Request Json',
        'Request Text': 'Request Text',
        'Request XML': 'Request XML',
        'Request Headers': 'Request Headers',
        'Request Cookie': 'Request Cookie',
        'Request Form-Data': 'Request Form-Data',
        'Response Json': 'Response Json',
        'Response Text': 'Response Text',
        'Response XML': 'Response XML',
        'Response Headers': 'Response Headers',
        'Response Cookie': 'Response Cookie'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '提取范围',
    key: 'scope',
    width: 120,
    render: (row) => (row.scope === 'ALL' ? '全部提取' : '部分提取')
  },
  {
    title: '提取路径',
    key: 'expr',
    width: 120,
    ellipsis: {tooltip: true}
  },
  {
    title: '提取值',
    key: 'extract_value',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.extract_value === null || row.extract_value === undefined) {
        return '-'
      }
      const value = typeof row.extract_value === 'object'
          ? JSON.stringify(row.extract_value)
          : String(row.extract_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '提取结果',
    key: 'success',
    width: 120,
    render: (row) => {
      return h(NTag, {
        type: row.success ? 'success' : 'error',
        round: true,
        size: 'small'
      }, {default: () => row.success ? 'pass' : 'fail'})
    }
  },
  {
    title: '错误信息',
    key: 'error',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => row.error || '-'
  }
]

// 断言结果表格列定义
const validatorColumns = [
  {
    title: '断言名称',
    key: 'name',
    width: 120,
    ellipsis: {tooltip: true}
  },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Request Json': 'requestJson',
        'Request Text': 'requestText',
        'Request XML': 'requestXml',
        'Request Headers': 'requestHeaders',
        'Request Cookie': 'requestCookie',
        'Request Form-Data': 'requestFormData',
        'Response Json': 'responseJson',
        'Response Text': 'responseText',
        'Response XML': 'responseXml',
        'Response Headers': 'responseHeaders',
        'Response Cookie': 'responseCookie',
        '变量池': '变量池'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '断言路径',
    key: 'expr',
    width: 130,
    ellipsis: {tooltip: true}
  },
  {
    title: '结果值',
    key: 'actual_value',
    width: 150,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.actual_value === null || row.actual_value === undefined) {
        return '-'
      }
      return String(row.actual_value)
    }
  },
  {
    title: '断言方式',
    key: 'operation',
    width: 100
  },
  {
    title: '期望值',
    key: 'expect_value',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.except_value === null || row.except_value === undefined) {
        return '-'
      }
      return String(row.except_value)
    }
  },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => {
      return h(NTag, {
        type: row.success ? 'success' : 'error',
        round: true,
        size: 'small'
      }, {default: () => row.success ? 'pass' : 'fail'})
    }
  },
  {
    title: '错误信息',
    key: 'error',
    ellipsis: {tooltip: true},
    render: (row) => row.error || '-'
  }
]

const dataSourcePanelRef = ref(null)
const saveDataSource = async (opts = {}) => {
  return await dataSourcePanelRef.value?.save?.({ silent: true, ...opts })
}
const getPendingDataSourceSceneNames = () => {
  return dataSourcePanelRef.value?.getPendingSceneNames?.() ?? null
}
defineExpose({ saveDataSource, getPendingDataSourceSceneNames })

</script>

<style scoped>
/* 卡片壳见 styles/autotest-theme.scss .step-editor-card */

/* 行间距统一由 n-form-item 自身的 margin-bottom 提供，与「步骤描述」等后续表单项保持一致 */
.http-request-rows {
  display: flex;
  flex-direction: column;
}

.http-request-row {
  width: 100%;
}

/* 第二行：步骤名称 40% / 所属应用 30% / 配置名称 30% */
.http-request-row-top {
  display: grid;
  grid-template-columns: 4fr 2.5fr 3.5fr;
  gap: 12px;
  align-items: start;
}

.http-request-row-top :deep(.n-form-item),
.http-request-row-bottom :deep(.n-form-item) {
  min-width: 0;
}

.http-field-step-name :deep(.n-input),
.http-field-project :deep(.n-select),
.http-field-config :deep(.n-select) {
  width: 100%;
}

.request-step-name-input {
  width: 100%;
}

.request-toolbar-select {
  width: 100%;
}

.request-toolbar-input-fill {
  width: 100%;
}

/* 第一行：请求方式约 20%，右侧为请求地址；调试按钮与输入框同一 form-item 内容区无缝并排（对齐 run_code 顶栏） */
.http-request-row-bottom {
  display: grid;
  grid-template-columns: minmax(0, 20%) minmax(0, 1fr);
  column-gap: 12px;
  align-items: start;
  width: 100%;
}

.http-url-debug-slot {
  min-width: 0;
}

.http-field-url :deep(.n-form-item-blank) {
  width: 100%;
}

.http-url-debug-inline {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
  width: 100%;
  min-width: 0;
}

.http-url-debug-inline .request-toolbar-input-fill {
  flex: 1;
  min-width: 0;
}

.http-debug-btn {
  flex-shrink: 0;
}

/* .panel-title 见 .step-editor-card */

.card-header-row {
  padding-right: 0;
}

.card-header-row--with-actions {
  padding-right: 220px; /* 预留右侧 status / tip 空间 */
}

.json-editor {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  border-radius: 10px;
  overflow: hidden;
  transition: height 0.3s ease;
}

/* 确保编辑器容器可以自适应内容高度 */
.json-editor :deep(.monaco-editor) {
  min-height: 90px;
  height: auto !important;
}


/* 添加必要的布局样式 */
.response-code {
  /* HTTP 调试响应体限高；滚动条样式见全局 .overlay-scroll */
  max-height: 400px;
  overflow: auto;
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}
</style>
