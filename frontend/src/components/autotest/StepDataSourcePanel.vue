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
              <div class="data-source-toolbar-row">
                <n-space>
                  <n-button
                      size="small"
                      type="primary"
                      :disabled="props.readonly"
                      :loading="downloadStepDataTemplateLoading"
                      @click="downloadStepDataTemplate"
                  >导入模板下载</n-button>
                </n-space>
                <n-space>
                  <n-button
                      size="small"
                      type="warning"
                      :disabled="props.readonly"
                      :loading="dataSourceImportLoading"
                      @click="dataSourceImport"
                  >导入
                    <input
                        ref="dataSourceImportFileInputRef"
                        type="file"
                        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        style="display: none"
                        @change="onDataSourceImportFileChange"
                    /></n-button>
                  <n-button size="small" type="info" :disabled="props.readonly" :loading="dataSourceExportLoading" @click="dataSourceExport">导出</n-button>
                  <n-button size="small" type="error" :disabled="props.readonly" @click="dataSourceDelete">删除</n-button>
                  <n-button
                      size="small"
                      type="success"
                      :disabled="props.readonly"
                      :loading="dataSourceSaveLoading"
                      @click="dataSourceSave"
                  >保存</n-button>
                </n-space>
              </div>
              <n-data-table
                  :row-key="dataSourcePreviewRowKey"
                  :checked-row-keys="dataSourcePreviewKeysRef"
                  @update:checked-row-keys="dataSourcePreviewHandleCheck"
                  :columns="dataSourcePreviewColumns"
                  :data="dataSource.previewRows"
                  :row-class-name="dataSourcePreviewRowClassName"
                  :bordered="false"
                  :scroll-x="dataSourcePreviewScrollX"
                  size="small"
              />
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
                  <n-button size="small" type="primary" tertiary :disabled="props.readonly"
                            @click="downloadApiDocTemplate">数据模板
                  </n-button>
                </n-space>
              </div>

              <div class="data-source-subtitle">数据校验点</div>
              <n-checkbox-group v-model:value="dataSource.validationPoints" :disabled="props.readonly">
                <n-space>
                  <n-checkbox value="required">必输性</n-checkbox>
                  <n-checkbox value="length">字段长度</n-checkbox>
                  <n-checkbox value="length">类型</n-checkbox>
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

import { computed, h, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCollapseTransition,
  NDataTable,
  NInput,
  NModal,
  NPopover,
  NSpace,
  NTabPane,
  NTabs,
  NText,
  NTooltip,
  NUpload,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const props = defineProps({
  step: { type: Object, default: () => ({}) },
  readonly: { type: Boolean, default: false },
  /** 步骤名称，用于折叠态 tip */
  stepName: { type: String, default: '' },
  /** 无名称时的类型文案，如「HTTP请求」「TCP请求」 */
  stepTypeLabel: { type: String, default: '请求' },
  dataSourceName: { type: String, default: '' },
  dataSourceDesc: { type: String, default: '' },
})

const emit = defineEmits(['update:dataSourceName', 'update:dataSourceDesc'])

const route = useRoute()

const dataSourceName = computed({
  get: () => props.dataSourceName,
  set: (v) => emit('update:dataSourceName', v),
})
const dataSourceDesc = computed({
  get: () => props.dataSourceDesc,
  set: (v) => emit('update:dataSourceDesc', v),
})

const dataSourceCollapsed = ref(true)
const toggleDataSourceCollapsed = () => {
  const wasCollapsed = dataSourceCollapsed.value
  dataSourceCollapsed.value = !dataSourceCollapsed.value
  if (wasCollapsed && !dataSourceCollapsed.value) {
    loadStepDataframePreview()
  }
}

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

const ts = () => new Date().toISOString().slice(0, 19).replace('T', ' ')
const dataSource = reactive({
  apiDocFileName: '',
  validationPoints: [],
  previewRows: [],
  generatedRows: [
    {id: 'gen-1', name: '生成数据1', remark: '备注1', generatedAt: ts()},
    {id: 'gen-2', name: '生成数据2', remark: '备注2', generatedAt: ts()},
    {id: 'gen-3', name: '生成数据3', remark: '备注3', generatedAt: ts()}
  ]
})

const dataSourceEditModalVisible = ref(false)
const dataSourceEditForm = reactive({rowKey: null, type: 'generated', cells: []})
const previewEditingCell = reactive({
  rowKey: null,
  colKey: '',
  originalValue: ''
})

/** DataSource「数据生成」行编辑（当前仅占位打开弹窗，字段编辑后续接入） */
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
  const list = type === 'generated' ? dataSource.generatedRows : dataSource.previewRows
  const idx = list.findIndex((x) => x.id === row?.id)
  if (idx >= 0) {
    list.splice(idx, 1)
    $message.success('已删除')
  }
}

const buildPreviewTableRowsByMatrix = (matrix) => {
  const safeMatrix = Array.isArray(matrix) ? matrix : []
  return safeMatrix.map((line, rowIndex) => {
    const rowObj = {__rowKey: String(rowIndex + 1), __rowNo: rowIndex + 1}
    const cells = Array.isArray(line) ? line : []
    cells.forEach((val, colIndex) => {
      rowObj[`c_${colIndex + 1}`] = val
    })
    return rowObj
  })
}

const isLockedKeywordRow = (row) => {
  const v = String(row?.c_1 ?? '').trim().toUpperCase()
  return v === 'HEAD' || v === 'BODY' || v === 'ASSERT_HEAD' || v === 'ASSERT_BODY'
}

const isProtectedPreviewRow = (row) => {
  // 第一行是字段名称行，固定保护；关键字行也保护
  return Number(row?.__rowNo || 0) === 1 || isLockedKeywordRow(row)
}

const renumberPreviewRows = () => {
  dataSource.previewRows = (dataSource.previewRows || []).map((row, idx) => ({
    ...row,
    __rowKey: String(idx + 1),
    __rowNo: idx + 1,
  }))
}

/** 将数据预览表格行转为后端 dataframe 二维矩阵（c_1..c_n → 每行数组，空单元为 null）。 */
const previewRowsToDataframeMatrix = (rows) => {
  const list = Array.isArray(rows) ? rows : []
  let maxCol = 0
  list.forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) {
        const n = Number(k.slice(2))
        if (Number.isFinite(n) && n > maxCol) maxCol = n
      }
    })
  })
  if (maxCol === 0) return []
  return list.map((row) => {
    const line = []
    for (let j = 1; j <= maxCol; j++) {
      const key = `c_${j}`
      const v = row[key]
      if (v === '' || v === undefined) line.push(null)
      else line.push(v)
    }
    return line
  })
}

/** 预览矩阵当前最大列序号（c_1 → 1），无数据列为 0 */
const getMaxPreviewColumnIndex = (rows) => {
  let max = 0
  for (const row of rows || []) {
    for (const k of Object.keys(row || {})) {
      if (k.startsWith('c_')) {
        const n = Number(k.slice(2))
        if (Number.isFinite(n) && n > max) max = n
      }
    }
  }
  return max
}

const buildPreviewColumnsByRows = (rows) => {
  const colSet = new Set()
  ;(rows || []).forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) colSet.add(k)
    })
  })
  const colKeys = Array.from(colSet).sort((a, b) => Number(a.slice(2)) - Number(b.slice(2)))
  const dynamicCols = []
  for (const colKey of colKeys) {
    const colIndex = Number(colKey.slice(2)) || 0
    const col = {
      title: () => h(
          'div',
          {style: 'display:flex;align-items:center;justify-content:center;gap:4px;'},
          [
            h('span', null, `列${colIndex}`)
            ,
            colKey === 'c_1'
                ? null
                : h(NCheckbox, {
                  checked: dataSourcePreviewColumnKeysRef.value.includes(colKey),
                  disabled: props.readonly,
                  onUpdateChecked: (checked) => {
                    const set = new Set(dataSourcePreviewColumnKeysRef.value || [])
                    if (checked) {
                      set.add(colKey)
                    } else {
                      set.delete(colKey)
                    }
                    dataSourcePreviewColumnKeysRef.value = Array.from(set)
                  }
                })
          ]
      ),
      key: colKey,
      align: 'center',
      ellipsis: {tooltip: true},
      minWidth: 150,
      render: (row) => {
        const editing = previewEditingCell.rowKey === row.__rowKey && previewEditingCell.colKey === colKey
        if (editing) {
          return h(NInput, {
            value: row[colKey] == null ? '' : String(row[colKey]),
            autofocus: true,
            onUpdateValue: (v) => {
              row[colKey] = v
            },
            onBlur: () => {
              previewEditingCell.rowKey = null
              previewEditingCell.colKey = ''
              previewEditingCell.originalValue = ''
            },
            onKeydown: (e) => {
              if (e.key === 'Enter') {
                previewEditingCell.rowKey = null
                previewEditingCell.colKey = ''
                previewEditingCell.originalValue = ''
              } else if (e.key === 'Escape') {
                row[colKey] = previewEditingCell.originalValue
                previewEditingCell.rowKey = null
                previewEditingCell.colKey = ''
                previewEditingCell.originalValue = ''
              }
            }
          })
        }
        const raw = row[colKey]
        const isEmpty = raw == null || raw === ''
        const displayText = isEmpty ? '\u00a0' : String(raw)
        return h('div', {
          style: {
            minHeight: '28px',
            width: '100%',
            minWidth: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'text',
            boxSizing: 'border-box',
          },
          onDblclick: (e) => {
            e.stopPropagation()
            if (props.readonly) return
            previewEditingCell.rowKey = row.__rowKey
            previewEditingCell.colKey = colKey
            previewEditingCell.originalValue = isEmpty ? '' : String(raw)
          },
        }, displayText)
      }
    }
    if (colKey === 'c_1') {
      col.fixed = 'left'
    }
    dynamicCols.push(col)
  }
  return dynamicCols
}

/** 数据预览表横向滚动宽度：固定列 + 每列至少 150px + 末尾「新增列」列，列多时自动超出容器出现滚动条 */
const dataSourcePreviewScrollX = computed(() => {
  const PREVIEW_FIXED_COL_WIDTH = 20 + 20 + 50
  const PREVIEW_COL_ADD_WIDTH = 32
  const MIN_DYNAMIC_COL_WIDTH = 100
  const colSet = new Set()
  ;(dataSource.previewRows || []).forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) colSet.add(k)
    })
  })
  const n = colSet.size
  const content = PREVIEW_FIXED_COL_WIDTH + n * MIN_DYNAMIC_COL_WIDTH + PREVIEW_COL_ADD_WIDTH
  return Math.max(content, 1500)
})

const buildBlankPreviewRow = () => {
  const maxCol = getMaxPreviewColumnIndex(dataSource.previewRows || [])
  const blank = {}
  for (let j = 1; j <= maxCol; j++) {
    blank[`c_${j}`] = ''
  }
  return blank
}

/** 表头「+」：在右侧追加一列（所有行补齐新列；无任何行时插入一行作为表头行） */
const addPreviewColumn = (e) => {
  e?.stopPropagation?.()
  if (props.readonly) return
  let rows = [...(dataSource.previewRows || [])]
  if (rows.length === 0) {
    dataSource.previewRows = [{__rowKey: '1', __rowNo: 1, c_1: ''}]
    renumberPreviewRows()
    return
  }
  const maxCol = getMaxPreviewColumnIndex(rows)
  const nextKey = `c_${maxCol + 1}`
  dataSource.previewRows = rows.map((row) => ({...row, [nextKey]: ''}))
}

const insertBlankPreviewRowAfter = (row) => {
  if (props.readonly) return
  const idx = (dataSource.previewRows || []).findIndex((x) => x.__rowKey === row.__rowKey)
  if (idx < 0) return
  const blankRow = {
    __rowKey: `tmp-${Date.now()}`,
    __rowNo: 0,
    ...buildBlankPreviewRow(),
  }
  const next = [...(dataSource.previewRows || [])]
  next.splice(idx + 1, 0, blankRow)
  dataSource.previewRows = next
  renumberPreviewRows()
}

const loadStepDataframePreview = async () => {
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    dataSource.previewRows = []
    return
  }
  try {
    const res = await api.getDataSourceByCaseStep({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
    })
    const info = res?.data || {}
    const matrix = Array.isArray(info.dataframe) ? info.dataframe : []
    dataSource.previewRows = buildPreviewTableRowsByMatrix(matrix)
    renumberPreviewRows()
  } catch (_) {
    dataSource.previewRows = []
  }
}

const dataSourcePreviewColumns = computed(() => [
  {
    type: "selection",
    fixed: "left",
    width: 25,
    align: 'center',
    disabled: (row) => isProtectedPreviewRow(row)
  },
  {
    title: '#',
    key: '__rowNo',
    align: 'center',
    width: 25,
    fixed: 'left',
    render: (row) => String(row.__rowNo ?? '')
  },
  {
    title: '',
    key: '__rowAdd',
    align: 'center',
    width: 25,
    fixed: 'left',
    render: (row) => h(
        'div',
        {style: 'width:100%;display:flex;justify-content:center;align-items:center;'},
        h(NButton, {
          text: true,
          quaternary: true,
          size: 'tiny',
          disabled: props.readonly,
          title: Number(row?.__rowNo || 0) === 1 ? '在首行（字段行）下方插入空白行' : '在下方新增空白行',
          onClick: (e) => {
            e.stopPropagation()
            insertBlankPreviewRowAfter(row)
          }
        }, {
          icon: () => h(TheIcon, {icon: 'material-symbols-light:add-rounded', size: 14})
        })
    )
  },
  ...buildPreviewColumnsByRows(dataSource.previewRows),
  {
    title: () =>
        h(
            'div',
            {style: 'width:100%;display:flex;justify-content:center;align-items:center;'},
            h(NButton, {
              text: true,
              quaternary: true,
              size: 'tiny',
              disabled: props.readonly,
              title: '在右侧新增列',
              onClick: addPreviewColumn,
            }, {
              icon: () => h(TheIcon, {icon: 'material-symbols-light:add-rounded', size: 14}),
            }),
        ),
    key: '__colAdd',
    align: 'center',
    width: 25,
    fixed: 'right',
    render: () =>
        h('div', {
          style: 'min-height:28px;width:100%;',
        }),
  },
])


const dataSourcePreviewKeysRef = ref([]);
const dataSourcePreviewColumnKeysRef = ref([])

/**
 * DataSource「数据预览」表格行主键。
 * @param {object} row
 * @returns {string}
 */
function dataSourcePreviewRowKey(row) {
  return row.__rowKey;
}

/**
 * DataSource「数据预览」表格勾选行变更。
 * @param {string[]} rowKeys
 */
function dataSourcePreviewHandleCheck(rowKeys) {
  dataSourcePreviewKeysRef.value = rowKeys;
}

const dataSourcePreviewRowClassName = (row) => (isProtectedPreviewRow(row) ? 'locked-keyword-row' : '')


const dataSourceGeneratedColumns = [
  {
    title: () => h(NPopover, {
      trigger: 'click',
      placement: 'bottom',
      showArrow: true
    }, {
      default: () => h(NSpace, {vertical: true, size: 6, style: {minWidth: '60px'}}, {
        default: () => [
          h(NButton, {
            size: 'small',
            type: 'error',
            block: true,
            disabled: props.readonly,
            onClick: dataSourceDelete
          }, {default: () => '删除'}),
          h(NButton, {
            size: 'small',
            type: 'success',
            block: true,
            disabled: props.readonly,
            onClick: dataSourceSave
          }, {default: () => '保存'}),
        ]
      }),
      trigger: () => h(NButton, {
        text: true,
        quaternary: true,
        size: 'small',
        title: '更多操作'
      }, {
        icon: () => h(TheIcon, {icon: 'material-symbols:keyboard-command-key', size: 18})
      })
    }),
    key: '_toolbarToggle',
    width: 30,
    align: 'center'
  },
  {
    type: 'selection',
    fixed: 'left',
    width: 30,
    align: 'center'
  },
  {title: '名称', key: 'name', align: 'center', ellipsis: {tooltip: true}},
  {title: '备注', key: 'remark', align: 'center', ellipsis: {tooltip: true}},
  {title: '生成时间', key: 'generatedAt', align: 'center', ellipsis: {tooltip: true}},
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 90,
    render: (row) => h(NSpace, {size: 8}, {
      default: () => [
        h(NButton, {
          text: true,
          type: 'error',
          size: 'small',
          onClick: () => removeDataSourceRow('generated', row)
        }, {default: () => '删除'}),
        h(NButton, {
          text: true,
          type: 'info',
          size: 'small',
          onClick: () => openDataSourceEdit('generated', row)
        }, {default: () => '修改'})
      ]
    })
  }
]

/**
 * DataSource「数据生成」表格行主键。
 * @param {object} row
 * @returns {string}
 */
function dataSourceGeneratedRowKey(row) {
  return row.id;
}

/**
 * 选择接口文档文件（仅前端占位）。
 * @param {object} options
 */
const onApiDocFileSelected = (options) => {
  const file = options?.file?.file
  dataSource.apiDocFileName = file?.name || ''
  if (dataSource.apiDocFileName) {
    $message.info(`已选择接口文档：${dataSource.apiDocFileName}（后端暂未实现上传）`)
  }
}

/** 下载步骤测试数据导入模板（output/template 内置 xlsx）。 */
const downloadStepDataTemplateLoading = ref(false)
const downloadStepDataTemplate = async () => {
  if (downloadStepDataTemplateLoading.value) return
  try {
    downloadStepDataTemplateLoading.value = true
    const res = await api.downloadHttpStepDatasetImportTemplate()
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const fileName = m?.[1]
        ? decodeURIComponent(m[1])
        : '测试用例HTTP请求步骤数据源模板.xlsx'
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('下载成功')
  } catch (e) {
    $message.error(`下载失败：${e?.message || e}`)
  } finally {
    downloadStepDataTemplateLoading.value = false
  }
}
/** 下载接口文档模板（仅前端占位）。 */
const downloadApiDocTemplate = () => $message.info('后端暂未实现：下载接口文档模板')

const dataSourceImportFileInputRef = ref(null)
const dataSourceImportLoading = ref(false)

/** 单步骤数据集导入：需步骤已入库；先选文件，再确认后上传（避免确认框被文件选择器卡住无法关闭）。 */
const dataSourceImport = () => {
  if (props.readonly) return
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('当前步骤尚未保存入库，请先保存步骤树后再进行数据导入')
    return
  }
  dataSourceImportFileInputRef.value?.click()
}

const onDataSourceImportFileChange = (ev) => {
  const input = ev.target
  const file = input?.files?.[0]
  if (input) input.value = ''
  if (!file) return
  if (!String(file.name || '').toLowerCase().endsWith('.xlsx')) {
    $message.warning('仅支持 .xlsx 格式的数据驱动文件')
    return
  }
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('缺少步骤上下文，请先保存步骤树后再试')
    return
  }
  $dialog.confirm({
    title: '导入确认',
    type: 'warning',
    content:
        '上传成功后将覆盖本步骤在服务器端已保存的数据源及缓存，数据预览将以导入文件为准。是否继续？',
    async confirm() {
      if (dataSourceImportLoading.value) return false
      try {
        dataSourceImportLoading.value = true
        const formData = new FormData()
        formData.append('case_id', String(caseId))
        formData.append('step_id', String(stepId))
        formData.append('step_code', stepCode)
        formData.append('file', file)
        const res = await api.uploadSingleStepDataset(formData)
        const info = res?.data || {}
        if (info.file_name != null) dataSourceName.value = String(info.file_name)
        if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
        await loadStepDataframePreview()
        $message.success(res?.message || '导入成功')
        return true
      } catch (_) {
        /* 错误信息由 http 拦截器统一提示 */
        return false
      } finally {
        dataSourceImportLoading.value = false
      }
    },
  })
}
/** 导出数据：基于后端 dataframe 导出 xlsx（不依赖当前前端表格编辑态）。 */
const dataSourceExportLoading = ref(false)
const dataSourceExport = async () => {
  if (dataSourceExportLoading.value) return
  try {
    dataSourceExportLoading.value = true
    const caseId = route.query.case_id ? Number(route.query.case_id) : null
    const original = props.step?.original || {}
    const stepId = original.id ? Number(original.id) : null
    const stepCode = String(original.step_code || '').trim()
    if (!caseId || !stepId || !stepCode) {
      $message.warning('缺少步骤上下文，无法导出')
      return
    }
    const res = await api.exportDataSourceXlsx({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const fileName = m?.[1] ? decodeURIComponent(m[1]) : `dataset_${caseId}_${stepCode}.xlsx`
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('导出成功')
  } catch (e) {
    $message.error(`导出失败：${e?.message || e}`)
  } finally {
    dataSourceExportLoading.value = false
  }
}
/** 删除数据：优先删除数据预览勾选行。 */
const dataSourceDelete = () => {
  if (props.readonly) return
  const selectedRows = new Set(dataSourcePreviewKeysRef.value || [])
  const selectedCols = new Set(dataSourcePreviewColumnKeysRef.value || [])
  if (selectedRows.size === 0 && selectedCols.size === 0) {
    $message.info('请先勾选要删除的行或列')
    return
  }
  const content = `确认删除已勾选的${selectedRows.size > 0 ? '行' : ''}${selectedRows.size > 0 && selectedCols.size > 0 ? '和' : ''}${selectedCols.size > 0 ? '列' : ''}吗？此操作不可撤销。`
  $dialog.confirm({
    title: '删除确认',
    type: 'warning',
    content,
    confirm() {
      let nextRows = (dataSource.previewRows || [])
      if (selectedRows.size > 0) {
        nextRows = nextRows.filter((row) => isProtectedPreviewRow(row) || !selectedRows.has(row.__rowKey))
      }
      if (selectedCols.size > 0) {
        nextRows = nextRows.map((row) => {
          const next = {...row}
          selectedCols.forEach((colKey) => {
            delete next[colKey]
          })
          return next
        })
      }
      dataSource.previewRows = nextRows
      renumberPreviewRows()
      // 清空已删除后的勾选状态，避免 UI 残留
      dataSourcePreviewKeysRef.value = []
      dataSourcePreviewColumnKeysRef.value = []
      $message.success(`已删除${selectedRows.size > 0 ? '行' : ''}${selectedRows.size > 0 && selectedCols.size > 0 ? '和' : ''}${selectedCols.size > 0 ? '列' : ''}`)
    }
  })
}
const dataSourceSaveLoading = ref(false)

/** 将当前数据预览表格提交后端，按 case_id + step_id + step_code 更新数据源（含解析后的 dataset）。 */
const dataSourceSave = async () => {
  if (props.readonly) return
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('当前步骤尚未保存入库，请先保存步骤树后再保存数据')
    return
  }
  if (dataSourceSaveLoading.value) return
  try {
    dataSourceSaveLoading.value = true
    const dataframe = previewRowsToDataframeMatrix(dataSource.previewRows || [])
    const res = await api.updateDataSource({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
      dataframe,
    })
    const info = res?.data || {}
    if (info.file_name != null) dataSourceName.value = String(info.file_name)
    if (info.file_desc != null) dataSourceDesc.value = String(info.file_desc || '')
    await loadStepDataframePreview()
    $message.success(res?.message || '保存成功')
  } catch (_) {
    /* 错误信息由 http 拦截器统一提示 */
  } finally {
    dataSourceSaveLoading.value = false
  }
}

watch(
    () => [route.query.case_id, props.step?.original?.id, props.step?.original?.step_code],
    async () => {
      if (!dataSourceCollapsed.value) {
        await loadStepDataframePreview()
      }
    },
    {deep: false}
)

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

.data-source-toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.data-source-tip {
  display: inline-block;
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
