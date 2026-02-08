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
            placeholder="执行代码请求(Python)"
            class="step-name-input"
            :disabled="props.readonly"
        />
        <n-button v-if="!props.readonly" strong secondary type="primary" :loading="debugLoading" @click="handleDebug">
          调试
        </n-button>
      </div>

      <!-- 使用说明 -->
      <div class="hint-box">
        <div class="hint-title">使用说明</div>
        <div class="hint-content">
          <p>• 仅可定义单个函数作为入口，系统将<code>自动调用</code>该函数；</p>
          <p>• 支持函数内部使用 <code>${变量名}</code> 占位符引用上下文变量；</p>
          <p>• 支持代码调试查看执行结果，如遇异常也会<code>反馈错误消息</code>；</p>
          <p>• 函数返回的执行结果类型必须是 <code>Dict[str, Any]</code>类型;</p>
          <p>• 系统会自动的获取该函数执行结果，并添加到<code>会话变量池;</code></p>
        </div>
      </div>

      <!-- 代码编辑器 -->
      <monaco-editor
          v-model:value="form.code"
          :options="codeEditorOptions"
          class="code-editor"
          style="min-height: 400px; height: auto;"
      />
    </n-card>

    <!-- 调试响应结果 Card -->
    <n-card
        v-if="debugResponse"
        :bordered="true"
        style="width: 100%; margin-top: 16px;"
        class="response-card"
        :title="`代码调试结果`"
    >
      <monaco-editor
          :value="debugResponseText"
          :options="responseEditorOptions"
          class="response-editor"
          style="min-height: 300px; height: auto;"
          :read-only="true"
      />
    </n-card>
  </div>
</template>

<script setup>
import { reactive, watch, nextTick, ref, computed } from 'vue'
import { NCard, NInput, NButton } from 'naive-ui'
import MonacoEditor from "@/components/monaco/index.vue"
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
  code: ''
}

// 合并config和原始数据
const mergeConfigAndOriginal = (config, original, stepName) => {
  return {
    // 优先使用 config.step_name，然后是 step.name，最后是 original.step_name
    step_name: config.step_name !== undefined
        ? config.step_name
        : (stepName || original?.step_name || ''),
    code: config.code !== undefined ? config.code : (original?.code || '')
  }
}

const form = reactive({
  ...defaults,
  ...mergeConfigAndOriginal(props.config, props.step?.original, props.step?.name)
})

const monacoEditorOptions = {
  theme: 'vs-dark',
  language: 'python',
  fontSize: 14,
  tabSize: 4,
  automaticLayout: true,
  minimap: {enabled: true},
  lineNumbers: 'on',
  wordWrap: 'off',
  scrollBeyondLastLine: false,
  folding: true,
}

const codeEditorOptions = computed(() => ({
  ...monacoEditorOptions,
  readOnly: props.readonly
}))

const responseEditorOptions = {
  theme: 'vs-dark',
  language: 'json',
  fontSize: 14,
  tabSize: 2,
  automaticLayout: true,
  minimap: {enabled: true},
  lineNumbers: 'on',
  wordWrap: 'off',
  scrollBeyondLastLine: false,
  folding: true,
  readOnly: true,
}

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
      // 使用 nextTick 确保在下一个 tick 重置标志
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    { deep: true, immediate: true }
)

// 监听表单变化，发送更新
watch(
    () => [form.step_name, form.code],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      emit('update:config', {
        step_name: form.step_name || '',
        code: form.code || ''
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
      step_name: form.step_name || 'Python代码调试',
      code: form.code,
      defined_variables: {},
      session_variables: {}
    }

    const response = await api.pythonCodeDebugging(requestData)
    if (response.code === '000000' && response.data) {
      debugResponse.value = response.data
      window.$message?.success?.(response.message || '代码调试成功')
    } else {
      window.$message?.error?.(response.message || '代码调试失败')
      debugResponse.value = response.data
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
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #F4511E;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
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
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}

.hint-content {
  font-size: 14px;
  line-height: 1.6;
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
