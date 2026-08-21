import { ref } from 'vue'
import api from '@/api'
import { downloadBlobResponse } from '@/utils/common/downloadFile'

/**
 * 数据源批量上传/下载
 *
 * @param {object} deps
 * @param {import('vue').ComputedRef<string|null>} deps.caseId - 路由 case_id
 * @param {() => Promise<void>} deps.loadSteps - 重载步骤树
 */
export function useDataSourceBatch({ caseId, loadSteps }) {
    const batchUploadFileRef = ref(null)
    const batchUploadLoading = ref(false)
    const summaryDownloadLoading = ref(false)

    const handleBatchUploadDatasource = () => {
        if (!caseId.value) {
            window.$message?.warning?.('请先保存用例后再批量上传数据源')
            return
        }
        batchUploadFileRef.value?.click()
    }

    const onBatchUploadFileChange = async (ev) => {
        const input = ev.target
        const file = input?.files?.[0]
        if (input) input.value = ''
        if (!file) return
        if (!String(file.name || '').toLowerCase().endsWith('.xlsx')) {
            window.$message?.warning?.('仅支持 .xlsx 格式的数据驱动文件')
            return
        }
        if (batchUploadLoading.value) return
        batchUploadLoading.value = true
        try {
            const fd = new FormData()
            fd.append('case_id', String(caseId.value))
            fd.append('file', file)
            const res = await api.batchStepDatasetUpload(fd)
            window.$message?.success?.(res?.message || '批量上传成功')
            await loadSteps()
        } catch {
            // 校验/系统错误提示已由请求拦截器统一弹出
        } finally {
            batchUploadLoading.value = false
        }
    }

    const handleSummaryDownloadDatasource = async () => {
        if (!caseId.value) {
            window.$message?.warning?.('请先保存用例后再下载数据源')
            return
        }
        if (summaryDownloadLoading.value) return
        summaryDownloadLoading.value = true
        try {
            const res = await api.batchStepDatasetDownload({ case_id: caseId.value })
            await downloadBlobResponse(res, '数据源汇总.xlsx')
            window.$message?.success?.('下载成功')
        } catch (e) {
            window.$message?.error?.(e?.message || '下载失败')
        } finally {
            summaryDownloadLoading.value = false
        }
    }

    return {
        batchUploadFileRef,
        batchUploadLoading,
        summaryDownloadLoading,
        handleBatchUploadDatasource,
        onBatchUploadFileChange,
        handleSummaryDownloadDatasource,
    }
}
