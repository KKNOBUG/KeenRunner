/**
 * 步骤树：后端数据 ↔ 前端树节点（执行配置弹窗、步骤编辑页共用）
 */

/** 步骤类型是否允许挂子节点 */
const stepDefinitions = {
  user_variables: { allowChildren: false },
  if: { allowChildren: true },
  wait: { allowChildren: false },
  loop: { allowChildren: true },
  tcp: { allowChildren: false },
  http: { allowChildren: false },
  code: { allowChildren: false },
  database: { allowChildren: false },
  redis: { allowChildren: false },
  quote: { allowChildren: false },
  assert: { allowChildren: false },
}

let seed = 1000
/** 生成临时前端步骤 id */
const genId = () => `step-${seed++}`

/** 后端 step_type 枚举文案 → 前端本地 type */
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
    case 'Redis请求':
      return 'redis'
    case '断言':
      return 'assert'
    default:
      return 'code'
  }
}

/**
 * 归一化请求体：后端 request_body 既可能是对象，也可能是 JSON 字符串（TEXT 列存储），
 * 统一转换为对象，兼容两种形态，提高健壮性。
 */
const normalizeRequestBody = (value) => {
  if (value == null) return {}
  if (typeof value === 'object') return value
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return {}
    try {
      const parsed = JSON.parse(trimmed)
      return parsed && typeof parsed === 'object' ? parsed : {}
    } catch {
      return {}
    }
  }
  return {}
}

/** 前序遍历步骤树 */
export function forEachStep(list, fn) {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children?.length) forEachStep(step.children, fn)
  }
}

/** 将后端步骤转为前端树节点（含 original、step_is_skipped，供编辑页与执行配置共用） */
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
    step_is_skipped: !!step.step_is_skipped,
    config: {},
    original: {
      ...step,
      id: step.step_id || step.id || null,
      step_code: step.step_code || null,
      step_is_skipped: !!step.step_is_skipped,
      children: undefined,
      quote_steps: step.quote_steps || [],
    },
  }

  if (localType === 'loop') {
    base.config = {
      loop_mode: step.loop_mode || '次数循环',
      loop_on_error: step.loop_on_error || '继续下一次循环',
      loop_maximums: step.loop_maximums != null && step.loop_maximums !== '' ? String(step.loop_maximums) : null,
      loop_interval: step.loop_interval ? Number(step.loop_interval) : 0,
      loop_iterable: step.loop_iterable || '',
      loop_timeout: step.loop_timeout ? Number(step.loop_timeout) : 0,
    }
    if (step.loop_conditions && typeof step.loop_conditions === 'object' && !Array.isArray(step.loop_conditions)) {
      const condition = step.loop_conditions
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
    const requestArgsType = ['xml', 'json', 'raw'].includes(argsType) ? argsType : 'xml'
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      data_source_id: step.data_source_id ?? null,
      data_source_name: step.data_source_name || '',
      data_source_desc: step.data_source_desc || '',
      request_args_type: requestArgsType,
      request_text: step.request_text || null,
      data: normalizeRequestBody(step.request_body),
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'http') {
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      method: step.request_method || 'POST',
      url: step.request_url || '',
      request_args_type: step.request_args_type || 'none',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      data_source_id: step.data_source_id ?? null,
      data_source_name: step.data_source_name || '',
      data_source_desc: step.data_source_desc || '',
      params: Array.isArray(step.request_params) ? step.request_params : [],
      data: normalizeRequestBody(step.request_body),
      headers: Array.isArray(step.request_header) ? step.request_header : [],
      form_data: Array.isArray(step.request_form_data) ? step.request_form_data : [],
      form_urlencoded: Array.isArray(step.request_form_urlencoded) ? step.request_form_urlencoded : [],
      request_text: step.request_text || null,
      defined_variables: Array.isArray(step.defined_variables) ? step.defined_variables : [],
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'if') {
    // 展示名固定为「条件分支」，忽略历史落库的 IF/ELIF/ELSE 后缀
    base.name = '条件分支'
    const rawBranches = Array.isArray(step.branch_items) ? step.branch_items : null
    if (rawBranches && rawBranches.length > 0) {
      base.config = {
        branch_items: rawBranches.map(b => ({
          _key: genId(),
          branch_type: b.branch_type || 'if',
          branch_conditions: b.branch_conditions && typeof b.branch_conditions === 'object' ? {
            condition_expr: b.branch_conditions.condition_expr != null ? String(b.branch_conditions.condition_expr) : '',
            condition_compare: b.branch_conditions.condition_compare || '非空',
            condition_value: b.branch_conditions.condition_value != null ? String(b.branch_conditions.condition_value) : '',
          } : null,
          branch_desc: b.branch_desc || '',
        })),
      }
      const branchChildren = []
      rawBranches.forEach((b, bi) => {
        if (Array.isArray(b.branch_children)) {
          b.branch_children.forEach(child => {
            const mapped = mapBackendStep(child)
            if (mapped) {
              mapped.branch_index = bi
              branchChildren.push(mapped)
            }
          })
        }
      })
      base.children = branchChildren
      base.original.children = branchChildren
      base.original.branch_items = step.branch_items
      return base
    }
    base.config = {
      branch_items: [{
        _key: genId(),
        branch_type: 'if',
        branch_conditions: {
          condition_expr: '',
          condition_compare: '非空',
          condition_value: '',
        },
        branch_desc: '',
      }],
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
  } else if (localType === 'redis') {
    const ops = Array.isArray(step.redis_operates) ? step.redis_operates : []
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      redis_searched: !!step.redis_searched,
      redis_operates: ops.length ? ops : [],
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'assert') {
    base.config = {
      step_name: step.step_name || '',
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
