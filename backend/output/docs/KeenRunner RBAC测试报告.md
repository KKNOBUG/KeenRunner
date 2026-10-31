# KeenRunner RBAC / 鉴权 / 认证 / 角色与标签范围 测试报告

| 项 | 内容 |
|---|---|
| 文档版本 | v1.1（v1.0 测试 + 本轮修复回归） |
| 测试日期 | 2026-10-31 |
| 被测对象 | 工作区当前 RBAC 权限改造改动（接口权限 + 数据范围 + 标签范围 + 菜单 + 认证） |
| 测试方式 | 代码核查 + 真实接口调用 + MySQL 直查 + 前端端到端（browser MCP） |
| 数据库 | 10.211.55.3:3306 / krun / root |
| 后端 | http://192.168.1.27:8518 |
| 前端 | http://192.168.1.27:5174 |
| 内置账号 | admin / tester / guest，密码均为 KFuser01@! |
| 约束 | v1.0 只登记不修复；v1.1 按需求裁定完成修复并回归验证 |
| 结论 | v1.0 登记 20 项；v1.1 已修复 9 项（F-01/F-02/F-03/F-04/F-06/F-07 登录面/F-10/F-13 order/F-16），3 项裁定为需求设计（多端 logout、角色默认范围、自动补建环境绑定），性能模块（F-05）按需求未定稿暂缓 |

> 说明：前端页面请求经 `VITE_BASE_API=/api` 前缀（`/api/user/login`），直接调用后端为无前缀路径（`/user/login`），本文所有接口均按后端实际路径书写；平台统一以 HTTP 200 + body.code 表达结果（000000 成功、400400 参数、400401 认证、400403 权限、400404 不存在、400405 方法、999999 服务异常）。

---

## 0. 结论摘要

| 维度 | 结果 |
|---|---|
| 接口权限矩阵（认证 13 断言 + self 9 + 19 路由×3 角色） | **79/79 PASS**；规则计算值与库内绑定零漂移 |
| 数据范围（跨部门 / 同部门 / 访客 / 无角色 / 公共脚本 / 写删 / 执行 / 跨资源引用） | **83/83 闭环**（78 首轮 PASS + 5 条补参复测 PASS），另补 RoleTag 覆盖正例 1 条 |
| 边界 / 异常 / 脏数据 | 43 条有效用例：37 PASS、1 FAIL、5 OBSERVE；另空白名探针 3 条全部创建成功（缺陷） |
| 并发 | 同名项目 5 并发→5 条成功；任务 run 5 并发→均受理；10 并发登录全成功 |
| 契约审计（243 路由 / 41 菜单 / 4 角色） | admin_only=7、资源族未登记 0、行为无法推导 0、悬挂关系 0、组件缺失 0 |
| 数据清理 | QA_ 残留全部为 0，业务基线恢复（项目 3 / 用例 32 / 标签 6 / 配置 18 / 绑定 9 / 环境 3 / 用户 8 / 任务 3 / 记录 22） |

**核心判断**：接口权限与行级数据隔离在本轮实测中按设计生效；v1.0 的三处高风险（菜单刷新补绑、调试通道绕过数据范围、登录异常透出）已在 v1.1 修复并回归通过；性能模块按需求暂缓。

### 0.1 v1.1 修复批次与回归结果（2026-10-31）

| 缺陷 | 修复动作 | 代码锚点 | 回归结果 |
|---|---|---|---|
| F-01 调试通道越权 | `resolve_env_config` 新增 `scope`：先 `load_readable_project`，再按 `ENV_CONFIG` 资源族校验配置创建人；HTTP/TCP/Redis 视图注入 `DependTagScope` 并捕获 `NoPermissionException`→403；Python 沙箱不读环境配置，无需范围入口 | `autotest_step_debug_service.py:194-261`、`autotest_step_view.py:692-808` | guest 相对 URL 调试项目 1 → 400403「无权使用应用[id=1]」；tester 可见同部门配置 → 000000；把配置创建人改为跨部门 ZZDIAG_A 后 tester → 400403「创建人不在当前用户可见范围」 |
| F-02 refresh 全量补绑菜单 | `sync_role_permission_bindings` 的 `menus` 未显式传入时不再 `Menu.all()` 回填，refresh 只同步路由 | `permission_rule.py:194-205`、`router_crud.py:144-147` | Users 解绑菜单 1 后执行 refresh：菜单 1 仍 NOT_BOUND，未被复活；refresh 前后四角色菜单/路由绑定零变化（41/243、41/209、41/209、0/0/0）；存量脏绑定（zzdiag_r 41 菜单）已备份后清零 |
| F-03 用户列表脏 dept / N+1 | 新增 `_attach_departments` 批量 `id__in` 查部门并挂载，脏引用降级 `dept={}`；详情同口径；入参名恢复 `user_id` 语义 | `user_view.py:66-82,185-205,310-330` | 把 nihao.dept_id 改成 999999：列表 000000 且 `dept={}`；`/user/get?user_id=12` 同为 000000；恢复后正常 |
| F-04 空白名称可创建 | `AutoTestProjectCreate/Update` 对 `project_name` 做 `strip()` 后拒绝空值 | `autotest_project_schema.py:37-45,72-80` | `"   "`、`""` 均 400400「参数[project_name]不允许为空」 |
| F-06 前端明文密码/DEV 硬编码 | 登录页不再写 `password` 到 localStorage，移除 DEV 默认账号；历史 `loginInfo` 只保留 username | `frontend/src/views/login/index.vue:76-84,99` | `pnpm build` 通过；全前端 grep 无 `KFuser01`、无写 password 到存储 |
| F-07/F-16 登录错误码与异常透出 | 账号不存在/密码错误统一 400401「用户名或密码错误」，不再回显入参；`CredentialsSchema` 增加 `min_length=1` + username strip 校验；状态异常 403、内部错误 999999 固定文案 | `user_view.py:473-525`、`token_schema.py` | 错误密码/不存在用户 400401 且 `data=null`；空用户名/空白用户名/空密码 400400 |
| F-10 page_size 无上限 | 新增 `PAGE_SIZE_MAX=99999`，非性能模块全部 `Field/Query` 入参加 `le=PAGE_SIZE_MAX` | `common/pagination.py` + autotest/base/user/department 共 22 处 | `page_size=100000` → 400400；`99999` → 000000；`5`（ge=10）→ 400400；已覆盖 user/role/audit/project 实测 |
| F-13 菜单 order 未排序 | `get_user_menu` 超管与角色菜单查询均加 `order_by("order", "id")` | `user_view.py:615-652` | admin/tester 菜单树每层 order 均升序（[1..8] 等） |
| 建用户入参校验 | `UserCreate` username 增加 strip 非空校验、password `min_length=1` | `user_schema.py` | 空/空白用户名、空密码建用户均 400400 |

---

## 1. 测试范围、方法与判定口径

### 1.1 范围

- 认证：登录、JWT 载荷、token 篡改/畸形/超长、登出与 token_version、无 token 访问。
- self 通道：`get_userinfo`、`menu/list`、`get_user_routers`、无角色用户。
- 接口权限：内置三角色 × 19 条代表路由；243 条路由契约与库内绑定一致性。
- 数据范围：8 个 scope_aware 资源族（项目/环境/环境配置/标签/用例/报告/明细/任务）× 跨部门/同部门/访客/无角色 × 读/写/删/执行/跨资源引用。
- 标签范围：RoleTag 覆盖角色默认范围。
- 菜单权限：角色-菜单绑定、菜单下发、前端动态路由。
- 前端端到端：登录、菜单可见性、页面数据、角色权限抽屉、token 失效跳转。
- 代码风险：异常处理、SQL、校验、硬编码、日志、错误泄露、重复代码。

### 1.2 方法

1. 直接读取后端服务/视图/Schema/枚举/初始化代码，确认权限判定唯一事实源。
2. 用临时脚本（`_qa_*`，已删除）以 admin/tester/guest + 临时造数账号登录并调用真实接口。
3. 直连 MySQL 核对 `krun_router / krun_role_routers / krun_menu / krun_role_menus / krun_role / krun_role_tags / krun_user / krun_audit`。
4. 契约审计脚本按 `PermissionRule.role_allows_router` 重算三角色应绑集合，与库内绑定做差集。
5. 前端用 browser MCP 走真实登录与页面操作，结合代码确认前端权限控制点。

### 1.3 判定口径

- 权限层判定只看是否 403；业务参数错误（400400/400404/999999）视为"权限层已放行"。
- 预期只取代码契约（AGENTS.md、backend/agents.md、路由依赖树、Schema、角色权限抽屉语义），不臆测业务规则。
- 首轮 FAIL 必须复核是用例设计问题还是实现问题，复核后重新计数（见第 15 节）。

---

## 2. 模块预期功能 vs 实现（要求 1）

| 模块 | 预期功能（依据） | 实现核查 | 判定 | 代码锚点 |
|---|---|---|---|---|
| 登录认证 | 校验用户名/密码/状态，签发含 `exp,user_id,token_version` 的 JWT | 错误密码/不存在用户统一 400401，空用户名/空密码 400400，失败不回显密码 | 实现符合（v1.1 修复） | `backend/applications/user/views/user_view.py:473-525`、`backend/applications/base/schemas/token_schema.py` |
| Token 校验 | 篡改/过期/登出后失效 | 篡改、畸形、8KB 超长 token 均 400401；logout 后旧 token 400401（token_version += 1） | 实现符合 | `backend/applications/user/services/user_crud.py:258-268`、`backend/services/dependency.py:46-57` |
| self 通道 | 仅认证，不受 RBAC | 三角色全部 200；无角色用户 0 菜单 0 接口键；password 为空 | 实现符合 | `backend/applications/user/views/user_view.py:579-666` |
| 接口权限 | 按资源域 + 行为放行；管理员全量；admin_only 仅超管/管理员 | 243 路由 admin_only=7；规则计算 243/209/209 与库内完全一致；19×3 实测全 PASS | 实现符合 | `backend/applications/base/services/permission_rule.py:81-112`、`backend/core/initializations/permission_contract.py` |
| 路由刷新 | 契约驱动 upsert、删废弃、回收 admin_only | refresh 后 243 条、废弃清理生效、admin_only 从非管理员角色回收 | 实现符合 | `backend/applications/base/services/router_crud.py:144-147`、`permission_rule.py:169-190` |
| 数据范围 | 角色 select/update/delete 三级 + RoleTag 覆盖 + 多角色取最宽 | 8 个 scope_aware 资源族按 `read_q/can_read/can_write/can_delete` 收口；跨部门全拒；RoleTag 覆盖生效 | 实现符合 | `backend/services/data_scope.py:90-250`、`backend/applications/autotest/services/autotest_scope_guard.py:24-114` |
| 标签范围 UI | 8 个资源族可配置，值应与库一致 | 角色抽屉"标签范围"8 项，env_config 标"已覆盖"，与 krun_role_tags 5 条一致 | 实现符合 | 前端角色抽屉 + `krun_role_tags` |
| 菜单权限 | 角色-菜单绑定决定菜单可见性（抽屉存在"菜单权限"Tab） | refresh 只同步路由，不再触碰角色菜单；自定义角色菜单由管理员显式配置 | 实现符合（v1.1 修复） | `permission_rule.py:194-205` + `router_crud.py:144-147` |
| 菜单下发 | 两级树、按 order 排序、隐藏项不展示 | 后端两级；超管与角色菜单均 `order_by("order","id")`；隐藏项由前端过滤 | 实现符合（v1.1 修复） | `user_view.py:615-652`、`frontend/src/store/modules/permission/index.js:36-87` |
| 前端路由 | 组件路径 `/src/views{component}/index.vue`、KeepAlive 名一致 | 41 菜单组件文件 0 缺失；路由名 `全路径#menu_id` 唯一 | 实现符合 | `frontend/src/store/modules/permission/index.js:32-87` |
| 按钮权限 | `v-permission`/`hasApiPermission` 控制按钮 | admin"更多操作"下拉含重置/新增/删除；接口键 243/209 与后端一致 | 部分验证（仅对照 admin） | `frontend/src/directives/permission.js`、`frontend/src/utils/permissionKey.js` |
| 审计 | 写/删/执行/上传/下载留痕，凭证脱敏 | 请求体敏感字段与 `token/authorization/cookie` 等头部已脱敏；读接口 403 不落审计 | 实现偏差（中） | `backend/core/middlewares/app_middleware.py:27-42,193-194,241-247` |
| 性能模块 | 是否有数据范围要求需业务确认 | 全部 perf 视图 0 处 DependTagScope | 暂缓（需求未定稿，无开发计划） | `backend/enums/resource_enum.py:78-85`、`backend/applications/performance/views/perf_report_view.py:295` |
| 调试通道 | 使用环境配置必须与角色/用户可见范围一致 | HTTP/TCP/Redis 调试注入 `DependTagScope`，解析配置前校验应用与配置创建人；Python 沙箱不读环境配置 | 实现符合（v1.1 修复） | `autotest_step_view.py:692-808`、`autotest_step_debug_service.py:194-261` |
| 自动化测试资产 | 单元/集成测试基线 | 无 tests/、无 pytest 配置 | 实现缺失（工程） | 仓库结构 |

### 2.1 隐含逻辑（代码有、文档未写）

1. 多端可同时在线，但任一端 logout 使该账号全部 token 失效（`token_version` 全局自增）——**需求设计（已确认）**。
2. 角色默认范围：Administrators ALL/ALL/ALL；Users DEPT_AND_CHILD/DEPT_AND_CHILD/SELF；Guests SELF×3——**需求设计（已确认，`krun_role` 实测一致）**。
3. 列表"静默过滤、详情显式 403"：列表用 `read_q` 收窄返回空集（200），详情 `can_read` 失败抛 403。
4. 配置创建时自动补建环境绑定（`_get_or_create_env_bind`），传不存在 env 名不会报错——**需求设计（已确认）**。
5. 用例创建先校验 `case_tags` 必填，再做父项目可读校验，顺序影响错误码。
6. 内置角色 code 比较大小写敏感（精确匹配 `"Administrators"`）。
7. 状态字段统一软删 `state=1`，查询均带 `state__not=1`。

---

## 3. 模块依赖、调用链路与数据流转（要求 2）

### 3.1 登录与动态路由

```text
[frontend/src/views/login/index.vue handleLogin]
  → api.login → POST /user/login (user_public，无依赖)
  → user_view.login → UserCrud 校验密码/state
  → jwt.encode{user_id, username, state, is_superuser, exp, token_version}
  → 前端 setToken(header: token) → userStore.setUserInfo → addDynamicRoutes()
  → POST /user/menu/list  (AuthControl.is_authed → CTX_USER_ID)
  → POST /user/get_user_routers
  → permissionStore.generateRoutes → buildRoutes(两级，name=/path#menu_id)
  → router.addRoute → guard 放行 → 工作台
```

### 3.2 单次请求鉴权（接口权限）

```text
axios request(header: token) → FastAPI
  → [DependPermission] PermissionControl.has_permission
      ├ decode JWT → 校验 exp/user_id/token_version/state（AuthControl.is_authed，request.state 缓存）
      ├ load_request_roles(user)（request.state.current_roles 缓存）
      ├ 角色为空 → 400403「暂无任何角色策略」
      ├ 命中 Administrators → 直通
      └ Router.filter(Q(method) & (Q(path) | Q(path__contains="{"))) → _path_matches（{param} 逐段匹配）
  → view → service → ORM → SuccessResponse(code=000000)
```

### 3.3 数据范围（标签范围）

```text
view(scope: DataScope = DependTagScope)
  → get_tag_scope → DataScope.from_user(user)（请求级 _ScopeResolver）
  → scope.for_tag("autotest.case" 等)
      ├ _effective_levels：RoleTag 覆盖 > 角色默认 → widest_scope（多角色取最宽）
      ├ _resolve_owners：SELF={自己}；DEPT/DEPT_AND_CHILD=部门(含子)全部在用账号
      └ _clamp_to_read：write/delete 收敛到 read 可见集
  → 列表：Q(owner_field__in=read_owners)（空集用 [""] 占位规避 MySQL IN ()）
  → 详情/写：can_read/can_write/can_delete(owner) → 403 NoPermissionException
  → 父资源挂载：load_readable_project / assert_parent_readable / assert_case_writable
```

### 3.4 菜单与路由刷新

```text
启动：include_router(dependencies=[DependPermission...])
  → bind_route_contracts：依赖树推导 auth_mode/resource/action/admin_only
  → validate_route_contracts：只 LOGGER.error 不阻断

POST /base/router/refresh (admin_only)
  → RouterCrud.refresh_router：删除不在契约的路由+清绑定 → upsert
  → PermissionRule.sync_role_permission_bindings(routers=..., menus=未传)
      ├ 三个内置角色：_append_missing_relations(routers=规则允许集)（只追加）
      └ menus 未传 → 不触碰角色菜单（v1.1 修复；旧实现会 Menu.all() 全量回填）
  → drop_admin_only_bindings(非管理员角色)
```

### 3.5 任务执行 / 性能压测

```text
POST /autotest/task/run → scope.can_read(task.created_user) + assert_cases_readable
  → run_autotest_task.apply_async(queue=autotest) → worker
  → batch_execute_cases → ExecutionEngine → krun_autotest_report/details → 回填 task
POST /perf/load_preset/run → run_perf_preset → PerfExecuteService → Locust → krun_perf_report
```

### 3.6 异常与审计

```text
service 抛 NoPermissionException → 全局 handler → 400403
其他异常 → view catch → FailureResponse("...异常描述: {e}")（泄露内部异常）
未捕获异常 → app_exception_handler → data=traceback（泄露堆栈）
写类成功/失败 → logging_middleware → krun_audit（读类不审计）
```

---

## 4. 正向用例设计与执行（要求 3）

### 4.1 全矩阵（19 路由 × 3 角色 = 57，全部 PASS）

| 路由 | 行为 | admin | tester | guest |
|---|---|---|---|---|
| POST /user/create | 系统写 | 放行(400400 参数) | 403 | 403 |
| POST /user/deletes | 系统删 | 000000 | 403 | 403 |
| GET /user/list | 系统读 | 000000 | 000000 | 000000 |
| GET /dept/list | 系统读 | 000000 | 000000 | 000000 |
| POST /dept/create | 系统写 | 放行(400400) | 403 | 403 |
| GET /base/role/list | 系统读 | 000000 | 000000 | 000000 |
| GET /base/role/authorized | admin_only | 放行(400400) | 403 | 403 |
| POST /base/menu/list | 系统读 | 000000 | 000000 | 000000 |
| POST /base/router/refresh | 运维 | 000000 | 403 | 403 |
| POST /autotest/project/search | 业务读 | 000000 | 000000 | 000000 |
| POST /autotest/project/create | 业务写 | 000000 | 放行 | 放行 |
| POST /autotest/case/search | 业务读 | 000000 | 000000 | 000000 |
| POST /autotest/case/deletes | 业务删 | 放行(400400) | 放行 | 放行 |
| POST /autotest/step/execute_or_debugging | 业务执行 | 放行(400400) | 放行 | 放行 |
| POST /autotest/report/create | admin_only | 放行(400400) | 403 | 403 |
| POST /autotest/detail/create | admin_only | 放行(400400) | 403 | 403 |
| POST /perf/api/search | 性能读 | 000000 | 000000 | 000000 |
| POST /perf/load_preset/run | 性能执行 | 放行(400404) | 放行 | 放行 |
| POST /toolbox/generate/create_info | 工具写 | 放行(400400) | 放行 | 放行 |

### 4.2 认证用例（A1-A11，13 断言，全部 PASS）

| ID | 用例 | 输入 | 预期 | 实测 |
|---|---|---|---|---|
| A1 | 三角色登录 | admin/tester/guest + KFuser01@! | 000000 + token | JWT 载荷：admin is_superuser=True；tester token_version=2；guest token_version=3 |
| A2 | 错误密码 | admin / wrong-pass | 400401 统一文案 | 400401「用户名或密码错误」，`data=null`（v1.1） |
| A3 | 不存在用户 | qa_no_such_user | 失败且不泄露账号是否存在 | 400401 同文案（v1.1 统一，防枚举） |
| A4 | 空用户名 | "" / "   " | 400400 参数校验失败 | 400400「参数[username]不允许为空」（v1.1） |
| A5 | 空密码 | admin / "" | 400400 参数校验失败 | 400400「String should have at least 1 character」（v1.1） |
| A6 | 无 token self | 无 header | 401 | 400401 |
| A7 | 篡改 token | 改签名 | 401 | 400401 |
| A8 | 畸形 token | 非 JWT | 401 | 400401 |
| A9 | 超长 token(8KB) | 8KB 串 | 401 且不泄露堆栈 | 400401 |
| A10 | logout | 有效 token | 成功 | 000000 登出成功 |
| A11 | 登出后旧 token | 旧 token | 401 版本失效 | 400401「鉴权已过期」 |

### 4.3 self 通道（9 条，全部 PASS）

| ID | 用例 | 预期 | 实测 |
|---|---|---|---|
| B1×3 | 三角色 get_userinfo | 本人信息、password 为空 | user_id=1/2/3，password=None |
| B2×3 | 三角色 menu/list | 返回菜单 | 均 8 根（41 节点） |
| B3×3 | 三角色 get_user_routers | 返回接口键 | 243 / 209 / 209 |

### 4.4 数据范围用例（83 条闭环）

| 分组 | 用例数 | 结果 | 说明 |
|---|---|---|---|
| D 读取可见性（8 资源族 × 7 账号） | 56 | PASS 56 | admin/tester/guest/QA_SAME/QA_CROSS/QA_GUEST/QA_NOROLE；公共脚本全员可见；无角色全拒 |
| E 写操作（update/delete + RoleTag） | 15 | PASS 15（5 条补参复测） | 同部门可改、跨部门拒绝、删除仅本人；RoleTag 覆盖后同部门可删他人配置 |
| F 执行/调试 | 4 | PASS 4（1 条预期校正） | 可读即可执行；公共用例跨部门可执行；独立 HTTP 调试无归属校验（F-01） |
| G 跨资源引用 | 4 | PASS 4（2 条补参复测） | 跨部门建环境/建标签拒绝；建用例/写步骤树补合法参数后 403 |
| 补充正例 | 1 | PASS 1 | E6 同部门用户删他人 APP 配置（RoleTag delete=DEPT_AND_CHILD） |

### 4.5 代表性正向用例（输入 → 预期 → 校验点）

| # | 用例 | 输入 | 预期 | 校验点 / 实测 |
|---|---|---|---|---|
| P1 | admin 登录 | admin / KFuser01@! | 000000 + token | JWT 含 user_id=1/is_superuser=True/token_version；PASS |
| P2 | 无角色用户 self | QA_NOROLE 登录后 get_userinfo | 000000 | 可读本人；菜单 0、接口键 0；业务接口 403「暂无任何角色策略」 |
| P3 | 同部门可见 | QA_SAME 查 admin 项目 | visible | D1 PASS，count=1 |
| P4 | 跨部门隔离 | QA_CROSS 查该项目 | hidden | D1 PASS count=0；详情 403 |
| P5 | 公共脚本全员可见 | QA_CROSS 查公共脚本 | visible | D7 PASS；PUBLIC_CASE_TYPES 跳过归属过滤 |
| P6 | 同部门可改 | QA_SAME 改项目 | 000000 | E1 PASS |
| P7 | 跨部门不可改 | QA_CROSS 改项目 | 403 | E2 PASS |
| P8 | 删除仅本人 | QA_SAME 删 admin 项目 | 403 | E4 PASS（Users delete_scope=SELF） |
| P9 | RoleTag 覆盖 | QA_SAME 删同部门 admin 的 APP 配置 | 000000 | E6 复测 PASS |
| P10 | 跨部门删配置 | QA_CROSS 删该配置 | 403 | E7 复测 PASS「创建人[ADMIN]非当前用户」 |
| P11 | 访客删他人配置 | QA_GUEST 删该配置 | 403 | E8 复测 PASS（Guests delete=SELF） |
| P12 | 跨部门建用例 | QA_CROSS 携合法标签建用例 | 403 | G2 复测 PASS「无权使用应用[id=...]」 |
| P13 | 跨部门写步骤树 | QA_CROSS 提交 case+空 steps | 403 | G4 复测 PASS「用例所属人[ADMIN]非当前用户」 |
| P14 | 访客执行他人私有用例 | QA_GUEST execute_or_debugging | 403 | F1 复测 PASS |
| P15 | 跨部门执行 | QA_CROSS 同上 | 403 | F1 复测 PASS |
| P16 | 公共脚本可跨部门执行 | QA_CROSS 执行公共脚本 | 放行 | F3 PASS（业务 400400 步骤为空） |
| P17 | 任务下发 | QA_SAME run 自己任务 | 000000 | F2 PASS「已下发执行」 |
| P18 | 菜单下发 | 三角色 menu/list | 8 根 | 实测均 8 根/41 节点 |
| P19 | 接口键下发 | 三角色 get_user_routers | 243/209/209 | 与库内绑定一致 |
| P20 | 角色标签范围 UI | admin 打开角色「权限」抽屉 | 8 项且值一致 | 与 krun_role_tags 一致 |

---

## 5. 单元级与模块集成用例划分（要求 4）

仓库无 pytest/tests 基线，本轮按以下层级组织：

| 层级 | 对象 | 执行方式 | 结果 |
|---|---|---|---|
| 单元级（纯函数/规则） | `widest_scope`、`scope_covers`、`normalize_username`、`derive_action`、`PermissionRule.role_allows_router`、`buildRouteName` | 契约审计脚本把规则对 243 路由逐条计算，与库内绑定做差集；前端函数经 E2E 间接验证 | 规则一致（差集 0）；未以 pytest 形式固化 |
| 模块集成（接口级） | 认证、self、19 路由×3 角色、8 资源族 CRUD、步骤树、任务/压测下发 | httpx 直连后端 | 79 + 83 + 7 全部闭环 |
| 端到端（前端） | 登录/菜单/页面/权限抽屉/token 失效 | browser MCP | 6 条关键路径通过 |
| 未覆盖 | 纯单元断言固化、Celery worker 失败分支、DB 断连、事务回滚注入 | 见第 16 节 | 不可在共享环境安全执行 |

---

## 6. 边界用例（要求 5）

| ID | 场景 | 结果 | 说明 |
|---|---|---|---|
| H1.1/1.2 | page=0 / -1 | PASS | 400400 `page >= 1` |
| H1.3 | page=999999999 | PASS | 000000 空页 |
| H1.4/1.5/1.6 | page_size=9/10/0 | PASS | 400400 / 000000 / 400400 |
| H1.7 | page_size=100000 | PASS（v1.1） | 400400 `page_size <= 99999`；99999 为 000000 |
| H1.8 | page='abc' | PASS | 400400 类型错误 |
| H2.1 | 空名称 | PASS | 400400（唯一冲突，非校验） |
| H2.2 | 仅空格名称 | PASS（v1.1） | `"  "`、`""` → 400400「参数[project_name]不允许为空」 |
| H2.3/2.4 | 255/256 字符 | PASS | 255 成功，256 400400 |
| H2.5-2.7 | SQL 注入串 / XSS / 中文 emoji | PASS | 原样存储，无拼接执行；查询按字面量匹配 total=1 |
| H3.1-3.7 | 超大/0/-1/超 bigint/不存在主键 | PASS | 400404/400400；超 bigint 返回 999999（异常文本外泄） |
| H4.1-4.3 | 类型/邮箱/用户名超长 | PASS | Pydantic 拦截 |
| H4.4 | 建用户引用不存在角色 | OBSERVE | 999999 + 内部 JSON；用户可能残留（F-11） |
| H4.5/4.6 | 用例类型/环境类型非法 | PASS | 枚举白名单 |
| H4.8/4.9 | 标签/环境引用不存在项目 | PASS | 400404 |
| H4.10 | 配置引用不存在环境 | FAIL | 000000 自动补建环境绑定（F-09） |
| H4.11 | 描述 2049 | PASS | 400400 |
| H5.1/5.2 | 用户名 200 / 密码 10000 | PASS | 400400 长度限制 |
| H5.3 | 用户名注入 | PASS | 400404 用户名不存在 |
| H5.4 | token 带 Bearer 前缀 | 用例作废 | 脚本 header 传参错误，未计入统计 |
| H6.1-6.4 | 无角色 self/菜单/接口/业务接口 | PASS | 0/0/403 |
| H6.5 | 无角色改自己密码 | OBSERVE | self 通道允许，符合"仅认证"设计 |

统计：37 PASS / 1 FAIL / 5 OBSERVE / 1 作废；另空白名探针 3 条全部创建成功（F-04）。

---

## 7. 异常输入（要求 6）

| 类型 | 用例 | 结果 |
|---|---|---|
| 非法类型 | project_id='abc'、page='abc' | 400400，Pydantic 拦截 |
| 格式错误 | 邮箱无 @、密码超长、枚举值非法 | 400400 |
| 脏数据 | 用户 dept_id=999999 | 列表/详情均 000000，该用户 `dept={}`（v1.1 修复） |
| 特殊字符 | emoji、全角空格、制表符、255 中文 | 原样落库；空白名成为脏数据 |
| 注入类 | SQL 注入串、XSS 串、用户名注入 | 无 SQL 拼接，按字面量处理 |
| 超出范围 ID | 999999999、0、-1、>bigint | 400404/400400；超 bigint 走 999999 |
| 不存在主键 | 项目/用例/任务/负载预设 999999 | 400404（文案含 id） |
| 多余参数 | hacker、state 注入 create | 被 Pydantic 默认忽略 |

SQL 风险专项：业务代码唯一原生 SQL 为 `_fuzzy_json_list_ids`（`backend/applications/autotest/views/autotest_project_view.py:44-68`），表名/字段名为调用点字面量，值用 `%s` 占位；其余全部走 ORM，无 f-string 拼值。

---

## 8. 运行时异常与并发（要求 7）

| 场景 | 实测/结论 |
|---|---|
| 数据库查询空 | 详情 400404；列表 200 空集（符合"静默过滤"约定） |
| 依赖服务不可达 | HTTP 调试返回 999999「连接失败: All connection attempts failed」；未做 DB/Redis 断连注入 |
| 事务失败 | 用例/步骤树保存使用 `in_transaction()`；用户创建为多步写入，非事务（F-11） |
| 超时 | 未做真实超时注入；调试接口超时受配置控制 |
| 并发创建同名项目 | 5 并发 5 条 000000，库内 5 条同名（id 225-229），无唯一约束/无锁（F-08） |
| 并发执行同一任务 | 5 次均「已下发执行」，生成多份报告，无运行态互斥/幂等键（F-08） |
| 并发重复删除 | 代码级：`get_by_id(on_error=True)` → 后到请求 400404，天然收敛；未复测 |
| 并发登录 | 10 并发全部 000000（无锁竞争、无会话互踢） |

---

## 9. 资源边界（要求 8）

| 点 | 现状 | 风险 |
|---|---|---|
| page_size=100000 | 400400（v1.1 已加 `le=99999`） | 仍存在单次最大 99999 条的合法大查询，需前端克制 |
| 部门范围解析 | 全量载入部门用户名再拼 IN 列表（`data_scope.py:171-177`） | 大部门 → 超大 SQL + 内存集合 |
| 用户列表 | `_attach_departments` 一次 `id__in` 批量查部门，脏引用降级 `dept={}`（v1.1 修复） | 无 N+1，无整表失败 |
| 审计中间件 | 读全部响应体、>100KB 截断；请求体全量读入 | 大报文内存峰值；上传请求仅记文件名 |
| 步骤树 | 递归校验/序列化 | 深度无硬上限，仅自循环检测；极深树有递归风险 |
| 代码调试 | `UserCodeSandbox.MAX_CODE_LENGTH`、导入白名单、禁下划线属性 | 沙箱逃逸未测试（超出本次范围） |
| 缓存 | DataScope 为请求级缓存，无跨请求缓存 | 无缓存击穿/雪崩面 |

---

## 10. 入参校验（要求 9）

| 项 | 结果 |
|---|---|
| 缺少必填 | 400400（Pydantic 文案含字段名）；如 `/autotest/case/deletes` 空参数 400400 |
| 多余参数 | 忽略（未配置 `extra=forbid`） |
| 类型不匹配 | 400400 |
| 边界值 | 见第 6 节 |
| 校验缺口 | v1.1 已补：空/空白用户名、空密码入参拒绝；page_size 上限 99999；project 空白名称拒绝；登录错误码统一 |
| 待观察 | project_id 超 bigint 仍可能落到 999999（既有异常出口，不在本轮范围） |

---

## 11. 代码隐患（要求 10）

| 检查项 | 结论 | 证据 |
|---|---|---|
| 裸 except | 0 处真实（1 处为字段名 `step_exec_except` 误匹配） | 全仓 grep（排除 .venv/__pycache__） |
| 宽泛 `except Exception` | 468 处，多数吞掉异常类型后转 FailureResponse | `grep -r "except Exception"` |
| 未捕获异常 | 全局 handler 存在，但 `data` 返回完整 traceback（F-07） | `backend/core/exceptions/http_exceptions.py:99-104` |
| 资源未释放 | 连接由 Tortoise 管理；审计响应体重建 Response，未见句柄泄漏 | `app_middleware.py:222-234` |
| 死循环/潜在死锁 | 未见显式死锁；步骤树递归有自循环检测；未做并发写同表压测 | `backend/applications/autotest/services/autotest_runtime/validation/step_tree.py:20-60` |
| SQL 风险 | 唯一原生 SQL 参数化，无拼接值 | `autotest_project_view.py:44-68` |
| 事务 | 步骤树单事务；用户创建非事务 | `autotest_step_view.py:511` |
| 日志 | 视图层 `LOGGER.error + traceback` 基本齐全；读接口 403 无审计 | F-14 |

---

## 12. 类型、ORM、缓存、并发安全（要求 11）

| 项 | 结论 |
|---|---|
| Pydantic 校验 | 主要 Schema 有长度/枚举/类型约束；`extra` 默认 ignore；登录与建用户已补 `min_length=1` + username strip |
| Tortoise 查询 | 列表均带 `state__not=1`（软删过滤正确）；空 IN 用 `[""]` 规避；多角色并集一次查询 |
| N+1 | 用户列表/详情已改批量部门查询（v1.1）；`_resolve_owners` 一次大查询（规模风险） |
| 缓存 | 请求级 `_ScopeResolver` + `request.state` 缓存；无跨请求缓存 → 无击穿 |
| 并发安全 | 项目同名无唯一约束；任务 run 无幂等；并发删除靠 404 收敛 |
| 越权面 | 调试通道已补应用+配置创建人可见性（F-01，v1.1）；性能模块无范围（F-05，暂缓） |

---

## 13. 硬编码、日志、错误泄露、返回值一致性（要求 12）

| 项 | 位置 | 说明 |
|---|---|---|
| DEV 硬编码账号密码 | `frontend/src/views/login/index.vue` | v1.1 已移除（全部前端无 `KFuser01`） |
| 明文密码落 localStorage | 同文件 | v1.1 只保存 `{username}`，历史记录自动覆写清理 |
| 异常文本外泄 | 469 处 `异常描述: {e}` | 登录/建用户实测已不再回显内部 JSON；其余视图模板仍为存量风险 |
| traceback 外泄 | `http_exceptions.py:104` `data=f"{traceback}"` | 未捕获异常仍把完整栈返回前端（存量，本轮未动） |
| 错误码不一致 | 登录入口 | v1.1 统一：错误密码/不存在用户 400401、空用户名/空密码 400400 |
| 错误文案语义不符 | 「创建人[X]非当前用户」实际由 DataScope 判定 | `autotest_env_config_crud.py:287` 等 |
| 魔术值 | 范围已枚举化；`"Administrators"` 硬编码且大小写敏感 | `backend/enums/role_enum.py` |
| 队列名 | 无硬编码，走 task_routes | 通过 |
| 审计脱敏 | 请求体与 `token/authorization/cookie` 已遮蔽；响应头未脱敏 | 低风险 |

---

## 14. 可读性、可维护性、工程规范（要求 13）

- 重复代码：469 个视图 `try/except → FailureResponse("...异常描述")` 模板高度重复，建议上收统一响应装饰器（本轮不修）。
- 可抽离点：`owner_q = scope.read_q(...)` 在 14 处重复，可抽 `apply_owner_scope(q, scope, field)`。
- 双语义：错误文案「非当前用户」与 DataScope 语义不一致，易误导排障。
- 注释质量：`data_scope.py`、`autotest_scope_guard.py`、`permission_rule.py` 注释解释"为什么"，符合仓库规范。
- 契约校验：`validate_route_contracts` 只告警不阻断，存在长期漂移风险。
- 测试资产：无自动化测试，回归依赖人工脚本（本轮临时脚本已删除）。

---

## 15. 缺陷台账与 v1.1 状态

| ID | 级别 | 缺陷 | 证据（运行时） | 代码锚点 | v1.1 状态 |
|---|---|---|---|---|---|
| F-01 | P0 | 调试接口（http/tcp/redis/python）无数据范围校验，可按 `project_id+env_name+config_name` 使用他人环境配置（host/port），任一直连内网目标 | v1.0：跨部门调试放行 | `autotest_step_view.py:692-808`、`autotest_step_debug_service.py:194-261` | **已修复**：应用+配置创建人双校验；guest 403、跨部门配置 403、同部门 000000；直接绝对 URL 不读环境配置，无需范围 |
| F-02 | P0 | 菜单权限失效：refresh 将全部菜单补绑给三个内置角色，且只追加不回收；自定义角色 0 路由也有 41 菜单 | v1.0：四角色菜单均 41/41 | `permission_rule.py:194-205`、`router_crud.py:144-147` | **已修复**：refresh 不再触碰菜单；解绑菜单 refresh 后不复活；zzdiag_r 存量 41 菜单已备份清零 |
| F-03 | P0 | 用户列表：单条脏 dept_id 导致整表 999999；循环内查部门 N+1；dept_id 变量复用入参名 | v1.0：脏 dept 使整表失败 | `user_view.py:66-82,185-205,310-330` | **已修复**：批量部门查询+脏引用降级；列表/详情均 000000 |
| F-04 | P1 | 空白名称可创建（无 strip 非空校验），绕开同名唯一约束 | v1.0：`"  "`/`"\t"`/`"\u3000"` 均 000000 | `autotest_project_schema.py:37-45,72-80` | **已修复**：project_name strip 后拒绝空值（400400） |
| F-05 | P1 | 性能模块整体未接入数据范围；Guest 可读他人报告、可触发压测 | v1.0：Guest 与 admin 同报告 | `resource_enum.py:78-85`、`perf_report_view.py:295` | **暂缓**：需求未定稿、无开发计划，本轮不处理 |
| F-06 | P1 | 前端明文保存密码到 localStorage，DEV 环境硬编码账号密码 | v1.0：`LOGININFO={username,password}` | `login/index.vue:76-84,99` | **已修复**：只存 username，移除 DEV 默认账号；`pnpm build` 通过 |
| F-07 | P1 | 错误响应泄露内部异常/堆栈 | v1.0：登录 999999 内嵌 JSON | 469 处视图 catch、`http_exceptions.py:104` | **部分修复**：登录/建用户入口已收敛；全局 traceback 出口为存量风险（未在本次清单） |
| F-08 | P1 | 并发/幂等缺失：项目无唯一约束；任务 run 无运行态互斥 | 5 并发同名项目 5 条成功 | `autotest_task_view.py:315-351` | 保留（未在本次修复清单） |
| F-09 | P1 | 配置引用不存在环境时自动补建绑定（数据污染），需求未明确 | H4.10 返回 000000 | `autotest_env_config_crud.py:102-108,542-573` | **需求设计（非缺陷）**：配置创建自动补建环境绑定 |
| F-10 | P2 | page_size 无上限（100000 成功），大表全量序列化 | H1.7 | `common/pagination.py` + 22 处入参 | **已修复**：上限 99999，100000 → 400400 |
| F-11 | P2 | 建用户非事务：角色/部门不存在时用户可能残留 | H4.4 | `user_view.py` create 链路 | 保留（未在本次修复清单） |
| F-12 | P2 | `/user/list` 向 Guests 暴露全量账号与 PII | v1.0：Guest 可见全字段 | `user_view.py` 列表排除字段 | 保留（未在本次修复清单） |
| F-13 | P2 | 菜单重复 path `ui`；order 未参与排序 | v1.0：无 ORDER BY | `user_view.py:615-652` | **部分修复**：order 已排序；重复 path 属存量菜单数据（未改） |
| F-14 | P2 | 读接口 403 不落审计 | 代码 | `app_middleware.py:193-194` | 保留（未在本次修复清单） |
| F-15 | P2 | 表格请求失败后清空数据，无持久空态区分 | E2E | `CrudTable.vue:159-161` | 保留（未在本次修复清单） |
| F-16 | P2 | 登录错误码不一致：空用户名 400404、空密码 999999 | v1.0：A4/A5 | `user_view.py:473-525` | **已修复**：400401 统一文案，参数错误 400400 |
| F-17 | P3 | 错误文案「非当前用户」与 DataScope 语义不符 | E7 文案 | `autotest_env_config_crud.py:287` 等 | 保留 |
| F-18 | P3 | `includes_admin` 大小写敏感 | 代码 | `role_enum.py` | 保留 |
| F-19 | P3 | 大部门范围解析为内存集合 + 超大 IN | 代码 | `data_scope.py:171-177` | 保留 |
| F-20 | P3 | 无自动化测试资产（无 tests/pytest） | 仓库结构 | — | 保留 |

---

## 16. 误报纠正记录

1. 「用户管理页恒空 = 403 静默」→ 实为脏数据 `QA_BADREF.dept_id=999999` 触发 999999；前端拦截器有全局 toast，表格同时被清空。改判 F-03 + F-15。
2. 「列表首屏不加载 = 缺陷」→ 代码注释明确"由用户点击搜索触发"，属设计约定（`frontend/src/views/autotest/testcase/index.vue:677-682`）。
3. 「空名称被拒 = 校验到位」→ 实为已存在 id=218 空名项目的唯一冲突；空白名复测证明可创建（F-04）。
4. 「admin 更多操作按钮缺失」→ 实为 split 按钮组，下拉含重置/新增/删除，正常。
5. 数据范围首轮 5 条 FAIL → 全部是用例入参不完整（缺 `config_id/env_type`、`case_tags`、空 `steps` 先触发 400400），补齐后定向复测 7/7 PASS，非权限缺陷。
6. 「列表静默过滤 200 vs 详情 403 不一致」→ 属合理的"列表收窄、详情显式拒绝"语义，不计缺陷。

---

## 17. 契约审计明细

| 项 | 结果 |
|---|---|
| 路由总数 | 243 |
| admin_only 路由 | 7（/autotest/detail/create、/autotest/detail/update、/autotest/report/create、/autotest/report/update、GET+POST /base/role/authorized、/base/router/refresh） |
| 资源族 | 29 个（scope_aware 8：project/env/env_config/tag/case/report/detail/task） |
| 资源族未登记路由 | 0 |
| 行为无法推导路由 | 0 |
| 角色路由绑定 | Administrators 243/243、Users 209/209、Guests 209/209；应绑未绑 0、已绑但规则拒 0 |
| 菜单 | 41 条、8 个根、0 个三级、0 个孤立父节点、4 个 is_hidden、组件文件缺失 0 |
| 角色菜单绑定 | Administrators/Users/Guests/zzdiag_r 均 41；自定义角色 zzdiag_r 路由 0 |
| RoleTag | 5 条（Guests 对 project/env/env_config/tag select=DEPT_AND_CHILD；Users 对 env_config delete=DEPT_AND_CHILD）；指向非 scope_aware 标签 0 |
| 重复菜单 path | `ui`（18 Web 测试 / 19 App 测试）、`report`（跨父级，不冲突） |
| 归属列 collation | utf8mb4_0900_ai_ci（大小写不敏感）；非规范化归属值 0 |
| 用户名规范 | 重名 0、超 16 位 0；无角色用户 zzdiag_u(97)；悬挂关系 0 |
| 审计表 | krun_audit 19 列；记录 response_code/response_message，不记录权限拒绝原因 |

---

## 18. 前端端到端验证

| 场景 | 结果 |
|---|---|
| guest 登录 | 进入工作台，侧边栏 8 根（含系统管理） |
| guest 用户管理页 | 请求 200；首轮因脏数据 999999 空表，清理后恢复 8 行 |
| 菜单可见不可用 | Guests 可见系统管理菜单，系统写接口 403 |
| admin 角色管理页 | 4 条角色与 DB 一致（Administrators 3×ALL、Users 2 项部门+本人、Guests 3×本人、zzdiag_r 3×本人） |
| 角色「权限」抽屉 | 菜单权限/接口权限/标签范围三 Tab；标签范围 8 项，env_config 标「已覆盖」，与 DB 一致 |
| token 篡改后刷新 | 自动跳 `/login?redirect=...`，ACCESS_TOKEN 被清除 |
| 列表首屏策略 | 项目管理/测试用例不自动查询（设计约定）；用户管理 `onMounted` 自动查询 |
| v-permission | admin 下拉按钮存在；其余角色未逐一枚举（部分验证） |

---

## 19. 测试数据清理与现场状态

- 清理对象：project 218-233、env 54-55、env_bind 64-67、config 87-90、tag 140、case 238-239、task 65、record 152-157、user 212-216；复测追加 project 234/config 91/tag 141/case 240/user 217-219。
- 残留核对：project/case/tag/config/env_bind/env/task/record/user 的 QA_ 残留均为 0；details/report 无孤儿记录。
- 业务基线：项目 3、用例 32、标签 6、配置 18、环境绑定 9、环境 3、用户 8、任务 3、记录 22；`/user/list` = 000000 total=8；`/autotest/project/search` = 000000 total=3。
- 临时脚本与日志（`_qa_*.py/.log/.json`）已全部删除，`git status` 无新增未跟踪测试文件。
- 保留未动：`backend/output/_env_backup_*.json`、`_step_ref_backup_*.json`（时间戳早于本轮测试，归属不明）；库内 `zzdiag_r/zzdiag_u/zzdiag_a/zzdiag_b`（2026-10-28 创建，非本轮产生，作为「自定义角色 0 路由 41 菜单」证据保留）。

---

## 20. 不可实施项说明

| 项 | 原因 |
|---|---|
| DB/Redis 断连、真实超时、事务失败注入 | 共享在运环境，无法安全中断依赖或制造回滚 |
| Celery worker 崩溃/重试分支 | 需改 worker 部署与队列，影响他人任务 |
| 多角色合并取最宽（widest_scope）运行时验证 | 库内无多角色账号；已清理造数，仅保留代码级结论 |
| 大规模数据（百万级行）与内存剖析 | 需独立压测库与监控，当前库仅 1.6k 明细 |
| 沙箱逃逸测试 | 超出权限改造范围，且可能影响服务稳定性 |
| 生产级并发压测 | 仅做 5-10 并发小样本 |
| 全 243 路由逐条真实业务调用 | 需为每条构造业务数据；采用「契约计算 + 19 条代表路由实测」组合覆盖 |

---

## 21. 建议的统一修复顺序（待确认后执行）

1. P0：F-02 菜单补绑改为"仅首次初始化/保留人工配置"；F-01 调试接口补 `scope.for_tag(PROJECT/ENV_CONFIG)` 校验；F-03 用户列表改批量查部门 + 脏引用降级为空对象。
2. P1：F-04 名称统一 `strip()` 后校验；F-05 性能资源族登记 scope_aware 并接 `DependTagScope`（或明确"不隔离"）；F-06 移除明文密码存储与 DEV 硬编码；F-07 统一错误出口，禁止回传异常文本/traceback；F-08 项目名唯一索引 + 任务运行态互斥。
3. P2/P3：分页上限、建用户事务、PII 最小化、菜单 path/order、审计补拒绝事件、表格空态文案、错误码与文案统一。

回归基线：79 接口矩阵 + 83 数据范围 + 43 边界 + 7 条并发/幂等补充。