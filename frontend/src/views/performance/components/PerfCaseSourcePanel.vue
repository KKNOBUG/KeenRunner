<!--
  PerfCaseSourcePanel — 压测场景来源面板（用例穿梭 + 施压步骤角色标注）

  上区为穿梭式双栏：左栏按条件分页查询「自动化测试-测试用例」，右栏为已选用例，
  中间移动按钮完成添加/移除；两侧均展示 用例类型/用例名称/所属应用/所属标签/所属人员 五列。
  下区把已选用例的步骤树整体拉取为候选步骤，由用户标注压测角色：
  - 准备段(setup)：每个虚拟用户启动时执行一次（登录/造数），不计入压测指标
  - 被测段(target)：持续施压并产出指标，至少标注一个
  - 忽略(skip)/未标注：仅浏览溯源，不会保存下发
  仅 setup/target 步骤会作为自包含快照随任务落库（含请求定义/断言/提取/数据集行）。

  相对地址的 host 由后端执行管线按「施压环境 + APP配置」实时解析补齐，因此调试需要
  父级传入 所属应用/施压环境/APP配置 三要素。
-->
<template>
  <n-space vertical :size="12">
    <n-grid :cols="24" :x-gap="8">
      <!-- 左栏：候选用例查询列表 -->
      <n-gi :span="11">
        <div class="pane-title">
          候选用例（勾选后添加到右侧）
          <n-text depth="3">已选 {{ selectedCases.length }}/{{ CASE_MAX }}</n-text>
        </div>
        <CrudTable
            ref="$caseTable"
            v-model:query-items="queryItems"
            v-model:checked-row-keys="leftCheckedKeys"
            :columns="leftCaseColumns"
            :get-data="fetchCaseList"
            :row-key="'case_id'"
            :scroll-x="620"
            @on-data-change="onCaseDataChange"
        >
          <template #queryBar>
            <QueryBarItem label="用例名称：">
              <n-input
                  v-model:value="queryItems.case_name"
                  clearable
                  placeholder="请输入用例名称"
                  style="width: 150px"
                  @keypress.enter="$caseTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="用例类型：">
              <n-select
                  v-model:value="queryItems.case_type"
                  :options="CASE_TYPE_OPTIONS"
                  clearable
                  placeholder="全部"
                  style="width: 120px"
                  @update:value="$caseTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="所属应用：">
              <n-select
                  v-model:value="queryItems.case_project"
                  :options="projectOptions"
                  clearable
                  filterable
                  placeholder="全部"
                  style="width: 150px"
                  @update:value="$caseTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="所属标签：">
              <n-select
                  v-model:value="queryItems.case_tags"
                  :options="tagOptions"
                  multiple
                  clearable
                  filterable
                  :max-tag-count="1"
                  placeholder="全部"
                  style="width: 160px"
                  @update:value="$caseTable?.handleSearch()"
              />
            </QueryBarItem>
            <QueryBarItem label="所属人员：">
              <n-input
                  v-model:value="queryItems.owner_user"
                  clearable
                  placeholder="账号"
                  style="width: 110px"
                  @keypress.enter="$caseTable?.handleSearch()"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
      </n-gi>

      <!-- 中栏：移动按钮 -->
      <n-gi :span="2">
        <div class="move-col">
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button block size="small" :disabled="!leftCheckedKeys.length" @click="handleAddChecked">&gt;</n-button>
            </template>
            添加勾选用例
          </n-tooltip>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button block size="small" :disabled="!currentPageCases.length" @click="handleAddPage">&gt;&gt;</n-button>
            </template>
            添加本页全部
          </n-tooltip>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button block size="small" :disabled="!rightCheckedKeys.length" @click="handleRemoveChecked">&lt;</n-button>
            </template>
            移除勾选用例
          </n-tooltip>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button block size="small" :disabled="!selectedCases.length" @click="handleClearAll">&lt;&lt;</n-button>
            </template>
            清空已选
          </n-tooltip>
        </div>
      </n-gi>

      <!-- 右栏：已选用例 -->
      <n-gi :span="11">
        <div class="pane-title">
          已选用例（其步骤在下方标注角色）
          <n-text depth="3">{{ selectedCases.length }} 条</n-text>
        </div>
        <div class="selected-pane">
          <n-data-table
              v-model:checked-row-keys="rightCheckedKeys"
              size="small"
              :columns="rightCaseColumns"
              :data="selectedCases"
              :row-key="(row) => row.case_id"
              :scroll-x="620"
              :max-height="360"
          />
          <n-empty v-if="!selectedCases.length" description="尚未选择用例" class="mt-40" />
        </div>
      </n-gi>
    </n-grid>

    <!-- 施压步骤标注 -->
    <n-alert :bordered="false" type="info">
      步骤来自已选用例的完整步骤树。<n-text strong>准备段</n-text>（登录/接口造数）每个虚拟用户启动时执行一次且不计入压测指标；
      <n-text strong>被测段</n-text> 持续施压并按「方法 + 路径」各自成一行统计；未标注或忽略的步骤仅用于浏览、不会保存下发。
      仅 HTTP 请求步骤支持施压（TCP 等类型下一期支持）。
    </n-alert>
    <n-data-table
        size="small"
        :columns="stepColumns"
        :data="stepRows"
        :row-key="(row) => row.step_id"
        :scroll-x="1280"
        :max-height="420"
        :loading="stepLoading"
    />

    <!-- 单步调试结果 -->
    <n-modal v-model:show="debugVisible" preset="card" title="步骤调试结果" style="width: 720px">
      <n-space vertical size="small">
        <n-text>
          {{ debugResult?.success ? '调试通过' : '调试未通过' }}
          · 状态码 {{ debugResult?.status_code ?? '-' }}
          · 耗时 {{ debugResult?.elapsed_ms ?? '-' }}ms
        </n-text>
        <n-text code>{{ debugResult?.request_url }}</n-text>
        <n-text v-if="debugResult?.transport_error" type="error">
          传输错误: {{ debugResult.transport_error }}
        </n-text>
        <n-text v-for="(item, index) in debugResult?.extracts || []" :key="`e${index}`" :type="item.success ? 'default' : 'warning'">
          提取[{{ item.name }}]: {{ item.success ? item.extract_value : `失败 ${item.error || ''}` }}
        </n-text>
        <n-text v-for="(item, index) in debugResult?.assertions || []" :key="`a${index}`" :type="item.success ? 'default' : 'error'">
          断言[{{ item.name }}]: {{ item.success ? '通过' : `失败 ${item.error || ''}` }}
        </n-text>
        <n-divider style="margin: 4px 0" />
        <n-scrollbar style="max-height: 260px">
          <n-text code style="white-space: pre-wrap; word-break: break-all">
            {{ debugResult?.response_body || '（无响应体）' }}
          </n-text>
        </n-scrollbar>
      </n-space>
    </n-modal>
  </n-space>
</template>

<script setup>
import { computed, h, nextTick, onMounted, ref, watch } from 'vue'
import {
  NAlert, NButton, NDataTable, NDivider, NEmpty, NGi, NGrid, NInput, NModal,
  NSelect, NSpace, NScrollbar, NTag, NText, NTooltip,
} from 'naive-ui'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from '@/api'

defineOptions({ name: 'PerfCaseSourcePanel' })

const props = defineProps({
  /** 所属应用下拉选项（复用父组件已加载的列表） */
  projectOptions: { type: Array, default: () => [] },
  /** 任务所属应用（相对地址调试需要） */
  perfProject: { type: Number, default: null },
  /** 施压环境名称（相对地址调试需要） */
  envName: { type: String, default: null },
  /** 施压目标 APP 配置名称（相对地址调试需要） */
  envConfigName: { type: String, default: null },
  /** 已选用例快照数组（v-model:quote-cases，落库口径） */
  quoteCases: { type: Array, default: () => [] },
  /** 已标注的施压步骤（v-model:execute-steps，仅 setup/target） */
  executeSteps: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:quoteCases', 'update:executeSteps'])

/** 与后端 PERF_QUOTE_CASES_MAX/PERF_EXECUTE_STEPS_MAX 对齐，避免提交才被拒 */
const CASE_MAX = 10
const STEP_MAX = 20
const STEP_TYPE_HTTP = 'HTTP请求'
const CASE_TYPE_OPTIONS = [
  { label: '公共脚本', value: '公共脚本' },
  { label: '公共接口', value: '公共接口' },
  { label: '用户脚本', value: '用户脚本' },
]
/** 压测角色选项（与后端 enums/PerfStepRole 取值一致） */
const ROLE_OPTIONS = [
  { label: '准备段（setup）', value: 'setup' },
  { label: '被测段（target）', value: 'target' },
  { label: '忽略（skip）', value: 'skip' },
]
const ROLE_LABELS = { setup: '准备段', target: '被测段', skip: '忽略' }

/**
 * 规范为用例查询请求体（空值剔除，仅启用状态；页面单选 case_type 映射为后端 case_types）。
 * @param {object} params CrudTable 透出的查询条件与分页参数
 * @returns {object} /autotest/case/search 请求体
 */
function fetchCaseList(params = {}) {
  const { case_type: caseType, ...rest } = params
  const body = { state: 0 }
  if (caseType != null && String(caseType).trim() !== '') body.case_types = [caseType]
  Object.entries(rest).forEach(([key, value]) => {
    if (value === null || value === undefined) return
    if (typeof value === 'string' && value.trim() === '') return
    if (Array.isArray(value) && !value.length) return
    body[key] = typeof value === 'string' ? value.trim() : value
  })
  return api.getApiTestcaseList(body)
}

// ---------- 双栏用例选择 ----------
const $caseTable = ref(null)
const queryItems = ref({ case_name: null, case_type: null, case_project: null, case_tags: [], owner_user: null })
const leftCheckedKeys = ref([])
const rightCheckedKeys = ref([])
/** 已选用例的完整行数据（含五列展示字段与 session_variables） */
const selectedCases = ref([])
/** 左栏当前页行缓存（移动按钮据此取行数据） */
const currentPageCases = ref([])

function onCaseDataChange(rows) {
  currentPageCases.value = rows || []
}

const tagOptions = ref([])
async function loadTags() {
  try {
    const res = await api.getTagList({ page: 1, page_size: 1000, state: 0 })
    tagOptions.value = (res?.data || []).map((tag) => ({ label: tag.tag_name, value: tag.tag_id }))
  } catch (e) {
    tagOptions.value = []
  }
}

/** 所属标签紧凑展示：首枚标签 + 剩余数量（对齐用例列表页口径） */
function renderCaseTags(row) {
  const tags = row.case_tags || []
  if (!tags.length) return '-'
  const children = [h(NTag, { type: 'info', size: 'small', bordered: true }, { default: () => tags[0].tag_name })]
  if (tags.length > 1) children.push(h('span', { style: 'margin-left:4px' }, `+${tags.length - 1}`))
  return h('div', { style: 'display:flex;align-items:center;justify-content:center' }, children)
}

/**
 * 构建用例列表列定义（左右两栏共用同一套展示列）。
 * @param {boolean} withSelection 是否带勾选列
 * @returns {Array} naive 数据表列定义
 */
function buildCaseColumns(withSelection) {
  const columns = withSelection ? [{ type: 'selection', fixed: 'left', width: 44 }] : []
  return [
    ...columns,
    {
      title: '用例类型',
      key: 'case_type',
      width: 96,
      align: 'center',
      render: (row) => h(NTag, { size: 'small', round: true, bordered: true, type: 'info' }, { default: () => row.case_type || '-' }),
    },
    { title: '用例名称', key: 'case_name', minWidth: 160, align: 'center', ellipsis: { tooltip: true } },
    {
      title: '所属应用',
      key: 'case_project',
      width: 130,
      align: 'center',
      ellipsis: { tooltip: true },
      render: (row) => row.case_project?.project_name || '-',
    },
    { title: '所属标签', key: 'case_tags', width: 120, align: 'center', render: renderCaseTags },
    { title: '所属人员', key: 'owner_user', width: 100, align: 'center', ellipsis: { tooltip: true } },
  ]
}
const leftCaseColumns = buildCaseColumns(true)
const rightCaseColumns = buildCaseColumns(true)

/** 追加已选用例（按 case_id 去重、超出上限拦截） */
function appendCases(rows) {
  const exists = new Set(selectedCases.value.map((item) => item.case_id))
  const added = (rows || []).filter((row) => row?.case_id != null && !exists.has(row.case_id))
  if (!added.length) return
  if (selectedCases.value.length + added.length > CASE_MAX) {
    window.$message?.error(`最多选择 ${CASE_MAX} 个用例`)
    return
  }
  selectedCases.value = [...selectedCases.value, ...added]
}

function handleAddChecked() {
  const rows = currentPageCases.value.filter((row) => leftCheckedKeys.value.includes(row.case_id))
  appendCases(rows)
  leftCheckedKeys.value = []
}

function handleAddPage() {
  appendCases(currentPageCases.value)
}

function handleRemoveChecked() {
  const removing = new Set(rightCheckedKeys.value)
  selectedCases.value = selectedCases.value.filter((row) => !removing.has(row.case_id))
  rightCheckedKeys.value = []
}

function handleClearAll() {
  selectedCases.value = []
  rightCheckedKeys.value = []
}

// ---------- 步骤候选（已选用例的步骤树 + 角色标注） ----------
const stepRows = ref([])
const stepLoading = ref(false)
/** 导入接口返回的用例快照（含 session_variables，落库 quote_cases 的最终形态） */
const caseSnapshots = ref([])
/** 编辑模式已保存的角色标注（step_id → role），首次导入时回填一次 */
const savedRoleMap = ref(new Map())
/** 请求序号：用例快速增删时丢弃过期响应，避免乱序覆盖步骤列表 */
let importSeq = 0

/**
 * 按已选用例批量导入步骤定义，并保留既有的角色标注。
 * 步骤列表始终以用例当前定义为准（候选全集），保存时只导出已标注为 setup/target 的步骤。
 */
async function refreshSteps() {
  const seq = ++importSeq
  const caseIds = selectedCases.value.map((row) => row.case_id)
  if (!caseIds.length) {
    stepRows.value = []
    caseSnapshots.value = []
    syncOut()
    return
  }
  stepLoading.value = true
  try {
    const res = await api.importPerfCases({ case_ids: caseIds })
    if (seq !== importSeq) return
    // 当前标注优先(用户最新意图), 编辑模式首次加载则回退到已保存标注
    const roleMap = new Map(stepRows.value.map((row) => [row.step_id, row.role]))
    const steps = (res.data?.steps || []).map((step) => ({
      ...step,
      role: roleMap.get(step.step_id) ?? savedRoleMap.value.get(step.step_id) ?? step.role,
    }))
    savedRoleMap.value = new Map()
    stepRows.value = steps
    caseSnapshots.value = res.data?.cases || []
    syncOut()
  } catch (e) {
    /* 拦截器已提示；保留上次步骤列表便于继续标注 */
  } finally {
    if (seq === importSeq) stepLoading.value = false
  }
}

function onRoleChange(row, role) {
  row.role = role
  syncOut()
}

/** 变量池：按已选用例顺序合并初始变量（同名保留首次出现，与后端 _merge_case_variables 一致） */
const mergedSessionVariables = computed(() => {
  const seen = new Set()
  const items = []
  caseSnapshots.value.forEach((row) => {
    (row.session_variables || []).forEach((item) => {
      if (!item?.key || seen.has(item.key)) return
      seen.add(item.key)
      items.push(item)
    })
  })
  return items
})

/** 用例ID → 用例名称（步骤表来源列展示） */
const caseNameMap = computed(() => {
  const map = {}
  selectedCases.value.forEach((row) => { map[row.case_id] = row.case_name })
  caseSnapshots.value.forEach((row) => { if (!map[row.case_id]) map[row.case_id] = row.case_name })
  return map
})

/** 仅 setup/target 步骤参与落库下发 */
function syncOut() {
  emit('update:quoteCases', caseSnapshots.value.map((row) => ({
    case_id: row.case_id,
    case_code: row.case_code,
    case_name: row.case_name,
    session_variables: row.session_variables || [],
  })))
  emit('update:executeSteps', stepRows.value.filter((row) => row.role === 'setup' || row.role === 'target'))
}

/** 数据集行数（导入结果 dataset_content 为参数化行数组） */
function datasetRowCount(row) {
  return (row.dataset_content || []).length
}

const stepColumns = [
  { title: '序号', key: 'seq', width: 60, align: 'center' },
  { title: '来源用例', key: 'case_id', width: 150, align: 'center', ellipsis: { tooltip: true }, render: (row) => caseNameMap.value[row.case_id] || '-' },
  { title: '步骤名称', key: 'step_name', minWidth: 150, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '步骤类型',
    key: 'step_type',
    width: 100,
    align: 'center',
    render: (row) => h(NTag, {
      size: 'small',
      bordered: true,
      type: row.step_type === STEP_TYPE_HTTP ? 'success' : 'default',
    }, { default: () => row.step_type || '-' }),
  },
  { title: '方法', key: 'request_method', width: 76, align: 'center', render: (row) => row.request_method || '-' },
  { title: '请求地址', key: 'request_url', minWidth: 220, align: 'center', ellipsis: { tooltip: true }, render: (row) => row.request_url || '-' },
  { title: 'APP配置', key: 'request_config_name', width: 130, align: 'center', ellipsis: { tooltip: true }, render: (row) => row.request_config_name || '-' },
  {
    title: '断言/提取',
    key: 'validator_count',
    width: 96,
    align: 'center',
    render: (row) => `${(row.assert_validators || []).length} / ${(row.extract_variables || []).length}`,
  },
  { title: '数据行', key: 'dataset_row_count', width: 76, align: 'center', render: datasetRowCount },
  {
    title: '压测角色',
    key: 'role',
    width: 168,
    align: 'center',
    render(row) {
      return h(NSelect, {
        value: row.role,
        options: ROLE_OPTIONS,
        size: 'small',
        clearable: true,
        placeholder: '未标注',
        disabled: row.step_type !== STEP_TYPE_HTTP,
        'onUpdateValue': (value) => onRoleChange(row, value),
      })
    },
  },
  {
    title: '标注',
    key: 'role_label',
    width: 84,
    align: 'center',
    render: (row) => (row.role ? h(NTag, { size: 'small', round: true, type: row.role === 'target' ? 'error' : 'info' }, { default: () => ROLE_LABELS[row.role] || row.role }) : h(NText, { depth: 3 }, { default: () => '未标注' })),
  },
  {
    title: '操作',
    key: 'actions',
    width: 76,
    align: 'center',
    fixed: 'right',
    render(row) {
      const disabled = row.step_type !== STEP_TYPE_HTTP || !row.request_url
      return h(NButton, {
        size: 'tiny',
        tertiary: true,
        disabled,
        loading: debuggingKey.value === row.step_id,
        onClick: () => handleDebugStep(row),
      }, { default: () => '调试' })
    },
  },
]

// ---------- 单步连通性调试 ----------
const debugVisible = ref(false)
const debugResult = ref(null)
const debuggingKey = ref(null)

/**
 * 以单次真实请求验证步骤定义（相对地址由后端按施压环境补齐 host）。
 * @param {object} row 步骤快照
 */
async function handleDebugStep(row) {
  try {
    debuggingKey.value = row.step_id
    const res = await api.debugPerfStep({
      perf_project: props.perfProject,
      env_name: props.envName,
      env_config_name: props.envConfigName,
      request_url: row.request_url,
      request_port: row.request_port,
      request_config_name: row.request_config_name,
      request_method: row.request_method,
      request_header: row.request_header,
      request_params: row.request_params,
      request_args_type: row.request_args_type,
      request_text: row.request_text,
      request_body: row.request_body,
      assert_validators: row.assert_validators,
      extract_variables: row.extract_variables,
      session_variables: mergedSessionVariables.value,
      dataset_content: row.dataset_content,
    })
    debugResult.value = res.data
    debugVisible.value = true
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    debuggingKey.value = null
  }
}

watch(selectedCases, () => refreshSteps())

/**
 * 所属应用变更时同步左栏筛选条件：候选用例默认只看当前应用，避免查出一堆无关脚本；
 * 需要跨应用引用时用户仍可自行清空该筛选项。
 */
watch(() => props.perfProject, (projectId) => {
  if (!projectId) return
  queryItems.value = { ...queryItems.value, case_project: projectId }
  $caseTable.value?.handleSearch()
})

/**
 * 表单保存前校验：返回错误文案（空串表示通过）。
 * 与后端 PerfTaskCrud.validate_execute_steps 口径对齐，避免提交后才报错。
 * @returns {string} 错误提示文案
 */
function validate() {
  if (!selectedCases.value.length) return '请先在场景来源中选择至少一个测试用例'
  const pressSteps = stepRows.value.filter((row) => row.role === 'setup' || row.role === 'target')
  if (!pressSteps.length) return '请至少标注一个施压步骤（准备段或被测段）'
  if (pressSteps.length > STEP_MAX) return `施压步骤最多 ${STEP_MAX} 个，当前已标注 ${pressSteps.length} 个`
  if (!pressSteps.some((row) => row.role === 'target')) return '请至少标注一个被测段（target）步骤，否则没有接口产出压测指标'
  const missingUrl = pressSteps.filter((row) => !(row.request_url || '').trim()).map((row) => row.step_name)
  if (missingUrl.length) return `以下步骤缺少请求地址：${missingUrl.join('、')}`
  const setupSeq = pressSteps.filter((row) => row.role === 'setup').map((row) => Number(row.seq || 0))
  const targetSeq = pressSteps.filter((row) => row.role === 'target').map((row) => Number(row.seq || 0))
  if (setupSeq.length && Math.min(...targetSeq) < Math.max(...setupSeq)) {
    return '准备段步骤的用例序号必须早于被测段（先造数、后施压）'
  }
  return ''
}

defineExpose({ validate, sessionVariables: mergedSessionVariables })

onMounted(async () => {
  loadTags()
  queryItems.value = { ...queryItems.value, case_project: props.perfProject ?? null }
  // 穿梭式面板必须开场即有候选，不沿用列表页「不默认查询」约定
  await nextTick()
  $caseTable.value?.handleSearch()
  const caseIds = (props.quoteCases || []).map((row) => row.case_id).filter(Boolean)
  if (!caseIds.length) return
  savedRoleMap.value = new Map((props.executeSteps || []).map((row) => [row.step_id, row.role]))
  try {
    // 编辑模式：用例快照仅存 4 个字段，五列展示数据按ID回查补齐
    const res = await api.getApiTestcaseList({
      case_ids: caseIds,
      page: 1,
      page_size: Math.max(10, caseIds.length),
      state: 0,
    })
    const rowMap = new Map((res.data || []).map((row) => [row.case_id, row]))
    selectedCases.value = caseIds.map((id) => rowMap.get(id)).filter(Boolean)
  } catch (e) {
    // 用例已删除时退化为快照展示，至少不阻断已保存施压步骤的查看与调整
    selectedCases.value = (props.quoteCases || []).map((row) => ({ ...row, case_tags: [] }))
    stepRows.value = (props.executeSteps || []).map((row) => ({ ...row }))
    caseSnapshots.value = (props.quoteCases || []).map((row) => ({ ...row }))
  }
})
</script>

<style scoped>
.pane-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
}

.move-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
  height: 100%;
  padding-top: 40px;
}

.selected-pane {
  min-height: 360px;
  padding: 8px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
}
</style>
