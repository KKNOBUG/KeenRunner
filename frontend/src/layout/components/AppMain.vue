<template>
  <router-view v-slot="{ Component, route }">
    <!-- KeepAlive 的 include 匹配的是组件名（defineOptions），不是路由名；使用 meta.componentName 或 route.name 作为组件名 -->
    <!-- aliveKeys 以 route.path 为重置键：路由名已改为菜单全路径+ID 派生，缓存重置只认 path，与菜单名彻底解耦 -->
    <KeepAlive :include="keepAliveComponentNames">
      <component
          :is="Component"
          v-if="appStore.reloadFlag"
          :key="appStore.aliveKeys[route.path] || (route.meta?.keepAlive ? route.path : route.fullPath)"
      />
    </KeepAlive>
  </router-view>
</template>

<script setup>
import { useAppStore } from '@/store'
import { useRouter } from 'vue-router'
const appStore = useAppStore()
const router = useRouter()

const allRoutes = router.getRoutes()

/** 递归收集需缓存的组件名：KeepAlive 的 include 匹配组件名（defineOptions），非路由名 */
function collectKeepAliveNames(routes, result = []) {
  for (const r of routes) {
    if (r.meta?.keepAlive) {
      const name = r.meta.componentName || r.name
      if (name && !result.includes(name)) result.push(name)
    }
    if (r.children?.length) collectKeepAliveNames(r.children, result)
  }
  return result
}

const keepAliveComponentNames = computed(() => collectKeepAliveNames(allRoutes))
</script>
