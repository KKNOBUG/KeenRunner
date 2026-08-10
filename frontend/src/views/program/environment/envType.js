/**
 * 环境节点类型：与后端 AutoTestConfigNodeType 对齐。
 * 协议值：api/file/database/redis。
 */
export const ENV_TYPE = {
  API: 'api',
  FILE: 'file',
  DB: 'database',
  REDIS: 'redis',
}

export const ENV_TYPE_OPTIONS = [
  { label: 'API', value: ENV_TYPE.API },
  { label: 'FILE', value: ENV_TYPE.FILE },
  { label: 'DB', value: ENV_TYPE.DB },
  { label: 'REDIS', value: ENV_TYPE.REDIS },
]

export const ENV_TYPE_LABEL = {
  [ENV_TYPE.API]: 'API',
  [ENV_TYPE.FILE]: 'FILE',
  [ENV_TYPE.DB]: 'DB',
  [ENV_TYPE.REDIS]: 'REDIS',
}

export const ENV_TYPE_TAG = {
  [ENV_TYPE.API]: 'success',
  [ENV_TYPE.FILE]: 'warning',
  [ENV_TYPE.DB]: 'info',
  [ENV_TYPE.REDIS]: 'error',
}

/** 路由路径中的 app 段对应 API 类型配置，非枚举值 */
export const CREATE_CONFIG_PERM = {
  [ENV_TYPE.API]: '/autotest/config/app/create',
  [ENV_TYPE.FILE]: '/autotest/config/file/create',
  [ENV_TYPE.DB]: '/autotest/config/database/create',
  [ENV_TYPE.REDIS]: '/autotest/config/redis/create',
}

export const UPDATE_CONFIG_PERM = {
  [ENV_TYPE.API]: '/autotest/config/app/update',
  [ENV_TYPE.FILE]: '/autotest/config/file/update',
  [ENV_TYPE.DB]: '/autotest/config/database/update',
  [ENV_TYPE.REDIS]: '/autotest/config/redis/update',
}
