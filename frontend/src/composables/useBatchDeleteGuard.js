import {useUserStore} from '@/store'

/**
 * 批量删除的行级守卫。
 *
 * 后端列表行已注入 can_delete（按当前资源族的删除范围判定，含部门范围），
 * 前端先按该结论过滤掉不可删的行，避免整批请求必然失败；
 * 跨页勾选无法在本地确认归属，将提示用户分页处理。
 */
export function useBatchDeleteGuard() {
  const userStore = useUserStore()

  /**
   * 过滤出当前用户可删除的主键列表，并对被跳过的行给出提示。
   *
   * @param {Object} options 过滤参数
   * @param {Array<number|string>} options.ids 勾选的主键列表
   * @param {Array<Object>} options.rows 当前页表格数据
   * @param {string} options.keyField 主键字段名
   * @param {string} [options.ownerField] 归属人字段名，用例为 owner_user
   * @param {string} [options.label] 数据中文名，用于提示文案
   * @returns {Array<number|string>} 可删除的主键列表
   */
  function pickDeletableIds({ids, rows, keyField, ownerField = 'created_user', label = '记录'}) {
    const rowMap = new Map((rows || []).map((row) => [row[keyField], row]))
    const deletableIds = []
    let otherOwners = 0
    let unknownRows = 0
    ;(ids || []).forEach((id) => {
      const row = rowMap.get(id)
      if (!row) {
        unknownRows += 1
        return
      }
      if (userStore.canDeleteData(row[ownerField], row.can_delete)) {
        deletableIds.push(id)
      } else {
        otherOwners += 1
      }
    })
    if (otherOwners) {
      window.$message?.warning?.(`已过滤 ${otherOwners} 条不在当前角色可删范围的${label}`)
    }
    if (unknownRows) {
      window.$message?.warning?.(`已忽略 ${unknownRows} 条不在当前页的${label}，请分页删除`)
    }
    return deletableIds
  }

  return {pickDeletableIds}
}