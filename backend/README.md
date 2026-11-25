# 环境配置与部署（.env 单一配置）

> 2026-11-18 更新：全环境共用唯一配置文件 `backend/.env`（不入 git，模板见 `.env.example`），内容由环境部署负责人按目标机器手动修改，修改后重启服务生效；已删除 .env.dev/.env.test/.env.production 与 PROGRAM_ENV 环境变量机制，所有平台启动前无需设置任何环境变量。

## 1. 环境配置（所有平台一致）

```shell
# 首次部署：以 .env.example 为模板复制，并按目标机器填写实际值
cd backend
cp .env.example .env
vi .env   # 至少核对 SERVER_PORT / SERVER_DEBUG / DATABASE_* / REDIS_* / CELERY_*_DB / AUTH_SECRET_KEY / SECURITY_RSA_PRIVATE_KEY
```

- 开发（Mac/Windows）与测试/生产（Linux）都使用同一份 `.env`，仅字段值随机器不同；
- `SERVER_PORT` 同时决定 PID/日志/队列名/进程名后缀，同机多实例需错开端口，并保证 `DATABASE_NAME` 与 Celery 库号不冲突。

## 2. 启动命令

### 2.1 Linux 部署（生产推荐 full_deploy.sh 一键）

```shell
cd backend && uv sync                          # 安装依赖
# 首次上线：数据库迁移（在 backend 目录下，先预检再应用）
aerich migrate --name init
aerich upgrade
# 可选：灌入业务示例种子（应用/标签/环境，详见第 3 章；不执行不影响启动与登录）
mysql -h <host> -P <port> -u <user> -p <database> < scripts/data_initialization.sql
# 一键部署（停旧→拉取分支代码→启动 Celery Worker+Beat→启动 Gunicorn）
bash full_deploy.sh start
bash full_deploy.sh status    # 查看状态
bash full_deploy.sh restart   # 重启（不拉代码）
bash full_deploy.sh stop      # 停止

# 手动启动 Gunicorn（与 fastapi_deploy.sh 内启动命令同口径；端口以 .env 的 SERVER_PORT 为准，示例 8520）
nohup gunicorn -c gunicorn.conf.py backend_main:app \
    --pid gunicorn_8520.pid --name gunicorn_8520 \
    > backend_main_8520.log 2>&1 &
```

### 2.2 macOS / Windows 开发

```shell
cd backend && uv sync
# 使 import backend.* 可用（backend 包位于仓库根；Windows 见下方说明）
export PYTHONPATH="$(pwd)/..:${PYTHONPATH:-}"
uv run uvicorn backend_main:app --reload      # 主服务（端口由 .env 的 SERVER_PORT 决定）
# Celery（需要任务执行时，队列名按 .env 端口派生，{port} 换成实际端口）
celery -A celery_scheduler.celery_worker:celery worker \
    --pool=solo --loglevel=info -Q {port}_default,{port}_autotest,{port}_perf
celery -A celery_scheduler.celery_worker:celery beat \
    --loglevel=info --scheduler=redbeat.schedulers:RedBeatScheduler
# 前端（仓库根目录 frontend）
cd ../frontend && pnpm install && pnpm dev
```

Windows：命令一致，差异仅在 PYTHONPATH 写法——PowerShell `$env:PYTHONPATH="..;$env:PYTHONPATH"`，CMD `set PYTHONPATH=..;%PYTHONPATH%`；无需设置其他环境变量。

## 3. 种子数据初始化

### 3.1 系统必需种子（启动自动初始化，无需手动）

应用启动时由 `core/initializations/data_initialization.py` 自动初始化系统启动与前后端交互的必需项（已有数据则跳过，幂等）：

| 分类 | 表 | 内容 |
|------|-----|------|
| 菜单 | `krun_menu` | 7 目录 + 33 子菜单 + 1 一级菜单 |
| 路由 | `krun_router` | 与 FastAPI 应用 RBAC 路由同源 |
| 角色 | `krun_role` + `krun_role_menus` + `krun_role_routers` | 内置三角色（含数据范围）与菜单/路由绑定 |
| 部门 | `krun_dept` + `krun_dept_nest` | 两个初始部门与闭包表 |
| 用户 | `krun_user` + `krun_user_role` | admin/tester/guest，初始密码 `KFuser01@!`，首次登录后请立即修改 |

除上述表外无其他启动必需种子：审计/角色标签范围等表空值即可正常运行（标签范围为空时按角色默认范围生效）。

### 3.2 业务示例种子（可选，由使用方自行决定）

应用/标签/环境等业务种子**不随启动灌入**，需要时手动执行 `backend/scripts/data_initialization.sql`：

```shell
# 仓库根目录或 backend 目录均可（路径按实际位置调整）
mysql -h <host> -P <port> -u <user> -p <database> < backend/scripts/data_initialization.sql
```

- **内容**：按 5 个分类组织——应用/标签/环境字典/环境绑定/环境配置，分类编号即依赖顺序，新增种子按分类追加即可；
- **前提**：表结构已由 aerich 迁移创建，且应用至少启动过一次（负责人 admin/tester/guest 等账号由启动初始化创建）；
- **幂等**：全部语句按自然键 `NOT EXISTS` 防重，可重复执行，不覆盖已有数据；
- **不执行的影响**：仅无默认应用/标签/环境示例数据，不影响系统启动、登录与权限；
- **占位配置**：环境配置种子（UAT1-UAT3 × APP/DB/FILE）的地址/端口/凭据为占位值，执行后请按真实环境修正；
- **维护**：种子口径变更后，在仓库根目录执行 `backend/.venv/bin/python -m backend.scripts.generate_data_initialization` 重新生成 SQL。

## 4. 同机双环境部署（可选）

同机跑两个环境（如测试+生产）时，部署为**两份独立后端目录**（如 `/xxx1/project1` 与 `/xxx2/project2`，各自一套完整代码 + 各自的 `.env`）——单目录只有一份 `.env`，无法同时加载两套配置：

```shell
mkdir -p /xxx2/project2 && cp -r /xxx1/project1/* /xxx2/project2/   # 第二份完整代码
vi /xxx2/project2/backend/.env        # 按下方清单与第一份错开
```

第二份 `.env` 需要核对的字段（celery 侧无需改任何脚本，全部从 `.env` 派生）：

| 字段 | 说明 |
|------|------|
| `SERVER_PORT` | 必须不同 → 队列名 {port}_default/_autotest/_perf、PID、日志、worker 节点名自动错开 |
| `DATABASE_NAME` | 必须不同（两环境各自 MySQL 库；若 MySQL 实例也不同则 `DATABASE_HOST/PORT/USERNAME/PASSWORD` 一并对齐） |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | 建议各自独立 Redis 实例；两环境共用同一实例时，靠右列三个 Celery 库号错开（业务键无共享前纠冲突） |
| `CELERY_BROKER_DB` / `CELERY_BACKEND_DB` / `CELERY_REDBEAT_DB` | 两环境**共用同一 Redis 实例时**必须与另一环境错开（如 7/8/9 → 10/11/12）——broker 任务消息、结果后端、redbeat 调度锁都在这些库里，错开才互不干扰；**各自独立 Redis 实例时可保持相同** |
| `AUTH_SECRET_KEY` | 建议不同，避免两环境 JWT 互通 |

然后分别在各自目录执行 `bash full_deploy.sh start`（或 celery_deploy.sh + fastapi_deploy.sh），命令完全一致。

## 5. 日志文件位置（按天生成，启动复用当天）

| 服务 | 位置 / 格式 |
|------|-------------|
| 应用 | `output/logs/{YYYYmmdd}-{HHMMSS}-执行日志.log` |
| Celery | `output/logs/celery_logs/{YYYYmmdd}-{HHMMSS}-{Worker|Beat}-{端口}.log` |
| Gunicorn nohup | `backend_main_{端口}.log`（backend 根目录） |

历史日志按 `LOGGER_RETENTION_DAYS`（`.env` 可配置，默认 30 天，0=不清理）在启动时自动清理。

## 6. 环境配置密码传输加密（config_password）

环境管理 DB/Redis/File 配置的 `config_password` 采用 RSA-2048 + PKCS1 v1.5 密文传输与存储（密文即存储态，保存/查询零加解密，仅执行期建连接池时解密），契约详见 AGENTS.md 3.1。

```shell
# 1. 生成密钥对（每台部署机器独立生成，私钥不入 git）
openssl genrsa -out private.pem 2048
# PEM 转单行 base64 填入 .env 的 SECURITY_RSA_PRIVATE_KEY（与 AUTH_SECRET_KEY 隔离）
base64 -w0 private.pem          # Linux
base64 -i private.pem | tr -d '\n'   # macOS
# 公钥无需配置：后端由私钥推导，经 POST /base/security/get_public_key 下发前端

# 2. 存量明文刷库（仓库根目录；先完成扩列迁移，脚本启动会校验列宽≥512）
backend/.venv/bin/python -m backend.scripts.encrypt_env_config_passwords          # dry-run 仅打印计划
backend/.venv/bin/python -m backend.scripts.encrypt_env_config_passwords --apply  # 单事务写库，写前自动备份到 output/
# 幂等：已是密文的行跳过，可重跑；超 245 字节的明文无法单块加密，按行跳过并列入清单
```

发布顺序硬约束：后端上线（含迁移 34 扩列 128→512）→ 低峰执行刷库 → 前端上线；密钥轮换需同步重刷存量（旧私钥密文无法用新私钥解密）。

---

# 技术栈：

| 技术                 | 版本       | 作用                                                       |   
|---------------------|------------|-----------------------------------------------------------|
| Python              | 3.12.13    | 主要编程语言(项目要求 ≥3.12)                                  |
| fastapi             | 0.115.6    | 基于Starlette+Pydantic且支持OpenAPI文档的高性能异步Web开发框架   |
| gunicorn            | 26.0.0     | WSGI进程管理器(用来管理Uvicorn工作进程，实现并发+协程组合)         |
| uvicorn             | 0.33.0     | ASGI异步处理器(专门运行FastAPI&Starlette应用)                  |
| aerich              | 0.9.0      | 数据库模型迁移工具(目前是自动迁移,请了解机制后决定)                 |
| aiomysql            | 0.3.2      | MySQL异步客户端(Tortoise-ORM的异步引擎)                        |
| tortoise-ORM        | 0.25.1     | 异步ORM框架(纯异步实现,在查询和新增操作时性能较高于SQLAlchemy框架)  |
| pypika-tortoise     | 0.6.5      | 基于Pypika的SQL构建器(为Tortoise-ORM补充复杂的SQL语法支持)       |
| aiohttp             | 3.13.3     | 异步HTTP客户端(支持大量并发)                                   |
| Celery              | 5.4.0      | 分布式任务队列框架(支持异步/定时/重试任务执行)                     |
| redis               | 5.2.1      | 缓存数据库(本项目中主要用于非重要数据关联和Celery消息管理)          |
| flower              | 2.0.1      | 监控Celery异步任务执行                                        |
| loguru              | 0.7.3      | 简化的日志收集器(替代内置的logging模块)                          |


--------------------

# 项目结构

```
┌─fastapi_toolbox
│  ├─applications               - 项目下所有子应用存储目录
│  │  ├─子应用 1                 - 内置目录结构请参考base应用
│  │  ├─子应用 2                 - ...
│  │  ├─子应用 N                 - ...
│  │  ├─base                    - 子应用
│  │  │  ├─__init__.py
│  │  │  ├─crud                 - 子应用数据库操作实现文件存放目录
│  │  │  ├─models               - 子应用数据库映射模型文件存放目录
│  │  │  ├─schemas              - 子应用模型数据序列化文件存放目录
│  │  │  ├─services             - 子应用业务逻辑实现文件存放目录
│  │  └─ └─views                - 子应用视图函数实现文件存放目录
│  ├─celery_scheduler           - Celery 实现
│  │  ├─__init__.py
│  │  ├─celery_base.py          - Celery 初始化配置
│  │  ├─celery_worker.py        - Worker 实现
│  │  └─ tasks                  - 各个子应用的任务定义文件存放目录
│  ├─common                     - 总项目中的公共方法、公共组件、公共工具类等实现
│  ├─configure                  - 总项目的各个配置文件存放目录
│  ├─core                       - 核心功能和实现
│  │  ├─__init__.py
│  │  ├─decorators              - 装饰器
│  │  ├─exceptions              - 异常处理
│  │  ├─initialization          - 初始化
│  │  ├─middleware              - 中间件
│  │  └─ response               - 响应处理
│  ├─enums                      - 总项目中的枚举构造
│  ├─output                     - 总项目中的输出文件存储目录
│  │  ├─__init__.py
│  │  ├─datagram                - 业务所需要数据文件模板
│  │  ├─docx                    - 需求/开发/依赖/说明类文档
│  │  ├─download                - 下载文件
│  │  ├─jmx                     - Jmeter脚本
│  │  ├─logs                    - 日志文件
│  │  ├─media                   - 多媒体文件
│  │  ├─upload                  - 上传文件
│  │  └─ xlsx                   - 其他数据文件
│  ├─service                    - 总项目中的公共业务实现、场景实现、业务底座等
│  ├─static                     - OpenAPI文档
│  ├─celery_start.sh            - Celery Linux启动脚本
│  ├─deploy.sh                  - fastapi_toolbox Linux部署脚本
│  ├─fastapi_toolbox.py         - 项目的启动文件
│  ├─gunicorn.configuration.py  - Gunicorn进程管理器的配置文件
│  ├─README.md                  - 项目的说明文档
└─ └─requirements.txt           - 项目的依赖清单
```

# 安装依赖
```shell script
# 将项目中output\docx\fastapi_toolbox_modules.zip依赖源下载并解压
# 全部安装
pip install --no-index --find-links=本地依赖源路径 -r requirements.txt

# 部分安装
pip install --no-index --find-links=本地依赖源路径 [依赖名称(可指定版本号)]

```

# 手动部署项目
```shell script
# 服务器：10.208.24.12
# 切换到项目根目录：
cd /zdhgj/python_projects/fastapi-toolbox/

# 查询进程：
ps aux | grep gunicorn
ps aux | grep python

# 终止进程：
pkill -f -9 "fastapi_toolbox:app"

# 拉取代码：
git pull origin fastapi-dev-master
> username
> password

# 启动进程
nohup gunicorn -c gunicorn.configuration.py fastapi_toolbox:app > /zdhgj/python_projects/fastapi-toolbox/fastapi-toolbox.log 2>&1 &
```

# 自动部署项目
```shell script
# 查看脚本权限：
ls -al

# 修改脚本权限：
chmod -R 777 deploy.sh

# 运行脚本
./deploy.sh


用户执行: ./deploy.sh full_deploy
    │
    ▼
┌─────────────────┐
│  1. fastapi_stop │  ← 停止 FastAPI (Gunicorn)
│     - 读取 gunicorn.pid
│     - kill -TERM (优雅停止)
│     - 等待15秒
│     - 未退出则 kill -9
│     - 清理残留 worker 进程
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. celery_stop  │  ← 停止 Celery
│     - celery_stop_beat (先停调度器)
│     - celery_stop_worker (后停工作器)
│     - 同样 TERM → KILL 渐进式
│     - 清理残留进程
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   sleep 2       │  ← 等待资源释放
│   (关键!)        │    确保端口/文件句柄释放
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. fastapi_pull │  ← 拉取最新代码
│     - 检查 git/expect 命令
│     - 检查 GIT_USERNAME/GIT_PASSWORD
│     - expect 交互式 git fetch
│     - git reset --hard 强制覆盖
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. celery_start │  ← 启动 Celery
│     - celery_start_worker (先启工作器)
│     - celery_start_beat (后启调度器)
│     - nohup + & 后台启动
│     - 等待10秒检测启动状态
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. fastapi_start│  ← 启动 FastAPI
│     - nohup + & 后台启动 Gunicorn
│     - 等待15秒检测启动状态
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. fastapi_status│ ← 显示 FastAPI 状态
│     - 运行状态/PID/Worker数/日志大小
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. celery_status │ ← 显示 Celery 状态
│     - Worker/Beat 状态/日志大小
└─────────────────┘
```



# 启动Celery Worker服务
```shell script
# celery_scheduler是专用于Celery的Worker实现

# Celery Worker Windows环境启动（Windows没有POSIX信号和Forx事件，因此只能单线程，网上说的可以借助gevent或eventlet实现协程池，但没效果）
celery -A celery_scheduler.celery_worker worker --pool=solo -l INFO

# Celery Worker Linux环境启动
celery -A celery_scheduler.celery_worker worker --pool=solo -c 10 -l INFO

```

# 启动Celery Beat服务
```shell script
# Celery Beat启动节拍器，定时任务需要
celery -A celery_scheduler.celery_worker beat --loglevel=info --scheduler=redbeat.schedulers:RedBeatScheduler

```

# 接口路径与行为规范

接口的「行为」由**路径末段动词**决定，不再看 summary。新增/改名接口必须遵守，否则启动日志会输出 ERROR（不阻断启动，但必须纠正）。

## 1. 判定规则（`common/permission_action.py` 的 `derive_action`）

1. `DELETE` 方法一律判为「删除」；
2. 路径末段按 `_` 分词，取**位置最后的已知动词**决定行为（`query_export` → 导出，`export_query` → 查询）；
3. `GET` 方法无动词时回落为「查询」；
4. 其余方法（POST/PUT/PATCH）无动词则为 `unknown`：不进审计、不参与资源域判定，并在启动时输出 ERROR。

## 2. 动词表（一个动词只归属一种行为）

| 行为 | 动词 |
|------|------|
| 新增 | `create`、`add`、`copy`、`duplicate`、`generate`、`register` |
| 更新 | `update`、`save`、`move`、`pin`、`bind`、`unbind`、`transfer`、`authorized`、`reset`、`assign`、`enable`、`disable` |
| 删除 | `delete`、`deletes`（批量）、`remove`、`clear`、`logout`、`revoke` |
| 上传 | `upload`、`import`、`parse` |
| 下载 | `download`、`export` |
| 执行 | `run`、`start`、`stop`、`debug`、`debugging`、`execute`、`compare`、`precheck`、`test`、`connection`、`login` |
| 查询 | `search`、`list`、`get`、`query`、`validate`、`build`、`read`、`fetch` |
| 运维 | `refresh` |

新增动词需同时改 `VERB_ACTIONS` 与本文表格。

## 3. 资源族（`enums/resource_enum.py` 的 `ResourceTag`）

路由 `tags` 的 label 必须能在 `ResourceTag` 注册表中精确命中（如 `自动化测试:用例` → `autotest.case`），否则视为未登记：不参与内置角色自动绑定，且启动时输出 ERROR。新增业务模块时先登记资源族，再挂路由。

## 4. 认证模式（`core/initializations/permission_contract.py`）

| 模式 | 路由依赖 | 是否写 `krun_router` | 说明 |
|------|----------|----------------------|------|
| 公开 | 无 | 否 | 登录等无需令牌接口 |
| 仅认证 | `DependAuth` | 否 | 当前用户自身操作（改密、登出、菜单、权限键） |
| 权限 | `DependPermission` | 是 | 参与角色绑定与审计 |

管理员专属接口在权限模式上再叠加 `DependSuperUser`，契约标记 `available_only_admin`：不自动绑定给非管理员角色，角色保存时忽略该分配，刷新时回收残留。

认证执行链路：`auth_middleware` 先认证（非白名单），RBAC 在路由依赖 `DependPermission` 中完成；认证结果缓存在 `request.state.current_user`，同一请求的中间件/依赖/审计只查一次用户表。所有业务接口必须携带有效登录令牌，不再接受任何开发阶段临时令牌。

## 5. 自检

- 启动日志出现 `[权限契约]` / `[权限规则]` ERROR：按本规范修正路径或登记资源族；
- 新增/改名接口后执行 `POST /base/router/refresh`，并确认日志无契约告警、角色补绑符合预期。

