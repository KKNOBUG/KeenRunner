# KeenRunner — Agent 仓库手册

> 本文件是 AI Agent 与新成员理解全仓的入口，同时是代码评审（Standards 轴）的基准文档。
> 仓库定位：**生产在运**的接口自动化 + 性能压测一体化平台（前后端分离）。

---

## 1. 权威文档索引（按优先级）

| 文档 | 作用 |
|------|------|
| `backend/agents.md` | 后端导航手册：模块结构、任务契约、链路地图（后端唯一权威入口） |
| 本文件 | 全仓概览 + 前端/跨端规范 + 评审基准 |
| `backend/性能测试*设计.md`、`backend/执行明细树结构展示需求文档.md` | 性能压测/明细树的补充设计说明（与代码冲突时以代码为准） |

> `.qoder/skills/production-project-guard/SKILL.md` 为历史生产约束文档，当前工作区可能不存在；缺失时以本文件与 `backend/agents.md` 为准。
> 规则裁决顺序：用户显式指令 > 高危禁止清单（`backend/agents.md` 第 15 节） > 仓库现状 > 文档。**代码是最终事实源**：文档与代码冲突时先以代码确认边界，再同步修正文档。

## 2. 技术栈（锁定，禁止替换）

**后端 `backend/`（Python ≥ 3.12）**：FastAPI + Tortoise-ORM（aerich 迁移）+ Pydantic v2；Celery(+redbeat)；MySQL + Redis；loguru；orjson；uv 管依赖（同步维护 requirements.txt）；gunicorn + uvicorn worker 部署。

**前端 `frontend/`（JavaScript 工程，无 TS）**：Vue3 Composition API（`<script setup>`）+ Naive UI + pinia + vue-router + vue-i18n；Vite 构建；pnpm 管依赖；sass + UnoCSS；编辑器用 monaco/codemirror、表格用 luckysheet。

## 3. 目录与分层

```text
backend/
├─ applications/<模块>/{models,schemas,services,views}  # autotest、performance、base、user、department、toolbox
├─ celery_scheduler/   # Celery 应用、任务契约与 tasks（tasks/ 下任务模块自动扫描注册）
├─ configure/          # 配置集中，.env 驱动（PROJECT_CONFIG / CELERY_CONFIG）
├─ core/               # 统一响应/异常/中间件/初始化
├─ common/             # 通用工具（cache/database/excel/request/...）
├─ enums/、migrations/ # 枚举、aerich 迁移产物（migrations/models 为版本文件）
└─ output/             # 运行时产物（下载/日志/上传等不入 git；template/ 是部署模板资产）

frontend/
├─ build/ settings/ i18n/  # 构建常量、布局开关、国际化
└─ src/
   ├─ api/           # 接口集中（src/api/index.js），统一走 request 工具
   ├─ composables/   # useXXX hooks（复杂页面逻辑必须拆到这里）
   ├─ directives/    # v-permission 等全局指令
   ├─ layout/        # 侧边栏/头部/页签/KeepAlive 容器
   ├─ router/        # 基础静态路由 + 守卫；业务路由由后端菜单动态生成
   ├─ store/         # pinia：user/permission/tags/autotest/app
   ├─ constants/ utils/ styles/
   └─ views/         # 页面组件；autotest 模块是全站样式基准模板
```

分层红线：业务不进 views、model 逻辑不进 schemas、后端业务不下沉前端。新增文件放入同业务模块既有目录，禁止新建未出现过的顶层目录。

### 3.1 关键链路（前端 → API → 后端 → 反馈）

- **动态路由/权限**：`main.js` → `setupRouter` → `/base/auth/usermenu` 生成菜单路由 + `/base/auth/get_user_routers` 生成接口权限键；菜单组件路径为 `/src/views{component}/index.vue`，KeepAlive 的 `include` 匹配 `defineOptions({name})`，即菜单名必须与组件名一致。
- **用例编辑保存**：用例列表 → `/autotest/steps?case_id&case_code` → `/autotest/step/tree` → 前端树编辑/校验 → **先保存数据源**（新步骤无 `step_code` 时跳过）→ `useStepTreeSerialization.buildUpdateOrCreateTreePayload` → `/autotest/step/update_or_create_tree` → 用 `success_detail` 回写 `step_id/step_code`，被跳过的数据源在拿到 `step_code` 后补存。离开页签由 `useDirtyCheck` 拦截。
- **任务执行**：`/autotest/task/run` → `run_autotest_task`（autotest 队列）→ worker → `AutoTestStepCrud.batch_execute_cases` → `AutoTestStepExecutionEngine.execute_case` → 写 report/details、回填 case/task；Beat 每 60 秒扫描到期任务（default 队列）。
- **异步导入/导出/生成**：视图校验 → Celery 任务 → `krun_autotest_record`（`task_summary` 结果快照，附件以 attachments 信封存放）→ 异步中心查询/下载。异步中心按 `task_type_in` 过滤五类任务。
- **数据源**：步骤面板 → `/autotest/data_source/{build,save_or_update,update_fields,...}` → `DataSourceService` 准入/矩阵清洗 → `DataSourceMatrixParser` → 落库；执行期 `DatasetLoader` 按 `dataset_name` 查库取场景（`cache_key` 仅落库，不参与读取）。
- **性能压测**：场景编辑页唯一保存入口 `/perf/scene/save_wizard`（场景+负载预设事务内 upsert）；执行 `/perf/load_preset/run` → `run_perf_preset`（perf 队列）→ `PerfExecuteService.execute_pipeline`（建报告→拉起 Locust→轮询→分片聚合→落终态）。

### 3.2 权限控制面（菜单 / 接口 / 数据行）

- 角色是唯一权限载体：菜单由 `krun_role_menus` 绑定、接口由 `krun_role_routers` 绑定、数据行按资源族标签在「标签范围」配置；新角色不自动绑定任何权限，必须显式配置。
- 管理员角色（`BuiltinRoleCode.ADMIN`=`Administrators`）与超管同权：`usermenu`/`get_user_routers`/`PermissionControl.has_permission`/`DependSuperUser`/`DataScope` 均直接全量放行，不依赖绑定记录；其角色编码不可修改、角色不可删除、绑定不可保存。内置角色码只从 `backend/enums/role_enum.py` 取，禁止散落字符串。
- 资源锚点是路由声明的资源族标签（`一级目录:二级模块`，如 `自动化测试:用例`），由 `resolve_request_tag` 从 `request.scope["route"].tags` 显式读取，**禁止用 URL 前缀推断**；未声明标签归入 `legacy`。标签清单由 `krun_router.tags` 汇总，新增/调整标签后必须 `POST /base/router/refresh` 同步。
- 角色三字段：`krun_role.select_scope`（可见）/`update_scope`（可写）/`delete_scope`（可删），取值 `ALL / DEPT_AND_CHILD / DEPT / SELF`，多角色取最宽（ALL > DEPT_AND_CHILD > DEPT > SELF）；新建角色默认 `DEPT_AND_CHILD/SELF/SELF`（schema 与库默认值一致）；超管与管理员角色不受限。
- 标签覆盖：`krun_role_tag_scope(role_id, tag)` 每个标签可单独配置三范围，字段为空表示按角色默认范围生效（`krun_role` 三字段），三字段均未设置的标签不落库；管理端「标签范围」Tab 未覆盖的行直接回显角色默认枚举，选中具体值保存后才生成覆盖记录。
- 未配置标签回落到角色默认范围；用户未挂角色时回退 SELF/SELF/SELF，超管、管理员角色与系统内部流程不受限。
- 写/删范围始终收敛到可见范围（运行期 `_clamp_to_read`、保存期 `scope_covers` 校验），保证不可写入不可读取的数据。
- 后端唯一入口 `backend/services/data_scope.py` 的 `DataScope`：`read_q(owner_field)` 构造列表过滤（`None` 表示不限），`can_write/can_delete(owner)` 判定归属，`for_tag(tag)` 按父资源族重解析，`DataScope.system()` 供任务执行、引擎回写等内部可信路径。部门范围按归属人**当前部门**动态解析，不落业务表快照。
- 父资源可读校验（B 级）：用例/任务/标签/环境/环境配置的创建与配置更新经 `autotest_scope_guard` 校验所属项目/环境对当前用户可读，避免向不可见父资源挂载子资源。
- 服务层写方法把 `scope: DataScope` 作为必填参数，越权抛 `NoPermissionException`；view 注入 `DependTagScope` 并 `except NoPermissionException: raise`（否则被 `except Exception` 吞掉），由全局处理器返回 403（`code=400403`，HTTP 200）。
- 归属口径：用例为 `owner_user`（转让后变更），其余资源为 `created_user`；步骤与数据源归属跟随所属用例；环境字典 `created_user/updated_user` 取登录态，忽略请求体。用例转让始终仅当前所属人本人可操作；性能压测模块不参与数据权限收口。
- 读过滤只作用于各资源**列表/主列表**接口；报告/明细批次下钻（`batch_code`/`task_code`）、项目/环境下拉、步骤树（按 `case_id`）不过滤。用例列表对 `PUBLIC_SCRIPT`/`PUBLIC_API` 放行。
- 内置角色接口绑定：Guests 在业务域（应用/自动化/任务/工具）全部放行，系统域只读；接口放行不等于可删他人数据，删除归属校验在 service 层兜底。
- 报告/明细写接口（create/update）仅超管或管理员角色可直调（`DependSuperUser`），执行引擎/内部流程走 service 直写；删除仍按归属人 + 接口权限双闸门。
- 审计中间件记录新增/更新/删除/执行/上传/下载类动作（`common/permission_action.py` 的 `AUDITED_ACTIONS`），刷新与查询直接透传；下载只记占位符，避免日志膨胀。

## 4. 编码规范（评审基准）

### 后端
- 分层固定：models → schemas → services → views；router 只做参数接收、调 service、返回统一响应；业务逻辑全部在 services，读写分离到 `*_crud.py`。
- 复用 `core/responses` 统一响应体（SuccessResponse/FailureResponse）与 `core/exceptions` 异常体系，禁止自造返回/错误结构；异常经 loguru 记录（`LOGGER.error + traceback.format_exc`）后返回 FailureResponse。
- 新增函数：全部参数 type hint 与返回类型；入参经 Pydantic schema 校验；docstring 附响应/返回结构示例。
- 数据库变更走 Tortoise Model + aerich 迁移，禁止裸写原生 SQL、禁止未经确认增删改表字段。
- 写操作收敛单一入口：新增写操作挂到资源既有 Crud/Service 入口，禁止另开直写路径。
- 数据与逻辑分离：常量、枚举、注册表独立声明，不内联在业务函数里；服务文件用「分区注释 + 分区内函数组」组织。
- 容器式字段/步骤类型变更必须四处同步：model 注释、schema 定义、执行引擎、前端 `useStepTreeSerialization.js`；遗漏任一处即断链。
- 禁止循环内查库/远程请求；复用现有连接池；队列名统一 `{port}_default`、`{port}_autotest`、`{port}_perf`，经 `task_routes` 路由，禁止硬编码 queue。
- 新增/修改接口后：FastAPI 路由需经 `POST /base/router/refresh` 同步 `krun_router`，并按 `PermissionRule` 的 summary 前缀规则确认角色补绑；新增页面还需在菜单管理写入 `krun_menu`（组件路径、keepalive、排序）。
- autotest 异步任务（导入/导出/脚本生成）统一写 `krun_autotest_record`（`task_summary` 结果快照，附件以 attachments 信封存放），失败态也要回填；终态以 `celery_status` 为准，`task_summary.success` 仅表示全部成功，失败/部分成功的 `task_error` 与 `task_summary.error` 写同一摘要，`task_summary.raw` 保留任务原始返回；异步中心按 `AutoTestTaskType` 过滤与展示。性能压测走 `perf_report` / `perf_load_preset` 自有状态链。

### 前端
- Vue3 `<script setup>` 组合式 API；复杂页面逻辑拆到 `composables/useXXX.js`。
- 业务路由不是手写静态表：由 `/base/auth/usermenu` 下发菜单动态生成，组件按 `/src/views{component}/index.vue` 解析；新增页面必须同步菜单记录，页面 `defineOptions({name})` 与菜单名一致（KeepAlive 的 include 依赖它）。
- 接口权限键统一 `apiPermissionKey(method, path)`（`method + VITE_BASE_API + path`），按钮级用 `v-permission`；超管与管理员角色直通。
- 行级删除显隐用 `userStore.canDeleteData(owner, can_delete)`：优先采用列表接口注入的 `can_delete`（后端按当前资源族的删除范围判定，含部门范围），缺失时回落归属账号比对；autotest 共享编辑不再按写入范围隐藏编辑入口。批量删除统一经 `composables/useBatchDeleteGuard` 的 `pickDeletableIds` 按同一结论过滤后再提交，避免整批被后端拒绝。
- 接口权限显隐统一用 `composables/useApiPermission` 的 `hasApiPermission(method, path)`（或 `v-permission` 指令）；受限角色不应看到必然 403 的新增/批量删除/导入导出/下载按钮。角色表单的范围选项复用 `src/constants/dataScope.js`。
- 请求统一走 `src/api/index.js` 与现有 request 工具，禁止新封装 axios 实例。成功判定为 `code === '000000' && status === 'success'`，401 自动登出；文件下载用裸 axios（带 token）+ `downloadBlobResponse`，不要套默认响应拦截器。
- 弹层/表格/表单等复用现有通用组件与 Naive UI 组件，不重复造轮子。
- 样式治理：`views/autotest` 是统一样式基准；基础 UI 样式优先复用 `styles/autotest-theme.scss` 全局类（`.step-editor-card`、`.log-item`、`.debug-loading` 等）；禁止在 scoped 样式里重复定义全局已有样式；多页面相似样式必须上收到全局基线并加作用域前缀。
- 注释为中文、简短说明意图。

### 通用
- 注释解释"为什么"与意图，不复述代码；禁止吞掉警告、类型错误与异常。
- 命名描述性自解释，跟随仓库既有命名；拒绝死代码、透传函数、过度抽象；不为用不到的扩展预留字段。
- 修复以根因为主，禁止持续打补丁、留历史淘汰痕迹；只约束新增与被修改代码，不得以此重构存量。
- 禁止硬编码 host/port/队列名/配置值：配置一律来自 `.env` → PROJECT_CONFIG。
- 禁止未经确认新增第三方依赖或升级版本（后端 uv、前端 pnpm）。

## 5. 交付与质量要求（每次改动）

1. 交付说明：改动文件列表；是否新增依赖（无则写明）；是否改表（无则写明）；线上兼容性说明。
2. 质量自检：链路复核（前端页面 → api → view → service → 数据库/Celery → 前端反馈）、空值/异常分支、后端 py_compile/导入冒烟、旧符号零残留；前端至少通过 `pnpm build`（或等价的编译检查）。
3. 明细表（details）只追加执行结果快照，禁止用明细数据回改步骤定义；软删字段 `state` 查询必须过滤。
4. 文档同步：链路、接口契约、菜单/权限、队列、模板资产等约定变化时，同步更新本文件与 `backend/agents.md`，避免文档再次滞后于代码。
5. 部署资产：`backend/output/template/*.xlsx` 是运行时模板资产，需随代码交付/同步（该目录下其余下载、日志、上传产物不入 git）。
