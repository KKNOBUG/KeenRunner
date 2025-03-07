import { request } from '@/utils'



export default {
  // 登录相关
  login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.post('/base/auth/userinfo'),
  getUserMenu: () => request.post('/base/auth/usermenu'),
  getUserRouters: () => request.post('/base/auth/getUserRouters'),
  // 用户相关
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  updatePassword: (data = {}) => request.post('/user/update_password', data),
  // 角色相关
  getRoleList: (params = {}) => request.get('/base/role/list', { params }),
  createRole: (data = {}) => request.post('/base/role/create', data),
  updateRole: (data = {}) => request.post('/base/role/update', data),
  deleteRole: (params = {}) => request.delete('/base/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/base/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/base/role/authorized', { params }),
  // 菜单相关
  getMenus: (params = {}) => request.post('/base/menu/list', { params }),
  createMenu: (data = {}) => request.post('/base/menu/create', data),
  updateMenu: (data = {}) => request.post('/base/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/base/menu/delete', { params }),
  // API相关
  getRouters: (params = {}) => request.get('/base/router/list', { params }),
  createRouter: (data = {}) => request.post('/base/router/create', data),
  updateRouter: (data = {}) => request.post('/base/router/update', data),
  deleteRouter: (params = {}) => request.delete('/base/router/delete', { params }),
  refreshRouter: (data = {}) => request.post('/base/router/refresh', data),
  // 部门相关
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // 审计相关
  getAuditLogList: (params = {}) => request.get('/base/audit/list', { params }),

  // 工具箱相关
  runPyCode: (data = {}) => request.post('/toolbox/runcode/python', data),
  fakerPerson: (data = {}) => request.post('/toolbox/generate/person', data),
}
