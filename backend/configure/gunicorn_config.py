# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : gunicorn_config.py
@DateTime: 2025/1/12 19:41
"""
from backend import PROJECT_CONFIG

# 工作进程数量
workers = 4
threads = 4

# 使用 uvicorn 工作线程
worker_class = "uvicorn.workers.UvicornWorker"

# 绑定地址
bind = f"{PROJECT_CONFIG.SERVER_HOST}:{PROJECT_CONFIG.SERVER_PORT}"

# 所有 worker 共享应用预加载的对象
preload_app = False

# 单个 worker 最大处理请求数量
max_requests = 1000

# 设置 worker 的重启时间波动值
max_requests_jitter = 200

# 记录访问日志
accesslog = "-"

# 记录错误日志
errorlog = "-"

# 日志级别
loglevel = "info"

# 超时时间
timeout = 300
