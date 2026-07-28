<template>
  <n-card :bordered="false" style="width: 100%;" :class="['step-editor-card', { 'is-collapsed': mainCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">Request</div>
        <div class="card-header-actions">
          <n-space align="center" :size="8">
            <n-tooltip trigger="hover">
              <template #trigger>
                <span class="db-stop-label">查到即止</span>
              </template>
              首条命令若返回有效结果，则终止本步骤内后续 Redis 命令，不再执行
            </n-tooltip>
            <n-switch v-model:value="state.form.redis_searched" :disabled="props.readonly" size="small"/>
          </n-space>
          <n-button text size="tiny" @click="toggleMainCardCollapsed" class="collapse-tiny-btn">
            <template #icon>
              <TheIcon
                  :icon="mainCardCollapsed ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                  :size="18"
              />
            </template>
            {{ mainCardCollapsed ? '展开' : '收起' }}
          </n-button>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!mainCardCollapsed">
      <n-form class="step-editor-form" :model="state.form" label-placement="left" label-width="80px" size="small">
        <n-form-item label="步骤名称" path="step_name" required>
          <div class="redis-step-name-debug">
            <n-input
                v-model:value="state.form.step_name"
                placeholder="请输入步骤名称"
                clearable
                :disabled="props.readonly"
            />
            <n-button
                v-if="!props.readonly"
                type="primary"
                :loading="debugLoading"
                @click="debugging"
            >
              调试
            </n-button>
          </div>
        </n-form-item>
        <n-form-item label="步骤描述" path="step_desc">
          <n-input
              type="textarea"
              v-model:value="state.form.step_desc"
              placeholder="请输入步骤描述"
              clearable
              :autosize="{ minRows: 1 }"
              :disabled="props.readonly"
          />
        </n-form-item>
      </n-form>

      <n-tabs type="line" animated style="margin-top: 12px;">
        <n-tab-pane name="request" tab="请求">
          <template #tab>
            <n-badge :value="opKeys.length" :max="99" show-zero>
              <span>请求</span>
            </n-badge>
          </template>
          <n-space vertical :size="12" class="extract-validator-list" style="margin-top: 4px;">
            <div v-for="(item, key) in state.form.redis_operates" :key="key" class="db-op-card-wrap">
              <n-card
                  size="small"
                  hoverable
                  :class="{ 'is-item-collapsed': opCollapseState[key] }"
              >
                <template #header>
                  <div class="extract-validator-card-header db-op-header">
                    <div
                        class="db-op-title-row"
                        role="button"
                        tabindex="0"
                        @click="toggleOpCollapse(key)"
                        @keydown.enter.prevent="toggleOpCollapse(key)"
                    >
                      <TheIcon
                          class="panel-collapse-icon"
                          :icon="opCollapseState[key] ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
                          :size="20"
                      />
                      <template v-if="editingRedisOpKey === String(key) && !props.readonly">
                        <n-input
                            v-model:value="item.name"
                            size="small"
                            class="db-op-title-input"
                            :placeholder="redisOpDefaultTitle(key)"
                            clearable
                            @click.stop
                            @blur="endEditRedisOpTitle"
                            @keydown.enter.prevent="endEditRedisOpTitle"
                        />
                      </template>
                      <template v-else>
                        <span class="db-op-title-text">{{ redisOpDisplayTitle(item, key) }}</span>
                        <n-tooltip v-if="!props.readonly" trigger="hover">
                          <template #trigger>
                            <n-button text size="tiny" class="db-op-title-edit" @click.stop="startEditRedisOpTitle(key)">
                              <template #icon>
                                <TheIcon icon="material-symbols:edit-outline" :size="18"/>
                              </template>
                            </n-button>
                          </template>
                          编辑显示名称
                        </n-tooltip>
                      </template>
                    </div>
                    <n-space @click.stop>
                      <n-button text @click="duplicateOp(key)" type="info" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="18"/>
                        </template>
                      </n-button>
                      <n-button text @click="removeOp(key)" type="error" size="small" :disabled="props.readonly">
                        <template #icon>
                          <TheIcon icon="material-symbols:delete-outline" :size="18"/>
                        </template>
                      </n-button>
                    </n-space>
                  </div>
                </template>
                <div v-show="!opCollapseState[key]" class="db-op-body">
                  <n-form class="step-editor-form" :model="item" label-width="80px" label-placement="left" size="small">
                    <div class="db-op-field-rows">
                      <div class="db-op-field-row db-op-field-row--cols3">
                        <n-form-item label="所属应用" required class="db-op-fi-fill">
                          <n-select
                              v-model:value="item.project_id"
                              placeholder="请选择所属应用"
                              :options="props.projectOptions"
                              :loading="props.projectLoading"
                              clearable
                              filterable
                              :disabled="props.readonly"
                              @update:value="() => onProjectChange(item)"
                          />
                        </n-form-item>
                        <n-form-item label="配置名称" required class="db-op-fi-fill">
                          <n-select
                              v-model:value="item.config_name"
                              :options="configOptionsForRow(item)"
                              placeholder="选择或输入配置名称（支持 ${变量}）"
                              clearable
                              filterable
                              tag
                              :disabled="props.readonly"
                              @update:value="() => onConfigNameChange(item)"
                          />
                        </n-form-item>
                        <n-form-item label="存储变量" required class="db-op-fi-fill">
                          <n-input
                              v-model:value="item.variable_name"
                              placeholder="写入变量池的变量名"
                              clearable
                              :disabled="props.readonly"
                          />
                        </n-form-item>
                      </div>
                      <div class="db-op-field-row db-op-field-row--full">
                        <n-form-item label="Redis命令" required class="db-op-fi-fill">
                          <n-input
                              v-model:value="item.expr"
                              type="textarea"
                              placeholder="如 GET mykey、LRANGE mylist 0 -1；负数索引写 -1 勿加空格；支持 ${变量名}"
                              :autosize="{ minRows: 1, maxRows: 18 }"
                              :disabled="props.readonly"
                              class="redis-expr-textarea"
                          />
                        </n-form-item>
                      </div>
                    </div>
                  </n-form>
                </div>
              </n-card>
            </div>
            <n-button type="primary" @click="addOp" block dashed :disabled="props.readonly">添加Redis操作</n-button>
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="extract" tab="提取">
          <template #tab>
            <n-badge :value="extractCount" :max="99" show-zero>
              <span>提取</span>
            </n-badge>
          </template>
          <StepExtractPanel
              v-model="state.form.extract_variables"
              mode="redis"
              :readonly="props.readonly"
              :source-options="storageVariableSelectOptions"
          />
        </n-tab-pane>

        <n-tab-pane name="assert" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <StepAssertPanel
              v-model="state.form.assert_validators"
              mode="redis"
              :readonly="props.readonly"
              :source-options="storageVariableSelectOptions"
          />
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <n-card
      v-if="response || debugLoading"
      :bordered="false"
      style="width: 100%; margin-top: 8px;"
      :class="['step-editor-card', { 'is-collapsed': responseCardCollapsed }]"
      ref="debugResultRef"
  >
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">Response</div>
        <div class="card-header-actions">
          <n-space align="center" :wrap="false">
            <n-space v-if="response && !debugLoading" align="center" :wrap="false">
              <n-tag :type="responseStatusType" round size="small">Status: {{ responseStatusText }}</n-tag>
              <n-tag :type="durationTagType" round size="small">Time: {{ response.duration }}ms</n-tag>
              <n-tag :type="sizeTagType" round size="small">Size: {{ response.size }}</n-tag>
              <n-tag round>Type: {{ contentType }}</n-tag>
            </n-space>
            <n-tag v-if="debugLoading" type="info" round size="small">
              <template #icon>
                <n-spin size="small"/>
              </template>
              请求中...
            </n-tag>
            <n-button text size="tiny" @click="toggleResponseCardCollapsed" class="collapse-tiny-btn">
              <template #icon>
                <TheIcon
                    :icon="responseCardCollapsed ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                    :size="18"
                />
              </template>
              {{ responseCardCollapsed ? '展开' : '收起' }}
            </n-button>
          </n-space>
        </div>
      </div>
    </template>
    <n-collapse-transition :show="!responseCardCollapsed">
      <div v-if="debugLoading" class="debug-loading">
        <n-spin size="large" description="正在发送请求，请稍候..."/>
      </div>
      <n-tabs v-else type="line" animated>
        <n-tab-pane name="requestInfo" tab="请求信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['requestBasic', 'requestBody']">
              <n-collapse-item title="Basic" name="requestBasic">
                <n-space vertical :size="12">
                  <n-descriptions bordered :column="2" size="small">
                    <n-descriptions-item label="环境">
                      <n-text copyable>{{ requestInfo.request_env_name || '-' }}</n-text>
                    </n-descriptions-item>
                    <n-descriptions-item label="查到即止">
                      <n-tag :type="requestInfo.redis_searched ? 'warning' : 'default'" size="small">
                        {{ requestInfo.redis_searched ? '是' : '否' }}
                      </n-tag>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Redis操作" name="requestBody">
                <monaco-editor
                    v-model:value="formattedRedisOperates"
                    :options="monacoEditorOptions(true)"
                    class="json-editor"
                    style="min-height: 400px; height: auto;"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
        </n-tab-pane>
        <n-tab-pane name="responseInfo" tab="响应信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['responseBody']" arrow-placement="right">
              <n-collapse-item :title="`Body (${contentType})`" name="responseBody">
                <monaco-editor
                    v-model:value="formattedResponse"
                    :options="monacoEditorOptions(true)"
                    class="json-editor"
                    style="min-height: 400px; height: auto;"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
        </n-tab-pane>
        <n-tab-pane name="extract_variables" tab="数据提取">
          <n-data-table
              v-if="response && response.extract_results && response.extract_results.length > 0"
              :columns="extractColumns"
              :data="response.extract_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无数据提取结果"/>
        </n-tab-pane>
        <n-tab-pane name="assert" tab="断言结果">
          <n-data-table
              v-if="response && response.validator_results && response.validator_results.length > 0"
              :columns="validatorColumns"
              :data="response.validator_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无断言结果"/>
        </n-tab-pane>
        <n-tab-pane name="logs" tab="执行日志">
          <n-space vertical :size="12" v-if="response && response.logs && response.logs.length > 0">
            <pre
                v-for="(log, index) in response.logs"
                :key="index"
                class="log-item"
            >{{ log }}</pre>
          </n-space>
          <n-empty v-else description="暂无执行日志"/>
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <n-modal
      v-model:show="debugModalVisible"
      preset="dialog"
      title="选择调试环境"
      positive-text="确定"
      negative-text="取消"
      @positive-click="confirmDebugModal"
  >
    <div style="padding: 8px 0;">
      <div style="margin-bottom: 8px;">执行环境：</div>
      <n-select
          v-model:value="selectedDebugEnvId"
          :options="envOptions"
          :loading="envLoading"
          placeholder="请选择执行环境"
          clearable
          filterable
          style="width: 100%;"
      />
    </div>
  </n-modal>
</template>

<script setup>
import {computed, h, nextTick, reactive, ref, watch} from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NCollapseTransition,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSpace,
  NSpin,
  NSwitch,
  NSelect,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTooltip
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import api from '@/api'
import {
  ASSERT_MODE_REDIS,
  buildAssertListFromDict,
  buildExtractListFromDict,
  countDictKeys,
  EXTRACT_MODE_REDIS,
  hydrateAssertDictFromBackend,
  hydrateExtractDictFromBackend,
  normalizeBackendList,
  validateAssertList,
  validateExtractList,
} from '@/utils/autotestExtractAssert'

const props = defineProps({
  config: {type: Object, default: () => ({})},
  step: {type: Object, default: () => ({})},
  projectOptions: {type: Array, default: () => []},
  projectLoading: {type: Boolean, default: false},
  readonly: {type: Boolean, default: false}
})

const emit = defineEmits(['update:config'])

const mainCardCollapsed = ref(false)
const editingRedisOpKey = ref('')

const toggleMainCardCollapsed = () => {
  mainCardCollapsed.value = !mainCardCollapsed.value
}

const redisOpDefaultTitle = (key) => {
  const i = opKeys.value.indexOf(Number(key))
  const n = i >= 0 ? i + 1 : Number(key) + 1
  return `Redis请求 ${n}`
}

const nextUniqueRedisOpName = () => {
  const used = new Set()
  for (const k of opKeys.value) {
    const t = String(state.form.redis_operates[k]?.name ?? '').trim()
    if (t) used.add(t)
  }
  let n = 1
  let candidate = `Redis请求 ${n}`
  while (used.has(candidate)) {
    n += 1
    candidate = `Redis请求 ${n}`
  }
  return candidate
}

const redisOpDisplayTitle = (item, key) => {
  const n = String(item?.name ?? '').trim()
  return n || redisOpDefaultTitle(key)
}

const startEditRedisOpTitle = (key) => {
  if (props.readonly) return
  editingRedisOpKey.value = String(key)
}

const endEditRedisOpTitle = () => {
  editingRedisOpKey.value = ''
}

const emptyOp = () => ({
  name: '',
  project_id: null,
  project_name: '',
  config_name: '',
  database_name: '0',
  variable_name: '',
  expr: '',
})

const state = reactive({
  form: {
    step_name: '',
    step_desc: '',
    redis_searched: false,
    redis_operates: {},
    extract_variables: {},
    assert_validators: {}
  }
})

const opCollapseState = reactive({})
const configCache = reactive({})
const configNameListByProject = reactive({})

const opKeys = computed(() =>
    Object.keys(state.form.redis_operates || {})
        .map((k) => parseInt(k, 10))
        .filter((n) => !isNaN(n))
        .sort((a, b) => a - b)
)

/** 「请求」里各条 Redis 操作的存储变量名 variable_name */
const storageVariableSelectOptions = computed(() => {
  const seen = new Set()
  const opts = []
  for (const k of opKeys.value) {
    const row = state.form.redis_operates[k] || {}
    const vn = String(row.variable_name || '').trim()
    if (!vn || seen.has(vn)) continue
    seen.add(vn)
    opts.push({ label: vn, value: vn })
  }
  return opts
})

const extractCount = computed(() => countDictKeys(state.form.extract_variables))
const validatorsCount = computed(() => countDictKeys(state.form.assert_validators))

const ensureCollapseKeys = () => {
  opKeys.value.forEach((k) => {
    if (opCollapseState[k] === undefined) opCollapseState[k] = true
  })
}

const projectNameFromId = (id) => {
  if (id == null || id === '') return ''
  const o = props.projectOptions.find((x) => x.value === id)
  return o ? String(o.label ?? '').trim() : ''
}

const projectIdFromName = (name) => {
  const s = String(name ?? '').trim()
  if (!s) return null
  const o = props.projectOptions.find((x) => String(x.label ?? '').trim() === s)
  return o ? o.value : null
}

const buildExtractForBackend = () =>
    buildExtractListFromDict(state.form.extract_variables, EXTRACT_MODE_REDIS)

const buildValidatorsForBackend = () =>
    buildAssertListFromDict(state.form.assert_validators, ASSERT_MODE_REDIS)

const buildConfigFromState = () => {
  const list = opKeys.value.map((k) => {
    const row = state.form.redis_operates[k] || {}
    const pname = String(row.project_name ?? '').trim() || projectNameFromId(row.project_id)
    const rawPid = row.project_id
    const projectId =
        rawPid != null && rawPid !== '' && !Number.isNaN(Number(rawPid)) ? Number(rawPid) : null
    return {
      name: String(row.name ?? '').trim(),
      project_id: projectId,
      project_name: pname,
      config_name: row.config_name ?? '',
      database_name: resolveDatabaseNameForRow(row),
      variable_name: row.variable_name ?? '',
      expr: row.expr ?? '',
    }
  })
  const ex = buildExtractForBackend()
  const as = buildValidatorsForBackend()
  return {
    step_name: state.form.step_name,
    step_desc: state.form.step_desc,
    redis_searched: !!state.form.redis_searched,
    redis_operates: list,
    extract_variables: ex.length ? ex : null,
    assert_validators: as.length ? as : null
  }
}

const loadConfigsForProject = async (projectId, force = false) => {
  const pid = projectId != null ? Number(projectId) : null
  if (!pid) return []
  if (configCache[pid] && !force) return configCache[pid]
  try {
    const [resNames, res] = await Promise.all([
      api.getEnvConfigNameList({project_id: pid, config_type: 'redis'}),
      api.searchEnvConfig({
        project_id: pid,
        config_type: 'redis',
        page: 1,
        page_size: 500,
        state: 0
      })
    ])
    const nameList = Array.isArray(resNames?.data) ? resNames.data : []
    configNameListByProject[pid] = nameList
    const rows = Array.isArray(res?.data) ? res.data : []
    configCache[pid] = rows
    return rows
  } catch (e) {
    console.error('加载Redis配置失败', e)
    configNameListByProject[pid] = []
    configCache[pid] = []
    return []
  }
}

const configOptionsForRow = (item) => {
  const pid = item?.project_id
  const fromList = configNameListByProject[pid]
  if (Array.isArray(fromList) && fromList.length) {
    return fromList.map((name) => ({label: name, value: name}))
  }
  const rows = configCache[pid] || []
  const names = [...new Set(rows.map((r) => r.config_name).filter(Boolean))]
  return names.map((label) => ({label, value: label}))
}

const resolveDatabaseNameForRow = (item) => {
  const pid = item?.project_id
  const configName = item?.config_name
  if (!pid || !configName) return item?.database_name || '0'
  const rows = (configCache[pid] || []).filter((r) => r.config_name === configName)
  const names = [...new Set(rows.map((r) => r.database_name).filter(Boolean))]
  if (names.length === 1) return names[0]
  return item?.database_name || '0'
}

const initExtractAndAssert = (cfg, original) => {
  state.form.extract_variables = hydrateExtractDictFromBackend(
      normalizeBackendList(cfg.extract_variables ?? original.extract_variables),
      EXTRACT_MODE_REDIS
  )
  state.form.assert_validators = hydrateAssertDictFromBackend(
      normalizeBackendList(cfg.assert_validators ?? original.assert_validators),
      ASSERT_MODE_REDIS
  )
}

const initFromProps = () => {
  const cfg = props.config || {}
  const original = props.step?.original || {}

  state.form.step_name = cfg.step_name ?? original.step_name ?? ''
  state.form.step_desc = cfg.step_desc ?? original.step_desc ?? ''
  state.form.redis_searched = !!(cfg.redis_searched ?? original.redis_searched)

  const src = cfg.redis_operates ?? original.redis_operates
  const list = !src ? [] : Array.isArray(src) ? src : typeof src === 'object' ? Object.values(src) : []
  const next = {}
  list.forEach((row, index) => {
    next[index] = {
      name: row.name ?? '',
      project_id: row.project_id ?? projectIdFromName(row.project_name),
      project_name: String(row.project_name ?? '').trim() || projectNameFromId(row.project_id) || '',
      config_name: row.config_name ?? '',
      database_name: row.database_name ?? '0',
      variable_name: row.variable_name ?? '',
      expr: row.expr ?? '',
    }
  })
  state.form.redis_operates = next
  Object.keys(opCollapseState).forEach((k) => delete opCollapseState[k])
  editingRedisOpKey.value = ''
  ensureCollapseKeys()

  initExtractAndAssert(cfg, original)

  const preload = new Set(
      Object.values(state.form.redis_operates).map((r) => r.project_id).filter(Boolean)
  )
  preload.forEach((pid) => loadConfigsForProject(pid))
}

watch(
    () => props.step?.id,
    () => initFromProps(),
    {immediate: true}
)

watch(
    () => state.form,
    () => {
      if (props.readonly) return
      emit('update:config', buildConfigFromState())
    },
    {deep: true}
)

const toggleOpCollapse = (key) => {
  opCollapseState[key] = !opCollapseState[key]
}

const addOp = () => {
  editingRedisOpKey.value = ''
  const keys = opKeys.value
  const newKey = keys.length ? Math.max(...keys) + 1 : 0
  const row = emptyOp()
  row.name = nextUniqueRedisOpName()
  state.form.redis_operates[newKey] = row
  opCollapseState[newKey] = false
}

const removeOp = (key) => {
  const k = String(key)
  if (editingRedisOpKey.value === k) editingRedisOpKey.value = ''
  delete state.form.redis_operates[k]
  delete opCollapseState[k]
}

const duplicateOp = (key) => {
  const row = state.form.redis_operates[key]
  if (!row) return
  editingRedisOpKey.value = ''
  const keys = opKeys.value
  const newKey = keys.length ? Math.max(...keys) + 1 : 0
  state.form.redis_operates[newKey] = {
    ...row,
    name: nextUniqueRedisOpName()
  }
  opCollapseState[newKey] = false
}

const onProjectChange = async (item) => {
  item.project_name = projectNameFromId(item.project_id) || ''
  item.config_name = ''
  item.database_name = '0'
  if (item.project_id) await loadConfigsForProject(item.project_id, true)
}

const onConfigNameChange = async (item) => {
  const pid = item.project_id
  if (!pid) return
  const rows = await loadConfigsForProject(pid)
  const names = [
    ...new Set(
        rows.filter((r) => r.config_name === item.config_name).map((r) => r.database_name).filter(Boolean)
    )
  ]
  if (names.length === 1) {
    item.database_name = names[0]
  }
}

/* =================== Debug =================== */
const response = ref(null)
const debugLoading = ref(false)
const responseCardCollapsed = ref(false)
const debugResultRef = ref(null)
const requestInfo = ref({
  request_env_name: '',
  redis_searched: false,
  redis_operates: []
})

const toggleResponseCardCollapsed = () => { responseCardCollapsed.value = !responseCardCollapsed.value }

const monacoEditorOptions = (readOnly) => {
  const options = {
    theme: 'vs-dark',
    language: 'json',
    fontSize: 14,
    tabSize: 4,
    automaticLayout: true,
    minimap: { enabled: true },
    lineNumbers: 'on',
    renderLineHighlight: 'line',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    folding: true,
    foldingStrategy: 'auto',
    roundedSelection: false,
    cursorStyle: 'line',
  }
  if (readOnly) {
    options.readOnly = true
  }
  return options
}

const contentType = computed(() => 'application/json')

const formattedResponse = computed(() => {
  try {
    return JSON.stringify(response.value?.data, null, 4)
  } catch {
    return response.value?.data ?? ''
  }
})

const formattedRedisOperates = computed(() => {
  try {
    return JSON.stringify(requestInfo.value.redis_operates, null, 4)
  } catch {
    return '[]'
  }
})

const responseStatusText = computed(() => {
  if (!response.value) return '-'
  const data = response.value.data
  if (Array.isArray(data) && data.some((item) => item?.error)) return 'ERROR'
  return response.value.status ?? 'OK'
})

const responseStatusType = computed(() => {
  if (!response.value) return 'default'
  if (responseStatusText.value === 'ERROR') return 'error'
  const validators = response.value.validator_results
  if (Array.isArray(validators) && validators.some((v) => !v.success)) return 'error'
  return 'success'
})

const durationTagType = computed(() => {
  if (!response.value) return 'default'
  return response.value.duration > 1000 ? 'warning' : 'success'
})

const sizeTagType = computed(() => {
  if (!response.value) return 'default'
  const sizeStr = String(response.value.size || '')
  const num = parseFloat(sizeStr)
  if (Number.isFinite(num) && sizeStr.toUpperCase().includes('KB')) {
    return num > 100 ? 'warning' : 'success'
  }
  return num > 102400 ? 'warning' : 'success'
})

const extractColumns = [
  { title: '变量名', key: 'name', width: 120 },
  {
    title: '提取来源',
    key: 'source',
    width: 120,
    render: (row) => row.source || '-'
  },
  {
    title: '提取范围',
    key: 'scope',
    width: 120,
    render: (row) => (row.scope === 'ALL' ? '全部提取' : '部分提取')
  },
  { title: '提取路径', key: 'expr', width: 120, ellipsis: { tooltip: true } },
  {
    title: '提取值',
    key: 'extract_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.extract_value === null || row.extract_value === undefined) return '-'
      const value = typeof row.extract_value === 'object'
          ? JSON.stringify(row.extract_value)
          : String(row.extract_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '提取结果',
    key: 'success',
    width: 120,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error',
      round: true,
      size: 'small'
    }, { default: () => (row.success ? 'pass' : 'fail') })
  },
  {
    title: '错误信息',
    key: 'error',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => row.error || '-'
  }
]

const validatorColumns = [
  { title: '断言名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => row.source || '-'
  },
  { title: '断言路径', key: 'expr', width: 130, ellipsis: { tooltip: true } },
  {
    title: '结果值',
    key: 'actual_value',
    width: 150,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.actual_value === null || row.actual_value === undefined) return '-'
      return String(row.actual_value)
    }
  },
  { title: '断言方式', key: 'operation', width: 100 },
  {
    title: '期望值',
    key: 'expect_value',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => {
      if (row.except_value === null || row.except_value === undefined) return '-'
      return String(row.except_value)
    }
  },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => h(NTag, {
      type: row.success ? 'success' : 'error',
      round: true,
      size: 'small'
    }, { default: () => (row.success ? 'pass' : 'fail') })
  },
  {
    title: '错误信息',
    key: 'error',
    ellipsis: { tooltip: true },
    render: (row) => row.error || '-'
  }
]

const envOptions = ref([])
const envLoading = ref(false)
const selectedDebugEnvId = ref(null)
const debugModalVisible = ref(false)

const loadEnvNames = async () => {
  envLoading.value = true
  try {
    const res = await api.getEnvList()
    const list = res?.data ?? []
    envOptions.value = list.map((row) => ({
      label: row.env_name != null ? String(row.env_name) : String(row.env_id),
      value: row.env_id
    }))
    if (envOptions.value.length > 0 && selectedDebugEnvId.value == null) {
      selectedDebugEnvId.value = envOptions.value[0].value
    }
  } catch (e) {
    console.error('加载环境列表失败', e)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

const validateBeforeDebug = () => {
  if (!String(state.form.step_name ?? '').trim()) {
    window.$message?.warning?.('请填写步骤名称')
    return false
  }
  if (!opKeys.value.length) {
    window.$message?.warning?.('请至少添加一条 Redis 操作')
    return false
  }
  for (const k of opKeys.value) {
    const row = state.form.redis_operates[k] || {}
    if (!row.project_id) {
      window.$message?.warning?.('请选择所属应用')
      return false
    }
    if (!String(row.config_name ?? '').trim()) {
      window.$message?.warning?.('请填写配置名称')
      return false
    }
    if (!String(row.expr ?? '').trim()) {
      window.$message?.warning?.('请填写 Redis 命令')
      return false
    }
    if (!String(row.variable_name ?? '').trim()) {
      window.$message?.warning?.('请填写存储变量')
      return false
    }
  }
  return true
}

const openDebugModal = () => {
  selectedDebugEnvId.value = null
  debugModalVisible.value = true
  loadEnvNames()
}

const confirmDebugModal = () => {
  if (selectedDebugEnvId.value == null || selectedDebugEnvId.value === '') {
    window.$message?.warning?.('请选择执行环境')
    return false
  }
  debugModalVisible.value = false
  doDebugRequest(selectedDebugEnvId.value)
  return true
}

const debugging = () => {
  if (!validateBeforeDebug()) return
  openDebugModal()
}

const doDebugRequest = async (env_id) => {
  const ev = buildExtractForBackend()
  const av = buildValidatorsForBackend()
  const extractCheck = validateExtractList(ev)
  if (!extractCheck.valid) {
    window.$message?.error?.(extractCheck.message)
    return
  }
  const assertCheck = validateAssertList(av)
  if (!assertCheck.valid) {
    window.$message?.error?.(assertCheck.message)
    return
  }

  debugLoading.value = true
  response.value = null
  try {
    const cfg = buildConfigFromState()
    const original = props.step?.original || {}
    const debugPayload = {
      env_id: Number(env_id),
      step_name: state.form.step_name || original.step_name || 'Redis 调试',
      redis_searched: !!cfg.redis_searched,
      redis_operates: cfg.redis_operates || []
    }
    if (ev.length > 0) {
      debugPayload.extract_variables = ev
    }
    if (av.length > 0) {
      debugPayload.assert_validators = av
    }

    const res = await api.redisRequestDebugging(debugPayload)
    if (res.code === '000000') {
      response.value = res.data
      if (res.data.extract_results) {
        response.value.extract_results = res.data.extract_results
      }
      if (res.data.validator_results) {
        response.value.validator_results = res.data.validator_results
      }
      if (res.data.logs) {
        response.value.logs = res.data.logs
      }
      if (res.data.request_info) {
        const reqInfo = res.data.request_info
        requestInfo.value = {
          request_env_name: reqInfo.request_env_name || '',
          redis_searched: !!reqInfo.redis_searched,
          redis_operates: reqInfo.redis_operates || []
        }
      } else {
        requestInfo.value = {
          request_env_name: '',
          redis_searched: !!cfg.redis_searched,
          redis_operates: cfg.redis_operates || []
        }
      }
      window.$message?.success?.('调试成功')
      nextTick(() => {
        debugResultRef.value?.$el?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      })
    } else {
      window.$message?.error?.(`调试失败：${res.message || '未知错误'}`)
    }
  } catch (e) {
    window.$message?.error?.(`调试失败：${e?.message || e}`)
  } finally {
    debugLoading.value = false
  }
}
</script>

<style scoped>
/* 卡片壳 / 标题 / 折叠见 .step-editor-card */

.card-header-row {
  padding-right: 220px;
}

.card-header-actions {
  gap: 12px;
}

.db-stop-label {
  font-size: var(--step-editor-font-size, 13px);
  color: var(--n-text-color-2);
}

.redis-step-name-debug {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.redis-step-name-debug :deep(.n-input) {
  flex: 1;
  min-width: 0;
}

.json-editor :deep(.monaco-editor) {
  min-height: 90px;
  height: auto !important;
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}

.db-op-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 28px;
  line-height: 1.5;
}

.db-op-title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
}

.db-op-title-row .panel-collapse-icon {
  flex-shrink: 0;
  color: var(--n-text-color-3);
}

.db-op-title-text {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-op-title-input {
  max-width: min(100%, 280px);
}

.db-op-title-edit {
  flex-shrink: 0;
}

.db-op-card-wrap {
  width: 100%;
}

.db-op-card-wrap :deep(.n-card) {
  border: 1px solid var(--n-border-color);
  background-color: var(--n-color);
}

.db-op-card-wrap :deep(.n-card-header) {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 10px 16px;
  box-sizing: border-box;
  background-color: var(--n-color-embedded);
  border-bottom: 1px solid var(--n-border-color);
}

.db-op-card-wrap :deep(.n-card-header__main) {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
}

.db-op-card-wrap :deep(.n-card.is-item-collapsed .n-card-header) {
  border-bottom: none;
}

.db-op-card-wrap :deep(.n-card.is-item-collapsed .n-card__content) {
  display: none;
  padding: 0;
}

.db-op-body {
  margin-top: 12px;
}

.db-op-body :deep(.n-form-item) {
  margin-bottom: 0;
}

.db-op-body :deep(.n-form-item-label) {
  padding-bottom: 0;
}

.db-op-field-rows {
  display: flex;
  flex-direction: column;
}

.db-op-field-row {
  width: 100%;
}

.db-op-field-row--cols3 {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 4fr) minmax(0, 3fr);
  gap: 12px;
  align-items: start;
}

/* 第二行：Redis命令 */
.db-op-field-row--full {
  width: 100%;
}

.db-op-field-row--cols3 :deep(.n-form-item),
.db-op-field-row--full :deep(.n-form-item) {
  min-width: 0;
}

.db-op-fi-fill :deep(.n-input),
.db-op-fi-fill :deep(.n-select),
.db-op-fi-fill :deep(.n-input-number) {
  width: 100%;
}

.redis-expr-textarea :deep(textarea) {
  resize: vertical;
  min-height: 34px;
}

.extract-validator-list {
  width: 100%;
}

.extract-validator-list :deep(.n-space-item) {
  width: 100%;
}

.extract-validator-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 28px;
  line-height: 1.5;
  font-size: 13px;
  font-weight: 500;
}
</style>
