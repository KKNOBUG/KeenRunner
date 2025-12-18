<template>
  <n-tabs type="line" animated>
    <n-tab-pane name="script_info" tab="脚本信息">
      <div className="hint-box">
        如果想获取返回值请在脚本中将结果赋值给result变量 如 result = 1
      </div>
      <monaco-editor
          v-model:value="form.script"
          :options="monacoEditorOptions"
          class="code-editor"
          style="min-height: 400px; height: auto;"
      />
    </n-tab-pane>
    <n-tab-pane name="variables" tab="变量">
      <KeyValueEditor
          v-model:items="form.variables"
          :body-type="'none'"
          :is-for-body="false"
      />
    </n-tab-pane>
    <n-tab-pane name="extract" tab="提取">
      <KeyValueEditor
          v-model:items="form.extracts"
          :body-type="'none'"
          :is-for-body="false"
      />
    </n-tab-pane>
  </n-tabs>
</template>

<script setup>
import {reactive, watch} from 'vue'
import {NTabPane, NTabs} from 'naive-ui'
import MonacoEditor from "@/components/monaco/index.vue";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:config'])

const defaults = {
  script: `def generate_var():\n    import random\n    return {\n        f"key{random.randint(1, 99)}": f"{random.randint(1, 99)}"\n    }`,
  variables: [],
  extracts: []
}

const form = reactive({...defaults, ...props.config})

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

watch(
    () => props.config,
    (val) => Object.assign(form, defaults, val || {}),
    {deep: true, immediate: true}
)

watch(
    form,
    () => emit('update:config', {...form}),
    {deep: true}
)
</script>

<style scoped>
.hint-box {
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 16px;
  color: #0369a1;
  font-size: 14px;
}

.code-editor {
  font-family: 'Fira Code', monospace;
  border-radius: 4px;
  overflow: hidden;
}
</style>
