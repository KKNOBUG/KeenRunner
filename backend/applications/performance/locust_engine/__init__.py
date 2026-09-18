# -*- coding: utf-8 -*-
"""
性能测试施压引擎子包(由 locust CLI 子进程直接加载运行)。

红线约束: 本包内所有文件禁止 import backend 主包 —— 子进程加载时避免拉起
Tortoise-ORM/项目配置/logging等主进程设施, 也不与 locust 的 gevent 环境互相污染;
依赖仅允许标准库与 locust/requests/orjson/jsonpath_ng。

占位符渲染、来源提取与断言比较语义独立实现, 与 autotest_runtime 的
resolver/extractors/assert_compare 保持一致, 一致性由对齐测试锁定;
调整任一侧时必须同步评估另一侧。

@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2026/9/14 14:40
"""
