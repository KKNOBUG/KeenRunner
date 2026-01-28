# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : task_example
@DateTime: 2026/1/27 16:25
"""
import random
import time
from datetime import datetime
from typing import Optional

from celery_scheduler.celery_worker import celery
from configure.global_config import GLOBAL_CONFIG


@celery.task
async def task_example(write_number: int = 100, write_message: Optional[str] = None):
    if not write_number or (0 > write_number > 100):
        raise ValueError("参数传[max_number]逻辑错误，必须传递小于100的正整数类型")

    if not write_message:
        write_message: str = "测试文本：通过Celery异步执行函数..."

    write_count: int = 0
    random_slp: int = random.randint(1, 3)

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