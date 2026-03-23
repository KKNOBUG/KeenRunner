<template>
  <AppPage>
    <iframe
        class="docs-iframe"
        title="ReDoc 文档"
        :src="iframeSrc"
        frameborder="0"
    />
  </AppPage>
</template>

<script setup>
import AppPage from '@/components/page/AppPage.vue'
import { computed } from 'vue'
import { BACKEND_URL } from '~/build/constant'

defineOptions({ name: 'ReDoc文档' })

/**
 * 同 Swagger：iframe 须直连后端，避免 ReDoc 内请求落在前端开发端口。
 */
const apiOrigin = computed(() => {
  const fromEnv = (import.meta.env.VITE_BACKEND_ORIGIN || '').trim().replace(/\/$/, '')
  const fromConst = String(BACKEND_URL || '').trim().replace(/\/$/, '')
  return fromEnv || fromConst
})

/** 与 backend/configure/project_config.py 中 APP_REDOC_URL 一致（默认 /krun/redoc） */
const iframeSrc = computed(() => `${apiOrigin.value}/krun/redoc`)
</script>

<style scoped>
.docs-iframe {
  width: 100%;
  height: calc(100vh - 120px);
  border: 0;
  display: block;
}
</style>
