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

/** 判断字符串是否全部由空白字符组成（空格、制表符等） */
const isBlankString = (value) => typeof value === 'string' && value.trim() === ''

/**
 * 严格数字正则（与后端 _STRICT_NUMBER_RE 保持一致）：
 * 不匹配前导零（0 本身、0.x、.x 除外），用于读回时的数字类型重推断。
 */
const NUMBER_RE = /^-?(?:(?:0|[1-9]\d*)(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?$/

/**
 * 将值写入 Luckysheet 单元格。
 * 前导 ' 是"强制文本"协议标记（对齐 Excel）：标记本身不展示给用户，
 * 通过单元格 qp=1 属性承载，保证内容原样保留（含首尾空白、前导零）。
 * - number → t:'n'；boolean → t:'b'；普通 string → t:'s' 文本格式
 * - ' 前缀 string：剥去标记，写入 qp=1 文本单元格
 * - 纯空白 string：写入 qp=1 保护（Luckysheet 判空会吞掉纯空白）
 */
const valueToLuckysheetCell = (value, extra = {}) => {
  if (value == null || value === '') {
    return {ct: {fa: 'General', t: 'g'}, m: '', v: '', ht: 0, vt: 0, ...extra}
  }
  if (typeof value === 'number') {
    return {ct: {fa: 'General', t: 'n'}, m: String(value), v: value, ht: 0, vt: 0, ...extra}
  }
  if (typeof value === 'boolean') {
    return {ct: {fa: 'General', t: 'b'}, m: String(value), v: value, ht: 0, vt: 0, ...extra}
  }
  // 字符串值：使用文本格式，防止 Luckysheet 自动转换 true→TRUE / 000000→0
  let text = value
  let forcedText = false
  if (text.startsWith("'")) {
    // 协议标记：剥去 '，用 qp=1 承载强制文本语义
    text = text.slice(1)
    forcedText = true
  } else if (isBlankString(text)) {
    forcedText = true
  }
  return {ct: {fa: '@', t: 's'}, m: text, v: text, ht: 0, vt: 0, ...(forcedText ? {qp: 1} : {}), ...extra}
}

/**
 * 读取 Luckysheet 单元格值（Excel 语义）：
 * - qp=1（用户输入过前导 '，或加载的强制文本）：返回 ' + 原文，原样保留
 * - 纯数字文本：重推断为 number，允许编辑改变类型（'000200 → 18 → 数字 18）
 * - 其他字符串：trim 后返回；true/false 保持字符串
 * - 非字符串值（number/boolean）：原样返回
 */
const readLuckysheetCell = (cell) => {
  if (cell == null) return null
  const raw = cell.v !== undefined && cell.v !== null ? cell.v : cell.m
  if (raw === undefined || raw === null || raw === '') return null
  if (typeof raw !== 'string') return raw
  if (cell.qp === 1) return `'${raw}`
  if (NUMBER_RE.test(raw)) return Number(raw)
  return raw.trim()
}

const hasUserInput = (value) => value != null && value !== ''

/**
 * 判断字符串剥离前导 ' 标记后是否为非空纯空白（如 "   " 或 "'   "）。
 * 注意必须先剥标记再判空："'   ".trim() 仍含 '，直接 isBlankString 会漏判。
 */
const extractForcedBlankText = (value) => {
  if (typeof value !== 'string') return null
  const text = value.startsWith("'") ? value.slice(1) : value
  if (text !== '' && isBlankString(text)) return text
  return null
}

/**
 * 纯空白 qp 单元格（如 "'   "）不能走 celldata 初始化路径：
 * luckysheet.create → buildGridData 内部写值函数开头会判空（纯空白视为空），
 * 直接删除 v/m，导致重载后双击显示 "'null"。收集这些位置，create 后直写 flowdata。
 */
let pendingBlankCells = []

/**
 * 获取当前活动 sheet 的 data 矩阵的【活动引用】（luckysheetfile[active].data）。
 * 关键陷阱：导出的 getSheetData() 内部用 $.extend(true, [], data) 深拷贝返回，
 * 直写到它的返回值上等于写进副本，下一次读取即丢失（实测验证）。
 * 只有 getLuckysheetfile() 返回的 luckysheetfile 数组里活动 sheet 的 data 才是真实本体，
 * 补写/恢复单元格必须写这里。每次调用都重新取，避免 destroy/create 后持有陈旧引用。
 */
const getLiveSheetData = () => {
  const luckysheet = luckysheetRef.value
  if (!luckysheet) return null
  try {
    const file = luckysheet.getLuckysheetfile?.()
    if (!Array.isArray(file) || !file.length) return null
    const active = file.find((s) => s && s.status == 1) || file[0]
    const data = active && active.data
    if (data && data.length) return data
  } catch (_) { /* ignore */ }
  return null
}

/**
 * 重绘表格。注意：Luckysheet 2.1.13 未导出 refresh 方法，
 * 直写 flowdata 后需用导出的 jfrefreshgrid(data) 触发重绘。
 */
const refreshGrid = () => {
  const luckysheet = luckysheetRef.value
  if (!luckysheet) return
  try {
    const data = getLiveSheetData()
    if (typeof luckysheet.jfrefreshgrid === 'function' && data) {
      luckysheet.jfrefreshgrid(data)
    }
  } catch (_) { /* 重绘失败不影响已写入的单元格值，后续交互会重绘 */ }
}

/** 将纯空白值补写入活动 sheet data（绕过内部写值的判空路径）。
 * create 内部存在异步初始化环节（flowdata 同步、首次渲染），且期间可能
 * 发生 destroy/重建（实例更替），因此：延迟启动 + 重试写入 + 校验目标数组
 * 仍是当前实例的 data（实例已更替时放弃，由新一轮 create 自行补写）。 */
const writeBlankCellOnce = (data, r, c, text) => {
  if (!data[r]) return false
  data[r][c] = {ct: {fa: '@', t: 's'}, m: text, v: text, qp: 1, ht: 0, vt: 0}
  return true
}

const applyPendingBlankCells = () => {
  const cells = pendingBlankCells
  pendingBlankCells = []
  if (!cells.length) return
  const containerAtApply = containerId.value
  let attempts = 0
  const attempt = () => {
    attempts += 1
    // 实例已销毁/容器已更替：放弃，避免把旧单元格写进新实例
    if (!luckysheetRef.value || !isReady.value || containerId.value !== containerAtApply) return
    const data = getLiveSheetData()
    const ok = data && cells.every(({r, c, text}) => writeBlankCellOnce(data, r, c, text))
    if (ok) {
      refreshGrid()
      return
    }
    if (attempts < 40) setTimeout(attempt, 50)
  }
  // 延迟一拍启动：等 create 同步尾部与首个微任务完成
  setTimeout(attempt, 0)
}

const buildLuckysheetData = () => {
  const celldata = []
  pendingBlankCells = []
  const columns = Array.isArray(props.columns) ? props.columns : []
  const dataRows = Array.isArray(props.data) ? props.data : []
  const keywords = Array.isArray(props.protectedRowKeywords) ? props.protectedRowKeywords : []
  const keywordSet = new Set(keywords.map((k) => String(k).trim().toUpperCase()))

  // 第一行：表头
  columns.forEach((col, c) => {
    const value = col == null ? '' : col
    const blankText = extractForcedBlankText(value)
    if (blankText != null) {
      pendingBlankCells.push({r: 0, c, text: blankText})
      return
    }
    celldata.push({r: 0, c, v: valueToLuckysheetCell(value)})
  })

  // 数据行
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
      const blankText = extractForcedBlankText(raw)
      if (blankText != null) {
        // 非空纯空白值（先剥前导 ' 再判空，覆盖 "'   " 场景）：
        // 跳过 celldata，create 后直写（空串不受判空影响，保留 celldata 路径以保住保护行样式）
        pendingBlankCells.push({r: rowIndex, c, text: blankText})
        continue
      }
      celldata.push({r: rowIndex, c, v: valueToLuckysheetCell(raw, extra)})
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
let editModeKeyFixCleanup = []

/**
 * 提交快照：cellUpdateBefore 阶段记录用户提交的原始文本，
 * 供 cellUpdated 后处理判断（Luckysheet 判空会吞掉纯空白，需事后恢复）。
 */
const lastCommittedText = ref(null)

/**
 * 恢复被 Luckysheet 判空逻辑吞掉的纯空白值：
 * 直接写入活动 sheet data（绕过 setCellValue 的判空路径），再整体重绘。
 */
const restoreBlankCell = (r, c, text) => {
  const data = getLiveSheetData()
  if (!data || !data[r]) return
  data[r][c] = {ct: {fa: '@', t: 's'}, m: text, v: text, qp: 1, ht: 0, vt: 0}
  refreshGrid()
}

/**
 * cellUpdated 后处理（对齐 Excel 语义）：
 * 用户不带前导 ' 编辑了 qp（强制文本）单元格 → 解除 qp 文本锁，
 * 读回时按新内容重新推断类型（'000200 → 输入 18 → 数字 18；输入 abc → 普通文本）。
 * 纯空白的恢复在 cellUpdateBefore 阶段完成（Luckysheet 判空后直接 cancel，不触发本钩子）。
 */
const postProcessCellUpdate = (r, c, newCell) => {
  const committed = lastCommittedText.value
  lastCommittedText.value = null
  if (committed == null || committed === '') return
  if (!committed.startsWith("'") && newCell && newCell.qp === 1) {
    try {
      // 同步清除 qp 锁（必须在 emit('change') 引发的矩阵读回之前完成），
      // 对象分支属性覆盖不重新触发类型推断；其内部再触发的 cellUpdated 因快照为空而跳过
      luckysheetRef.value?.setCellValue?.(r, c, {qp: 0})
    } catch (_) { /* ignore */ }
  }
}

/**
 * 修复 Luckysheet "第一个按键被吃掉" 的问题。
 *
 * Luckysheet 点击单元格后处于"选择模式"，按下可打印字符时它会进入编辑态，
 * 但触发编辑的那个字符不会自动填入 input（因为 keydown 触发时 input 尚未获焦）。
 * 此函数在 capture 阶段拦截可打印字符 keydown，若当前未处于编辑态，
 * 则记住该字符，等 Luckysheet 完成编辑态切换后手动注入到 contenteditable div。
 */
const setupEditModeKeyFix = () => {
  editModeKeyFixCleanup.forEach((fn) => fn())
  editModeKeyFixCleanup = []
  if (typeof document === 'undefined') return
  if (props.readonly) return

  const container = document.getElementById(containerId.value)
  if (!container) return

  const isEditing = () => {
    try {
      const inputBox = document.getElementById('luckysheet-input-box')
      if (!inputBox) return false
      const top = parseInt(inputBox.style.top, 10)
      return !isNaN(top) && top > 0
    } catch (_) {
      return false
    }
  }

  const isPrintableKey = (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return false
    if (e.keyCode === 229) return true
    if (e.key.length !== 1) return false
    if (e.key <= ' ' || e.key === 'Delete') return false
    return true
  }

  const handler = (e) => {
    // IME 输入（keyCode 229）：Luckysheet 不处理 229，需手动进入编辑态
    if (e.keyCode === 229 && !isEditing()) {
      try {
        const selections = luckysheetRef.value?.getluckysheet_select_save?.() || []
        if (!selections.length) return
        const sel = selections[selections.length - 1]
        const row = sel.row_focus ?? sel.row?.[0]
        const col = sel.column_focus ?? sel.column?.[0]
        if (row == null || col == null) return
        const inputBox = document.getElementById('luckysheet-input-box')
        const editor = document.getElementById('luckysheet-rich-text-editor')
        if (!inputBox || !editor) return
        // 获取单元格像素位置，显示输入框
        const cellPos = luckysheetRef.value?.getcellposition?.(row, col)
        if (cellPos) {
          const {top, left, height} = cellPos
          inputBox.style.top = `${top + height}px`
          inputBox.style.left = `${left}px`
          inputBox.style.display = 'block'
        }
        editor.focus()
      } catch (_) { /* ignore */ }
      // 阻止 Luckysheet 处理 keyCode 229，避免干扰 IME 组合输入
      e.stopPropagation()
      return
    }
    if (!isPrintableKey(e)) return
    if (isEditing()) return
    // 当前未处于编辑态，记住即将被 Luckysheet "吃掉" 的字符
    const char = e.key
    // 等 Luckysheet 处理完 keydown（进入编辑态）后，手动注入字符
    const inject = () => {
      requestAnimationFrame(() => {
        if (!isEditing()) return
        const editor = document.getElementById('luckysheet-rich-text-editor')
        if (!editor) return
        // 仅在编辑器为空（刚进入编辑态）时注入
        const currentText = editor.textContent || ''
        if (currentText.length === 0 || currentText === '\u200B') {
          editor.textContent = char
          // 触发 input 事件让 Luckysheet 同步内部状态
          editor.dispatchEvent(new Event('input', { bubbles: true }))
        }
      })
    }
    setTimeout(inject, 0)
  }

  container.addEventListener('keydown', handler, true)
  editModeKeyFixCleanup.push(() => container.removeEventListener('keydown', handler, true))
}

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
      cellUpdated: (r, c, oldValue, newValue, isRefresh) => {
        postProcessCellUpdate(r, c, newValue)
        emit('change')
      },
      cellUpdateBefore: (row, col, value, isRefresh) => {
        if (isProtectedRow(row)) return false
        if (typeof value === 'string') {
          // 纯空白（非空串）：Luckysheet 判空会吞掉并直接 cancel（不触发 cellUpdated），
          // 在此直接写入 qp=1 保护单元格并拦截默认处理（对齐 Excel：允许保存空格）
          if (value !== '' && isBlankString(value)) {
            restoreBlankCell(row, col, value)
            return false
          }
          // 记录提交原文，供 cellUpdated 后处理判断是否解除 qp 文本锁
          lastCommittedText.value = value
        }
      },
      rangePasteBefore: (selectSave) => {
        // 粘贴不走 cellUpdateBefore/cellUpdated，作废编辑提交快照避免状态串扰
        lastCommittedText.value = null
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
    // 纯空白 qp 单元格绕过 celldata/Cs 判空路径，直接补写 flowdata
    applyPendingBlankCells()
    isReady.value = true
    setupEditModeKeyFix()
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
  editModeKeyFixCleanup.forEach((fn) => fn())
  editModeKeyFixCleanup = []
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
      row.push(readLuckysheetCell(sheetData[r]?.[c]))
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
