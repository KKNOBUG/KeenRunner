import { useUserStore } from '@/store'

export function addBaseParams(params) {
  if (!params.userId) {
    params.userId = useUserStore().userId
  }
}

export function resolveResError(code, message) {
  // 将 code 转换为字符串，以便统一处理数字和字符串类型的错误码
  const codeStr = String(code || '')

  // 如果已经有消息，优先使用传入的消息
  if (message) {
    return message
  }

  // 处理 HTTP 状态码（数字类型）
  switch (Number(code)) {
    case 400:
      return '请求参数错误'
    case 401:
      return '登录已过期'
    case 403:
      return '没有权限'
    case 404:
      return '资源或接口不存在'
    case 500:
      return '服务器异常'
    default:
      break
  }

  // 处理后端业务错误码（字符串类型，如 '000000', '999999', '400400' 等）
  // 如果 code 是 '000000'，理论上不应该进入这里，但为了安全起见还是处理一下
  if (codeStr === '000000') {
    return '请求成功'
  }

  // 根据错误码前缀判断错误类型
  if (codeStr.startsWith('400')) {
    if (codeStr === '400400') return '请求参数验证失败'
    if (codeStr === '400401') return '请求服务鉴权失败'
    if (codeStr === '400403') return '请求服务不被接受'
    if (codeStr === '400404') return '请求资源不可访达'
    if (codeStr === '400405') return '请求方式不可访达'
    if (codeStr === '400408') return '请求服务等待超时'
    if (codeStr === '400429') return '请求速度不被允许'
    return '请求错误'
  }

  if (codeStr.startsWith('500')) {
    if (codeStr === '500500') return '服务器遇到错误无法完成请求'
    if (codeStr === '500502') return '服务器从上游网关收到无效响应'
    if (codeStr === '500504') return '服务器等待上游网关响应超时'
    return '服务器异常'
  }

  if (codeStr === '999999') {
    return '请求失败'
  }

  // 默认返回错误码和未知异常
  return `【${code}】: 未知异常!`
}
