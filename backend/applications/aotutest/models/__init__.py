# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : __init__.py
@DateTime: 2025/11/9 11:57
"""


def print_hi(name):
    print(f'Hi, {name}')


if __name__ == '__main__':
    print_hi('Python')


def unique_identify() -> str:
    import datetime
    import uuid
    timestamp = int(datetime.datetime.now().timestamp())
    uuid4_str = uuid.uuid4().hex.upper()
    return f"{timestamp}-{uuid4_str}"


print(unique_identify())
