import { useUserStore, usePermissionStore } from '@/store'

function hasPermission(permission) {
  const userStore = useUserStore()
  const userPermissionStore = usePermissionStore()

  const accessApis = userPermissionStore.apis
  if (userStore.isSuperUser) {
    return true
  }
  return accessApis.includes(permission)
}

export default function setupPermissionDirective(app) {
  function updateElVisible(el, permission) {
    if (!permission) {
      throw new Error('v-permission 需要传入 apiPermissionKey(method, path)')
    }
    if (!hasPermission(permission)) {
      el.parentElement?.removeChild(el)
    }
  }

  const permissionDirective = {
    mounted(el, binding) {
      updateElVisible(el, binding.value)
    },
    beforeUpdate(el, binding) {
      updateElVisible(el, binding.value)
    },
  }

  app.directive('permission', permissionDirective)
}
