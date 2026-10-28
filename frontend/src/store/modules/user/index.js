import { defineStore } from 'pinia'
import { resetRouter } from '@/router'
import { useTagsStore, usePermissionStore } from '@/store'
import { removeToken, toLogin } from '@/utils'
import api from '@/api'
import {BACKEND_URL} from "~/build/constant";

export const useUserStore = defineStore('user', {
  state() {
    return {
      userInfo: {},
    }
  },
  getters: {
    userId() {
      return this.userInfo?.id
    },
    username() {
      return this.userInfo?.username
    },
    email() {
      return this.userInfo?.email
    },
    alias() {
      return this.userInfo?.alias
    },
    phone() {
      return this.userInfo?.phone
    },
    avatar() {
      // 数据库头像可空：未设置头像时回落到内置默认头像，避免头部出现破图
      return BACKEND_URL + (this.userInfo?.avatar || '/static/avatar/default/20250101010101.png')
    },
    state() {
      return this.userInfo?.state
    },
    isActive() {
      return this.userInfo?.is_active
    },
    isSuperUser() {
      return this.userInfo?.is_superuser
    },
    /** 后端计算：超管或挂有管理员角色，运行期为全量权限 */
    isAdmin() {
      return this.userInfo?.is_admin
    },
    lastLogin() {
      return this.userInfo?.last_login
    },
    deptId() {
      return this.userInfo?.dept_id
    },
    selectScope() {
      return this.userInfo?.select_scope
    },
    updateScope() {
      return this.userInfo?.update_scope
    },
    /**
     * 行级删除权限：列表接口已在每行注入 can_delete（后端按当前资源族的删除范围判定，
     * 含本部门/下级部门，前端无法复算部门归属），有该结论时直接采用；
     * 缺失时回落到归属账号比对（超管与管理员角色放行）。
     */
    canDeleteData() {
      return (owner, allowed) => {
        if (typeof allowed === 'boolean') return allowed
        if (this.isSuperUser || this.isAdmin) return true
        return (owner || '').trim().toUpperCase() === (this.username || '').trim().toUpperCase()
      }
    },
  },
  actions: {
    async getUserInfo() {
      try {
        const res = await api.getUserInfo()
        if (res.code === 401) {
          this.logout()
          return
        }
        // 接口主键已改为user_id返回，内部仍映射为id，保证getter(userId)与下游消费不变
        const { user_id: id, username, alias, email, phone, avatar, state, is_superuser, is_admin, is_active, last_login, dept_id, select_scope, update_scope } = res.data
        this.userInfo = { id, username, alias, email, phone, avatar, state, is_superuser, is_admin, is_active, last_login, dept_id, select_scope, update_scope }
        return res.data
      } catch (error) {
        return error
      }
    },
    async logout() {
      const { resetTags } = useTagsStore()
      const { resetPermission } = usePermissionStore()
      removeToken()
      resetTags()
      resetPermission()
      resetRouter()
      this.$reset()
      toLogin()
    },
    setUserInfo(userInfo = {}) {
      this.userInfo = { ...this.userInfo, ...userInfo }
    },
  },
})
