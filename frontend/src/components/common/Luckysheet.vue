<template>
  <div :id="containerId" class="luckysheet-container"/>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import {useDark} from '@vueuse/core'

/**
 * Luckysheet Vue3 封装组件
 *
 * Props:
 *   - data: 二维数组，单元格可为 number/boolean/string/null（对齐 Excel 类型）
 *   - columns: 表头数组，第 0 项为第一列表头（通常留空），其余为场景列名
 *   - readonly: 是否只读
 *   - options: 透传给 luckysheet 的额外配置
 *   - protectedRowKeywords: 关键字数组，若某行第 0 列匹配其中一项，
 *     则该行整体置灰且只读（不可编辑/粘贴）。
 *
 * Expose:
 *   - getData(): 获取当前 sheet 的 celldata 二维数组
 *   - getDataForSave(): 获取去除了空行列后的干净二维数组
 *   - setData(data, columns): 重置表格数据与列头
 *   - getLuckysheet(): 返回 luckysheet 实例（全局对象）
 */

const props = defineProps({
  data: {type: Array, default: () => []},
  columns: {type: Array, default: () => []},
  readonly: {type: Boolean, default: false},
  options: {type: Object, default: () => ({})},
  protectedRowKeywords: {type: Array, default: () => []},
})

const emit = defineEmits(['change', 'protectedAction'])

const containerId = computed(() => `luckysheet-container-${Math.random().toString(36).slice(2, 10)}`)
const luckysheetRef = ref(null)
const isReady = ref(false)
const isInitializing = ref(false)

const baseUrl = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
const LUCKYSHEET_BASE = import.meta.env.DEV
    ? '/node_modules/luckysheet/dist'
    : `${baseUrl}/luckysheet`
const JQUERY_URL = import.meta.env.DEV
    ? '/node_modules/jquery/dist/jquery.min.js'
    : `${baseUrl}/luckysheet/jquery.min.js`
const LUCKYSHEET_PLUGIN_URL = import.meta.env.DEV
    ? '/node_modules/luckysheet/dist/plugins/js/plugin.js'
    : `${baseUrl}/luckysheet/plugins/js/plugin.js`

const loadScript = (src) =>
    new Promise((resolve, reject) => {
      if (typeof document === 'undefined') return resolve()
      const existing = document.querySelector(`script[src="${src}"]`)
      if (existing) {
        existing.addEventListener('load', () => resolve())
        if (window.luckysheet) resolve()
        return
      }
      const script = document.createElement('script')
      script.src = src
      script.async = true
      script.onload = () => resolve()
      script.onerror = (e) => reject(e)
      document.body.appendChild(script)
    })

const loadLuckysheet = async () => {
  if (typeof window === 'undefined') return null
  if (window.luckysheet && typeof window.luckysheet.create === 'function') {
    return window.luckysheet
  }
  await loadScript(JQUERY_URL)
  await loadScript(LUCKYSHEET_PLUGIN_URL)
  await loadScript(`${LUCKYSHEET_BASE}/luckysheet.umd.js`)
  if (window.luckysheet && typeof window.luckysheet.create === 'function') {
    return window.luckysheet
  }
  throw new Error('Luckysheet UMD 加载失败，未找到 window.luckysheet.create')
}

const loadStyles = () => {
  if (typeof document === 'undefined') return
  const styles = [
    { id: 'luckysheet-plugins-css', url: `${LUCKYSHEET_BASE}/plugins/css/pluginsCss.css` },
    { id: 'luckysheet-plugins2-css', url: `${LUCKYSHEET_BASE}/plugins/plugins.css` },
    { id: 'luckysheet-css', url: `${LUCKYSHEET_BASE}/css/luckysheet.css` },
    { id: 'luckysheet-iconfont-css', url: `${LUCKYSHEET_BASE}/assets/iconfont/iconfont.css` },
  ]
  styles.forEach(({ id, url }) => {
    if (document.getElementById(id)) return
    const link = document.createElement('link')
    link.id = id
    link.rel = 'stylesheet'
    link.href = url
    document.head.appendChild(link)
  })
}

const isDark = useDark()
/** 受保护行背景色：跟随应用深/浅色模式（深色用深灰、浅色用浅灰） */
const PROTECTED_ROW_BG = computed(() => (isDark.value ? '#3a3a3a' : '#f0f0f0'))

const isEmptyCellValue = (value) => value == null || value === ''

const looksLikeNumberText = (text) => /^-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)

const needsExcelTextFormat = (text) => {
  if (typeof text !== 'string' || text === '') return false
  const token = text.toLowerCase()
  return token === 'true' || token === 'false' || token === 'null' || looksLikeNumberText(text)
}

/** 将 dataset/矩阵值转为 Luckysheet 单元格，对齐 Excel 类型（数字/布尔/文本） */
const valueToLuckysheetCell = (value, extra = {}) => {
  if (isEmptyCellValue(value)) {
    return {ct: {fa: 'General', t: 'g'}, m: '', v: '', ht: 0, vt: 0, ...extra}
  }
  if (typeof value === 'boolean') {
    const m = value ? 'TRUE' : 'FALSE'
    return {ct: {fa: 'General', t: 'b'}, m, v: value, ht: 0, vt: 0, ...extra}
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return {ct: {fa: 'General', t: 'n'}, m: String(value), v: value, ht: 0, vt: 0, ...extra}
  }
  const text = String(value)
  if (needsExcelTextFormat(text)) {
    return {ct: {fa: '@', t: 's'}, m: text, v: text, ht: 0, vt: 0, ...extra}
  }
  return {ct: {fa: 'General', t: 'g'}, m: text, v: text, ht: 0, vt: 0, ...extra}
}

/**
 * 读取 Luckysheet 单元格为矩阵值。
 * 不在编辑钩子里改写格子，以免破坏复制/粘贴/撤销。
 * 前导 ' 仅在读取时去掉，作为 Excel 强制文本前缀。
 */
const readLuckysheetCell = (cell, {asText = false} = {}) => {
  if (cell == null) return asText ? '' : null
  const raw = cell.v !== undefined && cell.v !== null ? cell.v : cell.m
  if (raw === undefined || raw === null || raw === '') return asText ? '' : null
  if (asText) {
    const text = String(raw)
    return text.startsWith("'") ? text.slice(1) : text
  }
  const ctType = cell.ct && cell.ct.t
  if (ctType === 'n' && typeof raw === 'number' && Number.isFinite(raw)) return raw
  if (ctType === 'b') {
    if (typeof raw === 'boolean') return raw
    const token = String(raw).toLowerCase()
    if (token === 'true') return true
    if (token === 'false') return false
  }
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw
  if (typeof raw === 'boolean') return raw
  const text = String(raw)
  if (text.startsWith("'")) return text.slice(1)
  return text
}

const hasUserInput = (value) => value != null && value !== ''

const buildLuckysheetData = () => {
  const celldata = []
  const columns = Array.isArray(props.columns) ? props.columns : []
  const dataRows = Array.isArray(props.data) ? props.data : []
  const keywords = Array.isArray(props.protectedRowKeywords) ? props.protectedRowKeywords : []
  const keywordSet = new Set(keywords.map((k) => String(k).trim().toUpperCase()))

  // 第一行：表头（始终文本）
  columns.forEach((col, c) => {
    const value = col == null ? '' : String(col)
    celldata.push({r: 0, c, v: valueToLuckysheetCell(value)})
  })

  // 数据行：第 0 列为字段名/分区标记（文本），其余格按 Excel 类型写入
  dataRows.forEach((row, r) => {
    const rowIndex = r + 1
    const rowArr = Array.isArray(row) ? row : []
    const firstValue = rowArr[0] == null ? '' : String(rowArr[0]).trim().toUpperCase()
    const isProtected = keywordSet.has(firstValue)
    const numCols = Math.max(columns.length, rowArr.length)

    for (let c = 0; c < numCols; c++) {
      const raw = c < rowArr.length ? rowArr[c] : null
      if (isEmptyCellValue(raw) && !isProtected) continue
      const extra = isProtected ? {bg: PROTECTED_ROW_BG.value, bl: 1} : {}
      const cellValue = c === 0 ? (raw == null ? '' : String(raw)) : raw
      celldata.push({r: rowIndex, c, v: valueToLuckysheetCell(cellValue, extra)})
    }
  })

  return celldata
}

const isProtectedRow = (rowIndex) => {
  const keywords = Array.isArray(props.protectedRowKeywords) ? props.protectedRowKeywords : []
  if (!keywords.length || !luckysheetRef.value || !isReady.value) return false
  try {
    const sheetData = luckysheetRef.value.getSheetData() || []
    const cell = sheetData[rowIndex]?.[0]
    if (!cell) return false
    const value = String(cell.v ?? cell.m ?? '').trim().toUpperCase()
    return keywords.some((kw) => String(kw).trim().toUpperCase() === value)
  } catch (_) {
    return false
  }
}

const hasProtectedRowInSelection = () => {
  if (!luckysheetRef.value || !isReady.value) return false
  const keywords = Array.isArray(props.protectedRowKeywords) ? props.protectedRowKeywords : []
  if (!keywords.length) return false
  try {
    const selections = luckysheetRef.value.getluckysheet_select_save() || []
    for (const sel of selections) {
      if (!sel || !sel.row || !Array.isArray(sel.row)) continue
      for (let r = sel.row[0]; r <= sel.row[1]; r++) {
        if (isProtectedRow(r)) return true
      }
    }
  } catch (_) {}
  return false
}

const isSelectionColumnWide = () => {
  if (!luckysheetRef.value || !isReady.value) return false
  try {
    const sheetData = luckysheetRef.value.getSheetData() || []
    const totalRows = sheetData.length
    if (totalRows === 0) return false
    const selections = luckysheetRef.value.getluckysheet_select_save() || []
    for (const sel of selections) {
      if (!sel || !sel.row || !Array.isArray(sel.row)) continue
      if (sel.row[0] === 0 && sel.row[1] >= totalRows - 1) return true
    }
  } catch (_) {}
  return false
}

let deletionProtectionCleanup = []

const setupDeletionProtection = () => {
  deletionProtectionCleanup.forEach((fn) => fn())
  deletionProtectionCleanup = []
  if (typeof document === 'undefined') return
  if (!Array.isArray(props.protectedRowKeywords) || !props.protectedRowKeywords.length) return

  const shouldBlock = () => hasProtectedRowInSelection() && !isSelectionColumnWide()
  const interceptClick = (e) => {
    if (shouldBlock()) {
      e.stopImmediatePropagation()
      e.preventDefault()
      emit('protectedAction', 'delete')
    } else {
      setTimeout(() => emit('change'), 0)
    }
  }
  const interceptKeydown = (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (shouldBlock()) {
        e.stopImmediatePropagation()
        e.preventDefault()
        emit('protectedAction', 'delete')
      } else {
        setTimeout(() => emit('change'), 0)
      }
    }
  }

  const delBtnIds = [
    'luckysheet-del-selected',
    'luckysheet-del-selected_t',
    'luckysheet-delRows',
    'luckysheet-delCellsMoveUp',
  ]
  delBtnIds.forEach((id) => {
    const btn = document.getElementById(id)
    if (!btn) return
    btn.addEventListener('click', interceptClick, true)
    deletionProtectionCleanup.push(() => btn.removeEventListener('click', interceptClick, true))
  })

  const container = document.getElementById(containerId.value)
  if (container) {
    container.addEventListener('keydown', interceptKeydown, true)
    deletionProtectionCleanup.push(() => container.removeEventListener('keydown', interceptKeydown, true))
  }
}

const initLuckysheet = async () => {
  if (isInitializing.value) return
  isInitializing.value = true
  try {
    const luckysheet = await loadLuckysheet()
    if (!luckysheet) return

    loadStyles()
    luckysheetRef.value = luckysheet

    const config = {
    container: containerId.value,
    title: '',
    lang: 'zh',
    showtoolbar: false,
    showinfobar: false,
    sheetFormulaBar: !props.readonly,
    showsheetbar: false,
    showstatisticBar: false,
    enableAddRow: !props.readonly,
    enableAddCol: !props.readonly,
    rowHeaderWidth: 40,
    columnHeaderHeight: 28,
    defaultColWidth: 150,
    defaultRowHeight: 28,
    cellRightClickConfig: {
      copy: true,
      copyAs: false,
      paste: true,
      insertRow: true,
      insertColumn: true,
      deleteRow: true,
      deleteColumn: true,
      deleteCell: true,
      hideRow: false,
      hideColumn: false,
      rowHeight: false,
      columnWidth: false,
      clear: true,
      matrix: true,
      sort: false,
      filter: true,
      chart: false,
      image: false,
      link: false,
      data: false,
      cellFormat: false,
    },
    data: [
      {
        name: '数据源',
        color: '',
        status: 1,
        order: 0,
        celldata: buildLuckysheetData(),
        config: {
          columnlen: {},
          rowlen: {},
        },
      },
    ],
    hook: {
      // 只通知上层变脏，不在此改写单元格，避免打断 Luckysheet 自带的复制/粘贴/撤销
      cellUpdated: () => {
        emit('change')
      },
      cellUpdateBefore: (row, col, value, isRefresh) => {
        if (isProtectedRow(row)) return false
      },
      rangePasteBefore: (selectSave) => {
        if (!selectSave || !Array.isArray(selectSave)) return true
        for (const sel of selectSave) {
          if (!sel || !sel.row || !Array.isArray(sel.row)) continue
          for (let r = sel.row[0]; r <= sel.row[1]; r++) {
            if (isProtectedRow(r)) return false
          }
        }
        return true
      },
      cellDeleteBefore: () => {
        if (props.readonly) return false
      },
    },
    ...props.options,
  }

    luckysheet.create(config)
    isReady.value = true
    setupDeletionProtection()
  } catch (e) {
    console.error('[Luckysheet] create failed:', e)
    throw e
  } finally {
    isInitializing.value = false
  }
}

const destroyLuckysheet = () => {
  deletionProtectionCleanup.forEach((fn) => fn())
  deletionProtectionCleanup = []
  if (!luckysheetRef.value) return
  try {
    if (typeof luckysheetRef.value.destroy === 'function') {
      luckysheetRef.value.destroy()
    }
  } catch (_) {
    /* ignore */
  }
  luckysheetRef.value = null
  isReady.value = false
}

const getSheetData = () => {
  if (!luckysheetRef.value || !isReady.value) return []
  try {
    return luckysheetRef.value.getSheetData() || []
  } catch (_) {
    return []
  }
}

const getData = () => {
  const sheetData = getSheetData()
  const rows = sheetData.length
  if (rows === 0) return []
  const cols = Math.max(...sheetData.map((row) => (Array.isArray(row) ? row.length : 0)))
  const result = []
  for (let r = 0; r < rows; r++) {
    const row = []
    for (let c = 0; c < cols; c++) {
      const cell = sheetData[r]?.[c]
      row.push(readLuckysheetCell(cell, {asText: r === 0 || c === 0}))
    }
    result.push(row)
  }
  return result
}

const getDataForSave = () => {
  const raw = getData()
  if (!raw.length) return {headers: [], rows: []}

  const headers = raw[0].map((h) => (h == null || h === '' ? '' : String(h)))
  const dataRows = raw.slice(1)

  const blankCols = new Set()
  for (let c = 1; c < headers.length; c++) {
    const hasHeader = headers[c] !== ''
    const hasData = dataRows.some((row) => hasUserInput(row[c]))
    if (!hasHeader && !hasData) blankCols.add(c)
  }

  const keepCols = []
  for (let c = 0; c < headers.length; c++) {
    if (!blankCols.has(c)) keepCols.push(c)
  }

  const filteredRows = dataRows
      .filter((row) => keepCols.some((c) => hasUserInput(row[c])))
      .map((row) => keepCols.map((c) => {
        const v = row[c]
        return v == null ? '' : v
      }))

  const filteredHeaders = keepCols.map((c) => headers[c] == null ? '' : headers[c])
  return {headers: filteredHeaders, rows: filteredRows}
}

const setData = async (data, columns) => {
  if (isInitializing.value) {
    // 等待当前初始化完成后再重建，避免并发破坏实例状态
    await new Promise((resolve) => {
      const stop = watch(isInitializing, (v) => {
        if (!v) {
          stop()
          resolve()
        }
      })
    })
  }
  destroyLuckysheet()
  const el = document.getElementById(containerId.value)
  if (el) el.innerHTML = ''
  await initLuckysheet()
}

const getLuckysheet = () => luckysheetRef.value

watch(
    () => [props.data, props.columns],
    () => {
      if (isReady.value) {
        setData(props.data, props.columns)
      }
    },
    {deep: true}
)

onMounted(() => {
  initLuckysheet()
})

onUnmounted(() => {
  destroyLuckysheet()
})

defineExpose({
  getData,
  getDataForSave,
  setData,
  getLuckysheet,
  isReady,
})
</script>

<style scoped>
.luckysheet-container {
  width: 100%;
  min-height: 360px;
  height: 100%;
  padding: 0;
  margin: 0;
}
</style>
