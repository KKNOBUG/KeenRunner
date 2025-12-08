# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : callable_functions
@DateTime: 2025/11/12 14:34
"""


def print_hi(name):
    print(f'Hi, {name}')


if __name__ == '__main__':
    print_hi('Python')
    lst = ["application", "key", "dog", "english", "Apple"]
    sorted_lst = sorted(lst)
    print(sorted_lst)
    # 输出：['Apple', 'application', 'dog', 'english', 'key']

    lst = ["application", "key", "dog", "english", "Apple", "abc"]
    lst = ["苹果", "banana", "香蕉", "orange", "梨子", "Application"]
    sorted_lst = sorted(lst, key=str.lower)
    print(sorted_lst)
    # 输出：['Apple', 'application', 'dog', 'english', 'key']
    # （此时 "Apple" 和 "application" 按小写 "apple" 和 "application" 排序，结果同上，但逻辑不同）

