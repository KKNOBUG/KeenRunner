import { getToken } from '@/utils'
import { resolveResError } from './helpers'
import { useUserStore } from '@/store'

/**
 * 请求拦截器：在请求发送之前对请求配置进行处理
 * @param {Object} config - 请求配置对象，包含请求的各种信息，如 URL、方法、头信息等
 * @returns {Object} - 处理后的请求配置对象
 */
export function reqResolve(config) {
  // 处理不需要token的请求，如果配置中 noNeedToken 为 true，则直接返回原始配置
  if (config.noNeedToken) {
    return config
  }
  // 从工具函数中获取 token
  const token = getToken()
  // 如果获取到了 token，则将其添加到请求头中，如果请求头中已经有 token 则不覆盖
  if (token) {
    config.headers.token = config.headers.token || token
  }
  // 返回处理后的请求配置
  return config
}

/**
 * 请求拦截器：当请求发生错误时进行处理
 * @param {Error} error - 请求过程中抛出的错误对象
 * @returns {Promise<Error>} - 拒绝的 Promise，携带错误信息
 */
export function reqReject(error) {
  // 直接拒绝 Promise，将错误信息传递下去
  return Promise.reject(error)
}

/**
 * 响应拦截器：在响应成功返回时对响应数据进行处理
 * @param {Object} response - 响应对象，包含响应的状态码、头信息、数据等
 * @returns {Promise<Object>} - 根据响应数据的状态，返回成功或拒绝的 Promise
 */
export function resResolve(response) {
  // 从响应对象中解构出数据、状态码和状态文本
  const { data, status, statusText } = response

  // 检查响应数据是否存在
  if (!data) {
    const code = status
    const message = resolveResError(code, statusText || '响应数据为空')
    window.$message?.error(message, { keepAliveOnHover: true })
    return Promise.reject({ code, message, error: response })
  }

  // 将 code 转换为字符串进行比较，以处理可能的类型不匹配问题（数字 vs 字符串）
  const responseCode = String(data.code || '')
  const responseStatus = String(data.status || '')

  // 检查响应数据的 code 和 status 字段是否符合成功条件
  // 成功条件：code 必须是 '000000' 且 status 必须是 'success'
  const isSuccess = responseCode === '000000' && responseStatus === 'success'

  if (!isSuccess) {
    // 如果不符合成功条件，获取错误码，优先使用响应数据中的 code，若不存在则使用状态码
    const code = data.code ?? status
    /** 根据code处理对应的操作，并返回处理后的message */
        // 调用 resolveResError 函数处理错误信息
    const message = resolveResError(code, data.message ?? statusText ?? '请求失败')
    // 使用 window.$message 显示错误消息，并设置鼠标悬停时不自动关闭
    window.$message?.error(message, { keepAliveOnHover: true })
    // 拒绝 Promise，携带错误码、错误消息和错误数据
    return Promise.reject({ code, message, error: data || response })
  }

  // 如果响应数据符合成功条件，返回成功的 Promise，携带响应数据
  return Promise.resolve(data)
}

/**
 * 响应拦截器：当响应发生错误时进行处理
 * @param {Object} error - 响应错误对象，包含错误信息和响应信息
 * @returns {Promise<Object>} - 拒绝的 Promise，携带错误码、错误消息和错误数据
 */
export async function resReject(error) {
  // 检查错误对象是否存在或是否包含响应信息
  if (!error || !error.response) {
    // 如果不存在响应信息，获取错误码
    const code = error?.code
    /** 根据code处理对应的操作，并返回处理后的message */
        // 调用 resolveResError 函数处理错误信息
    const message = resolveResError(code, error.message)
    // 使用 window.$message 显示错误消息
    window.$message?.error(message)
    // 拒绝 Promise，携带错误码、错误消息和错误对象
    return Promise.reject({ code, message, error })
  }
  // 从错误对象的响应中解构出数据和状态码
  const { data, status } = error.response

  // 检查响应数据的 code 是否为 401，表示未授权（支持字符串和数字类型）
  const responseCode = data?.code
  if (responseCode === 401 || responseCode === '400401' || String(responseCode) === '401') {
    try {
      // 获取用户状态管理 store
      const userStore = useUserStore()
      // 调用 store 中的登出方法
      await userStore.logout()
    } catch (error) {
      // 捕获登出过程中可能出现的错误并打印日志
      console.log('resReject error', error)
      return
    }
  }

  // 后端返回的response数据，获取错误码，优先使用响应数据中的 code，若不存在则使用状态码
  const code = data?.code ?? status
  // 调用 resolveResError 函数处理错误信息
  const message = resolveResError(code, data?.message ?? error.message ?? '请求失败')
  // 使用 window.$message 显示错误消息，并设置鼠标悬停时不自动关闭
  window.$message?.error(message, { keepAliveOnHover: true })
  // 拒绝 Promise，携带错误码、错误消息和错误响应数据
  return Promise.reject({ code, message, error: error.response?.data || error.response })
}
