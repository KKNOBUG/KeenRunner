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
 * 将列表中的「工作台」页签排到第一位，其余保持原有相对顺序
 * @param {Array<{ path: string, name?: string, title?: string }>} tagList - 页签列表
 * @returns {Array} 工作台在前的新数组（不修改原数组）
 */
function sortTagsWithWorkbenchFirst(tagList) {
  const workbench = tagList.filter((t) => t.path === WORKBENCH_TAG_PATH)
  const rest = tagList.filter((t) => t.path !== WORKBENCH_TAG_PATH)
  return [...workbench, ...rest]
}

export const useTagsStore = defineStore('tag', {
  state() {
    return {
      /** 当前打开的页签列表，工作台（若存在）始终在索引 0 */
      tags: tags ? sortTagsWithWorkbenchFirst(tags) : [],
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
     * - 若关闭的是当前激活页签，则跳转到左侧或右侧页签
     * @param {string} path - 要关闭的页签 path
     */
    removeTag(path) {
      if (path === WORKBENCH_TAG_PATH) return
      if (path === this.activeTag) {
        if (this.activeIndex > 0) {
          router.push(this.tags[this.activeIndex - 1].path)
        } else {
          router.push(this.tags[this.activeIndex + 1].path)
        }
      }
      this.setTags(this.tags.filter((tag) => tag.path !== path))
    },

    /**
     * 关闭除「当前页签」和「工作台」以外的全部页签
     * 工作台始终保留且排在第一位
     * @param {string} [curPath=this.activeTag] - 要保留的当前页 path
     */
    removeOther(curPath = this.activeTag) {
      const keep = this.tags.filter(
          (tag) => tag.path === curPath || tag.path === WORKBENCH_TAG_PATH
      )
      this.setTags(keep)
      if (curPath !== this.activeTag) {
        router.push(this.tags[this.tags.length - 1].path)
      }
    },

    /**
     * 关闭当前页签左侧的所有页签（保留工作台与当前及右侧）
     * 若当前为工作台则不做任何操作
     * @param {string} curPath - 作为分界线的页签 path
     */
    removeLeft(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
          (item, index) => index >= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
    },

    /**
     * 关闭当前页签右侧的所有页签（保留工作台与当前及左侧）
     * 若当前为工作台则不做任何操作
     * @param {string} curPath - 作为分界线的页签 path
     */
    removeRight(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
          (item, index) => index <= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
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
