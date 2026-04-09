# 技术栈：

| 技术                 | 版本       | 作用                                                       |   
|---------------------|------------|-----------------------------------------------------------|
| Python              | 3.8.7      | 主要编程语言(Windos 7 最高支持Python 3.8.10)                  |  
| fastapi             | 0.115.4    | 基于Starlette+Pydantic且支持OpenAPI文档的高性能异步Web开发框架   |
| gunicorn            | 23.0.0     | WSGI进程管理器(用来管理Uvicorn工作进程，实现并发+协程组合)         |
| uvicorn             | 0.32.0     | ASGI异步处理器(专门运行FastAPI&Starlette应用)                  |
| aerich              | 0.7.2      | 数据库模型迁移工具(目前是自动迁移,请了解机制后决定)                 |
| aiomysql            | 0.2.0      | MySQL异步客户端(Tortoise-ORM的异步引擎)                        | 
| tortoise-ORM        | 0.23.0     | 异步ORM框架(纯异步实现,在查询和新增操作时性能较高于SQLAlchemy框架)  |
| pypika-tortoise     | 0.3.2      | 基于Pypika的SQL构建器(为Tortoise-ORM补充复杂的SQL语法支持)       |
| aiohttp             | 3.9.5      | 异步HTTP客户端(支持大量并发)                                   | 
| Celery              | 5.4.0      | 分布式任务队列框架(支持异步/定时/重试任务执行)                     |
| redis               | 5.0.8      | 缓存数据库(本项目中主要用于非重要数据关联和Celery消息管理)          |      
| flower              | 2.0.1      | 监控Celery异步任务执行                                        |
| loguru              | 0.7.2      | 简化的日志收集器(替代内置的logging模块)                          |


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

