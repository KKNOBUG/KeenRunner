<!--
  ExecConfigModal — 执行 / 调试前的「脚本执行配置」弹窗

  由父页面调用：
  - openRun(ctx)  — 使用已保存步骤树（用例列表「执行」等入口）
  - openDebug(ctx) — 使用当前编辑中的 steps（用例编辑页 handleDebug）

  运行确认后调用 api.executeStepTree；execute_type 由 openRun(ctx).executeType 传入（用例列表：定时执行）。
-->
<template>
  <n-modal
      v-if="!embedded"
      v-model:show="showModel"
      preset="card"
      title="脚本执行配置"
      :style="{ width: '70%' }"
      :segmented="{ content: true }"
      :close-on-esc="true"
      @after-enter="onModalAfterEnter"
  >
    <ExecConfigPanelBody />
    <template #footer>
      <n-space justify="end" size="medium">
        <n-button @click="showModel = false">取消</n-button>
        <n-button
            type="primary"
            :loading="execConfigMode === 'run' ? runLoading : debugLoading"
            @click="confirmExecConfigAndAction"
        >
          {{ execConfigMode === 'run' ? '确定并执行' : '确定并调试' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
  <div v-else class="exec-config-embedded">
    <div class="exec-config-embedded-body">
      <ExecConfigPanelBody />
      <div v-if="embeddedLoading" class="exec-config-embedded-loading">
        <n-spin size="medium" />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * ExecConfigModal.vue
 *
 * v-model:runLoading / debugLoading — 与父页面按钮 loading 同步
 *
 * 父组件传入的 ctx（openRun / openDebug）常用字段：
 *   - sourceSteps: 用于聚合配置行的步骤树（执行=已保存；调试=当前内存）
 *   - quoteStepsMap: 引用步骤内 HTTP/TCP/DB 也要参与聚合
 *   - projectOptions: 应用 id → 名称，左侧应用列表展示
 *   - resolveCaseId: () => number | null，执行/调试 payload 的 case_id
 *   - executeType: 执行类型枚举值（定时执行 等），对应后端 execute_type
 *   - ensureQuoteStepsLoaded: 仅 debug，打开前 await 加载 quoteStepsMap
 *   - buildDebugExecutePayload(step_exec_config_map, datasetPart): 调试专用请求体
 *
 * defineExpose: openRun(ctx), openDebug(ctx)
 *
 * 嵌入式（任务向导）：传 caseIds + savedConfigs，聚合多脚本步骤环境行，
 * 统一全局环境与数据源开关，通过 update:configs 回传
 * { env_mode, env_id, env_ids, [caseId]: { execute_count, involve_env_ids, steps_execute_config } }（只含引用键）
 */
import { computed, provide, reactive, ref, watch } from 'vue'
import {
  NButton,
  NModal,
  NSpace,
  NSpin,
} from 'naive-ui'
import api from '@/api'
import ExecConfigPanelBody from './ExecConfigPanelBody.vue'
import { loadQuoteStepsForList, toPositiveCaseId } from '@/views/autotest/steps/utils/prepareCaseExecute'
import { mapBackendStep } from '@/views/autotest/steps/utils/stepTreeMap'

const props = defineProps({
  embedded: { type: Boolean, default: false },
  caseId: { type: [Number, String], default: null },
  /** 嵌入式多脚本：聚合所有用例的步骤环境行，统一全局环境与数据源开关 */
  caseIds: { type: Array, default: () => [] },
  projectOptions: { type: Array, default: () => [] },
  savedConfig: { type: Object, default: null },
  /** 多脚本回填：{ [caseId]: config } */
  savedConfigs: { type: Object, default: null },
  /** 任务向导当前步骤：进入第三步骤(2)时才初始化 */
  currentStep: { type: Number, default: 0 },
  /** 任务级数据源开关初始状态(AutoTestTaskModel.dataset_enabled 独立字段) */
  datasetEnabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:config', 'update:configs', 'update:dataset-enabled'])

const runLoading = defineModel('runLoading', { type: Boolean, default: false })
const debugLoading = defineModel('debugLoading', { type: Boolean, default: false })

const embeddedLoading = ref(false)
/** 嵌入式：避免 init 与 emit 互相触发导致重复请求（值为 caseId 或 caseIds 拼接） */
const embeddedInitCaseId = ref(null)
let embeddedSkipConfigEmit = false
/** 恢复 savedConfig 时跳过 watcher，由 init 末尾统一拉取数据集，避免重复请求 */
let suppressDatasetAutoFetch = false
/** 已加载数据集名称的 case_id（或多脚本 key），同一 key 再次展开时不重复请求 */
const debugExecDatasetLoadedCaseId = ref(null)

const resolveEmbeddedCaseIds = () => {
  const fromArr = (Array.isArray(props.caseIds) ? props.caseIds : [])
    .map((x) => toPositiveCaseId(x))
    .filter(Boolean)
  if (fromArr.length) return [...new Set(fromArr)]
  const one = toPositiveCaseId(props.caseId)
  return one ? [one] : []
}

const isAggregatedEmbedded = computed(() => props.embedded && resolveEmbeddedCaseIds().length > 0 && Array.isArray(props.caseIds) && props.caseIds.length > 0)

/** 打开弹窗时由 index.vue 传入的上下文，见文件头注释 */
const execCtx = ref(null)

const showModel = ref(false)
const execConfigMode = ref('debug')
const execConfigCollapseExpanded = ref(['env'])
const debugExecDataSourceEnabled = ref(false)
const debugExecDatasetRows = ref([])
const debugExecDatasetSelectedIds = ref([])
const debugExecDatasetLoading = ref(false)
/** 任务向导：各脚本各自的数据源名称列表 { [caseId]: string[] } */
const debugExecDatasetNamesByCase = ref({})
const debugEnvMode = ref('single')
const debugGlobalEnvId = ref(null)
const debugSelectedProjectId = ref(null)
const debugEnvConfigDict = ref({})
/** 环境绑定ID → 环境名称（/env/list 提供，跨应用/跨节点同名换算是单环境模式的核心依据） */
const envNameById = ref(new Map())
/** 应用ID → 节点类型 → [{ env_id, env_name }]（行级环境选项与同名换算） */
const envBindsByProject = ref({})

const envLoading = ref(false)
const debugEnvOptions = ref([])
const debugRows = ref({ apiRows: [], dbRows: [], redisRows: [], fileRows: [] })

/** database_operates / redis_operates 可为数组或「序号→行」对象 */
const normalizeOpsList = (ops) => {
  if (!ops) return []
  if (Array.isArray(ops)) return ops
  if (typeof ops === 'object') return Object.values(ops)
  return []
}

const debugExecDatasetSelectedCount = computed(() => debugExecDatasetSelectedIds.value.length)

const debugExecDatasetBatchDisabled = computed(
    () =>
        execConfigMode.value === 'debug' ||
        debugExecDatasetLoading.value ||
        !debugExecDatasetRows.value.length,
)

const projectLabelMap = computed(() => {
  const m = new Map()
  const list = Array.isArray(execCtx.value?.projectOptions) ? execCtx.value.projectOptions : []
  list.forEach((x) => {
    if (x && x.value != null) m.set(String(x.value), x.label ?? String(x.value))
  })
  return m
})

/** 遍历步骤树，并在引用步骤（公共脚本/公共接口）下继续遍历 quoteStepsMap 内嵌步骤（执行配置聚合用） */
const forEachStepWithQuote = (list, fn, quoteStepsMap, { includeQuoteInner = true } = {}) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children?.length) forEachStepWithQuote(step.children, fn, quoteStepsMap, { includeQuoteInner })
    if (includeQuoteInner && (step?.type === 'quote_public_script' || step?.type === 'quote_public_api')) {
      const inner = quoteStepsMap?.[step.id] || []
      if (Array.isArray(inner) && inner.length) {
        forEachStepWithQuote(inner, fn, quoteStepsMap, { includeQuoteInner: false })
      }
    }
  }
}

/**
 * 从步骤树收集需在弹窗里配置环境的行（按应用+配置逻辑标识分组）
 * HTTP/TCP → apiRows；数据库多操作 → dbRows；Redis 多操作 → redisRows
 * 行对象只保留引用键（config_mode/env_id），配置名称与 IP/端口由环境配置字典实时反查
 */
const collectDebugRows = (sourceSteps, quoteStepsMap, caseId = null) => {
  const getBackendKeyFromStep = (step) => {
    const sid = step?.original?.id
    if (sid != null) return String(sid)
    const n = step?.name || step?.original?.step_name || ''
    return `@@${String(n).trim() || '未命名步骤'}`
  }

  const makeTarget = (partial) => {
    const t = { ...partial }
    if (caseId != null) t.case_id = caseId
    return t
  }

  const addToGroup = (map, groupKey, rowFactory, target) => {
    if (!map.has(groupKey)) map.set(groupKey, rowFactory())
    const row = map.get(groupKey)
    row.targets = row.targets || []
    const tkey = `${target.backend_key}#${target.local_step_id}#${target.op_index ?? ''}#${target.case_id ?? ''}`
    if (!row._targetKeySet) row._targetKeySet = new Set()
    if (!row._targetKeySet.has(tkey)) {
      row._targetKeySet.add(tkey)
      row.targets.push(target)
    }
    return row
  }

  const apiGroup = new Map()
  const dbGroup = new Map()
  const redisGroup = new Map()
  const fileGroup = new Map()

  const toMode = (raw) => (raw == null ? '' : String(raw).trim())
  const toBindId = (raw) => {
    const n = Number(raw)
    return Number.isFinite(n) && n > 0 ? n : null
  }

  const walk = Array.isArray(sourceSteps) ? sourceSteps : []
  forEachStepWithQuote(walk, (step) => {
    if (!step) return
    // 编辑回显：步骤上注入的绑定ID（initEmbeddedCases 预填），用于按 mode 还原行环境
    const stepEnvId = toBindId(step.env_id ?? step.original?.env_id)
    if (step.type === 'http' || step.type === 'tcp') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const project_id = cfg.request_project_id ?? orig.request_project_id ?? null
      if (!project_id) return
      const config_mode = toMode(cfg.request_config_mode ?? orig.request_config_mode)
      const backend_key = getBackendKeyFromStep(step)
      const groupKey = config_mode ? `p:${project_id}|m:${config_mode}` : `p:${project_id}|step:${backend_key}`
      addToGroup(
          apiGroup,
          groupKey,
          () => ({
            key: `api:${groupKey}`,
            project_id,
            config_mode: config_mode || null,
            env_id: stepEnvId,
            targets: [],
          }),
          makeTarget({ local_step_id: step.id, backend_key }),
      )
    } else if (step.type === 'database' || step.type === 'redis') {
      const isDb = step.type === 'database'
      const cfg = step.config || {}
      const orig = step.original || {}
      const opField = isDb ? 'database_operates' : 'redis_operates'
      const ops = cfg[opField] ?? orig[opField]
      const group = isDb ? dbGroup : redisGroup
      normalizeOpsList(ops).forEach((op, idx) => {
        if (!op) return
        const project_id = op.project_id ?? null
        if (!project_id) return
        const config_mode = toMode(op.config_mode ?? op.configMode)
        const backend_key = getBackendKeyFromStep(step)
        const groupKey = config_mode ? `p:${project_id}|m:${config_mode}` : `p:${project_id}|step:${backend_key}|op:${idx}`
        addToGroup(
            group,
            groupKey,
            () => ({
              key: `${isDb ? 'db' : 'redis'}:${groupKey}`,
              project_id,
              config_mode: config_mode || null,
              config_bucket: isDb ? 'database' : 'redis',
              op_field: opField,
              env_id: stepEnvId,
              targets: [],
            }),
            makeTarget({ local_step_id: step.id, backend_key, op_index: idx }),
        )
      })
    }
  }, quoteStepsMap)

  const strip = (rows) => rows.map((r) => {
    delete r._targetKeySet
    return r
  })

  return {
    apiRows: strip([...apiGroup.values()]),
    dbRows: strip([...dbGroup.values()]),
    redisRows: strip([...redisGroup.values()]),
    fileRows: strip([...fileGroup.values()]),
  }
}

/** 多脚本：按 row.key 合并聚合行，targets 带 case_id */
const mergeDebugRowBags = (bags) => {
  const mergeKind = (lists) => {
    const map = new Map()
    for (const list of lists) {
      for (const row of list || []) {
        if (!row?.key) continue
        if (!map.has(row.key)) {
          map.set(row.key, {
            ...row,
            targets: [...(row.targets || [])],
          })
          continue
        }
        const existing = map.get(row.key)
        const seen = new Set(
          (existing.targets || []).map(
            (t) => `${t.backend_key}#${t.local_step_id}#${t.op_index ?? ''}#${t.case_id ?? ''}`,
          ),
        )
        for (const t of row.targets || []) {
          const tkey = `${t.backend_key}#${t.local_step_id}#${t.op_index ?? ''}#${t.case_id ?? ''}`
          if (!seen.has(tkey)) {
            seen.add(tkey)
            existing.targets.push(t)
          }
        }
      }
    }
    return [...map.values()]
  }
  return {
    apiRows: mergeKind(bags.map((b) => b.apiRows)),
    dbRows: mergeKind(bags.map((b) => b.dbRows)),
    redisRows: mergeKind(bags.map((b) => b.redisRows)),
    fileRows: mergeKind(bags.map((b) => b.fileRows)),
  }
}

const debugApps = computed(() => {
  const byProject = new Map()
  const addCount = (pid, incApi = 0, incDb = 0, incRedis = 0) => {
    const k = String(pid)
    if (!byProject.has(k)) byProject.set(k, { project_id: pid, api: 0, db: 0, redis: 0 })
    const item = byProject.get(k)
    item.api += incApi
    item.db += incDb
    item.redis += incRedis
  }
  debugRows.value.apiRows.forEach((r) => addCount(r.project_id, 1, 0, 0))
  debugRows.value.dbRows.forEach((r) => addCount(r.project_id, 0, 1, 0))
  debugRows.value.redisRows.forEach((r) => addCount(r.project_id, 0, 0, 1))
  debugRows.value.fileRows.forEach((r) => addCount(r.project_id, 1, 0, 0))

  const list = Array.from(byProject.values()).map((x) => ({
    project_id: x.project_id,
    label: projectLabelMap.value.get(String(x.project_id)) || `应用${String(x.project_id)}`,
    apiCount: x.api,
    dbCount: x.db,
    redisCount: x.redis,
    totalCount: x.api + x.db + x.redis,
  }))
  list.sort((a, b) => String(a.project_id).localeCompare(String(b.project_id)))
  return list
})

const debugApiRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.apiRows.filter((r) => String(r.project_id) === String(pid))
})

const debugDbRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.dbRows.filter((r) => String(r.project_id) === String(pid))
})

const debugRedisRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.redisRows.filter((r) => String(r.project_id) === String(pid))
})

const debugFileRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.fileRows.filter((r) => String(r.project_id) === String(pid))
})

const resetModalFormState = () => {
  debugEnvMode.value = 'single'
  execConfigCollapseExpanded.value = ['env']
  debugExecDataSourceEnabled.value = false
  debugExecDatasetRows.value = []
  debugExecDatasetSelectedIds.value = []
  debugExecDatasetNamesByCase.value = {}
  debugExecDatasetLoadedCaseId.value = null
  debugGlobalEnvId.value = null
  debugSelectedProjectId.value = null
  debugEnvConfigDict.value = {}
  envNameById.value = new Map()
  envBindsByProject.value = {}
}

/** 聚合配置行引用的配置逻辑标识，供 /env/query 收窄环境选项 */
const collectReferencedConfigModes = () => {
  const modes = new Set()
  const grab = (rows) => {
    ;(rows || []).forEach((r) => {
      const mode = r.config_mode == null ? '' : String(r.config_mode).trim()
      if (mode) modes.add(mode)
    })
  }
  grab(debugRows.value.apiRows)
  grab(debugRows.value.dbRows)
  grab(debugRows.value.redisRows)
  grab(debugRows.value.fileRows)
  return [...modes]
}

/** 全局环境选项：配置字典中出现的绑定按名称去重（同名跨应用/节点只保留一个代表绑定ID），
 *  无配置行时回退环境绑定全集；value 为绑定ID，label 为环境名称 */
const deriveGlobalEnvOptions = () => {
  const dict = debugEnvConfigDict.value || {}
  const byName = new Map()
  const put = (envId) => {
    const numericId = Number(envId)
    const name = envNameById.value.get(numericId)
    if (!name || byName.has(name)) return
    byName.set(name, numericId)
  }
  Object.values(dict).forEach((envs) => {
    Object.keys(envs || {}).forEach(put)
  })
  if (!byName.size) envNameById.value.forEach((_name, envId) => put(envId))
  return [...byName.entries()]
      .sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'))
      .map(([name, envId]) => ({ label: name, value: envId }))
}

/** 环境选项加载：/env/list 提供绑定ID→名称（跨应用按名称换算的依据），
 *  /env/query 提供配置字典（判断某环境是否配置了某 log级标识），两请求并行且互不阻断 */
const loadEnvOptionsForContext = async () => {
  const project_ids = debugApps.value.map((x) => Number(x.project_id)).filter((x) => Number.isFinite(x))
  if (!project_ids.length) {
    debugEnvConfigDict.value = {}
    envNameById.value = new Map()
    envBindsByProject.value = {}
    debugEnvOptions.value = []
    return
  }
  envLoading.value = true
  try {
    const config_modes = collectReferencedConfigModes()
    const [envListRes, cfgRes] = await Promise.all([
      api.listEnvNames({ project_id: project_ids }).catch((e) => {
        console.error('加载环境绑定失败', e)
        return null
      }),
      api.queryEnvConfigClassifiedByProjects({
        project_ids,
        ...(config_modes.length ? { config_modes } : {}),
      }).catch((e) => {
        console.error('加载环境配置失败', e)
        return null
      }),
    ])
    const byProject = envListRes?.data && typeof envListRes.data === 'object' ? envListRes.data : {}
    const nameById = new Map()
    const bindsByProject = {}
    Object.entries(byProject).forEach(([pid, byType]) => {
      const typeMap = {}
      Object.entries(byType || {}).forEach(([envType, binds]) => {
        if (!Array.isArray(binds)) return
        typeMap[envType] = []
        binds.forEach((bind) => {
          const envId = Number(bind?.env_id)
          const envName = bind?.env_name == null ? '' : String(bind.env_name)
          if (!Number.isFinite(envId) || envId <= 0 || !envName) return
          nameById.set(envId, envName)
          typeMap[envType].push({ env_id: envId, env_name: envName })
        })
      })
      bindsByProject[String(pid)] = typeMap
    })
    envNameById.value = nameById
    envBindsByProject.value = bindsByProject
    debugEnvConfigDict.value = cfgRes?.data && typeof cfgRes.data === 'object' ? cfgRes.data : {}
    debugEnvOptions.value = deriveGlobalEnvOptions()
    // 已选全局环境不在新选项中时清空，避免提交一个不存在/无配置的绑定
    const currentGlobalId = Number(debugGlobalEnvId.value)
    if (
        Number.isFinite(currentGlobalId)
        && currentGlobalId > 0
        && !debugEnvOptions.value.some((opt) => Number(opt.value) === currentGlobalId)
    ) {
      const fallbackName = envNameById.value.get(currentGlobalId)
      const fallback = fallbackName
          ? debugEnvOptions.value.find((opt) => opt.label === fallbackName)
          : null
      debugGlobalEnvId.value = fallback ? fallback.value : null
    }
  } finally {
    envLoading.value = false
  }
}

/** 打开弹窗：重置表单 →（调试时）加载引用脚本 → 聚合配置行 → 拉取环境绑定与配置字典 */
const openWithContext = async (ctx) => {
  execCtx.value = ctx
  execConfigMode.value = ctx.mode
  resetModalFormState()
  if (ctx.mode === 'debug' && typeof ctx.ensureQuoteStepsLoaded === 'function') {
    await ctx.ensureQuoteStepsLoaded()
  }
  debugRows.value = collectDebugRows(ctx.sourceSteps, ctx.quoteStepsMap || {})
  showModel.value = true
  // 串行等待：全局环境选项先就位，避免与弹框内的配置字典收窄产生竞态覆盖
  await loadEnvOptionsForContext()
}

/** 调试：当前编辑步骤树 + buildDebugExecutePayload */
const openDebug = async (ctx) => {
  await openWithContext({ ...ctx, mode: 'debug' })
}

/** 执行：已保存步骤树，确认后 doExecuteFromSavedTree */
const openRun = async (ctx) => {
  await openWithContext({ ...ctx, mode: 'run' })
}

const onModalAfterEnter = () => {
  if (!debugSelectedProjectId.value && debugApps.value.length > 0) {
    debugSelectedProjectId.value = debugApps.value[0].project_id
  }
}

/** 行所属节点类型：API=app、数据库=database、Redis=redis、文件=file */
const rowBucketType = (row) => row?.config_bucket || 'app'

/**
 * 解析行实际生效的环境绑定ID。
 * - 多环境：行选绑定优先，未选回落全局；
 * - 单环境：全局绑定ID；全局绑定不属于行所属应用/节点类型时，按环境名称换算该应用同节点类型的同名绑定，
 *   换算不到返回 null（由缺失校验标红提示）。
 */
const resolveRowEnvId = (row) => {
  const globalIdRaw = Number(debugGlobalEnvId.value)
  const globalId = Number.isFinite(globalIdRaw) && globalIdRaw > 0 ? globalIdRaw : null
  if (debugEnvMode.value === 'multi' && row?.env_id != null) {
    const picked = Number(row.env_id)
    if (Number.isFinite(picked) && picked > 0) return picked
  }
  if (globalId == null) return null
  const type = rowBucketType(row)
  const binds = envBindsByProject.value[String(row.project_id)]?.[type] || []
  if (binds.some((bind) => Number(bind.env_id) === globalId)) return globalId
  const envName = envNameById.value.get(globalId)
  if (!envName) {
    // 绑定清单不可用时按配置字典兜底：字典含该绑定且节点类型匹配即视为当前绑定
    const projectEnvs = debugEnvConfigDict.value?.[row.project_id] || debugEnvConfigDict.value?.[String(row.project_id)] || {}
    return projectEnvs[String(globalId)]?.[type] ? globalId : null
  }
  const mapped = binds.find((bind) => bind.env_name === envName)
  return mapped ? Number(mapped.env_id) : null
}

/** 行在当前环境下的配置字典桶：project_id -> env_id -> 节点类型 -> config_mode -> 配置信息 */
const getBucket = (row, configType) => {
  const dict = debugEnvConfigDict.value || {}
  const envId = resolveRowEnvId(row)
  if (envId == null) return {}
  const p = dict?.[row.project_id] || dict?.[String(row.project_id)] || {}
  return p?.[String(envId)]?.[configType] || {}
}

const getDbDatabaseDisplay = (row) => {
  const bucket = getBucket(row, row.config_bucket || 'database')
  const info = row.config_mode ? bucket?.[row.config_mode] : null
  return info?.database_name != null ? String(info.database_name) : ''
}

const getRowAddrPreview = (row, configType) => {
  const bucket = getBucket(row, configType)
  const info = row.config_mode ? bucket?.[row.config_mode] : null
  return info?.config_host ? `${info.config_host}${info.config_port ? `:${info.config_port}` : ''}` : ''
}

/** 行绑定配置名称：当前环境未配置时回退该应用任一环境下的同名逻辑标识（Q15：仍显示绑定配置名） */
const getRowConfigName = (row) => {
  const dict = debugEnvConfigDict.value || {}
  const byEnv = dict?.[row.project_id] || dict?.[String(row.project_id)] || {}
  const type = rowBucketType(row)
  const mode = row.config_mode
  if (!mode) return ''
  const envId = resolveRowEnvId(row)
  const current = envId != null ? byEnv?.[String(envId)]?.[type]?.[mode] : null
  if (current?.config_name) return String(current.config_name)
  for (const buckets of Object.values(byEnv)) {
    const info = buckets?.[type]?.[mode]
    if (info?.config_name) return String(info.config_name)
  }
  return ''
}

/** 行完整性判定（Q15）：返回缺失原因，完整返回 null */
const rowMissingReason = (row) => {
  if (!row?.config_mode) return '配置未选择'
  if (resolveRowEnvId(row) == null) return '环境未选择'
  const bucket = getBucket(row, rowBucketType(row))
  if (!bucket?.[row.config_mode]) return '该环境未配置'
  return null
}

/** 多环境模式行级"环境"列选项：按行所属应用+节点类型过滤出已配置该逻辑标识的绑定；
 *  字典未覆盖该行时回退该应用全部绑定，仍为空时回退全局选项 */
const getRowEnvOptions = (row) => {
  const dict = debugEnvConfigDict.value || {}
  const byEnv = dict?.[row.project_id] || dict?.[String(row.project_id)]
  const type = rowBucketType(row)
  const mode = row.config_mode
  const options = []
  if (byEnv && typeof byEnv === 'object') {
    Object.keys(byEnv).forEach((envId) => {
      if (mode && !byEnv[envId]?.[type]?.[mode]) return
      const numericId = Number(envId)
      options.push({ label: envNameById.value.get(numericId) || `环境${envId}`, value: numericId })
    })
  }
  if (!options.length) {
    const binds = envBindsByProject.value[String(row.project_id)]?.[type] || []
    binds.forEach((bind) => options.push({ label: bind.env_name, value: Number(bind.env_id) }))
  }
  if (!options.length) return debugEnvOptions.value
  return options.sort((a, b) => a.label.localeCompare(b.label, 'zh-CN'))
}

const selectAllDebugExecDatasets = () => {
  if (execConfigMode.value === 'debug' || debugExecDatasetLoading.value) return
  debugExecDatasetSelectedIds.value = debugExecDatasetRows.value.map((r) => r.id)
}

const clearDebugExecDatasetSelection = () => {
  if (execConfigMode.value === 'debug' || debugExecDatasetLoading.value) return
  debugExecDatasetSelectedIds.value = []
}

const resolveExecCaseId = () => {
  const fromCtx = execCtx.value?.caseId
  if (fromCtx != null) return toPositiveCaseId(fromCtx)
  if (props.embedded) {
    const ids = resolveEmbeddedCaseIds()
    if (ids.length === 1) return ids[0]
    return toPositiveCaseId(props.caseId)
  }
  return null
}

const fetchDebugExecDatasetNames = async ({ force = false } = {}) => {
  const ids = props.embedded ? resolveEmbeddedCaseIds() : (() => {
    const one = resolveExecCaseId()
    return one ? [one] : []
  })()
  if (!ids.length) {
    debugExecDatasetRows.value = []
    debugExecDatasetNamesByCase.value = {}
    window.$message?.warning?.('缺少用例 ID，无法加载数据集名称')
    return
  }
  const cacheKey = ids.join(',')
  const autoAll = isAggregatedEmbedded.value
  if (
      !force
      && debugExecDatasetLoadedCaseId.value === cacheKey
      && (autoAll
          ? Object.keys(debugExecDatasetNamesByCase.value).length > 0
          : debugExecDatasetRows.value.length > 0)
  ) {
    if (autoAll) {
      const union = new Set()
      Object.values(debugExecDatasetNamesByCase.value).forEach((names) => {
        ;(names || []).forEach((n) => union.add(String(n)))
      })
      debugExecDatasetSelectedIds.value = [...union]
      debugExecDatasetRows.value = [...union].map((name) => ({ id: String(name), name: String(name) }))
    }
    return
  }
  debugExecDatasetLoading.value = true
  try {
    const results = await Promise.all(
      ids.map(async (cid) => {
        const fd = new FormData()
        fd.append('case_id', String(cid))
        const res = await api.queryDatasetNames(fd)
        const names = Array.isArray(res?.data) ? res.data.map(String) : []
        return { cid, names }
      }),
    )
    const byCase = {}
    results.forEach(({ cid, names }) => {
      byCase[String(cid)] = names
    })
    debugExecDatasetNamesByCase.value = byCase

    let nameList
    if (autoAll) {
      // 任务向导：开启即自动纳入各脚本全部数据源（按脚本分别下发）
      const union = new Set()
      results.forEach(({ names }) => names.forEach((n) => union.add(n)))
      nameList = [...union]
      debugExecDatasetSelectedIds.value = nameList.map(String)
    } else if (results.length === 1) {
      nameList = results[0].names
      const nameSet = new Set(nameList.map(String))
      debugExecDatasetSelectedIds.value = debugExecDatasetSelectedIds.value.filter((id) => nameSet.has(String(id)))
    } else {
      // 多脚本手工选择模式：仅展示交集
      let inter = null
      for (const { names } of results) {
        const set = new Set(names)
        if (inter == null) inter = set
        else inter = new Set([...inter].filter((n) => set.has(n)))
      }
      nameList = [...(inter || [])]
      const nameSet = new Set(nameList.map(String))
      debugExecDatasetSelectedIds.value = debugExecDatasetSelectedIds.value.filter((id) => nameSet.has(String(id)))
    }
    debugExecDatasetRows.value = nameList.map((name) => ({ id: String(name), name: String(name) }))
    debugExecDatasetLoadedCaseId.value = cacheKey
  } catch (e) {
    debugExecDatasetRows.value = []
    debugExecDatasetNamesByCase.value = {}
    debugExecDatasetLoadedCaseId.value = null
    console.error('queryDatasetNames failed', e)
  } finally {
    debugExecDatasetLoading.value = false
    if (props.embedded) emitEmbeddedConfigIfReady()
  }
}

const toggleDebugExecDatasetRow = (rowId, checked) => {
  const id = String(rowId)
  if (execConfigMode.value === 'debug') {
    debugExecDatasetSelectedIds.value = checked ? [id] : []
    return
  }
  const arr = debugExecDatasetSelectedIds.value
  if (checked) {
    if (!arr.includes(id)) debugExecDatasetSelectedIds.value = [...arr, id]
  } else {
    debugExecDatasetSelectedIds.value = arr.filter((x) => x !== id)
  }
}

const validateExecDatasetSelection = (silent = false) => {
  if (!debugExecDataSourceEnabled.value) return true
  if (debugExecDatasetLoading.value) {
    if (!silent) window.$message?.warning?.('数据集列表加载中，请稍候')
    return false
  }
  // 任务向导：数据源仅开关控制，不选择具体场景；执行时各脚本按自身条件查询全部数据源，无可用数据源不阻断
  if (isAggregatedEmbedded.value) {
    return true
  }
  if (!debugExecDatasetRows.value.length) {
    if (!silent) {
      window.$message?.warning?.('当前用例暂无可用数据集，请先上传数据源或关闭「请选择数据源」')
    }
    return false
  }
  const n = debugExecDatasetSelectedIds.value.length
  if (execConfigMode.value === 'debug') {
    if (n !== 1) {
      if (!silent) window.$message?.warning?.('调试模式下必须且仅能选择一个数据集')
      return false
    }
  } else if (n < 1) {
    if (!silent) window.$message?.warning?.('请至少勾选一个数据集，或关闭「请选择数据源」')
    return false
  }
  return true
}

watch(debugExecDataSourceEnabled, (on) => {
  if (!on) {
    debugExecDatasetSelectedIds.value = []
    debugExecDatasetRows.value = []
    debugExecDatasetNamesByCase.value = {}
    debugExecDatasetLoadedCaseId.value = null
    execConfigCollapseExpanded.value = execConfigCollapseExpanded.value.filter((n) => n !== 'dataset')
    return
  }
  if (suppressDatasetAutoFetch) return
  if (!isAggregatedEmbedded.value && !execConfigCollapseExpanded.value.includes('dataset')) {
    execConfigCollapseExpanded.value = [...execConfigCollapseExpanded.value, 'dataset']
  }
  // 任务向导仅开关控制数据源，无需拉取数据集名称列表
  if (!isAggregatedEmbedded.value) fetchDebugExecDatasetNames({ force: true })
})

/** 行级缺失收集（Q15）：环境未选择、配置逻辑标识缺失、当前环境未配置该标识；缺失原因同步用于行标红与提示 */
const collectExecConfigMissingRows = () => {
  const missing = []
  const check = (type, rows) => {
    ;(rows || []).forEach((row) => {
      const reason = rowMissingReason(row)
      if (!reason) return
      missing.push({
        type,
        project_id: row.project_id,
        text: `${getRowConfigName(row) || row.config_mode || '未命名配置'}（${reason}）`,
      })
    })
  }
  check('app', debugRows.value.apiRows)
  check('database', debugRows.value.dbRows)
  check('redis', debugRows.value.redisRows)
  check('file', debugRows.value.fileRows)
  return missing
}

const formatExecConfigMissingMessage = (missing, actionLabel) => {
  const typeLabel = { app: 'API', database: '数据库', redis: 'Redis', file: '文件' }
  const detail = missing
      .slice(0, 3)
      .map((m) => `${typeLabel[m.type] || m.type}:${m.text}`)
      .join('；')
  const more = missing.length > 3 ? ` 等${missing.length}条` : ''
  return `存在${missing.length}条配置未完成：${detail}${more}，请补全后再${actionLabel}`
}

/**
 * 根据弹窗聚合行生成后端 steps_execute_config（只含引用键 env_id/config_type/config_mode）。
 * caseIdFilter 用于多脚本按用例拆分；行环境由 resolveRowEnvId 解析（单环境=全局按名称换算，多环境=行选优先）。
 * 解析不到环境或当前环境未配置该逻辑标识的行不生成键（由缺失校验拦截，不编造引用）。
 */
const buildStepExecConfigMap = (caseIdFilter = null) => {
  const map = {}
  const targetBelongs = (t) => {
    if (caseIdFilter == null) return true
    if (t.case_id == null) return true
    return Number(t.case_id) === Number(caseIdFilter)
  }
  const applyRows = (rows, keyBuilder) => {
    ;(rows || []).forEach((row) => {
      const envId = resolveRowEnvId(row)
      const mode = row?.config_mode == null ? '' : String(row.config_mode).trim()
      if (envId == null || !mode) return
      const configType = rowBucketType(row)
      if (!getBucket(row, configType)?.[mode]) return
      const targets = Array.isArray(row.targets) ? row.targets : []
      targets.forEach((t) => {
        if (!targetBelongs(t)) return
        const key = keyBuilder(t)
        if (!key) return
        map[key] = { env_id: Number(envId), config_type: configType, config_mode: mode }
      })
    })
  }
  const stepKey = (t) => (t.backend_key == null ? '' : String(t.backend_key))
  const opKey = (t) => (t.op_index == null || t.op_index < 0 ? '' : `${String(t.backend_key)}_@@${t.op_index}`)
  applyRows(debugRows.value.apiRows, stepKey)
  applyRows(debugRows.value.dbRows, opKey)
  applyRows(debugRows.value.redisRows, opKey)
  applyRows(debugRows.value.fileRows, stepKey)
  return map
}

const getDatasetPayloadPart = () => {
  if (!debugExecDataSourceEnabled.value || !debugExecDatasetSelectedIds.value.length) {
    return {}
  }
  const part = { selected_dataset_names: [...debugExecDatasetSelectedIds.value] }
  return part
}

const confirmExecConfigBeforeRun = async (actionLabel, runAction) => {
  // 多环境模式下行级环境独立生效，全局环境可为空；单环境模式必须选全局环境
  if (debugEnvMode.value !== 'multi' && !debugGlobalEnvId.value) {
    window.$message?.warning?.('请选择全局环境')
    return
  }
  if (!validateExecDatasetSelection()) return
  const missingCfg = collectExecConfigMissingRows()
  if (missingCfg.length) {
    window.$message?.error?.(formatExecConfigMissingMessage(missingCfg, actionLabel))
    return
  }
  showModel.value = false
  await runAction(buildStepExecConfigMap())
}

/** 与 confirmExecConfigBeforeRun 约定：第 1 参为步骤执行配置字典（只含引用键） */
const doExecuteFromSavedTree = async (step_exec_config_map = null) => {
  const source = Array.isArray(execCtx.value?.sourceSteps) ? execCtx.value.sourceSteps : []
  if (!source.length) {
    window.$message?.warning?.('暂无已保存的步骤树可执行，请先保存后再执行')
    return
  }
  const resolveCaseId = execCtx.value?.resolveCaseId
  const cid = typeof resolveCaseId === 'function' ? resolveCaseId() : null
  if (cid == null) {
    window.$message?.warning?.('缺少用例 ID（case_id），无法执行，请先保存用例或从用例管理进入')
    return
  }
  const configMap =
      step_exec_config_map != null && typeof step_exec_config_map === 'object' && !Array.isArray(step_exec_config_map)
          ? step_exec_config_map
          : undefined
  runLoading.value = true
  try {
    const executeType = execCtx.value?.executeType || '定时执行'
    const payload = {
      case_id: cid,
      execute_type: executeType,
      initial_variables: [],
      ...(configMap != null ? { steps_execute_config: configMap } : {}),
      ...getDatasetPayloadPart(),
    }
    const res = await api.executeStepTree(payload)
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      if (executeType === '定时执行') {
        const taskId = res?.data?.celery_task_id
        const msg = res?.message || '任务已提交后台执行'
        window.$message?.success?.(taskId ? `${msg}（任务ID: ${taskId}）` : msg)
      } else {
        window.$message?.success?.(res?.message || '执行成功')
      }
    } else {
      window.$message?.error?.(res?.message || '执行失败')
    }
  } catch (error) {
    console.error('Failed to execute step tree', error)
    window.$message?.error?.(error?.message || '执行失败')
  } finally {
    runLoading.value = false
  }
}

const doDebug = async (step_exec_config_map = null) => {
  const buildPayload = execCtx.value?.buildDebugExecutePayload
  if (typeof buildPayload !== 'function') {
    window.$message?.error?.('调试参数未就绪')
    return
  }
  const payload = buildPayload(step_exec_config_map, getDatasetPayloadPart())
  if (!payload?.case_id) {
    window.$message?.warning?.('请先保存用例后再调试')
    return
  }
  debugLoading.value = true
  try {
    const res = await api.executeStepTree(payload)
    if (res?.code === '000000') {
      window.$message?.success?.(res.message)
    } else {
      window.$message?.error?.(res?.message || '调试失败')
    }
  } catch (error) {
    console.error('Failed to debug step tree', error)
    window.$message?.error?.(error?.message || '调试失败')
  } finally {
    debugLoading.value = false
  }
}

const confirmDebugConfigAndRun = async () => {
  await confirmExecConfigBeforeRun('调试', doDebug)
}

const confirmRunConfigAndExecute = async () => {
  await confirmExecConfigBeforeRun('执行', doExecuteFromSavedTree)
}

const confirmExecConfigAndAction = async () => {
  if (execConfigMode.value === 'run') {
    await confirmRunConfigAndExecute()
  } else {
    await confirmDebugConfigAndRun()
  }
}

provide(
    'execConfigPanel',
    reactive({
      taskWizardLayout: isAggregatedEmbedded,
      debugGlobalEnvId,
      debugEnvOptions,
      envLoading,
      debugEnvMode,
      debugExecDataSourceEnabled,
      execConfigCollapseExpanded,
      debugApps,
      debugSelectedProjectId,
      debugApiRowsForSelected,
      debugDbRowsForSelected,
      debugRedisRowsForSelected,
      debugFileRowsForSelected,
      debugExecDatasetLoading,
      debugExecDatasetRows,
      debugExecDatasetSelectedIds,
      debugExecDatasetBatchDisabled,
      debugExecDatasetSelectedCount,
      execConfigMode,
      getRowAddrPreview,
      getRowEnvOptions,
      resolveRowEnvId,
      getDbDatabaseDisplay,
      getRowConfigName,
      rowMissingReason,
      toggleDebugExecDatasetRow,
      selectAllDebugExecDatasets,
      clearDebugExecDatasetSelection,
    }),
)

/** 回显顶层环境配置：存储枚举 single/multiple，UI 内部值 single/multi；存量 env_name 按名称匹配代表绑定 */
const applySavedConfig = (cfg) => {
  if (!cfg || typeof cfg !== 'object') return
  if (cfg.env_mode === 'multiple' || cfg.env_mode === 'single') {
    debugEnvMode.value = cfg.env_mode === 'single' ? 'single' : 'multi'
  }
  let globalId = Number(cfg.env_id)
  if (!Number.isFinite(globalId) || globalId <= 0) {
    const legacyName = typeof cfg.env_name === 'string' ? cfg.env_name : ''
    const matched = legacyName ? debugEnvOptions.value.find((opt) => opt.label === legacyName) : null
    globalId = matched ? Number(matched.value) : null
  }
  if (globalId == null || !Number.isFinite(globalId) || globalId <= 0) return
  // 选项按环境名称去重（value 为代表绑定ID）：已保存绑定不在选项中时按名称换算，换算不到则留空由用户重选
  if (debugEnvOptions.value.some((opt) => Number(opt.value) === globalId)) {
    debugGlobalEnvId.value = globalId
    return
  }
  const envName = envNameById.value.get(globalId)
  const fallback = envName ? debugEnvOptions.value.find((opt) => opt.label === envName) : null
  debugGlobalEnvId.value = fallback ? fallback.value : null
}

/** 多脚本：按 savedConfigs 中各 case 的 steps_execute_config 精确定位行 targets 还原环境（同一 mode 的多行可各选不同环境） */
const applySavedStepsEnv = () => {
  const map = props.savedConfigs && typeof props.savedConfigs === 'object' ? props.savedConfigs : null
  if (!map) return
  // key: `${case_id}|${步骤配置键}` → 环境绑定ID；步骤配置键与 buildStepExecConfigMap 保持同一规则
  const envByTarget = new Map()
  Object.entries(map).forEach(([caseKey, cfg]) => {
    if (caseKey === 'env_mode' || caseKey === 'env_id' || caseKey === 'env_ids') return
    const steps = cfg?.steps_execute_config
    if (!steps || typeof steps !== 'object') return
    Object.entries(steps).forEach(([stepKey, sc]) => {
      const envId = Number(sc?.env_id)
      if (!Number.isFinite(envId) || envId <= 0) return
      envByTarget.set(`${caseKey}|${String(stepKey)}`, envId)
    })
  })
  if (!envByTarget.size) return
  const lookup = (target, type) => {
    if (target?.case_id == null) return null
    const backendKey = target.backend_key == null ? '' : String(target.backend_key)
    if (!backendKey) return null
    let stepKey = backendKey
    if (type === 'database' || type === 'redis') {
      // DB/Redis 多操作键为 `{backend_key}_@@{op_index}`，无操作下标时无对应配置
      if (target.op_index == null || Number(target.op_index) < 0) return null
      stepKey = `${backendKey}_@@${target.op_index}`
    }
    return envByTarget.get(`${String(target.case_id)}|${stepKey}`) ?? null
  }
  // 聚合行跨 case 共用同一个环境选择：取首个命中 target 的绑定ID（与生成侧统一写入一致）
  const applyTo = (rows, type) => {
    ;(rows || []).forEach((row) => {
      for (const target of Array.isArray(row.targets) ? row.targets : []) {
        const envId = lookup(target, type)
        if (envId != null) {
          row.env_id = envId
          break
        }
      }
    })
  }
  applyTo(debugRows.value.apiRows, 'app')
  applyTo(debugRows.value.dbRows, 'database')
  applyTo(debugRows.value.redisRows, 'redis')
  applyTo(debugRows.value.fileRows, 'file')
}

/** 多脚本回显：顶层环境配置(env_mode/env_id/env_ids) + 首个匹配脚本的用例级配置 */
const pickSavedConfigForCases = (ids) => {
  const map = props.savedConfigs && typeof props.savedConfigs === 'object' ? props.savedConfigs : null
  if (map) {
    const topLevelConfig = {
      env_mode: map.env_mode,
      env_id: map.env_id,
      env_ids: map.env_ids,
    }
    for (const cid of ids) {
      const cfg = map[String(cid)]
      if (cfg && typeof cfg === 'object') {
        return { ...topLevelConfig, ...cfg }
      }
    }
    return topLevelConfig
  }
  return props.savedConfig
}

/** 用例级涉及环境绑定ID：以步骤执行配置中的 env_id 去重升序 */
const collectInvolveEnvIds = (stepsConfig) => [...new Set(
  Object.values(stepsConfig || {})
    .map((sc) => Number(sc?.env_id))
    .filter((n) => Number.isFinite(n) && n > 0),
)].sort((a, b) => a - b)

/** 单脚本嵌入式回传：只含引用键（env_mode/env_id/env_ids + steps_execute_config），数据源由任务表字段独立承载 */
const buildConfigPayload = () => {
  const stepsConfig = buildStepExecConfigMap()
  const payload = {
    env_mode: debugEnvMode.value === 'multi' ? 'multiple' : 'single',
    env_id: debugGlobalEnvId.value ?? null,
    env_ids: collectInvolveEnvIds(stepsConfig),
    steps_execute_config: stepsConfig,
  }
  if (debugExecDataSourceEnabled.value && debugExecDatasetSelectedIds.value.length) {
    payload.selected_dataset_names = [...debugExecDatasetSelectedIds.value]
  }
  return payload
}

/** 多脚本：共享全局环境与全局数据源配置；用例级回传 involve_env_ids（权威）+ involve_envs（名称，仅供脚本行展示） */
const buildConfigsPayload = () => {
  const ids = resolveEmbeddedCaseIds()
  const out = {
    env_mode: debugEnvMode.value === 'multi' ? 'multiple' : 'single',
    env_id: debugGlobalEnvId.value ?? null,
    env_ids: [],
  }
  const allEnvIds = new Set()
  for (const cid of ids) {
    const stepsConfig = buildStepExecConfigMap(cid)
    const involveIds = collectInvolveEnvIds(stepsConfig)
    involveIds.forEach((id) => allEnvIds.add(id))
    out[String(cid)] = {
      execute_count: 1,  // 默认执行次数，后续由 TaskFormModal 覆盖
      involve_env_ids: involveIds,
      involve_envs: involveIds.map((id) => envNameById.value.get(id) || `env_id=${id}`),
      steps_execute_config: stepsConfig,
    }
  }
  out.env_ids = [...allEnvIds].sort((a, b) => a - b)
  return out
}

const validateConfigPayload = ({ silent = false, actionLabel = '保存' } = {}) => {
  // 多环境模式下行级环境独立生效（缺失由 collectExecConfigMissingRows 拦截），且全局环境已置灰可能为空，不在此强制
  if (debugEnvMode.value !== 'multi' && !debugGlobalEnvId.value) {
    if (!silent) window.$message?.warning?.('请选择全局环境')
    return false
  }
  if (!validateExecDatasetSelection(silent)) return false
  const missingCfg = collectExecConfigMissingRows()
  if (missingCfg.length) {
    if (!silent) window.$message?.error?.(formatExecConfigMissingMessage(missingCfg, actionLabel))
    return false
  }
  return true
}

const emitEmbeddedConfigIfReady = () => {
  if (!props.embedded || embeddedLoading.value || embeddedSkipConfigEmit) return
  // 不做完整性校验直接回传：配置更新必须实时同步到父组件，否则提交时会静默写入旧值；完整性校验由父组件提交时调用暴露的 validateConfigPayload 执行
  if (isAggregatedEmbedded.value) {
    emit('update:configs', buildConfigsPayload())
  } else {
    emit('update:config', buildConfigPayload())
  }
}

const initEmbeddedCases = async () => {
  const ids = resolveEmbeddedCaseIds()
  if (!ids.length) return
  embeddedLoading.value = true
  embeddedSkipConfigEmit = true
  suppressDatasetAutoFetch = true
  try {
    const bags = []
    const quoteStepsMapAll = {}
    
    // 使用 /build_splice_tree 接口批量获取多用例步骤树
    const res = await api.spliceStepTree({ case_ids: ids })
    const { details, indexes } = res?.data || {}
    
    if (!details || !indexes) {
      throw new Error('build_splice_tree 接口返回数据格式异常')
    }
    
    // 编辑模式：将保存的环境绑定ID注入到对应步骤，供 collectDebugRows 按行还原环境
    const savedConfigsMap = props.savedConfigs && typeof props.savedConfigs === 'object' ? props.savedConfigs : {}
    const stepEnvMap = new Map() // key: `${case_id}_${step_id}`, value: 环境绑定ID
    
    // 遍历保存的配置，提取每个步骤的环境信息
    Object.entries(savedConfigsMap).forEach(([key, cfg]) => {
      // 跳过顶层字段（env_mode/env_id/env_ids）
      if (key === 'env_mode' || key === 'env_id' || key === 'env_ids') return
      
      if (!cfg || typeof cfg !== 'object') return
      const stepsConfig = cfg.steps_execute_config || {}
      Object.entries(stepsConfig).forEach(([stepKey, stepCfg]) => {
        if (!stepCfg || typeof stepCfg !== 'object') return
        const envId = Number(stepCfg.env_id)
        if (!Number.isFinite(envId) || envId <= 0) return
        // stepKey 格式：step_id 或 step_id_@@op_index
        const stepId = stepKey.split('_@@')[0]
        stepEnvMap.set(`${key}_${stepId}`, envId)
      })
    })
    
    // 根据 indexes 拆分各用例的步骤树，并插入环境信息
    for (const cid of ids) {
      const caseIndexes = indexes[String(cid)] || []
      const caseSteps = caseIndexes.map(idx => {
        const step = details[idx]
        if (!step) return null
        
        // 插入环境绑定ID到步骤数据中（collectDebugRows 读取 step.env_id）
        const stepId = step.step_id || step.id
        if (stepId != null) {
          const envId = stepEnvMap.get(`${cid}_${stepId}`)
          if (envId != null) {
            step.env_id = envId
          }
        }
        return step
      }).filter(Boolean)
      
      const execSourceSteps = caseSteps.map(mapBackendStep).filter(Boolean)
      const quoteStepsMap = {}
      await loadQuoteStepsForList(execSourceSteps, quoteStepsMap)
      Object.assign(quoteStepsMapAll, quoteStepsMap)
      bags.push(collectDebugRows(execSourceSteps, quoteStepsMap, cid))
    }
    
    execCtx.value = {
      sourceSteps: [],
      quoteStepsMap: { ...quoteStepsMapAll },
      caseId: ids[0],
      projectOptions: props.projectOptions,
      resolveCaseId: () => ids[0],
      mode: 'run',
    }
    execConfigMode.value = 'run'
    resetModalFormState()
    debugRows.value = bags.length === 1 ? bags[0] : mergeDebugRowBags(bags)
    execConfigCollapseExpanded.value = ['env']
    if (!debugSelectedProjectId.value && debugApps.value.length > 0) {
      debugSelectedProjectId.value = debugApps.value[0].project_id
    }
    await loadEnvOptionsForContext()
    applySavedConfig(pickSavedConfigForCases(ids))
    applySavedStepsEnv()
    // 任务级数据源开关(任务表独立字段dataset_enabled)：初始状态由父组件传入；suppressDatasetAutoFetch期间不触发watcher，由init末尾统一拉取数据集
    if (props.datasetEnabled !== debugExecDataSourceEnabled.value) {
      debugExecDataSourceEnabled.value = props.datasetEnabled
    }
    if (debugExecDataSourceEnabled.value) {
      if (!isAggregatedEmbedded.value && !execConfigCollapseExpanded.value.includes('dataset')) {
        execConfigCollapseExpanded.value = [...execConfigCollapseExpanded.value, 'dataset']
      }
      // 任务向导仅开关控制数据源，无需拉取数据集名称列表
      if (!isAggregatedEmbedded.value) await fetchDebugExecDatasetNames({ force: true })
    }
  } catch (e) {
    console.error('加载用例执行配置失败', e)
    if (!props.embedded) return
    window.$message?.error?.(e?.message || '加载用例步骤树失败')
  } finally {
    suppressDatasetAutoFetch = false
    embeddedLoading.value = false
    embeddedSkipConfigEmit = false
    emitEmbeddedConfigIfReady()
  }
}

watch(
    () => (props.embedded ? resolveEmbeddedCaseIds().join(',') : null),
    (key) => {
      if (!props.embedded || !key) return
      if (embeddedInitCaseId.value === key) return
      embeddedInitCaseId.value = key
      // 不立即初始化，等待父组件通过 currentStep 触发
    },
    { immediate: true },
  )

// 监听父组件的 currentStep，进入第三步骤时才初始化
watch(
    () => props.currentStep,
    (step) => {
      if (!props.embedded) return
      if (step === 2 && embeddedInitCaseId.value) {
        initEmbeddedCases()
      }
    },
    { immediate: true },
  )

watch(debugGlobalEnvId, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

watch(debugEnvMode, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

watch(debugExecDataSourceEnabled, (on) => {
  if (props.embedded) {
    // 数据源开关变化回传父组件，保存时写入任务表 dataset_enabled 字段
    emit('update:dataset-enabled', on)
    emitEmbeddedConfigIfReady()
  }
})

watch(debugExecDatasetSelectedIds, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

/* 多环境：行级 env_id 变更需重新生成 steps_execute_config（深度监听聚合行） */
watch(
  debugRows,
  () => {
    if (props.embedded) emitEmbeddedConfigIfReady()
  },
  { deep: true },
)

/* 父组件 index.vue：execConfigModalRef.value?.openRun / openDebug；任务向导父组件提交前调用 validateConfigPayload 校验配置完整性 */
defineExpose({
  openDebug,
  openRun,
  validateConfigPayload,
})
</script>

<style>
.exec-config-embedded {
  border: none;
  border-radius: 0;
  padding: 0 12px;
  margin-bottom: 0;
  background: transparent;
  box-sizing: border-box;
  width: 100%;
  color: var(--n-text-color);
}

.exec-config-embedded-body {
  position: relative;
  width: 100%;
}

.exec-config-embedded-loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--n-color) 50%, transparent);
}

.exec-config-env-collapse-item :deep(.n-collapse-item__header) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  row-gap: 8px;
}

.exec-config-env-collapse-item :deep(.n-collapse-item__header-extra) {
  flex: 1;
  min-width: 0;
  margin-left: 12px;
}

.exec-config-env-header-extra {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
  width: 100%;
  font-size: var(--autotest-font-size);
  font-weight: 400;
  color: var(--n-text-color);
}

.exec-config-env-header-controls {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
  min-width: 0;
}

.exec-config-global-env-select {
  width: 220px;
  max-width: 100%;
}

/* 与折叠头内「单环境/多环境」small 按钮视觉高度对齐 */
.exec-config-global-env-select :deep(.n-base-selection) {
  --n-height: 28px;
  min-height: 28px;
  font-size: var(--autotest-font-size-small);
}

.exec-config-datasource-switch {
  flex-shrink: 0;
}

.exec-config-collapse :deep(.n-collapse-item) {
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: transparent;
}

.exec-config-collapse :deep(.n-collapse-item + .n-collapse-item) {
  margin-top: 12px;
}

.exec-config-collapse :deep(.n-collapse-item__header) {
  display: flex;
  align-items: center;
  padding: 10px 12px !important;
  font-size: var(--autotest-font-size);
  font-weight: 500;
  color: var(--n-text-color);
  min-height: 40px;
  box-sizing: border-box;
}

.exec-config-collapse :deep(.n-collapse-item__header-main) {
  display: flex;
  align-items: center;
  line-height: 1.4;
  font-size: inherit;
  font-weight: inherit;
}

.exec-config-collapse :deep(.n-collapse-item__content-inner) {
  padding: 0 12px 12px;
  background: transparent !important;
}

.exec-config-collapse :deep(.n-collapse-item__content-wrapper) {
  background: transparent !important;
}

.exec-config-collapse :deep(.n-collapse-item:not(.n-collapse-item--active) .n-collapse-item__content-wrapper) {
  height: 0 !important;
  min-height: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}

.exec-config-collapse :deep(.n-collapse-item:not(.n-collapse-item--active) .n-collapse-item__content-inner) {
  padding: 0 !important;
}

.exec-config-collapse :deep(.n-collapse-item--active) .exec-config-modal {
  min-height: 150px;
}

.exec-config-collapse :deep(.n-collapse-item--active) .exec-config-dataset-wrap {
  min-height: 200px;
  max-height: 300px;
}

.exec-config-dataset-wrap {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.exec-config-dataset-table {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: transparent;
  --exec-config-dataset-visible-rows: 5;
  --exec-config-dataset-row-height: 51px;
}

.exec-config-dataset-header {
  display: grid;
  grid-template-columns: 44px 72px 1fr;
  gap: 0;
  padding: 10px 12px;
  font-size: var(--autotest-font-size);
  font-weight: 600;
  color: var(--n-text-color-2);
  background-color: var(--n-action-color, var(--n-color-embedded));
  border-bottom: 1px solid var(--n-border-color);
}

.exec-config-dataset-header .col,
.exec-config-dataset-row .col {
  min-width: 0;
}

.exec-config-dataset-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 24px 16px;
}

.exec-config-dataset-body {
  flex: 1 1 auto;
  min-height: 0;
  max-height: calc(var(--exec-config-dataset-visible-rows) * var(--exec-config-dataset-row-height));
  overflow-x: hidden;
  overflow-y: auto;
}

.exec-config-dataset-row {
  display: grid;
  grid-template-columns: 44px 72px 1fr;
  padding: 10px 12px;
  font-size: var(--autotest-font-size);
  border-bottom: 1px solid var(--n-border-color);
}

.exec-config-dataset-row:last-child {
  border-bottom: none;
}

.exec-config-dataset-footer {
  flex-shrink: 0;
  margin-top: 10px;
  padding-top: 10px;
  font-size: var(--autotest-font-size-mini);
  color: var(--n-text-color-3);
}

.exec-config-dataset-footer-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.exec-config-dataset-footer-count {
  margin-left: auto;
  text-align: right;
}

.exec-config-dataset-mode-tip {
  margin-left: 6px;
  color: var(--n-text-color-3);
  font-size: var(--autotest-font-size-mini);
}

.exec-config-dataset-row .col.check {
  display: flex;
  align-items: center;
}

.exec-config-modal {
  display: flex;
  align-items: stretch;
  min-height: 0;
  overflow: hidden;
  background: transparent;
}

.exec-config-modal > .exec-config-left,
.exec-config-modal > .exec-config-right {
  min-height: 0;
  min-width: 0;
}

.exec-config-left {
  width: 200px;
  flex: 0 0 200px;
  border-right: 2px solid var(--n-border-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: transparent;
}

.exec-config-app-list {
  padding: 8px;
  overflow-y: auto;
  min-height: 0;
}

.exec-config-app-item {
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  margin-bottom: 8px;
}

.exec-config-app-item:hover {
  background-color: var(--n-action-color, var(--n-color-embedded));
}

.exec-config-app-item.is-active {
  border-color: var(--n-border-color);
  background-color: var(--n-action-color, var(--n-color-embedded));
}

.exec-config-app-name {
  font-size: var(--autotest-font-size);
  color: var(--n-text-color);
}

.exec-config-app-item.is-active .exec-config-app-name {
  font-weight: 600;
}

.exec-config-app-count {
  color: var(--n-text-color-3);
  margin-top: 4px;
  font-size: var(--autotest-font-size-mini);
}

.exec-config-empty {
  color: var(--n-text-color-3);
  padding: 16px 12px;
  font-size: var(--autotest-font-size-mini);
}

.exec-config-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 0 0 14px;
  background: transparent;
}

.exec-config-global-env-label {
  font-size: var(--autotest-font-size);
  font-weight: 400;
  color: var(--n-text-color);
  white-space: nowrap;
}

.exec-config-section {
  margin-top: 12px;
  flex-shrink: 0;
}

.exec-config-right > .exec-config-section:first-child {
  margin-top: 0;
}

.exec-config-section + .exec-config-section {
  margin-top: 16px;
}

.exec-config-section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 800;
  font-size: var(--autotest-font-size-huge);
  color: var(--n-text-color);
}

.exec-config-table {
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  overflow: hidden;
  --exec-config-visible-rows: 5;
  --exec-config-row-height: 51px;
}

.exec-config-table-body {
  max-height: calc(var(--exec-config-visible-rows) * var(--exec-config-row-height));
  overflow-x: hidden;
  overflow-y: auto;
}

.exec-config-table-header,
.exec-config-table-row {
  display: grid;
  grid-template-columns: 3fr 17fr 30fr 50fr;
  gap: 8px;
  align-items: center;
  padding: 10px 10px;
}

.exec-config-table.is-db .exec-config-table-header,
.exec-config-table.is-db .exec-config-table-row {
  grid-template-columns: 3fr 17fr 30fr 20fr 30fr;
}

.exec-config-table .col {
  min-width: 0;
}

.exec-config-table .col.addr {
  overflow: hidden;
}

.exec-config-table .col.addr :deep(.n-input-wrapper) {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.exec-config-table .col.addr :deep(input) {
  min-width: 0;
}

.exec-config-table .col > .n-select,
.exec-config-table .col > .n-input {
  width: 100%;
  max-width: 100%;
}

.exec-config-table-header {
  background-color: var(--n-action-color, var(--n-color-embedded)) !important;
  font-size: var(--autotest-font-size-mini);
  font-weight: 600;
  white-space: nowrap;
}

.exec-config-table-row {
  background-color: transparent;
  border-top: 1px solid var(--n-border-color);
}

.exec-config-table-row:hover {
  background-color: var(--n-action-color, var(--n-color-embedded));
}

/* 任务弹窗嵌入式：与独立「脚本执行配置」弹窗一致，避免卡片 --n-color-target(主色) 等变量污染 */
.exec-config-embedded .exec-config-app-item:hover,
.exec-config-embedded .exec-config-app-item.is-active {
  background-color: var(--n-action-color, var(--n-color-embedded)) !important;
}

.exec-config-embedded .exec-config-table-header {
  background-color: var(--n-action-color, var(--n-color-embedded)) !important;
}

.exec-config-embedded .exec-config-table-row,
.exec-config-embedded .exec-config-table-row:hover {
  background-color: transparent !important;
}

/* 任务弹窗：内层折叠项取消 Naive 嵌套 margin-left:32px，与上方「全局环境」左对齐 */
.exec-config-embedded .exec-config-collapse > .n-collapse-item {
  margin-left: 0 !important;
  margin-top: 0;
  background: transparent;
}

.exec-config-embedded .exec-config-collapse > .n-collapse-item + .n-collapse-item {
  margin-top: 12px;
}

.exec-config-embedded .exec-config-collapse {
  width: 100%;
  box-sizing: border-box;
}

.exec-config-section {
  background-color: transparent;
}

.exec-config-mode {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
