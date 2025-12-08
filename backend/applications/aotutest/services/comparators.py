# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : comparators
@DateTime: 2025/11/12 14:32
"""

import re
import typing


def equal(check_value: typing.Any, expect_value: typing.Any, message: str = ""):
    assert check_value == expect_value, message


def greater_than(
        check_value: typing.Union[int, float], expect_value: typing.Union[int, float], message: str = ""
):
    assert check_value > expect_value, message


def less_than(
        check_value: typing.Union[int, float], expect_value: typing.Union[int, float], message: str = ""
):
    assert check_value < expect_value, message


def greater_or_equals(
        check_value: typing.Union[int, float], expect_value: typing.Union[int, float], message: str = ""
):
    assert check_value >= expect_value, message


def less_or_equals(
        check_value: typing.Union[int, float], expect_value: typing.Union[int, float], message: str = ""
):
    assert check_value <= expect_value, message


def not_equal(check_value: typing.Any, expect_value: typing.Any, message: str = ""):
    assert check_value != expect_value, message


def not_none(check_value: typing.Any, expect_value: typing.Any, message: str = ""):
    assert check_value is not None or check_value != "", message


def is_none(check_value: typing.Any, expect_value: typing.Any, message: str = ""):
    assert check_value is None or check_value == "", message
