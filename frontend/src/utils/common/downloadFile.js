/**
 * 二进制文件下载通用函数
 *
 * 后端导出接口统一返回xlsx文件流，异常时返回application/json错误体，
 * 此处按响应类型分流：文件流触发浏览器下载，错误体解析message后抛出交由调用方提示
 *
 * 下载走裸axios（不套默认响应拦截器），因此鉴权失效的会话清理必须在此收口
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
                // 保留状态码与业务体，便于handleDownloadError识别鉴权失效
                const error = new Error(body?.message || '下载失败')
                error.response = {status: res?.status, data: body}
                throw error
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

/**
 * 下载失败统一处理：鉴权失效（HTTP 401 / 400401）清理本地会话并跳登录，其余输出可读提示
 * @param err 捕获到的异常（axios错误或downloadBlobResponse抛出的Error）
 * @param fallback 无错误消息时的兜底文案
 */
export async function handleDownloadError(err, fallback = '下载失败') {
        // blob响应下错误体仍是Blob，需先读文本再解析；普通请求则为对象/字符串
        let body = err?.response?.data
        if (body instanceof Blob) {
                try {
                        body = JSON.parse(await body.text())
                } catch {
                        body = null
                }
        } else if (typeof body === 'string') {
                try {
                        body = JSON.parse(body)
                } catch {
                        body = null
                }
        }
        const status = err?.response?.status
        const code = body?.code ?? status
        const unauthorized = status === 401 || code === 401 || code === '401' || code === '400401'
        if (unauthorized) {
                // 动态引入避免utils与store之间的循环依赖
                const { useUserStore } = await import('@/store')
                useUserStore().clearSession()
                window.$message?.error('登录已过期，请重新登录', { keepAliveOnHover: true })
                return
        }
        window.$message?.error(body?.message || err?.message || fallback, { keepAliveOnHover: true })
}
