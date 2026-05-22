<!--
  ExecConfigModal — 执行 / 调试前的「脚本执行配置」弹窗

  由 index.vue 调用：
  - openRun(ctx)  — 使用已保存步骤树（handleRun 重新请求后端后传入）
  - openDebug(ctx) — 使用当前编辑中的 steps（handleDebug 传入 buildDebugExecutePayload）

  确认后调用 api.executeStepTree，附带环境名与 steps_execute_config 映射。
-->
<template>
  <n-modal
      v-model:show="showModel"
      preset="card"
      title="脚本执行配置"
      :style="{ width: '70%' }"
      :segmented="{ content: true }"
      :close-on-esc="true"
      @after-enter="onModalAfterEnter"
  >
    <div class="exec-config-toolbar-row">
      <div class="exec-config-toolbar-inner">
        <n-space align="center" wrap :size="[8, 12]">
          <span class="exec-config-global-env-label">全局环境：</span>
          <n-select
              v-model:value="debugGlobalEnvId"
              :options="debugEnvOptions"
              :loading="envLoading"
              placeholder="全局环境"
              clearable
              filterable
              style="width: 220px;"
          />
          <div class="exec-config-mode">
            <n-button
                size="small"
                :type="debugEnvMode === 'single' ? 'primary' : 'default'"
                @click="debugEnvMode = 'single'"
            >
              单环境
            </n-button>
            <n-button
                size="small"
                :type="debugEnvMode === 'multi' ? 'primary' : 'default'"
                @click="debugEnvMode = 'multi'"
            >
              多环境
            </n-button>
          </div>
        </n-space>
        <n-switch
            v-model:value="debugExecDataSourceEnabled"
            size="large"
            :rail-style="debugExecDataSourceRailStyle"
            style="font-size: 12px;"
        >
          <template #checked>请选择数据源</template>
          <template #unchecked>未启用数据源</template>
        </n-switch>
      </div>
    </div>

    <n-collapse
        v-model:expanded-names="execConfigCollapseExpanded"
        class="exec-config-collapse"
        arrow-placement="right"
    >
      <n-collapse-item title="应用环境配置" name="env">
        <div class="exec-config-modal">
          <div class="exec-config-left">
            <div class="exec-config-app-list">
              <div
                  v-for="app in debugApps"
                  :key="String(app.project_id)"
                  class="exec-config-app-item"
                  :class="{ 'is-active': String(app.project_id) === String(debugSelectedProjectId) }"
                  @click="debugSelectedProjectId = app.project_id"
              >
                <div class="exec-config-app-name">{{ app.label }}</div>
                <div class="exec-config-app-count">{{ app.totalCount }}条配置</div>
              </div>
              <div v-if="debugApps.length === 0" class="exec-config-empty">
                暂无可配置的请求步骤
              </div>
            </div>
          </div>

          <div class="exec-config-right">
            <div v-if="!debugSelectedProjectId" class="exec-config-empty">请选择应用</div>
            <template v-else>
              <div v-if="debugApiRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  API
                  <n-tag size="small" type="info">{{ debugApiRowsForSelected.length }}条</n-tag>
                </div>
                <div>
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body">
                    <div v-for="(row, idx) in debugApiRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="debugEnvOptions"
                            size="small"
                            :disabled="!debugGlobalEnvId || debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.request_config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="getRowAddrPreview(row, 'api')"
                            size="small"
                            disabled
                            :placeholder="debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="debugDbRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  DataBase
                  <n-tag size="small" type="warning">{{ debugDbRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-db">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col config">数据库名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body">
                    <div v-for="(row, idx) in debugDbRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="debugEnvOptions"
                            size="small"
                            :disabled="!debugGlobalEnvId || debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col config">
                        <n-input
                            :value="getDbDatabaseDisplay(row)"
                            size="small"
                            disabled
                            :placeholder="debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="getRowAddrPreview(row, 'database')"
                            size="small"
                            disabled
                            :placeholder="debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="debugFileRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  File Server
                  <n-tag size="small" type="success">{{ debugFileRowsForSelected.length }}条</n-tag>
                </div>
                <div>
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body">
                    <div v-for="(row, idx) in debugFileRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="debugEnvOptions"
                            size="small"
                            :disabled="!debugGlobalEnvId || debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="getRowAddrPreview(row, 'file')"
                            size="small"
                            disabled
                            :placeholder="debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </n-collapse-item>

      <n-collapse-item v-if="debugExecDataSourceEnabled" title="数据驱动配置" name="dataset">
        <div class="exec-config-dataset-wrap">
          <div class="exec-config-dataset-table">
            <div class="exec-config-dataset-header">
              <div class="col check"></div>
              <div class="col idx">#</div>
              <div class="col name">数据驱动场景名称</div>
            </div>
            <div v-if="debugExecDatasetLoading" class="exec-config-dataset-empty">
              <n-spin size="medium" description="加载数据源列表..." />
            </div>
            <div v-else-if="!debugExecDatasetRows.length" class="exec-config-dataset-empty">
              <n-empty description="暂无数据, 请先上传数据源或确认用例已保存" />
            </div>
            <div v-else class="exec-config-dataset-body">
              <div
                  v-for="(row, idx) in debugExecDatasetRows"
                  :key="row.id"
                  class="exec-config-dataset-row"
              >
                <div class="col check">
                  <n-checkbox
                      size="small"
                      :checked="debugExecDatasetSelectedIds.includes(row.id)"
                      @update:checked="(v) => toggleDebugExecDatasetRow(row.id, v)"
                  />
                </div>
                <div class="col idx">{{ idx + 1 }}</div>
                <div class="col name">{{ row.name }}</div>
              </div>
            </div>
          </div>
          <div class="exec-config-dataset-footer">
            <div class="exec-config-dataset-footer-inner">
              <n-space :size="8">
                <n-button
                    size="tiny"
                    quaternary
                    :disabled="debugExecDatasetBatchDisabled"
                    @click="selectAllDebugExecDatasets"
                >
                  全选
                </n-button>
                <n-button
                    size="tiny"
                    quaternary
                    :disabled="debugExecDatasetBatchDisabled"
                    @click="clearDebugExecDatasetSelection"
                >
                  取消全选
                </n-button>
              </n-space>
              <div class="exec-config-dataset-footer-count">
                已选 {{ debugExecDatasetSelectedCount }} 项
                <span v-if="execConfigMode === 'debug'" class="exec-config-dataset-mode-tip">(调试模式仅可选 1 条)</span>
              </div>
            </div>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>

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
 *   - ensureQuoteStepsLoaded: 仅 debug，打开前 await 加载 quoteStepsMap
 *   - buildDebugExecutePayload(step_exec_config_map, datasetPart): 调试专用请求体
 *
 * defineExpose: openRun(ctx), openDebug(ctx)
 */
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NEmpty,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
} from 'naive-ui'
import api from '@/api'

const runLoading = defineModel('runLoading', { type: Boolean, default: false })
const debugLoading = defineModel('debugLoading', { type: Boolean, default: false })

/** 打开弹窗时由 index.vue 传入的上下文，见文件头注释 */
const execCtx = ref(null)

const showModel = ref(false)
const execConfigMode = ref('debug')
const execConfigCollapseExpanded = ref(['env'])
const debugExecDataSourceEnabled = ref(false)
const debugExecDatasetRows = ref([])
const debugExecDatasetSelectedIds = ref([])
const debugExecDatasetLoading = ref(false)
const debugEnvMode = ref('single')
const debugGlobalEnvId = ref(null)
const debugSelectedProjectId = ref(null)
const debugEnvConfigDict = ref({})

const envLoading = ref(false)
const debugEnvOptions = ref([])
const debugEnvIdToName = ref(new Map())
const debugRows = ref({ apiRows: [], dbRows: [], fileRows: [] })

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
 * HTTP/TCP → apiRows；数据库多操作 → dbRows；文件类 → fileRows
 */
const collectDebugRows = (sourceSteps, quoteStepsMap) => {
  const apiRows = []
  const dbRows = []
  const fileRows = []

  const getBackendKeyFromStep = (step) => {
    const sid = step?.original?.id
    if (sid != null) return String(sid)
    const n = step?.name || step?.original?.step_name || ''
    return `@@${String(n).trim() || '未命名步骤'}`
  }

  const addToGroup = (map, groupKey, rowFactory, target) => {
    if (!map.has(groupKey)) map.set(groupKey, rowFactory())
    const row = map.get(groupKey)
    row.targets = row.targets || []
    const tkey = `${target.backend_key}#${target.local_step_id}#${target.op_index ?? ''}`
    if (!row._targetKeySet) row._targetKeySet = new Set()
    if (!row._targetKeySet.has(tkey)) {
      row._targetKeySet.add(tkey)
      row.targets.push(target)
    }
    return row
  }

  const apiGroup = new Map()
  const dbGroup = new Map()
  const fileGroup = new Map()
  const apiConfigNameSetByProject = new Map()
  const dbConfigNameSetByProject = new Map()
  const dbNameSetByProject = new Map()
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
          { local_step_id: step.id, backend_key },
      )
    } else if (step.type === 'database') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const ops = cfg.database_operates ?? orig.database_operates
      const list = Array.isArray(ops) ? ops : []
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
              env_id: null,
              targets: [],
            }),
            { local_step_id: step.id, backend_key, op_index: idx },
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
    fileRows: strip([...fileGroup.values()]),
  }
}

const debugApps = computed(() => {
  const byProject = new Map()
  const addCount = (pid, incApi = 0, incDb = 0) => {
    const k = String(pid)
    if (!byProject.has(k)) byProject.set(k, { project_id: pid, api: 0, db: 0 })
    const item = byProject.get(k)
    item.api += incApi
    item.db += incDb
  }
  debugRows.value.apiRows.forEach((r) => addCount(r.project_id, 1, 0))
  debugRows.value.dbRows.forEach((r) => addCount(r.project_id, 0, 1))
  debugRows.value.fileRows.forEach((r) => addCount(r.project_id, 1, 0))

  const list = Array.from(byProject.values()).map((x) => ({
    project_id: x.project_id,
    label: projectLabelMap.value.get(String(x.project_id)) || `应用${String(x.project_id)}`,
    apiCount: x.api,
    dbCount: x.db,
    totalCount: x.api + x.db,
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
  debugGlobalEnvId.value = null
  debugSelectedProjectId.value = null
  debugEnvConfigDict.value = {}
}

const loadDebugEnvEnums = async () => {
  envLoading.value = true
  try {
    const res = await api.getEnvList({ page: 1, page_size: 9999, state: 0 })
    const list = Array.isArray(res?.data) ? res.data : []
    debugEnvOptions.value = list
        .map((x) => ({ label: x.env_name, value: x.env_id }))
        .filter((x) => x.value != null)
    const m = new Map()
    list.forEach((x) => {
      if (x?.env_id != null) m.set(String(x.env_id), x.env_name)
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
  const envId = getEffectiveEnvIdForRow(row)
  if (envId == null) return {}
  const p = dict?.[row.project_id] || dict?.[String(row.project_id)] || {}
  const e = p?.[envId] || p?.[String(envId)] || {}
  return e?.[configType] || {}
}

const getDbDatabaseDisplay = (row) => {
  const envId = getEffectiveEnvIdForRow(row)
  if (envId == null) return ''
  const bucket = getBucket({ ...row, env_id: envId }, 'database')
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

const fetchDebugExecDatasetNames = async () => {
  const caseId = execCtx.value?.caseId
  if (!caseId) {
    debugExecDatasetRows.value = []
    window.$message?.warning?.('缺少用例 ID，无法加载数据集名称')
    return
  }
  debugExecDatasetLoading.value = true
  try {
    const fd = new FormData()
    fd.append('case_id', String(caseId))
    const res = await api.queryDatasetNames(fd)
    const names = Array.isArray(res?.data) ? res.data : []
    debugExecDatasetRows.value = names.map((name) => ({ id: String(name), name: String(name) }))
    const nameSet = new Set(names.map(String))
    debugExecDatasetSelectedIds.value = debugExecDatasetSelectedIds.value.filter((id) => nameSet.has(String(id)))
  } catch (e) {
    debugExecDatasetRows.value = []
    console.error('queryDatasetNames failed', e)
  } finally {
    debugExecDatasetLoading.value = false
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

const validateExecDatasetSelection = () => {
  if (!debugExecDataSourceEnabled.value) return true
  if (debugExecDatasetLoading.value) {
    window.$message?.warning?.('数据集列表加载中，请稍候')
    return false
  }
  if (!debugExecDatasetRows.value.length) {
    window.$message?.warning?.('当前用例暂无可用数据集，请先上传数据源或关闭「请选择数据源」')
    return false
  }
  const n = debugExecDatasetSelectedIds.value.length
  if (execConfigMode.value === 'debug') {
    if (n !== 1) {
      window.$message?.warning?.('调试模式下必须且仅能选择一个数据集')
      return false
    }
  } else if (n < 1) {
    window.$message?.warning?.('请至少勾选一个数据集，或关闭「请选择数据源」')
    return false
  }
  return true
}

const debugExecDataSourceRailStyle = ({ focused, checked }) => {
  const style = {}
  if (checked) {
    style.background = '#F4511E'
    if (focused) style.boxShadow = '0 0 0 2px #d0305040'
  } else {
    style.background = '#2080f0'
    if (focused) style.boxShadow = '0 0 0 2px #2080f040'
  }
  return style
}

watch(debugExecDataSourceEnabled, (on) => {
  if (!on) {
    debugExecDatasetSelectedIds.value = []
    debugExecDatasetRows.value = []
    execConfigCollapseExpanded.value = execConfigCollapseExpanded.value.filter((n) => n !== 'dataset')
    return
  }
  if (!execConfigCollapseExpanded.value.includes('dataset')) {
    execConfigCollapseExpanded.value = [...execConfigCollapseExpanded.value, 'dataset']
  }
  fetchDebugExecDatasetNames()
})

watch(() => debugGlobalEnvId.value, (envId) => {
  const apply = (rows) => {
    rows.forEach((r) => { r.env_id = envId ?? null })
  }
  apply(debugRows.value.apiRows || [])
  apply(debugRows.value.dbRows || [])
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
    const bucket = getBucket({ ...row, env_id: envId }, 'database')
    const info = bucket?.[cfgName]
    const addr = getRowAddrPreview(row, 'database')
    if (!addr || !String(addr).trim()) {
      push('db', row, `${String(cfgName).trim()}(IP/端口未获取)`)
      return
    }
    const dbName = info?.database_name ?? row.database_name
    if (!dbName || !String(dbName).trim()) {
      push('db', row, `${String(cfgName).trim()}(数据库名未获取)`)
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
    const bucket = getBucket({ ...r, env_id: envId }, 'database')
    const cfgNm = r.config_name
    const info = cfgNm ? bucket?.[cfgNm] : null
    const resolvedDb = info?.database_name ?? r.database_name
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      const cfg = step.config || {}
      const ops = Array.isArray(cfg.database_operates) ? cfg.database_operates : []
      const idx = t.op_index
      if (idx == null || !ops[idx]) return
      ops[idx].project_id = r.project_id ?? ops[idx].project_id
      ops[idx].config_name = r.config_name ?? ops[idx].config_name
      ops[idx].database_name = resolvedDb ?? ops[idx].database_name
    })
  })
}

/** 根据弹窗表格与环境配置字典，生成后端 steps_execute_config 对象 */
const buildStepExecConfigMap = (env_name) => {
  const map = {}
  const prefill = (rows, mode) => {
    rows.forEach((r) => {
      const targets = Array.isArray(r.targets) ? r.targets : []
      targets.forEach((t) => {
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
  prefill(debugRows.value.fileRows || [], 'file')

  debugRows.value.apiRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'api')
    const name = r.request_config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
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
    const bucket = getBucket({ ...r, env_id: envId }, 'database')
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const opIdx = t.op_index
      if (opIdx == null || opIdx < 0) return
      map[`${String(t.backend_key)}_@@${opIdx}`] = {
        env_name,
        config_type: 'database',
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
  const env_name = debugEnvIdToName.value.get(String(debugGlobalEnvId.value)) || null
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
    const payload = {
      case_id: cid,
      initial_variables: [],
      ...(configMap != null ? { steps_execute_config: configMap } : {}),
      ...getDatasetPayloadPart(),
    }
    const res = await api.executeStepTree(payload)
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      window.$message?.success?.(res?.message || '执行成功')
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

const doDebug = async (env_name, step_exec_config_map = null) => {
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

/** 父组件 index.vue：execConfigModalRef.value?.openRun / openDebug */
defineExpose({
  openDebug,
  openRun,
})
</script>

<style scoped>
.exec-config-toolbar-row {
  margin-bottom: 12px;
}

.exec-config-toolbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.exec-config-toolbar-inner :deep(.n-switch) {
  flex-shrink: 0;
}

.exec-config-collapse :deep(.n-collapse-item) {
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--n-color);
}

.exec-config-collapse :deep(.n-collapse-item + .n-collapse-item) {
  margin-top: 12px;
}

.exec-config-collapse :deep(.n-collapse-item__header) {
  display: flex;
  align-items: center;
  padding: 10px 12px !important;
  font-size: 14px;
  font-weight: 600;
  min-height: 40px;
  box-sizing: border-box;
}

.exec-config-collapse :deep(.n-collapse-item__header-main) {
  display: flex;
  align-items: center;
  line-height: 1.4;
}

.exec-config-collapse :deep(.n-collapse-item__content-inner) {
  padding: 0 12px 12px;
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
  background: var(--n-color);
  --exec-config-dataset-visible-rows: 5;
  --exec-config-dataset-row-height: 51px;
}

.exec-config-dataset-header {
  display: grid;
  grid-template-columns: 44px 72px 1fr;
  gap: 0;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-2);
  background: var(--n-color-embedded);
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
  scrollbar-gutter: stable;
}

.exec-config-dataset-row {
  display: grid;
  grid-template-columns: 44px 72px 1fr;
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid var(--n-border-color);
}

.exec-config-dataset-row:last-child {
  border-bottom: none;
}

.exec-config-dataset-footer {
  flex-shrink: 0;
  margin-top: 10px;
  padding-top: 10px;
  font-size: 12px;
  color: #999;
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
  font-size: 12px;
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
  background: var(--n-color-hover);
}

.exec-config-app-item.is-active {
  border-color: #F45E11;
  background: color-mix(in srgb, var(--n-primary-color) 10%, var(--n-color) 90%);
}

.exec-config-app-name {
  font-size: 13px;
  font-weight: 600;
}

.exec-config-app-count {
  color: #999;
  margin-top: 4px;
  font-size: 12px;
}

.exec-config-empty {
  color: #999;
  padding: 16px 12px;
  font-size: 12px;
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
}

.exec-config-global-env-label {
  font-size: 14px;
  font-weight: 500;
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
  font-size: 16px;
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
  scrollbar-gutter: stable;
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
  background: var(--n-color-embedded);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.exec-config-table-row {
  background: var(--n-color);
  border-top: 1px solid var(--n-border-color);
}

.exec-config-table-row:hover {
  background: var(--n-color-hover);
}

.exec-config-mode {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
