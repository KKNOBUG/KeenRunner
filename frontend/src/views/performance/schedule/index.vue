<template>
  <CommonPage show-footer title="定时压测">
    <NEmpty description="功能建设中：负载预设定时调度（P1 规划，复用 redbeat 到期扫描下发 {port}_perf 队列）" class="py-120" />
  </CommonPage>
</template>

<script setup>
import { NEmpty } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '定时压测' })
</script>
