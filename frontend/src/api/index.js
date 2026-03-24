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

  // 应用管理（autotest 应用/环境/标签）
  getProject: (params = {}) => request.get('/autotest/project/get', { params }),
  createProject: (data = {}) => request.post('/autotest/project/create', data),
  deleteProject: (params = {}) => request.post('/autotest/project/delete', {}, { params }),
  updateProject: (data = {}) => request.post('/autotest/project/update', data),
  getProjectList: (data = {}) => request.post('/autotest/project/search', { page: 1, page_size: 9999, state: 0, ...data }),

  getEnv: (params = {}) => request.get('/autotest/env/get', { params }),
  createEnv: (data = {}) => request.post('/autotest/env/create', data),
  deleteEnv: (params = {}) => request.delete('/autotest/env/delete', { params }),
  updateEnv: (data = {}) => request.post('/autotest/env/update', data),
  getEnvList: (data = {}) => request.post('/autotest/env/search', { page: 1, page_size: 9999, state: 0, ...data }),

  getTag: (params = {}) => request.get('/autotest/tag/get', { params }),
  createTag: (data = {}) => request.post('/autotest/tag/create', data),
  updateTag: (data = {}) => request.post('/autotest/tag/update', data),
  deleteTag: (params = {}) => request.delete('/autotest/tag/delete', { params }),
  getTagList: (data = {}) => request.post('/autotest/tag/search', { page: 1, page_size: 9999, state: 0, ...data }),


  // 工具箱相关
  runcodePython: (data = {}) => request.post('/toolbox/runcode/python', data),
  generateInfo: (data = {}) => request.post('/toolbox/generate/info', data),

  // 自动化测试相关
  getApiTestcaseList: (data = {}) => request.post('/autotest/case/search', data),
  createApiTestcaseList: (data = {}) => request.post('/autotest/case/create', data),
  updateApiTestcaseList: (data = {}) => request.post('/autotest/case/update', data),
  deleteApiTestcaseList: (params = {}) => {
    const q = []
    if (params.case_id != null) q.push(`case_id=${params.case_id}`)
    if (params.case_code != null) q.push(`case_code=${encodeURIComponent(params.case_code)}`)
    return request.delete(`/autotest/case/delete${q.length ? '?' + q.join('&') : ''}`)
  },
  getAutoTestStepTree: (data = {}) => {
    const params = []
    if (data.case_id) params.push(`case_id=${data.case_id}`)
    if (data.case_code) params.push(`case_code=${data.case_code}`)
    return request.get(`/autotest/step/tree${params.length ? '?' + params.join('&') : ''}`)
  },
  /**
   * 复制用例步骤树（返回未保存的副本，不含 step_id/step_code 等更新必填项）
   * 后端接口：GET /autotest/step/copy_tree?case_id=X 或 ?case_code=X
   *
   * 返回 { case, steps }：
   *   - case: 来自原用例，case_id/case_code 已置空，表示未持久化
   *   - steps: 对 get_by_case_id 结果做 strip 后的步骤树（移除 step_id、step_code、parent_step_id 等）
   *
   * 前端使用场景（同一接口，两种用法）：
   *   1. 用例管理「复制」：使用 case + steps，创建新用例编辑页（路由跳转）
   *   2. 步骤明细「复制指定脚本」：仅使用 steps，将步骤插入当前用例的步骤树
   */
  copyCaseStepTree: (params = {}) => {
    const q = []
    if (params.case_id != null) q.push(`case_id=${params.case_id}`)
    if (params.case_code != null) q.push(`case_code=${encodeURIComponent(params.case_code)}`)
    return request.get(`/autotest/step/copy_tree${q.length ? '?' + q.join('&') : ''}`)
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
  // 环境相关：查询环境名称列表(去重)，用于执行/调试时选择执行环境
  getApiEnvNames: () => request.get('/autotest/env/get_names'),

  // 数据源（HTTP 步骤）
  getDataSourceByCaseStep: (params = {}) => request.get('/autotest/data_source/get_by_case_step', { params }),
  uploadSingleStepDataset: (formData) => request.post('/autotest/data_source/single_step_dataset_upload', formData),

}
