# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : file_utils.py
@DateTime: 2025/1/14 12:28
"""
import shutil, os, threading, glob, mimetypes, zipfile
from datetime import datetime
from pathlib import Path
from typing import Union, Optional

import yaml

from backend.core.exceptions.base_exceptions import (
    TypeRejectException, NotFoundException, NotImplementedException, ParameterException
)


class FileUtils:
    """
    FileUtils类提供了一系列用于文件和目录操作的静态方法，采用单例模式确保在整个应用程序中只有一个实例。
    """
    __slots__ = []
    # 用于存储该类的唯一实例
    __private_instance = None
    __private_initialized = False
    __private_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
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
        将输入的绝对路径（字符串或 Path 对象）转换为 Path 对象。

        :param abspath: 输入的绝对路径，可以是字符串或 Path 对象
        :return: 转换后的 Path 对象
        :raises TypeRejectException: 如果输入的路径不是字符串或 Path 对象类型
        """
        if not isinstance(abspath, (str, Path)):
            raise TypeRejectException()

        if isinstance(abspath, str):
            abspath: Path = Path(abspath)

        return abspath

    def is_file(self, abspath: Union[str, Path]) -> bool:
        """
        检查指定路径是否为文件。

        :param abspath: 输入的绝对路径，可以是字符串或 Path 对象
        :return: 如果是文件返回 True，否则返回 False
        """
        abspath = self.str_to_path(abspath=abspath)
        return abspath.is_file()

    def is_dir(self, abspath: Union[str, Path]) -> bool:
        """
        检查指定路径是否为目录。

        :param abspath: 输入的绝对路径，可以是字符串或 Path 对象
        :return: 如果是目录返回 True，否则返回 False
        """
        abspath = self.str_to_path(abspath=abspath)
        return abspath.is_dir()

    def delete_file(self, abspath: Union[str, Path]) -> bool:
        """
        删除指定路径的文件。

        :param abspath: 要删除的文件的绝对路径，可以是字符串或 Path 对象
        :return: 如果文件成功删除返回 True，否则返回 False
        """
        abspath = self.str_to_path(abspath=abspath)
        if abspath.exists() and abspath.is_file():
            os.remove(abspath)
            return True
        return False

    def delete_directory(self, abspath: Union[str, Path]) -> bool:
        """
        删除指定路径的目录及其所有内容。

        :param abspath: 要删除的目录的绝对路径，可以是字符串或 Path 对象
        :return: 如果目录成功删除返回 True，否则返回 False
        """
        abspath = self.str_to_path(abspath=abspath)
        if abspath.exists() and abspath.is_dir():
            shutil.rmtree(abspath)
            return True
        return False

    def create_file(self, abspath: Union[str, Path], safe: bool = True) -> bool:
        """
        创建一个新文件。

        :param abspath: 要创建的文件的绝对路径，可以是字符串或 Path 对象
        :param safe: 如果为 True，且文件已存在则不覆盖；如果为 False，且文件已存在则删除并重新创建
        :return: 如果文件成功创建返回 True，否则返回 False
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

        :param abspath: 要创建的目录的绝对路径，可以是字符串或 Path 对象
        :param safe: 如果为 True，且目录已存在则不覆盖；如果为 False，且目录已存在则删除并重新创建
        :return: 如果目录成功创建返回 True，否则返回 False
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
    def get_all_dirs(abspath: Union[str, Path], return_full_path: bool = True,
                     startswith: Optional[str] = None, endswith: Optional[str] = None,
                     exclude_startswith: Optional[str] = None, exclude_endswith: Optional[str] = None) -> list:
        """
        获取指定路径下的所有目录，并根据条件进行过滤。

        :param abspath: 要查找目录的绝对路径，可以是字符串或 Path 对象。
        :param return_full_path: 是否返回完整路径。默认为 True。
        :param startswith: 仅返回以该字符串开头的目录名。默认为 None。
        :param endswith: 仅返回以该字符串结尾的目录名。默认为 None。
        :param exclude_startswith: 排除以该字符串开头的目录名。默认为 None。
        :param exclude_endswith: 排除以该字符串结尾的目录名。默认为 None。
        :return: 满足条件的目录列表，如果 return_full_path 为 True，则返回完整路径，否则返回目录的基本名称。
        """
        # 获取指定路径下所有的目录
        dirs = [d for d in glob.glob(os.path.join(abspath, "*")) if os.path.isdir(d)]

        # 过滤目录名
        if startswith:
            dirs = [d for d in dirs if os.path.basename(d).startswith(startswith)]
        if endswith:
            dirs = [d for d in dirs if os.path.basename(d).endswith(endswith)]

        # 排除目录名
        if exclude_startswith:
            dirs = [d for d in dirs if not os.path.basename(d).startswith(exclude_startswith)]
        if exclude_endswith:
            dirs = [d for d in dirs if not os.path.basename(d).endswith(exclude_endswith)]

        if return_full_path:
            return dirs

        return [os.path.basename(d) for d in dirs]

    @staticmethod
    def get_all_files(abspath: Union[str, Path],
                      return_full_path: bool = True,
                      return_precut_path: Optional[str] = None,
                      startswith: Optional[str] = None,
                      endswith: Optional[str] = None,
                      extension: Optional[str] = None,
                      exclude_startswith: Optional[str] = None,
                      exclude_endswith: Optional[str] = None,
                      exclude_extension: Optional[str] = None) -> list:
        """
        获取指定路径下的所有文件，并根据条件进行过滤。

        :param abspath: 要查找文件的绝对路径，可以是字符串或 Path 对象。
        :param return_full_path: 是否返回完整路径。默认为 True。
        :param return_precut_path: 是否返回包含额外前缀的路径，默认为 False。
        :param startswith: 仅返回以该字符串开头的文件名。默认为 None。
        :param endswith: 仅返回以该字符串结尾的文件名（不包括扩展名）。默认为 None。
        :param extension: 仅返回具有该扩展名的文件。默认为 None。
        :param exclude_startswith: 排除以该字符串开头的文件名。默认为 None。
        :param exclude_endswith: 排除以该字符串结尾的文件名（不包括扩展名）。默认为 None。
        :param exclude_extension: 排除具有该扩展名的文件。默认为 None。
        :return: 满足条件的文件列表，如果 return_full_path 为 True，则返回完整路径；如果 return_precut_path 为 True，则返回带有额外前缀的文件名；否则返回文件的基本名称。
        """
        # 获取指定路径下所有的目录
        files = [file for file in glob.glob(os.path.join(abspath, "*")) if os.path.isfile(file)]

        # 过滤文件名
        if startswith:
            files = [file for file in files if os.path.basename(file).startswith(startswith)]
        if endswith:
            files = [file for file in files if os.path.splitext(os.path.basename(file))[0].endswith(endswith)]
        if extension:
            files = [file for file in files if file.endswith(extension)]

        # 排除文件名
        if exclude_startswith:
            files = [file for file in files if not os.path.basename(file).startswith(exclude_startswith)]
        if exclude_endswith:
            files = [file for file in files if
                     not os.path.splitext(os.path.basename(file))[0].endswith(exclude_endswith)]
        if exclude_extension:
            files = [file for file in files if not file.endswith(exclude_extension)]

        if return_full_path:
            return files
        elif return_precut_path:
            return [return_precut_path + os.path.splitext(os.path.basename(file))[0] for file in files]

        return [os.path.basename(file) for file in files]

    @staticmethod
    def get_file_info(abspath: Union[str, bytes, Path], filename: str = None) -> Union[bytes, tuple]:
        """
        获取文件的信息，包括文件名、文件字节内容和 MIME 类型。

        :param abspath: 输入的文件信息，可以是文件路径（str 或 Path）或文件字节数据（bytes）
        :param filename: 当输入为字节数据时需要提供的文件名
        :return: 如果输入是文件路径，返回 (文件名, 文件字节内容, MIME 类型) 的元组；如果输入是字节数据，返回 (文件名, 字节数据, MIME 类型) 的元组；其他情况抛出 NotImplementedException
        """
        if isinstance(abspath, (str, Path)):
            filename = os.path.basename(str(abspath))
            with open(file=abspath, mode="rb") as file:
                file_bytes = file.read()

            mime_type = mimetypes.guess_type(abspath)[0]
            return filename, file_bytes, mime_type

        elif isinstance(abspath, bytes):
            if not filename:
                raise ValueError("文件名称在传递字节数据时为必填")

            mime_type = mimetypes.guess_type(filename)[0]
            return filename, abspath, mime_type

        else:
            raise NotImplementedException(message="未实现非文件路径或字节以外的功能")

    def get_file_size(self, abspath: Union[str, Path], unit: str = 'B') -> float:
        """
        获取指定文件的大小，并将其转换为指定的单位。

        :param abspath: 文件的绝对路径，可以是字符串或 Path 对象
        :param unit: 要转换的目标单位，可选值包括 'B'（字节）、'KB'（千字节）、'MB'（兆字节）、'GB'（吉字节）等
        :return: 转换为指定单位后的文件大小，保留两位小数，四舍五入
        :raises NotFoundException: 如果文件不存在
        :raises NotImplementedException: 如果指定的单位不在支持的转换单位列表中
        """
        abspath = self.str_to_path(abspath=abspath)
        if not abspath.exists():
            raise NotFoundException(message=f"文件或目录不存在: {abspath}")

        file_size_bytes = os.path.getsize(abspath)

        # 定义单位转换的映射
        unit_mapping = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            # 可以根据需要添加更多单位
        }

        if unit not in unit_mapping:
            raise NotImplementedException(message=f"给定换算单位无效，必须是其中之一: {', '.join(unit_mapping.keys())}")

        # 转换文件大小到指定单位
        file_size_unit = round(file_size_bytes / unit_mapping[unit], 2)

        return file_size_unit

    def get_last_modified_time(self, abspath: Union[str, Path]) -> datetime:
        """
        获取指定文件的最后修改时间。

        :param abspath: 文件的绝对路径，可以是字符串或 Path 对象
        :return: 文件的最后修改时间
        :raises NotFoundException: 如果文件不存在
        """
        abspath = self.str_to_path(abspath=abspath)
        if not abspath.exists():
            raise NotFoundException(message=f"文件或目录不存在: {abspath}")

        return datetime.fromtimestamp(os.path.getmtime(abspath))

    def get_last_file_name(self, abspath: Union[str, Path]) -> str:
        """
        获取指定目录中最后创建的文件的名称。

        :param abspath: 目录的绝对路径，可以是字符串或 Path 对象
        :return: 最后创建的文件的名称
        :raises NotFoundException: 如果目录不存在或目录中没有文件
        """
        abspath = self.str_to_path(abspath=abspath)
        if not abspath.exists():
            raise NotFoundException(message=f"目录不存在: {abspath}")

        # 获取目录中的所有文件
        files = [f for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath, f))]
        if not files:
            raise NotFoundException(message=f"目录中不存在文件: {abspath}")

        # 按创建时间排序，取最后创建的文件
        last_file_name = max(files, key=lambda f: os.path.getctime(os.path.join(abspath, f)))
        return last_file_name

    def get_last_dir_name(self, abspath: Union[str, Path]) -> str:
        """
        获取指定目录中最后创建的目录的名称。

        :param abspath: 父目录的绝对路径，可以是字符串或 Path 对象
        :return: 最后创建的目录的名称
        """
        last_dir_name = ""
        last_dir_time = 0

        # 遍历指定目录下的所子目录
        abspath = self.str_to_path(abspath=abspath)
        for entry in os.scandir(abspath):
            if entry.is_dir(follow_symlinks=False):
                # 获取目录的创建时间
                dir_time = entry.stat().st_ctime

                # 比较时间，如果当前目录创建时间晚于之前记录的，则更新记录
                if dir_time > last_dir_time:
                    last_dir_time = dir_time
                    last_dir_name = entry.name

        return last_dir_name

    @staticmethod
    def copy_directory(src_abspath: Union[str, Path], dst_abspath: Union[str, Path]) -> bool:
        """
        复制目录或文件到指定目标路径。

        :param src_abspath: 源文件或目录的绝对路径，可以是字符串或 Path 对象
        :param dst_abspath: 目标文件或目录的绝对路径，可以是字符串或 Path 对象
        :return: 如果复制成功返回 True，否则返回 False
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
    def move_directory(src_abspath: Union[str, Path], dst_abspath: Union[str, Path]) -> bool:
        """
        移动目录或文件到指定目标路径。

        :param src_abspath: 源文件或目录的绝对路径，可以是字符串或 Path 对象
        :param dst_abspath: 目标文件或目录的绝对路径，可以是字符串或 Path 对象
        :return: 如果复制成功返回 True，否则返回 False
        """
        # 检查原始文件或目录是否存在
        if not os.path.exists(src_abspath):
            raise NotFoundException(message=f"目录中不存在文件: {src_abspath}")

        # 检查目标目录是否存在
        dst_dir = os.path.dirname(dst_abspath)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)

        # 检查目标文件是否存在
        if os.path.exists(dst_abspath):
            raise ParameterException(message=f"目标目录下存在同名文件: {dst_abspath}")

        shutil.move(src=src_abspath, dst=dst_abspath)
        return True

    @staticmethod
    def zip_files(zip_file_name: str, zip_dir_path: str) -> str:
        """
        压缩指定目录下的所有文件到一个 zip 文件。

        :param zip_file_name: 压缩文件的名称
        :param zip_dir_path: 要压缩的目录的路径
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

    def read_file(self, file_path: str, file_type: str) -> str:
        with open(file_path, 'r') as file:
            if file_type == 'yml':
                content = yaml.safe_load(file)
            else:
                content = file.readlines()
        return content

    def read_files(self, path: str, file_type: str) -> str:
        list_file = [item for item in os.listdir(path) if item.endswith(f'.{file_type}')]
        documentation = []
        if len(list_file) == 1:
            file_path = f"{path}/{list_file[0]}"
            response = self.read_file(file_path, file_type)
            return response
        else:
            for item in list_file:
                file_path = f"{path}/{item}"
                file = self.read_file(file_path, file_type)
                documentation += file
            return '\n'.join(documentation)
