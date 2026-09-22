/**
 * 压测接口 提取/断言 的「存储口径 ↔ 面板口径」转换层。
 *
 * 提取/断言编辑复用 autotest 的 StepExtractPanel/StepAssertPanel 与 autotestExtractAssert
 * 工具族, 但两域落库口径不同: perf 的 source 值与后端 PERF_ASSERT_SOURCES 及
 * locust 引擎注册表键逐字一致(小写), 而面板下拉选项值是 RESPONSE_EXTRACT_OBJECT_OPTIONS
 * 的大写形态。本文件负责双向映射; 映射表之外的值原样往返, 保证存量数据不丢失。
 */
import {
  ASSERT_MODE_RESPONSE,
  buildAssertListFromDict,
  buildExtractListFromDict,
  EXTRACT_MODE_RESPONSE,
  hydrateAssertDictFromBackend,
  hydrateExtractDictFromBackend,
  normalizeBackendList,
} from '@/utils/autotestExtractAssert'

/** perf 小写 source → 提取面板 object（提取面板无「变量池」选项, 变量池类来源原样保留显示原值） */
const EXTRACT_SOURCE_TO_OBJECT = {
  'response json': 'Response Json',
  'response text': 'Response Text',
  'response headers': 'Response Headers',
  'response cookie': 'Response Cookie',
  'request json': 'Request Json',
  'request text': 'Request Text',
  'request headers': 'Request Headers',
  'request cookie': 'Request Cookie',
  'request form-data': 'Request Form-Data',
}

/** perf 小写 source → 断言面板 object（断言面板有「变量池」选项, session_variables 与之等价归一） */
const ASSERT_SOURCE_TO_OBJECT = {
  ...EXTRACT_SOURCE_TO_OBJECT,
  session_variables: '变量池',
  变量池: '变量池',
}

/** 面板 object → perf 小写 source；「变量池」不在表内即原样往返(引擎注册表键本身合法) */
const OBJECT_TO_SOURCE = {
  'Response Json': 'response json',
  'Response Text': 'response text',
  'Response Headers': 'response headers',
  'Response Cookie': 'response cookie',
  'Request Json': 'request json',
  'Request Text': 'request text',
  'Request Headers': 'request headers',
  'Request Cookie': 'request cookie',
  'Request Form-Data': 'request form-data',
}

/** perf 存储提取列表 → 面板字典（source 归一为面板 object, 未知值原样保留） */
export function hydratePerfExtractDict(list) {
  return hydrateExtractDictFromBackend(
      normalizeBackendList(list).map((item) => ({ ...item, source: EXTRACT_SOURCE_TO_OBJECT[item.source] || item.source })),
      EXTRACT_MODE_RESPONSE,
  )
}

/** perf 存储断言列表 → 面板字典（source 归一为面板 object, session_variables 并入「变量池」） */
export function hydratePerfAssertDict(list) {
  return hydrateAssertDictFromBackend(
      normalizeBackendList(list).map((item) => ({ ...item, source: ASSERT_SOURCE_TO_OBJECT[item.source] || item.source })),
      ASSERT_MODE_RESPONSE,
  )
}

/** 面板提取字典 → perf 存储列表（object 映射回小写 source, 未知值原样往返） */
export function buildPerfExtractListFromDict(dict) {
  return buildExtractListFromDict(dict, EXTRACT_MODE_RESPONSE)
      .map((item) => ({ ...item, source: OBJECT_TO_SOURCE[item.source] || item.source }))
}

/** 面板断言字典 → perf 存储列表（object 映射回小写 source, 「变量池」原样保留） */
export function buildPerfAssertListFromDict(dict) {
  return buildAssertListFromDict(dict, ASSERT_MODE_RESPONSE)
      .map((item) => ({ ...item, source: OBJECT_TO_SOURCE[item.source] || item.source }))
}
