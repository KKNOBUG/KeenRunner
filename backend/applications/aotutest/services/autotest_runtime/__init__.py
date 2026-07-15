# -*- coding: utf-8 -*-
"""
自动化测试运行时领域包。

按语义拆分为 exchange（提取/断言）、placeholders（占位符）、datagram（数据驱动报文）、
validation（保存期校验）、sandbox（Python 沙箱常量）等子模块；对外仍经 AutoTestToolService 门面转发。
"""
