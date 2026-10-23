/**
 * 数据源面板卸载静默保存的在途登记。
 *
 * 切换步骤时面板卸载会静默保存旧步骤数据源（发后即忘）；页面保存步骤树前必须等待
 * 全部在途保存落库，否则树接口的数据源场景列一致性校验读到旧值会产生误判放行。
 */
const pendingSaves = new Set()

/** 登记一个在途保存Promise，落库或失败后自动移除；原样返回promise保持调用方语义 */
export function trackDataSourceSave(savePromise) {
  pendingSaves.add(savePromise)
  const settle = () => pendingSaves.delete(savePromise)
  savePromise.then(settle, settle)
  return savePromise
}

/** 等待全部在途静默保存结束（含等待期间新登记的），错误已由http拦截器统一提示，此处只做汇合 */
export async function awaitPendingDataSourceSaves() {
  while (pendingSaves.size > 0) {
    await Promise.allSettled([...pendingSaves])
  }
}
