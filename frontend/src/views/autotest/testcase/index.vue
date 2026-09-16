<script setup>
import {h, onMounted, ref, computed, watch} from 'vue'
import {useRouter} from 'vue-router'
import {NButton, NDropdown, NForm, NFormItem, NInput, NSelect, NPopover, NList, NListItem, NTag, NTooltip, NModal, NUpload, NUploadDragger, NAlert, NSpace, NPopconfirm} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import ExecConfigModal from '@/views/autotest/steps/components/ExecConfigModal.vue'
import CaseHistoryDrawer from '@/views/autotest/testcase/components/CaseHistoryDrawer.vue'
import { useAutotestSavedCaseRun } from '@/composables/useAutotestSavedCaseRun'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import {apiPermissionKey, formatDateTime, renderIcon} from '@/utils'
import {useCRUD} from '@/composables'
import api from '@/api'
import {useAutotestStore, usePermissionStore, useTagsStore, useUserStore} from '@/store'

defineOptions({name: '测试用例'})

/**
 * 与后端 AutoTestApiCaseSelect 对齐的可查询字段（不含仅 UI 态字段）。
 * 后端类型过滤认 case_types；页面下拉仍用 case_type，提交时映射为 case_types。
 */
const CASE_SEARCH_BODY_KEYS = new Set([
  'case_id', 'case_code', 'case_types', 'case_steps', 'case_state', 'case_last_time', 'case_version',
  'case_name', 'case_tags', 'case_attr', 'case_project', 'session_variables',
  'page', 'page_size', 'order',
  'step_type', 'request_args_type', 'created_user', 'owner_user', 'updated_user', 'state',
])

const $table = ref(null)
/** 查询表单：仅保留后端支持的筛选项；case_type 为 UI 单选，请求前转为 case_types */
const queryItems = ref({
  case_name: null,
  case_attr: null,
  case_type: null,
  case_project: null,
  case_tags: [],
  created_user: null,
  owner_user: null,
  updated_user: null,
})

/**
 * 将 CrudTable 传入的 params 规范为 AutoTestApiCaseSelect 请求体。
 * - 去掉 schema 外字段
 * - 空串/空数组/null 不传
 * - case_type → case_types: [case_type]
 */
function buildCaseSearchBody(params = {}) {
  const raw = {...params}
  const caseType = raw.case_type
  delete raw.case_type
  if (caseType != null && String(caseType).trim() !== '') {
    raw.case_types = [caseType]
  } else {
    delete raw.case_types
  }

  const body = {state: 0}
  for (const [key, value] of Object.entries(raw)) {
    if (!CASE_SEARCH_BODY_KEYS.has(key)) continue
    if (value === null || value === undefined) continue
    if (typeof value === 'string' && value.trim() === '') continue
    if (Array.isArray(value) && value.length === 0) continue
    body[key] = typeof value === 'string' ? value.trim() : value
  }
  if (body.page == null) body.page = 1
  if (body.page_size == null) body.page_size = 10
  return body
}

function fetchCaseList(params = {}) {
  return api.getApiTestcaseList(buildCaseSearchBody(params))
}

const userStore = useUserStore()
const permissionStore = usePermissionStore()
/** 与原头部「新增测试用例」按钮一致：无权限则不展示 QueryBar 中的「新增」 */
const CASE_CREATE_PERM = apiPermissionKey('post', '/autotest/case/create')
const canCreateCase = computed(
    () => userStore.isSuperUser || permissionStore.apis.includes(CASE_CREATE_PERM)
)
const queryBarProps = computed(() => ({
  addReset: true,
  addSearch: true,
  addCreate: canCreateCase.value,
  addDelete: true,
  actionMode: 'split',
  /** 仅测试用例：导出/导入收纳进右侧更多菜单 */
  extraActions: [
    {
      label: '导出报文',
      key: 'exportData',
      icon: renderIcon('material-symbols:download', { size: 16 }),
    },
    {
      label: '导出接口',
      key: 'exportScript',
      icon: renderIcon('material-symbols:download', { size: 16 }),
    },
    {
      label: '导入接口',
      key: 'importScript',
      icon: renderIcon('material-symbols:upload', { size: 16 }),
    },
    {
      label: '脚本生成',
      key: 'generateScript',
      icon: renderIcon('material-symbols:difference', { size: 16 }),
    },
  ],
}))

function onQueryBarAction(key) {
  if (key === 'exportData') handleExport()
  else if (key === 'exportScript') handleExportScript()
  else if (key === 'importScript') handleImportScript()
  else if (key === 'generateScript') handleGenerateScript()
}

const checkedRowKeys = ref([])

/** 与 CrudTable 远程分页同步，用于「序号」列跨页连续编号 */
const listPaginationMeta = ref({ page: 1, page_size: 10 })
function onListPaginationMeta(meta) {
  listPaginationMeta.value = meta
}

async function handleBatchDelete() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要删除的用例')
    return
  }
  await $dialog.confirm({
    title: '提示',
    type: 'warning',
    content: `确定删除选中的 ${ids.length} 条用例吗？`,
    async confirm() {
      await Promise.all(ids.map((case_id) => api.deleteApiTestcaseList({ case_id })))
      window.$message?.success?.('删除成功')
      checkedRowKeys.value = []
      $table.value?.handleSearch?.()
    },
  })
}

/** 拼装不合规用例明细文本 */
function buildInvalidDetail(invalid) {
  return (Array.isArray(invalid) ? invalid : [])
      .map((it) => `${it.case_name}：${it.reason}`)
      .join('；')
}

/** 导出勾选用例的请求头与请求体为 xlsx：统一异步下发，产物在异步中心下载 */
async function handleExport() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要导出的用例')
    return
  }
  try {
    const res = await api.exportTestcasesAsync({ case_ids: ids })
    window.$message?.success?.(res?.message || '导出任务已提交后台执行，请稍后在异步中心查看结果')
  } catch (err) {
    // 基础错误信息已由请求拦截器弹出，此处仅补充不合规明细
    const detail = buildInvalidDetail(err?.error?.data?.invalid)
    if (detail) window.$message?.error?.(`不合规明细：${detail}`, { keepAliveOnHover: true })
  }
}

/** 导出勾选公共接口为模板脚本 xlsx：统一异步下发，产物在异步中心下载；产出文件可直接用于导入脚本 */
async function handleExportScript() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先勾选要导出的公共接口')
    return
  }
  try {
    const res = await api.exportCaseScriptsAsync({ case_ids: ids })
    window.$message?.success?.(res?.message || '导出任务已提交后台执行，请稍后在异步中心查看结果')
  } catch (err) {
    // 基础错误信息已由请求拦截器弹出，此处仅补充不合规明细
    const detail = buildInvalidDetail(err?.error?.data?.invalid)
    if (detail) window.$message?.error?.(`不合规明细：${detail}`, { keepAliveOnHover: true })
  }
}

/** 导入脚本对话框状态；importErrors 为后端同步返回的模板解析不合规行明细([{row, reason}])，展示在对话框内便于修稿后重试；落库结果在异步中心查看 */
const importScriptShow = ref(false)
const importFileList = ref([])
const importLoading = ref(false)
const importErrors = ref([])

function handleImportScript() {
  importFileList.value = []
  importErrors.value = []
  importScriptShow.value = true
}

async function submitImportScript() {
  const rawFile = importFileList.value?.[0]?.file
  if (!rawFile) {
    window.$message?.warning?.('请先选择要导入的模板文件')
    return
  }
  const formData = new FormData()
  formData.append('file', rawFile)
  importLoading.value = true
  importErrors.value = []
  try {
    const res = await api.importCaseScriptsAsync(formData)
    window.$message?.success?.(res?.message || '导入任务已提交后台执行，请稍后在异步中心查看结果')
    // 导入为后台任务：清步骤树缓存并为仍打开的步骤编辑页签标记强制重载（KeepAlive 内存态不会仅靠清缓存失效），任务完成后重进页面可见最新数据
    const autotestStore = useAutotestStore()
    autotestStore.clearAllStepTreeCache()
    for (const tag of tagsStore.tags || []) {
      if (!String(tag.path || '').startsWith('/autotest/steps')) continue
      const { caseId, caseCode } = parseCaseFromPath(tag.path)
      if (caseId || caseCode) autotestStore.markStepEditorFreshLoad(caseId, caseCode)
    }
    importScriptShow.value = false
    $table.value?.handleSearch?.()
  } catch (err) {
    // 基础错误信息已由请求拦截器弹出，此处仅补充不合规行明细
    const invalid = err?.error?.data?.invalid
    if (Array.isArray(invalid) && invalid.length) {
      importErrors.value = invalid
    }
  } finally {
    importLoading.value = false
  }
}

/** 脚本生成：将勾选的公共接口逐个复制生成为独立脚本(异步任务，每个脚本仅含当前接口，不修改源接口) */
const generateScriptShow = ref(false)
const generateLoading = ref(false)
// 表单默认值与新增脚本口径一致：脚本类型默认用户脚本、属性默认正案例；标签用户脚本必选、公共脚本可选
const generateForm = ref({
  case_project: null,
  case_type: '用户脚本',
  case_attr: '正案例',
  case_tags: [],
})
// 脚本类型选项(不含公共接口：公共接口是生成源而非目标类型，与后端 schema 校验一致)
const generateTypeOptions = [
  { label: '用户脚本', value: '用户脚本' },
  { label: '公共脚本', value: '公共脚本' },
]
const generateTagRequired = computed(() => generateForm.value.case_type === '用户脚本')
// 弹窗内已选公共接口数量(入口已保证非空，此处仅作只读展示)
const generateSelectedCount = computed(() => (checkedRowKeys.value || []).length)
// 弹窗内标签二级面板状态(与查询区/步骤编辑面板同构，选中态独立于查询区)
const generateTagPopoverShow = ref(false)
const generateSelectedTagMode = ref(null)
const generateCurrentTagNames = computed(() => {
  if (!generateSelectedTagMode.value) return []
  return tagModeGroups.value[generateSelectedTagMode.value] || []
})

const isGenerateTagSelected = (tagId) => {
  const tags = generateForm.value.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

// 弹窗内勾选/取消标签(支持多选)
const handleGenerateTagSelect = (tagId) => {
  if (!Array.isArray(generateForm.value.case_tags)) {
    generateForm.value.case_tags = []
  }
  const index = generateForm.value.case_tags.indexOf(tagId)
  if (index > -1) {
    generateForm.value.case_tags.splice(index, 1)
  } else {
    generateForm.value.case_tags.push(tagId)
  }
}

// 已选标签名称回显(切换应用会清空已选，用当前过滤后的标签清单解析即可)
const getGenerateSelectedTagNames = () => {
  const tags = generateForm.value.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  const names = tags
      .map((tagId) => tagOptions.value.find((t) => t.tag_id === tagId)?.tag_name)
      .filter((name) => name)
  return names.join(', ')
}

function handleGenerateScript() {
  const ids = [...(checkedRowKeys.value || [])]
  if (!ids.length) {
    window.$message?.warning?.('请先选择要生成脚本的接口')
    return
  }
  generateForm.value = { case_project: null, case_type: '用户脚本', case_attr: '正案例', case_tags: [] }
  generateSelectedTagMode.value = null
  generateScriptShow.value = true
  loadTags(null)
}

// 弹窗内切换所属应用时按应用过滤标签并清空已选；关闭弹窗后的表单重置不重复拉取(打开时已统一全量加载)
watch(() => generateForm.value.case_project, (projectId) => {
  if (!generateScriptShow.value) return
  generateForm.value.case_tags = []
  generateSelectedTagMode.value = null
  loadTags(projectId)
})

async function submitGenerateScript() {
  if (!generateForm.value.case_project) {
    window.$message?.warning?.('请选择所属应用')
    return
  }
  if (!generateForm.value.case_type) {
    window.$message?.warning?.('请选择脚本类型')
    return
  }
  if (!generateForm.value.case_attr) {
    window.$message?.warning?.('请选择用例属性')
    return
  }
  if (generateTagRequired.value && !(generateForm.value.case_tags || []).length) {
    window.$message?.warning?.('请选择所属标签')
    return
  }
  generateLoading.value = true
  try {
    const res = await api.generateCaseScriptsAsync({
      case_ids: [...(checkedRowKeys.value || [])],
      case_project: generateForm.value.case_project,
      case_type: generateForm.value.case_type,
      case_attr: generateForm.value.case_attr,
      case_tags: generateForm.value.case_tags || [],
    })
    window.$message?.success?.(res?.message || '脚本生成任务已提交后台执行，请稍后在异步中心查看结果')
    generateScriptShow.value = false
    // 生成结果为新增用例记录，刷新列表可见
    $table.value?.handleSearch?.()
  } catch (err) {
    // 基础错误信息已由请求拦截器弹出，此处仅补充不合规明细
    const detail = buildInvalidDetail(err?.error?.data?.invalid)
    if (detail) window.$message?.error?.(`不合规明细：${detail}`, { keepAliveOnHover: true })
  } finally {
    generateLoading.value = false
  }
}

const {
  handleDelete,
} = useCRUD({
  name: '用例',
  doCreate: api.createApiTestcaseList,
  doDelete: api.deleteApiTestcaseList,
  doUpdate: api.updateApiTestcaseList,
  refresh: () => $table.value?.handleSearch(),
})

const router = useRouter()
const tagsStore = useTagsStore()

/** 从页签 path 解析 case_id / case_code */
function parseCaseFromPath(path) {
  try {
    const idx = String(path).indexOf('?')
    if (idx === -1) return { caseId: null, caseCode: null }
    const q = new URLSearchParams(String(path).slice(idx + 1))
    return { caseId: q.get('case_id'), caseCode: q.get('case_code') }
  } catch {
    return { caseId: null, caseCode: null }
  }
}

// 执行用例：与步骤编辑页一致，拉取已保存步骤树并打开「脚本执行配置」弹窗
const execConfigModalRef = ref(null)
const runLoading = ref(false)
const runningCaseId = ref(null)
const { runSavedCase } = useAutotestSavedCaseRun(execConfigModalRef, runLoading)

const openRunModal = async (row) => {
  if (!row?.case_id && !row?.case_code) {
    window.$message?.warning?.('缺少用例标识，无法执行')
    return
  }
  runningCaseId.value = row.case_id ?? null
  try {
    await runSavedCase({
      caseId: row.case_id,
      caseCode: row.case_code,
      projectOptions: projectOptions.value,
      executeType: '定时执行',
    })
  } finally {
    runningCaseId.value = null
  }
}

// 执行历史：左侧抽屉按 case_id 查报告列表 → 右侧步骤明细
const historyDrawerVisible = ref(false)
const historyCaseRow = ref(null)
function openHistoryDrawer(row) {
  historyCaseRow.value = row || null
  historyDrawerVisible.value = true
}

function openCaseEdit(row) {
  const query = {
    case_id: row.case_id,
    case_info: JSON.stringify(row),
  }
  if (row.case_code) {
    query.case_code = row.case_code
  }
  const targetPath = (() => {
    const match = (row.case_id != null && row.case_id !== '')
        ? tagsStore.tags.find((t) => {
          if (!t.path.startsWith('/autotest/steps')) return false
          const { caseId } = parseCaseFromPath(t.path)
          return caseId != null && String(caseId) === String(row.case_id)
        })
        : row.case_code
            ? tagsStore.tags.find((t) => {
              if (!t.path.startsWith('/autotest/steps')) return false
              const { caseCode } = parseCaseFromPath(t.path)
              return caseCode != null && String(caseCode) === String(row.case_code)
            })
            : null
    return match ? match.path : null
  })()
  if (targetPath) {
    router.push(targetPath)
  } else {
    router.push({path: '/autotest/steps', query})
  }
}

function hasCaseApiPermission(method, path) {
  return userStore.isSuperUser || permissionStore.apis.includes(apiPermissionKey(method, path))
}

/**
 * 【用例管理「复制」】整用例复制：获取步骤树副本并进入编辑页（数据未保存）
 *
 * 与「复制指定脚本」的区别：
 *   - 本功能：复制用例 + 步骤，创建新用例编辑页，用户保存后生成新用例
 *   - 复制指定脚本：仅复制步骤，插入当前正在编辑的用例步骤树中
 *
 * 实现原理：
 * 1. 调用 copyCaseStepTree(case_id) 获取后端返回的 { case, steps }（与复制指定脚本共用同一接口）
 * 2. 使用 case + steps：case 填充用例表单，steps 作为步骤树
 * 3. 拼接 case_info：合并 case、steps，追加 is_copy: true，case_name 加「(副本)」
 * 4. router.push 将 case_info 以 query 传入编辑页，编辑页据此加载（不请求 DB）
 * 5. 用户编辑后保存时，按「新增」逻辑处理（无 case_id/case_code）
 */
const copyLoading = ref(false)
const handleCopyCase = async (row) => {
  if (!row?.case_id) {
    window.$message?.warning?.('请选择用例')
    return
  }
  copyLoading.value = true
  try {
    const res = await api.copyCaseStepTree({ case_id: row.case_id })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      const { case: caseData, steps } = res?.data || {}
      const caseInfo = {
        ...caseData,
        case_id: null,
        case_code: null,
        case_name: (caseData?.case_name || row.case_name || '') + ' (副本)',
        steps: steps || [],
        is_copy: true
      }
      router.push({
        path: '/autotest/steps',
        query: { case_info: JSON.stringify(caseInfo) }
      })
      window.$message?.success?.('已成功复制用例，请在编辑后保存')
    } else {
      window.$message?.error?.(res?.message || '复制失败')
    }
  } catch (error) {
    console.error('复制用例失败', error)
    window.$message?.error?.(error?.message || error?.data?.message || '复制失败')
  } finally {
    copyLoading.value = false
  }
}

// 项目列表
const projectOptions = ref([])
const projectLoading = ref(false)
// 用例属性选项
const caseAttrOptions = [
  { label: '正案例', value: '正案例' },
  { label: '反案例', value: '反案例' }
]
// 用例类型选项（与后端 AutoTestCaseType 一致）
const caseTypeOptions = [
  { label: '公共脚本', value: '公共脚本' },
  { label: '公共接口', value: '公共接口' },
  { label: '用户脚本', value: '用户脚本' }
]
// 标签相关
const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach(tag => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) {
      groups[mode] = []
    }
    groups[mode].push(tag)
  })
  return groups
})
const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

// 选择标签（支持多选）
const handleTagSelect = (tagId) => {
  if (!Array.isArray(queryItems.value.case_tags)) {
    queryItems.value.case_tags = []
  }
  const index = queryItems.value.case_tags.indexOf(tagId)
  if (index > -1) {
    // 如果已选中，则取消选择
    queryItems.value.case_tags.splice(index, 1)
  } else {
    // 如果未选中，则添加
    queryItems.value.case_tags.push(tagId)
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getProjectList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      projectOptions.value = res.data.map(item => ({
        label: item.project_name,
        value: item.project_id
      }))
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  } finally {
    projectLoading.value = false
  }
}

// 加载标签列表
const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getTagList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      // 如果选择了项目，则过滤该项目的标签；否则显示所有标签
      if (projectId) {
        tagOptions.value = res.data.filter(tag => tag.tag_project === projectId)
      } else {
        tagOptions.value = res.data
      }
      selectedTagMode.value = null
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

// 获取选中的标签名称（用于显示）
const getSelectedTagNames = () => {
  const tags = queryItems.value.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  const names = tags
      .map(tagId => tagOptions.value.find(t => t.tag_id === tagId)?.tag_name)
      .filter(name => name)
  return names.join(', ')
}

// 判断标签是否被选中
const isTagSelected = (tagId) => {
  const tags = queryItems.value.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

// 确保 case_tags 始终是数组
watch(() => queryItems.value.case_tags, (newVal) => {
  if (newVal !== null && newVal !== undefined && !Array.isArray(newVal)) {
    queryItems.value.case_tags = []
  }
}, { immediate: true })

// 监听项目选择变化，重新加载标签
watch(() => queryItems.value.case_project, (newVal) => {
  loadTags(newVal)
})

onMounted(() => {
  // 所属应用、所属标签：进入页面时默认加载，供搜索条件使用
  loadProjects()
  loadTags()
  // 用例列表：不默认查询，由用户点击「搜索」按钮触发
})


// 重置逻辑（在handleAdd中处理）
const customHandleAdd = () => {
  router.push({path: '/autotest/steps'})
}

/** 列表「所属标签」列：仅展示一个标签 + 数量角标，悬停展示全部（避免多标签撑高行高） */
const renderCaseTagsCompact = (row) => {
  const tags = Array.isArray(row.case_tags) ? row.case_tags.filter((t) => t && t.tag_name) : []
  if (!tags.length) return h('span', '')
  const trigger = h(
      'div',
      {
        class: 'case-tags-cell-trigger',
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          maxWidth: '100%',
          minHeight: '22px'
        }
      },
      [
        h(NTag, {type: 'info', size: 'small', bordered: true}, {default: () => tags[0].tag_name}),
        tags.length > 1
            ? h('span', {class: 'case-tags-more'}, `+${tags.length - 1}`)
            : null
      ].filter(Boolean)
  )
  if (tags.length === 1) return trigger
  return h(NTooltip, {placement: 'top', trigger: 'hover', showArrow: true}, {
    trigger: () => trigger,
    default: () =>
        h(
            'div',
            {class: 'case-tags-tooltip-inner'},
            tags.map((tag) =>
                h(NTag, {type: 'info', size: 'small', bordered: true, style: {margin: '2px'}}, {default: () => tag.tag_name})
            )
        )
  })
}

// 使用 computed 使 columns 依赖 runLoading / 分页元数据，点击运行或翻页后表格会重新渲染
const columns = computed(() => {
  const { page, page_size } = listPaginationMeta.value
  const seqBase = (page - 1) * page_size
  return [
    { type: 'selection', fixed: 'left', width: 48 },
    {
      title: '序号',
      key: '__seq',
      width: 50,
      align: 'center',
      fixed: 'left',
      render(_row, rowIndex) {
        return seqBase + rowIndex + 1
      },
    },
    {
      title: '用例类型',
      key: 'case_type',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        let mode = "info"
        let round = true
        let bordered = true
        // 公共脚本 / 公共接口徽章对齐为 warning
        if (row.case_type === '公共脚本' || row.case_type === '公共接口') {
          mode = 'warning'
        }
        return h(
            NTag,
            {type: mode, round: round, bordered: bordered},
            {default: () => (row.case_type)}
        )
      },
    },
    {
      title: '用例名称',
      key: 'case_name',
      width: 300,
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        const name = row.case_name || ''
        if (!hasCaseApiPermission('post', '/autotest/case/update')) {
          return name
        }
        return h(
            'a',
            {
              href: 'javascript:void(0)',
              title: name,
              style: {
                display: 'inline-block',
                maxWidth: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: '#2080f0',
                textDecoration: 'underline',
                cursor: 'pointer',
              },
              onClick: (e) => {
                e.preventDefault()
                openCaseEdit(row)
              },
            },
            name
        )
      },
    },
    {
      title: '用例描述',
      key: 'case_desc',
      width: 300,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '用例属性',
      key: 'case_attr',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        let mode = "success"
        let round = true
        let bordered = true
        if (row.case_attr === '反案例') {
          mode = 'primary'
        }
        return h(
            NTag,
            {type: mode, round: round, bordered: bordered},
            {default: () => (row.case_attr)}
        )
      },
    },

    {
      title: '用例步骤',
      key: 'case_steps',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '用例版本',
      key: 'case_version',
      width: 100,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '所属应用',
      key: 'case_project',
      width: 150,
      align: 'center',
      ellipsis: {tooltip: true},
      render(row) {
        return h('span', row.case_project?.project_name || '')
      },
    },
    {
      title: '所属标签',
      key: 'case_tags',
      width: 150,
      align: 'center',
      render(row) {
        return renderCaseTagsCompact(row)
      },
    },

    {
      title: '最后执行结果',
      key: 'case_state',
      width: 110,
      align: 'center',
      render(row) {
        // case_state: null=未执行过, true=成功, false=失败
        if (row.case_state == null) return h('span', '-')
        return h(NTag, {type: row.case_state ? 'success' : 'error', size: 'small', round: true}, () => (row.case_state ? '成功' : '失败'))
      },
    },

    {
      title: '更新人员',
      key: 'updated_user',
      width: 150,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '更新时间',
      key: 'updated_time',
      width: 180,
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.updated_time))
      },
    },
    {
      title: '所属人员',
      key: 'owner_user',
      width: 150,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '创建人员',
      key: 'created_user',
      width: 150,
      align: 'center',
      ellipsis: {tooltip: true},
    },
    {
      title: '创建时间',
      key: 'created_time',
      width: 180,
      align: 'center',
      render(row) {
        return h('span', formatDateTime(row.created_time))
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      align: 'center',
      fixed: 'right',
      render(row) {
        const dropdownOptions = []
        dropdownOptions.push({
          label: '复制',
          key: 'copy',
          icon: renderIcon('material-symbols:content-copy-outline', {size: 16}),
          disabled: copyLoading.value,
          onClick: () => handleCopyCase(row),
        })
        if (hasCaseApiPermission('post', '/autotest/case/update')) {
          dropdownOptions.push({
            label: '编辑',
            key: 'edit',
            icon: renderIcon('material-symbols:edit-outline', {size: 16}),
            onClick: () => openCaseEdit(row),
          })
        }
        dropdownOptions.push({
          label: '历史',
          key: 'history',
          icon: renderIcon('material-symbols:history', {size: 16}),
          onClick: () => openHistoryDrawer(row),
        })
        // 删除使用 NPopconfirm（对齐用户管理）；需独立按钮作触发器，故不放在「更多」内
        const actions = [
          h(
              NButton,
              {
                size: 'tiny',
                quaternary: true,
                type: 'primary',
                loading: runLoading.value && runningCaseId.value === (row.case_id ?? null),
                disabled: runLoading.value,
                onClick: () => openRunModal(row),
              },
              {
                default: () => '执行',
                icon: renderIcon('material-symbols:play-arrow', {size: 16}),
              }
          ),
        ]
        if (hasCaseApiPermission('delete', '/autotest/case/delete')) {
          actions.push(
              h(
                  NPopconfirm,
                  {
                    onPositiveClick: () => handleDelete({case_id: row.case_id}),
                    onNegativeClick: () => {},
                  },
                  {
                    trigger: () =>
                        h(
                            NButton,
                            {
                              size: 'tiny',
                              quaternary: true,
                              type: 'error',
                            },
                            {
                              default: () => '删除',
                              icon: renderIcon('material-symbols:delete-outline', {size: 16}),
                            }
                        ),
                    default: () => h('div', {}, '确定删除该用例吗?'),
                  }
              )
          )
        }
        actions.push(
            h(
                NDropdown,
                {
                  trigger: 'click',
                  options: dropdownOptions.map((opt) => ({
                    label: opt.label,
                    key: opt.key,
                    icon: opt.icon,
                    disabled: opt.disabled,
                  })),
                  onSelect: (key) => dropdownOptions.find((o) => o.key === key)?.onClick?.(),
                },
                {
                  default: () =>
                      h(
                          NButton,
                          {
                            size: 'tiny',
                            quaternary: true,
                            type: 'default',
                          },
                          {
                            default: () => '更多',
                            icon: renderIcon('material-symbols:more-horiz', {size: 16}),
                          }
                      ),
                }
            )
        )
        return actions
      },
    },
  ]
})


</script>

<template>
  <CommonPage show-footer title="测试用例">

    <!--  搜索&表格  -->
    <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        v-model:checked-row-keys="checkedRowKeys"
        :query-bar-props="queryBarProps"
        :is-pagination="true"
        :columns="columns"
        :get-data="fetchCaseList"
        :row-key="'case_id'"
        :scroll-x="2210"
        :single-line="true"
        @pagination-meta="onListPaginationMeta"
        @query-bar-create="customHandleAdd"
        @query-bar-delete="handleBatchDelete"
        @query-bar-action="onQueryBarAction"
    >

      <!--  搜索  -->
      <template #queryBar>
        <QueryBarItem label="用例名称：">
          <NInput
              v-model:value="queryItems.case_name"
              clearable
              type="text"
              placeholder="请输入用例名称"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="用例属性：">
          <NSelect
              v-model:value="queryItems.case_attr"
              :options="caseAttrOptions"
              clearable
              placeholder="请选择用例属性"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="用例类型：">
          <NSelect
              v-model:value="queryItems.case_type"
              :options="caseTypeOptions"
              clearable
              placeholder="请选择用例类型"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="所属应用：">
          <NSelect
              v-model:value="queryItems.case_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择所属应用"
              class="query-input"
          />
        </QueryBarItem>
        <QueryBarItem label="所属标签：">
          <NPopover
              v-model:show="tagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
          >
            <template #trigger>
              <NInput
                  :value="getSelectedTagNames()"
                  clearable
                  readonly
                  placeholder="请选择所属标签"
                  class="query-input"
                  @clear="queryItems.case_tags = []"
                  @click="tagPopoverShow = !tagPopoverShow"
              />
            </template>
            <template #default>
              <div class="tag-picker-panel">
                <div class="tag-picker-col overlay-scroll">
                  <NList v-if="Object.keys(tagModeGroups).length > 0">
                    <NListItem
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': selectedTagMode === mode, 'tag-mode-item': true }"
                        @click="selectedTagMode = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="autotest-empty-hint">
                    {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                  </div>
                </div>
                <div class="tag-picker-col tag-picker-col--names overlay-scroll">
                  <NList v-if="selectedTagMode && currentTagNames.length > 0">
                    <NListItem
                        v-for="tag in currentTagNames"
                        :key="tag.tag_id"
                        :class="{ 'tag-name-selected': isTagSelected(tag.tag_id) }"
                        class="tag-list-item"
                        @click="handleTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="autotest-empty-hint">
                    {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </template>
          </NPopover>
        </QueryBarItem>
        <QueryBarItem label="所属人员：">
          <NInput
              v-model:value="queryItems.owner_user"
              clearable
              type="text"
              placeholder="请输入所属人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="创建人员：">
          <NInput
              v-model:value="queryItems.created_user"
              clearable
              type="text"
              placeholder="请输入创建人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="更新人员：">
          <NInput
              v-model:value="queryItems.updated_user"
              clearable
              type="text"
              placeholder="请输入更新人员"
              class="query-input"
              @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
      </template>

    </CrudTable>

    <!-- 导入公共接口脚本对话框：点击或拖拽上传模板xlsx；解析不合规行明细在框内展示便于修稿后重试，落库结果在异步中心查看 -->
    <NModal v-model:show="importScriptShow" preset="card" title="导入公共接口脚本" style="width: 640px">
      <NUpload
          v-model:file-list="importFileList"
          :max="1"
          accept=".xlsx"
          :default-upload="false"
          directory-dnd
      >
        <NUploadDragger>
          <TheIcon icon="material-symbols:upload" :size="40" class="import-drag-icon" />
          <div class="import-drag-text">点击或拖拽文件到该区域以上传</div>
          <div class="import-drag-hint">请使用模板文件(.xlsx)，仅读取第1个sheet页</div>
        </NUploadDragger>
      </NUpload>
      <NAlert
          v-if="importErrors.length"
          type="error"
          title="存在不合规行，已取消导入"
          style="margin-top: 12px"
      >
        <div class="import-error-list">
          <div v-for="(item, index) in importErrors" :key="index">第{{ item.row }}行：{{ item.reason }}</div>
        </div>
      </NAlert>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="importScriptShow = false">取消</NButton>
          <NButton type="primary" :loading="importLoading" @click="submitImportScript">开始导入</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 公共接口转脚本对话框：为勾选的公共接口逐个生成独立脚本(异步任务，结果在异步中心查看) -->
    <NModal v-model:show="generateScriptShow" preset="card" title="脚本生成" style="width: 560px">
      <NAlert type="info" style="margin-bottom: 16px">
        将为每个接口生成独立脚本，脚本仅包含当前接口
      </NAlert>
      <NForm :model="generateForm" label-placement="left" label-width="80" size="small">
        <NFormItem label="所属应用" required>
          <NSelect
              v-model:value="generateForm.case_project"
              :options="projectOptions"
              :loading="projectLoading"
              clearable
              filterable
              placeholder="请选择所属应用"
          />
        </NFormItem>
        <NFormItem label="脚本类型" required>
          <NSelect
              v-model:value="generateForm.case_type"
              :options="generateTypeOptions"
              clearable
              placeholder="请选择脚本类型"
          />
        </NFormItem>
        <NFormItem label="用例属性" required>
          <NSelect
              v-model:value="generateForm.case_attr"
              :options="caseAttrOptions"
              clearable
              placeholder="请选择用例属性"
          />
        </NFormItem>
        <NFormItem label="所属标签" :required="generateTagRequired">
          <NPopover
              v-model:show="generateTagPopoverShow"
              trigger="click"
              placement="bottom-start"
              :style="{ width: '400px' }"
          >
            <template #trigger>
              <NInput
                  :value="getGenerateSelectedTagNames()"
                  clearable
                  readonly
                  placeholder="请选择所属标签"
                  @clear="generateForm.case_tags = []"
                  @click="generateTagPopoverShow = !generateTagPopoverShow"
              />
            </template>
            <template #default>
              <div class="tag-picker-panel">
                <div class="tag-picker-col overlay-scroll">
                  <NList v-if="Object.keys(tagModeGroups).length > 0">
                    <NListItem
                        v-for="(tags, mode) in tagModeGroups"
                        :key="mode"
                        :class="{ 'tag-mode-selected': generateSelectedTagMode === mode, 'tag-mode-item': true }"
                        @click="generateSelectedTagMode = mode"
                    >
                      <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="autotest-empty-hint">
                    {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                  </div>
                </div>
                <div class="tag-picker-col tag-picker-col--names overlay-scroll">
                  <NList v-if="generateSelectedTagMode && generateCurrentTagNames.length > 0">
                    <NListItem
                        v-for="tag in generateCurrentTagNames"
                        :key="tag.tag_id"
                        :class="{ 'tag-name-selected': isGenerateTagSelected(tag.tag_id) }"
                        class="tag-list-item"
                        @click="handleGenerateTagSelect(tag.tag_id)"
                    >
                      <span class="tag-checkbox">{{ isGenerateTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                      <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                    </NListItem>
                  </NList>
                  <div v-else class="autotest-empty-hint">
                    {{ generateSelectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                  </div>
                </div>
              </div>
            </template>
          </NPopover>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="generate-footer">
          <span class="generate-selected-hint">已选择 {{ generateSelectedCount }} 条</span>
          <NSpace justify="end">
            <NButton @click="generateScriptShow = false">取消</NButton>
            <NButton type="primary" :loading="generateLoading" @click="submitGenerateScript">开始生成</NButton>
          </NSpace>
        </div>
      </template>
    </NModal>

    <ExecConfigModal ref="execConfigModalRef" v-model:run-loading="runLoading" />
    <CaseHistoryDrawer
        v-model:show="historyDrawerVisible"
        :case-row="historyCaseRow"
    />
  </CommonPage>
</template>


<style scoped>
/* 导入公共接口脚本弹窗：拖拽上传区提示 */
.import-drag-icon {
  color: var(--n-text-color-3);
  margin-bottom: 8px;
}

.import-drag-text {
  font-size: 14px;
}

.import-drag-hint {
  margin-top: 6px;
  font-size: 13px;
  color: var(--n-text-color-3);
}

.import-error-list {
  max-height: 240px;
  overflow-y: auto;
  line-height: 1.8;
}

.env-fields {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.field {
  width: 100%;
}

:deep(.n-collapse-item__header) {
  padding: 12px;
}

.tag-mode-selected {
  background-color: var(--n-color-primary-hover);
  font-weight: 500;
}

/* 用例列表查询：标签二级选择面板 */
.tag-picker-panel {
  display: flex;
  height: 300px;
  width: 400px;
}

.tag-picker-col {
  width: 45%;
  overflow-x: hidden;
  overflow-y: auto;
}

.tag-picker-col--names {
  width: 50%;
}

.tag-name-selected {
  background-color: var(--n-color-primary-hover);
  font-weight: 500;
}

:deep(.n-list-item) {
  transition: background-color 0.2s;
}

:deep(.n-list-item:hover) {
  background-color: var(--n-color-hover);
}

/* 统一查询输入框宽度 */
.query-input {
  width: 200px;
}

/* 列表「所属标签」紧凑展示 */
.case-tags-cell-trigger {
  max-width: 100%;
}

.case-tags-more {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-2);
}

.case-tags-tooltip-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 320px;
  justify-content: flex-start;
}

/* 标签列表项样式 */
.tag-list-item {
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-checkbox {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  color: #18a058;
  font-weight: bold;
}

.tag-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 标签分类列表项样式 */
.tag-mode-item {
  cursor: pointer;
  padding: 8px 12px;
}

.tag-mode-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

/* 脚本生成弹窗：footer 左下角已选数量与右侧按钮分列两端 */
.generate-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 脚本生成弹窗：已选接口数量置灰提示 */
.generate-selected-hint {
  color: var(--n-text-color-3);
  font-size: 13px;
}

</style>
