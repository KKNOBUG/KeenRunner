# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : configparser_utils.py
@DateTime: 2025/1/15 16:00
"""
import configparser
import os
import typing


class ConfigparserUtils:
    """
    配置文件工具类封装
    1.检查指定的section节点是否存在
    2.获取所有的section节点
    3.刷新config对象，避免数据更新不同步
    4.获取指定section节点下所有选项（key）
    5.获取指定section节点下option选项对应的值（value）
    6.获取指定section节点下所有的option选项和对应的值
    7.更新指定section节点下option选项对应的值（value），如果option选项不存在，则会新增
    8.新增指定section节点，内容以字典形式编写（key-value），节点名称另外指定，可以指定文件写入模式（追加或覆盖）
    9.删除指定section节点
    """

    def __init__(self, path: str) -> None:
        """
        对象初始化函数，在创建类对象时调用
        :param path:
        """
        self.path: str = path
        self.config = self.__acquire_config_object()

    def __get__(self) -> configparser.RawConfigParser:
        return self.config

    def __acquire_config_object(self) -> configparser.RawConfigParser:
        """
        获取配置文件读取对象(私有方法)
        :return: 配置文件处理对象
        """
        __config = configparser.RawConfigParser()
        if os.path.exists(self.path):
            __config.read(filenames=self.path, encoding='utf-8')
            return __config
        else:
            raise FileNotFoundError(f"加载[{self.path}]配置文件失败！")

    def has_section(self, section) -> bool:
        """
        检查指定的section节点是否存在
        :param section: 节点名称
        :return: 如果节点存在则返回True，否则返回False
        """
        return section in self.acquire_all_section()

    def acquire_all_section(self) -> typing.List[str]:
        """
        获取所有的section节点
        :return: 以列表形式返回配置文件中所有的节点名
        """
        return self.config.sections()

    def refresh_config_object(self) -> None:
        """
        刷新config对象，重新加载配置文件，防止缓存
        :return:
        """
        self.config = self.__acquire_config_object()

    def acquire_all_option(self, section) -> typing.List[str]:
        """
        获取指定section节点下所有选项（key）
        :param section: 节点名称
        :return: 以列表形式返回指定节点下所有的选项（key）
        """
        return self.config.options(section)

    def acquire_section_option(self, section: str, option: str) -> str:
        """
        获取指定section节点下option选项对应的值（value）
        :param section: 节点名称
        :param option:  节点选项（key）
        :return:
        """
        self.config.get(section, option)
        # 检查section节点是否存在
        if not self.has_section(section):
            raise KeyError(f"上送节点[{section}]不存在！")
        # 检查section节点下是否存在option选项
        if option not in self.acquire_all_option(section):
            raise KeyError(f"上送选项[{option}]不存在！")

        return self.config.get(section, option)

    def acquire_all_section_option(self, section: str) -> typing.Dict[str, str]:
        """
        获取指定section节点下所有的option选项和对应的值
        :param section: 节点
        :return: 以列表形式返回指定节点下的所有选项（key）
        """
        try:
            return {K: V for K, V in self.config.items(section)}
        except configparser.NoSectionError:
            raise configparser.NoSectionError(f"上送节点[{section}]不存在！")

    def update_section(self, section: str, option: str, value: str) -> bool:
        """
        更新指定section节点下option选项对应的值（value），如果option选项不存在，则会新增option选项和对应的值（value）
        :param section: 节点名称
        :param option:  选项名称
        :param value:   新数据
        :return:
        """
        try:
            self.config.set(section, option, value)
            with open(file=self.path, mode='w', encoding='utf-8') as f:
                self.config.write(f)
            return True
        except configparser.NoSectionError:
            raise configparser.NoSectionError(f"上送节点[{section}]不存在！")

    def create_section(self, dictionary: dict, section: str, mode: str = "a", new_path: str = None) -> bool:
        """
        新增指定section节点，内容以字典形式编写（key-value），节点名称另外指定，可以指定文件写入模式（追加或覆盖）
        将数据字典转换成config对象并写入文件
        :param mode:        写入文件方式（追加或覆盖）
        :param dictionary:  数据字典
        :param section:     节点名称
        :param new_path:    保存地址（如不指定，则保存在实例化对象时给的文件）
        :return:
        """
        if self.has_section(section=section):
            raise KeyError("节点已存在")
        try:
            __path = self.path if new_path is None else new_path
            __config = configparser.RawConfigParser()
            __config[section] = dictionary
            with open(file=__path, mode=mode, encoding="UTF-8") as file_object:
                __config.write(file_object)
            return True
        except Exception as e:
            raise Exception(f"出现未知错误：{e}")

    def delete_section(self, section: str) -> bool:
        """
        删除指定section节点
        :param section: 节点名称
        :return:
        """
        # 刷新config对象，防止缓存导致内容不一致
        self.refresh_config_object()
        # 如果section节点不存在，则返回False
        if not self.has_section(section=section):
            return False
        # 执行删除
        self.config.remove_section(section)
        # 重新写入
        with open(file=self.path, mode="w", encoding="utf-8") as file:
            self.config.write(file)
        return True


if __name__ == '__main__':
    config = ConfigparserUtils(path='')

    print(config)  # <__main__.ConfigparserUtils object at 0x7fea6005eb50>
    print(type(config))  # <class '__main__.ConfigparserUtils'>
    print(type(config.__get__()))  # <class 'configparser.RawConfigParser'>

    print("获取所有节点：", config.acquire_all_section())
    print("获取指定节点下指定选项的值：", config.acquire_section_option("mysql@imp", "host"))
    print("获取指定节点下所有选项：", config.acquire_all_option("mysql@imp"))
    print("获取指定节点下所有选项和值（k-v）：", config.acquire_all_section_option("mysql@imp"))

    # 修改节点
    # config.update_section("mysql@imp", "port", "11111")
    # config.update_section("mysql@imp", "new_key", "new_value")
    # 添加节点
    # config.create_section({"demo1": "demo1"}, "Single", "a")
    # 删除节点
    # print(config.delete_section("Single"))
