# KeenRunner Backend — Agent 导航手册

> 本文件为 AI Agent / 新成员快速理解后端仓库的入口地图。
> 仓库定位：**生产在运**的接口自动化 + 性能压测一体化平台后端。
> 任何改动前请先阅读 `.qoder/skills/production-project-guard/SKILL.md`（生产项目强制约束）。

---

## 1. 技术栈（锁定，禁止替换）

| 维度 | 选型 |
|------|------|
| 语言 | Python ≥ 3.12 |
| Web 框架 | FastAPI |
| ORM | Tortoise-ORM（aerich 迁移） |
| 数据校验 | Pydantic v2 |
| 任务队列 | Celery + redbeat（Beat 调度） |
| 数据库 | MySQL |
| 缓存 | Redis |
| 日志 | loguru |
| 序列化 | orjson |
| 依赖管理 | uv（`pyproject.toml` + `uv.lock`），同步维护 `requirements.txt` |
| 部署 | gunicorn + uvicorn worker（`gunicorn.conf.py`） |

---

## 2. 顶层目录结构

```text
backend/
├─ backend_main.py          # FastAPI 应用入口（lifespan/路由注册/中间件/异常）
├─ gunicorn.conf.py         # gunicorn 部署配置
├─ celery_deploy.sh         # Celery worker + beat 启动脚本
├─ fastapi_deploy.sh        # FastAPI 服务启动脚本
├─ full_deploy.sh           # 一键全量部署脚本
├─ pyproject.toml           # uv 依赖与项目元数据
├─ requirements.txt         # pip 兼容依赖清单
├─ uv.lock                  # uv 锁定文件
├─ .env / .env.example      # 环境变量（PROJECT_CONFIG 驱动）
│
├─ applications/            # 业务模块（按领域拆分，每个模块独立 models/schemas/services/views）
│  ├─ autotest/             # 接口自动化（用例/步骤/任务/报告/明细/环境/数据源/标签）
│  ├─ performance/          # 性能压测（接口/场景/预设/报告/对比/数据集/作业 + locust 引擎）
│  ├─ base/                 # 基础设施（菜单/角色/路由/审计/权限/脚手架）
│  ├─ user/                 # 用户
│  ├─ department/           # 部门
│  └─ toolbox/              # 工具箱（代码生成等辅助能力）
│
├─ celery_scheduler/        # Celery 应用与任务
│  ├─ celery_base.py        # Celery 实例
│  ├─ celery_task_contract.py # 任务契约（统一入参/出参规范）
│  ├─ celery_worker.py      # worker 启动入口
│  └─ tasks/                # 具体任务（autotest 执行/导出/导入、perf 执行、数据作业等）
│
├─ common/                  # 通用工具（跨模块复用）
│  ├─ cache/                # Redis 连接池（异步/同步）
│  ├─ database/             # 数据库连接池（异步/同步/原生操作）
│  ├─ excel/                # openpyxl + pandas 工具
│  ├─ request/              # HTTP/TCP 请求工具（异步/同步）
│  └─ *.py                  # curl/jsonpath/xpath/yaml/openapi/文件/生成/转换等工具
│
├─ configure/               # 配置集中（.env → PROJECT_CONFIG）
│  ├─ project_config.py     # 项目配置主入口
│  ├─ global_config.py      # 全局常量
│  ├─ database_config.py    # 数据库配置
│  ├─ celery_config.py      # Celery 配置（队列名 = {port}_default,{port}_autotest）
│  ├─ logging_config.py     # loguru 配置
│  └─ router_registry.py    # 路由注册表（ROUTER_SUMMARY/ROUTER_TAGS）
│
├─ core/                    # 框架核心（统一响应/异常/中间件/初始化/装饰器）
│  ├─ responses/            # SuccessResponse/FailureResponse/ParameterResponse/...
│  ├─ exceptions/           # ParameterException/NotFoundException/DataBaseStorageException/...
│  ├─ middlewares/          # app/auth/request_context 中间件
│  ├─ initializations/      # 数据库/路由/中间件/异常注册
│  └─ decorators/           # block/listen 装饰器
│
├─ enums/                   # 枚举集中（autotest/perf/http/menu/app/...）
├─ services/                # 顶层服务（ctx/dependency/file_transfer/password）
├─ migrations/models/       # aerich 迁移产物（25 个版本文件）
├─ scripts/                 # 运维脚本（菜单注册 SQL、修复脚本、冒烟测试）
├─ static/                  # 静态资源（avatar/pythonHelpDoc/redoc/swagger-ui）
└─ output/                  # 运行时产物目录（报告/导出文件，不入 git）
```

---

## 3. 业务模块详解（applications/）

### 3.1 autotest — 接口自动化

**数据模型地图**（详见 SKILL.md 第 10 节）：
- `krun_autotest_project`（应用主数据）← case/task/tag 关联
- `krun_autotest_case`（用例）1—N `krun_autotest_step`（步骤树，parent_step_id 自关联）
- `krun_autotest_data_source`（参数化文件，dataset/dataset_names/cache_key）
- 环境链：`env` 1—N `env_bind` 1—N `env_config`（唯一真实外键链）
- 执行链：`task` → `record`（Celery 观测）→ `report`（每用例）→ `details`（每步骤×每圈快照）
- 辅助：`tag`、`case_transfer`、`data_create`

**核心执行链路**：
```
views/autotest_task_view.py (/autotest/task/run)
  → apply_async(run_autotest_task)  # 队列经 celery_config.task_routes 路由
  → celery_scheduler/tasks/task_autotest_case.py (_run_autotest_task_impl)
  → AutoTestStepCrud.batch_execute_cases
  → AutoTestStepExecutionEngine.execute_case  # 返回七元组
  → 写 report + details、回填 case/task 状态
```

**步骤引擎**（`services/autotest_step_engine.py`）：
- `StepExecutionContext`：变量池、占位符解析（`${}`/函数）、日志、Python 受限执行
- `StepExecutorFactory` 按 `step_type` 路由
- `BaseStepExecutor.execute()` 统一编排：跳过检查 → 内置变量注入 → defined_variables 解析 → `_execute()` → 提取+断言 → 明细快照
- 执行器子类：Http / Tcp / DataBase / Redis / Python / Wait / Assert / UserVariables / QuoteCase / Loop / Condition / DatagramDiff / Default

**运行时子包**（`services/autotest_runtime/`）：
- `builtin_variables.py`：内置变量（SERVER_HOST/PORT、TARGET_HOST/PORT/PATH）
- `context.py`：执行上下文
- `protocol_http.py` / `protocol_tcp.py`：协议适配
- `sandbox.py`：Python 受限执行沙箱
- `results.py` / `util_kv.py`：结果与键值工具
- `datagram/`：报文替换（json/xml）、差异对比、值适配
- `exchange/`：提取/断言管线（extractors、assert_compare、pipeline）
- `placeholders/`：占位符解析（arithmetic、functions、resolver）
- `validation/`：执行器字段/步骤树/变量流校验

**调试模式**（不落库，顺序严格对齐执行模式）：
```
views (/http_debugging, /tcp_debugging)
  → services/autotest_step_debug_service.py (StepDebugService.debug_http/debug_tcp)
  → inject_builtin_variables_for_debug → resolve_env_config → 占位符替换 → 发请求返回
```

### 3.2 performance — 性能压测

**四层数据模型**：
- `perf_api`（压测接口资产：一个请求 + 断言 + 提取）
- `perf_scene`（场景编排：打什么、怎么打 + 判定口径）
- `perf_load_preset`（负载预设：打多狠、什么时候打）
- `perf_report`（执行报告：一次施压的不可变结论）
- 辅助：`perf_comparison`（对比/汇总）、`perf_dataset`（数据集）、`perf_job`（数据作业）

**Locust 引擎**（`locust_engine/`）：
- `perf_locustfile.py`：Locust 入口
- `request_executor.py`：请求执行器
- `datagram_replace.py`：报文替换
- `host_monitor.py`：主机监控
- `metrics_push.py`：指标推送（VictoriaMetrics）
- `reservoir.py`：蓄水池采样
- `result_writer.py`：结果分片写入

**核心服务**：
- `perf_execute_service.py`：执行管线（report 落库 → Celery 下发 → 引擎启动 → 结果聚合）
- `perf_result_aggregator.py`：结果聚合（真分位延迟、接口/事务维度）
- `perf_scene_service.py`：场景向导一体化保存（`save_wizard`）
- `perf_comparison_service.py`：横向对比/合并/混合模式
- `perf_metrics_service.py`：指标曲线代理（VictoriaMetrics query_range）
- `perf_analysis_service.py`：报告分析
- `perf_asset_utils.py`：资产工具（产物清单、差异对比、导出 sheet 构建）
- `perf_process_registry.py`：引擎进程注册表

**视图路由**：`/perf/api/*`、`/perf/scene/*`、`/perf/load_preset/*`、`/perf/report/*`、`/perf/comparison/*`、`/perf/dataset/*`、`/perf/job/*`、`/perf/analysis/*`

### 3.3 base — 基础设施

- `models/`：audit（审计）、menu（菜单）、role（角色）、router（路由）
- `services/`：
  - `scaffold.py`：**所有业务表继承的脚手架**（id/state/created_time/updated_time/created_user/updated_user/reserve_1~3）+ `unique_identify()` 生成 `*_code`
  - `permission_rule.py`：权限规则
  - `*_crud.py`：菜单/角色/路由/审计 CRUD
- `views/`：auth（登录/鉴权）、menu、role、router、audit、file_transfer

### 3.4 user / department / toolbox

- `user/`：用户模型 + CRUD + 视图
- `department/`：部门模型 + CRUD + 视图
- `toolbox/`：代码生成等辅助工具（`views/generate_view.py`）

---

## 4. 框架核心（core/）

### 4.1 统一响应（core/responses/）

所有视图**必须**返回统一响应体，禁止自造结构：
- `SuccessResponse(message, data, total)`
- `FailureResponse(message)`
- `ParameterResponse(message)`
- `NotFoundResponse(message)`
- `DataBaseStorageResponse(message)`
- `DataAlreadyExistsResponse(message)`

### 4.2 异常体系（core/exceptions/）

- `ParameterException`：参数错误
- `NotFoundException`：记录不存在
- `DataAlreadyExistsException`：数据已存在
- `DataBaseStorageException`：存储失败
- `NotImplementedException`：未实现

异常经 loguru 记录（`LOGGER.error` + `traceback.format_exc()`）后返回对应 `FailureResponse`。

### 4.3 中间件（core/middlewares/）

- `app_middleware.py`：应用级（CORS/日志等）
- `auth_middleware.py`：鉴权
- `request_context_middleware.py`：请求上下文（用户/租户注入）

### 4.4 初始化（core/initializations/）

- `app_initialization.py`：`register_database` / `register_exceptions` / `register_middlewares` / `register_routers` / `init_database_table`
- `data_initialization.py`：初始数据灌入

---

## 5. 配置（configure/）

**配置一律来自 `.env` → `PROJECT_CONFIG`，禁止硬编码 host/port/队列名/配置值。**

- `project_config.py`：`PROJECT_CONFIG` 单例（APP_TITLE/SERVER_HOST/SERVER_PORT/...）
- `celery_config.py`：队列名 = `{port}_default,{port}_autotest`（端口前缀派生）；`task_routes` 统一路由
- `database_config.py`：MySQL 连接
- `logging_config.py`：loguru 格式与轮转
- `router_registry.py`：`ROUTER_SUMMARY` / `ROUTER_TAGS`（OpenAPI 文档增强）

---

## 6. Celery 任务（celery_scheduler/）

**队列纪律**（禁止漂移）：
- 队列名统一为 `{port}_default,{port}_autotest`
- 生产者经 `task_routes` 统一路由，`apply_async` **不得硬编码 queue**
- worker 的 `-Q` 必须与配置一致

**任务清单**（`tasks/`）：
- `task_autotest_case.py`：autotest 用例执行（`run_autotest_task`）
- `task_execute_assign_case.py`：分配用例执行
- `task_export_case_datagram.py` / `task_export_case_script.py`：导出
- `task_import_case_script.py`：导入
- `task_public_api_to_script.py`：公共接口转脚本
- `task_performance.py`：性能压测执行
- `task_perf_data_job.py`：性能数据作业
- `task_example.py`：示例任务

**Beat 调度**：`scan_and_dispatch_autotest_tasks` 每 60 秒扫描到期任务并下发。

---

## 7. 通用工具（common/）

- `cache/`：Redis 连接池（`redis_connection_pool` 异步 / `redis_sync_pool` 同步）
- `database/`：MySQL 连接池（异步/同步/原生 SQL 操作）
- `excel/`：openpyxl + pandas 读写
- `request/`：HTTP（`request_async_utils`/`request_sync_utils`）+ TCP（`tcp_async_utils`）
- 单文件工具：`curl_utils`、`jsonpath_utils`、`xpath_utils`、`yaml_utils`、`openapi_utils`、`api_doc_convert`、`file_utils`、`generate_utils`、`convert_utils`、`replace_utils`、`shell_utils`、`url_utils`、`async_or_sync_convert`、`request_context`

---

## 8. 枚举（enums/）

按业务域集中声明，禁止内联魔法值：
- `autotest_enum.py`：步骤类型/执行状态/...
- `perf_enum.py`：`PerfRunMode`/`PerfLoadMode`/`PerfReportStatus`/`PerfAssertMode`/`PerfApiRole`/`PerfTargetMetric`/...
- `http_enum.py`：HTTP 方法/状态码
- `menu_enum.py`：菜单类型
- `app_enum.py`：应用级
- `base_enum_cls.py`：枚举基类
- `base_error_enum.py`：错误码
- `file_size_enum.py`：文件大小
- `program_env_enum.py`：环境
- `testcase_priority_enum.py`：用例优先级

---

## 9. 分层红线（强制）

```
models → schemas → services → views(router)
```

- **router 只做**：参数接收、调用 service、返回统一响应
- **业务逻辑全部在 services**
- **services 写法**：模块级函数与 `XxxService` 静态方法类并存，跟随同目录文件现有风格
- **业务不进 views、model 逻辑不进 schemas、后端业务不下沉前端**

---

## 10. 编码风格画像（动手前必读）

- 服务文件惯用「**分区注释 + 分区内函数组**」组织
- 常量与枚举按业务分组集中声明
- 业务操作按读写分离到 `*_crud.py`
- 视图只编排、不写业务
- 异常经 loguru 记录后返回 `FailureResponse`
- 新增函数必须：标注全部参数 type hint 与返回类型；入参经 Pydantic schema 校验；docstring 附响应/返回结构示例
- 命名描述性自解释、禁止随意缩写
- 注释解释"**为什么**"与意图，不复述代码"做了什么"
- 数据与逻辑分离：常量、注册表、配置映射独立声明
- 写操作收敛单一入口：新增写操作必须挂到该资源既有 Crud/Service 入口

---

## 11. 数据库约定

- 所有业务表继承 `base/services/scaffold.py` 脚手架字段
- `state`：0 启用 / 1 禁用（软删除，**查询必须过滤**）
- `*_code`：由 `unique_identify()` 生成（时间戳-UUID，全局唯一）
- 跨表引用优先 `*_code`，表内定位用 `id`
- 除环境链外均为 BigInt **逻辑关联**、无物理外键，业务层校验；**禁止擅自补外键**
- 新增字段走 Tortoise Model + aerich 迁移；**禁止裸写原生 SQL**

---

## 12. 入口与启动

| 入口 | 命令 |
|------|------|
| FastAPI 开发 | `uvicorn backend.backend_main:app --reload` |
| FastAPI 生产 | `gunicorn -c backend/gunicorn.conf.py backend.backend_main:app` |
| Celery worker | `bash backend/celery_deploy.sh` |
| 一键部署 | `bash backend/full_deploy.sh` |
| 依赖安装 | `uv sync`（或 `pip install -r requirements.txt`） |
| 迁移 | `aerich migrate` + `aerich upgrade` |

---

## 13. 关键文件速查

| 用途 | 路径 |
|------|------|
| FastAPI 应用入口 | `backend_main.py` |
| 项目配置 | `configure/project_config.py` |
| Celery 配置 | `configure/celery_config.py` |
| 路由注册 | `configure/router_registry.py` |
| 统一响应 | `core/responses/` |
| 异常体系 | `core/exceptions/` |
| 脚手架基类 | `applications/base/services/scaffold.py` |
| autotest 步骤引擎 | `applications/autotest/services/autotest_step_engine.py` |
| autotest 调试服务 | `applications/autotest/services/autotest_step_debug_service.py` |
| perf 执行管线 | `applications/performance/services/perf_execute_service.py` |
| perf 场景向导 | `applications/performance/services/perf_scene_service.py` |
| perf Locust 引擎 | `applications/performance/locust_engine/perf_locustfile.py` |
| Celery 任务目录 | `celery_scheduler/tasks/` |
| aerich 迁移 | `migrations/models/` |

---

## 14. Agent 改动检查清单

动手前：
1. 评估改动量，列出受影响文件与模块
2. 分解任务目标，拆为可独立验证的子目标
3. 审查功能链路：前端页面 → api → view → service → 数据库/Celery → 前端反馈
4. 读同目录 2-3 份已有源码，复制其命名、注释、异常捕获、返回格式

写代码前：
5. 评估对线上接口/业务的影响；有影响先说明影响范围
6. 复用 `core/responses` 与 `core/exceptions`，禁止自造返回/错误结构
7. 配置一律来自 `.env` → `PROJECT_CONFIG`，禁止硬编码
8. Celery 队列名统一，`apply_async` 不得硬编码 queue

交付前：
9. 链路复核：改动前后行为一致，未波及其他分支
10. 边界验证：空值、非法入参、异常分支均按预期处理
11. 编译与导入冒烟：`py_compile` 必做
12. 残留检查：全局搜索被替换的旧符号、旧路径、死代码
13. 影响声明：改动文件、依赖、表结构与线上兼容性

---

## 15. 高危禁止清单

- ❌ 大规模重构 / 整模块重写
- ❌ 删除已有业务逻辑、常量、枚举（除非用户明确指令）
- ❌ 未经确认新增第三方依赖或升级版本
- ❌ 未经确认增删改已有表字段（改表必须走 aerich 并显式确认）
- ❌ 硬编码 host/port/队列名/配置值
- ❌ Celery 队列漂移
- ❌ 把大二进制/压缩包写入 git 版本库

---

> 本文件由仓库结构扫描生成，作为 Agent 导航入口。
> 详细业务约束与数据模型地图见 `.qoder/skills/production-project-guard/SKILL.md`。
