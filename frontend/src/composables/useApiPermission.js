import { usePermissionStore, useUserStore } from '@/store'
import { apiPermissionKey } from '@/utils'

/**
 * 接口权限判定：超级管理员直通，其余校验角色已绑定的 method+path 接口键。
 *
 * 页面按钮显隐与后端路由权限同源，避免受限角色看到必然 403 的入口；
 * 数据归属等行级约束由调用方另行判断。
 */
export function useApiPermission() {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  const hasApiPermission = (method, path) =>
      userStore.isSuperUser || permissionStore.apis.includes(apiPermissionKey(method, path))

  return { hasApiPermission }
}