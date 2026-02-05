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
  getAutoTestStepTree: (data = {}) => {
    const params = []
    if (data.case_id) params.push(`case_id=${data.case_id}`)
    if (data.case_code) params.push(`case_code=${data.case_code}`)
    console.log(data.case_id)
    console.log(data.case_code)
    return request.get(`/autotest/step/tree${params.length ? '?' + params.join('&') : ''}`, data)
  },
  // 项目相关
  getApiProjectList: (data = {}) => request.post('/autotest/project/search', data),
  // 标签相关
  getApiTagList: (data = {}) => request.post('/autotest/tag/search', data),
  updateOrCreateStepTree: (data = {}) => request.post('/autotest/step/update_or_create_tree', data),
  httpRequestDebugging: (data = {}) => request.post('/autotest/step/http_debugging', data),
  pythonCodeDebugging: (data = {}) => request.post('/autotest/step/python_code_debugging', data),
  executeStepTree: (data = {}) => request.post('/autotest/step/execute_or_debugging', data),
  // 报告相关
  getApiReportList: (data = {}) => request.post('/autotest/report/search', data),
  deleteApiReport: (params = {}) => {
    const queryParams = []
    if (params.report_id) queryParams.push(`report_id=${params.report_id}`)
    if (params.report_code) queryParams.push(`report_code=${params.report_code}`)
    return request.delete(`/autotest/report/delete${queryParams.length ? '?' + queryParams.join('&') : ''}`)
  },
  getApiReport: (params = {}) => {
    const queryParams = []
    if (params.report_id) queryParams.push(`report_id=${params.report_id}`)
    if (params.report_code) queryParams.push(`report_code=${params.report_code}`)
    return request.get(`/autotest/report/get${queryParams.length ? '?' + queryParams.join('&') : ''}`)
  },
  // 明细相关
  getApiDetailList: (data = {}) => request.post('/autotest/detail/search', data),

  // 任务相关
  getApiTaskList: (data = {}) => request.post('/autotest/task/search', data),
  getApiTask: (params = {}) => request.get('/autotest/task/get', { params }),
  createApiTaskList: (data = {}) => request.post('/autotest/task/create', data),
  updateApiTaskList: (data = {}) => request.post('/autotest/task/update', data),
  deleteApiTaskList: (data = {}) => {
    const q = []
    if (data.task_id != null) q.push(`task_id=${data.task_id}`)
    if (data.task_code != null) q.push(`task_code=${encodeURIComponent(data.task_code)}`)
    return request.delete(`/autotest/task/delete${q.length ? '?' + q.join('&') : ''}`)
  },
  // 立即执行任务（下发 Celery）
  runApiTask: (data = {}) => request.post('/autotest/task/run', data),
  // 启动任务（启用调度，task_enabled=true）
  startApiTask: (data = {}) => request.post('/autotest/task/start', data),
  // 停止任务（关闭调度，task_enabled=false）
  stopApiTask: (data = {}) => request.post('/autotest/task/stop', data),
  // 任务执行记录
  getApiTaskRecordList: (data = {}) => request.post('/autotest/task/record/search', data),
  // 辅助函数列表（用户变量/占位符解析）
  getAssistFuncList: (params = {}) => request.get('/autotest/tool/get', { params }),
}
