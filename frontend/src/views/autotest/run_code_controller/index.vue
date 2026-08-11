<template>
  <div class="code-container">
    <n-card :bordered="false" class="step-editor-card">
      <template #header>
        <div class="card-header-row">
          <div class="panel-title">Python 代码</div>
          <div class="card-header-actions">
            <n-button
                v-if="!props.readonly"
                type="primary"
                size="small"
                :loading="debugLoading"
                @click="handleDebug"
            >
              调试
            </n-button>
          </div>
        </div>
      </template>

      <div class="top-bar">
        <div class="python-logo" aria-hidden="true">
          <svg viewBox="0 0 128 128" width="28" height="28">
            <linearGradient id="python-gradient-a" gradientUnits="userSpaceOnUse" x1="70.252" y1="1237.476" x2="170.659" y2="1151.089" gradientTransform="matrix(.563 0 0 -.568 -29.215 707.817)">
              <stop offset="0" stop-color="#5A9FD4"/>
              <stop offset="1" stop-color="#306998"/>
            </linearGradient>
            <linearGradient id="python-gradient-b" gradientUnits="userSpaceOnUse" x1="209.474" y1="1098.811" x2="173.62" y2="1149.537" gradientTransform="matrix(.563 0 0 -.568 -29.215 707.817)">
              <stop offset="0" stop-color="#FFD43B"/>
              <stop offset="1" stop-color="#FFE873"/>
            </linearGradient>
            <path fill="url(#python-gradient-a)" d="M63.391 1.988c-4.222.02-8.252.379-11.8 1.007-10.45 1.846-12.346 5.71-12.346 12.837v10.411h24.693v3.137H29.977c-7.176 0-13.46 4.313-15.426 12.521-2.268 9.405-2.368 15.275 0 25.096 1.755 7.311 5.947 12.521 13.124 12.521h8.491V67.234c0-8.151 7.051-15.34 15.426-15.34h24.665c6.866 0 12.346-5.654 12.346-12.548V15.833c0-6.693-5.646-11.72-12.346-12.837-4.244-.706-8.645-1.027-12.866-1.008zM50.037 9.557c2.55 0 4.634 2.117 4.634 4.721 0 2.593-2.083 4.69-4.634 4.69-2.56 0-4.633-2.097-4.633-4.69-.001-2.604 2.073-4.721 4.633-4.721z" transform="translate(0 10.26)"/>
            <path fill="url(#python-gradient-b)" d="M91.682 28.38v10.966c0 8.5-7.208 15.655-15.426 15.655H51.591c-6.756 0-12.346 5.783-12.346 12.549v23.515c0 6.691 5.818 10.628 12.346 12.547 7.816 2.297 15.312 2.713 24.665 0 6.845-1.522 12.346-5.75 12.346-12.547v-9.412H63.938v-3.138h37.012c7.176 0 9.852-5.005 12.348-12.519 2.578-7.735 2.467-15.174 0-25.096-1.774-7.145-5.161-12.521-12.348-12.521H91.682zm28.11 88.33c-2.561 0-4.634 2.097-4.634 4.692 0 2.602 2.074 4.719 4.634 4.719 2.55 0 4.633-2.117 4.633-4.719 0-2.595-2.083-4.692-4.633-4.692z" transform="translate(0 10.26)"/>
          </svg>
        </div>
        <n-form class="step-editor-form code-name-form" label-placement="left" label-width="80px" size="small">
          <n-form-item label="步骤名称" :show-feedback="false">
            <n-input
                v-model:value="form.step_name"
                placeholder="代码请求(Python)"
                class="step-name-input"
                :disabled="props.readonly"
            />
          </n-form-item>
        </n-form>
      </div>

      <n-tabs type="line" animated class="code-tabs">
        <n-tab-pane name="code" tab="代码">
          <div class="hint-box step-editor-hint">
            <div class="hint-title">使用说明</div>
            <div class="hint-content">
              <p>• 脚本以函数形式作为执行入口，<code>必须符合PEP8编码规范</code>，声明格式：<code>def func() -> dict | list: ...</code></p>
              <p>• 脚本返回值支持 <code>Dict[str, Any]</code> 或 <code>List[Dict]</code>：字典时各键写入会话变量池；列表时整体写入变量 <code>result</code>，方便后续步骤使用</p>
              <p>• 脚本支持使用 <code>${函数名称}</code> 格式占位符调用系统内置函数，使用 <code>${变量名称}</code> 格式占位符引用上下文变量</p>
              <p>• 脚本支持针对执行结果进行断言校验，可<code>从会话变量池读取目标变量，与预设预期值完成各类型比较核验</code></p>
            </div>
          </div>
          <div class="code-editor-row">
            <monaco-editor
                ref="codeEditorRef"
                v-model:value="form.code"
                :options="codeEditorOptions"
                class="code-editor code-editor-main"
                style="min-height: 500px; height: auto;"
            />
            <aside class="code-snippets-panel">
              <div class="code-snippets-title">代码片段</div>
              <ul class="code-snippets-list">
                <li v-for="item in codeSnippets" :key="item.label">
                  <button
                      type="button"
                      class="code-snippet-link"
                      :disabled="props.readonly"
                      @click="insertCodeSnippet(item)"
                  >
                    {{ item.label }}
                  </button>
                </li>
              </ul>
            </aside>
          </div>
        </n-tab-pane>
        <n-tab-pane name="assert_validators" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <StepAssertPanel
              v-model="form.assert_validators"
              mode="python"
              :readonly="props.readonly"
          />
        </n-tab-pane>
      </n-tabs>
    </n-card>

    <n-card
        v-if="debugResponse"
        :bordered="false"
        class="step-editor-card"
    >
      <template #header>
        <div class="panel-title">Response</div>
      </template>
      <n-tabs type="line" animated class="debug-tabs">
        <n-tab-pane name="result" tab="结果">
          <monaco-editor
              :value="debugResultText"
              :options="responseEditorOptions"
              class="response-editor"
              style="min-height: 500px; height: auto;"
              :read-only="true"
          />
        </n-tab-pane>
        <n-tab-pane name="assert" tab="断言">
          <template #tab>
            <n-badge :value="debugAssertCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <n-data-table
              v-if="debugAssertCount > 0"
              :columns="debugValidatorColumns"
              :data="debugAssertRows"
              :bordered="false"
              size="small"
          />
          <n-empty v-else description="暂无断言结果"/>
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, h } from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NTabPane,
  NTag,
  NTabs,
} from 'naive-ui'
import MonacoEditor from "@/components/monaco/index.vue"
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import {
  ASSERT_MODE_PYTHON,
  buildAssertListFromDict,
  countDictKeys,
  hydrateAssertDictFromBackend,
  normalizeBackendList,
  validateAssertList,
} from '@/utils/autotestExtractAssert'
import api from '@/api'
import { useStepEditorForm } from '@/composables/step-editor'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  },
  readonly: { type: Boolean, default: false }
})

const emit = defineEmits(['update:config'])

// 合并config和原始数据
const mergeConfigAndOriginal = (config, original, stepName) => {
  const validatorsRaw = config.assert_validators ?? original?.assert_validators
  return {
    step_name: config.step_name !== undefined
        ? config.step_name
        : (stepName || original?.step_name || ''),
    code: config.code !== undefined
        ? config.code
        : (config.script !== undefined ? config.script : (original?.code || '')),
    assert_validators: hydrateAssertDictFromBackend(
        normalizeBackendList(validatorsRaw),
        ASSERT_MODE_PYTHON
    ),
  }
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ step_name: '', code: '', assert_validators: {} }),
  hydrate: (p) => mergeConfigAndOriginal(p.config || {}, p.step?.original, p.step?.name),
  buildConfig: (f) => ({
    step_name: f.step_name || '',
    code: f.code || '',
    assert_validators: buildAssertListFromDict(f.assert_validators, ASSERT_MODE_PYTHON),
  }),
  watchFields: (f) => [f.step_name, f.code, f.assert_validators],
})

const validatorsCount = computed(() => countDictKeys(form.assert_validators))

function buildValidatorsForBackend() {
  return buildAssertListFromDict(form.assert_validators, ASSERT_MODE_PYTHON)
}

const monacoEditorOptions = {
  theme: 'vs-dark',
  language: 'python',
  fontSize: 12,
  tabSize: 4,
  automaticLayout: true,
  minimap: {enabled: true},
  lineNumbers: 'on',
  scrollBeyondLastLine: false,
  folding: true,
}

const codeEditorOptions = computed(() => ({
  ...monacoEditorOptions,
  readOnly: props.readonly
}))

/**
 * 常用代码片段（与执行上下文 defined_variables / session_variables 一致）
 * 展示名以 @ 开头表示在光标处插入；无 @ 则在文末换行追加
 */
/** 点击「示例代码」时替换编辑器全部内容的模板 */
const PYTHON_STEP_EXAMPLE = `import random


def generate_test_data() -> dict:
    """
    利用内置函数生成虚拟数据
    :return:
    """
    job = '\${generate_job()}'
    name = '\${generate_name()}'
    phone = '\${generate_phone()}'
    email = '\${generate_email()}'
    address = '\${generate_address()}'
    id_card = '\${generate_ident_card_number()}'
    birthday = f'\${{generate_ident_card_birthday(ident_card_number={id_card})}}'
    gender = f'\${{generate_ident_card_gender(ident_card_number={id_card})}}'
    datetime_str1 = '\${generate_datetime(fmt=11)}'
    datetime_str2 = '\${generate_datetime(fmt=21)}'
    datetime_str3 = '\${generate_datetime(fmt=31)}'
    datetime_str4 = '\${generate_datetime(fmt=41)}'
    datetime_str5 = '\${generate_datetime(fmt=42)}'
    datetime_str6 = '\${generate_datetime(fmt=51)}'
    datetime_str7 = '\${generate_datetime(fmt=52)}'
    random_float = '\${generate_float(min_=100, max_=999, num_3)}'
    random_int1 = '\${generate_random_int(min_=100000, max_=999999)}'
    random_int2 = '\${generate_random_int(min_=100, max_=999)}'
    random_int3 = '\${generate_string(length=10, digit=True)}'
    random_str1 = '\${generate_string(length=10, char=True)}'
    random_str2 = '\${generate_string(length=10, chinese=True)}'
    random_str3 = '\${generate_string(length=20, char=True, chinese=True, digit=True)}'

    # 布尔 & 状态
    is_active = random.choice([True, False])
    status = random.choice(["pending", "success", "failed", "closed"])
    return {
        "id": random_int1,
        "no": random_int2,
        "username": name,
        "password": random_str1,
        "phone": phone,
        "email": email,
        "job": job,
        "address": address,
        "id_card": id_card,
        "birthday": birthday,
        "gender": gender,
        "random_str1": random_str3,
        "random_str2": random_str2,
        "random_int": random_int3,
        "random_float": random_float,
        "datetime_str1": datetime_str1,
        "datetime_str2": datetime_str2,
        "datetime_str3": datetime_str3,
        "datetime_str4": datetime_str4,
        "datetime_str5": datetime_str5,
        "datetime_str6": datetime_str6,
        "datetime_str7": datetime_str7,
        "is_active": is_active,
        "status": status,
    }
`

const codeSnippets = [
  { label: '@插入UUID', content: "uuid_str = '${generate_uuid()}'" },
  { label: '@插入时间戳', content: "timestamp = '${generate_timestamp()}'" },
  { label: '示例代码', content: PYTHON_STEP_EXAMPLE },
]

function shouldInsertAtCursor(snippet) {
  const label = snippet?.label || ''
  return label.startsWith('@')
}

function insertCodeSnippet(snippet) {
  if (props.readonly || !snippet?.content) return
  const text = snippet.content
  if (shouldInsertAtCursor(snippet) && codeEditorRef.value?.insertAtCursor) {
    codeEditorRef.value.insertAtCursor(text)
    form.code = codeEditorRef.value.getValue?.() ?? form.code
    return
  }
  // 示例代码：先清空再写入完整模板
  if (snippet.label === '示例代码') {
    form.code = text
    codeEditorRef.value?.setValue?.(text)
    return
  }
  form.code = form.code?.trim() ? `${form.code}\n${text}` : text
}

const responseEditorOptions = {
  theme: 'vs-dark',
  language: 'json',
  fontSize: 12,
  tabSize: 2,
  automaticLayout: true,
  minimap: {enabled: true},
  lineNumbers: 'on',
  wordWrap: 'off',
  scrollBeyondLastLine: false,
  folding: true,
  readOnly: true,
}

const codeEditorRef = ref(null)

// 调试相关状态
const debugLoading = ref(false)
const debugResponse = ref(null)

// 后端调试接口：data = { result: Dict|List, assert_validators: List }；兼容旧版本直接返回 Dict
const debugResultData = computed(() => {
  const d = debugResponse.value
  if (!d) return {}
  if (typeof d === 'object' && d.result !== undefined) return d.result ?? {}
  return d
})

const debugAssertRows = computed(() => {
  const d = debugResponse.value
  if (!d) return []
  const list = (typeof d === 'object' && Array.isArray(d.assert_validators)) ? d.assert_validators : []
  return list
})

const debugAssertCount = computed(() => debugAssertRows.value.length)

const debugResultText = computed(() => {
  try {
    return JSON.stringify(debugResultData.value, null, 2)
  } catch (e) {
    return String(debugResultData.value)
  }
})

// 断言结果列（复用 HTTP 请求页面断言结果结构）
const debugValidatorColumns = [
  { title: '断言名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = { '变量池': '变量池', 'session_variables': '变量池' }
      return sourceMap[row.source] || row.source
    }
  },
  { title: '断言路径', key: 'expr', width: 130, ellipsis: { tooltip: true } },
  {
    title: '结果值',
    key: 'actual_value',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => (row.actual_value === null || row.actual_value === undefined) ? '-' : String(row.actual_value)
  },
  { title: '断言方式', key: 'operation', width: 100 },
  {
    title: '期望值',
    key: 'except_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => (row.except_value === null || row.except_value === undefined) ? '-' : String(row.except_value)
  },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error',
      round: true,
      size: 'small'
    }, { default: () => row.success ? 'pass' : 'fail' })
  },
  { title: '错误信息', key: 'error', ellipsis: { tooltip: true }, render: (row) => row.error || '-' }
]

// 调试功能
const handleDebug = async () => {
  if (!form.code || !form.code.trim()) {
    window.$message?.warning?.('请输入要调试的Python代码')
    return
  }
  const assertCheck = validateAssertList(buildValidatorsForBackend())
  if (!assertCheck.valid) {
    window.$message?.error?.(assertCheck.message)
    return
  }

  debugLoading.value = true
  debugResponse.value = null

  try {
    const requestData = {
      step_name: form.step_name || '代码请求(Python)',
      code: form.code,
      request_args_type: 'raw',
      defined_variables: [],
      session_variables: [],
      assert_validators: buildValidatorsForBackend(),
    }

    const response = await api.pythonCodeDebugging(requestData)
    if (response.code === '000000' && response.data) {
      debugResponse.value = response.data
      window.$message?.success?.(response.message || '代码调试成功')
    } else {
      debugResponse.value = response.data
      window.$message?.error?.(response.message || '代码调试失败')
    }
  } catch (error) {
    console.error('调试请求异常:', error)
    window.$message?.error?.(error.message || '代码调试异常')
  } finally {
    debugLoading.value = false
  }
}
</script>

<style scoped>
.code-container {
  display: flex;
  flex-direction: column;
  gap: var(--step-editor-gap, 8px);
  font-size: var(--step-editor-font-size, 13px);
}

.card-header-row {
  padding-right: 88px;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.python-logo {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
}

.code-name-form {
  flex: 1;
  min-width: 0;
}

.code-name-form :deep(.n-form-item) {
  margin-bottom: 0;
}

.step-name-input {
  width: 100%;
}

.hint-box {
  background-color: color-mix(in srgb, var(--step-editor-accent, #f4511e) 12%, transparent);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.hint-title {
  font-size: var(--step-editor-font-size, 13px);
  font-weight: 600;
  margin-bottom: 6px;
}

.hint-content {
  font-size: var(--step-editor-meta-size, 12px);
  line-height: 1.5;
}

.hint-content p {
  margin: 4px 0;
}

.hint-content code {
  background-color: var(--n-color-embedded);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Fira Code', monospace;
  font-size: var(--step-editor-meta-size, 12px);
  color: var(--step-editor-accent, #f4511e);
}

.code-tabs {
  margin-top: 4px;
}

.code-tabs :deep(.n-tab-pane),
.debug-tabs :deep(.n-tab-pane) {
  padding-top: 12px;
}

.code-editor-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
  width: 100%;
}

.code-editor-main {
  flex: 0 0 85%;
  max-width: 85%;
  min-width: 0;
}

.code-snippets-panel {
  flex: 0 0 15%;
  max-width: 15%;
  min-width: 0;
  padding: 2px 4px 8px 8px;
  border-left: 1px solid var(--n-border-color);
  box-sizing: border-box;
  line-height: 1.2;
}

.code-snippets-title {
  font-size: var(--step-editor-font-size, 13px);
  font-weight: 600;
  margin-bottom: 10px;
}

.code-snippets-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.code-snippets-list li + li {
  margin-top: 8px;
}

.code-snippet-link {
  display: block;
  width: 100%;
  padding: 0 0 4px 8px;
  border: none;
  background: none;
  text-align: left;
  font-size: var(--step-editor-meta-size, 12px);
  line-height: 1.4;
  color: var(--n-primary-color, #2080f0);
  cursor: pointer;
}

.code-snippet-link:hover:not(:disabled) {
  color: var(--step-editor-accent, #f4511e);
  text-decoration: underline;
}

.code-snippet-link:disabled {
  color: var(--n-text-color-3);
  cursor: not-allowed;
}

.code-editor,
.response-editor {
  font-family: 'Fira Code', monospace;
  border-radius: 8px;
  overflow: hidden;
}
</style>
