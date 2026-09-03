import { ref } from 'vue'
import api from '@/api'

/**
 * 任务列表「执行记录」弹框：按任务分页加载执行记录（/autotest/task/record/search）
 * @returns 执行记录弹框状态与操作（openLog / 分页回调供模板直接绑定）
 */
export function useTaskRecordLogModal() {
  const logModalVisible = ref(false)
  const logTaskName = ref('')
  const logTaskId = ref(null)
  const logRecordList = ref([])
  const logRecordLoading = ref(false)
  const logPage = ref(1)
  const logPageSize = ref(10)
  const logTotal = ref(0)

  const loadLogRecords = async () => {
    const id = logTaskId.value
    if (id == null) return
    logRecordLoading.value = true
    try {
      const res = await api.getApiTaskRecordList({
        task_id: id,
        page: logPage.value,
        page_size: logPageSize.value,
        order: ['-celery_start_time', '-id']
      })
      logRecordList.value = res?.data ?? []
      logTotal.value = res?.total ?? 0
    } catch (e) {
      window.$message?.error?.(e?.message || e?.data?.message || '加载执行记录失败')
    } finally {
      logRecordLoading.value = false
    }
  }

  /** 打开指定任务的执行记录弹框（重置到第一页） */
  const openLog = async (row) => {
    logTaskName.value = row.task_name ?? ''
    logTaskId.value = row.task_id
    logPage.value = 1
    logModalVisible.value = true
    await loadLogRecords()
  }

  const onLogPageChange = (page) => {
    logPage.value = page
    loadLogRecords()
  }

  const onLogPageSizeChange = (pageSize) => {
    logPageSize.value = pageSize
    logPage.value = 1
    loadLogRecords()
  }

  return {
    logModalVisible,
    logTaskName,
    logRecordList,
    logRecordLoading,
    logPage,
    logPageSize,
    logTotal,
    openLog,
    onLogPageChange,
    onLogPageSizeChange,
  }
}
