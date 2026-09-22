<!--
  PerfApiDatasetPanel — 压测接口 DataSource 卡（对齐 autotest StepDataSourcePanel 设计）

  数据源归属锁定当前接口（一个接口只能有一个数据源，bind_api_id 唯一）；
  卡片默认折叠，展开时自动加载接口绑定的数据源（不存在则按接口报文推导矩阵模板）；
  卡内承载该接口数据源的编辑：矩阵方向/Luckysheet 在线编辑后经「更多」下拉「保存数据源」落库
  （create/update 走 dataframe+axis 矩阵协议，按 bind_api_id upsert）；
  「更多」下拉 12 项与文案逐字对齐 StepDataSourcePanel：
  导入/导出/保存/同步报文字段/正交易场景/模板下载/全屏/解绑。
  上传解析复用 /perf/dataset/upload（autotest 四分区解析器），保存时随 payload 留文件溯源。
  卡片壳复用全局 .step-editor-card。
-->
<template>
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="['step-editor-card', { 'is-collapsed': collapsed }]"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleCollapsed"
            @keydown.enter.prevent="toggleCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="collapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">DataSource</div>
        </div>
        <div v-if="collapsed" class="card-header-actions">
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-text class="data-source-tip" depth="3" style="cursor: help;">
                {{ collapsedTip }}
              </n-text>
            </template>
            {{ collapsedTip }}
          </n-tooltip>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!collapsed">
      <!-- 接口未落库：数据源必须归属接口，先保存接口 -->
      <n-alert v-if="!apiRow?.api_id" :bordered="false" type="info">
        请先保存接口后再使用数据源（数据源归属当前接口，施压时按场景轮询替换报文占位符）。
      </n-alert>

      <div v-else class="data-source-content">
        <n-space vertical :size="12">
          <!-- 矩阵方向（对齐 StepDataSourcePanel） -->
          <div class="data-source-axis-row">
            <span class="data-source-axis-label">矩阵方向：</span>
            <n-radio-group v-model:value="axis" size="small" @update:value="onAxisChange">
              <n-radio-button :value="1">垂直模式</n-radio-button>
              <n-radio-button :value="0">水平模式</n-radio-button>
            </n-radio-group>
            <n-text depth="3" class="data-source-axis-tip">
              {{ axis === 0 ? '场景为行、字段为列' : '场景为列、字段为行' }}
            </n-text>
            <n-text v-if="hasDbRecord" depth="3" class="data-source-axis-tip" style="margin-left: 16px;">
              {{ sceneCount }} 个场景
            </n-text>
          </div>

          <!-- 矩阵编辑区：右上「更多」下拉承载保存等操作（对齐 StepDataSourcePanel，无底部按钮行） -->
          <div class="luckysheet-wrap" :class="{ 'is-fullscreen': isFullscreen }">
            <div class="luckysheet-more-dropdown">
              <n-dropdown trigger="click" placement="bottom-end" :options="moreOptions" @select="onMoreSelect">
                <n-button size="tiny" quaternary>
                  更多
                  <TheIcon icon="material-symbols:arrow-drop-down" :size="16" />
                </n-button>
              </n-dropdown>
            </div>
            <input
                ref="uploadFileRef"
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                style="display: none"
                @change="onUploadFileChange"
            />
            <Luckysheet
                ref="luckysheetRef"
                :data="sheetData"
                :columns="sheetColumns"
                :protectedRowKeywords="FIXED_KEYWORDS"
                @change="onSheetChange"
                @protectedAction="onProtectedAction"
            />
          </div>
        </n-space>
      </div>
    </n-collapse-transition>
  </n-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  NAlert, NButton, NCard, NCollapseTransition, NDropdown,
  NRadioButton, NRadioGroup, NSpace, NText, NTooltip,
} from 'naive-ui'

import TheIcon from '@/components/icon/TheIcon.vue'
import Luckysheet from '@/components/common/Luckysheet.vue'
import api from '@/api'
import { downloadBlobResponse } from '@/utils/common/downloadFile'

defineOptions({ name: 'PerfApiDatasetPanel' })

const props = defineProps({
  /** 编辑中的接口行（api_id 落库后才有值） */
  apiRow: { type: Object, default: null },
})

// 分区标记与后端 autotest 四分区解析器同一套词表（施压引擎只消费 HEAD/BODY 两分区）
const FIXED_KEYWORDS = ['HEAD', 'BODY', 'ASSERT_HEAD', 'ASSERT_BODY']

// 矩阵方向：1=垂直(场景为列)，0=水平(场景为行)，与后端 axis 字段一致；空白模板默认垂直
const AXIS_HORIZONTAL = 0
const AXIS_VERTICAL = 1

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
// 默认折叠（对齐步骤编辑页 DataSource 卡），展开时才按需加载数据源
const collapsed = ref(true)
/** 接口绑定的数据源（一个接口只能有一个数据源） */
const dataSource = ref(null)
/** 表格有未保存修改（切换/重置前据此确认丢弃） */
const isDirty = ref(false)
/** 上传解析的文件溯源（保存时随 create/update 落库） */
const uploadedFileInfo = ref(null)

/** 数据源是否已落库（后端返回 ds_id 而非 id） */
const hasDbRecord = computed(() => Boolean(dataSource.value?.ds_id))
/** 场景数量 */
const sceneCount = computed(() => (dataSource.value?.dataset_names || []).length)

/** 折叠态提示文案（对齐 StepDataSourcePanel 的 tip 口径） */
const collapsedTip = computed(() => {
  if (!props.apiRow?.api_id) return '请先保存接口后再使用数据源'
  const name = String(props.apiRow.api_name || '').trim()
  if (hasDbRecord.value) {
    return `${name} - ${sceneCount.value} 个场景`
  }
  return `${name} - 数据驱动文件上传或在线编辑`
})

/** 「更多」下拉：12 项结构与文案逐字对齐 StepDataSourcePanel（同步/导出/解绑仅对已落库数据源可用） */
const moreOptions = computed(() => {
  const canUse = Boolean(props.apiRow?.api_id);
  console.log(canUse);
  return [
    { label: '撤销', key: 'undo', disabled: !canUse },
    { label: '重做', key: 'redo', disabled: !canUse },
    { type: 'divider', key: 'd1' },
    { label: '导入数据源', key: 'import', disabled: !canUse || uploading.value },
    { label: '导出数据源', key: 'export', disabled: !canUse || !hasDbRecord.value || exportLoading.value },
    { label: '保存数据源', key: 'save', disabled: !canUse || saving.value || uploading.value },
    { label: '同步报文字段', key: 'syncFields', disabled: !canUse || !hasDbRecord.value || syncFieldsLoading.value },
    { label: '导入正交易场景', key: 'importNormalScene', disabled: !canUse },
    { label: '数据源模板下载', key: 'templateDownload', disabled: !canUse || templateDownloadLoading.value },
    { type: 'divider', key: 'd2' },
    { label: isFullscreen.value ? '退出全屏' : '全屏', key: 'fullscreen' },
    { label: '解绑', key: 'unbind', disabled: !canUse || !hasDbRecord.value || unbindLoading.value },
  ]
})

// ---------- 矩阵工具（与 StepDataSourcePanel 的 sheet↔matrix 约定一致） ----------

const luckysheetRef = ref(null)
const sheetColumns = ref([])
const sheetData = ref([])
const axis = ref(AXIS_VERTICAL)

const isSectionMarker = (value) => {
  const text = value == null ? '' : String(value).trim().toUpperCase()
  return FIXED_KEYWORDS.includes(text)
}

/** 按分区标记识别矩阵方向，避免沿用默认 axis 误判 */
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

/** 空白模板：首行场景名 + 四个分区标记行（新场景默认「场景N」递增） */
const buildBlankMatrix = (sceneCount = 1) => {
  const sceneNames = Array.from({ length: sceneCount }, (_, i) => `场景${i + 1}`)
  return [
    ['', ...sceneNames],
    ...FIXED_KEYWORDS.map((kw) => [kw, ...sceneNames.map(() => '')]),
  ]
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
  const effective = Array.isArray(matrix) && matrix.length ? matrix : buildBlankMatrix()
  const maxCol = Math.max(...effective.map((row) => (Array.isArray(row) ? row.length : 0)))
  sheetColumns.value = normalizeHeaderRow(effective[0], maxCol)
  sheetData.value = effective.slice(1).map((row) => padTypedRow(row, maxCol))
}

/** 当前表格内容 → 二维矩阵（Luckysheet 未就绪时返回空） */
const getCurrentMatrix = () => {
  if (luckysheetRef.value?.getDataForSave) {
    const { headers = [], rows = [] } = luckysheetRef.value.getDataForSave() || {}
    const maxCol = headers.length
    if (maxCol > 0) {
      return [normalizeHeaderRow(headers, maxCol), ...rows.map((row) => padTypedRow(row, maxCol))]
    }
  }
  return []
}

const onProtectedAction = (action) => {
  if (action === 'delete') {
    window.$message?.warning('HEAD/BODY/ASSERT_HEAD/ASSERT_BODY 所在行不允许删除')
  }
}

const onSheetChange = () => {
  isDirty.value = true
}

/** 切换矩阵方向：将当前表格内容转置到目标方向（axis 已由 v-model 更新） */
const onAxisChange = () => {
  const matrix = getCurrentMatrix()
  applyMatrixToSheet(matrix.length >= 2 ? transposeMatrix(matrix) : buildBlankMatrix())
  isDirty.value = true
}

/** 有未保存修改时先确认丢弃（对齐 autotest 数据不丢语义） */
const confirmDiscardIfDirty = (onConfirm) => {
  if (!isDirty.value) {
    onConfirm()
    return
  }
  window.$dialog?.warning({
    title: '放弃未保存修改',
    content: '当前数据源矩阵有未保存的修改，继续将丢弃这些修改',
    positiveText: '放弃修改',
    negativeText: '留在本页',
    onPositiveClick: () => onConfirm(),
  })
}

// ---------- 数据源加载 ----------

/** 报文原始值映射（HEAD/BODY 分区 → 字段路径 → 原始值），供正交易场景列回填（与 /build 同源返回） */
const reportOriginals = ref({})
const exportLoading = ref(false)
const syncFieldsLoading = ref(false)
const templateDownloadLoading = ref(false)
const unbindLoading = ref(false)

/** 加载接口绑定的数据源（一个接口只能有一个数据源） */
async function loadDataSource() {
  if (!props.apiRow?.api_id) {
    dataSource.value = null
    return
  }
  loading.value = true
  try {
    const res = await api.listPerfDatasetsForApi({ api_id: props.apiRow.api_id })
    // 后端已按 bind_api_id 过滤，直接取第一条
    const rows = res.data || []
    const dsRow = rows.length > 0 ? rows[0] : null
    if (dsRow?.ds_id) {
      // 加载详情（含矩阵数据）
      const detailRes = await api.getPerfDataset({ ds_id: dsRow.ds_id })
      dataSource.value = detailRes.data || null
      const matrix = Array.isArray(dataSource.value?.dataframe) ? dataSource.value.dataframe : []
      axis.value = detectAxisFromMatrix(matrix)
      applyMatrixToSheet(matrix)
      // 已落库数据源: 加载报文原始值映射供正交易场景回填
      await fetchReportOriginals()
    } else {
      dataSource.value = null
      // 未绑定数据源，按接口报文推导矩阵模板
      applyMatrixToSheet(await fetchReportTemplate())
    }
    uploadedFileInfo.value = null
    isDirty.value = false
  } catch (e) {
    dataSource.value = null
    applyMatrixToSheet(buildBlankMatrix())
  } finally {
    loading.value = false
  }
}

/** 按接口报文推导矩阵模板（HEAD/BODY 分区预填 path key）；未落库或失败回落空白模板；缓存报文原始值供正交易场景回填 */
async function fetchReportTemplate() {
  if (!props.apiRow?.api_id) return buildBlankMatrix()
  try {
    const res = await api.buildPerfApiMatrix({ api_id: props.apiRow.api_id })
    reportOriginals.value = res.data?.data_original && typeof res.data.data_original === 'object' ? res.data.data_original : {}
    const matrix = Array.isArray(res.data?.dataframe) ? res.data.dataframe : []
    return matrix.length ? matrix : buildBlankMatrix()
  } catch (e) {
    return buildBlankMatrix()
  }
}

/** 仅加载报文原始值映射（供正交易场景回填，不返回矩阵） */
async function fetchReportOriginals() {
  if (!props.apiRow?.api_id) return
  try {
    const res = await api.buildPerfApiMatrix({ api_id: props.apiRow.api_id })
    reportOriginals.value = res.data?.data_original && typeof res.data.data_original === 'object' ? res.data.data_original : {}
  } catch (e) {
    reportOriginals.value = {}
  }
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  // 展开时加载数据源
  if (!collapsed.value && props.apiRow?.api_id) {
    loadDataSource()
  }
}

// ---------- 「更多」下拉动作 ----------

const uploadFileRef = ref(null)

function onMoreSelect(key) {
  if (key === 'undo') {
    luckysheetRef.value?.getLuckysheet()?.undo?.()
    return
  }
  if (key === 'redo') {
    luckysheetRef.value?.getLuckysheet()?.redo?.()
    return
  }
  if (key === 'import') {
    uploadFileRef.value?.click()
    return
  }
  if (key === 'export') {
    handleExport()
    return
  }
  if (key === 'save') {
    handleSave()
    return
  }
  if (key === 'syncFields') {
    handleSyncFields()
    return
  }
  if (key === 'importNormalScene') {
    handleImportNormalScene()
    return
  }
  if (key === 'templateDownload') {
    handleTemplateDownload()
    return
  }
  if (key === 'fullscreen') {
    toggleFullscreen()
    return
  }
  if (key === 'unbind') {
    handleUnbind()
  }
}

async function onUploadFileChange(event) {
  const input = event.target
  const file = input?.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    // ds_project 随接口所属应用(request_project_id)，缺省回落后端默认值 1
    fd.append('ds_project', String(props.apiRow.request_project_id || 1))
    fd.append('file', file)
    const res = await api.uploadPerfDataset(fd)
    applyParsedFile(res?.data || {})
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    uploading.value = false
  }
}

/** 解析预览 → 矩阵回填 + 文件溯源（场景数据 dataset/dataset_names 由保存期服务端重新派生） */
function applyParsedFile(parsed) {
  const matrix = Array.isArray(parsed.dataframe) ? parsed.dataframe : []
  if (!matrix.length) {
    window.$message?.warning('解析结果为空，请检查文件内容')
    return
  }
  axis.value = parsed.axis ?? detectAxisFromMatrix(matrix)
  applyMatrixToSheet(matrix)
  uploadedFileInfo.value = {
    file_name: parsed.file_name || null,
    file_path: parsed.file_path || null,
    file_hash: parsed.file_hash || null,
  }
  isDirty.value = true
  window.$message?.success('解析成功，请确认矩阵后保存')
}

// ---------- 保存与删除 ----------

/** 矩阵有效性校验（与后端解析口径一致：至少一个场景列 + 至少一条字段行） */
function validateMatrix(matrix) {
  if (matrix.length < 2) {
    window.$message?.error('请先在线编辑数据矩阵或上传文件解析')
    return false
  }
  const hasScene = matrix[0].some((cell, index) => index > 0 && String(cell || '').trim())
  if (!hasScene) {
    window.$message?.error('矩阵缺少场景名（垂直模式在首行、水平模式在首列）')
    return false
  }
  const hasData = matrix.slice(1).some((row) => row.some((cell, index) => index > 0 && cell != null && cell !== ''))
  if (!hasData) {
    window.$message?.error('矩阵没有任何字段取值（空白矩阵在施压期只会产出假结果）')
    return false
  }
  return true
}

async function handleSave() {
  const matrix = getCurrentMatrix()
  if (!validateMatrix(matrix)) return
  saving.value = true
  try {
    // 按 bind_api_id upsert（一个接口只能有一个数据源）
    const payload = {
      ds_project: props.apiRow.request_project_id || 1,
      bind_api_id: props.apiRow.api_id,
      dataframe: matrix,
      axis: detectAxisFromMatrix(matrix),
    }
    if (uploadedFileInfo.value) {
      payload.ds_source = 'file'
      payload.file_name = uploadedFileInfo.value.file_name
      payload.file_path = uploadedFileInfo.value.file_path
      payload.file_hash = uploadedFileInfo.value.file_hash
    }
    // 使用 create 接口（后端按 bind_api_id upsert）
    const res = await api.createPerfDataset(payload)
    uploadedFileInfo.value = null
    isDirty.value = false
    window.$message?.success('保存成功')
    // 重新加载数据源
    await loadDataSource()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

/** 导出当前接口绑定的数据源（blob 下载，sheet 名为数据源名称） */
async function handleExport() {
  if (exportLoading.value) return
  if (!hasDbRecord.value) {
    window.$message?.warning('请先保存数据源')
    return
  }
  exportLoading.value = true
  try {
    const res = await api.downloadPerfDataset({ ds_id: dataSource.value.ds_id })
    const name = String(dataSource.value?.ds_name || props.apiRow?.api_name || '数据源').trim()
    await downloadBlobResponse(res, `${name}.xlsx`)
    window.$message?.success('导出成功')
  } catch (e) {
    window.$message?.error(`导出失败：${e?.message || e}`)
  } finally {
    exportLoading.value = false
  }
}

/** 同步报文字段：以接口当前报文为基准增删字段路径（保留字段值不动）；未保存编辑先确认 */
async function handleSyncFields() {
  if (syncFieldsLoading.value) return
  if (!hasDbRecord.value) {
    window.$message?.warning('请先保存数据源')
    return
  }
  if (isDirty.value) {
    // 同步以已落库数据为基准，先确认避免静默覆盖未保存编辑
    const goOn = await new Promise((resolve) => {
      window.$dialog?.confirm?.({
        title: '同步报文字段',
        type: 'warning',
        content: '当前表格有未保存的编辑，同步将以已保存的数据为准并覆盖当前编辑。是否继续？',
        positiveText: '继续同步',
        negativeText: '先不同步',
        confirm: () => resolve(true),
        cancel: () => resolve(false),
      }) ?? resolve(true)
    })
    if (!goOn) return
  }
  syncFieldsLoading.value = true
  try {
    // 使用新的 update_fields 接口（只需 api_id）
    const res = await api.updatePerfDatasetFields({ api_id: props.apiRow.api_id })
    window.$message?.success(res?.message || '字段同步成功')
    await loadDataSource()
    // 接口报文可能已变化，顺带刷新原始值映射供正交易场景回填（只读不落库）
    fetchReportTemplate()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    syncFieldsLoading.value = false
  }
}

/** 按接口报文下载数据源模板（HEAD/BODY 分区 path key 字段行，值留空） */
async function handleTemplateDownload() {
  if (templateDownloadLoading.value) return
  if (!props.apiRow?.api_id) {
    window.$message?.warning('请先保存接口后再下载模板')
    return
  }
  templateDownloadLoading.value = true
  try {
    const res = await api.downloadPerfApiTemplate({ api_id: props.apiRow.api_id })
    await downloadBlobResponse(res, '数据源导出模板.xlsx')
    window.$message?.success('下载成功')
  } catch (e) {
    window.$message?.error(`下载失败：${e?.message || e}`)
  } finally {
    templateDownloadLoading.value = false
  }
}

/* ============ 导入正交易场景（本地插入，随保存落库；与 StepDataSourcePanel 同款纯函数） ============ */
const NORMAL_SCENE_NAME = '正交易场景'

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

/** 在矩阵第2列(垂直)/第2行(水平)插入正交易场景：HEAD/BODY字段按所属分区取报文原始值(隔离同名字段)，其余填空；插入值全空时返回 null */
const insertNormalSceneIntoMatrix = (matrix, originals) => {
  const valueOf = (path, section) => {
    const value = (originals?.[section] || {})[path]
    return value === undefined || value === null ? '' : value
  }
  const newMatrix = matrix.map((row) => [...(row || [])])
  const insertedValues = []
  if (detectAxisFromMatrix(matrix) === AXIS_HORIZONTAL) {
    // 水平：第0行为分区标记+字段名行，新场景行固定在第2行，原有场景行整体下移
    const header = newMatrix[0] || []
    const sceneRow = [NORMAL_SCENE_NAME]
    let section = ''
    for (let c = 1; c < header.length; c++) {
      const cell = header[c] == null ? '' : String(header[c]).trim()
      if (isSectionMarker(cell)) {
        section = cell.toUpperCase()
        sceneRow.push('')
        continue
      }
      const value = (section === 'HEAD' || section === 'BODY') && cell ? valueOf(cell, section) : ''
      insertedValues.push(value)
      sceneRow.push(value)
    }
    newMatrix.splice(1, 0, sceneRow)
  } else {
    // 垂直：第0行为场景名行，新场景列固定在第2列，原有场景列整体右移
    let section = ''
    newMatrix.forEach((row, rowIndex) => {
      const cell = row[0] == null ? '' : String(row[0]).trim()
      if (rowIndex === 0) {
        row.splice(1, 0, NORMAL_SCENE_NAME)
        return
      }
      if (isSectionMarker(cell)) {
        section = cell.toUpperCase()
        row.splice(1, 0, '')
        return
      }
      const value = (section === 'HEAD' || section === 'BODY') && cell ? valueOf(cell, section) : ''
      insertedValues.push(value)
      row.splice(1, 0, value)
    })
  }
  if (!insertedValues.some((value) => value !== '' && String(value).trim() !== '')) return null
  return newMatrix
}

const handleImportNormalScene = () => {
  if (!props.apiRow?.api_id) {
    window.$message?.warning('请先保存接口后再导入正交易场景')
    return
  }
  // 以当前表格内容(含未保存编辑)为插入基准，随保存链路统一落库
  const matrix = getCurrentMatrix()
  if (!Array.isArray(matrix) || matrix.length < 2) {
    window.$message?.warning('当前没有可用字段，无法导入正交易场景')
    return
  }
  if (extractSceneNamesFromMatrix(matrix).includes(NORMAL_SCENE_NAME)) {
    window.$message?.warning('该接口已存在名称为"正交易场景"的测试数据，无法导入')
    return
  }
  const nextMatrix = insertNormalSceneIntoMatrix(matrix, reportOriginals.value || {})
  if (!nextMatrix) {
    window.$message?.warning('报文字段与数据源矩阵不匹配，正交易场景无可用数据')
    return
  }
  applyMatrixToSheet(nextMatrix)
  isDirty.value = true
  window.$message?.success('正交易场景已插入，保存后生效')
}

/* ============ 全屏（CSS 铺满页面窗口，与 StepDataSourcePanel 同款三段实现） ============ */
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

onMounted(() => {
  document.addEventListener('keydown', onFullscreenKeydown, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onFullscreenKeydown, true)
  document.body.classList.remove(BODY_FULLSCREEN_CLASS)
})

/** 解绑：硬删当前接口绑定的数据源并回到新增形态（对齐 autotest 解绑语义） */
async function handleUnbind() {
  if (unbindLoading.value) return
  if (!hasDbRecord.value) {
    window.$message?.warning('当前接口未绑定数据源')
    return
  }
  unbindLoading.value = true
  try {
    await api.deletePerfDataset({ ds_id: dataSource.value.ds_id })
    dataSource.value = null
    applyMatrixToSheet(buildBlankMatrix())
    isDirty.value = false
    window.$message?.success('解绑成功')
  } catch (e) {
    window.$message?.error('解绑失败：' + (e?.message || ''))
  } finally {
    unbindLoading.value = false
  }
}

// 接口落库后（api_id 从无到有）自动加载数据源
watch(() => props.apiRow?.api_id, (val) => {
  if (val) {
    loadDataSource()
  } else {
    dataSource.value = null
    applyMatrixToSheet(buildBlankMatrix())
  }
}, { immediate: true })
</script>

<style scoped>
/* 卡片壳/标题/折叠见 styles/autotest-theme.scss .step-editor-card；行规格与 Luckysheet 容器对齐 StepDataSourcePanel */

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 折叠态右侧提示词预留空间（对齐 StepDataSourcePanel） */
.card-header-row--with-actions {
  padding-right: 220px;
}

.panel-title-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
}

.panel-collapse-icon {
  cursor: pointer;
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

.data-source-axis-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.data-source-axis-label {
  font-size: 12px;
  flex-shrink: 0;
}

.data-source-axis-tip {
  font-size: 12px;
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
