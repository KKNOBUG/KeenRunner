<template>
  <CommonPage show-footer title="新增压测场景">
    <PerfTaskForm @saved="goBack" @cancel="goBack" />
  </CommonPage>
</template>

<script setup>
import { useRouter } from 'vue-router'

import CommonPage from '@/components/page/CommonPage.vue'
import PerfTaskForm from '../components/PerfTaskForm.vue'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '新增场景' })

const router = useRouter()

function goBack() {
  router.push('/performance/perf_case')
}
</script>
