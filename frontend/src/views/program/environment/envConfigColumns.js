import { ENV_TYPE } from './envType'

/**
 * 环境配置子表展示列（字段名与后端表对齐）。
 * 操作列由使用方追加。
 *
 * @param {string} type 配置类型：app/file/database/redis
 * @returns {Array} Naive UI DataTable 列定义
 */
export function buildConfigDisplayColumns(type) {
  const cols = [
    { title: '配置名称', key: 'config_name', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 },
  ]
  if (type === ENV_TYPE.DB) {
    cols.push({ title: '数据库名称', key: 'database_name', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
    cols.push({ title: '数据库类型', key: 'database_type', align: 'center', width: 100 })
  }
  if (type === ENV_TYPE.REDIS) {
    cols.push({ title: '库编号', key: 'database_name', align: 'center', width: 90 })
  }
  cols.push({ title: '主机地址', key: 'config_host', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
  cols.push({ title: '端口', key: 'config_port', align: 'center', width: 80 })
  cols.push({ title: '备注', key: 'config_desc', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
  cols.push({ title: '维护人员', key: 'updated_user', align: 'center', width: 100, ellipsis: { tooltip: true } })
  cols.push({ title: '维护时间', key: 'updated_time', align: 'center', width: 170, ellipsis: { tooltip: true } })
  return cols
}
