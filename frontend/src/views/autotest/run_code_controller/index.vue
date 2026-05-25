<template>
  <div class="code-container">
    <!-- 合并后的 Card：步骤名称、使用说明、调试按钮和代码编辑器 -->
    <n-card :bordered="true" style="width: 100%;" class="code-card">
      <!-- 顶部操作栏 -->
      <div class="top-bar">
        <div class="python-logo">
          <svg viewBox="0 0 128 128" width="32" height="32">
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
        <n-input
            v-model:value="form.step_name"
            placeholder="代码请求(Python)"
            class="step-name-input"
            :disabled="props.readonly"
        />
        <n-button v-if="!props.readonly" strong secondary type="primary" :loading="debugLoading" @click="handleDebug">
          调试
        </n-button>
      </div>

      <n-tabs type="line" animated class="code-tabs">
        <n-tab-pane name="code" tab="代码">
          <!-- 使用说明（仅 Code 页） -->
          <div class="hint-box">
            <div class="hint-title">使用说明</div>
            <div class="hint-content">
              <p>• 仅可定义单个函数作为入口，系统将<code>自动调用</code>该函数；</p>
              <p>• 支持函数内部使用 <code>${变量名}</code> 占位符引用上下文变量；</p>
              <p>• 支持代码调试查看执行结果，如遇异常也会<code>反馈错误消息</code>；</p>
              <p>• 函数返回的执行结果类型必须是 <code>Dict[str, Any]</code>类型;</p>
              <p>• 系统会自动的获取该函数执行结果，并添加到<code>会话变量池;</code></p>
              <p>• 「断言」页仅支持从<code>变量池</code>取实际值（变量名为表达式），与 HTTP 步骤中断言列表布局一致。</p>
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
          <n-space vertical :size="16">
            <div v-for="(item, key) in form.assert_validators" :key="key" class="validator-item">
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

    <!-- 调试响应结果 Card -->
    <n-card
        v-if="debugResponse"
        :bordered="true"
        style="width: 100%; margin-top: 16px;"
        class="response-card"
    >
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
import { reactive, watch, nextTick, ref, computed, h } from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NDataTable,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NTabPane,
  NTag,
  NTabs,
} from 'naive-ui'
import MonacoEditor from "@/components/monaco/index.vue"
import TheIcon from "@/components/icon/TheIcon.vue"
import { assertionOperationSelectOptions } from '@/constants/autotestAssertionOperation'
import api from '@/api'

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

const defaults = {
  step_name: '',
  code: '',
  assert_validators: {}
}

/** 后端 assert_validators 列表 -> 表单中的字典结构（与 HTTP 控制器一致字段：jsonpath/expr、assertion/operation、value/except_value） */
function initValidatorsFromBackend(list) {
  const obj = {}
  if (!Array.isArray(list) || !list.length) return obj
  list.forEach((item, i) => {
    const key = String(i + 1)
    obj[key] = {
      name: item.name || '',
      object: '变量池',
      jsonpath: item.expr || '',
      assertion: item.operation || '等于',
      value: item.except_value != null ? String(item.except_value) : '',
    }
  })
  return obj
}

/** 表单断言 -> 后端列表（含未填完的草稿，避免 emit 空数组后父组件回写把本地行清空） */
function buildValidatorsForBackend() {
  return Object.values(form.assert_validators || {}).map((item) => ({
    expr: item.jsonpath || '',
    name: item.name || '',
    source: '变量池',
    operation: item.assertion || '等于',
    except_value: item.value != null ? String(item.value) : '',
  }))
}

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
    assert_validators: initValidatorsFromBackend(
        Array.isArray(validatorsRaw) ? validatorsRaw : []
    ),
  }
}

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original, props.step?.name)
})

const validatorCollapseState = reactive({})

const validatorsCount = computed(() => Object.keys(form.assert_validators || {}).length)

// Python 步骤断言仅允许变量池（与后端一致）；选项保留一项避免误选 Response*
const validatorObjectOptions = [{ label: '变量池', value: '变量池' }]

function getExtractObjectLabel(value) {
  const opt = validatorObjectOptions.find((o) => o.value === value)
  return opt ? opt.label : value || '变量池'
}

function getValidatorPlaceholder(object) {
  if (object === '变量池') return '请输入变量池中的变量名，如：token'
  return '请输入变量名'
}

const assertionOptions = assertionOperationSelectOptions

function getNextValidatorKey() {
  const keys = Object.keys(form.assert_validators || {})
      .map((k) => parseInt(k, 10))
      .filter((k) => !Number.isNaN(k))
  if (keys.length === 0) return '1'
  return String(Math.max(...keys) + 1)
}

// 添加断言
const addValidator = () => {
  const key = getNextValidatorKey()
  form.assert_validators[key] = {
    name: '',
    object: '变量池',
    jsonpath: '',
    assertion: '等于',
    value: '',
  }
  validatorCollapseState[key] = false
}

// 删除断言
const removeValidator = (key) => {
  delete form.assert_validators[key]
  delete validatorCollapseState[key]
}

// 复制断言
const duplicateValidator = (key) => {
  const item = form.assert_validators[key]
  if (item) {
    const newKey = getNextValidatorKey()
    form.assert_validators[newKey] = {
      ...JSON.parse(JSON.stringify(item)),
      name: item.name ? `${item.name}_副本` : ''
    }
    validatorCollapseState[newKey] = validatorCollapseState[key] ?? false
  }
}
function toggleValidatorCollapse(key) {
  validatorCollapseState[key] = !validatorCollapseState[key]
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

// 格式化调试响应为 JSON 字符串
const debugResponseText = computed(() => {
  if (!debugResponse.value) return ''
  try {
    return JSON.stringify(debugResponse.value, null, 2)
  } catch (e) {
    return String(debugResponse.value)
  }
})

// 后端调试接口：data = { result: Dict, assert_validators: List }；兼容旧版本直接返回 Dict
const debugResultData = computed(() => {
  const d = debugResponse.value
  if (!d) return {}
  if (typeof d === 'object' && d.result !== undefined) return d.result || {}
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

// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false

// 监听props变化，更新表单
watch(
    () => [props.step?.id, props.config, props.step?.original, props.step?.name],
    ([stepId, config, original, stepName]) => {
      // 当步骤变化时，重新初始化表单
      isExternalUpdate = true
      const merged = mergeConfigAndOriginal(config || {}, original, stepName)
      Object.assign(form, defaults, merged)
      Object.keys(validatorCollapseState).forEach((k) => delete validatorCollapseState[k])
      // 使用 nextTick 确保在下一个 tick 重置标志
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { deep: true, immediate: true }
)

// 监听表单变化，发送更新
watch(
    () => [form.step_name, form.code, form.assert_validators],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      emit('update:config', {
        step_name: form.step_name || '',
        code: form.code || '',
        assert_validators: buildValidatorsForBackend(),
      })
    },
    { deep: true }
)

// 调试功能
const handleDebug = async () => {
  if (!form.code || !form.code.trim()) {
    window.$message?.warning?.('请输入要调试的Python代码')
    return
  }

  debugLoading.value = true
  debugResponse.value = null

  try {
    const requestData = {
      step_name: form.step_name || '代码请求(Python)',
      code: form.code,
      request_args_type: 'raw',
      // 后端要求为 List[Dict[str, Any]]，此处调试模式先传空数组
      defined_variables: [],
      session_variables: [],
      assert_validators: buildValidatorsForBackend(),
    }

    const response = await api.pythonCodeDebugging(requestData)
    console.log("response")
    console.log(response)
    console.log("response")
    if (response.code === '000000' && response.data) {
      debugResponse.value = response.data
      window.$message?.success?.(response.message || '代码调试成功')
    } else {
      debugResponse.value = response.data
      console.log(debugResponse)
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
}

.code-card {
  margin: 8px 0;
  border-radius: 12px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.5);
  border-left: 3px solid #F4511E
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.python-logo {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.step-name-input {
  flex: 1;
}

.hint-box {
  background-color: rgba(244, 81, 30, 0.15);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 16px;
}

.hint-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
}

.hint-content {
  font-size: 12px;
  line-height: 1.4;
}

.hint-content p {
  margin: 4px 0;
}

.hint-content code {
  background-color: rgba(255, 255, 255, 0.8);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  color: #F4511E;
}

.code-tabs {
  margin-top: 4px;
}

.code-tabs :deep(.n-tab-pane) {
  padding-top: 12px;
}

.debug-tabs :deep(.n-tab-pane) {
  padding-top: 12px;
}

.validator-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.validator-item {
  margin-bottom: 1px;
}

.validator-item :deep(.n-card) {
  border: 1px solid #e0e0e0;
}

.validator-item :deep(.n-card-header) {
  padding: 12px 16px;
  background-color: #fafafa;
  border-bottom: 1px solid #e0e0e0;
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
  border-left: 1px solid #999;
  box-sizing: border-box;
  line-height: 1.2;
}

.code-snippets-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
}

.code-snippets-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.code-snippets-list li + li {
  margin-top: 10px;
}

.code-snippet-link {
  display: block;
  width: 100%;
  padding: 0 0 4px 8px;
  border: none;
  background: none;
  text-align: left;
  font-size: 12px;
  line-height: 1.4;
  color: #2080f0;
  cursor: pointer;
}

.code-snippet-link:hover:not(:disabled) {
  color: #F4511E;
  text-decoration: underline;
}

.code-snippet-link:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}

.code-editor {
  font-family: 'Fira Code', monospace;
  border-radius: 10px;
  overflow: hidden;
}

.response-card {
  border-left: 4px solid #F4511E;
}

.response-editor {
  font-family: 'Fira Code', monospace;
  border-radius: 10px;
  overflow: hidden;
}
</style>
