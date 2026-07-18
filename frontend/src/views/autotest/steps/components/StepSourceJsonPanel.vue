<!--
  StepSourceJsonPanel — 步骤编辑「源数据模式」：编辑 update_or_create_tree 同构 JSON
-->
<template>
  <n-card size="small" :bordered="false" class="step-source-json-card">
    <template #header>
      <div class="source-json-header">
        <span class="source-json-title">源数据（case + steps）</span>
        <n-space :size="8">
          <n-button size="small" @click="emit('reset')">重置</n-button>
          <n-button type="primary" size="small" :loading="applyLoading" @click="emit('apply')">
            应用JSON数据
          </n-button>
        </n-space>
      </div>
    </template>
    <div class="source-json-editor-wrap">
      <MonacoEditor
          :value="modelValue"
          lang="json"
          theme="vs"
          :read-only="false"
          :options="editorOptions"
          @update:value="(v) => emit('update:modelValue', v)"
      />
    </div>
  </n-card>
</template>

<script setup>
import { NButton, NCard, NSpace } from 'naive-ui'
import MonacoEditor from '@/components/monaco/index.vue'

defineProps({
  modelValue: { type: String, default: '' },
  applyLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'reset', 'apply'])

const editorOptions = {
  automaticLayout: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  fontSize: 13,
  tabSize: 2,
  formatOnPaste: true,
}
</script>

<style scoped>
.step-source-json-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.step-source-json-card :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-top: 8px;
}

.source-json-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.source-json-title {
  font-size: 13px;
  font-weight: 500;
}

.source-json-editor-wrap {
  flex: 1;
  min-height: 480px;
  height: calc(100vh - 280px);
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  overflow: hidden;
}

.source-json-editor-wrap :deep(.monaco-editor) {
  height: 100% !important;
  min-height: 480px;
}
</style>
