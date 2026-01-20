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
  // 路由相关
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

  // 应用管理相关
  getProject: (params = {}) => request.get('/program/project/get', { params }),
  createProject: (data = {}) => request.post('/program/project/create', data),
  deleteProject: (params = {}) => request.delete('/program/project/delete', { params }),
  updateProject: (data = {}) => request.post('/program/project/update', data),
  getProjectList: (params = {}) => request.get('/program/project/list', { params }),

  getModule: (params = {}) => request.get('/program/module/get', { params }),
  createModule: (data = {}) => request.post('/program/module/create', data),
  deleteModule: (params = {}) => request.delete('/program/module/delete', { params }),
  updateModule: (data = {}) => request.post('/program/module/update', data),
  getModuleList: (params = {}) => request.get('/program/module/list', { params }),

  getEnv: (params = {}) => request.get('/program/env/get', { params }),
  createEnv: (data = {}) => request.post('/program/env/create', data),
  deleteEnv: (params = {}) => request.delete('/program/env/delete', { params }),
  updateEnv: (data = {}) => request.post('/program/env/update', data),
  getEnvList: (params = {}) => request.get('/program/env/list', { params }),


  // 工具箱相关
  runcodePython: (data = {}) => request.post('/toolbox/runcode/python', data),
  generateInfo: (data = {}) => request.post('/toolbox/generate/info', data),

  // 测试用例相关
  updateOrCreate: (data = {}) => request.post('/testcase/api/updateOrCreate', data),
  debugging: (data = {}) => request.post('/testcase/api/debugging', data),

  // 自动化测试相关
  getApiTestcaseList: (data = {}) => request.post('/autotest/case/search', data),
  createApiTestcaseList: (data = {}) => request.post('/autotest/case/create', data),
  updateApiTestcaseList: (data = {}) => request.post('/autotest/case/update', data),
  deleteApiTestcaseList: (data = {}) => request.delete(`/autotest/case/delete?case_id=${data.case_id}`, data),
  // getStepTree: (data = {}) => request.get(`/autotest/step/tree?case_id=${data.case_id}`, data),
  getStepTree: (data = {}) => {
    const params = []
    if (data.case_id) params.push(`case_id=${data.case_id}`)
    if (data.case_code) params.push(`case_code=${data.case_code}`)
    console.log(data.case_id)
    console.log(data.case_code)
    return request.get(`/autotest/step/tree${params.length ? '?' + params.join('&') : ''}`, data)
  },
  updateStepTree: (data = {}) => request.post('/autotest/step/update/tree', data),
  httpRequestDebugging: (data = {}) => request.post('/autotest/step/http/debugging', data),
  executeStepTree: (data = {}) => request.post('/autotest/step/execute', data),
}
