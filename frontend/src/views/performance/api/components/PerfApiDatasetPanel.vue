<!--
  PerfApiDatasetPanel — 压测接口参数化数据集卡（接口编辑页内联数据源管理）

  数据集归属锁定当前接口（bind_api_id 随接口落库，用户无需再选归属）；
  矩阵编辑交互对齐 autotest StepDataSourcePanel（分区标记行 + 垂直/水平转置），
  上传解析复用 /perf/dataset/upload（autotest 四分区解析器），保存走 dataframe+axis 矩阵协议。
-->
<template>
  <n-card size="small">
    <template #header>
      <n-space align="center" :size="8">
        <span class="card-title">参数化数据集</span>
        <n-tag v-if="!editingMode" size="small" type="info" :bordered="false">{{ datasets.length }} 个</n-tag>
      </n-space>
    </template>
    <template #header-extra>
      <n-button v-if="!editorVisible && apiRow?.api_id" size="small" type="primary" @click="openCreate">
        新增数据集
      </n-button>
    </template>

    <!-- 接口未落库：数据集必须归属接口，先保存接口 -->
    <n-alert v-if="!apiRow?.api_id" :bordered="false" type="info">
      请先保存接口后再管理参数化数据集（数据集归属当前接口，施压时按场景轮询替换报文占位符）。
    </n-alert>

    <!-- 列表态 -->
    <template v-else-if="!editorVisible">
      <n-empty v-if="!datasets.length && !loading" description="暂无数据集，点击右上角「新增数据集」在线编辑或上传文件" class="py-40" />
      <n-data-table
          v-else
          :columns="dsColumns"
          :data="datasets"
          :loading="loading"
          :pagination="false"
          :max-height="360"
          size="small"
          :scroll-x="640"
      />
      <n-text depth="3" style="font-size: 12px; display: block; margin-top: 8px">
        场景列中的字段路径（如 $.data.token、./Order/@no）在施压期替换请求报文中的同名占位符；HEAD/BODY 行分别对应请求头与请求体。
      </n-text>
    </template>

    <!-- 编辑态：矩阵在线编辑 / 上传解析回填 -->
    <template v-else>
      <n-form label-placement="left" label-width="96" size="small">
        <n-grid :cols="24" :x-gap="12">
          <n-gi :span="10">
            <n-form-item label="数据集名称" :show-feedback="false">
              <n-input v-model:value="dsForm.ds_name" placeholder="请输入数据集名称" clearable />
            </n-form-item>
          </n-gi>
          <n-gi :span="14">
            <n-form-item label="数据集描述" :show-feedback="false">
              <n-input v-model:value="dsForm.ds_desc" placeholder="数据集描述（可选）" clearable />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>

      <n-space align="center" :size="12" style="margin: 8px 0">
        <span class="axis-label">矩阵方向：</span>
        <n-radio-group v-model:value="axis" size="small" @update:value="onAxisChange">
          <n-radio-button :value="1">垂直模式</n-radio-button>
          <n-radio-button :value="0">水平模式</n-radio-button>
        </n-radio-group>
        <n-text depth="3" style="font-size: 12px">
          {{ axis === 0 ? '场景为行、字段为列' : '场景为列、字段为行' }}
        </n-text>
        <n-space :size="8" style="margin-left: auto">
          <n-button size="small" :loading="uploading" @click="triggerUpload">上传 xlsx</n-button>
          <n-popconfirm @positive-click="applyBlankTemplate">
            <template #trigger>
              <n-button size="small">重置模板</n-button>
            </template>
            确认清空当前矩阵并重置为空白模板？
          </n-popconfirm>
        </n-space>
      </n-space>

      <div class="luckysheet-wrap">
        <Luckysheet
            ref="luckysheetRef"
            :data="sheetData"
            :columns="sheetColumns"
            :readonly="false"
            :protectedRowKeywords="FIXED_KEYWORDS"
            @protectedAction="onProtectedAction"
        />
      </div>

      <n-space justify="end" style="margin-top: 12px">
        <n-button @click="closeEditor">返 回</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">保 存</n-button>
      </n-space>
    </template>
  </n-card>

  <!-- 上传解析：结果仅回填矩阵预览，保存时随 create/update 落库并留文件溯源 -->
  <input
      ref="uploadFileRef"
      type="file"
      accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      style="display: none"
      @change="onUploadFileChange"
  />
</template>

<script setup>
import { h, reactive, ref, watch } from 'vue'
import {
  NAlert, NButton, NCard, NDataTable, NEmpty, NForm, NFormItem, NGi, NGrid, NInput,
  NPopconfirm, NRadioButton, NRadioGroup, NSpace, NTag, NText,
} from 'naive-ui'

import Luckysheet from '@/components/common/Luckysheet.vue'
import { formatDateTime } from '@/utils'
import api from '@/api'

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
/** 该接口可用数据集（归属当前接口） */
const datasets = ref([])

// ---------- 矩阵编辑状态（对齐 StepDataSourcePanel 的 sheet↔matrix 约定） ----------

const luckysheetRef = ref(null)
const sheetColumns = ref([])
const sheetData = ref([])
const axis = ref(AXIS_VERTICAL)

/** 编辑中的数据集ID；null 表示新增 */
const editingId = ref(null)
/** 编辑态开关（列表态/编辑态切换） */
const editorVisible = ref(false)
/** 上传解析的文件溯源（保存时随 create/update 落库） */
const uploadedFileInfo = ref(null)

const dsForm = reactive({ ds_name: null, ds_desc: null })

const DS_SOURCE_LABELS = { manual: '手动录入', file: '文件导入', job: '数据作业' }

const dsColumns = [
  { title: '数据集名称', key: 'ds_name', minWidth: 160, ellipsis: { tooltip: true } },
  {
    title: '场景数', key: 'scene_count', width: 80,
    render: (row) => (row.dataset_names || []).length,
  },
  {
    title: '来源', key: 'ds_source', width: 90,
    render: (row) => DS_SOURCE_LABELS[row.ds_source] || row.ds_source || '-',
  },
  {
    title: '更新时间', key: 'updated_time', width: 160,
    render: (row) => (row.updated_time ? formatDateTime(row.updated_time) : '-'),
  },
  {
    title: '操作', key: 'actions', width: 120,
    render: (row) => h(NSpace, { size: 4, wrap: false }, {
      default: () => [
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => openEdit(row) },
            { default: () => '编辑' }),
        h(NButton, {
          size: 'tiny', type: 'error', secondary: true,
          onClick: () => handleDelete(row),
        }, { default: () => '删除' }),
      ],
    }),
  },
]

// ---------- 矩阵工具（复制 StepDataSourcePanel 的列头/数据行约定） ----------

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

/** 当前表格内容 → 二维矩阵（Luckysheet 未就绪时回落到已载入状态） */
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

/** 切换矩阵方向：将当前表格内容转置到目标方向（axis 已由 v-model 更新） */
const onAxisChange = () => {
  const matrix = getCurrentMatrix()
  applyMatrixToSheet(matrix.length >= 2 ? transposeMatrix(matrix) : buildBlankMatrix())
}

const applyBlankTemplate = () => {
  axis.value = AXIS_VERTICAL
  uploadedFileInfo.value = null
  applyMatrixToSheet(buildBlankMatrix())
}

// ---------- 列表与编辑器 ----------

async function loadDatasets() {
  if (!props.apiRow?.api_id) {
    datasets.value = []
    return
  }
  loading.value = true
  try {
    const res = await api.listPerfDatasetsForApi({ api_id: props.apiRow.api_id })
    datasets.value = (res.data || []).filter((row) => row.bind_api_id === props.apiRow.api_id)
  } catch (e) {
    datasets.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  dsForm.ds_name = null
  dsForm.ds_desc = null
  uploadedFileInfo.value = null
  axis.value = AXIS_VERTICAL
  applyMatrixToSheet(buildBlankMatrix())
  editorVisible.value = true
}

function openEdit(row) {
  loading.value = true
  api.getPerfDataset({ ds_id: row.id }).then((res) => {
    const detail = res.data || {}
    editingId.value = row.id
    dsForm.ds_name = detail.ds_name
    dsForm.ds_desc = detail.ds_desc
    uploadedFileInfo.value = null
    axis.value = detectAxisFromMatrix(detail.dataframe)
    applyMatrixToSheet(detail.dataframe)
    editorVisible.value = true
  }).catch(() => {}).finally(() => {
    loading.value = false
  })
}

function closeEditor() {
  editorVisible.value = false
  editingId.value = null
}

// ---------- 上传解析 ----------

const uploadFileRef = ref(null)

function triggerUpload() {
  uploadFileRef.value?.click()
}

async function onUploadFileChange(event) {
  const input = event.target
  const file = input?.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('ds_project', String(props.apiRow.api_project))
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
  const name = String(dsForm.ds_name || '').trim()
  if (!name) {
    window.$message?.error('请输入数据集名称')
    return
  }
  const matrix = getCurrentMatrix()
  if (!validateMatrix(matrix)) return
  saving.value = true
  try {
    const payload = {
      ds_project: props.apiRow.api_project,
      ds_name: name,
      ds_desc: String(dsForm.ds_desc || '').trim() || null,
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
    if (editingId.value) {
      await api.updatePerfDataset({ ds_id: editingId.value, ...payload })
    } else {
      await api.createPerfDataset(payload)
    }
    window.$message?.success('保存成功')
    closeEditor()
    await loadDatasets()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  window.$dialog?.warning({
    title: '删除确认',
    content: `确认删除数据集「${row.ds_name}」？已被场景引用时删除会被拒绝。`,
    positiveText: '删 除',
    negativeText: '取 消',
    onPositiveClick: async () => {
      try {
        await api.deletePerfDataset({ ds_id: row.id })
        window.$message?.success('删除成功')
        await loadDatasets()
      } catch (e) {
        /* 拦截器已提示 */
      }
    },
  })
}

// 接口落库后（api_id 从无到有）自动加载归属数据集
watch(() => props.apiRow?.api_id, (val) => {
  if (val) loadDatasets()
  else datasets.value = []
}, { immediate: true })
</script>

<style scoped>
.card-title {
  font-weight: 600;
}

.axis-label {
  font-size: 13px;
}

.luckysheet-wrap {
  height: 360px;
}
</style>
