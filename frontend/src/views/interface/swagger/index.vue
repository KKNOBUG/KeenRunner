<template>
  <AppPage>
    <iframe
        class="docs-iframe"
        title="Swagger 文档"
        :src="iframeSrc"
        frameborder="0"
    />
  </AppPage>
</template>

<script setup>
import AppPage from '@/components/page/AppPage.vue'
import { computed } from 'vue'
import { BACKEND_URL } from '~/build/constant'

defineOptions({ name: 'Swagger文档' })

/**
 * 必须与「后端」同源加载文档页，不能走 Vite 代理用 /krun/docs：
 * 否则 iframe 的 document 在 localhost:5173，Swagger「Try it out」会把请求发到 5173 而非 FastAPI，表现为 404（不是 CORS）。
 */
const apiOrigin = computed(() => {
  const fromEnv = (import.meta.env.VITE_BACKEND_ORIGIN || '').trim().replace(/\/$/, '')
  const fromConst = String(BACKEND_URL || '').trim().replace(/\/$/, '')
  return fromEnv || fromConst
})

/** 与 backend/configure/project_config.py 中 APP_DOCS_URL 一致（默认 /krun/docs） */
const iframeSrc = computed(() => `${apiOrigin.value}/krun/docs`)
</script>

<style scoped>
.docs-iframe {
  width: 100%;
  height: calc(100vh - 120px);
  border: 0;
  display: block;
}
</style>
