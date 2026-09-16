<template>
  <CommonPage show-footer title="执行机器">
    <NEmpty description="功能建设中：施压 worker 机器注册与资源监控（P1 规划）" class="py-120" />
  </CommonPage>
</template>

<script setup>
import { NEmpty } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '执行机器' })
</script>
