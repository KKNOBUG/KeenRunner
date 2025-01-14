# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : file_utils.py
@DateTime: 2025/1/14 12:28
"""
import shutil, os
import threading
import zipfile
from pathlib import Path
from typing import Union

from backend.core.exceptions.base_exceptions import TypeRejectException


class FileUtils:
    """
    FileUtils类提供了一系列用于文件和目录操作的静态方法，采用单例模式确保在整个应用程序中只有一个实例。
    """

    # 用于存储该类的唯一实例
    __private_instance = None
    __private_initialized = False
    __private_lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> object:
        """
        创建并返回类的唯一实例。

        使用单例模式，在整个应用程序的生命周期内仅创建一个 `FileUtils` 实例。
        在多线程环境下，通过 `threading.Lock` 确保线程安全。

        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: `FileUtils` 类的实例
        """
        if not cls.__private_instance and not cls.__private_initialized:
            with cls.__private_lock:
                if not cls.__private_instance and not cls.__private_initialized:
                    cls.__private_instance = super().__new__(cls)
                    cls.__private_initialized = True
        return cls.__private_instance

    @staticmethod
    def str_to_path(abspath: Union[str, Path]):
        """
        将字符串路径转换为Path对象。

        :param abspath: 字符串或Path对象表示的绝对路径
        :return: Path对象
        :raises TypeRejectException: 如果输入的路径不是字符串或Path对象类型
        """
        if not isinstance(abspath, (str, Path)):
            raise TypeRejectException()

        if isinstance(abspath, str):
            abspath: Path = Path(abspath)

        return abspath

    def delete_file(self, abspath: Union[str, Path]) -> bool:
        """
        删除指定路径的文件。

        :param abspath: 要删除的文件的绝对路径
        :return: 如果文件成功删除返回True，否则返回False
        """
        abspath = self.str_to_path(abspath=abspath)
        if abspath.exists() and abspath.is_file():
            os.remove(abspath)
            return True
        return False

    def delete_directory(self, abspath: Union[str, Path]) -> bool:
        """
        删除指定路径的目录及其所有内容。

        :param abspath: 要删除的目录的绝对路径
        :return: 如果目录成功删除返回True，否则返回False
        """
        abspath = self.str_to_path(abspath=abspath)
        if abspath.exists() and abspath.is_dir():
            shutil.rmtree(abspath)
            return True
        return False

    def create_file(self, abspath: Union[str, Path], safe: bool = True) -> bool:
        """
        创建一个新文件。

        :param abspath: 要创建的文件的绝对路径
        :param safe: 如果为True，且文件已存在则不覆盖；如果为False，且文件已存在则删除并重新创建
        :return: 如果文件成功创建返回True，否则返回False
        """
        abspath = self.str_to_path(abspath=abspath)

        def create(path):
            with open(path, 'w') as file:
                file.write('')

        if not abspath.exists():
            create(path=abspath)
            return True

        if safe is False and abspath.is_file():
            self.delete_file(abspath=abspath)
            create(path=abspath)
            return True

        return False

    def create_directory(self, abspath: Union[str, Path], safe: bool = True) -> bool:
        """
        创建一个新目录。

        :param abspath: 要创建的目录的绝对路径
        :param safe: 如果为True，且目录已存在则不覆盖；如果为False，且目录已存在则删除并重新创建
        :return: 如果目录成功创建返回True，否则返回False
        """
        abspath = self.str_to_path(abspath=abspath)

        if not abspath.exists():
            abspath.mkdir()
            return True

        if safe is False and abspath.is_dir():
            self.delete_directory(abspath=abspath)
            abspath.mkdir()
            return True

        return False

    @staticmethod
    def get_all_files(abspath: Union[str, Path]) -> list:
        """
        获取指定目录下的所有文件路径。

        :param abspath: 目录的绝对路径
        :return: 包含所有文件路径的列表
        """
        filename = []
        # 获取所有文件下的子文件名称
        for root, dirs, files in os.walk(abspath):
            for _file_path in files:
                path = os.path.join(root, _file_path)
                filename.append(path)
        return filename

    @staticmethod
    def copy_directory(src_abspath: Union[str, Path], dst_abspath: Union[str, Path]) -> bool:
        """
        复制目录或文件到指定目标路径。

        :param src_abspath: 源文件或目录的绝对路径
        :param dst_abspath: 目标文件或目录的绝对路径
        :return: 如果复制成功返回True，否则返回False
        """
        if not os.path.exists(src_abspath):
            return False
        try:
            if os.path.isdir(src_abspath):
                shutil.copytree(src=src_abspath, dst=dst_abspath, dirs_exist_ok=True)
                return True
            if os.path.isfile(src_abspath):
                shutil.copy(src=src_abspath, dst=dst_abspath)
                return True
            return False
        except Exception as e:
            return False

    @staticmethod
    def zip_files(zip_file_name: str, zip_dir_path: str) -> str:
        """
        压缩指定目录下的所有文件到一个zip文件。

        :param zip_file_name: 压缩文件的名称
        :param zip_dir_path: 要压缩的目录路径
        :return: 压缩文件的名称
        """
        parent_name = os.path.dirname(zip_dir_path)
        # 压缩文件最后需要close，为了方便我们直接用with
        with zipfile.ZipFile(file=zip_file_name, mode="w", compression=zipfile.ZIP_STORED) as zip:
            for root, dirs, files in os.walk(zip_dir_path):
                for file in files:
                    if str(file).startswith("~$"):
                        continue
                    filepath = os.path.join(root, file)
                    writepath = os.path.relpath(filepath, parent_name)
                    zip.write(filepath, writepath)
            zip.close()
        return zip_file_name
