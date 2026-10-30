# KeenRunner Backend — Agent 导航手册

> 本文件为 AI Agent / 新成员快速理解后端仓库的入口地图。
> 仓库定位：**生产在运**的接口自动化 + 性能压测一体化平台后端。

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
│  ├─ celery_config.py      # Celery 配置（队列名 = {port}_default / _autotest / _perf）
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
├─ migrations/models/       # aerich 迁移产物（当前 11 个版本文件，以目录现状为准）
├─ scripts/                 # 运维/修复脚本（aerich 对齐、redoc slug 等）
├─ static/                  # 静态资源（avatar/pythonHelpDoc/redoc/swagger-ui）
└─ output/                  # 运行时产物（download/logs/jmx/upload 等不入 git；template/ 为部署模板资产）
```

---

## 3. 业务模块详解（applications/）

### 3.1 autotest — 接口自动化

**数据模型地图**（字段以 `applications/autotest/models/` 模型定义为准）：
- `krun_autotest_project`（应用主数据）← case/task/tag 关联
- `krun_autotest_case`（用例）1—N `krun_autotest_step`（步骤树，parent_step_id 自关联）
- `krun_autotest_data_source`（参数化文件，dataset/dataset_names/cache_key）
- 环境链：`env` 1—N `env_bind` 1—N `env_config`（唯一真实外键链）
- 执行链：`task` → `record`（Celery 观测）→ `report`（每用例）→ `details`（每步骤×每圈快照）
- 辅助：`tag`、`case_transfer`、`data_create`

**核心执行链路**：
```
views/autotest_task_view.py (/autotest/task/run)
  → apply_async(run_autotest_task)  # task_routes 路由到 {port}_autotest
  → celery_scheduler/tasks/task_autotest_case.py (_run_autotest_task_impl)
  → AutoTestStepCrud.batch_execute_cases  # batch_code；任务级串行/并行；用例内 轮次×数据场景
  → AutoTestStepExecutionEngine.execute_case  # 七元组：results/logs/report_code/statistics/session_variables/defer_create_report/pending_create_details
  → 写 report + details、回填 case/task 状态；执行观测写 record(task_summary)
```

**步骤引擎**（`services/autotest_step_engine.py`）：
- `StepExecutionContext`：变量池、占位符解析（`${}`/函数）、日志、Python 受限执行
- `StepExecutorFactory` 按 `step_type` 路由
- `BaseStepExecutor.execute()` 统一编排：跳过检查 → 内置变量注入 → defined_variables 解析 → `_execute()` → 提取+断言 → 明细快照
- HTTP/TCP 报文类型判定统一走 `AutoTestToolService.resolve_datagram_is_xml`（显式类型优先，RAW/NONE 按内容嗅探），执行器与数据源采集共用同一口径
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

**步骤边界**：
- `step_is_skipped` 的步骤视为不存在：不写明细、不计统计；
- 引用公共脚本/公共接口的壳步骤执行的是被引用用例内部步骤（children 逐项计数，壳不重复计数）；
- `details` 只存执行快照，步骤定义仍以 `krun_autotest_step` 为准。

**数据源链路**：
```
views/autotest_data_source_view.py (/autotest/data_source/*)
  → services/autotest_data_source_service.py (DataSourceService：准入校验/字段同步/矩阵清洗)
  → services/autotest_data_source_parser.py (DataSourceMatrixParser：HEAD/BODY/ASSERT_* 四分区、水平/垂直方向、字符串化)
  → AutoTestDataSourceCrud 落库
执行期：DatasetLoader.load_dataset_for_request_step → AutoTestDataSourceCrud.get_dataset_scenario
        （按 case_id + step_code + dataset_name 查库）
```
- 仅 HTTP/TCP 步骤可挂载；用户脚本宿主下的「引用公共接口」步骤可挂；公共脚本/公共接口禁止使用数据源。
- BODY 分区：JSON 展平 JSONPath、XML 展平 XPath、PARAMS/FORM_DATA/X_WWW_FORM_URLENCODED 取键值；RAW/NONE/未指定类型正文为 XML 时同样按 XPath 展平（不改变纯文本/十六进制报文语义）。
- 引用公共接口壳：数据源归属仍是宿主 case_id + 壳 step_code（保存/执行定位），但矩阵与 data_original 取自被引用公共接口用例的唯一根 HTTP/TCP 请求步骤；`resolve_datagram_source_step` / `resolve_datagram_source_steps` 统一该口径（批量模板一次预载，避免循环查库）。
- `cache_key` 仅作为字段落库（`dataset_{case_id}_{step_code}`），当前执行期不读 Redis。
- 数据源字段/报文替换契约变更必须同步压测侧独立副本：`applications/performance/locust_engine/datagram_replace.py`（PerfXPath/PerfJsonDatagram/PerfXmlDatagram）、`request_executor.py` 与前端 `PerfApiDatasetPanel.vue`；压测 Locust 子进程禁止 import backend 主包，不能假定自动复用 autotest 修改。

**执行记录与异步中心**：
- 异步导入/导出/脚本生成统一写 `krun_autotest_record`：`task_type` 分类、`task_summary` 结果快照（含 `attachments` 信封）、失败态也回填；终态以 `celery_status` 为准，`task_summary.success` 仅表示全部成功，失败/部分成功的 `task_error` 与 `task_summary.error` 写同一摘要，`task_summary.raw` 保留任务原始返回；异步中心按 `AutoTestTaskType` 的 `task_type_in` 过滤。
- 报告读模型：`/report/search`（手工报告）、`/report/search_task_batches`（task_code 批次）、`/report/search_batch_scripts`（batch_code 脚本维度）、`/report/search_script_round_reports`（batch_code+case_id+round_no）、`/report/search_batch_reports`；报告明细树由 `/detail/tree` 后端组装。
- 列表页与删除入口：报告 `/report/search`、执行明细 `/detail/search`（菜单 `/autotest/detail`）、执行记录 `/task/record/search`（菜单 `/task/record`）、异步中心（同执行记录接口 + `task_type_in` 过滤）；四页均支持列表多选批量删除，行级删除按钮按后端回传的 `can_delete` 控制。

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

**执行链路**：
```
/perf/load_preset/run
  → PerfExecuteService.run_preset（完整性校验，原子置 queued）
  → run_perf_preset.apply_async（{port}_perf）
  → PerfExecuteService.execute_pipeline（消费闸门 → 建报告 → 拉起 Locust → 轮询停止/退出 → 分片聚合 → 报告终态）
停止：/perf/load_preset/stop → stopping → 管线数秒内杀进程组
```
- 状态机：`queued → running → completed/failed/stopped`；停止过渡态为 `stopping`，消息重投靠 queued 消费闸门防重复施压。
- 场景独立编辑页唯一保存入口 `save_wizard`：事务内 upsert scene + diff upsert presets（新增/更新/软删）。

**视图路由**：`/perf/api/*`、`/perf/scene/*`、`/perf/load_preset/*`、`/perf/report/*`、`/perf/comparison/*`、`/perf/dataset/*`、`/perf/job/*`、`/perf/analysis/*`

### 3.3 base — 基础设施

- `models/`：audit（审计）、menu（菜单）、role（角色）、router（路由）
- `services/`：
  - `scaffold.py`：**所有业务表继承的脚手架**（id/state/created_time/updated_time/created_user/updated_user/reserve_1~3）+ `unique_identify()` 生成 `*_code`
  - `permission_rule.py`：权限规则
  - `*_crud.py`：菜单/角色/路由/审计 CRUD
- `views/`：auth（登录/鉴权）、menu、role、router、audit、file_transfer
- `Role` 含数据权限三字段：`select_scope`（可见范围，默认 DEPT_AND_CHILD）、`update_scope`（可写范围，默认 SELF）与 `delete_scope`（可删范围，默认 SELF），即角色默认范围；标签级覆盖见 `RoleTagScope`（`krun_role_tag_scope`），详见 4.5。
- 内置角色码统一定义在 `enums/role_enum.py` 的 `BuiltinRoleCode`（`Administrators` / `Users` / `Guests`），判断逻辑用 `BuiltinRoleCode.includes_admin(role_codes)`，禁止在业务代码里散落角色码字符串。
- 删除语义：角色单删与批量删除均为**物理删除**（`krun_role` 无 `state` 字段）；管理员角色不可删除；存在未删除用户绑定（`krun_user_role`，该表为级联外键，删角色会静默清空用户权限）时整体拒绝，单删与批量删除口径一致。

### 3.4 user / department / toolbox

- `user/`：用户模型 + CRUD + 视图；单删与批量删除均为**软删除**（`state=1` 并递增 `token_version` 吊销 Token）；`/user/update` 仅在显式传 `role_ids` 时重建角色绑定，局部更新（如调岗）不清空既有授权。
- `department/`：部门模型 + CRUD + 视图；单删为**物理删除**，批量删除为**软删除**（`state=1`）；两条路径都拒绝存在启用子部门或在用用户的部门，删除时在事务内清理闭包表 `krun_dept_nest`
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
- `NoPermissionException`：数据越权（全局 handler 统一返回 `ForbiddenResponse`，`code=400403`、HTTP 200）
- `NotImplementedException`：未实现

异常经 loguru 记录（`LOGGER.error` + `traceback.format_exc()`）后返回对应 `FailureResponse`。

### 4.3 中间件（core/middlewares/）

- `app_middleware.py`：应用级（CORS/日志等）
- `auth_middleware.py`：鉴权
- `request_context_middleware.py`：请求上下文（用户/租户注入）

### 4.4 初始化（core/initializations/）

- `app_initialization.py`：`register_database` / `register_exceptions` / `register_middlewares` / `register_routers` / `init_database_table`
- `data_initialization.py`：初始数据灌入（角色种子含数据范围：管理员 ALL/ALL/ALL，标准用户与宾客 DEPT_AND_CHILD/SELF/SELF；存量库启动时校正管理员三范围为 ALL）

### 4.5 数据权限（services/data_scope.py）

- 枚举：`enums/permission_enum.py` 的 `DataScopeEnum`（`ALL / DEPT_AND_CHILD / DEPT / SELF`）。
- 模型：`Role.select_scope`（可见，默认 DEPT_AND_CHILD）/`Role.update_scope`（可写，默认 SELF）/`Role.delete_scope`（可删，默认 SELF），aerich 自动迁移；`RoleTagScope`（表 `krun_role_tag_scope`，唯一键 `role_id + tag`，同名字段承载标签级覆盖，字段为空表示按角色默认范围生效）
- 资源锚点：路由 tags 声明 `一级目录:二级模块`，`resolve_request_tag` 直接读取 `request.scope["route"].tags`，**不做 URL 前缀推断**；未声明归入 `legacy`。标签清单从 `krun_router.tags` 汇总，改标签后需 `POST /base/router/refresh`。
- 解析：`DataScope.from_user` 超管与管理员角色（`BuiltinRoleCode.ADMIN`）固定三范围全部数据；其余用户按标签两层解析「标签覆盖 > 角色默认范围」，逐字段回落，多角色取最宽，再解析为归属人集合（`None` 表示不限）。部门范围按归属人**当前部门**动态解析：`DEPT` 取本部门，`DEPT_AND_CHILD` 借闭包表 `DeptStruct` 展开。
- 写/删 ≤ 读：运行期 `_clamp_to_read` 收敛，保存期 `RoleCrud._assert_tag_scope_order` 用 `scope_covers` 拒绝超出可见范围的配置；未显式设置的字段按角色默认范围参与校验，避免“回读显示默认值、运行期被收敛”的不一致。
- 使用：`read_q(owner_field)` 产出列表过滤 `Q`（空集合用空串占位，规避 MySQL `IN ()` 语法限制）；`can_write(owner)`/`can_delete(owner)` 按归属账号（大写 16 位截断）判定；`for_tag(tag)` 按父资源族重解析；`DataScope.system()` 表示任务执行、引擎回写等内部可信路径。视图经 `DependTagScope` 注入，单请求只解析一次。列表响应在 view 层为每行注入 `can_delete`（`scope.can_delete(归属人)`），前端按钮显隐直接采用，禁止按归属人自行比对（部门范围无法在前端复算，且部分列表已排除 `created_user`）。
- 父资源可读校验（B 级）：`services/autotest_scope_guard.py` 的 `load_readable_project`/`assert_parent_readable` 校验所属项目/环境对当前用户可读，接入用例/任务/标签/环境/环境配置的创建与配置更新。
- 写校验约定：service 写方法将 `scope: DataScope` 设为必填参数，越权抛 `NoPermissionException`；view 注入 scope 并在 `except Exception` **之前**加 `except NoPermissionException: raise`，否则异常被吞。
- 权限载体：角色是唯一权限载体，菜单（`krun_role_menus`）、接口（`krun_role_routers`）与标签范围（`krun_role_tag_scope`）都挂在角色上；新建角色默认零绑定，必须由管理员显式配置。
- 管理员角色：`Administrators` 与超管同权，`usermenu`/`get_user_routers`/`PermissionControl.has_permission`/`DependSuperUser`/`DataScope` 均运行期直接全量放行，不依赖绑定记录；其角色编码不可修改、角色不可删除、绑定不可保存（`/base/role/authorized` 直接返回参数提示）。
- 管理员入口：`GET/POST /base/role/authorized` 在原有菜单/路由之外增删 `tag_scopes`（每项 tag + 三范围，空值=按角色默认），由 `RoleCrud.list_tag_scopes/save_tag_scopes` 事务内重建。
- 审计：`common/permission_action.py` 的 `classify_summary_action` + `AUDITED_ACTIONS` 为唯一分类源，`permission_rule.py` 与 `app_middleware.py` 共用；中间件对新增/更新/删除/执行/上传/下载落库，**刷新(ops)与查询直接透传**（下载响应仅记 `<FILE DOWNLOAD>` 占位符，不复制文件流）。新增接口的 summary 必须沿用标准动词前缀（刷新/查询/更新/新增/导入/上传/导出/下载/注销/删除/批量删除/执行/调试/启动/停止，以 `permission_action.ACTION_RULES` 为准），否则既不会进入审计也会被权限规则告警。
- 报告/明细写接口：HTTP `create/update` 加 `DependSuperUser`，仅超管、管理员角色或执行引擎可直调；引擎内部经 service 直写不走 HTTP。环境字典 `created_user/updated_user` 取登录态，忽略请求体回传。
- 内置角色接口绑定：Guests 业务域（应用/自动化/任务/工具）全部放行（含执行/调试/上传/下载），系统域只读；接口放行不代表可删他人数据，删除归属由 service 层 `can_delete` 兜底。
- 归属字段：用例用 `owner_user`（转让后变更，转让始终仅当前所属人本人可操作）；步骤与数据源以所属用例 `owner_user` 为准；项目/标签/环境/环境配置/任务/报告/明细/执行记录用 `created_user`。
- 删除语义矩阵：
  - **全物理删除**：审计日志（单删/批量/按用户/按时间）、测试报告（单删 `/report/delete` + 批量 `/report/deletes`，两路径均同事务级联删除明细）、执行明细（单删 `/detail/delete` + 批量 `/detail/deletes`）、异步中心与执行记录（同一资源，单删 `/task/record/delete` + 批量 `/task/record/deletes`，仅允许删除终态并清理产物）。报告/明细/执行记录的批量入口均按「全有或全无」校验，按 `report_codes` 删除与按 `report_ids` 等义。
  - **单删物理 + 批量软删**：应用（`autotest/project`）、标签、环境、环境配置、用例、步骤。两条路径都拒绝存在引用关系的数据：应用→用例/标签/环境绑定/环境配置/任务；标签→用例 `case_tags`；环境→环境配置/任务环境名；环境配置→步骤的请求配置/数据库/Redis 操作；用例→公共用例被引用步骤。用例单删连带物理删除其步骤，批量删除连带软删除其步骤；步骤无独立批量删除入口。
  - 批量删除一律「全有或全无」：先全量校验行级 `can_delete` 与引用关系，再单次落库，禁止边校验边删除导致部分成功。
  - 步骤树保存（`/autotest/step/update_or_create_tree`）的淘汰步骤为**物理删除**（含 IF 分支缩减的子步骤），并同步清理数据源与数据生成记录；同一用例内 `step_no` 必须唯一（前端按全树前序统一编号）。
- 读过滤边界：仅各资源列表/主列表接口注入；报告/明细批次下钻（`batch_code`/`task_code`）、项目/环境下拉、步骤树（按 `case_id`）不过滤；用例列表对公共用例放行。
- 不参与：性能压测模块。

---

## 5. 配置（configure/）

**配置一律来自 `.env` → `PROJECT_CONFIG`，禁止硬编码 host/port/队列名/配置值。**

- `project_config.py`：`PROJECT_CONFIG` 单例（APP_TITLE/SERVER_HOST/SERVER_PORT/...）
- `celery_config.py`：队列名 = `{port}_default` / `{port}_autotest` / `{port}_perf`（端口前缀派生）；`task_routes` 统一路由
- `database_config.py`：MySQL 连接
- `logging_config.py`：loguru 格式与轮转
- `router_registry.py`：`ROUTER_SUMMARY` / `ROUTER_TAGS`（OpenAPI 文档增强）

---

## 6. Celery 任务（celery_scheduler/）

**队列纪律**（禁止漂移）：
- 队列名统一为 `{port}_default`、`{port}_autotest`、`{port}_perf`（以 `configure/celery_config.py` 为准）
- 生产者经 `task_routes` 统一路由，`apply_async` **不得硬编码 queue**
- worker 的 `-Q` 必须与配置一致；`visibility_timeout=36000` 与最长任务硬时限（perf `36000s`）对齐，防止 unacked 消息被重投导致重复执行

**任务清单**（`tasks/`）：
- `task_autotest_case.py`：用例执行 `run_autotest_task` + Beat 扫描 `scan_and_dispatch_autotest_tasks`
- `task_execute_assign_case.py`：分配用例执行
- `task_export_case_datagram.py` / `task_export_case_script.py`：公共接口报文/脚本导出
- `task_import_case_script.py`：公共接口脚本导入
- `task_public_api_to_script.py`：公共接口转脚本
- `task_performance.py`：压测执行（`run_perf_preset`，perf 队列）
- `task_perf_data_job.py`：性能数据作业（perf 队列）
- `task_example.py`：示例任务

**任务时限**：任务级覆盖全局 `3300/3600s`；`run_autotest_task` 为 `25200/28800s`；`run_perf_preset` 为 `32400/36000s`。

**Beat 调度**：`scan_and_dispatch_autotest_tasks` 每 60 秒扫描到期任务，经 default 队列下发。

**执行记录类型**（`AutoTestTaskType`）：任务定义实际只用「多个用例执行」；记录分类另有「单个用例执行/调度任务扫描/公共接口报文导出/公共接口导出/公共接口导入/单接口脚本生成/测试案例生成」。

---

## 7. 通用工具（common/）

- `cache/`：Redis 连接池（`redis_connection_pool` 异步 / `redis_sync_pool` 同步）
- `database/`：MySQL 连接池（异步/同步/原生 SQL 操作）
- `excel/`：openpyxl + pandas 读写
- `xml_utils.py`：XML 命名空间/声明保留解析与序列化（数据驱动替换、占位符解析共用）
- `request/`：HTTP（`request_async_utils`/`request_sync_utils`）+ TCP（`tcp_async_utils`）
- 单文件工具：`curl_utils`、`jsonpath_utils`、`xpath_utils`、`yaml_utils`、`openapi_utils`、`api_doc_convert`、`file_utils`、`generate_utils`、`convert_utils`、`replace_utils`、`shell_utils`、`url_utils`、`async_or_sync_convert`、`request_context`

---

## 8. 枚举（enums/）

按业务域集中声明，禁止内联魔法值：
- `autotest_enum.py`：步骤类型/任务类型/报告类型/任务状态/执行模式/断言与比较操作/...
- `perf_enum.py`：`PerfRunMode`/`PerfLoadMode`/`PerfPresetStatus`/`PerfReportStatus`/`PerfAssertMode`/`PerfApiRole`/`PerfTargetMetric`/...
- `http_enum.py`：HTTP 方法/状态码
- `menu_enum.py`：菜单类型
- `app_enum.py`：应用级
- `base_enum_cls.py`：枚举基类（StringEnum 与 str 值等价比较）
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
- **依赖注入**：视图通过 `applications/<模块>/dependencies.py` 的 `XxxServices` 聚合获取 CRUD（`get_autotest_api_services` / `get_perf_api_services`），不要在各视图自行 new
- **路由挂载**：模块内 `views/__init__.py` 聚合并声明前缀/tags，统一由 `core/initializations/app_initialization.register_routers` 挂载
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
- 禁止循环内查库/远程请求：用批量 `__in` 查询或事务内一次处理，复用现有连接池/客户端
- 响应序列化用模型 `to_dict()`（异步方法，必须 `await`）；跨表引用优先 `*_code`

---

## 11. 数据库约定

- 所有业务表继承 `base/services/scaffold.py` 脚手架字段
- `state`：0 启用 / 1 禁用（软删除，**查询必须过滤**）
- `*_code`：由 `unique_identify()` 生成（时间戳-UUID，全局唯一）
- 跨表引用优先 `*_code`，表内定位用 `id`
- 除环境链外均为 BigInt **逻辑关联**、无物理外键，业务层校验；**禁止擅自补外键**
- 新增字段走 Tortoise Model + aerich 迁移；**禁止裸写原生 SQL**
- 报告 `report_code` 全局唯一；明细 `unique_together=(report_code, case_code, step_code, loop_cycles)`
- `krun_autotest_details` 只追加执行快照，禁止用明细数据回改步骤定义

---

## 12. 入口与启动

| 入口 | 命令 |
|------|------|
| FastAPI 开发 | `uvicorn backend.backend_main:app --reload` |
| FastAPI 生产 | `gunicorn -c backend/gunicorn.conf.py backend.backend_main:app` |
| 后端直启 | `PYTHONPATH=. python backend/backend_main.py`（从仓库根目录执行） |
| Celery worker | `bash backend/celery_deploy.sh` |
| Celery 队列 | worker `-Q` 需覆盖 `{port}_default,{port}_autotest,{port}_perf` |
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
| XML 解析/序列化 | `common/xml_utils.py` |
| autotest CRUD 聚合 | `applications/autotest/dependencies.py` |
| perf CRUD 聚合 | `applications/performance/dependencies.py` |
| autotest 数据源解析 | `applications/autotest/services/autotest_data_source_parser.py` |
| autotest 数据源装载 | `applications/autotest/services/autotest_dataset_loader.py` |
| autotest Excel 导入导出 | `applications/autotest/services/autotest_case_excel_service.py` |
| 初始菜单/路由灌入 | `core/initializations/data_initialization.py` |
| 权限规则 | `applications/base/services/permission_rule.py` |
| 数据权限范围 | `services/data_scope.py`、`enums/permission_enum.py` |
| 当前用户菜单/路由 | `applications/base/views/auth_view.py` |
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
9. 受数据权限管控的写操作：service 必传 `scope`，view 注入 `DependTagScope`（按路由标签解析）或 `DependDataScope`（按角色全局）并 `except NoPermissionException: raise`

新增页面/接口额外检查：
10. 菜单：`krun_menu` 写入/更新（component 指向 `/xxx`、keepalive、order、parent_id），否则前端无路由；菜单初始化是「表非空即跳过」，存量环境的新页面必须像 `ensure_autotest_detail_menu` 一样写幂等补建（按 parent_id + name 判定）
11. 接口：`POST /base/router/refresh` 同步 `krun_router`，核对 summary 前缀分类与角色补绑
12. 异步任务：record 写入 `task_type`、`task_summary`（含 attachments 信封），并纳入异步中心类型过滤

交付前：
13. 链路复核：改动前后行为一致，未波及其他分支
14. 边界验证：空值、非法入参、异常分支均按预期处理
15. 编译与导入冒烟：`py_compile` 必做
16. 残留检查：全局搜索被替换的旧符号、旧路径、死代码
17. 影响声明：改动文件、依赖、表结构与线上兼容性

---

## 15. 高危禁止清单

- ❌ 大规模重构 / 整模块重写
- ❌ 删除已有业务逻辑、常量、枚举（除非用户明确指令）
- ❌ 未经确认新增第三方依赖或升级版本
- ❌ 未经确认增删改已有表字段（改表必须走 aerich 并显式确认）
- ❌ 硬编码 host/port/队列名/配置值
- ❌ Celery 队列漂移
- ❌ 绕过 `core/responses` / `core/exceptions` 自造返回或错误结构
- ❌ 在循环内查库或发起远程请求
- ❌ 新增页面/接口未同步菜单与路由表即上线
- ❌ 把大二进制/压缩包写入 git 版本库

---

> 本文件由仓库结构扫描生成，作为后端 Agent 导航入口；与代码冲突时以代码为准。
> 跨端编码规范与前端链路见仓库根 `AGENTS.md`；原 `.qoder/skills/production-project-guard/SKILL.md` 为历史文档，缺失时以根 `AGENTS.md` 与本文件为准。
