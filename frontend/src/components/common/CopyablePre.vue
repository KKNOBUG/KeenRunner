<!--
  可复制的只读文本块：有内容时渲染带背景的 <pre>（点击复制到剪贴板），
  无内容时回退为 <n-empty> 占位。用于 Headers / Cookies 等键值对文本展示。
-->
<template>
  <pre v-if="content" class="copyable-pre" @click="doCopy">{{ content }}</pre>
  <n-empty v-else :description="emptyText" />
</template>

<script setup>
import { NEmpty } from 'naive-ui'

const props = defineProps({
  /** 展示文本（为空/空白时自动切换至 empty 态） */
  content: { type: String, default: '' },
  /** 空态提示文案 */
  emptyText: { type: String, default: '暂无数据' },
})

function doCopy() {
  if (!props.content) return
  navigator.clipboard?.writeText(props.content).then(() => {
    window.$message?.success('已复制')
  }).catch(() => {})
}
</script>

<style scoped>
.copyable-pre {
  margin: 0;
  padding: 8px 12px;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--n-action-color, rgba(128, 128, 128, 0.08));
  border-radius: 6px;
  cursor: copy;
}
</style>
