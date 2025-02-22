# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : base_error_enum.py
@DateTime: 2025/1/12 23:15
"""
from backend.enums.base_enum_cls import StringEnum


class BaseErrorEnum(StringEnum):
    """
    错误码分类
        - 100   通用配置类错误代码
        - 200   待定
        - 300   通用业务类错误代码
        - 400   通用服务类错误代码
        - 500   通用系统类错误代码
    """

    BASE000 = ("000000", "请求成功")
    BASE999 = ("999999", "请求失败")

    BASE100 = ("100100", "导入依赖失败或未实现")
    BASE101 = ("100101", "配置参数无效或未定义")
    BASE102 = ("100102", "序列化时发生未知错误")
    BASE103 = ("100103", "未能及时获取响应结果")
    BASE104 = ("100104", "读取数据文件发生错误")
    BASE105 = ("100105", "传递参数类型不被接受")

    BASE300 = ("300300", "模型数据落库失败")

    BASE400 = ("400400", "请求参数验证失败")
    BASE401 = ("400401", "请求服务鉴权失败")
    BASE403 = ("400403", "请求服务不被接受")
    BASE404 = ("400404", "请求资源不可访达")
    BASE405 = ("400405", "请求方式不可访达")
    BASE408 = ("400408", "请求服务等待超时")
    BASE429 = ("400429", "请求速度不被允许")

    BASE500 = ("500500", "服务器遇到错误无法完成请求")
    BASE501 = ("500501", "服务器无法识别该请求或响应")
    BASE502 = ("500502", "服务器从上游网关收到无效响应")
    BASE503 = ("500503", "服务器暂时处于超载或停机维护")
    BASE504 = ("500504", "服务器等待上游网关响应超时")
    BASE505 = ("500505", "服务器不支持请求中所使用的HTTP协议版本")

    @property
    def code(self):
        return self._value_

    @property
    def value(self):
        return self.desc


if __name__ == '__main__':
    print(BaseErrorEnum.get_names())
    print(BaseErrorEnum.get_values())
    print(BaseErrorEnum.get_members())
    print(BaseErrorEnum.get_member_by_desc("请求成功", only_value=True))

    base000 = BaseErrorEnum.BASE000
    print(base000.code)
    print(base000.value)
    print(type(base000))
