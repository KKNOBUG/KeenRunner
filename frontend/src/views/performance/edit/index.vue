<template>
  <CommonPage show-footer title="编辑压测场景">
    <PerfTaskForm v-if="perfId != null" :perf-id="perfId" @saved="goBack" @cancel="goBack" />
  </CommonPage>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CommonPage from '@/components/page/CommonPage.vue'
import PerfTaskForm from '../components/PerfTaskForm.vue'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '编辑场景' })

const route = useRoute()
const router = useRouter()

/** 由列表页「编辑」按钮经 query 传入，缺省回列表 */
const perfId = ref(null)

onMounted(() => {
  const id = Number(route.query.perf_id)
  if (!id) {
    window.$message?.warning('缺少场景ID，请从压测场景列表进入')
    goBack()
    return
  }
  perfId.value = id
})

function goBack() {
  router.push('/performance/perf_case')
}
</script>
