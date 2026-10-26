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
- 接口权限键统一 `apiPermissionKey(method, path)`（`method + VITE_BASE_API + path`），按钮级用 `v-permission`；超管直通。
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
