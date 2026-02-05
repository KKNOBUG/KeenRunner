<template>
  <n-card :bordered="false" style="width: 100%;" class="http-card">
    <n-form
        :rules="rules"
        :model="state.form"
        label-placement="left"
        label-width="80px"
        ref="formRef"
    >
      <!-- 请求方式、所属应用、请求地址 -->
      <n-form-item label="请求方式" path="method">
        <n-select
            v-model:value="state.form.method"
            placeholder="请选择请求方式"
            :options="methodOptions"
            :render-label="renderMethodLabel"
            style="width: 100px;"
        />
        <n-select
            v-model:value="state.form.request_project_id"
            placeholder="所属应用"
            :options="projectOptions"
            :loading="projectLoading"
            clearable
            filterable
            style="width: 160px;"
        />
        <n-input
            v-model:value="state.form.url"
            placeholder="请输入请求地址"
            clearable
            style="flex: 1;"
        />
        <n-button type="primary" @click="debugging" :loading="debugLoading">调试</n-button>
      </n-form-item>

      <!-- 步骤名称 -->
      <n-form-item label="步骤名称" path="step_name" required>
        <n-input
            v-model:value="state.form.step_name"
            placeholder="请输入步骤名称"
            clearable
            style="width: 100%;"
        />
      </n-form-item>

      <!-- 步骤描述 -->
      <n-form-item label="步骤描述" path="description">
        <n-input
            type="textarea"
            v-model:value="state.form.description"
            placeholder="请输入步骤描述"
            clearable
            style="width: 100%; min-height: 6rem;"
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
        />
      </n-tab-pane>
      <n-tab-pane name="params" tab="请求体">
        <template #tab>
          <n-badge :value="getBodyCount" :max="99" show-zero>
            <span>请求体</span>
          </n-badge>
        </template>
        <n-radio-group v-model:value="state.form.bodyType" name="bodyType">
          <n-space>
            <n-radio value="none">none</n-radio>
            <n-radio value="params">params</n-radio>
            <n-radio value="form-data">form-data</n-radio>
            <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
            <n-radio value="json">json</n-radio>
            <n-radio value="raw">raw</n-radio>
          </n-space>
        </n-radio-group>
        <div v-if="state.form.bodyType === 'params'">
          <KeyValueEditor
              v-model:items="state.form.bodyForm"
              :body-type="'none'"
              :is-for-body="true"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
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
          />
        </div>
        <div v-if="state.form.bodyType === 'x-www-form-urlencoded'">
          <KeyValueEditor
              v-model:items="state.form.bodyForm"
              :body-type="state.form.bodyType"
              :is-for-body="true"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
          />
        </div>
        <div v-if="state.form.bodyType === 'json'">
          <monaco-editor
              v-model:value="state.form.jsonBody"
              lang="json"
              :options="monacoEditorOptionsForBody()"
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
        />
      </n-tab-pane>
      <n-tab-pane name="extract_variables" tab="提取">
        <template #tab>
          <n-badge :value="extractCount" :max="99" show-zero>
            <span>提取</span>
          </n-badge>
        </template>
        <!-- 提取配置 -->
        <n-space vertical :size="16">
          <div v-for="(item, key) in state.form.extract_variables" :key="key" class="extract_variables-item">
            <n-card size="small" hoverable>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ item.name || '未命名提取' }} {{
                      getExtractObjectLabel(item.object)
                    }}{{
                      item.extractScope === '部分提取' && item.jsonpath ? `( ${item.jsonpath} )` : item.extractScope === '全部提取' ? '( 全部提取 )' : ''
                    }}</span>
                  <n-space>
                    <n-button text @click="toggleExtractCollapse(key)" size="small">
                      <template #icon>
                        <TheIcon
                            :icon="extractCollapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                            :size="18"/>
                      </template>
                    </n-button>
                    <n-button text @click="duplicateExtract(key)" type="info" size="small">
                      <template #icon>
                        <TheIcon icon="material-symbols:content-copy" :size="18"/>
                      </template>
                    </n-button>
                    <n-button text @click="removeExtract(key)" type="error" size="small">
                      <template #icon>
                        <TheIcon icon="material-symbols:delete-outline" :size="18"/>
                      </template>
                    </n-button>
                  </n-space>
                </div>
              </template>
              <div v-show="!extractCollapseState[key]">
                <n-form :model="item" label-width="auto" label-placement="left">
                  <n-form-item label="提取名称">
                    <n-input v-model:value="item.name" placeholder="请输入提取名称" clearable/>
                  </n-form-item>
                  <n-form-item label="提取对象">
                    <n-select
                        v-model:value="item.object"
                        :options="extractObjectOptions"
                        placeholder="请选择提取对象"
                    />
                  </n-form-item>
                  <n-form-item label="提取范围">
                    <n-space align="center" :wrap-item="false">
                      <n-radio-group v-model:value="item.extractScope" name="extractScope">
                        <n-space>
                          <n-radio value="部分提取">部分提取</n-radio>
                          <n-radio value="全部提取">全部提取</n-radio>
                        </n-space>
                      </n-radio-group>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <TheIcon icon="material-symbols:help-outline" :size="18"
                                   style="cursor: help; margin-left: 8px;"/>
                        </template>
                        选择提取范围：部分提取需要指定JSONPath/XPath等表达式，全部提取将提取整个响应内容
                      </n-tooltip>
                    </n-space>
                  </n-form-item>
                  <n-form-item v-if="item.extractScope === '部分提取'" label="提取路径">
                    <n-space align="center" :wrap-item="false" style="width: 100%;">
                      <n-input
                          v-model:value="item.jsonpath"
                          :placeholder="getExtractPlaceholder(item.object)"
                          clearable
                          style="flex: 1;"
                      />
                      <n-button text type="primary" @click="continueExtract(key)">
                        继续提取
                        <template #icon>
                          <TheIcon icon="material-symbols:dataset-linked-outline" :size="18"/>
                        </template>
                      </n-button>
                      <n-switch v-model:value="item.continueExtract" size="small"/>
                      <n-input-number v-model:value="item.extractIndex" :min="0" size="small" style="width: 80px;"/>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <TheIcon icon="material-symbols:help-outline" :size="18" style="cursor: help;"/>
                        </template>
                        0 表示第1项，1表示第2项，-1表示倒数第1项，-2表示倒数第2项，以此类推
                      </n-tooltip>
                    </n-space>
                  </n-form-item>
                </n-form>
              </div>
            </n-card>
          </div>
          <n-button type="primary" @click="addExtract" block dashed>添加提取</n-button>
        </n-space>
      </n-tab-pane>
      <n-tab-pane name="assert_validators" tab="断言">
        <template #tab>
          <n-badge :value="validatorsCount" :max="99" show-zero>
            <span>断言</span>
          </n-badge>
        </template>
        <!-- 断言配置 -->
        <n-space vertical :size="16">
          <div v-for="(item, key) in state.form.assert_validators" :key="key" class="validator-item">
            <n-card size="small" hoverable>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ item.name || '未命名断言' }} {{ getExtractObjectLabel(item.object) }}( {{
                      item.jsonpath || ''
                    }} )</span>
                  <n-space>
                    <n-button text @click="toggleValidatorCollapse(key)" size="small">
                      <template #icon>
                        <TheIcon
                            :icon="validatorCollapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                            :size="18"/>
                      </template>
                    </n-button>
                    <n-button text @click="duplicateValidator(key)" type="info" size="small">
                      <template #icon>
                        <TheIcon icon="material-symbols:content-copy" :size="18"/>
                      </template>
                    </n-button>
                    <n-button text @click="removeValidator(key)" type="error" size="small">
                      <template #icon>
                        <TheIcon icon="material-symbols:delete-outline" :size="18"/>
                      </template>
                    </n-button>
                  </n-space>
                </div>
              </template>
              <div v-show="!validatorCollapseState[key]">
                <n-form :model="item" label-width="auto" label-placement="left">
                  <n-form-item label="断言名称">
                    <n-input v-model:value="item.name" placeholder="请输入断言名称" clearable/>
                  </n-form-item>
                  <n-form-item label="断言对象">
                    <n-select
                        v-model:value="item.object"
                        :options="validatorObjectOptions"
                        placeholder="请选择断言对象"
                    />
                  </n-form-item>
                  <n-form-item label="断言表达式">
                    <n-space align="center" :wrap-item="false" style="width: 100%;">
                      <n-input
                          v-model:value="item.jsonpath"
                          :placeholder="getValidatorPlaceholder(item.object)"
                          clearable
                          style="flex: 1;"
                      />
                      <n-button text type="primary" @click="continueExtractValidator(key)">
                        继续提取
                        <template #icon>
                          <TheIcon icon="material-symbols:dataset-linked-outline" :size="18"/>
                        </template>
                      </n-button>
                      <n-switch v-model:value="item.continueExtract" size="small"/>
                      <n-input-number v-model:value="item.extractIndex" :min="0" size="small" style="width: 80px;"/>
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <TheIcon icon="material-symbols:help-outline" :size="18" style="cursor: help;"/>
                        </template>
                        0 表示第1项，1表示第2项，-1表示倒数第1项，-2表示倒数第2项，以此类推
                      </n-tooltip>
                    </n-space>
                  </n-form-item>
                  <n-form-item label="断言操作符">
                    <n-select
                        v-model:value="item.assertion"
                        :options="assertionOptions"
                        placeholder="请选择断言方法"
                    />
                  </n-form-item>
                  <n-form-item label="断言预期值">
                    <n-input v-model:value="item.value" placeholder="请输入预期值" clearable/>
                  </n-form-item>
                </n-form>
              </div>
            </n-card>
          </div>
          <n-button type="primary" @click="addValidator" block dashed>添加断言</n-button>
        </n-space>
      </n-tab-pane>
    </n-tabs>
  </n-card>

  <!-- 响应结果卡片：在加载中或有响应数据时展示 -->
  <n-card
      v-if="response || debugLoading"
      :bordered="false"
      style="width: 100%; margin-top: 16px;"
      class="http-card"
      ref="debugResultRef"
  >
    <!-- 在卡片标题右侧添加响应状态信息 -->
    <template #header-extra>
      <n-space v-if="response && !debugLoading" align="center">
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
    </template>
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
              <div v-else-if="isJsonRequest">
                <monaco-editor
                    v-model:value="formattedRequestJson"
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
                  class="response-code"
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
  </n-card>
</template>

<script setup>
import {computed, h, nextTick, reactive, ref, watch} from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCode,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTooltip
} from 'naive-ui'
import api from "@/api";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";
import MonacoEditor from "@/components/monaco/index.vue";
import TheIcon from "@/components/icon/TheIcon.vue";
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
  }
})

const emit = defineEmits(['update:config'])

const formRef = ref(null);
const route = useRoute()

// 请求方式下拉框
const methodOptions = [
  {label: 'GET', value: 'GET', color: '#49CC90'},
  {label: 'POST', value: 'POST', color: '#61AFFE'},
  {label: 'PUT', value: 'PUT', color: '#FFA500'},
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
  step_name: [
    {
      required: true,
      message: '请输入步骤名称',
      trigger: 'blur'
    }
  ]
}

/* 表单状态管理：从步骤配置初始化，不写死默认值 */
const state = reactive({
  form: {
    url: '',
    method: 'GET',
    headers: [],
    bodyType: 'none',
    params: [],
    bodyParams: [],
    bodyForm: [],
    jsonBody: '',
    rawBody: '',
    step_name: '',
    description: '',
    request_project_id: null, // 请求项目ID（与 request_args_type 等一致，从 form 读写；无 UI 时由 init 从 config/original 带入）
    defined_variables: [],
    extract_variables: {},
    assert_validators: {},
  }
})

// 提取/断言折叠状态
const extractCollapseState = ref({})
const validatorCollapseState = ref({})

// 注意：不再使用 kvObjectToList 和 kvListToObject，所有字段都必须是列表格式

const initFromConfig = () => {
  const cfg = props.config || {}
  const step = props.step || {}
  const original = step.original || {}

  console.log('========== HTTP 控制器 - 接收到的数据 ==========')
  console.log('1. props.config (配置数据，从 step.config 传递):', cfg)
  console.log('2. props.step (完整的步骤对象):', step)
  console.log('3. props.step.original (原始后端步骤数据):', original)
  console.log('4. props.step.original 的所有 key:', original ? Object.keys(original) : [])

  // 打印原始数据中的关键字段
  if (original) {
    console.log('5. 原始步骤数据中的关键字段:')
    console.log('   - step_code:', original.step_code)
    console.log('   - step_name:', original.step_name)
    console.log('   - step_desc:', original.step_desc)
    console.log('   - step_type:', original.step_type)
    console.log('   - id:', original.id)
    console.log('   - case_id:', original.case_id)
    console.log('   - request_method:', original.request_method)
    console.log('   - request_url:', original.request_url)
    console.log('   - extract_variables:', original.extract_variables)
    console.log('   - assert_validators:', original.assert_validators)
    console.log('   - defined_variables:', original.defined_variables)
  }
  console.log('==================================================')

  // 从原始数据中获取步骤名称和描述
  // 优先使用 config（含 emit 回写），再回退到 original，避免失焦时被旧 original 覆盖
  state.form.step_name = cfg.step_name !== undefined
      ? cfg.step_name
      : (step.name || original.step_name || '')
  state.form.description = cfg.step_desc !== undefined ? (cfg.step_desc ?? '') : (original.step_desc || '')

  state.form.method = cfg.method || original.request_method || 'GET'
  state.form.url = cfg.url || original.request_url || ''
  // headers、params 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
  state.form.headers = Array.isArray(cfg.headers) ? cfg.headers : (Array.isArray(original.request_header) ? original.request_header : [])
  state.form.params = Array.isArray(cfg.params) ? cfg.params : (Array.isArray(original.request_params) ? original.request_params : [])
  state.form.request_project_id = cfg.request_project_id ?? original.request_project_id ?? null

  // 请求体类型（与后端 request_args_type 枚举一致：none, params, form-data, x-www-form-urlencoded, json, raw）
  // 请求体类型：统一用 request_args_type（与后端枚举一致），form 内用 bodyType 仅作 UI 绑定
  const requestArgsType = cfg.request_args_type ?? original.request_args_type
  if (requestArgsType) {
    state.form.bodyType = requestArgsType
  } else if (cfg.data) {
    state.form.bodyType = 'json'
  } else if (cfg.form_data) {
    state.form.bodyType = 'form-data'
  } else if (cfg.form_urlencoded) {
    state.form.bodyType = 'x-www-form-urlencoded'
  } else if (cfg.request_text != null && cfg.request_text !== '') {
    state.form.bodyType = 'raw'
  } else {
    state.form.bodyType = 'none'
  }
  state.form.rawBody = cfg.request_text ?? original.request_text ?? ''

  // form_data、form_urlencoded 必须是列表格式，每个元素包含 key、value、desc、type（form-data 需 type 供 KeyValueEditor 显示「数据」列）
  const bodyParamsRaw = Array.isArray(cfg.form_data) ? cfg.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : [])
  state.form.bodyParams = bodyParamsRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))
  const bodyFormRaw = Array.isArray(cfg.form_urlencoded) ? cfg.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : [])
  state.form.bodyForm = bodyFormRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))

  // JSON 请求体：优先使用配置中的原始文本，避免格式错误时被清空
  const jsonBodyText = cfg.jsonBodyText
  if (jsonBodyText !== undefined && jsonBodyText !== null) {
    state.form.jsonBody = String(jsonBodyText)
  } else {
    try {
      const body = cfg.data ?? original.request_body
      if (body === null || body === undefined) {
        state.form.jsonBody = ''
      } else if (typeof body === 'string') {
        state.form.jsonBody = body
      } else {
        state.form.jsonBody = Object.keys(body).length ? JSON.stringify(body, null, 2) : ''
      }
    } catch {
      state.form.jsonBody = state.form.jsonBody ?? ''
    }
  }

  // defined_variables 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
  state.form.defined_variables = Array.isArray(cfg.defined_variables) ? cfg.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : [])

  // 提取：无默认内容，仅当 config/original 有数据时填充（与后端字段对齐：expr, name, source, range, index）
  state.form.extract_variables = {}
  extractCollapseState.value = {}
  const extractSource = cfg.extract_variables ?? original.extract_variables
  const extractList = !extractSource
      ? []
      : Array.isArray(extractSource)
          ? extractSource
          : (typeof extractSource === 'object' && Object.keys(extractSource).length > 0 ? [extractSource] : [])
  extractList.forEach((item, index) => {
    const key = String(index + 1)
    state.form.extract_variables[key] = {
      name: item.name || '',
      object: item.source || 'Response Json',
      extractScope: item.range === 'ALL' ? '全部提取' : '部分提取',
      jsonpath: item.expr || '',
      continueExtract: item.continueExtract || false,
      extractIndex: item.index !== undefined && item.index !== null ? Number(item.index) : null
    }
    extractCollapseState.value[key] = false
  })

  // 断言：无默认内容，仅当 config/original 有数据时填充（与后端字段对齐：expr, name, source, operation, except_value）
  state.form.assert_validators = {}
  validatorCollapseState.value = {}
  const validatorsSource = cfg.assert_validators ?? original.assert_validators
  const validatorsList = !validatorsSource
      ? []
      : Array.isArray(validatorsSource)
          ? validatorsSource
          : (typeof validatorsSource === 'object' && Object.keys(validatorsSource).length > 0 ? [validatorsSource] : [])
  validatorsList.forEach((item, index) => {
    const key = String(index + 1)
    state.form.assert_validators[key] = {
      name: item.name || '',
      object: item.source || 'Response Json',
      jsonpath: item.expr || '',
      assertion: item.operation || '等于',
      value: item.except_value != null ? String(item.except_value) : '',
      continueExtract: item.continueExtract || false,
      extractIndex: item.extractIndex ?? 0
    }
    validatorCollapseState.value[key] = false
  })
}

initFromConfig()

// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false

// 仅在切换步骤或步骤原始数据变化时重新初始化，不监听 props.config，避免用户编辑（如请求地址全选删除/剪切）后被 config 回写覆盖
watch(
    () => [props.step?.id, props.step?.original, props.step?.name],
    ([stepId, original, stepName]) => {
      isExternalUpdate = true
      initFromConfig()
      const cfg = props.config || {}
      const step = props.step || {}
      const orig = step.original || {}
      state.form.step_name = cfg.step_name !== undefined
          ? cfg.step_name
          : (stepName || orig.step_name || '')
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {deep: true, immediate: false}
)

// 与后端 autotest_step_engine 提取字段一致：expr, name, source, range, index；剔除提取名称或提取路径为空的项
const buildExtractForBackend = () => {
  return Object.values(state.form.extract_variables || {})
      .map(item => ({
        expr: item.jsonpath || '',
        name: item.name || '',
        range: item.extractScope === '全部提取' ? 'ALL' : 'SOME',
        source: item.object || 'Response Json',
        index: item.extractIndex !== undefined && item.extractIndex !== null && item.extractIndex !== '' ? Number(item.extractIndex) : null
      }))
      .filter(item => String(item.name ?? '').trim() !== '' && String(item.expr ?? '').trim() !== '')
}

// 与后端 autotest_step_engine 断言字段一致：expr, name, source, operation, except_value；剔除断言名称或断言表达式为空的项
const buildValidatorsForBackend = () => {
  return Object.values(state.form.assert_validators || {})
      .map(item => ({
        expr: item.jsonpath || '',
        name: item.name || '',
        source: item.object || 'Response Json',
        operation: item.assertion || '等于',
        except_value: item.value != null ? String(item.value) : ''
      }))
      .filter(item => String(item.name ?? '').trim() !== '' && String(item.expr ?? '').trim() !== '')
}

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

  let jsonBodyText = undefined
  switch (state.form.bodyType) {
    case 'json':
      try {
        data = state.form.jsonBody ? JSON.parse(state.form.jsonBody) : {}
      } catch {
        data = {}
      }
      jsonBodyText = state.form.jsonBody ?? ''
      break
    case 'raw':
      request_text = state.form.rawBody ?? ''
      break
    case 'none':
    default:
      break
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

// 使用防抖，避免频繁触发
let emitTimer = null
watch(
    () => [
      state.form.step_name, state.form.description, state.form.method,
      state.form.url, state.form.headers, state.form.params,
      state.form.bodyType, state.form.bodyParams, state.form.bodyForm,
      state.form.jsonBody, state.form.rawBody, state.form.request_project_id,
      state.form.defined_variables, state.form.extract_variables, state.form.assert_validators
    ],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      // 清除之前的定时器
      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      // 使用防抖，延迟发送更新
      emitTimer = setTimeout(() => {
        emit('update:config', buildConfigFromState())
      }, 300) // 300ms 防抖延迟
    },
    {deep: true}
)


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
    language: 'json',
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
    ...monacoEditorOptions(false),
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
    POST: 'info',
    PUT: 'warning',
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
    'raw': 'Raw'
  }
  return typeMap[requestInfo.value.bodyType] || 'Params'
})

const isJsonRequest = computed(() => requestInfo.value.bodyType === 'json')
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

/* 调试方法 */
const debugging = async () => {
  const userStore = useUserStore(); // 获取用户状态管理 store
  const currentUser = userStore.username; // 获取当前登录用户信息
  const valid = await formRef.value.validate();
  if (!valid) {
    $message.warning("请填写必填字段");
    return;
  }

  // 设置加载状态
  debugLoading.value = true
  response.value = null // 清空之前的响应数据

  try {
    const cfg = buildConfigFromState()

    // 将列表格式转换为字典格式用于显示（仅用于requestInfo）
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
      rawBody: state.form.rawBody ?? '',
      formData: state.form.bodyType === 'form-data' ? state.form.bodyParams : null,
      formUrlencoded: (state.form.bodyType === 'params' || state.form.bodyType === 'x-www-form-urlencoded') ? state.form.bodyForm : null
    }

    const caseId = route.query.case_id ? Number(route.query.case_id) : null

    // 获取步骤的原始数据
    const original = props.step?.original || {}

    const debugPayload = {
      case_id: caseId,
      step_type: original.step_type || 'HTTP/HTTPS协议网络请求',
      step_name: state.form.step_name || original.step_name || 'HTTP 调试',
      request_url: cfg.url,
      request_method: cfg.method,
      request_args_type: cfg.request_args_type ?? original.request_args_type ?? 'none',
      request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
      request_params: Array.isArray(cfg.params) && cfg.params.length > 0 ? cfg.params : null,
      request_body: cfg.data,
      request_form_data: Array.isArray(cfg.form_data) && cfg.form_data.length > 0 ? cfg.form_data : null,
      request_form_urlencoded: Array.isArray(cfg.form_urlencoded) && cfg.form_urlencoded.length > 0 ? cfg.form_urlencoded : null,
      request_text: cfg.request_text ?? null,
      request_header: Array.isArray(cfg.headers) && cfg.headers.length > 0 ? cfg.headers : null,
      defined_variables: Array.isArray(cfg.defined_variables) && cfg.defined_variables.length > 0 ? cfg.defined_variables : null,
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
          formUrlencoded: (reqInfo.body_type === 'params' || reqInfo.body_type === 'x-www-form-urlencoded') ? reqInfo.body : null,
          rawBody: reqInfo.body_type === 'raw' && reqInfo.request_text != null ? reqInfo.request_text : (requestInfo.value.rawBody ?? '')
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

/* ======================================= */
/* =============== Extract =============== */
/*  ====================================== */
// 提取对象选项
const extractObjectOptions = [
  {label: 'Response Json', value: 'Response Json'},
  {label: 'Response Text', value: 'Response Text'},
  {label: 'Response XML', value: 'Response XML'},
  {label: 'Response Header', value: 'Response Header'},
  {label: 'Response Cookie', value: 'Response Cookie'}
]

// 断言对象选项（包含变量池）
const validatorObjectOptions = [
  {label: 'Response Json', value: 'Response Json'},
  {label: 'Response Text', value: 'Response Text'},
  {label: 'Response XML', value: 'Response XML'},
  {label: 'Response Header', value: 'Response Header'},
  {label: 'Response Cookie', value: 'Response Cookie'},
  {label: '变量池', value: '变量池'}
]

// 断言方法选项（必须与后端 AutoTestToolService.compare_assertion 中的 op_map 一致）
const assertionOptions = [
  {label: '等于', value: '等于'},
  {label: '不等于', value: '不等于'},
  {label: '大于', value: '大于'},
  {label: '大于等于', value: '大于等于'},
  {label: '小于', value: '小于'},
  {label: '小于等于', value: '小于等于'},
  {label: '长度等于', value: '长度等于'},
  {label: '包含', value: '包含'},
  {label: '不包含', value: '不包含'},
  {label: '以...开始', value: '以...开始'},
  {label: '以...结束', value: '以...结束'},
  {label: '非空', value: '非空'},
  {label: '为空', value: '为空'}
]

// 提取数量计算
const extractCount = computed(() => {
  return Object.keys(state.form.extract_variables).length
})

// 断言数量计算
const validatorsCount = computed(() => {
  return Object.keys(state.form.assert_validators).length
})

// 获取提取对象标签
const getExtractObjectLabel = (value) => {
  const option = extractObjectOptions.find(opt => opt.value === value) || validatorObjectOptions.find(opt => opt.value === value)
  return option ? option.label : value || ''
}

// 获取提取功能的placeholder
const getExtractPlaceholder = (object) => {
  const placeholderMap = {
    'Response Json': '请输入JSONPath表达式，如：$.data.name',
    'Response Text': '请输入正则表达式，如：^[A-Za-z0-9]+$',
    'Response XML': '请输入XPath表达式，如：/store/book[1]/title',
    'Response Header': '请输入 Header 名称，如：Content-Type',
    'Response Cookie': '请输入 Cookie 名称，如：Auth'
  }
  return placeholderMap[object] || '请输入表达式'
}

// 获取断言功能的placeholder
const getValidatorPlaceholder = (object) => {
  const placeholderMap = {
    'Response Json': '请输入JSONPath表达式，如：$.data.name',
    'Response Text': '请输入正则表达式，如：^[A-Za-z0-9]+$',
    'Response XML': '请输入XPath表达式，如：/store/book[1]/title',
    'Response Header': '请输入 Header 名称，如：Content-Type',
    'Response Cookie': '请输入 Cookie 名称，如：Auth',
    '变量池': '请输入变量名称，如：name'
  }
  return placeholderMap[object] || '请输入表达式'
}

// 生成下一个提取序号
const getNextExtractKey = () => {
  const keys = Object.keys(state.form.extract_variables).map(k => parseInt(k)).filter(k => !isNaN(k))
  if (keys.length === 0) return '1'
  return String(Math.max(...keys) + 1)
}

// 生成下一个断言序号
const getNextValidatorKey = () => {
  const keys = Object.keys(state.form.assert_validators).map(k => parseInt(k)).filter(k => !isNaN(k))
  if (keys.length === 0) return '1'
  return String(Math.max(...keys) + 1)
}

// 添加提取
const addExtract = () => {
  const key = getNextExtractKey()
  state.form.extract_variables[key] = {
    name: '',
    object: 'Response Json',
    extractScope: '部分提取', // 默认选择部分提取
    jsonpath: '',
    continueExtract: false,
    extractIndex: 0
  }
  extractCollapseState.value[key] = false
}

// 删除提取
const removeExtract = (key) => {
  delete state.form.extract_variables[key]
  delete extractCollapseState.value[key]
}

// 复制提取
const duplicateExtract = (key) => {
  const item = state.form.extract_variables[key]
  if (item) {
    const newKey = getNextExtractKey()
    state.form.extract_variables[newKey] = {
      ...JSON.parse(JSON.stringify(item)),
      name: item.name ? `${item.name}_副本` : ''
    }
    extractCollapseState.value[newKey] = extractCollapseState.value[key] ?? false
  }
}

const toggleExtractCollapse = (key) => {
  extractCollapseState.value[key] = !extractCollapseState.value[key]
}

// 继续提取（提取功能）
const continueExtract = (key) => {
  // TODO: 实现继续提取逻辑
  $message.info('继续提取功能待实现')
}

// 添加断言
const addValidator = () => {
  const key = getNextValidatorKey()
  state.form.assert_validators[key] = {
    name: '',
    object: 'Response Json',
    jsonpath: '',
    assertion: '等于',
    value: '',
    continueExtract: false,
    extractIndex: 0
  }
  validatorCollapseState.value[key] = false
}

// 删除断言
const removeValidator = (key) => {
  delete state.form.assert_validators[key]
  delete validatorCollapseState.value[key]
}

// 复制断言
const duplicateValidator = (key) => {
  const item = state.form.assert_validators[key]
  if (item) {
    const newKey = getNextValidatorKey()
    state.form.assert_validators[newKey] = {
      ...JSON.parse(JSON.stringify(item)),
      name: item.name ? `${item.name}_副本` : ''
    }
    validatorCollapseState.value[newKey] = validatorCollapseState.value[key] ?? false
  }
}

const toggleValidatorCollapse = (key) => {
  validatorCollapseState.value[key] = !validatorCollapseState.value[key]
}

// 继续提取（断言功能）
const continueExtractValidator = (key) => {
  // TODO: 实现继续提取逻辑
  $message.info('继续提取功能待实现')
}

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
        'Response Json': 'Response Json',
        'Response Text': 'Response Text',
        'Response XML': 'Response XML',
        'Response Header': 'Response Header',
        'Response Cookie': 'Response Cookie'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '提取范围',
    key: 'range',
    width: 120,
    render: (row) => {
      return row.range === 'ALL' ? '全部提取' : '部分提取'
    }
  },
  {
    title: '提取路径',
    key: 'expr',
    width: 120,
    ellipsis: {tooltip: true}
  },
  {
    title: '提取值',
    key: 'extracted_value',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.extracted_value === null || row.extracted_value === undefined) {
        return '-'
      }
      const value = typeof row.extracted_value === 'object'
          ? JSON.stringify(row.extracted_value)
          : String(row.extracted_value)
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
        'Response Json': 'responseJson',
        'Response Text': 'responseText',
        'Response XML': 'responseXml',
        'Response Header': 'responseHeader',
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

</script>

<style scoped>
.http-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}

.key-value-editor .key-value-row {
  display: grid;
  grid-template-columns: 1fr 1fr 100px;
  gap: 12px;
  margin-bottom: 12px;
}

.key-value-view .view-row {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.key-value-view .key {
  min-width: 200px;
  color: #1f2937;
}

.key-value-view .value {
  color: #4b5563;
  word-break: break-all;
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
  max-height: 400px; /* 限制代码块高度 */
  overflow: auto; /* 添加滚动条 */
}

:root {
  --pre-bg-color: #f4f4f4;
  --pre-text-color: #333;
}

@media (prefers-color-scheme: dark) {
  :root {
    --pre-bg-color: #222;
    --pre-text-color: #eee;
  }
}

pre {
  background-color: var(--pre-bg-color);
  color: var(--pre-text-color);
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

.extract_variables-item,
.validator-item {
  margin-bottom: 1px;
}

.extract_variables-item :deep(.n-card),
.validator-item :deep(.n-card) {
  border: 1px solid #e0e0e0;
}

.extract_variables-item :deep(.n-card-header),
.validator-item :deep(.n-card-header) {
  padding: 12px 16px;
  background-color: #fafafa;
  border-bottom: 1px solid #e0e0e0;
}

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

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}
</style>
