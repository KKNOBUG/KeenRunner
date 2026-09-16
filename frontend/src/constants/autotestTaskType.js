/**
 * 异步中心任务类型（与后端 AutoTestTaskType 存储值一一对应）。
 * 存储值即展示文案，历史存储值由后端 task_type_rename_migrate.sql 迁移，无需前端映射。
 */
export const ASYNC_CENTER_TASK_TYPE_OPTIONS = Object.freeze([
  { label: '公共接口导入', value: '公共接口导入' },
  { label: '公共接口导出', value: '公共接口导出' },
  { label: '公共接口报文数据导出', value: '公共接口报文数据导出' },
  { label: '单接口脚本生成', value: '单接口脚本生成' },
  { label: '测试案例生成', value: '测试案例生成' },
])

/** 异步中心范围过滤：非脚本执行类任务类型存储值集合，列表请求固定携带 task_type_in */
export const ASYNC_CENTER_TASK_TYPE_VALUES = Object.freeze(
  ASYNC_CENTER_TASK_TYPE_OPTIONS.map((o) => o.value),
)

/** 任务记录范围过滤：定时任务（多用例编排）执行记录的存储值集合 */
export const TASK_RECORD_TASK_TYPE_VALUES = Object.freeze(['多个用例执行'])
