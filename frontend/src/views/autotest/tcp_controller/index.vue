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
        <!-- 第一行：请求地址60%/请求端口与调试同栏无缝；第二行：步骤名称、所属应用、配置名称 -->
        <div class="tcp-request-rows">
          <div class="tcp-request-row tcp-request-row-bottom">
            <n-form-item label="请求地址" path="host" required class="tcp-field-host">
              <n-input
                  v-model:value="state.form.host"
                  placeholder="请输入请求地址"
                  clearable
                  class="request-toolbar-input-fill"
                  :disabled="props.readonly"
              />
            </n-form-item>
            <div class="tcp-port-debug-slot">
              <n-form-item
                  v-if="!props.readonly"
                  label="请求端口"
                  path="port"
                  required
                  class="tcp-field-port"
              >
                <div class="tcp-port-debug-inline">
                  <n-input
                      v-model:value="state.form.port"
                      placeholder="端口"
                      clearable
                      class="request-toolbar-input-fill"
                      :disabled="props.readonly"
                  />
                  <n-button
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
              <n-form-item
                  v-else
                  label="请求端口"
                  path="port"
                  required
                  class="tcp-field-port"
              >
                <n-input
                    v-model:value="state.form.port"
                    placeholder="端口"
                    clearable
                    class="request-toolbar-input-fill"
                    :disabled="props.readonly"
                />
              </n-form-item>
            </div>
          </div>
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
              <n-select
                  v-model:value="state.form.request_config_name"
                  placeholder="配置名称"
                  :options="tcpConfigNameOptions"
                  :loading="tcpConfigNameLoading"
                  clearable
                  filterable
                  tag
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
          </div>
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
        <n-tab-pane name="body" tab="请求体">
          <!-- 与 HTTP「请求体」json 区布局一致；编辑模式仅影响 Monaco 语法高亮，不做自动排版美化 -->
          <div class="tcp-body-mode-row">
            <span class="tcp-body-mode-label">编辑模式</span>
            <n-radio-group
                v-model:value="state.form.body_format_mode"
                name="tcpBodyFormat"
                :disabled="props.readonly"
            >
              <n-space>
                <n-radio value="xml">XML</n-radio>
                <n-radio value="json">JSON</n-radio>
                <n-radio value="text">文本</n-radio>
              </n-space>
            </n-radio-group>
          </div>
          <monaco-editor
              v-model:value="state.form.request_payload"
              :lang="monacoBodyLang"
              :options="monacoEditorOptionsForBody()"
              class="json-editor"
              style="min-height: 400px; height: auto; margin-top: 12px;"
              :readOnly="props.readonly"
          />
          <div class="hint" style="margin-top: 8px;">
            编辑模式仅切换语法高亮。TCP 保存与调试按原始字符串发送（raw），暂不实现 JSON/XML 一键排版。
          </div>
        </n-tab-pane>
        <n-tab-pane name="extract" tab="变量提取">
          <KeyValueEditor
              v-model:items="state.form.extract_variables"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
              placeholder-key="name"
              placeholder-value="expr"
          />
          <div class="hint">
            source 建议使用：<code>response json</code> / <code>response xml</code> / <code>response text</code> / <code>session_variables</code>。
          </div>
        </n-tab-pane>
        <n-tab-pane name="assert" tab="断言验证">
          <KeyValueEditor
              v-model:items="state.form.assert_validators"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
              placeholder-key="name"
              placeholder-value="expr"
          />
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

  <n-modal v-model:show="debugModalVisible" preset="dialog" title="选择环境" :show-icon="false">
    <div style="padding: 8px 0;">
      <n-select
          v-model:value="selectedEnvName"
          :options="envOptions"
          :loading="envLoading"
          placeholder="请选择环境"
          filterable
          clearable
      />
    </div>
    <template #action>
      <n-button @click="debugModalVisible = false">取消</n-button>
      <n-button type="primary" :disabled="!selectedEnvName" @click="confirmDebugModal">确定</n-button>
    </template>
  </n-modal>
</template>

<script setup>
defineOptions({ name: 'TCP请求控制器' })

import { computed, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NTabPane,
  NTabs
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import api from '@/api'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store'

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
    host: '',
    port: '',
    request_payload: '',
    /** xml | json | text：Monaco 语法高亮，默认 XML */
    body_format_mode: 'xml',
    extract_variables: [],
    assert_validators: []
  }
})

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
  host: [
    {
      validator(_rule, value) {
        if (!String(value ?? '').trim()) {
          return new Error('请输入请求地址')
        }
        return true
      },
      trigger: ['change', 'blur']
    }
  ],
  port: [
    {
      validator(_rule, value) {
        if (!String(value ?? '').trim()) {
          return new Error('请输入请求端口')
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

const monacoBodyLang = computed(() => {
  const k = state.form.body_format_mode
  if (k === 'xml') return 'xml'
  if (k === 'text') return 'plaintext'
  return 'json'
})

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
    host: (state.form.host || '').trim(),
    port: String(state.form.port ?? '').trim(),
    body_format_mode: state.form.body_format_mode || 'xml',
    // TCP 步骤：始终按原始文本发送，不区分 JSON/XML 提交类型
    request_args_type: 'raw',
    request_text: payloadText,
    data: {},
    request_payload: payloadText,
    extract_variables: Array.isArray(state.form.extract_variables) ? state.form.extract_variables : [],
    assert_validators: Array.isArray(state.form.assert_validators) ? state.form.assert_validators : [],
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
  if (cfg.host !== undefined || cfg.port !== undefined) {
    state.form.host = cfg.host ?? ''
    state.form.port = cfg.port != null && cfg.port !== '' ? String(cfg.port) : ''
  } else if (cfg.target) {
    const t = String(cfg.target).trim()
    const m = t.match(/^(.+):(\d{1,5})$/)
    if (m) {
      state.form.host = m[1].trim()
      state.form.port = m[2]
    } else {
      state.form.host = t
      state.form.port = ''
    }
  } else {
    state.form.host = original.request_url ?? ''
    state.form.port = original.request_port != null && original.request_port !== ''
        ? String(original.request_port)
        : ''
  }
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
    state.form.body_format_mode = cfg.body_format_mode
  } else if (cfg.body_editor_kind && ['json', 'xml', 'text'].includes(cfg.body_editor_kind)) {
    state.form.body_format_mode = cfg.body_editor_kind
  } else if (!rawAfterLoad.trim()) {
    state.form.body_format_mode = 'xml'
  } else if (argsType === 'json') {
    state.form.body_format_mode = 'json'
  } else if (/^\s*</.test(rawAfterLoad)) {
    state.form.body_format_mode = 'xml'
  } else {
    state.form.body_format_mode = 'text'
  }

  state.form.extract_variables = cfg.extract_variables ?? original.extract_variables ?? []
  state.form.assert_validators = cfg.assert_validators ?? original.assert_validators ?? []
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

/* =================== Debug（参考 HTTP 控制器） =================== */
const route = useRoute()
const response = ref(null)
const debugLoading = ref(false)
const responseCardCollapsed = ref(false)
const toggleResponseCardCollapsed = () => { responseCardCollapsed.value = !responseCardCollapsed.value }

const formatResponseData = (data) => {
  try { return typeof data === 'string' ? data : JSON.stringify(data, null, 2) } catch { return String(data ?? '') }
}

const envOptions = ref([])
const envLoading = ref(false)
const selectedEnvName = ref(null)
const debugModalVisible = ref(false)

const loadEnvNames = async () => {
  envLoading.value = true
  try {
    const res = await api.getApiEnvNames()
    const list = res?.data ?? []
    envOptions.value = list.map((name) => ({ label: name, value: name }))
    if (envOptions.value.length > 0 && !selectedEnvName.value) {
      selectedEnvName.value = envOptions.value[0].value
    }
  } catch (e) {
    console.error('加载环境名称失败', e)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

const openDebugModal = () => {
  selectedEnvName.value = null
  debugModalVisible.value = true
  loadEnvNames()
}

const confirmDebugModal = () => {
  debugModalVisible.value = false
  doDebugRequest(selectedEnvName.value ?? '')
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

const doDebugRequest = async (env_name) => {
  const userStore = useUserStore()
  const currentUser = userStore.username
  debugLoading.value = true
  response.value = null
  try {
    const cfg = buildConfigFromState()
    const original = props.step?.original || {}
    const caseId = route.query.case_id ? Number(route.query.case_id) : null

    const debugPayload = {
      env_name: env_name || '',
      case_id: caseId,
      step_type: original.step_type || 'TCP请求',
      step_name: state.form.step_name || original.step_name || 'TCP 调试',
      request_url: (state.form.host || '').trim(),
      request_port: String(state.form.port || '').trim()
          ? Number(String(state.form.port).trim())
          : null,
      request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
      request_args_type: 'raw',
      request_text: cfg.request_text ?? cfg.request_payload ?? null,
      request_body: {},
      defined_variables: Array.isArray(cfg.defined_variables) && cfg.defined_variables.length > 0 ? cfg.defined_variables : null,
      session_variables: Array.isArray(cfg.session_variables) && cfg.session_variables.length > 0 ? cfg.session_variables : null,
      extract_variables: cfg.extract_variables ?? null,
      assert_validators: cfg.assert_validators ?? null,
      created_user: currentUser,
      updated_user: currentUser
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
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
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

.tcp-request-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tcp-request-row {
  width: 100%;
}

/* 第二行：40% / 30% / 30%（与 HTTP 一致用 4fr 3fr 3fr） */
.tcp-request-row-top {
  display: grid;
  grid-template-columns: 4fr 2.5fr 3.5fr;
  gap: 12px;
  align-items: start;
}

.tcp-request-row-top :deep(.n-form-item),
.tcp-request-row-bottom :deep(.n-form-item) {
  min-width: 0;
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

.request-toolbar-input-fill {
  width: 100%;
}

/* 第一行：请求地址约 60%，右侧请求端口与调试同一 form-item 内容区无缝并排 */
.tcp-request-row-bottom {
  display: grid;
  grid-template-columns: minmax(0, 60%) minmax(0, 1fr);
  column-gap: 12px;
  align-items: start;
  width: 100%;
}

.tcp-port-debug-slot {
  min-width: 0;
}

.tcp-field-port :deep(.n-form-item-blank) {
  width: 100%;
}

.tcp-port-debug-inline {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
  width: 100%;
  min-width: 0;
}

.tcp-port-debug-inline .request-toolbar-input-fill {
  flex: 1;
  min-width: 0;
}

.tcp-debug-btn {
  flex-shrink: 0;
}

.tcp-body-mode-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 4px;
}

.tcp-body-mode-label {
  font-size: 14px;
  color: var(--n-text-color-2);
  min-width: 56px;
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

