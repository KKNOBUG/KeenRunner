import { request } from '@/utils'
import axios from 'axios'
import { getToken } from '@/utils'



/**
 * 前端 API 封装（与后端路由一一对应）。
 */
export default {
  // 登录相关
  login: (data) => request.post('/base/auth/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.post('/base/auth/userinfo'),
  getUserMenu: () => request.post('/base/auth/usermenu'),
  getUserRouters: () => request.post('/base/auth/get_user_routers'),
  // 用户相关
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => {
    const { id, user_id, roles, dept, ...rest } = data
    return request.post('/user/update', { ...rest, user_id: user_id ?? id })
  },
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  /** 批量删除：Body { user_ids?: number[] } */
  deleteUserBatch: (data = {}) => request.post('/user/deletes', data),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  updatePassword: (data = {}) => request.post('/user/update_password', data),
  // 角色相关
  getRoleList: (params = {}) => request.get('/base/role/list', { params }),
  /** 角色分页搜索（支持code/name/description），Body 同后端 RoleSelect */
  searchRoleList: (data = {}) => request.post('/base/role/search', data),
  createRole: (data = {}) => request.post('/base/role/create', data),
  updateRole: (data = {}) => request.post('/base/role/update', data),
  deleteRole: (params = {}) => request.delete('/base/role/delete', { params }),
  /** 批量删除：Body { role_ids?: number[] } 或 { role_codes?: string[] } */
  deleteRoleBatch: (data = {}) => request.post('/base/role/deletes', data),
  updateRoleAuthorized: (data = {}) => request.post('/base/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/base/role/authorized', { params }),
  // 菜单相关
  /** Query 走 URL params（与后端 list_menu 的 Query 一致） */
  getMenus: (params = {}) => request.post('/base/menu/list', {}, { params }),
  createMenu: (data = {}) => request.post('/base/menu/create', data),
  updateMenu: (data = {}) => request.post('/base/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/base/menu/delete', { params }),
  // 路由相关
  getRouters: (params = {}) => request.get('/base/router/list', { params }),
  /** 路由分页搜索（支持method/tags/path/summary），Body 同后端 RouterSelect */
  searchRouterList: (data = {}) => request.post('/base/router/search', data),
  createRouter: (data = {}) => request.post('/base/router/create', data),
  updateRouter: (data = {}) => request.post('/base/router/update', data),
  deleteRouter: (params = {}) => request.delete('/base/router/delete', { params }),
  refreshRouter: (data = {}) => request.post('/base/router/refresh', data),
  // 部门相关
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  /** 部门分页列表（平面数据），Body 同后端 DepartmentSelect */
  searchDeptList: (data = {}) => request.post('/dept/search', { page: 1, page_size: 10, order: ['id'], ...data }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  /** 批量删除：Body { department_ids?: number[] } */
  deleteDeptBatch: (data = {}) => request.post('/dept/deletes', data),
  // 审计相关
  getAuditLogList: (params = {}) => request.get('/base/audit/list', { params }),
  /** 单条审计日志详情（含请求/响应头体大字段）。Query: audit_id */
  getAuditLog: (params = {}) => request.get('/base/audit/get', { params }),
  /** 批量删除：Body { audit_ids?: number[] } */
  deleteAuditLogBatch: (data = {}) => request.post('/base/audit/deletes', data),

  // ---------- autotest：应用 / 环境 / 标签（元数据）----------
  getProject: (params = {}) => request.get('/autotest/project/get', { params }),
  createProject: (data = {}) => request.post('/autotest/project/create', data),
  /** 单笔删除：Query project_id 或 project_code */
  deleteProject: (params = {}) => request.delete('/autotest/project/delete', { params }),
  /** 批量删除：Body { project_ids?: number[] } 或 { project_codes?: string[] } */
  deleteProjectBatch: (data = {}) => request.post('/autotest/project/delete', data),
  updateProject: (data = {}) => request.post('/autotest/project/update', data),
  /** 应用分页搜索（默认大页全量；传入 data 可覆盖 page/page_size/state） */
  getProjectList: (data = {}) => request.post('/autotest/project/search', { page: 1, page_size: 9999, state: 0, ...data }),

  // 环境（主表）
  getEnv: (params = {}) => request.get('/autotest/env/get', { params }),
  createEnv: (data = {}) => request.post('/autotest/env/create', data),
  /** 单笔删除：Query env_id 或 env_code */
  deleteEnv: (params = {}) => request.delete('/autotest/env/delete', { params }),
  /** 批量删除：Body { env_ids?: number[] } 或 { env_codes?: string[] } */
  deleteEnvBatch: (data = {}) => request.post('/autotest/env/deletes', data),
  updateEnv: (data = {}) => request.post('/autotest/env/update', data),
  /** 环境分页搜索（默认大页全量；传入 data 可覆盖 page/page_size/state） */
  getEnvList: (data = {}) => request.post('/autotest/env/search', { page: 1, page_size: 9999, state: 0, ...data }),
  /** 按节点类型/应用聚合环境名称。Body: { project_id?: number[] } */
  listEnvNames: (data = {}) => request.post('/autotest/env/list', data),
  /** 环境分页列表（聚合应用名/是否可删）。Query: project_id/env_name/env_type(api|file|database|redis)/ip/page/page_size；行主键字段为env_id(绑定主键) */
  getEnvPage: (params = {}) => request.get('/autotest/env/page', { params }),
  /** 全部启用应用（环境侧）。Query: page/page_size */
  getAllApps: (params = {}) => request.get('/autotest/env/get_all_app', { params }),

  // 环境配置（子表，按节点类型拆分）
  getEnvConfig: (params = {}) => request.get('/autotest/config/get', { params }),
  /** 新增 API 类型配置。Body: APPEnvConfigCreate */
  createAppEnvConfig: (data = {}) => request.post('/autotest/config/app/create', data),
  /** 新增 FILE 类型配置。Body: FILEEnvConfigCreate */
  createFileEnvConfig: (data = {}) => request.post('/autotest/config/file/create', data),
  /** 新增 DB 类型配置。Body: DBEnvConfigCreate */
  createDbEnvConfig: (data = {}) => request.post('/autotest/config/database/create', data),
  /** 新增 Redis 类型配置。Body: RedisEnvConfigCreate */
  createRedisEnvConfig: (data = {}) => request.post('/autotest/config/redis/create', data),
  /** 更新 API 类型配置。Body: APPEnvConfigUpdate */
  updateAppEnvConfig: (data = {}) => request.post('/autotest/config/app/update', data),
  /** 更新 FILE 类型配置。Body: FILEEnvConfigUpdate */
  updateFileEnvConfig: (data = {}) => request.post('/autotest/config/file/update', data),
  /** 更新 DB 类型配置。Body: DBEnvConfigUpdate */
  updateDbEnvConfig: (data = {}) => request.post('/autotest/config/database/update', data),
  /** 更新 Redis 类型配置。Body: RedisEnvConfigUpdate */
  updateRedisEnvConfig: (data = {}) => request.post('/autotest/config/redis/update', data),
  /** 删除子表配置（单条）。Body: { config_id, env_type(api|file|database|redis), updated_user? } */
  deleteEnvConfig: (data = {}) => request.post('/autotest/config/delete', data),
  /** 子表配置分页搜索（含 project_name/env_name）。Body: AutoTestApiEnvConfigSelect */
  searchEnvConfig: (data = {}) => request.post('/autotest/config/search', { page: 1, page_size: 20, state: 0, ...data }),
  /** 子表配置分页列表。Query: project_id/env_name/env_type(api|file|database|redis)/page/page_size */
  getEnvConfigList: (params = {}) => request.get('/autotest/config/list', { params }),
  /** Query: project_id、env_id、env_type(api|database|redis|file) 可选 */
  getEnvConfigNameList: (params = {}) => request.get('/autotest/config/config_names', { params }),
  /** Body: { project_ids: number[] } -> project_id -> env_name -> api|file|database|redis -> config_name -> {config_host,...} */
  queryEnvConfigClassifiedByProjects: (data = {}) => request.post('/autotest/config/query', data),
  /** 数据库连通性测试。Body: { config_id, project_id, env_name, config_name, database_name } */
  testDbConnection: (data = {}) => request.post('/autotest/config/database/test_connection', data),

  getTag: (params = {}) => request.get('/autotest/tag/get', { params }),
  createTag: (data = {}) => request.post('/autotest/tag/create', data),
  updateTag: (data = {}) => request.post('/autotest/tag/update', data),
  deleteTag: (params = {}) => request.delete('/autotest/tag/delete', { params }),
  /** 批量删除：Body { tag_ids?: number[] } 或 { tag_codes?: string[] } */
  deleteTagBatch: (data = {}) => request.post('/autotest/tag/delete', data),
  /** 标签分页搜索（默认大页全量；传入 data 可覆盖 page/page_size/state） */
  getTagList: (data = {}) => request.post('/autotest/tag/search', { page: 1, page_size: 9999, state: 0, ...data }),

  // 工具箱相关
  generateInfo: (data = {}) => request.post('/toolbox/generate/info', data),

  // ---------- autotest：用例 / 步骤 / 报告 / 任务 ----------
  getApiTestcaseList: (data = {}) => request.post('/autotest/case/search', data),
  createApiTestcaseList: (data = {}) => request.post('/autotest/case/create', data),
  updateApiTestcaseList: (data = {}) => request.post('/autotest/case/update', data),
  deleteApiTestcaseList: (params = {}) => {
    const q = []
    if (params.case_id != null) q.push(`case_id=${params.case_id}`)
    if (params.case_code != null) q.push(`case_code=${encodeURIComponent(params.case_code)}`)
    return request.delete(`/autotest/case/delete${q.length ? '?' + q.join('&') : ''}`)
  },
  /** Body：{ case_ids } —— 同步导出公共接口用例请求头与请求体为 xlsx（≤10），返回 blob；校验失败时返回 JSON */
  exportTestcasesXlsx: (data = {}) => axios.post(
      `${import.meta.env.VITE_BASE_API}/autotest/case/export_case_datagram_sync`,
      data,
      {
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** Body：{ case_ids } —— 异步导出公共接口用例（>10），返回 { celery_task_id } */
  exportTestcasesAsync: (data = {}) => request.post('/autotest/case/export_case_datagram_async', data),
  /** Body：{ case_ids } —— 同步导出公共接口脚本为模板xlsx（≤10），返回 blob；校验失败时返回 JSON */
  exportCaseScriptsXlsx: (data = {}) => axios.post(
      `${import.meta.env.VITE_BASE_API}/autotest/case/export_case_scripts_sync`,
      data,
      {
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** Body：{ case_ids } —— 异步导出公共接口脚本（>10），返回 { celery_task_id } */
  exportCaseScriptsAsync: (data = {}) => request.post('/autotest/case/export_case_scripts_async', data),
  /** FormData：file —— 导入公共接口脚本（模板xlsx：按应用+接口名称匹配，存在更新/不存在新增） */
  importCaseScript: (formData) => request.post('/autotest/case/import_case_scripts', formData),
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
  updateOrCreateStepTree: (data = {}) => request.post('/autotest/step/update_or_create_tree', data),
  httpRequestDebugging: (data = {}) => request.post('/autotest/step/http_debugging', data),
  tcpRequestDebugging: (data = {}) => request.post('/autotest/step/tcp_debugging', data),
  pythonCodeDebugging: (data = {}) => request.post('/autotest/step/python_code_debugging', data),
  redisRequestDebugging: (data = {}) => request.post('/autotest/step/redis_debugging', data),
  executeStepTree: (data = {}) => request.post('/autotest/step/execute_or_debugging', data),
  // 报告相关
  getApiReportList: (data = {}) => request.post('/autotest/report/search', data),
  /** 任务执行历史：按 batch_code 聚合，含 execute_result */
  getApiReportBatches: (data = {}) => request.post('/autotest/report/search_batches', data),
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
  /** params：record_id、key —— 下载执行记录附件（blob） */
  downloadApiTaskRecordAttachment: (recordId, key = 'main') => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/task/record/${recordId}/attachments/${encodeURIComponent(key)}/download`,
      {
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  // 辅助函数列表（用户变量/占位符解析）
  getAssistFuncList: (params = {}) => request.get('/autotest/tool/get', { params }),
  // 环境相关：查询环境名称列表(去重)，用于执行/调试时选择执行环境
  getApiEnvNames: () => request.get('/autotest/env/get_names'),

  // 数据源（HTTP/TCP 请求步骤）
  getDataSource: (params = {}) => request.get('/autotest/data_source/get', { params }),
  getDataSourceByCaseStep: (params = {}) => request.get('/autotest/data_source/get_by_case_step', { params }),
  getSceneNamesByCase: (params = {}) => request.get('/autotest/data_source/scene_names_by_case', { params }),
  /** Form：case_id */
  queryDatasetNames: (formData) => request.post('/autotest/data_source/query_dataset_names', formData),
  updateDataSource: (data = {}) => request.post('/autotest/data_source/update', data),
  saveOrUpdateDataSource: (data = {}) => request.post('/autotest/data_source/save_or_update', data),
  /** FormData：case_id、step_id、step_code、file_desc?、file —— 单步骤数据源上传 */
  singleStepDatasetUpload: (formData) => request.post('/autotest/data_source/single_step_dataset_upload', formData),
  /** params：case_id、step_id、step_code —— 单步骤数据源下载（blob） */
  singleStepDatasetDownload: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/data_source/single_step_dataset_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** Body：{ case_id } —— 解绑用例全部数据源（软删记录并清空步骤指针），公共家族(脚本/接口)保存时调用 */
  unbindCaseDataSource: (data = {}) => request.post('/autotest/data_source/unbind_case', data),
  /** FormData：case_id、file —— 多步骤数据源批量上传（sheet 名对应步骤名） */
  batchStepDatasetUpload: (formData) => request.post('/autotest/data_source/batch_step_dataset_upload', formData),
  /** params：case_id —— 汇总下载用例所有步骤数据源（blob） */
  batchStepDatasetDownload: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/data_source/batch_step_dataset_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  downloadHttpStepDatasetImportTemplate: () => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/data_source/import_template_download`,
      {
        responseType: 'blob',
        headers: {
          token: getToken() || '',
        },
      },
  ),
}
