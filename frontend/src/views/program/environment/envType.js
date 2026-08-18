/**
 * 环境节点类型：与后端 AutoTestConfigNodeType 对齐。
 * 协议值：app/file/database/redis。
 */
export const ENV_TYPE = {
  APP: 'app',
  FILE: 'file',
  DB: 'database',
  REDIS: 'redis',
}

export const ENV_TYPE_OPTIONS = [
  { label: 'APP', value: ENV_TYPE.APP },
  { label: 'FILE', value: ENV_TYPE.FILE },
  { label: 'DB', value: ENV_TYPE.DB },
  { label: 'REDIS', value: ENV_TYPE.REDIS },
]

export const ENV_TYPE_LABEL = {
  [ENV_TYPE.APP]: 'APP',
  [ENV_TYPE.FILE]: 'FILE',
  [ENV_TYPE.DB]: 'DB',
  [ENV_TYPE.REDIS]: 'REDIS',
}

export const ENV_TYPE_TAG = {
  [ENV_TYPE.APP]: 'success',
  [ENV_TYPE.FILE]: 'warning',
  [ENV_TYPE.DB]: 'info',
  [ENV_TYPE.REDIS]: 'error',
}

/** 路由路径中的 app 段对应 APP 类型配置，非枚举值 */
export const CREATE_CONFIG_PERM = {
  [ENV_TYPE.APP]: '/autotest/config/app/create',
  [ENV_TYPE.FILE]: '/autotest/config/file/create',
  [ENV_TYPE.DB]: '/autotest/config/database/create',
  [ENV_TYPE.REDIS]: '/autotest/config/redis/create',
}

export const UPDATE_CONFIG_PERM = {
  [ENV_TYPE.APP]: '/autotest/config/app/update',
  [ENV_TYPE.FILE]: '/autotest/config/file/update',
  [ENV_TYPE.DB]: '/autotest/config/database/update',
  [ENV_TYPE.REDIS]: '/autotest/config/redis/update',
}
