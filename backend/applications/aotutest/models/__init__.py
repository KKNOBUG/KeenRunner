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
    import json
    str1 = [{"name": "断言是否登录成功", "expr": "$.code", "operation": "等于", "expected": 0, "actual": -1, "success": False, "message": "断言[断言是否登录成功] $.code 等于 0, 实际值=-1"}]
    obj1 = json.dumps(str1, ensure_ascii=False)
    print(type(obj1), obj1)


    str2 = '[{"name": "断言是否登录成功", "expr": "$.code", "operation": "等于", "expected": 0, "actual": -1, "success": false, "message": "断言[断言是否登录成功] $.code 等于 0, 实际值=-1"}]'
    obj2 = json.loads(str2)
    print(type(obj2), obj2)
