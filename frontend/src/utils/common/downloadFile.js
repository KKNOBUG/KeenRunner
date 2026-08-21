/**
 * 二进制文件下载通用函数
 *
 * 后端导出接口统一返回xlsx文件流，异常时返回application/json错误体，
 * 此处按响应类型分流：文件流触发浏览器下载，错误体解析message后抛出交由调用方提示
 */

/**
 * 将axios的blob响应保存为文件并触发浏览器下载
 * @param res axios响应对象(需responseType: blob)
 * @param fallbackName Content-Disposition缺失时的兜底文件名
 */
export async function downloadBlobResponse(res, fallbackName) {
        const contentType = res?.headers?.['content-type'] || ''
        if (contentType.includes('application/json')) {
                const body = JSON.parse(await res.data.text())
                throw new Error(body?.message || '下载失败')
        }
        const blob = new Blob([res.data], {type: contentType || 'application/octet-stream'})
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        // 文件名以Content-Disposition的filename*=UTF-8''编码段为准
        const disposition = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
        const matched = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
        link.download = matched?.[1] ? decodeURIComponent(matched[1]) : fallbackName
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
}
