# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : yaml_utils.py
@DateTime: 2025/1/15 10:49
"""
import json
import os.path
from typing import Dict, Any

import yaml


class YamlUtils:

    def __init__(self, abspath: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abspath: str = abspath
        self.config_data: dict = self.load_yaml_data()

    def __str__(self, *args, **kwargs):
        return json.dumps(self.config_data, ensure_ascii=False)

    def load_yaml_data(self) -> Dict[str, Any]:
        """
        加载 YAML 配置文件并返回数据字典。

        :return: 配置数据字典。
        :raises FileNotFoundError: 如果文件不存在，将引发异常。
        :raises yaml.YAMLError: 如果 YAML 文件格式错误，将引发异常。
        """
        try:
            with open(file=self.abspath, mode="r", encoding="utf-8") as file:
                return yaml.safe_load(file) or {}
        except FileNotFoundError as e:
            raise FileNotFoundError(f"配置文件[{self.abspath}]不存在：{e}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 文件格式错误：{e}")

    def get_value(self, path: str) -> Any:
        """
        根据给定路径获取配置值。

        :param path: 配置值的路径，使用点分隔符。
        :return: 返回对应的配置值，如果路径无效则返回 None。
        :raises TypeError: 如果 path 不是字符串，将引发异常。
        """
        if not isinstance(path, str):
            raise TypeError("path 必须是字符串")

        keys: list = path.split(".")
        current_dict: dict = self.config_data

        for k in keys:
            if k in current_dict:
                current_dict: Any = current_dict[k]
            elif k.isdigit() and (0 <= int(k) < len(current_dict)):
                current_dict: Any = current_dict[int(k)]
            else:
                return None

        return current_dict

    def update_value(self, path: str, value: Any) -> Any:
        """
        更新指定路径的配置值。

        :param path: 配置值的路径，使用点分隔符。
        :param value: 要更新的值。
        :return: 更新后的配置数据字典。
        :raises TypeError: 如果 path 不是字符串，将引发异常。
        """
        if not isinstance(path, str):
            raise TypeError("path 必须是字符串")

        keys: list = path.split(".")
        current_dict: dict = self.config_data

        for k in keys[:-1]:
            if k not in current_dict:
                current_dict[k]: dict = {}

            current_dict: Any = value

        current_dict[keys[-1]]: Any = value

        return self.config_data

    def delete_value(self, path: str) -> Any:
        """
        删除指定路径的配置值。

        :param path: 配置值的路径，使用点分隔符。
        :return: 删除后的配置数据字典。
        :raises TypeError: 如果 path 不是字符串，将引发异常。
        """
        if not isinstance(path, str):
            raise TypeError("path 必须是字符串")

        keys: list = path.split(".")
        current_dict: dict = self.config_data

        for k in keys[:-1]:
            if k in current_dict:
                current_dict: Any = current_dict[k]
            else:
                return None

        if keys[-1] in current_dict:
            del current_dict[keys[-1]]

        return self.config_data

    def save_yaml_data(self):
        """
        将当前配置数据保存到 YAML 文件中。

        :raises FileNotFoundError: 如果文件路径无效，将引发异常。
        """
        if not os.path.exists(self.abspath):
            raise FileNotFoundError(f"配置文件[{self.abspath}]不存在")

        with open(file=self.abspath, mode="w", encoding="utf-8") as file:
            yaml.safe_dump(self.config_data, file, default_flow_style=False)


if __name__ == '__main__':
    # 测试 YamlUtils 类
    yaml_file_path = 'config.yaml'  # 请根据需要修改路径
    yaml_utils = YamlUtils(yaml_file_path)

    # 获取值
    print("获取值:", yaml_utils.get_value("some.key"))

    # 更新值
    yaml_utils.update_value("some.key", "new_value")
    print("更新后的值:", yaml_utils.get_value("some.key"))

    # 删除值
    yaml_utils.delete_value("some.key")
    print("删除后的值:", yaml_utils.get_value("some.key"))

    # 保存数据
    yaml_utils.save_yaml_data()
