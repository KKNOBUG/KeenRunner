<template>
  <n-card :bordered="false" style="width: 100%;" :class="['http-card', { 'is-collapsed': mainCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div class="panel-title">Request</div>
        <div class="card-header-actions">
          <n-space align="center" :size="8">
            <n-tooltip trigger="hover">
              <template #trigger>
                <span class="db-stop-label">查到即止</span>
              </template>
              首条查询若返回至少一行数据，则终止本步骤内后续 SQL，不再执行
            </n-tooltip>
            <n-switch v-model:value="state.form.database_searched" :disabled="props.readonly" size="small"/>
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
      <n-form :model="state.form" label-placement="left" label-width="88px">
        <n-form-item label="步骤名称" path="step_name" required>
          <n-input
              v-model:value="state.form.step_name"
              placeholder="请输入步骤名称"
              clearable
              :disabled="props.readonly"
          />
        </n-form-item>
        <n-form-item label="步骤描述" path="step_desc">
          <n-input
              type="textarea"
              v-model:value="state.form.step_desc"
              placeholder="请输入步骤描述"
              clearable
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
            <div v-for="(item, key) in state.form.database_operates" :key="key" class="db-op-card-wrap">
              <n-card
                  size="small"
                  hoverable
                  :class="{ 'is-item-collapsed': opCollapseState[key] }"
              >
                <template #header>
                  <div class="extract-validator-card-header db-op-header">
                    <div class="db-op-title-row">
                      <template v-if="editingDatabaseOpKey === String(key) && !props.readonly">
                        <n-input
                            v-model:value="item.name"
                            size="small"
                            class="db-op-title-input"
                            :placeholder="databaseOpDefaultTitle(key)"
                            clearable
                            @blur="endEditDatabaseOpTitle"
                            @keydown.enter.prevent="endEditDatabaseOpTitle"
                        />
                      </template>
                      <template v-else>
                        <span class="db-op-title-text">{{ databaseOpDisplayTitle(item, key) }}</span>
                        <n-tooltip v-if="!props.readonly" trigger="hover">
                          <template #trigger>
                            <n-button text size="tiny" class="db-op-title-edit" @click="startEditDatabaseOpTitle(key)">
                              <template #icon>
                                <TheIcon icon="material-symbols:edit-outline" :size="18"/>
                              </template>
                            </n-button>
                          </template>
                          编辑显示名称
                        </n-tooltip>
                      </template>
                    </div>
                    <n-space>
                      <n-button text @click="toggleOpCollapse(key)" size="small">
                        <template #icon>
                          <TheIcon
                              :icon="opCollapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                              :size="18"
                          />
                        </template>
                      </n-button>
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
                <div v-show="!opCollapseState[key]">
                  <n-form :model="item" label-width="96px" label-placement="left">
                    <div class="db-op-field-rows">
                      <!-- 第一行：所属应用 30% / 配置名称 40% / 数据库名 30% -->
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
                        <n-form-item label="数据库名" required class="db-op-fi-fill">
                          <n-select
                              v-model:value="item.database_name"
                              :options="dbNameOptionsForRow(item)"
                              placeholder="选择或输入库名（支持 ${变量}）"
                              clearable
                              filterable
                              tag
                              :disabled="props.readonly"
                          />
                        </n-form-item>
                      </div>
                      <!-- 第二行：存储变量 30%、请求描述 70% -->
                      <div class="db-op-field-row db-op-field-row--var-desc">
                        <n-form-item label="存储变量" required class="db-op-fi-fill">
                          <n-input v-model:value="item.variable_name" placeholder="写入变量池的变量名" clearable :disabled="props.readonly"/>
                        </n-form-item>
                        <n-form-item label="请求描述" class="db-op-fi-fill">
                          <n-input v-model:value="item.desc" placeholder="可选，说明本操作用途" clearable :disabled="props.readonly"/>
                        </n-form-item>
                      </div>
                      <!-- 第三行：SQL语句 -->
                      <div class="db-op-field-row db-op-field-row--full">
                        <n-form-item label="SQL语句" required class="db-op-fi-fill">
                          <n-input
                              v-model:value="item.expr"
                              type="textarea"
                              placeholder="支持表名/字段中使用 ${变量名}"
                              :autosize="{ minRows: 4, maxRows: 18 }"
                              :disabled="props.readonly"
                          />
                        </n-form-item>
                      </div>
                    </div>
                  </n-form>
                </div>
              </n-card>
            </div>
            <n-button type="primary" @click="addOp" block dashed :disabled="props.readonly">添加数据库操作</n-button>
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
              mode="database"
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
              mode="database"
              :readonly="props.readonly"
              :source-options="storageVariableSelectOptions"
          />
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
import {computed, reactive, ref, watch} from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCollapseTransition,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadio,
  NRadioGroup,
  NSpace,
  NSwitch,
  NSelect,
  NTabPane,
  NTabs,
  NTooltip
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import api from '@/api'
import {
  ASSERT_MODE_DATABASE,
  buildAssertListFromDict,
  buildExtractListFromDict,
  countDictKeys,
  EXTRACT_MODE_DATABASE,
  hydrateAssertDictFromBackend,
  hydrateExtractDictFromBackend,
  normalizeBackendList,
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
/** 正在编辑卡片标题（item.name）的数据库操作项 key（字符串） */
const editingDatabaseOpKey = ref('')
const toggleMainCardCollapsed = () => {
  mainCardCollapsed.value = !mainCardCollapsed.value
}

const databaseOpDefaultTitle = (key) => {
  const i = opKeys.value.indexOf(Number(key))
  const n = i >= 0 ? i + 1 : Number(key) + 1
  return `数据库请求 ${n}`
}

/** 生成未与当前各条「操作名称」重复的名称（用于新增 / 复制） */
const nextUniqueDatabaseOpName = () => {
  const used = new Set()
  for (const k of opKeys.value) {
    const t = String(state.form.database_operates[k]?.name ?? '').trim()
    if (t) used.add(t)
  }
  let n = 1
  let candidate = `数据库请求 ${n}`
  while (used.has(candidate)) {
    n += 1
    candidate = `数据库请求 ${n}`
  }
  return candidate
}

const databaseOpDisplayTitle = (item, key) => {
  const n = String(item?.name ?? '').trim()
  return n || databaseOpDefaultTitle(key)
}

const startEditDatabaseOpTitle = (key) => {
  if (props.readonly) return
  editingDatabaseOpKey.value = String(key)
}

const endEditDatabaseOpTitle = () => {
  editingDatabaseOpKey.value = ''
}

const emptyOp = () => ({
  name: '',
  desc: '',
  project_id: null,
  project_name: '',
  config_name: '',
  database_name: '',
  expr: '',
  variable_name: ''
})

const state = reactive({
  form: {
    step_name: '',
    step_desc: '',
    database_searched: false,
    database_operates: {},
    extract_variables: {},
    assert_validators: {}
  }
})

const opCollapseState = reactive({})
const configCache = reactive({})
/** project_id -> 去重后的配置名称列表（与 getEnvConfigNameList config_type=database 一致） */
const configNameListByProject = reactive({})

const opKeys = computed(() => Object.keys(state.form.database_operates || {}).map((k) => parseInt(k, 10)).filter((n) => !isNaN(n)).sort((a, b) => a - b))

/** 「请求」里各条 SQL 的存储变量名 variable_name（与后端响应列表项匹配） */
const storageVariableSelectOptions = computed(() => {
  const seen = new Set()
  const opts = []
  for (const k of opKeys.value) {
    const row = state.form.database_operates[k] || {}
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
    if (opCollapseState[k] === undefined) opCollapseState[k] = false
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
    buildExtractListFromDict(state.form.extract_variables, EXTRACT_MODE_DATABASE)

const buildValidatorsForBackend = () =>
    buildAssertListFromDict(state.form.assert_validators, ASSERT_MODE_DATABASE)

const buildConfigFromState = () => {
  const list = opKeys.value.map((k) => {
    const row = state.form.database_operates[k] || {}
    const pname = String(row.project_name ?? '').trim() || projectNameFromId(row.project_id)
    const rawPid = row.project_id
    const projectId =
        rawPid != null && rawPid !== '' && !Number.isNaN(Number(rawPid)) ? Number(rawPid) : null
    return {
      name: String(row.name ?? '').trim(),
      desc: row.desc ?? '',
      project_id: projectId,
      project_name: pname,
      config_name: row.config_name ?? '',
      database_name: row.database_name ?? '',
      expr: row.expr ?? '',
      variable_name: row.variable_name ?? ''
    }
  })
  const ex = buildExtractForBackend()
  const as = buildValidatorsForBackend()
  return {
    step_name: state.form.step_name,
    step_desc: state.form.step_desc,
    database_searched: !!state.form.database_searched,
    database_operates: list,
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
      api.getEnvConfigNameList({ project_id: pid, config_type: 'database' }),
      api.searchEnvConfig({
        project_id: pid,
        config_type: 'database',
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
    console.error('加载数据库配置失败', e)
    configNameListByProject[pid] = []
    configCache[pid] = []
    return []
  }
}

const configOptionsForRow = (item) => {
  const pid = item?.project_id
  const fromList = configNameListByProject[pid]
  if (Array.isArray(fromList) && fromList.length) {
    return fromList.map((name) => ({ label: name, value: name }))
  }
  const rows = configCache[pid] || []
  const names = [...new Set(rows.map((r) => r.config_name).filter(Boolean))]
  return names.map((label) => ({ label, value: label }))
}

const dbNameOptionsForRow = (item) => {
  const pid = item?.project_id
  const rows = (configCache[pid] || []).filter((r) => !item?.config_name || r.config_name === item.config_name)
  const names = [...new Set(rows.map((r) => r.database_name).filter(Boolean))]
  return names.map((label) => ({label, value: label}))
}

const onProjectChange = async (item) => {
  item.project_name = projectNameFromId(item.project_id) || ''
  item.config_name = ''
  item.database_name = ''
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

const initExtractAndAssert = (cfg, original) => {
  state.form.extract_variables = hydrateExtractDictFromBackend(
      normalizeBackendList(cfg.extract_variables ?? original.extract_variables),
      EXTRACT_MODE_DATABASE
  )
  state.form.assert_validators = hydrateAssertDictFromBackend(
      normalizeBackendList(cfg.assert_validators ?? original.assert_validators),
      ASSERT_MODE_DATABASE
  )
}

const initFromProps = () => {
  const cfg = props.config || {}
  const original = props.step?.original || {}

  state.form.step_name = cfg.step_name ?? original.step_name ?? ''
  state.form.step_desc = cfg.step_desc ?? original.step_desc ?? ''
  state.form.database_searched = !!(cfg.database_searched ?? original.database_searched)

  const src = cfg.database_operates ?? original.database_operates
  const list = !src ? [] : Array.isArray(src) ? src : typeof src === 'object' ? Object.values(src) : []
  const next = {}
  list.forEach((row, index) => {
    next[index] = {
      name: row.name ?? '',
      desc: row.desc ?? '',
      project_id: row.project_id ?? projectIdFromName(row.project_name),
      project_name: String(row.project_name ?? '').trim() || projectNameFromId(row.project_id) || '',
      config_name: row.config_name ?? '',
      database_name: row.database_name ?? '',
      expr: row.expr ?? '',
      variable_name: row.variable_name ?? ''
    }
  })
  state.form.database_operates = next
  Object.keys(opCollapseState).forEach((k) => delete opCollapseState[k])
  editingDatabaseOpKey.value = ''
  ensureCollapseKeys()

  initExtractAndAssert(cfg, original)

  const preload = new Set(
      Object.values(state.form.database_operates).map((r) => r.project_id).filter(Boolean)
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
  editingDatabaseOpKey.value = ''
  const keys = opKeys.value
  const newKey = keys.length ? Math.max(...keys) + 1 : 0
  const row = emptyOp()
  row.name = nextUniqueDatabaseOpName()
  state.form.database_operates[newKey] = row
  opCollapseState[newKey] = false
}

const removeOp = (key) => {
  const k = String(key)
  if (editingDatabaseOpKey.value === k) editingDatabaseOpKey.value = ''
  delete state.form.database_operates[k]
  delete opCollapseState[k]
}

const duplicateOp = (key) => {
  const row = state.form.database_operates[key]
  if (!row) return
  editingDatabaseOpKey.value = ''
  const keys = opKeys.value
  const newKey = keys.length ? Math.max(...keys) + 1 : 0
  state.form.database_operates[newKey] = {
    ...row,
    name: nextUniqueDatabaseOpName()
  }
  opCollapseState[newKey] = false
}

</script>

<style scoped>
.http-card {
  margin: 8px 0;
  border-radius: 12px;
  box-shadow: 0 0 15px rgba(214, 214, 214, 0.2);
  border-left: 3px solid #F4511E
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.2px;
}

.card-header-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
  min-height: 24px;
  padding-right: 220px;
}

.card-header-actions {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
}

.db-stop-label {
  font-size: 13px;
  color: var(--n-text-color-2);
}

.collapse-tiny-btn :deep(.n-button__content) {
  font-size: 12px;
}

.http-card.is-collapsed :deep(.n-card__content) {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
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
  gap: 2px;
  min-width: 0;
  flex: 1;
  font-size: 13px;
  font-weight: 500;
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

.db-op-field-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.db-op-field-row {
  width: 100%;
}

/* 第一行：所属应用 30% / 配置名称 40% / 数据库名 30% */
.db-op-field-row--cols3 {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 4fr) minmax(0, 3fr);
  gap: 12px;
  align-items: start;
}

/* 第二行：存储变量 30%、请求描述 70%（与「所属应用」列宽比例一致） */
.db-op-field-row--var-desc {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 7fr);
  gap: 12px;
  align-items: start;
}

.db-op-field-row--full {
  min-width: 0;
}

.db-op-field-row--cols3 :deep(.n-form-item),
.db-op-field-row--var-desc :deep(.n-form-item),
.db-op-field-row--full :deep(.n-form-item) {
  min-width: 0;
}

.db-op-fi-fill :deep(.n-input),
.db-op-fi-fill :deep(.n-select) {
  width: 100%;
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

.db-op-card-wrap .extract-validator-card-header {
  min-height: 100%;
}

.extract_variables-item,
.validator-item {
  width: 100%;
}

.extract_variables-item :deep(.n-card),
.validator-item :deep(.n-card) {
  border: 1px solid var(--n-border-color);
  background-color: var(--n-color);
}

.extract_variables-item :deep(.n-card-header),
.validator-item :deep(.n-card-header) {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 10px 16px;
  box-sizing: border-box;
  background-color: var(--n-color-embedded);
  border-bottom: 1px solid var(--n-border-color);
}

.extract_variables-item :deep(.n-card-header__main),
.validator-item :deep(.n-card-header__main) {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
}

.extract_variables-item :deep(.n-card.is-item-collapsed .n-card-header),
.validator-item :deep(.n-card.is-item-collapsed .n-card-header) {
  border-bottom: none;
}

.extract_variables-item :deep(.n-card.is-item-collapsed .n-card__content),
.validator-item :deep(.n-card.is-item-collapsed .n-card__content) {
  display: none;
  padding: 0;
}
</style>
