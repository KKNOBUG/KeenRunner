# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : database_config.py
@DateTime: 2025/1/12 22:20
"""
from typing import Dict, Any

DATABASES = Dict[str, Dict[str, Dict[str, Any]]] = {
    # 无所属环境 -> 无所属单元 -> 无所属分区 -> 无分片 -> 公共数据库
    "none": {
        "none": {
            "none": {
                "xxx": {
                    "host": "10.240.37.120",
                    "port": 3306,
                    "username": "impuser",
                    "password": "Zy3306@zkk120!",
                    "database": "imp"
                }
            }
        }
    },

    # 所属环境 -> 所属单元 -> 所属分区 -> 所属分片 -> 业务数据库
    "cb_sit1": {
        # 所属单元
        "对私-rzone": {
            # 所属分区
            "dept_r01": {
                # 所属分片
                "dept_pb_00": {
                    "host": "10.240.37.120",
                    "port": 3306,
                    "username": "impuser",
                    "password": "Zy3306@zkk120!",
                    "database": "imp"
                }
            }
        }
    }
}
