/**
 * 多页签（Tags）状态管理
 *
 * 职责：
 * - 维护当前打开的页签列表（tags）与当前激活页签（activeTag）
 * - 持久化到本地存储（lStorage），刷新后恢复
 * - 保证「工作台」页签不可关闭，且始终排在第一位
 *
 * 与路由的配合：
 * - 布局中的 watch(route.path) 会调用 addTag，新增或激活对应页签
 * - 关闭页签时 removeTag 会跳转到相邻页签
 */

import { defineStore } from 'pinia'
import { activeTag, tags, WITHOUT_TAG_PATHS, WORKBENCH_TAG_PATH } from './helpers'
import { router } from '@/router'
import { lStorage } from '@/utils'

/**
 * 从路由解析「工作台」页签信息（path/name/title），用于在列表缺失工作台时补全
 * @returns {{ path: string, name?: string, title?: string }}
 */
function getWorkbenchTag() {
  const resolved = router.resolve(WORKBENCH_TAG_PATH)
  return {
    name: resolved.name,
    path: WORKBENCH_TAG_PATH,
    title: resolved.meta?.title,
  }
}

/**
 * 保证「工作台」页签始终存在并排在第一位，其余保持原有相对顺序
 * @param {Array<{ path: string, name?: string, title?: string }>} tagList - 页签列表
 * @returns {Array} 工作台在前的新数组（不修改原数组）；列表无工作台时自动补全
 */
function sortTagsWithWorkbenchFirst(tagList) {
  const workbench = tagList.filter((t) => t.path === WORKBENCH_TAG_PATH)
  const rest = tagList.filter((t) => t.path !== WORKBENCH_TAG_PATH)
  return [...(workbench.length ? workbench : [getWorkbenchTag()]), ...rest]
}

/**
 * 尝试导航到目标页签；若被路由守卫拦截（如步骤编辑页脏检查选择「留下」）则返回 false。
 * 页签的增删/激活只在导航真正成功后进行，避免「页面留下但页签已关闭」的不一致。
 * @param {string} path - 目标路由 path
 * @returns {Promise<boolean>} 导航成功返回 true，被拦截返回 false
 */
async function navigateIfAllowed(path) {
  const failure = await router.push(path)
  return !failure
}

export const useTagsStore = defineStore('tag', {
  state() {
    return {
      /** 当前打开的页签列表，工作台始终存在且在索引 0 */
      tags: sortTagsWithWorkbenchFirst(tags || []),
      /** 当前激活的页签路径，与路由 path 一致 */
      activeTag: activeTag || '',
    }
  },
  getters: {
    /** 当前激活页签在 tags 数组中的下标 */
    activeIndex() {
      return this.tags.findIndex((item) => item.path === this.activeTag)
    },
  },
  actions: {
    /**
     * 设置当前激活的页签（并持久化）
     * @param {string} path - 页签对应路由 path
     */
    setActiveTag(path) {
      this.activeTag = path
      lStorage.set('activeTag', path)
    },

    /**
     * 替换整个页签列表（写入前会强制将工作台排到第一位并持久化）
     * @param {Array<{ path: string, name?: string, title?: string }>} tags - 新页签列表
     */
    setTags(tags) {
      this.tags = sortTagsWithWorkbenchFirst(tags)
      lStorage.set('tags', this.tags)
    },

    /**
     * 新增或激活一个页签
     * - 若 path 在 WITHOUT_TAG_PATHS 中或已存在，仅做激活不追加
     * - 否则追加到列表并激活，setTags 会保证工作台仍在第一位
     * @param {{ path: string, name?: string, title?: string }} tag - 页签信息（path 必填）
     */
    addTag(tag = {}) {
      this.setActiveTag(tag.path)
      if (WITHOUT_TAG_PATHS.includes(tag.path) || this.tags.some((item) => item.path === tag.path))
        return
      this.setTags([...this.tags, tag])
    },

    /**
     * 关闭指定 path 的页签
     * - 工作台（WORKBENCH_TAG_PATH）不允许关闭，直接 return
     * - 若关闭的是当前激活页签，先导航到相邻页签；导航被守卫拦截（如脏检查「留下」）时保留该页签
     * @param {string} path - 要关闭的页签 path
     */
    async removeTag(path) {
      if (path === WORKBENCH_TAG_PATH) return
      if (path === this.activeTag) {
        const nextPath = this.activeIndex > 0
            ? this.tags[this.activeIndex - 1].path
            : this.tags[this.activeIndex + 1].path
        // 先导航（可能被脏检查守卫拦截）；成功后再更新激活页签与列表，避免「页面留下但页签已关闭」。
        // 显式更新激活页签：相邻页签与当前页 route.path 相同（仅 query 不同，如多个「步骤编辑」页签）时，
        // 布局 watch(route.path) 不会触发，activeTag 不会被自动更新，会导致后续关闭页签不再跳转
        if (!await navigateIfAllowed(nextPath)) return
        this.setActiveTag(nextPath)
      }
      this.setTags(this.tags.filter((tag) => tag.path !== path))
    },

    /**
     * 关闭除「当前页签」和「工作台」以外的全部页签
     * 工作台始终保留并排在第一位
     * @param {string} [curPath=this.activeTag] - 要保留的当前页 path
     */
    async removeOther(curPath = this.activeTag) {
      const keep = this.tags.filter(
          (tag) => tag.path === curPath || tag.path === WORKBENCH_TAG_PATH
      )
      if (curPath !== this.activeTag) {
        // 将离开当前激活页签：先导航（可能被脏检查拦截），成功后再裁剪列表
        if (!await navigateIfAllowed(keep[keep.length - 1].path)) return
      }
      this.setTags(keep)
    },

    /**
     * 关闭当前页签左侧的所有页签（保留工作台与当前及右侧）
     * 若当前为工作台则不做任何操作
     * @param {string} curPath - 作为分界线的页签 path
     */
    async removeLeft(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
          (item, index) => index >= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        // 当前激活页签将被移除：先导航（可能被脏检查拦截），成功后再裁剪列表
        if (!await navigateIfAllowed(filterTags[filterTags.length - 1].path)) return
      }
      this.setTags(filterTags)
    },

    /**
     * 关闭当前页签右侧的所有页签（保留工作台与当前及左侧）
     * 若当前为工作台则不做任何操作
     * @param {string} curPath - 作为分界线的页签 path
     */
    async removeRight(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
          (item, index) => index <= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        // 当前激活页签将被移除：先导航（可能被脏检查拦截），成功后再裁剪列表
        if (!await navigateIfAllowed(filterTags[filterTags.length - 1].path)) return
      }
      this.setTags(filterTags)
    },

    /**
     * 清空页签列表并清空激活态（如登出时调用）
     */
    resetTags() {
      this.setTags([])
      this.setActiveTag('')
    },
  },
})
