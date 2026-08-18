/**
 * 源数据模式：与 POST /autotest/step/update_or_create_tree 入参一致的 { case, steps } 校验与模板。
 * 不自动补齐缺失字段（含 step_no）；结构规则对齐后端 validate_step_tree_structure。
 * 步骤可选字段 step_is_skipped（跳过/注释，默认 false）随 JSON 原样保留，不做剥离。
 */

export const ALLOWED_CHILDREN_STEP_TYPES = new Set(['循环结构', '条件分支'])

export const VALID_STEP_TYPES = new Set([
  '用户变量',
  '条件分支',
  '等待控制',
  '循环结构',
  'TCP请求',
  'HTTP请求',
  '代码请求(Python)',
  '数据库请求',
  'Redis请求',
  '引用公共脚本',
  '断言',
])

/** 新建/无步骤时编辑器初始模板（对齐 update_or_create_tree 新建入参） */
export function createEmptyStepTreePayloadTemplate(casePartial = {}) {
  return {
    case: {
      case_id: casePartial.case_id ?? null,
      case_code: casePartial.case_code ?? null,
      case_name: casePartial.case_name ?? '',
      case_desc: casePartial.case_desc ?? '',
      case_tags: Array.isArray(casePartial.case_tags) ? casePartial.case_tags : [],
      case_type: casePartial.case_type ?? '用户脚本',
      case_attr: casePartial.case_attr ?? null,
      case_project: casePartial.case_project ?? null,
      case_steps: casePartial.case_steps ?? 0,
      case_state: casePartial.case_state ?? null,
      session_variables: casePartial.session_variables ?? null,
      case_version: casePartial.case_version ?? null,
      case_last_time: casePartial.case_last_time ?? null,
      updated_user: casePartial.updated_user ?? null,
    },
    steps: [],
  }
}

export function stringifyStepTreePayload(payload, space = 2) {
  return JSON.stringify(payload ?? createEmptyStepTreePayloadTemplate(), null, space)
}

/**
 * 新建用例：与后端 update_or_create_tree「新增」约定对齐。
 * - case：case_id、case_code 置为 null（保留键）
 * - steps（含 children）：step_id、step_code、case_id 置为 null；删除嵌套 case；parent_step_id 置 null
 */
export function stripIdentityFieldsForNewCase(payload) {
  if (!payload || typeof payload !== 'object') return payload

    const stripStep = (step) => {
    if (!step || typeof step !== 'object' || Array.isArray(step)) return step
    const next = { ...step }
    next.step_id = null
    next.step_code = null
    next.case_id = null
    next.parent_step_id = null
    // 新建/副本不得携带源用例数据源指针，否则会误触发外键场景列校验
    next.data_source_id = null
    next.data_source_name = null
    next.data_source_desc = null
    delete next.case
    delete next.id
    if (Array.isArray(next.children)) {
      next.children = next.children.map(stripStep)
    }
    if (Array.isArray(next.quote_steps)) {
      next.quote_steps = next.quote_steps.map(stripStep)
    }
    return next
  }

  let caseObj = payload.case
  if (caseObj && typeof caseObj === 'object' && !Array.isArray(caseObj)) {
    caseObj = {
      ...caseObj,
      case_id: null,
      case_code: null,
    }
  }

  return {
    ...payload,
    case: caseObj,
    steps: Array.isArray(payload.steps) ? payload.steps.map(stripStep) : [],
  }
}

/** 规范化后比较两段 JSON 文本是否等价（忽略空白与对象键序） */
export function isJsonTextEqual(a, b) {
  try {
    return stableStringify(JSON.parse(a || 'null')) === stableStringify(JSON.parse(b || 'null'))
  } catch {
    return String(a ?? '') === String(b ?? '')
  }
}

/** 递归按键排序后序列化，供脏检查忽略键序差异 */
export function stableStringify(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value)
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`
  }
  const keys = Object.keys(value).sort()
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(',')}}`
}

/**
 * 解析并校验源数据 JSON。
 * @returns {{ ok: true, payload: object } | { ok: false, message: string }}
 */
export function parseAndValidateStepTreePayload(text) {
  let raw
  try {
    raw = JSON.parse(text ?? '')
  } catch (e) {
    return { ok: false, message: `JSON 解析失败: ${e?.message || e}` }
  }

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ok: false, message: '根节点必须为对象，格式: { case, steps }' }
  }
  if (!Object.prototype.hasOwnProperty.call(raw, 'case') || raw.case == null || typeof raw.case !== 'object' || Array.isArray(raw.case)) {
    return { ok: false, message: '缺少 case 对象（与 update_or_create_tree 一致）' }
  }
  if (!Object.prototype.hasOwnProperty.call(raw, 'steps')) {
    return { ok: false, message: '缺少 steps 字段（步骤树数组）' }
  }
  if (!Array.isArray(raw.steps)) {
    return { ok: false, message: 'steps 必须为数组' }
  }

  const struct = validateStepTreeStructure(raw.steps)
  if (!struct.ok) {
    return struct
  }

  return { ok: true, payload: { case: raw.case, steps: raw.steps } }
}

/**
 * 对齐后端 StepTreeValidation.validate_step_tree_structure，并校验构建步骤树所需的基础字段。
 * 不自动补齐 step_no 等字段。
 */
export function validateStepTreeStructure(stepsData) {
  if (!Array.isArray(stepsData)) {
    return { ok: false, message: 'steps 必须为数组' }
  }

  const checkStep = (step, visitedIds, path, loc) => {
    if (!step || typeof step !== 'object' || Array.isArray(step)) {
      return { ok: false, message: `${loc} 必须为对象` }
    }

    const stepType = step.step_type
    if (stepType == null || String(stepType).trim() === '') {
      return { ok: false, message: `${loc} 缺少必填字段 step_type` }
    }
    if (!VALID_STEP_TYPES.has(stepType)) {
      return { ok: false, message: `${loc} step_type="${stepType}" 非法，需为后端枚举值` }
    }

    if (step.step_name == null || String(step.step_name).trim() === '') {
      return { ok: false, message: `${loc} 缺少必填字段 step_name` }
    }

    if (step.step_no == null || step.step_no === '') {
      return { ok: false, message: `${loc} 缺少必填字段 step_no（不会自动补齐）` }
    }
    const stepNo = Number(step.step_no)
    if (!Number.isFinite(stepNo) || stepNo < 1) {
      return { ok: false, message: `${loc} step_no 须为 >= 1 的整数` }
    }

  const hasId = step.step_id != null && step.step_id !== ''
  const hasCode = step.step_code != null && String(step.step_code).trim() !== ''
  if (hasId !== hasCode) {
    return {
      ok: false,
      message: `${loc} 更新步骤须同时提供 step_id 与 step_code；新建步骤请同时省略或都置为 null`,
    }
  }

    if (stepType === '引用公共脚本' && (step.quote_case_id == null || step.quote_case_id === '')) {
      return { ok: false, message: `${loc} 引用公共脚本须填写 quote_case_id` }
    }

    const stepId = step.step_id
    const stepCode = step.step_code

    if (stepId && visitedIds.has(stepId)) {
      return { ok: false, message: `步骤(step_id=${stepId}, step_code=${stepCode || 'N/A'})存在自循环引用` }
    }
    if (stepCode && path.includes(stepCode)) {
      return { ok: false, message: `步骤(step_code=${stepCode})存在自循环引用` }
    }

    const nextVisited = new Set(visitedIds)
    const nextPath = path.slice()
    if (stepId) nextVisited.add(stepId)
    if (stepCode) nextPath.push(stepCode)

    const children = step.children
    if (Array.isArray(children) && children.length > 0) {
      if (!ALLOWED_CHILDREN_STEP_TYPES.has(stepType)) {
        return {
          ok: false,
          message:
            `步骤(step_id=${stepId ?? 'N/A'}, step_code=${stepCode || 'N/A'}, step_type=${stepType})` +
            `不允许包含子步骤, 仅允许「循环结构」和「条件分支」包含子步骤`,
        }
      }
      for (let i = 0; i < children.length; i++) {
        const childResult = checkStep(children[i], nextVisited, nextPath, `${loc}.children[${i}]`)
        if (!childResult.ok) return childResult
      }
    } else if (children != null && !Array.isArray(children)) {
      return { ok: false, message: `${loc}.children 必须为数组或省略` }
    }

    return { ok: true }
  }

  for (let i = 0; i < stepsData.length; i++) {
    const r = checkStep(stepsData[i], new Set(), [], `steps[${i}]`)
    if (!r.ok) return r
  }
  return { ok: true }
}
