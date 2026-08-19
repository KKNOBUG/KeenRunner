<template>
  <StepDataSourcePanel
      v-if="!props.hideDataSource"
      ref="dataSourcePanelRef"
      :step="props.step"
      :readonly="props.readonly"
      :step-name="state.form.step_name"
      step-type-label="TCP请求"
      :resize-trigger="props.layoutVersion"
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
          :model="state.form"
          :rules="rules"
          label-placement="left"
          class="step-editor-form"
          label-width="80px"
          size="small"
          ref="formRef"
      >
        <!-- 前两列：步骤名称、所属应用；第三列：配置名称 + 调试同表单项内 flex 并排，避免末列与 n-select 垂直错位 -->
        <div class="tcp-request-row tcp-request-row-top">
          <n-form-item label="步骤名称" path="step_name" required class="tcp-field-step-name">
            <n-input
                v-model:value="state.form.step_name"
                :placeholder="props.lockStepName ? '公共接口：与用例名称保持一致' : '请输入步骤名称'"
                :clearable="!props.lockStepName"
                class="request-step-name-input"
                :disabled="props.readonly || props.lockStepName"
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
                :disabled="props.readonly || props.lockProject"
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
                  size="small"
                  class="tcp-debug-btn"
                  @click="debugging"
                  :loading="debugLoading"
              >
                调试
              </n-button>
            </div>
          </n-form-item>
        </div>

        <!-- 步骤描述（公共接口：锁定为用例描述） -->
        <n-form-item label="步骤描述" path="step_desc">
          <n-input
              type="textarea"
              v-model:value="state.form.step_desc"
              :placeholder="props.lockStepDesc ? '公共接口：与用例描述保持一致' : '请输入步骤描述'"
              :clearable="!props.lockStepDesc"
              :autosize="{ minRows: 1 }"
              :disabled="props.readonly || props.lockStepDesc"
          />
        </n-form-item>
      </n-form>

      <n-tabs type="line" animated style="margin-top: 16px;">
        <n-tab-pane name="body" tab="请求体">
          <template #tab>
            <n-badge :value="getBodyCount" :max="99" show-zero>
              <span>请求体</span>
            </n-badge>
          </template>
          <n-radio-group v-model:value="state.form.bodyType" name="tcpBodyType" :disabled="props.readonly">
            <n-space>
              <n-radio value="xml">xml</n-radio>
              <n-radio value="json">json</n-radio>
              <n-radio value="raw">raw</n-radio>
            </n-space>
          </n-radio-group>

          <div v-if="state.form.bodyType === 'xml'">
            <monaco-editor
                v-model:value="state.form.xmlBody"
                lang="xml"
                :options="monacoEditorOptionsForBody()"
                class="json-editor"
                style="min-height: 400px; height: auto; margin-top: 12px;"
                :readOnly="props.readonly"
            />
          </div>

          <div v-if="state.form.bodyType === 'json'">
            <monaco-editor
                v-model:value="state.form.jsonBody"
                lang="json"
                :options="monacoEditorOptionsForBody()"
                class="json-editor"
                style="min-height: 400px; height: auto; margin-top: 12px;"
                :readOnly="props.readonly"
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

  <n-card
      v-if="response || debugLoading"
      :bordered="false"
      style="width: 100%; margin-top: 8px;"
      :class="['step-editor-card', { 'is-collapsed': responseCardCollapsed }]"
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
              <n-tag :type="durationTagType" round size="small">Time: {{ response.duration }}ms</n-tag>
              <n-tag :type="sizeTagType" round size="small">Size: {{ response.size }}</n-tag>
              <n-tag round size="small">Type: {{ contentType }}</n-tag>
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
            <n-collapse :default-expanded-names="['requestBasic', 'requestBody']">
              <n-collapse-item title="Basic" name="requestBasic">
                <n-space vertical :size="12">
                  <n-descriptions bordered :column="2" size="small">
                    <n-descriptions-item label="方法">
                      <n-tag type="info">TCP</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item label="目标地址">
                      <n-text copyable>{{ response.request_info?.url || '-' }}</n-text>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-space>
              </n-collapse-item>
              <n-collapse-item :title="`Body (${requestBodyType})`" name="requestBody">
                <monaco-editor
                    v-model:value="requestBodyDisplay"
                    :lang="requestBodyLanguage"
                    :options="monacoEditorOptionsForBody()"
                    :readOnly="true"
                    class="json-editor"
                    style="min-height: 400px; height: auto;"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
        </n-tab-pane>
        <!-- 响应信息 -->
        <n-tab-pane name="responseInfo" tab="响应信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['responseBody']" arrow-placement="right">
              <n-collapse-item :title="`Body (${contentType})`" name="responseBody">
                <monaco-editor
                    v-model:value="formattedResponse"
                    :lang="responseLanguage"
                    :options="monacoEditorOptionsForBody()"
                    :readOnly="true"
                    class="json-editor"
                    style="min-height: 400px; height: auto;"
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

import { computed, ref, watch, h } from 'vue'
import {
  NBadge,
  NButton,
  NCard,
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
  NModal,
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
import TheIcon from '@/components/icon/TheIcon.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import StepDataSourcePanel from '@/components/autotest/StepDataSourcePanel.vue'
import api from '@/api'
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

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  step: { type: Object, default: () => ({}) },
  projectOptions: { type: Array, default: () => [] },
  projectLoading: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
  hideDataSource: { type: Boolean, default: false },
  /** 公共接口用例：Request 面板「所属应用」锁定（只读），值为用例所属应用 */
  lockProject: { type: Boolean, default: false },
  caseProjectId: { type: [Number, String], default: null },
  /** 公共接口用例：Request 面板「步骤描述」锁定（只读），值为用例描述 */
  lockStepDesc: { type: Boolean, default: false },
  caseDesc: { type: String, default: null },
  /** 公共接口用例：Request 面板「步骤名称」锁定（只读），值为用例名称 */
  lockStepName: { type: Boolean, default: false },
  caseName: { type: String, default: null },
  /** 外部布局变化触发器，透传给数据源面板 */
  layoutVersion: { type: Number, default: 0 },
})
const emit = defineEmits(['update:config'])

const formRef = ref(null)
const requestCardCollapsed = ref(false)
const toggleRequestCardCollapsed = () => {
  requestCardCollapsed.value = !requestCardCollapsed.value
}

const extractCount = computed(() => countDictKeys(state.form.extract_variables))
const validatorsCount = computed(() => countDictKeys(state.form.assert_validators))

const getBodyCount = computed(() => {
  switch (state.form.bodyType) {
    case 'xml':
      return String(state.form.xmlBody || '').trim() ? 1 : 0
    case 'json':
      return String(state.form.jsonBody || '').trim() ? 1 : 0
    case 'raw':
      return String(state.form.rawBody || '').trim() ? 1 : 0
    default:
      return 0
  }
})

const jsonBodyError = computed(() => {
  // 无论当前在哪个模式，只要 JSON 数据非空就校验
  const str = (state.form.jsonBody ?? '').trim()
  if (!str) return ''
  try {
    JSON.parse(str)
    return ''
  } catch (e) {
    return `JSON 语法错误: ${e.message}`
  }
})

const xmlBodyError = computed(() => {
  // 无论当前在哪个模式，只要 XML 数据非空就校验
  const str = (state.form.xmlBody ?? '').trim()
  if (!str) return ''
  const doc = tryParseValidXml(str)
  if (!doc) return 'XML 语法错误: 解析失败'
  return ''
})

const buildExtractForBackend = () =>
    buildExtractListFromDict(state.form.extract_variables, EXTRACT_MODE_RESPONSE)

const buildValidatorsForBackend = () =>
    buildAssertListFromDict(state.form.assert_validators, ASSERT_MODE_RESPONSE)

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
 * 简易 XML 排版：在已通过 DOMParser 校验后，在标签间断行并缩进
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

/** 尝试格式化 XML；无效时返回 null */
const tryBeautifyXml = (raw) => {
  const doc = tryParseValidXml(raw)
  if (!doc) return null
  const ser = new XMLSerializer().serializeToString(doc.documentElement)
  return formatXmlPretty(ser)
}

/** 尝试格式化 JSON；无效时返回 null */
const tryBeautifyJson = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  try {
    return JSON.stringify(JSON.parse(s), null, 2)
  } catch {
    return null
  }
}

/** 自动格式化 xml（仅加载 / 切换到 xml 时调用一次；编辑过程不强制重排） */
const autoFormatXmlBody = () => {
  const raw = state.form.xmlBody
  if (!String(raw ?? '').trim()) return false
  const pretty = tryBeautifyXml(raw)
  if (pretty == null || pretty === String(raw)) return false
  state.form.xmlBody = pretty
  return true
}

/** 自动格式化 json（仅加载 / 切换到 json 时调用一次；编辑过程不强制重排） */
const autoFormatJsonBody = () => {
  const raw = state.form.jsonBody
  if (!String(raw ?? '').trim()) return false
  const pretty = tryBeautifyJson(raw)
  if (pretty == null || pretty === String(raw)) return false
  state.form.jsonBody = pretty
  return true
}

/**
 * 与 HTTP JSON 一致：依赖 Monaco formatOnPaste（粘贴时排版一次）。
 * XML 的 DocumentFormattingEditProvider 已在 monaco 组件内注册；用户手动改格式后不再强制重排。
 */
const monacoEditorOptions = (readOnly) => {
  const options = {
    theme: 'vs-dark',
    fontSize: 14,
    tabSize: 2,
    automaticLayout: true,
    minimap: { enabled: true },
    lineNumbers: 'on',
    renderLineHighlight: 'line',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    folding: true,
    foldingStrategy: 'auto',
    roundedSelection: false,
    cursorStyle: 'line',
    formatOnPaste: true,
  }
  if (readOnly) options.readOnly = true
  return options
}

const monacoEditorOptionsForBody = () => ({ ...monacoEditorOptions(!!props.readonly) })

const normalizeBodyType = (raw) => {
  const t = String(raw ?? '').toLowerCase()
  if (t === 'xml' || t === 'json' || t === 'raw') return t
  return 'xml'
}

const buildConfigFromState = () => {
  const bodyType = normalizeBodyType(state.form.bodyType)
  // 三种类型草稿始终带回 config（对齐 HTTP form_data / jsonBodyText），切换时互不覆盖
  const xmlBodyText = state.form.xmlBody ?? ''
  const jsonBodyText = state.form.jsonBody ?? ''
  const rawBodyText = state.form.rawBody ?? ''

  let request_text = null
  // JSON草稿为空时保持null：只有用户显式输入的JSON（含"{}"）才会落库
  let data = null

  // 始终解析 JSON（无论当前在哪个模式），用于落库到 request_body
  const jsonStr = jsonBodyText.trim()
  if (jsonStr) {
    try {
      data = JSON.parse(jsonStr)
    } catch {
      data = {}
    }
  }

  switch (bodyType) {
    case 'json':
      // JSON 模式下后端使用 request_body(data) 作为 payload，
      // request_text 保留 XML 文本用于落库（raw 已在切换时清空 XML 或被覆盖）
      request_text = xmlBodyText || null
      break
    case 'xml':
      // XML 模式下 request_text = XML 文本（payload），data = JSON dict（落库）
      request_text = xmlBodyText
      break
    case 'raw':
    default:
      // raw 模式下 request_text = raw 文本（payload），data = JSON dict（落库）
      // XML 已在切换 raw 模式时经用户确认后清空
      request_text = rawBodyText
      break
  }

  return {
    step_name: state.form.step_name,
    step_desc: state.form.step_desc,
    request_project_id: state.form.request_project_id,
    request_config_name: state.form.request_config_name != null && String(state.form.request_config_name).trim() !== ''
        ? String(state.form.request_config_name).trim()
        : null,
    /** 目标地址由「脚本执行配置」或后端按应用+环境解析，页面不再编辑 */
    request_url: '',
    request_port: null,
    request_args_type: bodyType,
    request_text,
    data,
    xmlBodyText,
    jsonBodyText,
    rawBodyText,
    data_source_id: state.form.data_source_id ?? null,
    data_source_name: state.form.data_source_name || '',
    data_source_desc: state.form.data_source_desc || '',
    extract_variables: buildExtractForBackend(),
    assert_validators: buildValidatorsForBackend(),
  }
}

/** 从 props 合并出表单值（config 优先、original 兜底）；纯函数，供 useStepEditorForm 灌入 */
const hydrateTcpForm = (p) => {
  const cfg = p.config || {}
  const original = p.step?.original || {}

  const argsType = normalizeBodyType(cfg.request_args_type ?? original.request_args_type ?? 'xml')
  const backendText = cfg.request_text ?? original.request_text ?? ''
  const legacyPayload = typeof cfg.request_payload === 'string' ? cfg.request_payload : ''

  // 三种类型各自恢复：
  // XML：草稿 > request_text（按 < 前缀判断）> argsType=xml时的 backendText
  // JSON：草稿 > request_body（解析后 stringify）> request_text（按 { 前缀，语法错误恢复场景）
  // raw：草稿 > argsType=raw时的 backendText
  const xmlRecoverable = backendText && backendText.trim().startsWith('<')
  const jsonRecoverable = backendText && backendText.trim().startsWith('{')

  const xmlBody = cfg.xmlBodyText != null
      ? String(cfg.xmlBodyText)
      : (xmlRecoverable ? backendText : (argsType === 'xml' ? (backendText || legacyPayload || '') : ''))

  let jsonBody
  if (cfg.jsonBodyText != null) {
    jsonBody = String(cfg.jsonBodyText)
  } else {
    // 无论当前在哪个模式，都从 request_body 恢复 JSON 数据
    const bodyObj = cfg.data ?? original.request_body ?? {}
    try {
      if (typeof bodyObj === 'string') {
        jsonBody = bodyObj
      } else if (Object.keys(bodyObj || {}).length) {
        jsonBody = JSON.stringify(bodyObj, null, 2)
      } else if (jsonRecoverable) {
        // request_body 为空（JSON 语法错误导致 data={}），从 request_text 恢复原始文本
        jsonBody = backendText
      } else {
        jsonBody = ''
      }
    } catch {
      jsonBody = ''
    }
  }

  const rawBody = cfg.rawBodyText != null
      ? String(cfg.rawBodyText)
      : (argsType === 'raw' ? (backendText || legacyPayload || '') : '')

  return {
    step_name: cfg.step_name ?? original.step_name ?? p.step?.name ?? '',
    step_desc: cfg.step_desc ?? original.step_desc ?? '',
    request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
    request_config_name: cfg.request_config_name ?? original.request_config_name ?? null,
    bodyType: argsType,
    xmlBody,
    jsonBody,
    rawBody,
    data_source_id: cfg.data_source_id ?? original.data_source_id ?? null,
    data_source_name: cfg.data_source_name ?? original.data_source_name ?? '',
    data_source_desc: cfg.data_source_desc ?? original.data_source_desc ?? '',
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

const { form, syncFromExternal } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({
    step_name: '',
    step_desc: '',
    request_project_id: null,
    request_config_name: null,
    bodyType: 'xml',
    xmlBody: '',
    jsonBody: '',
    rawBody: '',
    data_source_id: null,
    data_source_name: '',
    data_source_desc: '',
    extract_variables: {},
    assert_validators: {},
  }),
  hydrate: hydrateTcpForm,
  buildConfig: () => buildConfigFromState(),
  watchFields: (f) => [
    f.step_name, f.step_desc,
    f.request_project_id, f.request_config_name,
    f.bodyType, f.xmlBody, f.jsonBody, f.rawBody,
    f.data_source_id, f.data_source_name, f.data_source_desc,
    f.extract_variables, f.assert_validators
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
      if ((state.form.step_desc ?? '') !== desc) {
        syncFromExternal(() => {
          state.form.step_desc = desc
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

/** 步骤切换后按当前报文类型排版（表单灌入由 useStepEditorForm 完成） */
watch(
    () => props.step?.id,
    () => {
      if (state.form.bodyType === 'xml') autoFormatXmlBody()
      else if (state.form.bodyType === 'json') autoFormatJsonBody()
    },
    { immediate: true }
)

// 父级切换用例类型时会暂存/恢复 data_source 指针并直接改写 step.config；此处把外部对
// config.data_source_* 的改动同步进表单，保证当前编辑器与步骤树一致。相等性判断避免回写循环
// （即便触发一次防抖 emit，回写的也是与 config 相同的值，自然收敛）。
watch(
    () => [props.config?.data_source_id, props.config?.data_source_name, props.config?.data_source_desc],
    ([dsId, dsName, dsDesc]) => {
      if (state.form.data_source_id === dsId
          && state.form.data_source_name === dsName
          && state.form.data_source_desc === dsDesc) return
      state.form.data_source_id = dsId ?? null
      state.form.data_source_name = dsName ?? ''
      state.form.data_source_desc = dsDesc ?? ''
    },
)

/** 切换模式时排版 + raw 模式冲突处理 */
watch(
    () => state.form.bodyType,
    (type, prev) => {
      if (props.readonly) return
      if (prev == null || prev === type) return

      // 切换到 raw 模式时，若已有 XML 数据，弹窗确认是否清空
      if (type === 'raw' && prev !== 'raw') {
        const xmlStr = (state.form.xmlBody ?? '').trim()
        if (xmlStr) {
          if (window.confirm('切换到 raw 模式将清空已有 XML 数据，是否继续？')) {
            state.form.xmlBody = ''
          } else {
            state.form.bodyType = prev
            return
          }
        }
      }

      if (type === 'xml') autoFormatXmlBody()
      else if (type === 'json') autoFormatJsonBody()
    }
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
    const res = await api.getEnvConfigNameList({ project_id: pid, env_type: 'app' })
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

// 使用防抖，避免频繁触发；JSON/XML 语法错误不阻断 emit，由 steps/index.vue 统一校验拦截保存
let emitTimer = null
watch(
    () => [
      state.form.step_name, state.form.step_desc,
      state.form.request_project_id, state.form.request_config_name,
      state.form.bodyType, state.form.xmlBody, state.form.jsonBody, state.form.rawBody,
      state.form.data_source_id, state.form.data_source_name, state.form.data_source_desc,
      state.form.extract_variables, state.form.assert_validators
    ],
    () => {
      if (props.readonly) return
      if (emitTimer) clearTimeout(emitTimer)
      emitTimer = setTimeout(() => {
        emit('update:config', buildConfigFromState())
      }, 300)
    },
    {deep: true}
)

/* =================== Debug（与 AutoTestTcpDebugRequest 一致，仅传 schema 所需字段） =================== */
const response = ref(null)
const debugLoading = ref(false)
const responseCardCollapsed = ref(false)
const toggleResponseCardCollapsed = () => { responseCardCollapsed.value = !responseCardCollapsed.value }

// 响应类型
const contentType = computed(() => {
  const data = response.value?.data
  if (data === null || data === undefined) return 'text'
  if (typeof data === 'object') return 'application/json'
  if (typeof data === 'string') {
    const trimmed = data.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) return 'application/json'
    if (trimmed.startsWith('<') && trimmed.endsWith('>')) return 'application/xml'
  }
  return 'text/plain'
})

const isJsonResponse = computed(() => contentType.value.includes('json'))

const responseLanguage = computed(() => {
  const ct = contentType.value.toLowerCase()
  if (ct.includes('json')) return 'json'
  if (ct.includes('xml')) return 'xml'
  return 'text'
})

// 响应格式化
const formattedResponse = computed(() => {
  try {
    const data = response.value?.data
    if (data && typeof data === 'object') {
      return JSON.stringify(data, null, 2)
    }
    if (data && typeof data === 'string') {
      try {
        const parsed = JSON.parse(data)
        return JSON.stringify(parsed, null, 2)
      } catch {
        return data
      }
    }
    return String(data ?? '')
  } catch {
    return String(response.value?.data ?? '')
  }
})

// 耗时标签颜色
const durationTagType = computed(() => {
  const d = response.value?.duration
  if (d == null) return 'default'
  return d >= 5000 ? 'error' : d >= 1000 ? 'warning' : 'success'
})

// 大小标签颜色
const sizeTagType = computed(() => {
  const s = response.value?.size
  if (!s) return 'default'
  const match = s.match(/^([\d.]+)\s*(KB|MB|B)$/i)
  if (!match) return 'default'
  const val = parseFloat(match[1])
  const unit = match[2].toUpperCase()
  if (unit === 'MB' || (unit === 'KB' && val > 500)) return 'warning'
  return 'success'
})

// 请求体类型
const requestBodyType = computed(() => {
  const bt = response.value?.request_info?.body_type
  if (bt) return String(bt)
  return 'text'
})

const isJsonRequest = computed(() => {
  const bt = requestBodyType.value.toLowerCase()
  return bt === 'json' || bt === 'application/json'
})

const requestBodyLanguage = computed(() => {
  const bt = requestBodyType.value.toLowerCase()
  if (bt === 'json' || bt === 'application/json') return 'json'
  if (bt === 'xml' || bt === 'application/xml') return 'xml'
  return 'text'
})

// 请求体文本
const requestBodyText = computed(() => {
  const body = response.value?.request_info?.body
  if (body === null || body === undefined) return ''
  if (typeof body === 'object') return JSON.stringify(body, null, 2)
  return String(body)
})

// 请求体 JSON 格式化
const formattedRequestJson = computed(() => {
  try {
    const body = response.value?.request_info?.body
    if (body && typeof body === 'object') {
      return JSON.stringify(body, null, 2)
    }
    if (body && typeof body === 'string') {
      try {
        const parsed = JSON.parse(body)
        return JSON.stringify(parsed, null, 2)
      } catch {
        return body
      }
    }
    return String(body ?? '')
  } catch {
    return String(response.value?.request_info?.body ?? '')
  }
})

// 请求体展示：JSON 格式化为字符串，非 JSON 直接展示原文
const requestBodyDisplay = computed(() => {
  return isJsonRequest.value ? formattedRequestJson.value : requestBodyText.value
})

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
        'Response Json': 'Response Json',
        'Response Text': 'Response Text',
        'Response XML': 'Response XML',
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
        'Response Json': 'responseJson',
        'Response Text': 'responseText',
        'Response XML': 'responseXml',
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
      const value = typeof row.actual_value === 'object'
          ? JSON.stringify(row.actual_value)
          : String(row.actual_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '期望值',
    key: 'expect_value',
    width: 150,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.expect_value === null || row.expect_value === undefined) {
        return '-'
      }
      const value = typeof row.expect_value === 'object'
          ? JSON.stringify(row.expect_value)
          : String(row.expect_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '断言结果',
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
  // 语法校验：JSON 或 XML 有语法错误时阻止调试
  if (jsonBodyError.value) {
    window.$message?.error?.(jsonBodyError.value)
    return
  }
  if (xmlBodyError.value) {
    window.$message?.error?.(xmlBodyError.value)
    return
  }

  const extractCheck = validateExtractList(buildExtractForBackend())
  if (!extractCheck.valid) {
    window.$message?.error?.(extractCheck.message)
    return
  }
  const assertCheck = validateAssertList(buildValidatorsForBackend())
  if (!assertCheck.valid) {
    window.$message?.error?.(assertCheck.message)
    return
  }

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

    const bodyType = normalizeBodyType(cfg.request_args_type)

    /** @type {Record<string, unknown>} */
    const debugPayload = {
      env_id: Number(env_id),
      step_name: state.form.step_name || original.step_name || 'TCP 调试',
      request_project_id: Number(cfg.request_project_id ?? original.request_project_id),
      request_config_name: requestConfigName,
      request_args_type: bodyType,
    }
    if (bodyType === 'json') {
      debugPayload.request_body = cfg.data && typeof cfg.data === 'object' ? cfg.data : {}
    } else {
      const bodyText = cfg.request_text
      if (bodyText != null && String(bodyText) !== '') {
        debugPayload.request_text = String(bodyText)
      }
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
/* 卡片壳 / 标题 / 折叠见 .step-editor-card */

.card-header-row {
  padding-right: 0;
}

.card-header-row--with-actions {
  padding-right: 220px;
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}

.response-code {
  max-height: 400px;
  overflow: auto;
}

.log-item {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
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
</style>

