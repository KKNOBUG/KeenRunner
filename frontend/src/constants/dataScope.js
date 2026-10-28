/**
 * 角色数据权限范围（与 backend/enums/permission_enum.py 的 DataScopeEnum 取值一致）。
 * select_scope 控制可见范围，update_scope 控制可修改/新建范围，delete_scope 控制可删除范围；
 * 可写/可删范围不得宽于可见范围，多角色按最宽范围合并；超管与管理员角色不受限制。
 */
export const DATA_SCOPE_ALL = 'ALL'
export const DATA_SCOPE_DEPT_AND_CHILD = 'DEPT_AND_CHILD'
export const DATA_SCOPE_DEPT = 'DEPT'
export const DATA_SCOPE_SELF = 'SELF'

export const DATA_SCOPE_OPTIONS = Object.freeze([
  { label: '全部数据', value: DATA_SCOPE_ALL },
  { label: '本部门及下级部门', value: DATA_SCOPE_DEPT_AND_CHILD },
  { label: '本部门', value: DATA_SCOPE_DEPT },
  { label: '仅本人', value: DATA_SCOPE_SELF },
])

/** 范围值转展示文案，未知值原样返回便于排查配置 */
export const dataScopeLabel = (value) =>
  DATA_SCOPE_OPTIONS.find((option) => option.value === value)?.label || value || ''