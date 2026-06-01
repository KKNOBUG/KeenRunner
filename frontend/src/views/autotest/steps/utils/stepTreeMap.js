/**
 * 步骤树：后端数据 ↔ 前端树节点（执行配置弹窗、步骤编辑页共用）
 */

const stepDefinitions = {
  user_variables: { allowChildren: false },
  if: { allowChildren: true },
  wait: { allowChildren: false },
  loop: { allowChildren: true },
  tcp: { allowChildren: false },
  http: { allowChildren: false },
  code: { allowChildren: false },
  database: { allowChildren: false },
  quote: { allowChildren: false },
}

let seed = 1000
const genId = () => `step-${seed++}`

const backendTypeToLocal = (step_type) => {
  switch (step_type) {
    case '用户变量':
      return 'user_variables'
    case 'TCP请求':
      return 'tcp'
    case 'HTTP请求':
      return 'http'
    case '代码请求(Python)':
      return 'code'
    case '条件分支':
      return 'if'
    case '等待控制':
      return 'wait'
    case '循环结构':
      return 'loop'
    case '引用公共脚本':
      return 'quote'
    case '数据库请求':
      return 'database'
    default:
      return 'code'
  }
}

/** 前序遍历步骤树 */
export function forEachStep(list, fn) {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children?.length) forEachStep(step.children, fn)
  }
}

/** 将后端步骤转为前端树节点（含 original，供 ExecConfigModal 聚合环境配置） */
export function mapBackendStep(step) {
  if (!step || !step.step_type) return null
  const localType = backendTypeToLocal(step.step_type)
  const stepId =
    step.step_code ||
    (step.step_id != null ? `step-${step.step_id}` : step.id != null ? `step-${step.id}` : genId())
  const base = {
    id: stepId,
    type: localType,
    name: step.step_name || step.step_type || '步骤',
    config: {},
    original: {
      ...step,
      id: step.step_id || step.id || null,
      step_code: step.step_code || null,
      children: undefined,
      quote_steps: step.quote_steps || [],
    },
  }

  if (localType === 'loop') {
    base.config = {
      loop_mode: step.loop_mode || '次数循环',
      loop_on_error: step.loop_on_error || '继续下一次循环',
      loop_maximums: step.loop_maximums ? Number(step.loop_maximums) : null,
      loop_interval: step.loop_interval ? Number(step.loop_interval) : 0,
      loop_iterable: step.loop_iterable || '',
      loop_timeout: step.loop_timeout ? Number(step.loop_timeout) : 0,
    }
    if (step.conditions && typeof step.conditions === 'object' && !Array.isArray(step.conditions)) {
      const condition = step.conditions
      base.config.condition_expr = condition.condition_expr != null ? String(condition.condition_expr) : ''
      base.config.condition_compare = condition.condition_compare || '非空'
      base.config.condition_value = condition.condition_value != null ? String(condition.condition_value) : ''
    } else {
      base.config.condition_expr = ''
      base.config.condition_compare = '非空'
      base.config.condition_value = ''
    }
    base.children = []
  } else if (localType === 'code') {
    base.config = {
      step_name: step.step_name || '',
      code: step.code || '',
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'tcp') {
    const argsType = (step.request_args_type || '').toString().toLowerCase()
    const payloadStr =
      argsType === 'json' ? JSON.stringify(step.request_body || {}, null, 2) : step.request_text || ''
    let body_format_mode = 'xml'
    if (!String(payloadStr).trim()) body_format_mode = 'xml'
    else if (argsType === 'json') body_format_mode = 'json'
    else if (/^\s*</.test(String(payloadStr))) body_format_mode = 'xml'
    else body_format_mode = 'text'
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      body_format_mode,
      request_args_type: 'raw',
      request_payload: payloadStr,
      request_text: step.request_text || null,
      data: {},
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'http') {
    base.config = {
      method: step.request_method || 'POST',
      url: step.request_url || '',
      request_args_type: step.request_args_type || 'none',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      data_source_name: step.data_source_name || '',
      data_source_desc: step.data_source_desc || '',
      params: Array.isArray(step.request_params) ? step.request_params : [],
      data: step.request_body || {},
      headers: Array.isArray(step.request_header) ? step.request_header : [],
      form_data: Array.isArray(step.request_form_data) ? step.request_form_data : [],
      form_urlencoded: Array.isArray(step.request_form_urlencoded) ? step.request_form_urlencoded : [],
      request_text: step.request_text || null,
      extract: step.extract_variables || {},
      validators: step.validators || {},
    }
  } else if (localType === 'if') {
    const raw = step.conditions
    const condition = raw != null && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
    base.config = {
      conditions: {
        condition_expr: condition.condition_expr != null ? String(condition.condition_expr) : '',
        condition_compare: condition.condition_compare || '非空',
        condition_value: condition.condition_value != null ? String(condition.condition_value) : '',
        condition_desc: condition.condition_desc != null ? String(condition.condition_desc) : '',
      },
    }
    base.children = []
  } else if (localType === 'wait') {
    base.config = { seconds: step.wait || 0 }
  } else if (localType === 'user_variables') {
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      session_variables: Array.isArray(step.session_variables) ? step.session_variables : [],
    }
  } else if (localType === 'quote') {
    base.config = {
      quote_case_id: step.quote_case_id ?? null,
      step_name: step.step_name || (step.quote_case?.case_name || '引用公共脚本'),
    }
  } else if (localType === 'database') {
    const ops = Array.isArray(step.database_operates) ? step.database_operates : []
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      database_searched: !!step.database_searched,
      database_operates: ops.length ? ops : [],
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  }

  if (step.children?.length && stepDefinitions[localType]?.allowChildren) {
    base.children = step.children.map(mapBackendStep).filter(Boolean)
    base.original.children = step.children
  }

  if (!stepDefinitions[localType]?.allowChildren) {
    delete base.children
    base.original.children = step.children || []
  } else if (!base.children) {
    base.children = []
    base.original.children = []
  }

  return base
}
