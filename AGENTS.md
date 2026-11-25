# KeenRunner — Agent 仓库手册

> 本文件是 AI Agent 与新成员理解全仓的唯一权威手册，同时是代码评审（Standards 轴）的基准；随代码同步维护。
> 仓库定位：**生产在运**的接口自动化 + 性能压测一体化平台（前后端分离）。
> 规则裁决顺序：用户显式指令 > 高危禁止清单（第 15 章） > 仓库现状 > 文档。代码是最终事实源：与代码冲突时先以代码确认边界，再回写本文件。

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

**前端 `frontend/`（JavaScript 工程，无 TS）**：Vue3 Composition API（`<script setup>`）+ Naive UI + pinia + vue-router + vue-i18n；Vite 构建；pnpm 管依赖；sass + UnoCSS；编辑器用 monaco/codemirror、表格用 luckysheet。

---

## 2. 顶层目录结构

```text
backend/
├─ backend_main.py          # FastAPI 应用入口（lifespan/路由注册/中间件/异常）
├─ gunicorn.conf.py         # gunicorn 部署配置
├─ celery_deploy.sh         # Celery worker + beat 启停脚本（只管 Celery）
├─ fastapi_deploy.sh        # FastAPI 部署脚本（只管 Gunicorn：start 含强制拉取 GIT_BRANCH，restart 不拉取）
├─ pyproject.toml           # uv 依赖与项目元数据
├─ requirements.txt         # pip 兼容依赖清单
├─ uv.lock                  # uv 锁定文件
├─ .env / .env.example       # 环境配置文件（.env 不入 git，内容由环境部署负责人手动修改，PROJECT_CONFIG 驱动）
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
│  └─ logging_config.py     # loguru 配置
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
├─ migrations/models/       # aerich 迁移产物（版本文件以目录现状为准）
├─ scripts/                 # 运维/迁移/修复脚本（pending 迁移、回填、mode 合并、aerich 对齐等）
├─ static/                  # 静态资源（avatar/pythonHelpDoc/redoc/swagger-ui）
└─ output/                  # 运行时产物（download/logs/jmx/upload 等不入 git；template/ 为部署模板资产）

frontend/
├─ build/ settings/ i18n/   # 构建常量、布局开关、国际化
└─ src/
   ├─ api/                  # 接口集中（src/api/index.js），统一走 request 工具
   ├─ composables/          # useXXX hooks（复杂页面逻辑必须拆到这里）
   ├─ directives/           # v-permission 等全局指令
   ├─ layout/               # 侧边栏/头部/页签/KeepAlive 容器
   ├─ router/               # 基础静态路由 + 守卫；业务路由由后端菜单动态生成
   ├─ store/                # pinia：user/permission/tags/autotest/app
   ├─ constants/ utils/ styles/
   └─ views/                # 页面组件；autotest 模块是全站样式基准模板
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
- 辅助：`tag`、`case_transfer`

**核心执行链路**：
```
views/autotest_task_view.py (/autotest/task/run)
  → apply_async(run_autotest_task)  # task_routes 路由到 {port}_autotest
  → celery_scheduler/tasks/task_autotest_case.py (_run_autotest_task_impl)
  → AutoTestStepCrud.batch_execute_cases  # batch_code；任务级串行/并行；用例内轮次×数据场景
  → AutoTestStepExecutionEngine.execute_case  # 七元组：results/logs/report_code/statistics/session_variables/defer_create_report/pending_create_details
  → 写 report + details、回填 case/task 状态；执行观测写 record(task_summary)
```

**用例执行状态回写口径（case_state）**：`execute_single_case` 仅负责单场景报告/明细落库，是否回写用例状态由 `update_case_state` 控制（默认 True）。多轮调用方（`_execute_one_case` 的执行次数×数据场景、`task_execute_assign_case._execute_step_tree_impl` 的参数化逐场景）一律传 `update_case_state=False`，全部轮次结束后经 `finalize_case_execute_state` 按「全部轮次成功才成功」一次聚合回写 `case_state` 与 `case_last_time`（取最后一轮报告快照），避免最后一个成功数据场景覆盖中间失败场景的状态（last-write-wins 缺陷）；单用例异常兜底同样回写失败。单次执行（view 直跑、参数化单场景、`perf_job_service` fail-fast）保持默认 True 在事务内直接回写。每条数据场景仍各自生成独立报告，报告级 `case_state` 只反映本场景成败，与用例级聚合状态互不覆盖。

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
- 报告读模型：`/report/search`（手工报告）、`/report/search_task_batches`（task_code 批次）、`/report/search_batch_scripts`（batch_code 脚本维度）、`/report/search_script_round_reports`（batch_code+case_id+round_no）、`/report/search_batch_reports`；报告明细树由 `/detail/search_tree` 后端组装。
- 列表页与删除入口：报告 `/report/search`、执行明细 `/detail/search`（菜单 `/autotest/detail`）、执行记录 `/task/record/search`（菜单 `/task/record`）、异步中心（同执行记录接口 + `task_type_in` 过滤）；四页均支持列表多选批量删除，行级删除按钮按后端回传的 `can_delete` 控制。

**环境配置命名约定（config_mode）**：
- `config_mode` 是同应用、同节点类型（app/file/database/redis）下的**跨环境逻辑唯一键**：同组各环境实例共享一个 mode，`config_name` 是组内展示名（同组必须一致）；步骤/压测按 `request_config_mode` 定位配置；步骤与压测接口的旧名称列已随迁移 32 删除，仅明细快照 `krun_autotest_details.request_config_name` 与步骤 DB/Redis 的 `operates.config_name` 保留（展示与未回填兜底）。
- 创建与改名：四个 `/autotest/config/{app|file|database|redis}/create|update` 共用 `AutoTestEnvConfigCrud.create_config`/`update_config`。创建先 `_lock_project_type_binds` 锁定同（应用 + 节点类型）全部启用绑定行（`only("id")`、主键升序 `FOR UPDATE`），再由 `_resolve_config_mode` 解析：同维度已有同名（忽略大小写）启用实例则复用其 mode 并统一为组内既有写法，仅命中空标识行就地补齐（LOGGER.warning），未命中生成 `unique_identify()`；锁等待后的快照读能看到先到者写入的 mode，并发创建不会分裂出两组。改名由 `_sync_config_mode_group_name` 在同一事务内锁定同 mode 启用行并预检冲突：唯一键按环境绑定独立，仅**同环境（同绑定）内**存在同名配置（**含软删记录，软删行占用 `UNIQUE(env_bind, config_name)`**）时拒绝并点出环境；目标名被其他环境占用时与创建同口径复用该组 mode 与组内写法，当前配置**并入**该逻辑组（只改当前行，原组其余实例保留旧名；仅软删行占用时沿用其标识，避免恢复后同名分裂出第二组），并入后该环境引用旧 mode 的步骤/任务需重新选择；目标名未被占用时批量同步同组启用实例改名（mode 不变、引用零影响），软删行不参与改名；不同节点类型/不同应用互不影响，同步不区分配置创建人；死锁 1213/锁超时 1205 统一转 `DataBaseStorageException`。
- 删除引用校验：`_assert_configs_not_referenced` 按 mode 匹配步骤 `request_config_mode`、压测接口 `perf_api.request_config_mode`（同应用启用接口一次查询）与步骤 DB/Redis 的 `database_operates/redis_operates.config_mode`；DB/Redis 操作内未回填的 `config_name` 按同应用名称兜底（步骤与压测旧名称列已在迁移 32 删除）；同 mode 的多环境实例按传入 id 逐个删除，其余实例保留。
- 母子表职责：`/autotest/env/create|update` 维护母表绑定（所属应用 + 环境名称 + 节点类型），`update` 允许改 `env_name`/`env_desc`/`project_id`；换应用由 `_move_env_to_project` 处理——存在启用配置直接拒绝，仅软删配置时按目标应用重新解析 mode/写法后迁移；`env_type` 由创建时确定。配置 create 以 `project_id/env_name/env_type` 经 `_get_or_create_env_bind` 解析绑定（不存在则创建、软删则恢复），传入的 `env_id` 不参与落库，`env_name` 不落配置表、`project_id/env_type` 作为冗余维度随写入回填；update 以 `config_id/config_code` 定位，`project_id/env_type` 仅做归属一致性校验并回填、`env_name` 不参与更新；`config_name` 在 create/update 均由服务层入口 strip 后拒绝纯空白（schema 只约束必填，前端校验不能替代服务层）。删除环境由 `_assert_envs_not_referenced` 校验启用配置与任务引用：`task_involve_env_ids` 精确匹配优先，`cases_execute_config` 的环境名称仅作存量兜底。
- 读取契约：`/autotest/env/query` 返回 `project_id → env_id(数字字符串) → 节点类型 → config_mode → {config_name, 主机信息}`，入参为 `config_modes`；`get_envs` 叶子统一为 `{env_id, env_name}`（value 用绑定 ID，名称仅展示）；`/autotest/config/*/config_names` 返回 `[{config_name, config_mode}]` 且只含启用配置。`list_env_names` 经启用绑定过滤，未被任何绑定引用的孤儿字典不泄漏。
- host/port/database_name 只有实际变化时才重做唯一性校验（host 不是数据库唯一键）；名称未变由唯一索引兜底，不再重复查名。更新不再解析环境名或重建绑定。改名**不级联**步骤与压测引用：读取按 mode 定位（步骤与压测旧名称列已删除，未回填 mode 的存量行执行期报配置缺失）；任务 `cases_execute_config` 只存 `{env_id, config_type, config_mode}` 引用键，执行期实时解析地址；任务保存后该快照即执行期权威，步骤随后改选配置不影响已存任务，需重新保存任务才会刷新。
- 执行期解析：`StepsExecuteConfigBase` 只含 `{env_id, config_type, config_mode}` 引用键；`AutoTestStepExecutionEngine.execute_case` 执行前调 `StepExecutionContext.preload_execute_configs` 固定 2 次查询（配置行按 `config_mode IN`、绑定按 `id IN`），执行器只读 `ResolvedStepExecuteConfig` 快照（名称/主机/端口/库名），缺失按设计 6.4 文案报错（空引用报 `参数[request_config_mode]不能为空`，缺失报 `执行配置缺失: 配置[名称] 在环境[环境名]的[节点]节点下不存在`）；明细写解析名称 `request_config_name` + 逻辑标识 `request_config_mode`；DB/Redis 建池/建客户端走 `*_by_mode`（四层缓存键含 host/port，改地址立即生效）；报告 `involve_envs` 由 `env_bind_index`（env_id→名称）生成。单步调试（HTTP/TCP/Redis）入参统一 `env_id + request_config_mode`，Redis 顶层 `env_id` 必须是 REDIS 节点绑定、跨应用 operate 按同名环境反查绑定；HTTP 绝对地址不依赖配置。执行弹窗与任务 `cases_execute_config` 已切换为引用键结构；步骤与压测接口的旧名称列已删除，明细快照字段保留（展示层专用）。
- 数据库步骤库名不落快照：`database_operates[]` 以 `config_mode` 为执行引用、`config_id` 为库名展示引用（指向 `krun_autotest_env_config` 行，仅前端反显、不参与执行；旧 `database_name` 字段已移除、不再接受）；前端「数据库名称」下拉按 `config_id` 反显库名，未选或引用失效时展示同 mode 库名合集作为参考，执行期库名一律取环境配置解析值。

**环境配置密码密文契约（config_password）**：
- 传输与存储均为 RSA-2048 + PKCS1 v1.5 密文（base64 后固定 344 字符）：前端 jsencrypt 只加密密码字符串本身（非信封，无时间戳/nonce）；**密文即存储态**——保存期仅格式校验（`assert_cipher_format`：base64 可解 + 344 字符 + 解码 256 字节）拒明文后原样入库，查询原样回传（`serialize_config` 不做加解密），仅执行期建 DB/Redis 连接池时解密（`common/database/database_connection_pool.py`、`common/cache/redis_connection_pool.py` 函数内惰性导入 `backend/services/transport_crypto.py`，避免 common 层循环依赖）。
- 密钥：私钥 `.env` 的 `SECURITY_RSA_PRIVATE_KEY`（PEM 单行 base64，与 `AUTH_SECRET_KEY` 完全隔离）；公钥由私钥推导，接口 `POST /base/security/get_public_key`（`security_self` 仅认证契约，不进 RBAC、不可被角色绑定；路径动词 get 保证推导为 READ 不落审计）；前端公钥懒加载 + Promise 内存缓存（`frontend/src/utils/crypto/index.js`，直连 `@/utils/http` 避免循环导入），解密失败报错时清缓存重拉。
- 列宽 `config_password` VARCHAR(512)（迁移 34）；前端新输入明文限 64 字符且 UTF-8 ≤245 字节（RSA 单块上限）；密码框无小眼睛，maxlength=64（框内不再程序回填整段密文）。
- 更新语义：DB 更新未传/None=不修改（已从 `explicit_restored_null_fields` 移除），空串拒绝（DB 密码不允许清空）；File/Redis 免密走 `is_no_password=true` + 空串；Redis schema 的 `is_no_password` 自 Base 继承。
- 前端单态交互（`EnvConfigModal.vue`）：`form.config_password` 唯一数据源，真实密文仅存 `originalCipher` 快照；未修改时密码框展示固定 8 圆点哨兵（`PASSWORD_MASK`，避免整段密文圆点过长），空/哨兵=未修改；聚焦清空/失焦还原；编辑未改密码不传该字段，复制场景密文透传零重输；新输入保存时才加密。
- 存量刷库：`scripts/encrypt_env_config_passwords.py`（默认 dry-run，`--apply` 单事务 + 写前备份到 output/，含软删行，幂等可重跑，启动先校验列宽≥512）；发布顺序硬约束：后端上线（含迁移）→低峰刷库→前端上线。

**调试模式**（不落库，顺序严格对齐执行模式）：
```
views (/http_debugging, /tcp_debugging, /redis_debugging)
  → services/autotest_step_debug_service.py (StepDebugService.debug_http/debug_tcp/debug_redis)
  → inject_builtin_variables_for_debug → resolve_env_config_by_mode(env_id + config_mode) → 占位符替换 → 发请求返回
```

**TCP 测试服务器管理**（/autotest/tcp_test/*）：视图 `views/autotest_tcp_test_view.py` 仅薄路由层，实现下沉 `services/autotest_tcp_test_service.py`（`TcpTestServerService` 静态门面 + `TcpTestServerManager` 声明式端口编排 + mock/帧诊断服务器），内置端口组合与启动入参在 `schemas/autotest_tcp_test_schema.py`；挂在独立的 `autotest_public` 蓝图（`applications/autotest/views/__init__.py`），不并入 `autotest`、不挂权限依赖，启动契约判定为 public 不参与 RBAC 路由收集；认证由 `auth_middleware` 白名单 `* /autotest/tcp_test/*` 放行，无需用户认证；审计仍按行为分类落库（无 Token 时 user_id=0）。

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
- 场景独立编辑页唯一保存入口 `save_wizard`：事务内 upsert scene + diff upsert presets（新增/更新/软删）；`batch_duplicate_presets` 同样同事务批量派生，任一项失败整体回滚。负载预设对外序列化口径（排除脚手架字段、主键对外为 `preset_id`）统一走 `PerfLoadPresetCrud.serialize_preset`，列表/详情/向导回包共用。

**环境配置引用（与 autotest 同口径）**：
- `perf_api.request_config_mode` 定位 APP 配置（编辑页下拉 value=mode，旧名称列已删除）；调试入参 `env_id + env_config_mode`，接口自身 mode 优先、调试入参兜底，HTTP 绝对地址不依赖配置。
- `/perf/scene/precheck`、`/perf/load_preset/*` 请求结构保持名称（D 级契约）：`perf_env_binding.py` 在服务层一次性换算为 `(env_id, config_mode)`（预检按应用缓存），执行地址按接口 mode 优先、预设缺省配置回退；报告快照保留名称。

**视图路由**：`/perf/api/*`、`/perf/scene/*`、`/perf/load_preset/*`、`/perf/report/*`、`/perf/comparison/*`、`/perf/dataset/*`、`/perf/job/*`、`/perf/analysis/*`

### 3.3 base — 基础设施

- `models/`：audit（审计）、menu（菜单）、role（角色）、router（路由）
- `services/`：
  - `scaffold.py`：**所有业务表继承的脚手架**（id/state/created_time/updated_time/created_user/updated_user/reserve_1~3）+ `unique_identify()` 生成 `*_code`
  - `permission_rule.py`：内置角色接口放行规则（资源域 × 行为）与补绑/管理员专属回收
  - `*_crud.py`：菜单/角色/路由/审计 CRUD
- `views/`：menu、role、router、audit、file_transfer；登录与当前用户接口在 `applications/user/views/user_view.py`（`user_public`/`user_self`/`user_secure` 三个路由）
- `Role` 含数据权限三字段：`select_scope`（可见范围，默认 DEPT_AND_CHILD）、`update_scope`（可写范围，默认 SELF）与 `delete_scope`（可删范围，默认 SELF），即角色默认范围；标签级覆盖见 `RoleTag`（`krun_role_tags`），详见 4.5。
- 内置角色码统一定义在 `enums/role_enum.py` 的 `BuiltinRoleCode`（`Administrators` / `Users` / `Guests`），判断逻辑用 `BuiltinRoleCode.includes_admin(role_codes)`，禁止在业务代码里散落角色码字符串。
- 删除语义：角色单删与批量删除均为**物理删除**（`krun_role` 无 `state` 字段）；管理员角色不可删除；存在未删除用户绑定（`krun_user_role`，该表为级联外键，删角色会静默清空用户权限）时整体拒绝，单删与批量删除口径一致。

### 3.4 user / department / toolbox

- `user/`：用户模型 + CRUD + 视图；单删与批量删除均为**软删除**（`state=1` 并递增 `token_version` 吊销 Token）；`/user/update` 仅在显式传 `role_ids` 时重建角色绑定，局部更新（如调岗）不清空既有授权。登录与当前用户自身接口收在 `user_view.py`：公开 `POST /user/login`、`POST /user/transfer_login`；仅认证 `POST /user/get_userinfo`、`POST /user/menu/list`、`POST /user/get_user_routers`、`POST /user/update_password`（不做 RBAC 鉴权，也不能被角色绑定）；`POST /user/logout` 为公开幂等登出，由中间件可选认证，有效 Token 吊销全部会话，失效或无 Token 不修改用户数据并返回成功。
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

- `app_middleware.py`：应用级日志与审计；仅 `AUDITED_ACTIONS`/`unknown` 落库，查询透传；取用户复用认证缓存，不再重复查库。
- `auth_middleware.py`：非白名单请求统一先认证，**不做 RBAC**（RBAC 在路由依赖 `DependPermission`）；Token 认证失败返回真实 HTTP 401，响应体仍保留统一业务码与明细，其余异常记录 `LOGGER.error` 后返回 500（不能用 401，否则前端会误登出）；白名单仅登录、根路径、docs、static 与 TCP 测试服务器管理（`* /autotest/tcp_test/*`），`POST /user/logout` 单独使用可选认证白名单，失效凭证仅幂等放行登出，不能访问其他业务接口。
- `request_context_middleware.py`：请求上下文（用户/租户注入）
- 认证结果请求级缓存：`AuthControl.is_authed` 命中 `request.state.current_user` 时只重建 `CTX_USER_ID`/`CTX_USERNAME` 不查库；Starlette `BaseHTTPMiddleware` 与端点共享同一 `scope["state"]`，中间件 → 路由依赖 → 审计三处调用只查一次用户表。
- 令牌校验：`is_authed` 只接受登录签发的 JWT，`jwt.decode` 以 `options={"require": ["exp","user_id","token_version"]}` 强制校验，缺任一声明或签名/过期/版本不符一律 401；不存在开发阶段临时令牌旁路。

### 4.4 初始化（core/initializations/）

- `app_initialization.py`：`register_database` / `register_exceptions` / `register_middlewares` / `register_routers`
- `permission_contract.py`：启动时为每个路由绑定一次权限元数据（资源族/行为/认证模式/管理员专属），运行期只读，详见 4.6
- `data_initialization.py`：启动时自动初始化系统必需种子（菜单/路由/角色/部门/用户及绑定表，已有数据则跳过；角色种子含数据范围：管理员 ALL/ALL/ALL，标准用户与宾客 DEPT_AND_CHILD/SELF/SELF，存量库启动时校正管理员三范围为 ALL）；业务种子（应用/标签/环境）不随启动灌入，由使用方按需手动执行 `scripts/data_initialization.sql`（5 分类、自然键幂等），口径变更后由 `scripts/generate_data_initialization.py` 重新生成，详见 backend/README.md 第 3 章

### 4.5 数据权限（services/data_scope.py）

- 枚举：`enums/permission_enum.py` 的 `DataScopeEnum`（`ALL / DEPT_AND_CHILD / DEPT / SELF`）。
- 模型：`Role.select_scope`（可见，默认 DEPT_AND_CHILD）/`Role.update_scope`（可写，默认 SELF）/`Role.delete_scope`（可删，默认 SELF），aerich 自动迁移；`RoleTag`（表 `krun_role_tags`，唯一键 `role_id + tag`，同名字段承载标签级覆盖，字段为空表示按角色默认范围生效）
- 资源锚点：视图注册统一 `tags=[ResourceTag.X.desc]`（禁止手写中文字面量），启动时由 `bind_route_contracts` 精确匹配成 `route.resource`，`DependTagScope` 只读该契约，**不做 URL 前缀推断**；未声明或未登记归入 `legacy`。`ResourceTag` 的 code（如 `autotest.case`）是持久化与判定的唯一口径，`desc` 仅用于路由 tags 与展示；`RoleTag.tag` 存 code，与运行期解析同源，中文名由 `ResourceTag.label_of` 转出。
- 可配置范围：`ResourceTag.scope_aware=True` 的资源族才进入「标签范围」配置（当前为 `application.project/env/env_config/tag`、`autotest.case/report/detail`、`task.task`）；步骤与数据源无独立归属，范围跟随所属用例，不单独配置；其写校验统一走 `assert_case_writable`（按 `autotest.case` 资源族同时校验可读与可写），禁止用自身 `STEP`/`DATASET` 标签判定；新增资源族若要参与数据权限，必须同时接入 `DependTagScope` 与归属字段过滤后再置 `scope_aware=True`，否则不展示，避免生成配置了却不生效的空项。
- 解析：`DataScope.from_user` 超管与管理员角色（`BuiltinRoleCode.ADMIN`）固定三范围全部数据；其余用户按标签两层解析「标签覆盖 > 角色默认范围」，逐字段回落，多角色取最宽，再解析为**部门ID集合**（`read/write/delete_depts`，`None` 表示不限，空集表示仅本人）。部门范围按归属人**当前部门**动态解析：`DEPT` 取本部门，`DEPT_AND_CHILD` 借闭包表 `DeptStruct` 展开；不再把部门成员展开为内存集合，避免大部门下超大 IN。
- 写/删 ≤ 读：运行期 `_clamp_to_read` 收敛，保存期 `RoleCrud._assert_tag_scope_order` 用 `scope_covers` 拒绝超出可见范围的配置；未显式设置的字段按角色默认范围参与校验，避免“回读显示默认值、运行期被收敛”的不一致。
- 使用：`read_q(owner_field)` 产出列表过滤 `Q`：本人等值 OR 部门成员子查询（`LEFT(UPPER(TRIM(username)),16)`，与 `normalize_username` 同源），SQL 长度与部门人数无关；`can_read/can_write/can_delete(owner)` 按归属人当前部门判定，**调用前必须 `await scope.load_owners(owners)` 预取**（单条传单个归属人，批量在循环前一次传全集，未预取按不在范围处理并告警）；`for_tag(tag)` 按父资源族重解析；`DataScope.system()` 表示任务执行、引擎回写等内部可信路径。视图经 `DependTagScope` 注入，单请求只解析一次。列表响应在 view 层为每行注入 `can_delete`（`scope.can_delete(归属人)`），前端按钮显隐直接采用，禁止按归属人自行比对（部门范围无法在前端复算，且部分列表已排除 `created_user`）。
- 父资源可读校验（B 级）：`services/autotest_scope_guard.py` 的 `load_readable_project`/`assert_parent_readable` 校验所属项目/环境对当前用户可读，接入用例/任务/标签/环境/环境配置的创建与配置更新。
- 写校验约定：service 写方法（create/update/delete/copy 及子资源写入）将 `scope: DataScope` 设为必填参数，越权抛 `NoPermissionException`；只读查询可 `Optional` 缺省仅供内部可信路径，不得从视图透传缺省；view 注入 scope 并在 `except Exception` **之前**加 `except NoPermissionException: raise`，否则异常被吞。
- 权限载体：角色是唯一权限载体，菜单（`krun_role_menus`）、接口（`krun_role_routers`）与标签范围（`krun_role_tags`）都挂在角色上；新建角色默认零绑定，必须由管理员显式配置。
- 管理员角色：`Administrators` 与超管同权，`/user/menu/list`/`/user/get_user_routers`/`PermissionControl.has_permission`/`DependSuperUser`/`DataScope` 均运行期直接全量放行，不依赖绑定记录；其角色编码不可修改、角色不可删除、绑定不可保存（`/base/role/authorized` 直接返回参数提示）。
- 管理员入口：`GET/POST /base/role/authorized` 在原有菜单/路由之外增删 `tag_scopes`（每项 tag=资源族编码 + tag_label 展示名 + 三范围，空值=按角色默认）；菜单、接口与标签范围同属一次授权，统一由 `RoleCrud.save_authorization` 先全量校验、再单事务重建三张关联表；两个方向都叠加 `DependSuperUser`，非管理员不可读也不可写。
- 审计：`common/permission_action.py` 的 `derive_action` + `AUDITED_ACTIONS` 为唯一分类源，`permission_rule.py` 与 `app_middleware.py` 共用；中间件对新增/更新/删除/执行/上传/下载落库，**刷新(ops)与查询直接透传**（下载响应仅记 `<FILE DOWNLOAD>` 占位符，不复制文件流）。行为由路径末段动词判定（见 4.6），新增接口必须让路径末段带已知动词，否则既不进审计也会被契约校验告警。
- 报告/明细写接口：HTTP `create/update` 加 `DependSuperUser`，仅超管、管理员角色或执行引擎可直调；引擎内部经 service 直写不走 HTTP。
- 内置角色接口绑定：Guests 业务域（应用/自动化/任务/工具）全部放行（含执行/调试/上传/下载），系统域只读；接口放行不代表可删他人数据，删除归属由 service 层 `can_delete` 兜底。
- 归属字段：用例用 `owner_user`（转让后变更，转让始终仅当前所属人本人可操作）；步骤与数据源以所属用例 `owner_user` 为准；项目/标签/环境绑定/环境配置/任务/报告/明细/执行记录用 `created_user`；环境字典（`krun_autotest_env`）是全局共享纯词典，只存 `env_name/env_code`，无归属、软删状态、审计与预留字段，所有应用共用且无行级过滤。
- 删除语义矩阵：
  - **全物理删除**：审计日志（单删/批量/按用户/按时间）、测试报告（单删 `/report/delete` + 批量 `/report/deletes`，两路径均同事务级联删除明细）、执行明细（单删 `/detail/delete` + 批量 `/detail/deletes`）、异步中心与执行记录（同一资源，单删 `/task/record/delete` + 批量 `/task/record/deletes`，仅允许删除终态并清理产物）。报告/明细/执行记录的批量入口均按「全有或全无」校验，按 `report_codes` 删除与按 `report_ids` 等义。
  - **单删物理 + 批量软删**：应用（`autotest/project`）、标签、环境、环境配置、用例、步骤。两条路径都拒绝存在引用关系的数据：应用→用例/标签/环境绑定/环境配置/任务；标签→用例 `case_tags`；环境→环境配置/任务环境引用（`task_involve_env_ids` 精确匹配，名称快照兜底）；环境配置→步骤的请求配置/数据库/Redis 操作；用例→公共用例被引用步骤。用例单删连带物理删除其步骤，批量删除连带软删除其步骤；步骤无独立批量删除入口。
  - 批量删除一律「全有或全无」：先全量校验行级 `can_delete` 与引用关系，再单次落库，禁止边校验边删除导致部分成功。
  - 步骤树保存（`/autotest/step/update_or_create_tree`）的淘汰步骤为**物理删除**（含 IF 分支缩减的子步骤），并同步清理数据源与数据生成记录；同一用例内 `step_no` 必须唯一（前端按全树前序统一编号）。
- 读过滤边界：资源列表/下拉/聚合查询与报告/明细批次下钻（`batch_code`、`report_code` 明细树）均按对应资源族 `read_q` 收窄；步骤列表按父用例 `owner_user` 过滤，步骤树/单条步骤按父用例可见性校验；用例列表对公共用例（`PUBLIC_CASE_TYPES`）放行。
- 不参与：性能压测模块。

### 4.6 接口契约与认证模式（core/initializations/permission_contract.py）

- 启动时 `bind_route_contracts` 给每个 `APIRoute` 绑定 `resource`（`enums/resource_enum.py` 的 `ResourceTag`，按 tag label 精确匹配）/`action`/`auth_mode`/`available_only_admin`；运行期消费方只读契约，不再解析 tags、路径或 summary。
- 认证模式按路由级依赖判定：含 `DependPermission` → permission（写 `krun_router`、参与角色绑定）；含 `DependAuth` → self（仅认证，不下发角色）；都无 → public。公开与仅认证接口不进入权限体系。`krun_router` 只存 path/method/summary/tags/available_only_admin，资源族编码由启动契约 `route.resource` 承载，不落库副本（避免与枚举漂移）。
- 路径即行为契约：路径末段按 `_` 分词后取**位置最后的已知动词**，归入 `新增/更新/删除/上传/下载/执行/查询/运维` 八组（`common/permission_action.py` 的 `VERB_ACTIONS`）；DELETE 一律删除，GET 无动词回落查询，其余方法无动词为 `unknown`。
- `validate_route_contracts` 对「资源族未登记」「路径末段缺已知动词」输出 **ERROR 日志但不阻断启动**，`PermissionRule.warn_unclassified_routers` 在刷新路由时按同一规则告警；开发者必须修正，禁止长期留存 unknown。
- 管理员专属接口在 `DependPermission` 之外叠加 `DependSuperUser`：契约标记 `available_only_admin`，内置角色自动绑定跳过，`RoleCrud.save_authorization` 忽略该分配，刷新时 `PermissionRule.drop_available_only_admin_bindings` 回收非管理员角色上的残留。`DependSuperUser` 声明在 include_router、路由装饰器或视图参数任一处均可被识别（`_route_dependency_funcs` 递归遍历 `route.dependant`）。当前为 `GET/POST /base/role/authorized`、`POST /base/router/refresh` 与报告/明细写接口 `POST /autotest/report/create|update`、`POST /autotest/detail/create|update`（共 7 条）。`available_only_admin` 只影响权限配置面，运行期放行由 `DependSuperUser` 决定，禁止手改库中该字段。

---

## 5. 配置（configure/）

**配置一律来自环境文件 → `PROJECT_CONFIG`，禁止硬编码 host/port/队列名/配置值。**

- 环境配置 `.env`：全环境共用唯一文件（不入 git，内容由环境部署负责人按目标机器手动修改，修改后重启服务生效）；`.env.example` 为字段模板；禁止按字段名/主机/端口推断环境
- `project_config.py`：直接加载 `backend/.env` 构建 `PROJECT_CONFIG` 单例（APP_TITLE/SERVER_HOST/SERVER_PORT/...）；维护脚本固定读 `backend/.env`，部署脚本从 `.env` grep `SERVER_PORT`（PID/日志/队列/进程名均按该端口区分）
- `celery_config.py`：队列名 = `{port}_default` / `{port}_autotest` / `{port}_perf`（端口前缀派生）；`task_routes` 统一路由
- **同机多实例共存（端口主线）**：部署脚本的 PID 文件（`gunicorn_{port}.pid`、`celery_worker_{port}.pid`、`celery_beat_{port}.pid`）、nohup 日志（`backend_main_{port}.log`，应用日志按天复用见 logging_config 条目）、worker 节点名（`worker_{port}@%h`）与 gunicorn 进程名（`--name=gunicorn_{port}`）全部携带 `SERVER_PORT` 区分，停止/状态/强制清理（force_kill）仅匹配 `{port}` 模式，禁止不经端口过滤按 cwd 清理进程；Celery broker/backend/redbeat 三个 Redis 库号由 `.env` 配置（同机多实例各自 `.env` 错开即可），redbeat 锁随各自库天然隔离；同机部署还需保证各实例 `DATABASE_NAME` 不同
- `database_config.py`：MySQL 连接
- `logging_config.py`：loguru 格式与轮转；日志文件按天复用——应用日志 `output/logs/{YYYYmmdd}-{HHMMSS}-执行日志.log`（gunicorn 各 worker 经 `resolve_daily_log_path` 命中同一文件，多进程共写靠 ConcurrentRotatingFileHandler 跨进程锁），Celery 日志 `output/logs/celery_logs/{YYYYmmdd}-{HHMMSS}-{Worker|Beat}-{port}.log` 同口径；`LOGGER` 仅绑定 Loguru 引用不产生初始化副作用，应用进程由 `backend_main.py` 显式调 `loguru_logging()`、Celery 由 `setup_loggers` 安装专属 sink（禁止再让 Celery 往「执行日志」写入）；启动时按 `LOGGER_RETENTION_DAYS`（环境文件可配，默认30）以 mtime 清理过期日志/滚动备份/孤儿锁

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
- 配置驱动池管理器（`DBConnPoolFromConfig`/`RedisConnPoolFromConfig`，进程单例）生命周期契约：`get_or_create_*` 经 loop 感知异步锁串行建池（锁内 double-check，Celery 换 loop 自动重建锁）；`*_by_mode` 四层缓存键含 host/port，改地址命中新键后旧键池/客户端空闲时自动淘汰、忙时保留待回收；测试连接 `close_coordinate` 即用即关（不波及执行期 mode 池）；FastAPI lifespan 关停与 Celery `worker_process_shutdown` 统一 `close()` 释放
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
- `resource_enum.py`：权限资源族（code/label/domain，`ResourceTag` 单一事实源）
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
- **依赖注入**：视图通过 `applications/<模块>/dependencies.py` 获取 CRUD，不要在各视图自行 new；聚合形式为 dataclass `XxxServices` 加 `get_xxx_services()`（`AutoTestServices` / `PerfServices`），注入别名统一 `Depend` 前缀（`DependAutoTestServices` / `DependUserServices`），视图以默认值注入 `xxx_crud: XxxCrud = DependXxxServices`，不逐端点写 `Depends(get_xxx_crud)`
- **路由挂载**：模块内 `views/__init__.py` 聚合并声明前缀/tags，统一由 `core/initializations/app_initialization.register_routers` 挂载
- **业务不进 views、model 逻辑不进 schemas、后端业务不下沉前端**
- **目录约束**：新增文件放入同业务模块既有目录，禁止新建未出现过的顶层目录

---

## 10. 编码准则（动手前必读）

以下准则约束新增与被修改代码，不据此重构存量代码。

### 10.1 现有风格画像
- 服务文件用分区注释加分区内函数组组织；常量与枚举按业务分组集中声明
- 业务操作按读写分离到 `*_crud.py`；视图只编排、不写业务；模型逻辑不进 schemas
- 写操作收敛单一入口：新增写操作挂到该资源既有 Crud/Service 入口
- 异常经 loguru 记录（`LOGGER.error` 加 `traceback.format_exc()`）后返回统一 `FailureResponse`
- 新增函数标注全部参数 type hint 与返回类型；入参经 Pydantic schema 校验
- 数据与逻辑分离：常量、注册表、配置映射独立声明，不内联在业务函数里
- 响应序列化用模型 `to_dict()`（异步方法，必须 `await`）；跨表引用优先 `*_code`
- 禁止循环内查库/远程请求：用批量 `__in` 查询或事务内一次处理，复用现有连接池/客户端

### 10.2 结构分清主次
- 主函数只保留主干流程：定位、校验、执行、落库的动作序列一眼可读
- 校验逻辑下沉子函数：分支多、判断冗长的校验抽为独立函数，主函数只留调用与异常语义
- 主干中禁止平铺大段 if/raise：同类判断出现三次以上即视为主干被污染，必须下沉

### 10.3 严谨、高内聚、低耦合
- 一个函数只承担一个业务动作；跨模块依赖走既有 service/crud 入口，不穿透他人表
- 事务边界由调用方进入：锁、事务、幂等恢复在同一入口内闭环，不把半程状态暴露给调用方
- 功能必须高度稳定：新增分支要覆盖失败路径（异常类型、事务回滚、软删恢复、并发冲突），不能只验证成功路径
- 数据流单向：入口校验后的数据在内部视为已定型，下游不再二次清洗

### 10.4 校验与防御边界
- 外部输入只在入口校验一次（Pydantic schema 加服务层入口的必要兜底）；内部已定型的数据禁止重复判空、strip、类型转换与嵌套检查
- 禁止滥用 try/except：只捕获可归因的具体异常（如 `IntegrityError`/`OperationalError`）并转换为统一业务异常，不写捕获后原样抛出的空壳
- 禁止无证据的防御代码：没有实锤证据、概率极低、触发后影响面极小、几乎不会发生的竞态问题，不加锁、不重试、不双检、不写兜底分支
- 确需防御时先给出证据（复现路径、日志、设计约束）、风险与代价，征得同意后再写，并在代码注释写明依据
- 真实存在的路径不豁免：唯一键冲突、并发死锁、软删恢复冲突按既有异常体系转换并记录，不得吞掉

### 10.5 抽象与复用
- 逻辑简短、仅单次调用、无复用价值的函数不强行抽函数，直接内联在主干流程
- 允许破例：校验逻辑分支多、判断冗长、严重污染主函数可读性时，抽成一次性校验子函数
- 一次性校验子函数的 docstring 必须标注固定说明：单次调用，仅用于主干解耦，无复用意图
- 反向约束：出现第二处调用即提升为通用函数并删掉一次性标注；禁止为将来可能用到预留参数或扩展点

### 10.6 docstring 与注释
- 每个函数编写 reStructuredText 风格 docstring 块：功能概述加 `:param:`、`:return:`、必要的 `:raises:` 字段
- 功能概述只写一句话事实描述，不使用星号、反引号、方括号、花括号、引号书名号等装饰或标注符号、引用英文单词不使用空格；字段参数只写含义，不写冗余解释
- 功能概述与 `:param:` 之间只允许一个空行，禁止插入第二段补充解释；实现细节（缓存、事务、预取、降级、匹配规则）写入对应参数/返回值说明或行内注释
- 返回结构复杂时在 `:return:` 中给出键位说明，不展开示例代码
- 难懂、反直觉、复杂的代码块写一行直白准确的注释说明为什么这样做；简单代码不写注释
- 注释解释为什么与意图，不复述代码做了什么；修改代码时同步剔除历史淘汰内容与不再准确的注释

### 10.7 命名、测试、依赖与独立判断
- 命名见名知意并跟随仓库既有命名，禁止随意缩写；特殊变量（缓存键、复合键、快照结构）写一行目的注释
- 测试优先跑真实逻辑（真实库、真实接口、真实 Celery 链路），少用 mock；mock 仅用于外部不可控依赖
- 不引入仓库原本不存在的工具或依赖；确需引入先给出理由与替代方案对比，征得同意后再行动
- 保持独立判断：结论必须核对来源（代码、实测、日志）；发现需求与事实冲突直接指出错误并说明潜在风险
- 主动提示未考虑到的风险：变量影响、改造成本、行为偏差、破坏性变更（含线上兼容与数据不可逆）

### 10.8 后端专项约束
- 容器式字段与步骤类型变更必须四处同步：model 注释、schema 定义、执行引擎、前端 `useStepTreeSerialization.js`；遗漏任一处即断链
- 修复以根因为主：禁止持续打补丁、留存历史淘汰痕迹；拒绝死代码与透传函数，不为用不到的扩展预留字段
- 配置一律来自环境文件（backend/.env 单一文件）→ `PROJECT_CONFIG`，禁止硬编码 host/port/队列名/配置值
- 接口与页面的同步动作（`POST /base/router/refresh`、`krun_menu` 写入）按第 14 章检查清单执行

### 10.9 错误提示文案（面向用户）
- 未预期异常兜底统一为「暂时无法{动作}{对象}，请稍后重试」：不叠加「失败」、不写「暂时无法完成{动作}」、不在句末追加「请刷新页面」等第二建议
- 可归因的业务失败写「{动作}失败, {原因}」：如「登录失败，请稍后重试」「新增失败, 用户已存在」「旧密码验证失败」
- 记录不存在写「未找到[{字段}={值}]的{对象}记录，请稍后重试」
- 同一资源族的动作与对象用词固定（新增/删除/更新/查询 加 用户信息/用户密码/访问令牌），不出现「获取用户数据」「完成创建」等虚动词
- 文案不暴露实现细节：表名、SQL、异常类名、堆栈、密码与令牌
- 真实异常与关键字段只进 `LOGGER.error`，对外文案与日志文案分开维护

---

## 11. 数据库约定

- 所有业务表继承 `base/services/scaffold.py` 脚手架字段
- `state`：0 启用 / 1 禁用（软删除，**查询必须过滤**）
- `*_code`：由 `unique_identify()` 生成（时间戳-UUID，全局唯一）
- 跨表引用优先 `*_code`，表内定位用 `id`
- 除环境链外均为 BigInt **逻辑关联**、无物理外键，业务层校验；**禁止擅自补外键**
- 新增字段走 Tortoise Model + aerich 迁移；**禁止裸写原生 SQL**
- 配置逻辑标识迁移链（历史，已完成）：29 占位 → 30 回填列级 request_config_mode → 31 收紧 NOT NULL + 索引 → 32 删除 step/perf_api 旧名称列；迁移不覆盖的存量缺口（任务 cases_execute_config 引用键化、步骤 operates 键化（DB 的 database_name 按 mode+旧库名唯一命中回填 config_id 展示引用，同 mode 多环境库名不同不猜测）、明细 request_config_mode 回填、空 config_mode 生成等）由 `scripts/repair_legacy_config_data.py` 统一纠正：krun/tbx 两端通用（读各自 backend/.env，表前缀按 {prefix}_autotest_task 自动探测，缺表自动降级），默认 dry-run，--apply 单事务+写前备份，幂等；无法解析的引用不猜测，任务整体排除待人工；明细 operates 为独立快照契约（index/env_name/config_name/database_name 必填，与步骤定义 schema 不同），不在键化改造范围；今后迁移一律走 aerich migrate + aerich upgrade
- 报告 `report_code` 全局唯一；明细 `unique_together=(report_code, case_code, step_code, loop_cycles)`
- `krun_autotest_details` 只追加执行快照，禁止用明细数据回改步骤定义

---

## 12. 入口与启动

| 入口 | 命令 |
|------|------|
| FastAPI 开发 | `uvicorn backend.backend_main:app --reload` |
| FastAPI 生产 | `gunicorn -c backend/gunicorn.conf.py backend.backend_main:app` |
| 后端直启 | `PYTHONPATH=. python backend/backend_main.py`（从仓库根目录执行） |
| Celery worker | `bash backend/celery_deploy.sh`（PID/日志/节点名按 .env 端口隔离） |
| Celery 队列 | worker `-Q` 需覆盖 `{port}_default,{port}_autotest,{port}_perf` |
| FastAPI 部署 | `bash backend/fastapi_deploy.sh start`（停止 → fetch+reset 强制拉取 GIT_BRANCH → 启动 Gunicorn；restart 不拉取；Celery 另由 celery_deploy.sh 启动） |
| 依赖安装 | `uv sync`（或 `pip install -r requirements.txt`） |
| 迁移 | 在 `backend/` 下 `aerich migrate` 生成迁移文件 + `aerich upgrade` 应用；对齐/登记问题用 `scripts/repair_aerich_alignment.py`（`--help` 查看用法） |
| 存量配置数据纠正（krun/tbx 通用） | `python -m backend.scripts.repair_legacy_config_data`（读 backend/.env，前缀自动探测，默认 dry-run，确认后加 `--apply`；第三方同构项目直接复用） |

---

## 13. 关键文件速查

| 用途 | 路径 |
|------|------|
| FastAPI 应用入口 | `backend_main.py` |
| 项目配置 | `configure/project_config.py` |
| Celery 配置 | `configure/celery_config.py` |
| 统一响应 | `core/responses/` |
| 异常体系 | `core/exceptions/` |
| 脚手架基类 | `applications/base/services/scaffold.py` |
| XML 解析/序列化 | `common/xml_utils.py` |
| autotest CRUD 聚合 | `applications/autotest/dependencies.py` |
| perf CRUD 聚合 | `applications/performance/dependencies.py` |
| autotest 数据源解析 | `applications/autotest/services/autotest_data_source_parser.py` |
| autotest 数据源装载 | `applications/autotest/services/autotest_dataset_loader.py` |
| autotest Excel 导入导出 | `applications/autotest/services/autotest_case_excel_service.py` |
| 系统必需种子（启动自动） | `core/initializations/data_initialization.py` |
| 业务示例种子（可选执行） | `scripts/data_initialization.sql`（生成器 `scripts/generate_data_initialization.py`） |
| 存量配置数据纠正 | `scripts/repair_legacy_config_data.py`（krun/tbx 两端通用，前缀自动探测） |
| 权限规则 | `applications/base/services/permission_rule.py` |
| 数据权限范围 | `services/data_scope.py`、`enums/permission_enum.py` |
| 当前用户菜单/路由 | `applications/user/views/user_view.py` |
| 接口契约绑定/校验 | `core/initializations/permission_contract.py` |
| 资源族枚举 | `enums/resource_enum.py` |
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
7. 配置一律来自环境文件 → `PROJECT_CONFIG`，禁止硬编码
8. Celery 队列名统一，`apply_async` 不得硬编码 queue
9. 受数据权限管控的写操作：service 必传 `scope`，view 注入 `DependTagScope`（按路由绑定的资源族编码解析）并 `except NoPermissionException: raise`

编码质量（细则见第 10 章）：
- 主函数只留主干，冗长校验下沉子函数；一次性子函数带固定标注
- 外部输入只在入口校验，内部数据不重复判空、strip、嵌套 try
- 无证据的低概率风险不加防御代码；确需添加先给证据、风险与代价
- docstring 用 reST 块且无装饰符号，概述单句、不写第二段解释，改动后剔除过时注释
- 提示文案按 10.9 口径：兜底「暂时无法…」、业务失败「…失败, 原因」、未找到「未找到[字段=值]…」
- 测试优先真实逻辑；新工具或依赖先申请

新增页面/接口额外检查：
10. 菜单：`krun_menu` 写入/更新（component 指向 `/xxx`、keepalive、order、parent_id），否则前端无路由；`path` 允许跨父级重复，但**同父级唯一**（`uid_krun_menu_parent_path`，重复会让前端注册出同 URL 路由、后注册者不可达），`menu_crud` 创建/更新（含换父）先做同级预校验、`(name, path)` 唯一索引保留做同名幂等；菜单初始化是「表非空即跳过」，存量环境的新页面必须像 `ensure_autotest_detail_menu` 一样写幂等补建（按 parent_id + name 判定）
11. 接口：`POST /base/router/refresh` 同步 `krun_router`，路径末段必须带已知动词（启动日志无契约 ERROR），并核对角色补绑结果
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
- ❌ 无证据的防御代码（低概率竞态加锁/重试/双检）与重复校验（内部数据反复判空、strip、滥捕异常）
- ❌ 仅单次调用且无复用价值的强行抽函数；一次性校验子函数缺少固定标注
- ❌ docstring 功能概述堆砌装饰符号，或保留历史淘汰内容与失准注释
- ❌ 用 mock 替代可直接跑的真实逻辑；未经确认引入仓库外工具或依赖

---

## 16. 前端关键链路与规范

### 16.1 关键链路

- **动态路由/权限**：`main.js` → `setupRouter` → `/user/menu/list` 生成菜单路由 + `/user/get_user_routers` 生成接口权限键；菜单组件路径为 `/src/views{component}/index.vue`，KeepAlive 的 `include` 匹配 `defineOptions({name})`，即菜单名必须与组件名一致。
- **用例编辑保存**：用例列表 → `/autotest/steps?case_id&case_code` → `/autotest/step/tree` → 前端树编辑/校验 → **先保存数据源**（新步骤无 `step_code` 时跳过）→ `useStepTreeSerialization.buildUpdateOrCreateTreePayload` → `/autotest/step/update_or_create_tree` → 用 `success_detail` 回写 `step_id/step_code`，被跳过的数据源在拿到 `step_code` 后补存。离开页签由 `useDirtyCheck` 拦截。

### 16.2 开发规范

- Vue3 `<script setup>` 组合式 API；复杂页面逻辑拆到 `composables/useXXX.js`。
- 业务路由不是手写静态表：由 `/user/menu/list` 下发菜单动态生成，组件按 `/src/views{component}/index.vue` 解析；新增页面必须同步菜单记录，页面 `defineOptions({name})` 与菜单名一致（KeepAlive 的 include 依赖它）。
- 接口权限键统一 `apiPermissionKey(method, path)`（`method + VITE_BASE_API + path`），按钮级用 `v-permission`；超管与管理员角色直通。
- 行级删除显隐用 `userStore.canDeleteData(owner, can_delete)`：优先采用列表接口注入的 `can_delete`（后端按当前资源族的删除范围判定，含部门范围），缺失时回落归属账号比对；autotest 共享编辑不再按写入范围隐藏编辑入口。批量删除统一经 `composables/useBatchDeleteGuard` 的 `pickDeletableIds` 按同一结论过滤后再提交，避免整批被后端拒绝。
- 接口权限显隐统一用 `composables/useApiPermission` 的 `hasApiPermission(method, path)`（或 `v-permission` 指令）；受限角色不应看到必然 403 的新增/批量删除/导入导出/下载按钮。角色表单的范围选项复用 `src/constants/dataScope.js`。
- 请求统一走 `src/api/index.js` 与现有 request 工具，禁止新封装 axios 实例。成功判定为 `code === '000000' && status === 'success'`；HTTP 401 或认证业务码触发 `clearSession` 本地清理并跳转登录页，不能再调用 `/logout` 形成循环请求；主动退出调用 `/logout` 后在 `finally` 清理本地会话。文件下载用裸 axios（带 token）+ `downloadBlobResponse`，不要套默认响应拦截器。
- 弹层/表格/表单等复用现有通用组件与 Naive UI 组件，不重复造轮子。
- 模态框视觉基线：`NModal preset="card"` 根节点用 `:global(.modal-class.n-card)` 声明圆角令牌、`corner-shape: squircle` 与 `overflow: hidden`（Teleport 后根节点无 scoped 属性）；嵌套卡片栏头自身保持 `border-radius: 0`，顶部由父卡片统一裁切，左下/右下保持直角，禁止再叠 `clip-path` 或独立圆角。
- 模态框颜色与排版：颜色使用 Naive UI 主题变量并适配深色（info 色系深色用 `--info-color-suppl`）；标题用强调色，说明文字用 11px 主题灰，卡片内容底部留白与表单项间距保持一致（8px）。结构调整后同步删除无用 import、模板类、选择器与变量。
- 样式治理：`views/autotest` 是统一样式基准；基础 UI 样式优先复用 `styles/autotest-theme.scss` 全局类（`.step-editor-card`、`.log-item`、`.debug-loading` 等）；禁止在 scoped 样式里重复定义全局已有样式；多页面相似样式必须上收到全局基线并加作用域前缀。
- 注释为中文、简短说明意图。

---

## 17. 交付与质量要求（每次改动）

1. 交付说明：改动文件列表；是否新增依赖（无则写明）；是否改表（无则写明）；线上兼容性说明。
2. 质量自检：链路复核（前端页面 → api → view → service → 数据库/Celery → 前端反馈）、空值/异常分支、后端 py_compile/导入冒烟、旧符号零残留；前端至少通过 `pnpm build`（或等价的编译检查）。
3. 明细表（details）只追加执行结果快照，禁止用明细数据回改步骤定义；软删字段 `state` 查询必须过滤。
4. 文档同步：链路、接口契约、菜单/权限、队列、模板资产等约定变化时，同步更新本文件，避免文档滞后于代码。
5. 部署资产：`backend/output/template/*.xlsx` 是运行时模板资产，需随代码交付/同步（该目录下其余下载、日志、上传产物不入 git）。
6. 迁移顺序约束（历史，已完成）：29 占位 → 30 回填 mode → 31 收紧 NOT NULL + 索引 → 32 删除 step/perf_api 旧名称列；配套维护脚本已删除，存量环境均已迁移完成；新变更一律在 `backend/` 下 `aerich migrate` 生成迁移文件并 `aerich upgrade` 应用，对齐/登记问题用 `scripts/repair_aerich_alignment.py` 修复。

---

> 本文件是仓库唯一权威手册，随代码同步维护；与代码冲突时先以代码确认边界，再回写本文件。
> 性能压测、明细树等补充设计见 `backend/性能测试*设计.md` 与 `backend/执行明细树结构展示需求文档.md`，与代码冲突时以代码为准。