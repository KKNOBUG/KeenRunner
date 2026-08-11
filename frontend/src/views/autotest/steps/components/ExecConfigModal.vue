<!--
  ExecConfigModal — 执行 / 调试前的「脚本执行配置」弹窗

  由父页面调用：
  - openRun(ctx)  — 使用已保存步骤树（用例列表「执行」等入口）
  - openDebug(ctx) — 使用当前编辑中的 steps（步骤编辑页 handleDebug）

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
 * 统一全局环境与数据源开关，通过 update:configs 回传 { [caseId]: config }
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
})

const emit = defineEmits(['update:config', 'update:configs'])

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

const envLoading = ref(false)
const debugEnvOptions = ref([])
const debugEnvIdToName = ref(new Map())
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

/** 遍历步骤树，并在 quote 步骤下继续遍历 quoteStepsMap 内嵌步骤（执行配置聚合用） */
const forEachStepWithQuote = (list, fn, quoteStepsMap, { includeQuoteInner = true } = {}) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children?.length) forEachStepWithQuote(step.children, fn, quoteStepsMap, { includeQuoteInner })
    if (includeQuoteInner && step?.type === 'quote') {
      const inner = quoteStepsMap?.[step.id] || []
      if (Array.isArray(inner) && inner.length) {
        forEachStepWithQuote(inner, fn, quoteStepsMap, { includeQuoteInner: false })
      }
    }
  }
}

/**
 * 从步骤树收集需在弹窗里配置环境的行（按应用+配置名分组）
 * HTTP/TCP → apiRows；数据库多操作 → dbRows；Redis 多操作 → redisRows；文件类 → fileRows
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
  const apiConfigNameSetByProject = new Map()
  const dbConfigNameSetByProject = new Map()
  const dbNameSetByProject = new Map()
  const redisConfigNameSetByProject = new Map()
  const redisDbNameSetByProject = new Map()
  const fileConfigNameSetByProject = new Map()

  const pushSet = (map, k, v) => {
    if (!k) return
    const key = String(k)
    if (!map.has(key)) map.set(key, new Set())
    if (v != null && String(v).trim() !== '') map.get(key).add(String(v))
  }

  const walk = Array.isArray(sourceSteps) ? sourceSteps : []
  forEachStepWithQuote(walk, (step) => {
    if (!step) return
    if (step.type === 'http' || step.type === 'tcp') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const project_id = cfg.request_project_id ?? orig.request_project_id ?? null
      if (!project_id) return
      const request_config_name = cfg.request_config_name ?? orig.request_config_name ?? null
      pushSet(apiConfigNameSetByProject, project_id, request_config_name)
      const backend_key = getBackendKeyFromStep(step)
      const normalizedName = request_config_name != null ? String(request_config_name).trim() : ''
      const groupKey = normalizedName ? `p:${project_id}|n:${normalizedName}` : `p:${project_id}|step:${backend_key}`
      addToGroup(
          apiGroup,
          groupKey,
          () => ({
            key: `api:${groupKey}`,
            project_id,
            request_config_name: normalizedName || null,
            env_id: null,
            targets: [],
          }),
          makeTarget({ local_step_id: step.id, backend_key }),
      )
    } else if (step.type === 'database') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const ops = cfg.database_operates ?? orig.database_operates
      const list = normalizeOpsList(ops)
      list.forEach((op, idx) => {
        if (!op) return
        const project_id = op.project_id ?? null
        if (!project_id) return
        const opCfgName = op.config_name ?? op.configName ?? null
        const opDbName = op.database_name ?? op.databaseName ?? null
        pushSet(dbConfigNameSetByProject, project_id, opCfgName)
        pushSet(dbNameSetByProject, project_id, opDbName)
        const backend_key = getBackendKeyFromStep(step)
        const cfgName = opCfgName != null ? String(opCfgName).trim() : ''
        const dbName = opDbName != null ? String(opDbName).trim() : ''
        const groupKey = (cfgName && dbName)
            ? `p:${project_id}|c:${cfgName}|d:${dbName}`
            : `p:${project_id}|step:${backend_key}|op:${idx}`
        addToGroup(
            dbGroup,
            groupKey,
            () => ({
              key: `db:${groupKey}`,
              project_id,
              config_name: cfgName || null,
              database_name: dbName || null,
              config_bucket: 'database',
              op_field: 'database_operates',
              env_id: null,
              targets: [],
            }),
            makeTarget({ local_step_id: step.id, backend_key, op_index: idx }),
        )
      })
    } else if (step.type === 'redis') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const ops = cfg.redis_operates ?? orig.redis_operates
      const list = normalizeOpsList(ops)
      list.forEach((op, idx) => {
        if (!op) return
        const project_id = op.project_id ?? null
        if (!project_id) return
        const opCfgName = op.config_name ?? op.configName ?? null
        const opDbName = op.database_name ?? op.databaseName ?? null
        pushSet(redisConfigNameSetByProject, project_id, opCfgName)
        pushSet(redisDbNameSetByProject, project_id, opDbName)
        const backend_key = getBackendKeyFromStep(step)
        const cfgName = opCfgName != null ? String(opCfgName).trim() : ''
        const dbName = opDbName != null ? String(opDbName).trim() : ''
        const groupKey = (cfgName && dbName)
            ? `p:${project_id}|c:${cfgName}|d:${dbName}`
            : `p:${project_id}|step:${backend_key}|op:${idx}`
        addToGroup(
            redisGroup,
            groupKey,
            () => ({
              key: `redis:${groupKey}`,
              project_id,
              config_name: cfgName || null,
              database_name: dbName || null,
              config_bucket: 'redis',
              op_field: 'redis_operates',
              env_id: null,
              targets: [],
            }),
            makeTarget({ local_step_id: step.id, backend_key, op_index: idx }),
        )
      })
    }
  }, quoteStepsMap)

  const buildOptions = (set) => Array.from(set || []).map((x) => ({ label: x, value: x }))
  Array.from(apiGroup.values()).forEach((r) => {
    r._configNameSeed = buildOptions(apiConfigNameSetByProject.get(String(r.project_id)))
  })
  Array.from(dbGroup.values()).forEach((r) => {
    r._configNameSeed = buildOptions(dbConfigNameSetByProject.get(String(r.project_id)))
    r._dbNameSeed = buildOptions(dbNameSetByProject.get(String(r.project_id)))
  })
  Array.from(redisGroup.values()).forEach((r) => {
    r._configNameSeed = buildOptions(redisConfigNameSetByProject.get(String(r.project_id)))
    r._dbNameSeed = buildOptions(redisDbNameSetByProject.get(String(r.project_id)))
  })
  Array.from(fileGroup.values()).forEach((r) => {
    r._configNameSeed = buildOptions(fileConfigNameSetByProject.get(String(r.project_id)))
  })

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
  const mergeSeed = (a, b) => {
    if (!b?.length) return a || []
    const m = new Map((a || []).map((o) => [String(o.value), o]))
    b.forEach((o) => m.set(String(o.value), o))
    return [...m.values()]
  }
  const mergeKind = (lists) => {
    const map = new Map()
    for (const list of lists) {
      for (const row of list || []) {
        if (!row?.key) continue
        if (!map.has(row.key)) {
          map.set(row.key, {
            ...row,
            targets: [...(row.targets || [])],
            _configNameSeed: [...(row._configNameSeed || [])],
            _dbNameSeed: [...(row._dbNameSeed || [])],
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
        existing._configNameSeed = mergeSeed(existing._configNameSeed, row._configNameSeed)
        existing._dbNameSeed = mergeSeed(existing._dbNameSeed, row._dbNameSeed)
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
}

/** 将选中值（环境名，或历史遗留的 bind env_id）解析为环境名称 */
const resolveEnvName = (envKey) => {
  if (envKey == null || envKey === '') return null
  return debugEnvIdToName.value.get(String(envKey)) || null
}

const loadDebugEnvEnums = async () => {
  envLoading.value = true
  try {
    // listEnvNames：{ project_id: { api|file|database|redis: env_name[] } }，第二层 key 为枚举 .value
    const [namesRes, listRes] = await Promise.all([
      api.listEnvNames({ project_id: [] }),
      api.getEnvList({ page: 1, page_size: 9999, state: 0 }),
    ])
    const byProject = namesRes?.data || {}
    const names = new Set()
    Object.values(byProject).forEach((byType) => {
      if (!byType || typeof byType !== 'object') return
      Object.values(byType).forEach((arr) => {
        if (Array.isArray(arr)) arr.forEach((n) => { if (n) names.add(n) })
      })
    })
    const sorted = [...names].sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'))
    // 选项 value 用环境名，与 /config/query 分类字典第二层 key 对齐
    debugEnvOptions.value = sorted.map((n) => ({ label: n, value: n }))

    const m = new Map()
    sorted.forEach((n) => m.set(String(n), n))
    // 兼容旧任务/本地缓存里存的 bind env_id
    const list = Array.isArray(listRes?.data) ? listRes.data : []
    list.forEach((x) => {
      if (x?.env_id != null && x?.env_name) m.set(String(x.env_id), x.env_name)
    })
    debugEnvIdToName.value = m
  } catch (e) {
    console.error('加载环境枚举失败', e)
    debugEnvOptions.value = []
    debugEnvIdToName.value = new Map()
  } finally {
    envLoading.value = false
  }
}

/** 打开弹窗：重置表单 →（调试时）加载引用脚本 → 聚合配置行 → 拉环境枚举 */
const openWithContext = async (ctx) => {
  execCtx.value = ctx
  execConfigMode.value = ctx.mode
  resetModalFormState()
  if (ctx.mode === 'debug' && typeof ctx.ensureQuoteStepsLoaded === 'function') {
    await ctx.ensureQuoteStepsLoaded()
  }
  debugRows.value = collectDebugRows(ctx.sourceSteps, ctx.quoteStepsMap || {})
  showModel.value = true
  loadDebugEnvEnums()
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
  const project_ids = debugApps.value.map((x) => Number(x.project_id)).filter((x) => !Number.isNaN(x))
  if (project_ids.length) loadEnvConfigByProjects(project_ids)
}

const loadEnvConfigByProjects = async (project_ids) => {
  try {
    const res = await api.queryEnvConfigClassifiedByProjects({ project_ids })
    debugEnvConfigDict.value = res?.data || {}
  } catch (e) {
    console.error('加载环境配置失败', e)
    debugEnvConfigDict.value = {}
  }
}

const getEffectiveEnvIdForRow = (row) => (
    debugEnvMode.value === 'single'
        ? (debugGlobalEnvId.value || null)
        : (row.env_id || debugGlobalEnvId.value || null)
)

const getBucket = (row, configType) => {
  const dict = debugEnvConfigDict.value || {}
  const envName = resolveEnvName(getEffectiveEnvIdForRow(row))
  if (!envName) return {}
  // /config/query：project_id -> env_name -> api|file|database|redis -> config_name
  const p = dict?.[row.project_id] || dict?.[String(row.project_id)] || {}
  return p?.[envName]?.[configType] || {}
}

const getDbDatabaseDisplay = (row) => {
  const envId = getEffectiveEnvIdForRow(row)
  if (envId == null) return ''
  const bucketKey = row.config_bucket || 'database'
  const bucket = getBucket({ ...row, env_id: envId }, bucketKey)
  const cfgName = row.config_name
  const info = cfgName ? bucket?.[cfgName] : null
  const fromEnv = info?.database_name
  if (fromEnv != null && String(fromEnv).trim() !== '') return String(fromEnv)
  return row.database_name ? String(row.database_name) : ''
}

const getRowAddrPreview = (row, configType) => {
  const bucket = getBucket(row, configType)
  const name = configType === 'api' ? row.request_config_name : row.config_name
  const info = name ? bucket?.[name] : null
  return info?.config_host ? `${info.config_host}${info.config_port ? `:${info.config_port}` : ''}` : ''
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
  // 任务向导：开启后自动纳入全部数据源，无需手工勾选
  if (isAggregatedEmbedded.value) {
    const any = Object.values(debugExecDatasetNamesByCase.value || {}).some(
      (names) => Array.isArray(names) && names.length > 0,
    )
    if (!any) {
      if (!silent) {
        window.$message?.warning?.('所选脚本暂无可用数据源，请先上传数据源或关闭数据源开关')
      }
      return false
    }
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
  fetchDebugExecDatasetNames({ force: true })
})

watch(() => debugGlobalEnvId.value, (envId) => {
  const apply = (rows) => {
    rows.forEach((r) => { r.env_id = envId ?? null })
  }
  apply(debugRows.value.apiRows || [])
  apply(debugRows.value.dbRows || [])
  apply(debugRows.value.redisRows || [])
  apply(debugRows.value.fileRows || [])
})

const collectExecConfigMissingRows = () => {
  const missing = []
  const push = (type, row, text) => {
    missing.push({ type, project_id: row.project_id, text: String(text || '') })
  }

  const checkApiRow = (row) => {
    const envId = getEffectiveEnvIdForRow(row)
    if (envId == null || String(envId).trim() === '') {
      push('api', row, '环境未选择')
      return
    }
    const cfgName = row.request_config_name
    if (!cfgName || !String(cfgName).trim()) {
      push('api', row, '配置名未填写')
      return
    }
    const addr = getRowAddrPreview(row, 'api')
    if (!addr || !String(addr).trim()) {
      push('api', row, `${String(cfgName).trim()}(IP/端口未获取)`)
    }
  }

  const checkDbRow = (row) => {
    const envId = getEffectiveEnvIdForRow(row)
    if (envId == null || String(envId).trim() === '') {
      push('db', row, '环境未选择')
      return
    }
    const cfgName = row.config_name
    if (!cfgName || !String(cfgName).trim()) {
      push('db', row, '配置名未填写')
      return
    }
    const bucketKey = 'database'
    const bucket = getBucket({ ...row, env_id: envId }, bucketKey)
    const info = bucket?.[cfgName]
    const addr = getRowAddrPreview({ ...row, config_bucket: bucketKey }, bucketKey)
    if (!addr || !String(addr).trim()) {
      push('db', row, `${String(cfgName).trim()}(IP/端口未获取)`)
      return
    }
    const dbName = info?.database_name ?? row.database_name
    if (!dbName || !String(dbName).trim()) {
      push('db', row, `${String(cfgName).trim()}(库编号未获取)`)
    }
  }

  const checkRedisRow = (row) => {
    const envId = getEffectiveEnvIdForRow(row)
    if (envId == null || String(envId).trim() === '') {
      push('redis', row, '环境未选择')
      return
    }
    const cfgName = row.config_name
    if (!cfgName || !String(cfgName).trim()) {
      push('redis', row, '配置名未填写')
      return
    }
    const bucketKey = 'redis'
    const bucket = getBucket({ ...row, env_id: envId }, bucketKey)
    const info = bucket?.[cfgName]
    const addr = getRowAddrPreview({ ...row, config_bucket: bucketKey }, bucketKey)
    if (!addr || !String(addr).trim()) {
      push('redis', row, `${String(cfgName).trim()}(IP/端口未获取)`)
      return
    }
    const dbName = info?.database_name ?? row.database_name
    if (!dbName || !String(dbName).trim()) {
      push('redis', row, `${String(cfgName).trim()}(库编号未获取)`)
    }
  }

  const checkFileRow = (row) => {
        const envId = getEffectiveEnvIdForRow(row)
        if (envId == null || String(envId).trim() === '') {
          push('file', row, '环境未选择')
          return
        }
        const cfgName = row.config_name
        if (!cfgName || !String(cfgName).trim()) {
          push('file', row, '配置名未填写')
          return
        }
        const addr = getRowAddrPreview(row, 'file')
        if (!addr || !String(addr).trim()) {
          push('file', row, `${String(cfgName).trim()}(IP/端口未获取)`)
        }
      }

  ;(debugRows.value.apiRows || []).forEach(checkApiRow)
  ;(debugRows.value.dbRows || []).forEach(checkDbRow)
  ;(debugRows.value.redisRows || []).forEach(checkRedisRow)
  ;(debugRows.value.fileRows || []).forEach(checkFileRow)
  return missing
}

const formatExecConfigMissingMessage = (missing, actionLabel) =>
    `存在${missing.length}条配置未完成，请补全后再${actionLabel}`

const applyDebugConfigToSteps = () => {
  const findStep = execCtx.value?.findStep
  if (typeof findStep !== 'function') return

  debugRows.value.apiRows.forEach((r) => {
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      if (!step.config) step.config = {}
      step.config.request_project_id = r.project_id ?? step.config.request_project_id
      step.config.request_config_name = r.request_config_name ?? step.config.request_config_name
    })
  })

  debugRows.value.dbRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucketKey = 'database'
    const bucket = getBucket({ ...r, env_id: envId }, bucketKey)
    const cfgNm = r.config_name
    const info = cfgNm ? bucket?.[cfgNm] : null
    const resolvedDb = info?.database_name ?? r.database_name
    const opField = 'database_operates'
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      const cfg = step.config || {}
      const ops = Array.isArray(cfg[opField]) ? cfg[opField] : normalizeOpsList(cfg[opField])
      const idx = t.op_index
      if (idx == null || !ops[idx]) return
      ops[idx].project_id = r.project_id ?? ops[idx].project_id
      ops[idx].config_name = r.config_name ?? ops[idx].config_name
      ops[idx].database_name = resolvedDb ?? ops[idx].database_name
    })
  })

  debugRows.value.redisRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucketKey = 'redis'
    const bucket = getBucket({ ...r, env_id: envId }, bucketKey)
    const cfgNm = r.config_name
    const info = cfgNm ? bucket?.[cfgNm] : null
    const resolvedDb = info?.database_name ?? r.database_name
    const opField = 'redis_operates'
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      const cfg = step.config || {}
      const ops = Array.isArray(cfg[opField]) ? cfg[opField] : normalizeOpsList(cfg[opField])
      const idx = t.op_index
      if (idx == null || !ops[idx]) return
      ops[idx].project_id = r.project_id ?? ops[idx].project_id
      ops[idx].config_name = r.config_name ?? ops[idx].config_name
      ops[idx].database_name = resolvedDb ?? ops[idx].database_name
    })
  })
}

/** 根据弹窗表格与环境配置字典，生成后端 steps_execute_config 对象；caseIdFilter 用于多脚本拆分 */
const buildStepExecConfigMap = (env_name, caseIdFilter = null) => {
  const map = {}
  const targetBelongs = (t) => {
    if (caseIdFilter == null) return true
    if (t.case_id == null) return true
    return Number(t.case_id) === Number(caseIdFilter)
  }
  const prefill = (rows, mode) => {
    rows.forEach((r) => {
      const targets = Array.isArray(r.targets) ? r.targets : []
      targets.forEach((t) => {
        if (!targetBelongs(t)) return
        const bk = String(t.backend_key)
        if (mode === 'db' && t.op_index != null && t.op_index >= 0) {
          map[`${bk}_@@${t.op_index}`] = {}
        } else if (mode !== 'db') {
          map[bk] = {}
        }
      })
    })
  }
  prefill(debugRows.value.apiRows || [], 'api')
  prefill(debugRows.value.dbRows || [], 'db')
  prefill(debugRows.value.redisRows || [], 'db')
  prefill(debugRows.value.fileRows || [], 'file')

  debugRows.value.apiRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'api')
    const name = r.request_config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      if (!targetBelongs(t)) return
      map[String(t.backend_key)] = {
        env_name,
        config_type: 'api',
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? null,
      }
    })
  })

  debugRows.value.dbRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucketKey = 'database'
    const bucket = getBucket({ ...r, env_id: envId }, bucketKey)
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      if (!targetBelongs(t)) return
      const opIdx = t.op_index
      if (opIdx == null || opIdx < 0) return
      map[`${String(t.backend_key)}_@@${opIdx}`] = {
        env_name,
        config_type: bucketKey,
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? r.database_name ?? null,
      }
    })
  })

  debugRows.value.redisRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucketKey = 'redis'
    const bucket = getBucket({ ...r, env_id: envId }, bucketKey)
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      if (!targetBelongs(t)) return
      const opIdx = t.op_index
      if (opIdx == null || opIdx < 0) return
      map[`${String(t.backend_key)}_@@${opIdx}`] = {
        env_name,
        config_type: bucketKey,
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? r.database_name ?? null,
      }
    })
  })

  debugRows.value.fileRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'file')
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      if (!targetBelongs(t)) return
      map[String(t.backend_key)] = {
        env_name,
        config_type: 'file',
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? null,
      }
    })
  })

  return map
}

const getDatasetPayloadPart = () => {
  if (!debugExecDataSourceEnabled.value || !debugExecDatasetSelectedIds.value.length) {
    return {}
  }
  return { selected_dataset_names: [...debugExecDatasetSelectedIds.value] }
}

const confirmExecConfigBeforeRun = async (actionLabel, runAction) => {
  if (!debugGlobalEnvId.value) {
    window.$message?.warning?.('请选择全局环境')
    return
  }
  const env_name = resolveEnvName(debugGlobalEnvId.value)
  if (!env_name) {
    window.$message?.warning?.('全局环境无效，请重新选择')
    return
  }
  if (!validateExecDatasetSelection()) return
  const missingCfg = collectExecConfigMissingRows()
  if (missingCfg.length) {
    window.$message?.error?.(formatExecConfigMissingMessage(missingCfg, actionLabel))
    return
  }
  showModel.value = false
  const step_exec_config_map = buildStepExecConfigMap(env_name)
  await runAction(env_name, step_exec_config_map)
}

/** 与 confirmExecConfigBeforeRun 约定：第 1 参为 env_name，第 2 参为步骤执行配置字典 */
const doExecuteFromSavedTree = async (_env_name, step_exec_config_map = null) => {
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

const doDebug = async (_env_name, step_exec_config_map = null) => {
  const buildPayload = execCtx.value?.buildDebugExecutePayload
  if (typeof buildPayload !== 'function') {
    window.$message?.error?.('调试参数未就绪')
    return
  }
  const payload = buildPayload(step_exec_config_map, getDatasetPayloadPart())
  if (!payload?.case_id) {
    window.$message?.warning?.('缺少用例 ID（case_id），请先保存用例后再调试')
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
  applyDebugConfigToSteps()
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
      getDbDatabaseDisplay,
      toggleDebugExecDatasetRow,
      selectAllDebugExecDatasets,
      clearDebugExecDatasetSelection,
    }),
)

const applySavedConfig = (cfg) => {
  if (!cfg || typeof cfg !== 'object') return
  if (cfg.global_env_id != null) {
    // 选项 value 已改为环境名；兼容历史缓存里的 bind env_id
    debugGlobalEnvId.value = resolveEnvName(cfg.global_env_id) || cfg.global_env_id
  }
  if (cfg.env_mode === 'multi' || cfg.env_mode === 'single') debugEnvMode.value = cfg.env_mode
  const names = cfg.selected_dataset_names
  if (Array.isArray(names) && names.length) {
    debugExecDataSourceEnabled.value = true
    debugExecDatasetSelectedIds.value = names.map(String)
  }
}

const pickSavedConfigForCases = (ids) => {
  const map = props.savedConfigs && typeof props.savedConfigs === 'object' ? props.savedConfigs : null
  if (map) {
    for (const cid of ids) {
      const cfg = map[String(cid)]
      if (cfg && typeof cfg === 'object' && (cfg.global_env_id != null || cfg.env_mode || Array.isArray(cfg.selected_dataset_names))) {
        return cfg
      }
    }
    for (const cid of ids) {
      if (map[String(cid)]) return map[String(cid)]
    }
  }
  if (ids.length === 1 && props.savedConfig) return props.savedConfig
  return props.savedConfig
}

const buildConfigPayload = () => {
  const env_name = resolveEnvName(debugGlobalEnvId.value)
  const payload = {
    steps_execute_config: buildStepExecConfigMap(env_name),
    global_env_id: debugGlobalEnvId.value,
    env_mode: debugEnvMode.value,
    env_name,
  }
  if (debugExecDataSourceEnabled.value && debugExecDatasetSelectedIds.value.length) {
    payload.selected_dataset_names = [...debugExecDatasetSelectedIds.value]
  }
  return payload
}

/** 多脚本：共享全局环境；数据源按脚本自动纳入各自全部数据集 */
const buildConfigsPayload = () => {
  const env_name = resolveEnvName(debugGlobalEnvId.value)
  const ids = resolveEmbeddedCaseIds()
  const shared = {
    global_env_id: debugGlobalEnvId.value,
    env_mode: debugEnvMode.value,
    env_name,
  }
  const out = {}
  for (const cid of ids) {
    const cfg = {
      ...shared,
      steps_execute_config: buildStepExecConfigMap(env_name, cid),
    }
    if (debugExecDataSourceEnabled.value) {
      const names = debugExecDatasetNamesByCase.value[String(cid)] || []
      if (names.length) {
        cfg.selected_dataset_names = [...names]
      }
    }
    out[String(cid)] = cfg
  }
  return out
}

const validateConfigPayload = ({ silent = false, actionLabel = '保存' } = {}) => {
  if (!debugGlobalEnvId.value) {
    if (!silent) window.$message?.warning?.('请选择全局环境')
    return false
  }
  const env_name = resolveEnvName(debugGlobalEnvId.value)
  if (!env_name) {
    if (!silent) window.$message?.warning?.('全局环境无效，请重新选择')
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
  if (!validateConfigPayload({ silent: true })) return
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
    for (const cid of ids) {
      const res = await api.getAutoTestStepTree({ case_id: cid })
      const data = Array.isArray(res?.data) ? res.data : []
      const execSourceSteps = data.map(mapBackendStep).filter(Boolean)
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
    await loadDebugEnvEnums()
    if (!debugSelectedProjectId.value && debugApps.value.length > 0) {
      debugSelectedProjectId.value = debugApps.value[0].project_id
    }
    const project_ids = debugApps.value.map((x) => Number(x.project_id)).filter((x) => !Number.isNaN(x))
    if (project_ids.length) await loadEnvConfigByProjects(project_ids)
    applySavedConfig(pickSavedConfigForCases(ids))
    if (debugExecDataSourceEnabled.value) {
      if (!isAggregatedEmbedded.value && !execConfigCollapseExpanded.value.includes('dataset')) {
        execConfigCollapseExpanded.value = [...execConfigCollapseExpanded.value, 'dataset']
      }
      await fetchDebugExecDatasetNames({ force: true })
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
      initEmbeddedCases()
    },
    { immediate: true },
  )

watch(debugGlobalEnvId, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

watch(debugEnvMode, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

watch(debugExecDataSourceEnabled, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

watch(debugExecDatasetSelectedIds, () => {
  if (props.embedded) emitEmbeddedConfigIfReady()
})

/** 父组件 index.vue：execConfigModalRef.value?.openRun / openDebug */
defineExpose({
  openDebug,
  openRun,
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
