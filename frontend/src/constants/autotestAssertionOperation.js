/**
 * 与 backend/enums/autotest_enum.py 中 AutoTestAssertionOperation 取值一致。
 * 新增比较符时：先扩展后端枚举与 AutoTestToolServiceImpl.compare_assertion，再同步本数组。
 */
export const AUTO_TEST_ASSERTION_OPERATION_VALUES = Object.freeze([
    '等于',
    '不等于',
    '大于',
    '大于等于',
    '小于',
    '小于等于',
    '长度等于',
    '包含',
    '不包含',
    '以...开始',
    '以...结束',
    '非空',
    '为空',
])

/** 下拉 { label, value }，label 与 value 均为中文枚举值 */
export const assertionOperationSelectOptions = AUTO_TEST_ASSERTION_OPERATION_VALUES.map((v) => ({
    label: v,
    value: v,
}))

export const DEFAULT_ASSERTION_OPERATION = '非空'
