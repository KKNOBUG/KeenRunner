import { ENV_TYPE } from './envType'

/**
 * 环境配置子表展示列（按配置类型）。
 * 操作列由使用方追加。
 *
 * @param {string} type 配置类型：api/file/database/redis
 * @returns {Array} Naive UI DataTable 列定义
 */
export function buildConfigDisplayColumns(type) {
  const cols = [
    { title: '配置名称', key: 'config_name', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 },
  ]
  if (type === ENV_TYPE.DB) {
    cols.push({ title: '数据库名称', key: 'db_name', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
    cols.push({ title: '数据库类型', key: 'db_type', align: 'center', width: 100 })
  }
  cols.push({ title: 'IP地址', key: 'ip', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
  cols.push({ title: '端口', key: 'port', align: 'center', width: 80 })
  cols.push({ title: '备注', key: 'remark', align: 'center', ellipsis: { tooltip: true }, minWidth: 120 })
  cols.push({ title: '维护人员', key: 'maintainer', align: 'center', width: 100, ellipsis: { tooltip: true } })
  cols.push({ title: '维护时间', key: 'updated_time', align: 'center', width: 170, ellipsis: { tooltip: true } })
  return cols
}
