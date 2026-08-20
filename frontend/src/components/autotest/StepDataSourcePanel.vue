<template>
  <!-- DataSource卡片：位于 Request 下方、Response 上方 -->
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="[
        'step-editor-card',
        { 'is-collapsed': dataSourceCollapsed },
        { 'is-unavailable': !canUseDataSource },
      ]"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            :class="{ 'is-disabled': !canUseDataSource }"
            role="button"
            :tabindex="canUseDataSource ? 0 : -1"
            :aria-disabled="!canUseDataSource"
            @click="toggleDataSourceCollapsed"
            @keydown.enter.prevent="toggleDataSourceCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="dataSourceCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">DataSource</div>
        </div>
        <div v-if="dataSourceCollapsed" class="card-header-actions">
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-text class="data-source-tip" depth="3" style="cursor: help;">
                {{ dataSourceTipText }}
              </n-text>
            </template>
            {{ dataSourceTipText }}
          </n-tooltip>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!dataSourceCollapsed && canUseDataSource">
      <div class="data-source-content">
        <n-tabs type="line" animated class="data-source-tabs">
          <n-tab-pane name="preview" tab="数据预览">
            <n-space vertical :size="12">
              <div class="data-source-axis-row">
                <span class="data-source-axis-label">矩阵方向：</span>
                <n-radio-group
                    v-model:value="axis"
                    size="small"
                    :disabled="panelReadonly"
                    @update:value="onAxisChange"
                >
                  <n-radio-button :value="1">垂直模式</n-radio-button>
                  <n-radio-button :value="0">水平模式</n-radio-button>
                </n-radio-group>
                <n-text depth="3" class="data-source-axis-tip">
                  {{ axis === 0 ? '场景为行、字段为列' : '场景为列、字段为行' }}
                </n-text>
              </div>
              <div ref="luckysheetWrapRef" class="luckysheet-wrap" :class="{ 'is-fullscreen': isFullscreen }">
                <div class="luckysheet-more-dropdown">
                  <n-dropdown
                      trigger="click"
                      placement="bottom-end"
                      :options="dataSourceMoreOptions"
                      :z-index="10002"
                      @select="onDataSourceMoreSelect"
                  >
                    <n-button size="tiny" quaternary :disabled="panelReadonly">
                      更多
                      <TheIcon icon="material-symbols:arrow-drop-down" :size="16" />
                    </n-button>
                  </n-dropdown>
                </div>
                <input
                    ref="importFileRef"
                    type="file"
                    accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    style="display: none"
                    @change="onImportFileChange"
                />
                <Luckysheet
                    ref="luckysheetRef"
                    :data="sheetData"
                    :columns="sheetColumns"
                    :readonly="panelReadonly"
                    :protectedRowKeywords="FIXED_KEYWORDS"
                    @change="onSheetChange"
                    @protectedAction="onProtectedAction"
                />
              </div>
            </n-space>
          </n-tab-pane>

          <n-tab-pane name="generate" tab="数据生成">
            <n-space vertical :size="12">
              <div class="data-source-row">
                <div class="data-source-row-label">接口文档：</div>
                <n-space>
                  <n-upload
                      :default-upload="false"
                      :show-file-list="false"
                      accept=".xlsx,.xls,.csv,.json,.yaml,.yml"
                      @change="onApiDocFileSelected"
                  >
                    <n-button size="small" type="primary" tertiary :disabled="panelReadonly">上传</n-button>
                  </n-upload>
                  <n-button
                      size="small"
                      type="primary"
                      tertiary
                      :disabled="panelReadonly"
                      @click="downloadApiDocTemplate"
                  >数据模板
                  </n-button>
                </n-space>
              </div>

              <div class="data-source-subtitle">数据校验点</div>
              <n-checkbox-group v-model:value="dataSource.validationPoints" :disabled="panelReadonly">
                <n-space>
                  <n-checkbox value="required">必输性</n-checkbox>
                  <n-checkbox value="length">字段长度</n-checkbox>
                  <n-checkbox value="type">类型</n-checkbox>
                  <n-checkbox value="enum">枚举值</n-checkbox>
                  <n-checkbox value="decimal">小数点位数</n-checkbox>
                </n-space>
              </n-checkbox-group>

              <n-data-table
                  :row-key="dataSourceGeneratedRowKey"
                  :columns="dataSourceGeneratedColumns"
                  :data="dataSource.generatedRows"
                  :bordered="false"
                  :scroll-x="900"
                  size="small"
              />
            </n-space>
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-collapse-transition>
  </n-card>

  <!-- DataSource 行编辑弹窗 -->
  <n-modal
      v-model:show="dataSourceEditModalVisible"
      preset="dialog"
      title="编辑数据"
      positive-text="确定"
      negative-text="取消"
      @positive-click="confirmDataSourceEdit"
  >
    <div style="padding: 8px 0;">
      <n-space vertical :size="10">
        <div v-for="cell in dataSourceEditForm.cells" :key="cell.key">
          <div style="margin-bottom: 6px;">{{ cell.label }}：</div>
          <n-input v-model:value="cell.value" clearable/>
        </div>
      </n-space>
    </div>
  </n-modal>
</template>

<script setup>
defineOptions({ name: 'StepDataSourcePanel' })

import { computed, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCollapseTransition,
  NDataTable,
  NDropdown,
  NInput,
  NModal,
  NRadioButton,
  NRadioGroup,
  NSpace,
  NTabPane,
  NTabs,
  NText,
  NTooltip,
  NUpload,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import Luckysheet from '@/components/common/Luckysheet.vue'
import api from '@/api'

const props = defineProps({
  step: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
  /** 步骤名称，用于折叠态 tip */
  stepName: { type: String, default: '' },
  /** 无名称时的类型文案，如「HTTP请求」「TCP请求」 */
  stepTypeLabel: { type: String, default: '请求' },
  dataSourceId: { type: [Number, String], default: null },
  dataSourceName: { type: String, default: '' },
  dataSourceDesc: { type: String, default: '' },
  /** 外部布局变化触发器（如步骤树折叠/展开），用于通知表格重新计算尺寸 */
  resizeTrigger: { type: Number, default: 0 },
})

const emit = defineEmits(['update:dataSourceId', 'update:dataSourceName', 'update:dataSourceDesc'])

const dataSourceId = computed({
  get: () => props.dataSourceId,
  set: (v) => emit('update:dataSourceId', v),
})
const dataSourceName = computed({
  get: () => props.dataSourceName,
  set: (v) => emit('update:dataSourceName', v),
})
const dataSourceDesc = computed({
  get: () => props.dataSourceDesc,
  set: (v) => emit('update:dataSourceDesc', v),
})

const route = useRoute()
const dataSourceCollapsed = ref(true)

const REQUEST_STEP_TYPES = new Set(['HTTP请求', 'TCP请求', 'http', 'tcp'])

/** 步骤已落库：具备 step_id 或 step_code */
const isStepPersisted = computed(() => {
  const original = props.step?.original || {}
  const stepId = original.id != null ? Number(original.id) : NaN
  const stepCode = String(original.step_code || '').trim()
  return Boolean((Number.isFinite(stepId) && stepId > 0) || stepCode)
})

const isRequestStepType = computed(() => {
  const original = props.step?.original || {}
  const typeValue = String(original.step_type || props.step?.type || props.stepTypeLabel || '').trim()
  return REQUEST_STEP_TYPES.has(typeValue)
})

/** 仅已落库的 HTTP/TCP 请求步骤可展开 DataSource */
const canUseDataSource = computed(() => isStepPersisted.value && isRequestStepType.value)

/** 只读或未落库时，面板内操作均不可用 */
const panelReadonly = computed(() => props.readonly || !canUseDataSource.value)

const ts = () => new Date().toISOString().slice(0, 19).replace('T', ' ')
const dataSource = reactive({
  apiDocFileName: '',
  validationPoints: [],
  generatedRows: [
    { id: 'gen-1', name: '生成数据1', remark: '备注1', generatedAt: ts() },
    { id: 'gen-2', name: '生成数据2', remark: '备注2', generatedAt: ts() },
    { id: 'gen-3', name: '生成数据3', remark: '备注3', generatedAt: ts() },
  ],
})

const dataSourceTipText = computed(() => {
  const name = String(props.stepName || '').trim()
  const typeLabel = String(props.stepTypeLabel || '请求').trim() || '请求'
  const stepName = name || `${typeLabel}`
  if (!isStepPersisted.value) {
    return `${stepName}(本步骤) - 请先保存步骤后再使用数据源`
  }
  if (!isRequestStepType.value) {
    return `${stepName}(本步骤) - 仅HTTP/TCP请求步骤可使用数据源`
  }
  const dsName = String(dataSourceName.value || '').trim()
  const dsDesc = String(dataSourceDesc.value || '').trim()
  if (dsName && dsDesc) return `${stepName}(本步骤) - ${dsName} (${dsDesc})`
  if (dsName) return `${stepName}(本步骤) - ${dsName}`
  return `${stepName}(本步骤) - 数据驱动文件上传或接口文档分析`
})

const FIXED_KEYWORDS = ['HEAD', 'BODY', 'ASSERT_HEAD', 'ASSERT_BODY']

// 矩阵方向：1=垂直(场景为列)，0=水平(场景为行)，与后端 axis 字段一致；空白模板默认垂直
const AXIS_HORIZONTAL = 0
const AXIS_VERTICAL = 1
const axis = ref(AXIS_VERTICAL)

const isSectionMarker = (value) => {
  const text = value == null ? '' : String(value).trim().toUpperCase()
  return FIXED_KEYWORDS.includes(text)
}

/** 按分区标记识别矩阵方向，避免沿用库中默认 axis=0 误判垂直矩阵 */
const detectAxisFromMatrix = (matrix) => {
  if (!Array.isArray(matrix) || !matrix.length) return AXIS_VERTICAL
  const header = Array.isArray(matrix[0]) ? matrix[0] : []
  if (header.some(isSectionMarker)) return AXIS_HORIZONTAL
  for (let r = 1; r < matrix.length; r++) {
    if (isSectionMarker(matrix[r]?.[0])) return AXIS_VERTICAL
  }
  return AXIS_VERTICAL
}

/** 矩阵转置（水平 ↔ 垂直互换） */
const transposeMatrix = (matrix) => {
  if (!Array.isArray(matrix) || !matrix.length) return []
  const colCount = Math.max(...matrix.map((row) => (Array.isArray(row) ? row.length : 0)))
  const result = []
  for (let c = 0; c < colCount; c++) {
    const row = []
    for (let r = 0; r < matrix.length; r++) {
      row.push(matrix[r]?.[c] ?? '')
    }
    result.push(row)
  }
  return result
}

/* ========================= Luckysheet 数据状态 ========================= */
const luckysheetRef = ref(null)
const luckysheetWrapRef = ref(null)
const sheetColumns = ref([])
const sheetData = ref([])
const hasDbRecord = ref(false)
const isDirty = ref(false)
const isLoading = ref(false)
const hasLoaded = ref(false)
/** 表格编辑缓存：步骤切换会销毁编辑器(key=step.id)，Luckysheet 先于本组件卸载，须用缓存拼 dataframe */
const cachedMatrix = ref([])
const cachedAxis = ref(1)

const getCaseId = () => (route.query.case_id ? Number(route.query.case_id) : null)

const getStepContext = () => {
  const original = props.step?.original || {}
  const caseCode = String(original.case_code ?? original.case?.case_code ?? route.query.case_code ?? '').trim()
  const originalCaseId = original.case_id != null ? Number(original.case_id) : null
  return {
    caseId: getCaseId() || originalCaseId,
    caseCode,
    stepId: original.id ? Number(original.id) : null,
    stepCode: String(original.step_code || '').trim(),
  }
}

/** 上一次的步骤上下文，用于步骤切换时保存旧步骤数据 */
const lastStepContext = ref(null)

const buildBlankTemplate = (sceneNames = []) => {
  const headers = ['', ...sceneNames]
  const data = FIXED_KEYWORDS.map((kw) => [kw, ...sceneNames.map(() => '')])
  return { headers, data }
}

const normalizeHeaderRow = (row, length) => {
  const arr = Array.isArray(row) ? row : []
  const result = []
  for (let i = 0; i < length; i++) {
    const v = arr[i]
    result.push(v == null || v === '' ? '' : String(v))
  }
  return result
}

const padTypedRow = (row, length) => {
  const arr = Array.isArray(row) ? row : []
  const result = []
  for (let i = 0; i < length; i++) {
    if (i >= arr.length || arr[i] === undefined || arr[i] === null) {
      result.push(i === 0 ? '' : null)
      continue
    }
    result.push(arr[i])
  }
  return result
}

/** 将二维矩阵载入表格（第 0 行为列头，其余为数据行）；空矩阵回落为空白模板 */
const applyMatrixToSheet = (matrix) => {
  if (!Array.isArray(matrix) || !matrix.length) {
    const { headers, data } = buildBlankTemplate()
    sheetColumns.value = headers
    sheetData.value = data
    return
  }
  const maxCol = Math.max(...matrix.map((row) => (Array.isArray(row) ? row.length : 0)))
  sheetColumns.value = normalizeHeaderRow(matrix[0], maxCol)
  sheetData.value = matrix.slice(1).map((row) => padTypedRow(row, maxCol))
}

/** 将当前 sheetColumns/sheetData 写入缓存（Luckysheet 未就绪或已销毁时用） */
const syncCacheFromSheetState = () => {
  const headers = Array.isArray(sheetColumns.value) ? sheetColumns.value : []
  const rows = Array.isArray(sheetData.value) ? sheetData.value : []
  if (!headers.length) return
  const maxCol = headers.length
  cachedMatrix.value = [
    normalizeHeaderRow(headers, maxCol),
    ...rows.map((r) => padTypedRow(r, maxCol)),
  ]
  cachedAxis.value = axis.value
}

const loadStepDataframePreview = async (dataSourceIdOverride) => {
  if (isLoading.value) return
  if (!canUseDataSource.value) {
    hasLoaded.value = false
    isDirty.value = false
    return
  }
  const ctx = getStepContext()
  lastStepContext.value = ctx
  const { caseId, caseCode, stepId, stepCode } = ctx
  const effectiveDataSourceId = dataSourceIdOverride != null ? dataSourceIdOverride : dataSourceId.value

  if (!caseId && !caseCode && !stepId && !stepCode && !effectiveDataSourceId) {
    applyMatrixToSheet([])
    axis.value = AXIS_VERTICAL
    hasDbRecord.value = false
    isDirty.value = false
    hasLoaded.value = true
    syncCacheFromSheetState()
    return
  }

  isLoading.value = true
  try {
    const params = {}
    if (effectiveDataSourceId) {
      params.data_source_id = effectiveDataSourceId
    } else {
      if (caseId) params.case_id = caseId
      if (caseCode) params.case_code = caseCode
      if (stepId) params.step_id = stepId
      if (stepCode) params.step_code = stepCode
    }
    const res = await api.buildDataSource(params)
    const info = res?.data || {}
    const matrix = Array.isArray(info.dataframe) ? info.dataframe : []
    applyMatrixToSheet(matrix)
    axis.value = detectAxisFromMatrix(matrix)
    hasDbRecord.value = info.data_source_id != null
    if (info.data_source_id != null) dataSourceId.value = info.data_source_id
    if (info.file_name != null) dataSourceName.value = String(info.file_name)
    if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
    isDirty.value = false
  } catch (_) {
    applyMatrixToSheet([])
    axis.value = AXIS_VERTICAL
    hasDbRecord.value = false
    isDirty.value = false
  } finally {
    isLoading.value = false
    hasLoaded.value = true
    syncCacheFromSheetState()
  }
}

const toggleDataSourceCollapsed = () => {
  if (!canUseDataSource.value) return
  const wasCollapsed = dataSourceCollapsed.value
  dataSourceCollapsed.value = !dataSourceCollapsed.value
  if (wasCollapsed && !dataSourceCollapsed.value) {
    loadStepDataframePreview()
  }
}

const onSheetChange = () => {
  isDirty.value = true
  refreshMatrixCache()
}

const onProtectedAction = (action) => {
  if (action === 'delete') {
    $message.warning('HEAD/BODY/ASSERT_HEAD/ASSERT_BODY 所在行不允许删除')
  }
}

/** 切换矩阵方向：将当前表格内容转置到目标方向（axis 已由 v-model 更新） */
const onAxisChange = () => {
  if (panelReadonly.value) return
  const matrix = getCurrentDataframeMatrix()
  applyMatrixToSheet(transposeMatrix(matrix))
  isDirty.value = true
  // 转置后 Luckysheet 异步重建，下一拍再缓存，避免读到旧实例
  Promise.resolve().then(() => refreshMatrixCache())
}

const getCurrentDataframeMatrix = () => {
  if (luckysheetRef.value?.getDataForSave) {
    const { headers = [], rows = [] } = luckysheetRef.value.getDataForSave() || {}
    const maxCol = headers.length
    if (maxCol > 0) {
      const matrix = [normalizeHeaderRow(headers, maxCol)]
      rows.forEach((row) => {
        matrix.push(padTypedRow(row, maxCol))
      })
      cachedMatrix.value = matrix
      cachedAxis.value = axis.value
      return matrix
    }
  }
  return Array.isArray(cachedMatrix.value) ? cachedMatrix.value.map((row) => [...(row || [])]) : []
}

const refreshMatrixCache = () => {
  const matrix = getCurrentDataframeMatrix()
  if (matrix.length >= 2) {
    cachedMatrix.value = matrix
    cachedAxis.value = axis.value
  }
}

const hasAnySceneData = (matrix) => {
  if (matrix.length < 2) return false
  for (let r = 1; r < matrix.length; r++) {
    const row = matrix[r]
    for (let c = 1; c < row.length; c++) {
      if (row[c] != null && row[c] !== '') return true
    }
  }
  return false
}

/** 垂直矩阵：第 0 行第 1 列起为场景名 */
const extractSceneNamesFromMatrix = (matrix) => {
  if (!Array.isArray(matrix) || !matrix.length) return []
  const header = Array.isArray(matrix[0]) ? matrix[0] : []
  const names = []
  for (let c = 1; c < header.length; c++) {
    const text = header[c] == null ? '' : String(header[c]).trim()
    if (text) names.push(text)
  }
  return names
}

const shouldSave = (force = false) => {
  if (!force && !isDirty.value) return false
  // force 保存（步骤树保存按钮触发）时，必须确保数据已加载，避免空白模板覆盖已有数据源
  if (force && !isDirty.value && !hasLoaded.value) return false
  const matrix = getCurrentDataframeMatrix()
  if (matrix.length < 2) return false
  // /build 默认矩阵只有场景名、字段值全空，不允许落库
  return hasAnySceneData(matrix)
}

/** 供步骤树保存前读取当前面板待落库的场景列名；无字段值时不参与一致性预检 */
const getPendingSceneNames = () => {
  if (!canUseDataSource.value && !hasLoaded.value) return null
  const matrix = getCurrentDataframeMatrix()
  if (!hasAnySceneData(matrix)) return null
  const names = extractSceneNamesFromMatrix(matrix)
  return names.length ? names : null
}

const saveWithContext = async (ctx, opts = {}) => {
  // 引用内嵌只读步骤不写库；步骤切换卸载时不要用 canUseDataSource 当闸门，
  // 卸载过程中 step props 可能已空，会导致误判只读而跳过自动保存。
  if (props.readonly) return { success: true, skipped: true }
  const { caseId, caseCode, stepId, stepCode } = ctx || {}
  if (!(caseId || caseCode) || !(stepId || stepCode)) {
    if (!opts.silent) $message.warning('当前步骤尚未保存入库，请先保存步骤树后再使用数据源')
    return { success: false, skipped: true }
  }
  if (!shouldSave(opts.force)) {
    return { success: true, skipped: true }
  }
  try {
    const matrix = getCurrentDataframeMatrix()
    const payload = {
      case_id: caseId || undefined,
      case_code: caseCode || undefined,
      step_id: Number.isFinite(Number(stepId)) ? Number(stepId) : undefined,
      step_code: stepCode || undefined,
      dataframe: matrix,
      axis: detectAxisFromMatrix(matrix),
    }
    if (dataSourceId.value) payload.data_source_id = dataSourceId.value
    const res = await api.saveOrUpdateDataSource(payload)
    const info = res?.data || {}
    if (info.data_source_id != null) dataSourceId.value = info.data_source_id
    if (info.file_name != null) dataSourceName.value = String(info.file_name)
    if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
    hasDbRecord.value = true
    isDirty.value = false
    if (!opts.silent) {
      $message.success(res?.message || '保存成功')
      await loadStepDataframePreview()
    }
    return { success: true, skipped: false }
  } catch (e) {
    if (!opts.silent) {
      /* 错误信息由 http 拦截器统一提示 */
    }
    return { success: false, skipped: false, error: e }
  }
}

const saveLoading = ref(false)
const dataSourceSave = async (opts = {}) => {
  if (saveLoading.value) return { success: true, skipped: true }
  saveLoading.value = true
  try {
    return await saveWithContext(getStepContext(), { force: true, ...opts })
  } finally {
    saveLoading.value = false
  }
}

/* ========================= 导入/导出 xlsx ========================= */
const importFileRef = ref(null)
const importLoading = ref(false)
const exportLoading = ref(false)

const dataSourceMoreOptions = computed(() => [
  { label: '撤销', key: 'undo', disabled: panelReadonly.value },
  { label: '重做', key: 'redo', disabled: panelReadonly.value },
  { type: 'divider', key: 'd1' },
  { label: '导入模板下载', key: 'downloadTemplate', disabled: panelReadonly.value || downloadTemplateLoading.value },
  { label: '导入', key: 'import', disabled: panelReadonly.value || importLoading.value },
  { label: '导出', key: 'export', disabled: panelReadonly.value || exportLoading.value },
  { label: '保存', key: 'save', disabled: panelReadonly.value || saveLoading.value },
  { type: 'divider', key: 'd2' },
  { label: isFullscreen.value ? '退出全屏' : '全屏', key: 'fullscreen' },
  { label: '解绑', key: 'unbind', disabled: panelReadonly.value || !hasDbRecord.value },
])

const onDataSourceMoreSelect = (key) => {
  if (key === 'undo') luckysheetRef.value?.getLuckysheet()?.undo?.()
  else if (key === 'redo') luckysheetRef.value?.getLuckysheet()?.redo?.()
  else if (key === 'downloadTemplate') downloadStepDataTemplate()
  else if (key === 'import') openImport()
  else if (key === 'export') dataSourceExport()
  else if (key === 'save') dataSourceSave()
  else if (key === 'fullscreen') toggleFullscreen()
  else if (key === 'unbind') unbindDataSource()
}

const openImport = () => {
  if (panelReadonly.value) return
  importFileRef.value?.click()
}

const onImportFileChange = async (ev) => {
  const input = ev.target
  const file = input?.files?.[0]
  if (input) input.value = ''
  if (!file) return
  if (!String(file.name || '').toLowerCase().endsWith('.xlsx')) {
    $message.warning('仅支持 .xlsx 格式的数据驱动文件')
    return
  }
  const { caseId, stepId, stepCode } = getStepContext()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('请先保存步骤后再导入数据源')
    return
  }
  if (importLoading.value) return
  importLoading.value = true
  try {
    const fd = new FormData()
    fd.append('case_id', String(caseId))
    fd.append('step_id', String(stepId))
    fd.append('step_code', stepCode)
    if (dataSourceDesc.value) fd.append('file_desc', dataSourceDesc.value)
    fd.append('file', file)
    const res = await api.singleStepDatasetUpload(fd)
    const info = res?.data || {}
    if (info.data_source_id != null) dataSourceId.value = info.data_source_id
    if (info.file_name != null) dataSourceName.value = String(info.file_name)
    if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
    await loadStepDataframePreview(info.data_source_id)
    $message.success('导入成功')
  } catch (e) {
    $message.error(`导入失败：${e?.message || e}`)
  } finally {
    importLoading.value = false
  }
}

const dataSourceExport = async () => {
  if (exportLoading.value) return
  const { caseId, stepId, stepCode } = getStepContext()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('请先保存步骤后再导出数据源')
    return
  }
  exportLoading.value = true
  try {
    const res = await api.singleStepDatasetDownload({ case_id: caseId, step_id: stepId, step_code: stepCode })
    const contentType = res?.headers?.['content-type'] || ''
    if (contentType.includes('application/json')) {
      const body = JSON.parse(await res.data.text())
      $message.error(body?.message || '导出失败')
      return
    }
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const stepName = String(props.stepName || '').trim() || String(props.stepTypeLabel || '请求').trim()
    link.download = m?.[1] ? decodeURIComponent(m[1]) : `${stepName}_数据源.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('导出成功')
  } catch (e) {
    $message.error(`导出失败：${e?.message || e}`)
  } finally {
    exportLoading.value = false
  }
}

/* ========================= 导入模板下载 ========================= */
const downloadTemplateLoading = ref(false)
const downloadStepDataTemplate = async () => {
  if (downloadTemplateLoading.value) return
  try {
    downloadTemplateLoading.value = true
    const res = await api.downloadHttpStepDatasetImportTemplate()
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const fileName = m?.[1] ? decodeURIComponent(m[1]) : '测试用例HTTP请求步骤数据源模板.xlsx'
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('下载成功')
  } catch (e) {
    $message.error(`下载失败：${e?.message || e}`)
  } finally {
    downloadTemplateLoading.value = false
  }
}

const downloadApiDocTemplate = () => $message.info('后端暂未实现：下载接口文档模板')

/* ========================= 数据生成（占位） ========================= */
const dataSourceEditModalVisible = ref(false)
const dataSourceEditForm = reactive({ rowKey: null, type: 'generated', cells: [] })

const openDataSourceEdit = (type, row) => {
  dataSourceEditForm.rowKey = row?.__rowKey ?? row?.id ?? null
  dataSourceEditForm.type = type
  dataSourceEditForm.cells = []
  dataSourceEditModalVisible.value = true
}

const confirmDataSourceEdit = () => {
  $message.success('已更新')
  dataSourceEditModalVisible.value = false
}

const removeDataSourceRow = (type, row) => {
  const list = type === 'generated' ? dataSource.generatedRows : []
  const idx = list.findIndex((x) => x.id === row?.id)
  if (idx >= 0) {
    list.splice(idx, 1)
    $message.success('已删除')
  }
}

const dataSourceGeneratedColumns = [
  {
    title: '名称',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  { title: '备注', key: 'remark', align: 'center', ellipsis: { tooltip: true } },
  { title: '生成时间', key: 'generatedAt', align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 90,
    render: (row) =>
        h(
            NSpace,
            { size: 8 },
            {
              default: () => [
                h(
                    NButton,
                    {
                      text: true,
                      type: 'error',
                      size: 'small',
                      onClick: () => removeDataSourceRow('generated', row),
                    },
                    { default: () => '删除' }
                ),
                h(
                    NButton,
                    {
                      text: true,
                      type: 'info',
                      size: 'small',
                      onClick: () => openDataSourceEdit('generated', row),
                    },
                    { default: () => '修改' }
                ),
              ],
            }
        ),
  },
]

function dataSourceGeneratedRowKey(row) {
  return row.id
}

const onApiDocFileSelected = (options) => {
  const file = options?.file?.file
  dataSource.apiDocFileName = file?.name || ''
  if (dataSource.apiDocFileName) {
    $message.info(`已选择接口文档：${dataSource.apiDocFileName}（后端暂未实现上传）`)
  }
}

/* ========================= 步骤切换自动保存 ========================= */
// 注意：步骤编辑页右侧编辑器使用 :key="currentStep.id"，切换步骤会销毁整棵子树。
// props.step.id 的 watch 往往来不及触发；实际走 onBeforeUnmount，且子组件 Luckysheet 会先销毁，
// 因此必须依赖编辑过程中的 cachedMatrix，而不能再临时 getDataForSave()。
watch(
    () => props.step?.id,
    async (newId, oldId) => {
      if (oldId != null && oldId !== newId && isDirty.value && lastStepContext.value && canUseDataSource.value) {
        await saveWithContext(lastStepContext.value, { silent: true })
      }
      if (!dataSourceCollapsed.value && canUseDataSource.value) {
        await loadStepDataframePreview()
      }
    },
    { immediate: false }
)

watch(
    () => [route.query.case_id, props.dataSourceId],
    async () => {
      if (isDirty.value) return
      if (!dataSourceCollapsed.value && canUseDataSource.value) {
        await loadStepDataframePreview()
      }
    },
    { deep: false }
)

/** 步骤树保存后 original.id/step_code 回写：恢复可展开并在展开态下加载 */
watch(canUseDataSource, (ok, prev) => {
  if (!ok) {
    dataSourceCollapsed.value = true
    return
  }
  if (ok && !prev && !dataSourceCollapsed.value) {
    loadStepDataframePreview()
  }
})

onBeforeUnmount(() => {
  if (props.readonly || !isDirty.value) return
  const ctx = lastStepContext.value || getStepContext()
  const { caseId, caseCode, stepId, stepCode } = ctx || {}
  if (!(caseId || caseCode) || !(stepId || stepCode)) return
  // Luckysheet 已先卸载，只能用编辑过程中的 cachedMatrix
  const matrix = Array.isArray(cachedMatrix.value) ? cachedMatrix.value.map((row) => [...(row || [])]) : []
  if (matrix.length < 2) return
  if (!hasDbRecord.value && !dataSourceId.value && !hasAnySceneData(matrix)) return
  const payload = {
    case_id: caseId || undefined,
    case_code: caseCode || undefined,
    step_id: Number.isFinite(Number(stepId)) ? Number(stepId) : undefined,
    step_code: stepCode || undefined,
    dataframe: matrix,
    axis: detectAxisFromMatrix(matrix),
  }
  if (dataSourceId.value) payload.data_source_id = dataSourceId.value
  api.saveOrUpdateDataSource(payload).catch(() => {
    /* 静默保存，错误由 http 拦截器统一提示 */
  })
})

/* ========================= 全屏（CSS 铺满页面窗口） ========================= */
const isFullscreen = ref(false)

const BODY_FULLSCREEN_CLASS = 'luckysheet-fullscreen-active'

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
  document.body.classList.toggle(BODY_FULLSCREEN_CLASS, isFullscreen.value)
  nextTick(() => {
    try {
      luckysheetRef.value?.getLuckysheet()?.resize?.()
    } catch (_) {}
  })
}

const onFullscreenKeydown = (e) => {
  if (e.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
    document.body.classList.remove(BODY_FULLSCREEN_CLASS)
    nextTick(() => {
      try {
        luckysheetRef.value?.getLuckysheet()?.resize?.()
      } catch (_) {}
    })
  }
}

/* ========================= 解绑（硬删） ========================= */
const unbindLoading = ref(false)
const unbindDataSource = async () => {
  if (unbindLoading.value) return
  if (!dataSourceId.value) {
    $message.warning('当前步骤未绑定数据源')
    return
  }
  unbindLoading.value = true
  try {
    await api.deleteDataSource({ data_source_id: dataSourceId.value })
    dataSourceId.value = null
    dataSourceName.value = ''
    dataSourceDesc.value = ''
    hasDbRecord.value = false
    isDirty.value = false
    cachedMatrix.value = []
    applyMatrixToSheet([])
    axis.value = 1
    $message.success('解绑成功')
  } catch (e) {
    $message.error('解绑失败：' + (e?.message || ''))
  } finally {
    unbindLoading.value = false
  }
}

/* ========================= 布局变化 → 表格尺寸重算 ========================= */
watch(
    () => props.resizeTrigger,
    () => {
      if (!luckysheetRef.value?.isReady) return
      nextTick(() => {
        setTimeout(() => {
          try {
            luckysheetRef.value?.getLuckysheet()?.resize?.()
          } catch (_) {}
        }, 100)
      })
    }
)

onMounted(() => {
  document.addEventListener('keydown', onFullscreenKeydown, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onFullscreenKeydown, true)
  document.body.classList.remove(BODY_FULLSCREEN_CLASS)
})

defineExpose({
  save: dataSourceSave,
  getPendingSceneNames,
})
</script>

<style scoped>
.card-header-row--with-actions {
  padding-right: 220px;
}

.data-source-tip {
  display: inline-block;
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-source-content {
  padding-top: 4px;
}

.step-editor-card.is-unavailable {
  opacity: 0.55;
}

.panel-title-wrap.is-disabled {
  cursor: not-allowed;
  pointer-events: none;
}

.data-source-axis-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.data-source-axis-label {
  font-size: 12px;
}

.data-source-axis-tip {
  font-size: 12px;
}

.data-source-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.data-source-row-label {
  min-width: 130px;
}

.data-source-subtitle {
  margin-top: 12px;
  margin-bottom: 8px;
  font-weight: 600;
}

.data-source-tabs {
  margin-top: 4px;
}

.luckysheet-wrap {
  width: 100%;
  min-height: 400px;
  height: 520px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.luckysheet-more-dropdown {
  position: absolute;
  top: 0;
  right: 4px;
  z-index: 10;
  display: flex;
  align-items: center;
  height: 28px;
}

/* 全屏模式：CSS 铺满当前页面窗口 */
.luckysheet-wrap.is-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  border-radius: 0;
  border: none;
  background: var(--n-color);
  padding: 8px;
}

.luckysheet-wrap.is-fullscreen > .luckysheet-more-dropdown {
  z-index: 10000;
}
</style>

<!-- 全屏时 Luckysheet 输入框/编辑器挂载在 body 上，需提升其 z-index 使其不被全屏容器遮挡 -->
<style>
body.luckysheet-fullscreen-active #luckysheet-input-box,
body.luckysheet-fullscreen-active #luckysheet-rightclick-menu,
body.luckysheet-fullscreen-active .luckysheet-cols-menu,
body.luckysheet-fullscreen-active .luckysheet-cols-rows-shift-panel {
  z-index: 10001 !important;
}
</style>
