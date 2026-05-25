<template>
  <n-card :bordered="false" style="width: 100%;" :class="['http-card', { 'is-collapsed': requestCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">Request</div>
        <div class="card-header-actions">
          <n-button text size="tiny" @click="toggleRequestCardCollapsed" class="collapse-tiny-btn">
            <template #icon>
              <TheIcon
                  :icon="requestCardCollapsed ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                  :size="18"
              />
            </template>
            {{ requestCardCollapsed ? '展开' : '收起' }}
          </n-button>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!requestCardCollapsed">
      <n-form
          :model="state.form"
          :rules="rules"
          label-placement="left"
          label-width="80px"
          ref="formRef"
      >
        <!-- 前两列：步骤名称、所属应用；第三列：配置名称 + 调试同表单项内 flex 并排，避免末列与 n-select 垂直错位 -->
        <div class="tcp-request-row tcp-request-row-top">
          <n-form-item label="步骤名称" path="step_name" required class="tcp-field-step-name">
            <n-input
                v-model:value="state.form.step_name"
                placeholder="请输入步骤名称"
                clearable
                class="request-step-name-input"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="所属应用" path="request_project_id" required class="tcp-field-project">
            <n-select
                v-model:value="state.form.request_project_id"
                placeholder="所属应用"
                :options="props.projectOptions"
                :loading="props.projectLoading"
                clearable
                filterable
                class="request-toolbar-select"
                :disabled="props.readonly"
            />
          </n-form-item>
          <n-form-item label="配置名称" path="request_config_name" required class="tcp-field-config">
            <div class="tcp-config-debug-inline">
              <n-select
                  v-model:value="state.form.request_config_name"
                  placeholder="配置名称"
                  :options="tcpConfigNameOptions"
                  :loading="tcpConfigNameLoading"
                  clearable
                  filterable
                  tag
                  class="request-toolbar-select tcp-config-select-inline"
                  :disabled="props.readonly"
              />
              <n-button
                  v-if="!props.readonly"
                  type="primary"
                  size="medium"
                  class="tcp-debug-btn"
                  @click="debugging"
                  :loading="debugLoading"
              >
                调试
              </n-button>
            </div>
          </n-form-item>
        </div>

        <n-form-item label="步骤描述" path="step_desc">
          <n-input
              type="textarea"
              v-model:value="state.form.step_desc"
              placeholder="请输入步骤描述"
              clearable
              :disabled="props.readonly"
          />
        </n-form-item>
      </n-form>

      <n-tabs type="line" animated style="margin-top: 16px;">
        <n-tab-pane name="body" tab="请求">
          <div v-if="!props.readonly" class="tcp-body-toolbar">
            (排版规则：XML格式 -> JSON格式 -> 纯文本)
            <n-button size="small" type="primary" tertiary @click="beautifyRequestPayload">
              一键排版
            </n-button>
          </div>
          <monaco-editor
              v-model:value="state.form.request_payload"
              :lang="monacoBodyLang"
              :options="monacoEditorOptionsForBody()"
              class="json-editor"
              style="min-height: 400px; height: auto; margin-top: 8px;"
              :readOnly="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="extract_variables" tab="提取">
          <template #tab>
            <n-badge :value="extractCount" :max="99" show-zero>
              <span>提取</span>
            </n-badge>
          </template>
          <n-space vertical :size="12" class="extract-validator-list">
            <div v-for="(item, key) in state.form.extract_variables" :key="key" class="extract_variables-item">
              <n-card
                  size="small"
                  hoverable
                  :class="{ 'is-item-collapsed': extractCollapseState[key] }"
              >
                <template #header>
                  <div class="extract-validator-card-header">
                    <span>{{ item.name || '未命名提取' }} {{
                        getExtractObjectLabel(item.object)
                      }}{{
                        item.extractScope === '部分提取' && item.jsonpath ? `( ${item.jsonpath} )` : item.extractScope === '全部提取' ? '( 全部提取 )' : ''
                      }}</span>
                    <n-space>
                      <n-button text @click="toggleExtractCollapse(key)" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon
                              :icon="extractCollapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                              :size="18"/>
                        </template>
                      </n-button>
                      <n-button text @click="duplicateExtract(key)" type="info" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="18"/>
                        </template>
                      </n-button>
                      <n-button text @click="removeExtract(key)" type="error" size="small" :disabled="props.readonly">
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
                      <n-input v-model:value="item.name" placeholder="请输入提取名称" clearable :disabled="props.readonly"/>
                    </n-form-item>
                    <n-form-item label="提取对象">
                      <n-select
                          v-model:value="item.object"
                          :options="extractObjectOptions"
                          placeholder="请选择提取对象"
                          :disabled="props.readonly"
                      />
                    </n-form-item>
                    <n-form-item label="提取范围">
                      <n-space align="center" :wrap-item="false">
                        <n-radio-group v-model:value="item.extractScope" name="extractScope" :disabled="props.readonly">
                          <n-space>
                            <n-radio value="部分提取">部分提取</n-radio>
                            <n-radio value="全部提取">全部提取</n-radio>
                          </n-space>
                        </n-radio-group>
                        <n-tooltip trigger="hover">
                          <template #trigger>
                            <TheIcon icon="material-symbols:help-outline" :size="18" style="cursor: help; margin-left: 8px;"/>
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
                            :disabled="props.readonly"
                        />
                        <n-button text type="primary" @click="continueExtract(key)" :disabled="props.readonly">
                          继续提取
                          <template #icon>
                            <TheIcon icon="material-symbols:dataset-linked-outline" :size="18"/>
                          </template>
                        </n-button>
                        <n-switch v-model:value="item.continueExtract" size="small" :disabled="props.readonly"/>
                        <n-input-number v-model:value="item.extractIndex" :min="0" size="small" style="width: 80px;" :disabled="props.readonly"/>
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
            <n-button type="primary" @click="addExtract" block dashed :disabled="props.readonly">添加提取</n-button>
          </n-space>
        </n-tab-pane>
        <n-tab-pane name="assert_validators" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <n-space vertical :size="12" class="extract-validator-list">
            <div v-for="(item, key) in state.form.assert_validators" :key="key" class="validator-item">
              <n-card
                  size="small"
                  hoverable
                  :class="{ 'is-item-collapsed': validatorCollapseState[key] }"
              >
                <template #header>
                  <div class="extract-validator-card-header">
                    <span>{{ item.name || '未命名断言' }} {{ getExtractObjectLabel(item.object) }}( {{
                        item.jsonpath || ''
                      }} )</span>
                    <n-space>
                      <n-button text @click="toggleValidatorCollapse(key)" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon
                              :icon="validatorCollapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                              :size="18"/>
                        </template>
                      </n-button>
                      <n-button text @click="duplicateValidator(key)" type="info" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="18"/>
                        </template>
                      </n-button>
                      <n-button text @click="removeValidator(key)" type="error" size="small" :disabled="props.readonly">
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
                      <n-input v-model:value="item.name" placeholder="请输入断言名称" clearable :disabled="props.readonly"/>
                    </n-form-item>
                    <n-form-item label="断言对象">
                      <n-select
                          v-model:value="item.object"
                          :options="validatorObjectOptions"
                          placeholder="请选择断言对象"
                          :disabled="props.readonly"
                      />
                    </n-form-item>
                    <n-form-item label="断言表达式">
                      <n-space align="center" :wrap-item="false" style="width: 100%;">
                        <n-input
                            v-model:value="item.jsonpath"
                            :placeholder="getValidatorPlaceholder(item.object)"
                            clearable
                            style="flex: 1;"
                            :disabled="props.readonly"
                        />
                      </n-space>
                    </n-form-item>
                    <n-form-item label="断言操作符">
                      <n-select
                          v-model:value="item.assertion"
                          :options="assertionOptions"
                          placeholder="请选择断言方法"
                          :disabled="props.readonly"
                      />
                    </n-form-item>
                    <n-form-item label="断言预期值">
                      <n-input v-model:value="item.value" placeholder="请输入预期值" clearable :disabled="props.readonly"/>
                    </n-form-item>
                  </n-form>
                </div>
              </n-card>
            </div>
            <n-button type="primary" @click="addValidator" block dashed :disabled="props.readonly">添加断言</n-button>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <n-card v-if="response || debugLoading" :bordered="false" style="width: 100%; margin-top: 12px;">
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">Response</div>
        <div class="card-header-actions">
          <n-button text size="tiny" @click="toggleResponseCardCollapsed" class="collapse-tiny-btn">
            <template #icon>
              <TheIcon
                  :icon="responseCardCollapsed ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                  :size="18"
              />
            </template>
            {{ responseCardCollapsed ? '展开' : '收起' }}
          </n-button>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!responseCardCollapsed">
      <div v-if="debugLoading" style="padding: 12px;">调试中...</div>
      <div v-else-if="response" style="padding: 12px;">
        <div class="hint">耗时：{{ response.duration }}ms ｜ 大小：{{ response.size }}</div>
        <MonacoEditor
            v-if="response.data != null"
            :value="formatResponseData(response.data)"
            language="json"
            height="240px"
            :readonly="true"
        />
        <div v-if="Array.isArray(response.logs) && response.logs.length" class="hint" style="margin-top: 10px;">
          <div style="font-weight: 600; margin-bottom: 6px;">Logs</div>
          <pre style="white-space: pre-wrap; margin: 0;">{{ response.logs.join('\n') }}</pre>
        </div>
      </div>
    </n-collapse-transition>
  </n-card>

  <n-modal v-model:show="debugModalVisible" preset="dialog" title="选择调试环境" :show-icon="false">
    <div style="padding: 8px 0;">
      <div style="margin-bottom: 8px;">执行环境：</div>
      <n-select
          v-model:value="selectedDebugEnvId"
          :options="envOptions"
          :loading="envLoading"
          placeholder="请选择执行环境"
          filterable
          clearable
          style="width: 100%;"
      />
    </div>
    <template #action>
      <n-button @click="debugModalVisible = false">取消</n-button>
      <n-button type="primary" :disabled="selectedDebugEnvId == null || selectedDebugEnvId === ''" @click="confirmDebugModal">确定</n-button>
    </template>
  </n-modal>
</template>

<script setup>
defineOptions({ name: 'TCP请求控制器' })

import { computed, reactive, ref, watch } from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSwitch,
  NTabPane,
  NTabs,
  NTooltip,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import { assertionOperationSelectOptions } from '@/constants/autotestAssertionOperation'
import api from '@/api'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  step: { type: Object, default: () => ({}) },
  projectOptions: { type: Array, default: () => [] },
  projectLoading: { type: Boolean, default: false },
  availableVariableList: { type: Array, default: () => [] },
  assistFunctions: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['update:config'])

const formRef = ref(null)
const requestCardCollapsed = ref(false)
const toggleRequestCardCollapsed = () => {
  requestCardCollapsed.value = !requestCardCollapsed.value
}

const state = reactive({
  form: {
    step_name: '',
    step_desc: '',
    request_project_id: null,
    request_config_name: null,
    request_payload: '',
    extract_variables: {},
    assert_validators: {},
  }
})

const extractCollapseState = ref({})
const validatorCollapseState = ref({})

const extractObjectOptions = [
  { label: 'Response Json', value: 'Response Json' },
  { label: 'Response Text', value: 'Response Text' },
  { label: 'Response XML', value: 'Response XML' },
  { label: 'Response Header', value: 'Response Header' },
  { label: 'Response Cookie', value: 'Response Cookie' },
]

const validatorObjectOptions = [
  ...extractObjectOptions,
  { label: '变量池', value: '变量池' },
]

const assertionOptions = assertionOperationSelectOptions

const extractCount = computed(() => Object.keys(state.form.extract_variables || {}).length)
const validatorsCount = computed(() => Object.keys(state.form.assert_validators || {}).length)

const getExtractObjectLabel = (value) => {
  const option = extractObjectOptions.find((opt) => opt.value === value)
      || validatorObjectOptions.find((opt) => opt.value === value)
  return option ? option.label : value || ''
}

const getExtractPlaceholder = (object) => {
  const placeholderMap = {
    'Response Json': '请输入JSONPath表达式，如：$.data.name',
    'Response Text': '请输入正则表达式，如：^[A-Za-z0-9]+$',
    'Response XML': '请输入XPath表达式，如：/store/book[1]/title',
    'Response Header': '请输入 Header 名称，如：Content-Type',
    'Response Cookie': '请输入 Cookie 名称，如：Auth',
  }
  return placeholderMap[object] || '请输入表达式'
}

const getValidatorPlaceholder = (object) => {
  if (object === '变量池') return '请输入变量名称，如：name'
  return getExtractPlaceholder(object)
}

const getNextExtractKey = () => {
  const keys = Object.keys(state.form.extract_variables || {}).map((k) => parseInt(k, 10)).filter((k) => !isNaN(k))
  if (!keys.length) return '1'
  return String(Math.max(...keys) + 1)
}

const getNextValidatorKey = () => {
  const keys = Object.keys(state.form.assert_validators || {}).map((k) => parseInt(k, 10)).filter((k) => !isNaN(k))
  if (!keys.length) return '1'
  return String(Math.max(...keys) + 1)
}

const hydrateExtractValidatorsFromSource = (cfg, original) => {
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
      extractScope: item.scope === 'ALL' ? '全部提取' : '部分提取',
      jsonpath: item.expr || '',
      continueExtract: item.continueExtract || false,
      extractIndex: item.index !== undefined && item.index !== null ? Number(item.index) : 0,
    }
    extractCollapseState.value[key] = false
  })

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
    }
    validatorCollapseState.value[key] = false
  })
}

const buildExtractForBackend = () => {
  return Object.values(state.form.extract_variables || {})
      .map((item) => ({
        expr: item.jsonpath || '',
        name: item.name || '',
        scope: item.extractScope === '全部提取' ? 'ALL' : 'SOME',
        source: item.object || 'Response Json',
        index: item.extractIndex !== undefined && item.extractIndex !== null && item.extractIndex !== ''
            ? Number(item.extractIndex)
            : null,
      }))
      .filter((item) => String(item.name ?? '').trim() !== '' && String(item.expr ?? '').trim() !== '')
}

const buildValidatorsForBackend = () => {
  return Object.values(state.form.assert_validators || {})
      .map((item) => ({
        expr: item.jsonpath || '',
        name: item.name || '',
        source: item.object || 'Response Json',
        operation: item.assertion || '等于',
        except_value: item.value != null ? String(item.value) : '',
      }))
      .filter((item) => String(item.name ?? '').trim() !== '' && String(item.expr ?? '').trim() !== '')
}

const addExtract = () => {
  const key = getNextExtractKey()
  state.form.extract_variables[key] = {
    name: '',
    object: 'Response Json',
    extractScope: '部分提取',
    jsonpath: '',
    continueExtract: false,
    extractIndex: 0,
  }
  extractCollapseState.value[key] = false
}

const removeExtract = (key) => {
  delete state.form.extract_variables[key]
  delete extractCollapseState.value[key]
}

const duplicateExtract = (key) => {
  const item = state.form.extract_variables[key]
  if (!item) return
  const newKey = getNextExtractKey()
  state.form.extract_variables[newKey] = {
    ...JSON.parse(JSON.stringify(item)),
    name: item.name ? `${item.name}_副本` : '',
  }
  extractCollapseState.value[newKey] = extractCollapseState.value[key] ?? false
}

const toggleExtractCollapse = (key) => {
  extractCollapseState.value[key] = !extractCollapseState.value[key]
}

const continueExtract = () => {
  window.$message?.info?.('继续提取功能待实现')
}

const addValidator = () => {
  const key = getNextValidatorKey()
  state.form.assert_validators[key] = {
    name: '',
    object: 'Response Json',
    jsonpath: '',
    assertion: '等于',
    value: '',
  }
  validatorCollapseState.value[key] = false
}

const removeValidator = (key) => {
  delete state.form.assert_validators[key]
  delete validatorCollapseState.value[key]
}

const duplicateValidator = (key) => {
  const item = state.form.assert_validators[key]
  if (!item) return
  const newKey = getNextValidatorKey()
  state.form.assert_validators[newKey] = {
    ...JSON.parse(JSON.stringify(item)),
    name: item.name ? `${item.name}_副本` : '',
  }
  validatorCollapseState.value[newKey] = validatorCollapseState.value[key] ?? false
}

const toggleValidatorCollapse = (key) => {
  validatorCollapseState.value[key] = !validatorCollapseState.value[key]
}

const rules = {
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

/** Monaco 语言：xml | json | plaintext，与落库 body_format_mode 对应 */
const monacoBodyLang = ref('xml')

/** 将 Monaco languageId 转为步骤 config 中的 body_format_mode */
const monacoLangToBodyFormatMode = (lang) => {
  if (lang === 'plaintext') return 'text'
  if (lang === 'json' || lang === 'xml') return lang
  return 'text'
}

/** 校验是否为可解析的 XML（无 parsererror） */
const tryParseValidXml = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s || !s.includes('<')) return null
  const doc = new DOMParser().parseFromString(s, 'text/xml')
  const pe = doc.querySelector('parsererror')
  if (pe && String(pe.textContent || '').trim()) return null
  if (!doc.documentElement) return null
  return doc
}

/**
 * 简易 XML 排版：在已通过 DOMParser 校验后，在标签间断行并缩进（与常见 snippet 行为一致）
 */
const formatXmlPretty = (xml) => {
  let formatted = ''
  let pad = 0
  const normalized = String(xml).replace(/>\s*</g, '>\n<')
  normalized.split('\n').forEach((line) => {
    const node = line.trim()
    if (!node) return
    let indent = 0
    if (node.match(/.+<\/\w[^>]*>$/)) {
      indent = 0
    } else if (node.match(/^<\/\w/)) {
      if (pad > 0) pad -= 1
    } else if (node.match(/^<\w[^>]*[^/]>.*$/)) {
      indent = 1
    } else {
      indent = 0
    }
    formatted += `${'  '.repeat(pad)}${node}\n`
    pad += indent
  })
  return formatted.trimEnd()
}

const tryBeautifyJson = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  try {
    return JSON.stringify(JSON.parse(s), null, 2)
  } catch {
    return null
  }
}

/** 非 XML/JSON 时仅做轻量纯文本整理 */
const normalizePlainText = (raw) =>
    String(raw ?? '')
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trimEnd()

const beautifyRequestPayload = () => {
  if (props.readonly) return
  const raw = state.form.request_payload
  const doc = tryParseValidXml(raw)
  if (doc) {
    const ser = new XMLSerializer().serializeToString(doc.documentElement)
    state.form.request_payload = formatXmlPretty(ser)
    monacoBodyLang.value = 'xml'
    window.$message?.success?.('已按 XML 排版')
    return
  }
  const jsonStr = tryBeautifyJson(raw)
  if (jsonStr != null) {
    state.form.request_payload = jsonStr
    monacoBodyLang.value = 'json'
    window.$message?.success?.('已按 JSON 排版')
    return
  }
  state.form.request_payload = normalizePlainText(raw)
  monacoBodyLang.value = 'plaintext'
  window.$message?.info?.('未识别为 XML/JSON，已按纯文本整理')
}

/** 与 http_controller 请求体 JSON 编辑器 options 一致 */
const monacoEditorOptions = (readOnly) => {
  const options = {
    theme: 'vs-dark',
    language: 'json',
    fontSize: 14,
    tabSize: 4,
    automaticLayout: true,
    minimap: { enabled: true },
    lineNumbers: 'on',
    renderLineHighlight: 'line',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    folding: true,
    foldingStrategy: 'auto',
    roundedSelection: false,
    cursorStyle: 'line'
  }
  if (readOnly) options.readOnly = true
  return options
}

const monacoEditorOptionsForBody = () => ({ ...monacoEditorOptions(false) })

const buildConfigFromState = () => {
  const payloadText = String(state.form.request_payload ?? '')
  const cfg = {
    step_name: state.form.step_name,
    step_desc: state.form.step_desc,
    request_project_id: state.form.request_project_id,
    request_config_name: state.form.request_config_name != null && String(state.form.request_config_name).trim() !== ''
        ? String(state.form.request_config_name).trim()
        : null,
    /** 目标地址由「脚本执行配置」或后端按应用+环境解析，页面不再编辑 */
    request_url: '',
    request_port: null,
    body_format_mode: monacoLangToBodyFormatMode(monacoBodyLang.value),
    // TCP 步骤：始终按原始文本发送，不区分 JSON/XML 提交类型
    request_args_type: 'raw',
    request_text: payloadText,
    data: {},
    request_payload: payloadText,
    extract_variables: buildExtractForBackend(),
    assert_validators: buildValidatorsForBackend(),
  }
  return cfg
}

const initFromProps = () => {
  const cfg = props.config || {}
  const original = props.step?.original || {}
  state.form.step_name = cfg.step_name ?? original.step_name ?? props.step?.name ?? ''
  state.form.step_desc = cfg.step_desc ?? original.step_desc ?? ''
  state.form.request_project_id = cfg.request_project_id ?? original.request_project_id ?? null
  state.form.request_config_name = cfg.request_config_name ?? original.request_config_name ?? null
  const argsType = String(cfg.request_args_type ?? original.request_args_type ?? '').toLowerCase()
  if (argsType === 'json') {
    const bodyObj = cfg.data ?? original.request_body ?? {}
    state.form.request_payload = typeof cfg.request_payload === 'string'
        ? cfg.request_payload
        : JSON.stringify(bodyObj || {}, null, 2)
  } else {
    state.form.request_payload = cfg.request_payload ?? cfg.request_text ?? original.request_text ?? ''
  }

  const rawAfterLoad = String(state.form.request_payload || '')
  if (cfg.body_format_mode && ['xml', 'json', 'text'].includes(cfg.body_format_mode)) {
    monacoBodyLang.value = cfg.body_format_mode === 'text' ? 'plaintext' : cfg.body_format_mode
  } else if (cfg.body_editor_kind && ['json', 'xml', 'text'].includes(cfg.body_editor_kind)) {
    monacoBodyLang.value = cfg.body_editor_kind === 'text' ? 'plaintext' : cfg.body_editor_kind
  } else if (!rawAfterLoad.trim()) {
    monacoBodyLang.value = 'xml'
  } else if (argsType === 'json') {
    monacoBodyLang.value = 'json'
  } else if (/^\s*</.test(rawAfterLoad)) {
    monacoBodyLang.value = 'xml'
  } else {
    monacoBodyLang.value = 'plaintext'
  }

  hydrateExtractValidatorsFromSource(cfg, original)
}

watch(
    () => props.step?.id,
    () => initFromProps(),
    { immediate: true }
)

const tcpConfigNameOptions = ref([])
const tcpConfigNameLoading = ref(false)
const loadTcpConfigNames = async (projectId) => {
  const pid = projectId != null && projectId !== '' ? Number(projectId) : null
  if (!pid) {
    tcpConfigNameOptions.value = []
    return
  }
  tcpConfigNameLoading.value = true
  try {
    const res = await api.getEnvConfigNameList({ project_id: pid, config_type: 'api' })
    const list = Array.isArray(res?.data) ? res.data : []
    tcpConfigNameOptions.value = list.map((name) => ({ label: name, value: name }))
  } catch (e) {
    console.error('加载配置名称列表失败', e)
    tcpConfigNameOptions.value = []
  } finally {
    tcpConfigNameLoading.value = false
  }
}
watch(
    () => state.form.request_project_id,
    (pid, prev) => {
      void loadTcpConfigNames(pid)
      if (pid == null || pid === '') {
        state.form.request_config_name = null
      } else if (prev != null && Number(pid) !== Number(prev)) {
        state.form.request_config_name = null
      }
    },
    { immediate: true }
)

watch(
    () => state.form,
    () => {
      if (props.readonly) return
      emit('update:config', buildConfigFromState())
    },
    { deep: true }
)

/* =================== Debug（与 AutoTestTcpDebugRequest 一致，仅传 schema 所需字段） =================== */
const response = ref(null)
const debugLoading = ref(false)
const responseCardCollapsed = ref(false)
const toggleResponseCardCollapsed = () => { responseCardCollapsed.value = !responseCardCollapsed.value }

const formatResponseData = (data) => {
  try { return typeof data === 'string' ? data : JSON.stringify(data, null, 2) } catch { return String(data ?? '') }
}

const envOptions = ref([])
const envLoading = ref(false)
/** 调试所选环境枚举 ID（与 HTTP 控制器、后端 schema 的 env_id 一致） */
const selectedDebugEnvId = ref(null)
const debugModalVisible = ref(false)

const loadEnvNames = async () => {
  envLoading.value = true
  try {
    const res = await api.getEnvList()
    const list = res?.data ?? []
    envOptions.value = list.map((row) => ({
      label: row.env_name != null ? String(row.env_name) : String(row.env_id),
      value: row.env_id
    }))
    if (envOptions.value.length > 0 && selectedDebugEnvId.value == null) {
      selectedDebugEnvId.value = envOptions.value[0].value
    }
  } catch (e) {
    console.error('加载环境列表失败', e)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

const openDebugModal = () => {
  selectedDebugEnvId.value = null
  debugModalVisible.value = true
  loadEnvNames()
}

const confirmDebugModal = () => {
  debugModalVisible.value = false
  doDebugRequest(selectedDebugEnvId.value)
}

const debugging = async () => {
  try {
    await formRef.value?.validate?.()
  } catch (_) {
    window.$message?.warning?.('请填写必填字段')
    return
  }
  openDebugModal()
}

const doDebugRequest = async (env_id) => {
  debugLoading.value = true
  response.value = null
  try {
    const cfg = buildConfigFromState()
    const original = props.step?.original || {}

    const requestConfigName =
        cfg.request_config_name != null && String(cfg.request_config_name).trim() !== ''
            ? String(cfg.request_config_name).trim()
            : (original.request_config_name != null && String(original.request_config_name).trim() !== ''
                ? String(original.request_config_name).trim()
                : '')

    const bodyText = cfg.request_text ?? cfg.request_payload
    const requestText = bodyText != null && String(bodyText) !== '' ? String(bodyText) : undefined

    /** @type {Record<string, unknown>} */
    const debugPayload = {
      env_id: Number(env_id),
      step_name: state.form.step_name || original.step_name || 'TCP 调试',
      request_project_id: Number(cfg.request_project_id ?? original.request_project_id),
      request_config_name: requestConfigName
    }
    if (requestText !== undefined) {
      debugPayload.request_text = requestText
    }
    const ev = buildExtractForBackend()
    if (ev.length > 0) {
      debugPayload.extract_variables = ev
    }
    const av = buildValidatorsForBackend()
    if (av.length > 0) {
      debugPayload.assert_validators = av
    }

    const res = await api.tcpRequestDebugging(debugPayload)
    if (res.code === '000000') {
      response.value = res.data
      window.$message?.success?.('调试成功')
    } else {
      window.$message?.error?.(`调试失败：${res.message || '未知错误'}`)
    }
  } catch (e) {
    window.$message?.error?.(`调试失败：${e?.message || e}`)
  } finally {
    debugLoading.value = false
  }
}
</script>

<style scoped>
/* 与 HTTP 请求步骤「Request」卡片一致 */
.http-card {
  margin: 8px 0;
  border-radius: 12px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.5);
  border-left: 3px solid #F4511E;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.2px;
}

.card-header-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  min-height: 24px;
  padding-right: 220px;
}

.card-header-actions {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-tiny-btn :deep(.n-button__content) {
  font-size: 12px;
}

.http-card.is-collapsed :deep(.n-card__content) {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.hint {
  margin-top: 8px;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.tcp-request-row {
  width: 100%;
}

/* 三列：步骤名 / 应用 /（配置名+调试）；第三列内 flex 保证下拉与按钮同一基线 */
.tcp-request-row-top {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 2.5fr) minmax(0, 3.5fr);
  gap: 12px;
  align-items: start;
  width: 100%;
  box-sizing: border-box;
}

.tcp-request-row-top :deep(.n-form-item) {
  min-width: 0;
}

.tcp-config-debug-inline {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.tcp-config-select-inline {
  flex: 1 1 0;
  min-width: 0;
}

.tcp-debug-btn {
  flex: 0 0 auto;
  flex-shrink: 0;
  white-space: nowrap;
}

.tcp-field-step-name :deep(.n-input),
.tcp-field-project :deep(.n-select),
.tcp-field-config :deep(.n-select) {
  width: 100%;
}

.request-step-name-input {
  width: 100%;
}

.request-toolbar-select {
  width: 100%;
}

.tcp-body-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 0;
}

/* 与 http_controller「请求体」json 编辑器一致 */
.json-editor {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  border-radius: 10px;
  overflow: hidden;
  transition: height 0.3s ease;
}

.json-editor :deep(.monaco-editor) {
  min-height: 90px;
  height: auto !important;
}

.extract-validator-list {
  width: 100%;
}

.extract-validator-list :deep(.n-space-item) {
  width: 100%;
}

.extract-validator-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 28px;
  line-height: 1.5;
}

.extract_variables-item,
.validator-item {
  width: 100%;
}

.extract_variables-item :deep(.n-card),
.validator-item :deep(.n-card) {
  border: 1px solid var(--n-border-color);
  background-color: var(--n-color);
}

.extract_variables-item :deep(.n-card-header),
.validator-item :deep(.n-card-header) {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 10px 16px;
  box-sizing: border-box;
  background-color: var(--n-color-embedded);
  border-bottom: 1px solid var(--n-border-color);
}

.extract_variables-item :deep(.n-card-header__main),
.validator-item :deep(.n-card-header__main) {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
}

.extract_variables-item :deep(.n-card.is-item-collapsed .n-card-header),
.validator-item :deep(.n-card.is-item-collapsed .n-card-header) {
  border-bottom: none;
}

.extract_variables-item :deep(.n-card.is-item-collapsed .n-card__content),
.validator-item :deep(.n-card.is-item-collapsed .n-card__content) {
  display: none;
  padding: 0;
}
</style>

