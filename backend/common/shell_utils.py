# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : shell_utils.py
@DateTime: 2025/1/15 12:35
"""
import re
import subprocess
import socket
from pathlib import Path


class ShellUtils:
    """
    Shell终端命令行工具封装
    1. 执行终端命令行，接受结果
    2. 获取本机IP地址
    3. 打开应用程序
    4. 终止应用程序
    5. 获取系统信息
    6. 根据端口号查找进程
    7. 根据端口号杀死进程
    """

    @staticmethod
    def execute_command(command) -> str:
        """
        执行终端命令
        :param command: cmd命令
        :return: 命令输出结果
        """
        output, errors = subprocess.Popen(command,
                                          shell=True,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
        try:
            output_message: str = output.decode("utf-8")
        except UnicodeDecodeError as e:
            output_message: str = output.decode('gbk')

        return output_message

    @staticmethod
    def acquire_localhost():
        """
        查询本机IP地址
        :return: 本机IP地址
        """
        socket_object = None
        local_host_ip = None
        try:
            socket_object = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_object.connect(('8.8.8.8', 80))
            local_host_ip = socket_object.getsockname()[0]
        except Exception as e:
            raise RuntimeError(f"获取本机IP地址失败:{e}")
        finally:
            if socket_object:
                socket_object.close()

        return local_host_ip

    @staticmethod
    def open_application(app_root: str, app_name: str):
        """
        打开指定的应用程序
        :param app_root: 应用程序根目录
        :param app_name: 应用程序名称
        :return: 应用程序进程ID
        """
        app_root = Path(app_root)
        abs_path = app_root / app_name
        if not abs_path.exists() or not abs_path.is_file():
            raise FileNotFoundError(f"应用程序启动失败，无法识别：{abs_path}")

        popend = subprocess.Popen(
            args=app_name,
            cwd=app_root,
            shell=True,
            start_new_session=True,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
        if popend.stderr is not None and popend.returncode != 0:
            raise RuntimeError(f"应用程序启动失败，错误描述：{popend.stderr.read()}")

        return str(popend.pid)

    @staticmethod
    def kill_application(app: str = None, pid: str = None) -> bool:
        """
        终止指定的应用程序
        :param app: 应用程序名称
        :param pid: 进程ID
        :return: 是否成功终止
        """
        cmd: str = f"taskkill /f /im {app}" if app else f"taskkill /f /pid {pid}"

        popend: subprocess.Popen = subprocess.Popen(
            args=cmd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        output_message, error_message = popend.communicate()

        if not ("成功: 已终止" in output_message or "错误: 没有找到进程" in error_message):
            raise RuntimeError(f"应用程序终止失败，错误描述：{error_message}")

        return True

    @staticmethod
    def list_running_processes() -> str:
        """
        列出当前运行的进程
        :return: 当前运行的进程列表
        """
        return ShellUtils.execute_command("tasklist")

    @staticmethod
    def get_system_info() -> str:
        """
        获取系统信息
        :return: 系统信息
        """
        return ShellUtils.execute_command("systeminfo")

    @staticmethod
    def find_process_by_port(port: int) -> str:
        """
        根据端口号查找进程
        :param port: 端口号
        :return: 进程信息
        """
        command = f"netstat -ano | findstr :{port}"
        output = ShellUtils.execute_command(command)
        if not output:
            raise RuntimeError(f"未找到使用端口 {port} 的进程")
        return output

    @staticmethod
    def kill_process_by_port(port: int) -> bool:
        """
        根据端口号杀死进程
        :param port: 端口号
        :return: 是否成功终止
        """
        process_info = ShellUtils.find_process_by_port(port)
        # 提取进程ID
        pid_match = re.search(r'\s+(\d+)$', process_info.strip())
        if not pid_match:
            raise RuntimeError(f"未找到使用端口 {port} 的进程ID")

        pid = pid_match.group(1)
        return ShellUtils.kill_application(pid=pid)

    @staticmethod
    def kill_all_processes_by_name(app_name: str) -> bool:
        """
        根据应用名称杀死所有相关进程
        :param app_name: 应用程序名称
        :return: 是否成功终止
        """
        try:
            return ShellUtils.kill_application(app=app_name)
        except RuntimeError as e:
            if "错误: 没有找到进程" in str(e):
                print(f"未找到名为 {app_name} 的进程")
                return False
            raise


if __name__ == '__main__':
    print(ShellUtils.execute_command("ls"))
    print(ShellUtils.acquire_localhost())
    print(ShellUtils.list_running_processes())
    print(ShellUtils.get_system_info())

    # 示例：根据端口查找进程
    try:
        print(ShellUtils.find_process_by_port(8080))  # 替换为实际端口
    except RuntimeError as e:
        print(e)

    # 示例：根据端口杀死进程
    try:
        ShellUtils.kill_process_by_port(8080)  # 替换为实际端口
        print("进程已成功终止")
    except RuntimeError as e:
        print(e)

    # 示例：根据应用名称杀死所有相关进程
    try:
        ShellUtils.kill_all_processes_by_name("python.exe")  # 替换为实际应用名称
        print("所有相关进程已成功终止")
    except RuntimeError as e:
        print(e)
