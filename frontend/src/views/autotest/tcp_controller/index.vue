<template>
  <n-card :bordered="false" style="width: 100%;" :class="['tcp-card', { 'is-collapsed': requestCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">TCP Request</div>
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
          label-placement="left"
          label-width="90px"
          ref="formRef"
      >
        <n-form-item label="请求地址" path="request_project_id">
          <n-select
              v-model:value="state.form.request_project_id"
              placeholder="请求应用"
              :options="props.projectOptions"
              :loading="props.projectLoading"
              clearable
              filterable
              style="width: 180px;"
              :disabled="props.readonly"
          />
          <n-input
              v-model:value="state.form.target"
              placeholder="目标服务器(可选)：host:port，如 127.0.0.1:8080；不填则使用应用+环境配置"
              clearable
              style="flex: 1; margin-left: 8px;"
              :disabled="props.readonly"
          />
          <n-button
              v-if="!props.readonly"
              type="primary"
              @click="debugging"
              :loading="debugLoading"
              style="margin-left: 8px;"
          >
            调试
          </n-button>
        </n-form-item>

        <n-form-item label="步骤名称" path="step_name" required>
          <n-input
              v-model:value="state.form.step_name"
              placeholder="请输入步骤名称"
              clearable
              :disabled="props.readonly"
          />
        </n-form-item>

        <n-form-item label="步骤描述" path="step_desc">
          <n-input
              type="textarea"
              v-model:value="state.form.step_desc"
              placeholder="请输入步骤描述"
              clearable
              :disabled="props.readonly"
          />
        </n-form-item>

        <n-form-item label="请求内容" path="request_payload">
          <n-input
              type="textarea"
              v-model:value="state.form.request_payload"
              placeholder="输入 JSON 或文本（支持 ${var} 占位符）。若为合法 JSON 将按 JSON 发送，否则按 raw 文本发送。"
              clearable
              :disabled="props.readonly"
              :autosize="{ minRows: 6, maxRows: 14 }"
          />
        </n-form-item>
      </n-form>

      <n-tabs type="line" animated style="margin-top: 16px;">
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

import { reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
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
    target: '',
    request_payload: '',
    extract_variables: [],
    assert_validators: []
  }
})

const parseJsonSafely = (val) => {
  if (!val) return null
  if (typeof val === 'object') return val
  try { return JSON.parse(val) } catch { return null }
}

const buildConfigFromState = () => {
  const payloadText = String(state.form.request_payload ?? '')
  const parsed = parseJsonSafely(payloadText)
  const request_args_type = parsed != null ? 'json' : 'raw'
  const cfg = {
    step_name: state.form.step_name,
    step_desc: state.form.step_desc,
    request_project_id: state.form.request_project_id,
    target: state.form.target,
    request_args_type,
    request_text: parsed == null ? payloadText : null,
    data: parsed != null ? parsed : {},
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
  state.form.target = cfg.target ?? (
      original.request_url && original.request_port
          ? `${original.request_url}:${original.request_port}`
          : (original.request_url || '')
  )
  const argsType = String(cfg.request_args_type ?? original.request_args_type ?? '').toLowerCase()
  if (argsType === 'json') {
    const bodyObj = cfg.data ?? original.request_body ?? {}
    state.form.request_payload = typeof cfg.request_payload === 'string'
        ? cfg.request_payload
        : JSON.stringify(bodyObj || {}, null, 2)
  } else {
    state.form.request_payload = cfg.request_payload ?? cfg.request_text ?? original.request_text ?? ''
  }

  state.form.extract_variables = cfg.extract_variables ?? original.extract_variables ?? []
  state.form.assert_validators = cfg.assert_validators ?? original.assert_validators ?? []
}

watch(
    () => props.step?.id,
    () => initFromProps(),
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
      request_url: cfg.target || '',
      request_port: null,
      request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
      request_args_type: cfg.request_args_type ?? original.request_args_type ?? 'raw',
      request_text: cfg.request_text ?? null,
      request_body: cfg.data ?? null,
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
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title {
  font-weight: 600;
}
.hint {
  margin-top: 8px;
  color: var(--n-text-color-3);
  font-size: 12px;
}
.tcp-card :deep(.n-card-header) {
  padding-bottom: 10px;
}
</style>

