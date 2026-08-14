import { assertionOperationSelectOptions } from '@/constants/autotestAssertionOperation'

/** 提取：HTTP/TCP 响应对象 */
export const EXTRACT_MODE_RESPONSE = 'response'
/** 提取：数据库步骤，来源为请求中的 variable_name */
export const EXTRACT_MODE_DATABASE = 'database'
/** 提取：Redis 步骤，来源为请求中的 variable_name */
export const EXTRACT_MODE_REDIS = 'redis'

/** 断言：HTTP/TCP 响应 + 变量池 */
export const ASSERT_MODE_RESPONSE = 'response'
/** 断言：数据库步骤，来源为 variable_name */
export const ASSERT_MODE_DATABASE = 'database'
/** 断言：Redis 步骤，来源为 variable_name */
export const ASSERT_MODE_REDIS = 'redis'
/** 断言：Python 代码步骤，仅变量池 */
export const ASSERT_MODE_PYTHON = 'python'

export const RESPONSE_EXTRACT_OBJECT_OPTIONS = [
  { label: 'Request Json', value: 'Request Json' },
  { label: 'Request Text', value: 'Request Text' },
  { label: 'Request XML', value: 'Request XML' },
  { label: 'Request Header', value: 'Request Header' },
  { label: 'Request Cookie', value: 'Request Cookie' },
  { label: 'Response Json', value: 'Response Json' },
  { label: 'Response Text', value: 'Response Text' },
  { label: 'Response XML', value: 'Response XML' },
  { label: 'Response Header', value: 'Response Header' },
  { label: 'Response Cookie', value: 'Response Cookie' },
]

export const RESPONSE_ASSERT_OBJECT_OPTIONS = [
  ...RESPONSE_EXTRACT_OBJECT_OPTIONS,
  { label: '变量池', value: '变量池' },
]

export const PYTHON_ASSERT_OBJECT_OPTIONS = [{ label: '变量池', value: '变量池' }]

export const DB_JSONPATH_PLACEHOLDER =
    '如 $.sql_data[0].列名、$.sql_count、$.env_name（相对该 variable_name 对应执行结果项，字段均在外层）'

export const REDIS_JSONPATH_PLACEHOLDER =
    '如 $.[0] 或 $.[1][0]（相对该 variable_name 对应 redis_data 命令结果列表）'

export const DB_SOURCE_HINT =
    '与执行结果列表中该 variable_name 对应项匹配；JSONPath 写在该项外层字段上，例如 $.sql_data[0].列名、$.sql_count、$.config_name。'

export const REDIS_SOURCE_HINT =
    '与执行结果列表中该 variable_name 对应项匹配；JSONPath 相对 redis_data，例如 $.[0] 表示第一条命令返回值。'

export const isVariableNameExtractMode = (mode) =>
    mode === EXTRACT_MODE_DATABASE || mode === EXTRACT_MODE_REDIS

export const isVariableNameAssertMode = (mode) =>
    mode === ASSERT_MODE_DATABASE || mode === ASSERT_MODE_REDIS

export const assertionOptions = assertionOperationSelectOptions

export function normalizeBackendList(source) {
  if (!source) return []
  if (Array.isArray(source)) return source
  if (typeof source === 'object' && Object.keys(source).length > 0) return [source]
  return []
}

export function getNextDictKey(dict) {
  const keys = Object.keys(dict || {})
      .map((k) => parseInt(k, 10))
      .filter((k) => !Number.isNaN(k))
  if (!keys.length) return '1'
  return String(Math.max(...keys) + 1)
}

export function countDictKeys(dict) {
  return Object.keys(dict || {}).length
}

export function resolveDatabaseSourceVar(item) {
  let srcVar = String(item?.source ?? '').trim()
  if (!srcVar || srcVar.toLowerCase() === 'response json') {
    srcVar = String(item?.subject_key ?? '').trim()
  }
  return srcVar || null
}

export function getExtractObjectLabel(value) {
  const option =
      RESPONSE_EXTRACT_OBJECT_OPTIONS.find((opt) => opt.value === value)
      || RESPONSE_ASSERT_OBJECT_OPTIONS.find((opt) => opt.value === value)
      || PYTHON_ASSERT_OBJECT_OPTIONS.find((opt) => opt.value === value)
  return option ? option.label : value || ''
}

export function getExtractPlaceholder(object) {
  const placeholderMap = {
    'Request Json': '请输入JSONPath表达式，如：$.data.name',
    'Request Text': '请输入正则表达式，如：^[A-Za-z0-9]+$',
    'Request XML': '请输入XPath表达式，如：/store/book[1]/title',
    'Request Header': '请输入JSONPath表达式，如：$.Content-Type',
    'Request Cookie': '请输入JSONPath表达式，如：$.Auth',
    'Response Json': '请输入JSONPath表达式，如：$.data.name',
    'Response Text': '请输入正则表达式，如：^[A-Za-z0-9]+$',
    'Response XML': '请输入XPath表达式，如：/store/book[1]/title',
    'Response Header': '请输入JSONPath表达式，如：$.Content-Type',
    'Response Cookie': '请输入JSONPath表达式，如：$.Auth',
  }
  return placeholderMap[object] || '请输入表达式'
}

export function getAssertPlaceholder(object, assertMode) {
  if (assertMode === ASSERT_MODE_DATABASE) return DB_JSONPATH_PLACEHOLDER
  if (assertMode === ASSERT_MODE_REDIS) return REDIS_JSONPATH_PLACEHOLDER
  if (object === '变量池' || assertMode === ASSERT_MODE_PYTHON) {
    return 'JSONPath，如：$.token 或 $.list[0].name'
  }
  return getExtractPlaceholder(object)
}

export function createEmptyExtractItem(extractMode, defaultSource = null) {
  if (isVariableNameExtractMode(extractMode)) {
    return {
      name: '',
      source: defaultSource ?? null,
      extractScope: '部分提取',
      jsonpath: '',
      extractIndex: 0,
      extractContinue: false,
    }
  }
  return {
    name: '',
    object: 'Response Json',
    extractScope: '部分提取',
    jsonpath: '',
    extractIndex: null,
    extractContinue: false,
  }
}

export function createEmptyAssertItem(assertMode, defaultSource = null, defaultObject = null) {
  if (isVariableNameAssertMode(assertMode)) {
    return {
      name: '',
      source: defaultSource ?? null,
      jsonpath: '',
      assertion: '等于',
      value: '',
    }
  }
  if (assertMode === ASSERT_MODE_PYTHON) {
    return {
      name: '',
      object: '变量池',
      jsonpath: '',
      assertion: '等于',
      value: '',
    }
  }
  return {
    name: '',
    object: defaultObject || 'Response Json',
    jsonpath: '',
    assertion: '等于',
    value: '',
    extractIndex: 0,
  }
}

export function hydrateExtractDictFromBackend(list, extractMode) {
  const dict = {}
  const rows = normalizeBackendList(list)
  rows.forEach((item, index) => {
    const key = String(index + 1)
    if (isVariableNameExtractMode(extractMode)) {
      dict[key] = {
        name: item.name || '',
        source: resolveDatabaseSourceVar(item),
        extractScope: item.scope === 'ALL' ? '全部提取' : '部分提取',
        jsonpath: item.expr || '',
        extractIndex: item.index !== undefined && item.index !== null ? Number(item.index) : 0,
        extractContinue: item.index !== undefined && item.index !== null && item.index !== '',
      }
    } else {
      dict[key] = {
        name: item.name || '',
        object: item.source || 'Response Json',
        extractScope: item.scope === 'ALL' ? '全部提取' : '部分提取',
        jsonpath: item.expr || '',
        extractIndex: item.index !== undefined && item.index !== null && item.index !== '' ? Number(item.index) : null,
        extractContinue: item.index !== undefined && item.index !== null && item.index !== '',
      }
    }
  })
  return dict
}

export function hydrateAssertDictFromBackend(list, assertMode) {
  const dict = {}
  const rows = normalizeBackendList(list)
  rows.forEach((item, index) => {
    const key = String(index + 1)
    if (isVariableNameAssertMode(assertMode)) {
      dict[key] = {
        name: item.name || '',
        source: resolveDatabaseSourceVar(item),
        jsonpath: item.expr || '',
        assertion: item.operation || '等于',
        value: item.except_value != null ? String(item.except_value) : '',
      }
    } else if (assertMode === ASSERT_MODE_PYTHON) {
      dict[key] = {
        name: item.name || '',
        object: '变量池',
        jsonpath: item.expr || '',
        assertion: item.operation || '等于',
        value: item.except_value != null ? String(item.except_value) : '',
      }
    } else {
      dict[key] = {
        name: item.name || '',
        object: item.source || 'Response Json',
        jsonpath: item.expr || '',
        assertion: item.operation || '等于',
        value: item.except_value != null ? String(item.except_value) : '',
            extractIndex: item.extractIndex ?? 0,
      }
    }
  })
  return dict
}

export function formatExtractCardTitle(item, extractMode) {
  const name = item?.name || '未命名提取'
  if (isVariableNameExtractMode(extractMode)) {
    const src = item?.source || '未选来源'
    const path =
        item?.extractScope === '部分提取' && item?.jsonpath
            ? ` (${item.jsonpath})`
            : item?.extractScope === '全部提取'
                ? ' (全部提取)'
                : ''
    return `${name} · ${src}${path}`
  }
  const objLabel = getExtractObjectLabel(item?.object)
  const path =
      item?.extractScope === '部分提取' && item?.jsonpath
          ? `( ${item.jsonpath} )`
          : item?.extractScope === '全部提取'
              ? '( 全部提取 )'
              : ''
  return `${name} ${objLabel}${path ? ` ${path}` : ''}`
}

export function formatAssertCardTitle(item, assertMode) {
  const name = item?.name || '未命名断言'
  const expr = item?.jsonpath || ''
  if (isVariableNameAssertMode(assertMode)) {
    return `${name} · ${item?.source || '未选来源'} ( ${expr} )`
  }
  const objLabel = getExtractObjectLabel(item?.object)
  return `${name} ${objLabel}( ${expr} )`
}

export function buildExtractListFromDict(dict, extractMode) {
  // 不做静默过滤：不完整配置原样带出，由 validateExtractList 在保存/调试时拦截并提示
  if (isVariableNameExtractMode(extractMode)) {
    return Object.values(dict || {}).map((item) => ({
      expr: item.jsonpath || '',
      name: item.name || '',
      scope: item.extractScope === '全部提取' ? 'ALL' : 'SOME',
      source: String(item.source ?? '').trim(),
      index:
          item.extractIndex !== undefined && item.extractIndex !== null && item.extractIndex !== ''
              ? Number(item.extractIndex)
              : null,
    }))
  }
  return Object.values(dict || {}).map((item) => ({
    expr: item.jsonpath || '',
    name: item.name || '',
    scope: item.extractScope === '全部提取' ? 'ALL' : 'SOME',
    source: item.object || 'Response Json',
    index:
        item.extractIndex !== undefined && item.extractIndex !== null && item.extractIndex !== ''
            ? Number(item.extractIndex)
            : null,
  }))
}

export function buildAssertListFromDict(dict, assertMode) {
  // 不做静默过滤：不完整配置原样带出，由 validateAssertList 在保存/调试时拦截并提示
  if (isVariableNameAssertMode(assertMode)) {
    return Object.values(dict || {}).map((item) => ({
      expr: item.jsonpath || '',
      name: item.name || '',
      source: String(item.source ?? '').trim(),
      operation: item.assertion || '等于',
      except_value: item.value != null ? String(item.value) : '',
    }))
  }
  if (assertMode === ASSERT_MODE_PYTHON) {
    return Object.values(dict || {}).map((item) => ({
      expr: item.jsonpath || '',
      name: item.name || '',
      source: '变量池',
      operation: item.assertion || '等于',
      except_value: item.value != null ? String(item.value) : '',
    }))
  }
  return Object.values(dict || {}).map((item) => ({
    expr: item.jsonpath || '',
    name: item.name || '',
    source: item.object || 'Response Json',
    operation: item.assertion || '等于',
    except_value: item.value != null ? String(item.value) : '',
  }))
}

/**
 * 校验提取配置列表（后端数组形态）。
 * 部分提取时提取路径必填；全部提取允许路径为空。
 */
export function validateExtractList(list) {
  if (!Array.isArray(list) || list.length === 0) {
    return { valid: true }
  }
  for (let i = 0; i < list.length; i += 1) {
    const item = list[i] || {}
    const name = String(item.name ?? '').trim()
    const expr = String(item.expr ?? '').trim()
    const source = String(item.source ?? '').trim()
    const scope = String(item.scope ?? 'SOME').trim().toUpperCase()
    const label = name || `第${i + 1}项`
    if (!name) {
      return {
        valid: false,
        message: `提取配置「${label}」名称不能为空，请填写或删除该配置`,
      }
    }
    if (!source) {
      return {
        valid: false,
        message: `提取配置「${name}」未选择提取对象/来源，请选择或删除该配置`,
      }
    }
    if (scope !== 'ALL' && !expr) {
      return {
        valid: false,
        message: `提取配置「${name}」为部分提取时提取路径不能为空，请填写、改为全部提取，或删除该配置`,
      }
    }
  }
  return { valid: true }
}

/** 校验断言配置列表（后端数组形态） */
export function validateAssertList(list) {
  if (!Array.isArray(list) || list.length === 0) {
    return { valid: true }
  }
  for (let i = 0; i < list.length; i += 1) {
    const item = list[i] || {}
    const name = String(item.name ?? '').trim()
    const expr = String(item.expr ?? '').trim()
    const source = String(item.source ?? '').trim()
    const operation = String(item.operation ?? '').trim()
    const label = name || `第${i + 1}项`
    if (!name) {
      return {
        valid: false,
        message: `断言配置「${label}」名称不能为空，请填写或删除该配置`,
      }
    }
    if (!source) {
      return {
        valid: false,
        message: `断言配置「${name}」未选择断言对象/来源，请选择或删除该配置`,
      }
    }
    if (!expr) {
      return {
        valid: false,
        message: `断言配置「${name}」断言表达式不能为空，请填写或删除该配置`,
      }
    }
    if (!operation) {
      return {
        valid: false,
        message: `断言配置「${name}」未选择断言方式，请选择或删除该配置`,
      }
    }
  }
  return { valid: true }
}
