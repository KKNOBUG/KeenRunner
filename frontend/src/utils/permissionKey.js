/**
 * RBAC 权限键与后端 getUserRouters 一致：method 小写 + 真实路径（无网关前缀）。
 * 前端比对时在 method 与 path 之间拼接 VITE_BASE_API（如 /api、/api/v1），与浏览器实际请求前缀一致。
 */
export function apiPermissionKey(method, path) {
  const m = String(method || '').toLowerCase().trim()
  let p = String(path || '').trim()
  if (!p.startsWith('/')) p = `/${p}`
  const base = (import.meta.env.VITE_BASE_API || '').replace(/\/$/, '')
  return `${m}${base}${p}`
}

/**
 * 将后端下发的键（如 post/autotest/case/create）转为与 apiPermissionKey 相同规则的比对键。
 */
export function normalizeBackendApiPermissionKey(backendKey) {
  if (typeof backendKey !== 'string') return backendKey
  const m = backendKey.match(/^([a-z]+)(\/.*)$/)
  if (!m) return backendKey
  return apiPermissionKey(m[1], m[2])
}
