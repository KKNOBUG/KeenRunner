# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : logger_utils.py
@DateTime: 2025/1/15 16:05
"""
import logging
import os
import threading
import time
import traceback  # 回溯模块
import typing
from logging import handlers
from datetime import datetime

from backend.configure.project_config import PROJECT_CONFIG


class LoggerUtils(object):
    """
    代码设计思想：
    1.利用logging模块构建日志收集器
    2.利用PyYaml模块读取日志配置信息，实现日志文件名称前后缀、生成频率、备份文件数量配置
    3.利用TimedRotatingFileHandler方法，实现日志文件轮转日期（支持年、月、日、时、分、秒）、日志文件备份文件数量控制
    4.利用魔术方法____new__完成单例模式，保证日志收集器不会重复实例化
    """

    # 用于存储该类的唯一实例
    __private_instance = None
    __private_initialized = False
    __private_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> object:
        """
        创建并返回类的唯一实例。

        使用单例模式，在整个应用程序的生命周期内仅创建一个 `LoggerUtils` 实例。
        在多线程环境下，通过 `threading.Lock` 确保线程安全。

        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: `LoggerUtils` 类的实例
        """
        if not cls.__private_instance and not cls.__private_initialized:
            with cls.__private_lock:
                if not cls.__private_instance and not cls.__private_initialized:
                    cls.__private_instance = super().__new__(cls)
                    cls.__private_initialized = True
        return cls.__private_instance

    def __init__(self) -> None:
        """日志收集工具类的初始化函数"""
        self.__get_setting()
        self.file_fmt = None
        self.console_fmt = None
        self.file_handler = None
        self.console_handler = None
        self.log = logging.getLogger()
        # 创建handlers之前，将已经存在的移除，再重新创建，可以防止日志重复
        while self.log.hasHandlers():
            for handler in self.log.handlers:
                self.log.removeHandler(handler)
        # 设置日志信息等级
        self.log.setLevel(level='INFO')

    def __get_setting(self) -> None:
        self.timed_rotating, self.timed_rotating_fmt = {
            "周": ["W0", "%Y-%m-%d %Uw"],
            "天": ["D", "%Y-%m-%d"],
            "时": ["H", "%Y-%m-%d %H"],
            "分": ["M", "%Y-%m-%d %H:%M"],
            "秒": ["S", "%Y-%m-%d %H:%M:%S"]
        }.get(PROJECT_CONFIG.logger_timed_rotating)
        self.file_name_prefix = PROJECT_CONFIG.logger_file_name_prefix
        self.file_name_suffix = PROJECT_CONFIG.logger_file_name_suffix
        if self.file_name_suffix:
            self.file_name_prefix += " " + datetime.now().strftime(self.timed_rotating_fmt)

        self.file_root = PROJECT_CONFIG.OUTPUT_LOGS_DIR
        self.file_path = os.path.join(self.file_root, self.file_name_prefix + ".log")
        self.backup_count = PROJECT_CONFIG.LOGGER_BACKUP_COUNT

    def console_handle(self) -> logging.StreamHandler:
        """
        创建控制台处理器
        :return:
        """
        self.console_handler = logging.StreamHandler()
        # 设置格式器
        self.console_handler.setFormatter(self.get_formatter()[0])
        # 返回作用给日志器使用
        return self.console_handler

    def file_handle(self) -> logging.FileHandler:
        """
        创建文件处理器
        :return:
        """
        try:
            # 判断是否已经生成日志文件存放目录
            if not os.path.exists(self.file_root):
                os.makedirs(self.file_root)
        except OSError:
            pass
        self.file_handler = handlers.TimedRotatingFileHandler(
            filename=self.file_path,
            # when 参数决定了何时轮转（分割）日志文件
            # W每周轮转一次日志（间隔为0表示周一，1表示周二，依此类推）
            # D每天轮转一次日志
            # H每小时轮转一次日志
            # M每分钟轮转一次日志
            # S每秒钟轮转一次日志
            when=self.timed_rotating,
            # 保留的备份日志文件的数量
            # 当超过这个数量时，最旧的备份文件将被删除
            # 默认值为 0，表示不保留备份
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        # 设置格式器
        self.file_handler.setFormatter(self.get_formatter()[1])
        # 返回作用给日志器使用
        return self.file_handler

    def get_formatter(self) -> typing.Tuple[logging.Formatter, logging.Formatter]:
        """
        创建格式器
        :return:
        """
        self.console_fmt = logging.Formatter(
            fmt='%(asctime)s --> %(filename)-20s [line:%(lineno)-3d] --> %(levelname)-5s --> %(message)s')
        self.file_fmt = logging.Formatter(
            fmt='%(asctime)s --> %(filename)-20s [line:%(lineno)-3d] --> %(levelname)-5s --> %(message)s')
        # 返回作用给控制台处理器、文件处理器使用
        return self.console_fmt, self.file_fmt

    def get_log(self) -> logging.Logger:
        """
        创建日志器并添加处理器
        :return:
        """
        self.log.addHandler(self.console_handle())
        self.log.addHandler(self.file_handle())
        return self.log


log = LoggerUtils().get_log()

if __name__ == '__main__':
    log1 = LoggerUtils().get_log()
    log2 = LoggerUtils().get_log()
    log3 = LoggerUtils().get_log()
    log1.info('提示信息')
    log2.warning('错误信息')
    log3.error('错误信息')
    try:
        int('hello world')
    except ValueError as e:
        print('在此处进行异常的处理')
        # 将错误信息写入日志文件
        log3.error(traceback.format_exc())

    time.sleep(3)
    print('测试是否被异常中断')
