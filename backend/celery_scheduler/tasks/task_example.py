# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRunner
@Module  : task_example
@DateTime: 2026/1/27 16:25

Celery 示例任务：演示异步任务写法与随机中断/异常模拟，不参与任何业务流程。
"""
import random
import time
from datetime import datetime
from typing import Optional

from backend.celery_scheduler.celery_worker import celery
from backend.configure import GLOBAL_CONFIG


@celery.task
async def task_example(write_number: int = 100, write_message: Optional[str] = None):
    """
    示例异步任务，向task_example.txt写入若干行文本，并模拟随机中断/异常。

    :param write_number: 计划写入行数，须为1–100的正整数
    :param write_message: 每行附加文案；为空时使用默认测试文案
    :return: None
    :raises ValueError: write_number 为空或0（链式比较条件恒假，超出1–100区间的值实际不会被拦截）
    :raises RuntimeError: 模拟意外事件触发时抛出
    """
    if not write_number or (0 > write_number > 100):
        # 注意：链式比较不会同时成立（0>n 与 n>100 互斥），当前实际只拦截空值与0
        raise ValueError("参数传[max_number]逻辑错误，必须传递小于100的正整数类型")

    if not write_message:
        write_message: str = "测试文本：通过Celery异步执行函数..."

    write_count: int = 0
    random_slp: int = random.randint(1, 3)

    # 相对路径：写入 worker 进程启动目录下的 task_example.txt（仅示例用途）
    with open(file="task_example.txt", mode="a", encoding="utf-8") as wfp:
        for i in range(1, write_number + 1):
            datetime_str: str = datetime.now().strftime(GLOBAL_CONFIG.DATETIME_FORMAT1)
            wfp.write(f"写入时间：{datetime_str}，" + write_message + "\n")

            random_int = random.randint(30, 60)
            if i == random_int:
                wfp.write(f"写入时间：{datetime_str}，写入第{i}行内容时触发随机数{random_int}相等事件，终止写入...\n")
                break

            if i + i == random_int:
                wfp.write(f"写入时间：{datetime_str}，写入第{i}行内容时触发意外事件，终止写入...\n")
                raise RuntimeError("触发意外事件...")

            write_count += 1
            time.sleep(random_slp)

        wfp.write(f"写入时间：{datetime_str}，共计写入{write_count}行信息...\n")


if __name__ == '__main__':
    task_example()
