<template>
  <!-- DataSource卡片：位于 Request 下方、Response 上方 -->
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="['step-editor-card', { 'is-collapsed': dataSourceCollapsed }]"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
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

    <n-collapse-transition :show="!dataSourceCollapsed">
      <div class="data-source-content">
        <n-tabs type="line" animated class="data-source-tabs">
          <n-tab-pane name="preview" tab="数据预览">
            <n-space vertical :size="12">
              <div class="luckysheet-wrap">
                <div class="luckysheet-more-dropdown">
                  <n-dropdown
                      trigger="click"
                      placement="bottom-end"
                      :options="dataSourceMoreOptions"
                      @select="onDataSourceMoreSelect"
                  >
                    <n-button size="tiny" quaternary :disabled="props.readonly">
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
                    :readonly="props.readonly"
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
                    <n-button size="small" type="primary" tertiary :disabled="props.readonly">上传</n-button>
                  </n-upload>
                  <n-button
                      size="small"
                      type="primary"
                      tertiary
                      :disabled="props.readonly"
                      @click="downloadApiDocTemplate"
                  >数据模板
                  </n-button>
                </n-space>
              </div>

              <div class="data-source-subtitle">数据校验点</div>
              <n-checkbox-group v-model:value="dataSource.validationPoints" :disabled="props.readonly">
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

import { computed, h, onBeforeUnmount, reactive, ref, watch } from 'vue'
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
import * as XLSX from 'xlsx'

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
  const dsName = String(dataSourceName.value || '').trim()
  const dsDesc = String(dataSourceDesc.value || '').trim()
  const name = String(props.stepName || '').trim()
  const typeLabel = String(props.stepTypeLabel || '请求').trim() || '请求'
  const stepName = name || `${typeLabel}`
  if (dsName && dsDesc) return `${stepName}(本步骤) - ${dsName} (${dsDesc})`
  if (dsName) return `${stepName}(本步骤) - ${dsName}`
  return `${stepName}(本步骤) - 数据驱动文件上传或接口文档分析`
})

const FIXED_KEYWORDS = ['HEAD', 'BODY', 'ASSERT_HEAD', 'ASSERT_BODY']

/* ========================= Luckysheet 数据状态 ========================= */
const luckysheetRef = ref(null)
const sheetColumns = ref([])
const sheetData = ref([])
const hasDbRecord = ref(false)
const isDirty = ref(false)
const isLoading = ref(false)
const hasLoaded = ref(false)

const getCaseId = () => (route.query.case_id ? Number(route.query.case_id) : null)

const getStepContext = () => {
  const original = props.step?.original || {}
  const caseCode = String(original.case_code ?? original.case?.case_code ?? route.query.case_code ?? '').trim()
  return {
    caseId: getCaseId(),
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

const normalizeMatrixRow = (row, length) => {
  const arr = Array.isArray(row) ? row : []
  const result = []
  for (let i = 0; i < length; i++) {
    const v = arr[i]
    result.push(v == null ? '' : String(v))
  }
  return result
}

const loadStepDataframePreview = async () => {
  if (isLoading.value) return
  const ctx = getStepContext()
  lastStepContext.value = ctx
  const { caseId, stepId, stepCode } = ctx

  if (!caseId) {
    const { headers, data } = buildBlankTemplate()
    sheetColumns.value = headers
    sheetData.value = data
    hasDbRecord.value = false
    isDirty.value = false
    hasLoaded.value = true
    return
  }

  // 新增步骤尚未保存（无 stepId/stepCode）：仍查询当前用例下已落库数据源的场景列名，
  // 填充到空白模板列上，便于用户直接在已有场景列上录入数据
  if (!stepId || !stepCode) {
    isLoading.value = true
    try {
      const res = await api.getSceneNamesByCase({ case_id: caseId })
      const scenes = Array.isArray(res?.data?.data_source_scene_name_set)
          ? res.data.data_source_scene_name_set
          : []
      const { headers, data } = buildBlankTemplate(scenes)
      sheetColumns.value = headers
      sheetData.value = data
      hasDbRecord.value = false
      isDirty.value = false
    } catch (_) {
      const { headers, data } = buildBlankTemplate()
      sheetColumns.value = headers
      sheetData.value = data
      hasDbRecord.value = false
      isDirty.value = false
    } finally {
      isLoading.value = false
    }
    hasLoaded.value = true
    return
  }

  isLoading.value = true
  try {
    if (dataSourceId.value) {
      const res = await api.getDataSourceByCaseStep({
        case_id: caseId,
        step_id: stepId,
        step_code: stepCode,
      })
      const info = res?.data || {}
      const matrix = Array.isArray(info.dataframe) ? info.dataframe : []
      if (matrix.length > 0) {
        const maxCol = Math.max(...matrix.map((row) => (Array.isArray(row) ? row.length : 0)))
        sheetColumns.value = normalizeMatrixRow(matrix[0], maxCol)
        sheetData.value = matrix.slice(1).map((row) => normalizeMatrixRow(row, maxCol))
      } else {
        const { headers, data } = buildBlankTemplate()
        sheetColumns.value = headers
        sheetData.value = data
      }
      hasDbRecord.value = true
      if (info.file_name != null) dataSourceName.value = String(info.file_name)
      if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
    } else {
      const res = await api.getSceneNamesByCase({ case_id: caseId })
      const scenes = Array.isArray(res?.data?.data_source_scene_name_set)
          ? res.data.data_source_scene_name_set
          : []
      const { headers, data } = buildBlankTemplate(scenes)
      sheetColumns.value = headers
      sheetData.value = data
      hasDbRecord.value = false
    }
    isDirty.value = false
  } catch (_) {
    const { headers, data } = buildBlankTemplate()
    sheetColumns.value = headers
    sheetData.value = data
    hasDbRecord.value = false
    isDirty.value = false
  } finally {
    isLoading.value = false
    hasLoaded.value = true
  }
}

const toggleDataSourceCollapsed = () => {
  const wasCollapsed = dataSourceCollapsed.value
  dataSourceCollapsed.value = !dataSourceCollapsed.value
  if (wasCollapsed && !dataSourceCollapsed.value) {
    loadStepDataframePreview()
  }
}

const onSheetChange = () => {
  isDirty.value = true
}

const onProtectedAction = (action) => {
  if (action === 'delete') {
    $message.warning('HEAD/BODY/ASSERT_HEAD/ASSERT_BODY 所在行不允许删除')
  }
}

const getCurrentDataframeMatrix = () => {
  if (!luckysheetRef.value) return []
  const { headers = [], rows = [] } = luckysheetRef.value.getDataForSave() || {}
  const maxCol = headers.length
  const matrix = [normalizeMatrixRow(headers, maxCol)]
  rows.forEach((row) => {
    matrix.push(normalizeMatrixRow(row, maxCol))
  })
  return matrix
}

const hasAnySceneData = (matrix) => {
  if (matrix.length < 2) return false
  for (let r = 1; r < matrix.length; r++) {
    const row = matrix[r]
    for (let c = 1; c < row.length; c++) {
      if (row[c] != null && String(row[c]).trim() !== '') return true
    }
  }
  return false
}

const shouldSave = (force = false) => {
  if (!force && !isDirty.value) return false
  // force 保存（步骤树保存按钮触发）时，必须确保数据已加载，避免空白模板覆盖已有数据源
  if (force && !isDirty.value && !hasLoaded.value) return false
  const matrix = getCurrentDataframeMatrix()
  if (matrix.length < 2) return false
  if (hasDbRecord.value || dataSourceId.value) return true
  return hasAnySceneData(matrix)
}

const saveWithContext = async (ctx, opts = {}) => {
  if (props.readonly) return { success: true, skipped: true }
  const { caseId, caseCode, stepId, stepCode } = ctx || {}
  if (!caseId || !stepId || !stepCode) {
    if (!opts.silent) $message.warning('当前步骤尚未保存入库，请先保存步骤树后再保存数据')
    return { success: false, skipped: true }
  }
  if (!shouldSave(opts.force)) {
    return { success: true, skipped: true }
  }
  try {
    const matrix = getCurrentDataframeMatrix()
    const res = await api.saveOrUpdateDataSource({
      case_id: caseId,
      case_code: caseCode,
      step_id: stepId,
      step_code: stepCode,
      dataframe: matrix,
    })
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
  { label: '导入模板下载', key: 'downloadTemplate', disabled: props.readonly || downloadTemplateLoading.value },
  { label: '导入', key: 'import', disabled: props.readonly || importLoading.value },
  { label: '导出', key: 'export', disabled: props.readonly || exportLoading.value },
  { label: '保存', key: 'save', disabled: props.readonly || saveLoading.value },
])

const onDataSourceMoreSelect = (key) => {
  if (key === 'downloadTemplate') downloadStepDataTemplate()
  else if (key === 'import') openImport()
  else if (key === 'export') dataSourceExport()
  else if (key === 'save') dataSourceSave()
}

const openImport = () => {
  if (props.readonly) return
  importFileRef.value?.click()
}

const readFileAsArrayBuffer = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve(e.target.result)
      reader.onerror = (e) => reject(e)
      reader.readAsArrayBuffer(file)
    })

const onImportFileChange = async (ev) => {
  const input = ev.target
  const file = input?.files?.[0]
  if (input) input.value = ''
  if (!file) return
  if (!String(file.name || '').toLowerCase().endsWith('.xlsx')) {
    $message.warning('仅支持 .xlsx 格式的数据驱动文件')
    return
  }
  if (importLoading.value) return
  importLoading.value = true
  try {
    const buffer = await readFileAsArrayBuffer(file)
    const workbook = XLSX.read(buffer, { type: 'array' })
    const sheetName = workbook.SheetNames[0]
    const worksheet = workbook.Sheets[sheetName]
    const aoa = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' })
    if (!aoa.length) {
      $message.warning('导入文件为空')
      return
    }
    const maxCol = Math.max(...aoa.map((row) => (Array.isArray(row) ? row.length : 0)))
    sheetColumns.value = normalizeMatrixRow(aoa[0], maxCol)
    sheetData.value = aoa.slice(1).map((row) => normalizeMatrixRow(row, maxCol))
    isDirty.value = true
    $message.success('导入成功，请保存后生效')
  } catch (e) {
    $message.error(`导入失败：${e?.message || e}`)
  } finally {
    importLoading.value = false
  }
}

const dataSourceExport = () => {
  if (exportLoading.value) return
  exportLoading.value = true
  try {
    const matrix = getCurrentDataframeMatrix()
    const worksheet = XLSX.utils.aoa_to_sheet(matrix)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1')
    const caseId = getCaseId()
    const stepName = String(props.stepName || '').trim() || String(props.stepTypeLabel || '请求').trim()
    const fileName = `${caseId}_${stepName}_数据源.xlsx`.replace(/[\\/:*?"<>|]/g, '_')
    XLSX.writeFile(workbook, fileName)
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
watch(
    () => props.step?.id,
    async (newId, oldId) => {
      if (oldId != null && oldId !== newId && isDirty.value && lastStepContext.value) {
        await saveWithContext(lastStepContext.value, { silent: true })
      }
      if (!dataSourceCollapsed.value) {
        await loadStepDataframePreview()
      }
    },
    { immediate: false }
)

watch(
    () => [route.query.case_id, props.dataSourceId],
    async () => {
      if (!dataSourceCollapsed.value) {
        await loadStepDataframePreview()
      }
    },
    { deep: false }
)

onBeforeUnmount(async () => {
  if (!isDirty.value || !lastStepContext.value) return
  const ctx = lastStepContext.value
  const { caseId, caseCode, stepId, stepCode } = ctx
  if (!caseId || !stepId || !stepCode) return
  try {
    const matrix = getCurrentDataframeMatrix()
    if (matrix.length < 2) return
    await api.saveOrUpdateDataSource({
      case_id: caseId,
      case_code: caseCode,
      step_id: stepId,
      step_code: stepCode,
      dataframe: matrix,
    })
  } catch (_) {
    /* 静默保存，错误由 http 拦截器统一提示 */
  }
})

defineExpose({
  save: dataSourceSave,
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
</style>
