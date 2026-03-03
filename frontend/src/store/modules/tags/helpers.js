/**
 * 页签（Tags）模块的常量与本地存储初始值
 * 供 store 初始化 state 及判断逻辑使用
 */
import { lStorage } from '@/utils'

/** 从本地存储读取的「当前激活页签路径」，用于 store 初始化 activeTag，刷新后恢复上次选中页签 */
export const activeTag = lStorage.get('activeTag')

/** 从本地存储读取的「已打开页签列表」，用于 store 初始化 tags，刷新后恢复已打开页签 */
export const tags = lStorage.get('tags')

/** 不参与页签的路由 path 列表：访问这些路由时不会新增/展示页签（如 404、登录页） */
export const WITHOUT_TAG_PATHS = ['/404', '/login']

/** 工作台页签的 path：该页签不可关闭，且在多页签中始终排在第一位 */
export const WORKBENCH_TAG_PATH = '/workbench'
