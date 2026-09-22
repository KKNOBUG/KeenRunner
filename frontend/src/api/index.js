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
  /** 环境分页列表（聚合应用名/是否可删）。Body: project_id/env_name/env_type/ip/config_name + 分页 */
  getEnvPage: (data = {}) => request.post('/autotest/env/page', data),
  /** Body: { project_ids: number[] } -> project_id -> env_name -> api|file|database|redis -> config_name -> {config_host,...} */
  queryEnvConfigClassifiedByProjects: (data = {}) => request.post('/autotest/env/query', data),
  /** 全部启用应用（环境侧）。Query: page/page_size */
  getAllApps: (params = {}) => request.get('/autotest/env/get_all_app', { params }),

  // 环境配置（子表，挂载于绑定；project_id/env_type由绑定派生）
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
  /** 删除子表配置（单条）。Body: { config_id, env_type(app|file|database|redis), updated_user? } */
  deleteEnvConfig: (data = {}) => request.post('/autotest/config/delete', data),
  /** 子表配置分页搜索（含 project_name/env_name）。Body: AutoTestApiEnvConfigSelect */
  searchEnvConfig: (data = {}) => request.post('/autotest/config/search', { page: 1, page_size: 20, state: 0, ...data }),
  /** 子表配置分页列表。Query: project_id/env_name/env_type(app|file|database|redis)/page/page_size */
  getEnvConfigList: (params = {}) => request.get('/autotest/config/list', { params }),
  /** Query: project_id、env_id(绑定主键)、env_type 可选 */
  getEnvConfigNameList: (params = {}) => request.get('/autotest/config/config_names', { params }),
  /** 按应用/配置名称/节点类型查询环境名称列表。Body: { project_id?, config_name?, env_type? } */
  queryAssignConfigEnvs: (data = {}) => request.post('/autotest/config/query_assign_config_envs', data),
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
  /** Body：{ case_ids } —— 导出公共接口用例请求头/体报文为 xlsx(统一异步)，返回 { celery_task_id } */
  exportTestcasesAsync: (data = {}) => request.post('/autotest/case/export_case_datagram_async', data),
  /** Body：{ case_ids } —— 导出公共接口脚本模板为 xlsx(统一异步)，返回 { celery_task_id } */
  exportCaseScriptsAsync: (data = {}) => request.post('/autotest/case/export_case_scripts_async', data),
  /** Body：{ case_ids, case_project, case_type, case_attr, case_tags } —— 公共接口转脚本生成(统一异步，每个接口生成独立脚本)，返回 { celery_task_id } */
  generateCaseScriptsAsync: (data = {}) => request.post('/autotest/case/generate_case_scripts_async', data),
  /** FormData：file —— 导入公共接口脚本（模板xlsx：按应用+接口名称匹配，存在更新/不存在新增；统一异步），返回 { celery_task_id } */
  importCaseScriptsAsync: (formData) => request.post('/autotest/case/import_case_scripts_async', formData),
  getAutoTestStepTree: (data = {}) => {
    const params = []
    if (data.case_id) params.push(`case_id=${data.case_id}`)
    if (data.case_code) params.push(`case_code=${data.case_code}`)
    return request.get(`/autotest/step/tree${params.length ? '?' + params.join('&') : ''}`)
  },
  /** Body: { case_ids?: number[], case_codes?: string[] } —— 批量查询多用例步骤树并拼接为一个列表 */
  spliceStepTree: (data = {}) => request.post('/autotest/step/splice_tree', data),
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
  /** 批次执行报告列表：按 batch_code 精确分页查询同批次全部数据源报告 */
  getApiReportBatchReports: (data = {}) => request.post('/autotest/report/search_batch_reports', data),
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
  getApiDetailTree: (data = {}) => request.post('/autotest/detail/tree', data),
  getApiDetail: (params = {}) => {
    const queryParams = []
    if (params.detail_id) queryParams.push(`detail_id=${params.detail_id}`)
    return request.get(`/autotest/detail/get${queryParams.length ? '?' + queryParams.join('&') : ''}`)
  },

  // 任务相关
  getApiTaskList: (data = {}) => request.post('/autotest/task/search', data),
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
  /** Body：{ task_id } —— 复制任务(完全复刻配置, 重置执行痕迹并停用调度) */
  copyApiTask: (data = {}) => request.post('/autotest/task/copy', data),
  // 定时执行预览（近10次触发时间）
  previewTaskSchedule: (data = {}) => request.post('/autotest/task/schedule_preview', data),
  // 任务执行记录
  getApiTaskRecordList: (data = {}) => request.post('/autotest/task/record/search', data),
  /** params：record_id —— 删除终态执行记录并物理清理产物文件 */
  deleteApiTaskRecord: (recordId) => request.delete(`/autotest/task/record/delete?record_id=${recordId}`),
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
  // 内置环境变量列表（HTTP/TCP请求步骤「关联数据」提示，后端为唯一数据源）
  getBuiltinVariableList: () => request.get('/autotest/tool/builtin_variables'),
  // 环境相关：查询环境名称列表(去重)，用于执行/调试时选择执行环境
  getApiEnvNames: () => request.get('/autotest/env/get_names'),

  // 数据源（HTTP/TCP 请求步骤）
  getDataSource: (params = {}) => request.get('/autotest/data_source/get', { params }),
  getDataSourceByCaseStep: (params = {}) => request.get('/autotest/data_source/get_by_case_step', { params }),
  getSceneNamesByCase: (params = {}) => request.get('/autotest/data_source/scene_names_by_case', { params }),
  /** Form：case_id */
  queryDatasetNames: (formData) => request.post('/autotest/data_source/query_dataset_names', formData),
  updateDataSource: (data = {}) => request.post('/autotest/data_source/update', data),
  /** Query：data_source_id/code 或 (case_id|case_code)+(step_id|step_code) —— 软删除数据源并解绑步骤指针 */
  deleteDataSource: (params = {}) => request.delete('/autotest/data_source/delete', { params }),
  saveOrUpdateDataSource: (data = {}) => request.post('/autotest/data_source/save_or_update', data),
  /** Body：data_source_id/code 或 (case_id|case_code)+(step_id|step_code) ——  已有矩阵直接返回，否则按报文构建 */
  buildDataSource: (data = {}) => request.post('/autotest/data_source/build', data),
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
  /** Body：{ data_source_id?, data_source_code?, case_id?, case_code?, step_id?, step_code? } —— 按步骤当前报文同步数据源矩阵字段 */
  updateDataSourceFields: (data = {}) => request.post('/autotest/data_source/update_fields', data),
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
  /** params：case_id、step_id、step_code —— 单步骤数据源模板下载（blob，按步骤报文生成默认原始数据） */
  singleStepTemplateDownload: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/data_source/single_step_template_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** params：case_id —— 汇总下载所有请求步骤的默认数据模板（blob） */
  batchStepTemplateDownload: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/autotest/data_source/batch_step_template_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),

  // ---------- performance：性能测试（接口/数据集/场景/任务/报告） ----------
  /** Body：PerfApiSelect —— 压测接口分页列表 */
  searchPerfApiList: (data = {}) => request.post('/perf/api/search', data),
  /** Query：api_id 或 api_code —— 接口详情 */
  getPerfApi: (params = {}) => request.get('/perf/api/get', { params }),
  /** Query：api_id 或 api_code —— 按接口报文推导 DataSource 矩阵模板（HEAD/BODY 分区预填 path key，不落库） */
  buildPerfApiMatrix: (params = {}) => request.get('/perf/api/build_matrix', { params }),
  /** params：api_id 或 api_code —— 接口数据源模板下载（blob，按接口报文生成默认矩阵） */
  downloadPerfApiTemplate: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/perf/api/template_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** Body：PerfApiCreate —— 新增压测接口 */
  createPerfApi: (data = {}) => request.post('/perf/api/create', data),
  /** Body：PerfApiUpdate（api_id/api_code 定位）—— 更新接口，版本号自增 */
  updatePerfApi: (data = {}) => request.post('/perf/api/update', data),
  /** Query：api_id 或 api_code —— 软删接口（被场景引用时禁止） */
  deletePerfApi: (params = {}) => request.delete('/perf/api/delete', { params }),
  /** Body：PerfApiLocate —— 复制接口为同应用下新资产 */
  copyPerfApi: (data = {}) => request.post('/perf/api/copy', data),
  /** Body：PerfApiDebug —— 真实请求验证已保存接口（口径与施压引擎一致，回写调试结论） */
  debugPerfApi: (data = {}) => request.post('/perf/api/debug', data),
  /** Body：PerfApiImport —— 从公共接口/用例步骤导入草稿（仅返回不落库，确认后走 create） */
  importPerfApisFromCase: (data = {}) => request.post('/perf/api/import_from_case', data),
  /** Body：PerfApiCurlParse —— cURL粘贴解析为接口草稿（不落库，另含warnings解析提示） */
  parsePerfApiCurl: (data = {}) => request.post('/perf/api/parse_curl', data),
  /** Body：PerfApiOpenapiParse —— OpenAPI/Swagger文档批量解析为接口草稿列表（不落库，逐条确认后走 create） */
  parsePerfApisOpenapi: (data = {}) => request.post('/perf/api/parse_openapi', data),
  /** Body：PerfApiSimpleSelect —— 场景选择器查询启用接口（不分页+名称搜索） */
  getPerfApisForScene: (data = {}) => request.post('/perf/api/list_for_scene', data),

  /** Query：api_id —— 某接口可用数据集（归属该接口，轻量字段不分页，编辑页数据源卡/调试取数/场景下拉共用） */
  listPerfDatasetsForApi: (params = {}) => request.get('/perf/dataset/list_for_api', { params }),
  /** Query：ds_id 或 ds_code —— 数据集详情（含 dataframe+axis 矩阵） */
  getPerfDataset: (params = {}) => request.get('/perf/dataset/get', { params }),
  /** Body：PerfDatasetCreate —— 新增数据集（dataframe+axis 矩阵协议，dataset/dataset_names 由服务端派生） */
  createPerfDataset: (data = {}) => request.post('/perf/dataset/create', data),
  /** Body：PerfDatasetUpdate（ds_id/ds_code 定位）—— 更新数据集，矩阵整体覆盖 */
  updatePerfDataset: (data = {}) => request.post('/perf/dataset/update', data),
  /** Query：ds_id 或 ds_code —— 软删数据集（被场景引用时禁止） */
  deletePerfDataset: (params = {}) => request.delete('/perf/dataset/delete', { params }),
  /** FormData：ds_project + file —— 上传xlsx解析为矩阵预览（不落库，保存时随create/update提交dataframe+axis+溯源） */
  uploadPerfDataset: (formData) => request.post('/perf/dataset/upload', formData),
  /** Body：PerfDatasetUpdateFields（ds + api 定位）—— 按参照接口当前报文同步数据集矩阵字段 */
  updatePerfDatasetFields: (data = {}) => request.post('/perf/dataset/update_fields', data),
  /** params：ds_id 或 ds_code —— 数据集导出下载（blob，sheet名为数据集名称） */
  downloadPerfDataset: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/perf/dataset/download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),

  /** Body：PerfSceneSelect —— 场景分页列表（不含容器大字段） */
  searchPerfSceneList: (data = {}) => request.post('/perf/scene/search', data),
  /** Query：scene_id 或 scene_code —— 场景详情（含编排与判定口径全量字段） */
  getPerfScene: (params = {}) => request.get('/perf/scene/get', { params }),
  /** Body：PerfSceneCreate —— 新增场景（接口项引用保存期校验） */
  createPerfScene: (data = {}) => request.post('/perf/scene/create', data),
  /** Body：PerfSceneUpdate（scene_id/scene_code 定位）—— 整编排覆盖保存 */
  updatePerfScene: (data = {}) => request.post('/perf/scene/update', data),
  /** Query：scene_id 或 scene_code —— 软删场景（被任务引用时禁止） */
  deletePerfScene: (params = {}) => request.delete('/perf/scene/delete', { params }),
  /** Body：PerfSceneLocate —— 复制场景为同应用下新场景 */
  copyPerfScene: (data = {}) => request.post('/perf/scene/copy', data),
  /** Body：PerfScenePrecheck —— 场景预检：逐接口发1次真实请求回显连通性与业务结论 */
  precheckPerfScene: (data = {}) => request.post('/perf/scene/precheck', data),
  /** Body：PerfScenePinBaseline —— 钉选/取消场景基线报告（同场景 completed 限定，report_code 留空为取消） */
  pinPerfSceneBaseline: (data = {}) => request.post('/perf/scene/pin_baseline', data),

  /** Body：PerfTaskSelect —— 压测任务分页列表 */
  getPerfTaskList: (data = {}) => request.post('/perf/task/search', data),
  /** Query：perf_id 或 perf_code —— 任务详情 */
  getPerfTask: (params = {}) => request.get('/perf/task/get', { params }),
  /** Body：PerfTaskCreate —— 新增压测任务 */
  createPerfTask: (data = {}) => request.post('/perf/task/create', data),
  /** Body：PerfTaskUpdate（perf_id/perf_code 定位）—— 更新任务，running 状态禁止 */
  updatePerfTask: (data = {}) => request.post('/perf/task/update', data),
  /** Query：perf_id 或 perf_code —— 软删任务 */
  deletePerfTask: (params = {}) => request.delete('/perf/task/delete', { params }),
  /** Body：PerfTaskRun —— 立即执行（场景装载闸门 + 高危二次确认，置排队后异步施压） */
  runPerfTask: (data = {}) => request.post('/perf/task/run', data),
  /** Body：PerfTaskLocate —— 停止执行（置 stopping，管线数秒内终止） */
  stopPerfTask: (data = {}) => request.post('/perf/task/stop', data),

  /** Body：PerfJobSelect —— 数据作业分页列表（不含失败原因大字段） */
  searchPerfJobList: (data = {}) => request.post('/perf/job/search', data),
  /** Body：PerfJobCreate —— 新增数据作业（prepare需提取列+归属接口，无update契约，配置变更重建） */
  createPerfJob: (data = {}) => request.post('/perf/job/create', data),
  /** Body：PerfJobLocate —— 立即执行（置排队后经{port}_perf队列异步跑脚本用例N轮） */
  runPerfJob: (data = {}) => request.post('/perf/job/run', data),
  /** Query：job_id 或 job_code —— 轻量轮询执行状态与观测字段 */
  getPerfJobStatus: (params = {}) => request.get('/perf/job/status', { params }),
  /** Query：job_id 或 job_code —— 软删作业（执行中禁止） */
  deletePerfJob: (params = {}) => request.delete('/perf/job/delete', { params }),

  /** Body：PerfReportSelect —— 压测报告分页列表（不含 locust_stats 快照） */
  getPerfReportList: (data = {}) => request.post('/perf/report/search', data),
  /** Query：report_id 或 report_code —— 报告详情（含 locust_stats 快照） */
  getPerfReport: (params = {}) => request.get('/perf/report/get', { params }),
  /** Body：PerfReportMetrics —— 指标曲线（代理 VictoriaMetrics query_range） */
  getPerfReportMetrics: (data = {}) => request.post('/perf/report/metrics', data),
  /** Query：report_code + baseline_code —— 对比两份报告（双侧指标对照 + 配置差异明细） */
  getPerfReportSnapshotDiff: (params = {}) => request.get('/perf/report/snapshot_diff', { params }),
  /** Query：report_code —— 报告产物清单（场景快照/引擎日志/结果分片；裸 axios 直连，404=无产物由调用方静默处理） */
  getPerfReportArtifacts: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/perf/report/artifacts`,
      { params, headers: { token: getToken() || '' } },
  ),
  /** Query：report_code + name —— 下载报告产物文件（blob，白名单内） */
  downloadPerfReportArtifact: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/perf/report/artifact_download`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),
  /** Query：report_code —— 导出报告 xlsx 报表（blob，六 sheet） */
  exportPerfReport: (params = {}) => axios.get(
      `${import.meta.env.VITE_BASE_API}/perf/report/export`,
      {
        params,
        responseType: 'blob',
        headers: { token: getToken() || '' },
      },
  ),

  /** Body：PerfComparisonCreate —— 新建多记录对比/汇总（创建时一次性计算结果快照，无update契约） */
  createPerfComparison: (data = {}) => request.post('/perf/comparison/create', data),
  /** Query：comparison_id 或 comparison_code —— 对比详情（含结果快照与引用报告现存性复核） */
  getPerfComparison: (params = {}) => request.get('/perf/comparison/detail', { params }),
  /** Body：PerfComparisonSelect —— 对比记录分页列表（不含结果快照大字段） */
  searchPerfComparisonList: (data = {}) => request.post('/perf/comparison/search', data),
  /** Query：comparison_id 或 comparison_code —— 软删对比记录（结论可重新创建） */
  deletePerfComparison: (params = {}) => request.delete('/perf/comparison/delete', { params }),
}
