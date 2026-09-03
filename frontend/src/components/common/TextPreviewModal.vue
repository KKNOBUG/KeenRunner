<!-- TextPreviewModal — 文本/JSON 只读查看弹框：monaco 只读展示 + 一键复制（任务列表排期明细、执行记录结果摘要共用） -->
<template>
  <NModal
      :show="show"
      preset="card"
      :title="title"
      :mask-closable="true"
      :close-on-esc="true"
      :style="{ width }"
      @update:show="(v) => emit('update:show', v)"
  >
    <MonacoEditor
        :value="content"
        :lang="lang"
        theme="vs"
        :read-only="true"
        :options="editorOptions"
        style="height: 48vh"
    />
    <template #footer>
      <div class="text-preview-modal-footer">
        <NButton size="small" type="primary" @click="handleCopy">复制</NButton>
      </div>
    </template>
  </NModal>
</template>

<script setup>
import { NButton, NModal } from 'naive-ui'
import MonacoEditor from '@/components/monaco/index.vue'
import { copyTextToClipboard } from '@/utils'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' },
  /** 展示文本（调用方负责格式化，如 toPrettyJson） */
  content: { type: String, default: '' },
  /** monaco 语言标识：json | plaintext */
  lang: { type: String, default: 'json' },
  width: { type: String, default: 'min(720px, 92vw)' },
})

const emit = defineEmits(['update:show'])

// 只读查看：跟随 ReportDetailDrawer 详情展示的编辑器配置
const editorOptions = {
  automaticLayout: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  formatOnPaste: true,
}

const handleCopy = () => copyTextToClipboard(props.content)
</script>

<style scoped>
.text-preview-modal-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
