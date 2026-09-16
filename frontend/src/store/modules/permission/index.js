import { defineStore } from 'pinia'
import { basicRoutes, vueModules } from '@/router/routes'
import Layout from '@/layout/index.vue'
import api from '@/api'
import { normalizeBackendApiPermissionKey } from '@/utils/permissionKey'

// * 后端路由相关函数

/**
 * 拼接父菜单与子菜单 path，子路径以 / 开头视为绝对路径（与侧边栏 resolvePath 同口径）。
 * @param {string} basePath 父菜单 path，如 /performance
 * @param {string} subPath 子菜单 path，如 record
 * @returns {string} 菜单全路径，如 /performance/record
 */
function joinRoutePath(basePath, subPath) {
  if (String(subPath || '').startsWith('/')) return subPath
  return `/${[basePath, subPath]
    .filter((path) => !!path && path !== '/')
    .map((path) => String(path).replace(/(^\/)|(\/$)/g, ''))
    .join('/')}`
}

/**
 * 生成路由名。路由名必须全局唯一：vue-router 的名字表是全局的，重名时后注册的路由会把先注册的顶掉，
 * 被顶掉的菜单点击即匹配不到路由而落 404。而菜单 name 只是显示标题，不同目录下重名是合理的
 * （后端唯一性口径为 name+path），故路由名改由「全路径 + 菜单ID」派生，menu_id 为主键保证唯一，
 * 保留全路径是为了 devtools 可直接定位页面。
 * @param {string} fullPath 菜单全路径
 * @param {number} menuId 菜单ID
 * @returns {string} 路由名，如 /performance/record#38
 */
function buildRouteName(fullPath, menuId) {
  return `${fullPath}#${menuId}`
}

function buildRoutes(routes = []) {
  return routes.map((e) => {
    const route = {
      name: buildRouteName(e.path, e.menu_id),
      path: e.path,
      component: shallowRef(Layout),
      isHidden: e.is_hidden,
      redirect: e.redirect,
      meta: {
        title: e.name,
        icon: e.icon,
        order: e.order,
        keepAlive: e.keepalive,
      },
      children: [],
    }

    if (e.children && e.children.length > 0) {
      // 有子菜单
      route.children = e.children.map((e_child) => ({
        name: buildRouteName(joinRoutePath(e.path, e_child.path), e_child.menu_id),
        path: e_child.path,
        component: vueModules[`/src/views${e_child.component}/index.vue`],
        isHidden: e_child.is_hidden,
        meta: {
          title: e_child.name,
          icon: e_child.icon,
          order: e_child.order,
          keepAlive: e_child.keepalive,
          componentName: e_child.name, // KeepAlive include 匹配组件名，需与 defineOptions 一致
        },
      }))
    } else {
      // 没有子菜单，创建一个默认的子路由
      route.children.push({
        name: `${route.name}Default`,
        path: '',
        component: vueModules[`/src/views${e.component}/index.vue`],
        isHidden: true,
        meta: {
          title: e.name,
          icon: e.icon,
          order: e.order,
          keepAlive: e.keepalive,
          componentName: e.name, // KeepAlive include 匹配组件名，需与 defineOptions 一致
        },
      })
    }

    return route
  })
}

export const usePermissionStore = defineStore('permission', {
  state() {
    return {
      accessRoutes: [],
      accessApis: [],
    }
  },
  getters: {
    routes() {
      return basicRoutes.concat(this.accessRoutes)
    },
    menus() {
      return this.routes.filter((route) => route.name && !route.isHidden)
    },
    apis() {
      return this.accessApis
    },
  },
  actions: {
    async generateRoutes() {
      const res = await api.getUserMenu() // 调用接口获取后端传来的菜单路由
      this.accessRoutes = buildRoutes(res.data) // 处理成前端路由格式
      return this.accessRoutes
    },
    async getAccessApis() {
      const res = await api.getUserRouters()
      const raw = Array.isArray(res.data) ? res.data : []
      this.accessApis = raw.map(normalizeBackendApiPermissionKey)
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
  },
})
