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
      return BACKEND_URL + this.userInfo?.avatar
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
    lastLogin() {
      return this.userInfo?.last_login
    },
    deptId() {
      return this.userInfo?.dept_id
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
        const { id, username, alias, email, phone, avatar, state, is_superuser, is_active, last_login, dept_id } = res.data
        this.userInfo = { id, username, alias, email, phone, avatar, state, is_superuser, is_active, last_login, dept_id }
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
