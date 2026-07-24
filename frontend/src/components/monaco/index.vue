<template>
  <div className="monaco-editor" ref="monacoEditorRef"></div>
</template>
<script>
/**
 * Monaco 编辑器主题挂载栈（跨组件实例共享的模块级状态）。
 * Monaco 的主题是全局唯一的（monaco.editor.setTheme 作用于页面上所有编辑器），
 * 当不同主题的编辑器共存时（如主页面暗色编辑器 + 报告明细抽屉亮色编辑器）会相互覆盖。
 * 通过挂载栈管理：最近挂载的编辑器主题生效；卸载时回退到上一层主题，
 * 避免临时浮层（报告详情抽屉）关闭后把主页面编辑器主题"带偏"。
 */
const mountedEditorThemes = []
</script>
<script setup name="monacoEditor">
/**
 * 通用 Monaco 编辑器封装
 *
 * 能力概览：
 * - 支持 v-model:value 双向绑定、props.options 透传 Monaco 配置
 * - 可选 Diff 双栏对比（isDiff + oldString）
 * - SQL：表字段智能补全、右键执行
 * - JSON：光标处 JsonPath 计算、右键复制路径
 * - 暴露 getValue / setValue / insertAtCursor 等供业务页插入代码片段
 */
import * as monaco from 'monaco-editor'
import editorWorker from '~/node_modules/monaco-editor/esm/vs/editor/editor.worker?worker';
import jsonWorker from '~/node_modules/monaco-editor/esm/vs/language/json/json.worker?worker';
import cssWorker from '~/node_modules/monaco-editor/esm/vs/language/css/css.worker?worker';
import htmlWorker from '~/node_modules/monaco-editor/esm/vs/language/html/html.worker?worker';
import tsWorker from '~/node_modules/monaco-editor/esm/vs/language/typescript/ts.worker?worker';

import {onMounted, onUnmounted, reactive, ref, toRaw, watch} from 'vue'
import SQLSnippets from "./core/sql.js"
import {getJsonPath} from '@/utils/common/jsonPath'
import commonFunction from "@/utils/common/commonFunction";

/**
 * Monaco Web Worker 环境配置（须在 create 编辑器之前设置）
 * 按语言类型加载对应 worker，避免主线程解析大文件时卡顿
 */
self.MonacoEnvironment = {
  getWorker(_, label) {
    if (label === 'json') {
      return new jsonWorker()
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new cssWorker()
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor' || label === 'xml') {
      return new htmlWorker()
    }
    if (label === 'typescript' || label === 'javascript') {
      return new tsWorker()
    }
    return new editorWorker()
  }
}

/** XML 简易排版（供 formatOnPaste / formatOnType 使用） */
const tryParseValidXmlDoc = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s || !s.includes('<')) return null
  if (typeof DOMParser === 'undefined') return null
  const doc = new DOMParser().parseFromString(s, 'text/xml')
  const pe = doc.querySelector('parsererror')
  if (pe && String(pe.textContent || '').trim()) return null
  if (!doc.documentElement) return null
  return doc
}

const formatXmlPrettyText = (xml) => {
  let formatted = ''
  let pad = 0
  const normalized = String(xml).replace(/>\s*</g, '>\n<')
  normalized.split('\n').forEach((line) => {
    const node = line.trim()
    if (!node) return
    let indent = 0
    if (node.match(/.+<\/\w[^>]*>$/)) {
      indent = 0
    } else if (node.match(/^<\/\w/)) {
      if (pad > 0) pad -= 1
    } else if (node.match(/^<\w[^>]*[^/]>.*$/)) {
      indent = 1
    } else {
      indent = 0
    }
    formatted += `${'  '.repeat(pad)}${node}\n`
    pad += indent
  })
  return formatted.trimEnd()
}

const beautifyXmlText = (raw) => {
  const doc = tryParseValidXmlDoc(raw)
  if (!doc) return null
  const ser = new XMLSerializer().serializeToString(doc.documentElement)
  return formatXmlPrettyText(ser)
}

/** 仅注册一次，避免重复 provider */
let xmlFormattingProvidersRegistered = false
const ensureXmlFormattingProviders = () => {
  if (xmlFormattingProvidersRegistered) return
  xmlFormattingProvidersRegistered = true
  monaco.languages.registerDocumentFormattingEditProvider('xml', {
    provideDocumentFormattingEdits(model) {
      const text = model.getValue()
      const pretty = beautifyXmlText(text)
      if (pretty == null || pretty === text) return []
      return [{ range: model.getFullModelRange(), text: pretty }]
    },
  })
  monaco.languages.registerDocumentRangeFormattingEditProvider('xml', {
    provideDocumentRangeFormattingEdits(model) {
      const text = model.getValue()
      const pretty = beautifyXmlText(text)
      if (pretty == null || pretty === text) return []
      return [{ range: model.getFullModelRange(), text: pretty }]
    },
  })
}

const props = defineProps({
  /** @deprecated 与 value 二选一；当前实现以 value + update:value 为主 */
  modelValue: {
    type: String,
    default: '',
  },
  /** 编辑器绑定文本，变更时通过 update:value 回传父组件 */
  value: {
    type: String,
    default: '',
  },
  /** true 时使用 DiffEditor 左右对比，否则为单编辑器 */
  isDiff: {
    type: Boolean,
    default: false,
  },
  /** 是否只读（也可在 options.readOnly 中设置） */
  readOnly: {
    type: Boolean,
    default: false,
  },
  /** Diff 模式左侧原文（original） */
  oldString: {
    type: String,
    default: '',
  },
  /** Diff 模式右侧文案预留；当前 Diff 实现主要使用 value / oldString */
  newString: {
    type: String,
    default: '',
  },
  // 语言
  lang: {
    type: String,
    default: 'python',
  },
  // 主题
  theme: {
    type: String,
    // vs：浅色默认主题（适合白天使用）
    // vs-dark：深色主题（VS Code 默认深色，推荐）
    // hc-black：高对比度黑色主题（适配视觉障碍用户）
    default: 'vs-dark',
  },
  //lineNumbers
  options: {
    type: Object,
    default: () => {
      return {}
    }
  },
  /** SQL 右键「执行」时调用的回调 */
  executeHandle: {
    type: Function,
  },
  /** 数据库列表（历史字段，补全主要使用 dbs） */
  dbList: {
    type: Array,
    default: () => []
  },
  /** SQL 补全：表别名列表或返回表别名的函数 */
  onInputTableAlia: {
    type: [Array, Function],
    default: () => []
  },
  /** SQL 补全：可选字段名列表 */
  onInputField: {
    type: Array,
    default: () => []
  },
  /** SQL 补全：库表结构 schema，变更时触发 watch 刷新 SQLSnippets */
  dbs: {
    type: Array,
    default: () => []
  }
})

/** 光标移动时向父组件上报偏移（JSON 场景） */
const emit = defineEmits(["on-cursor-change", "update:value"])

/** 普通模式下的 Monaco 编辑器实例；Diff 模式下为 DiffEditor 实例 */
const editor = ref(null)
/** 挂载 Monaco 的 DOM 容器 */
const monacoEditorRef = ref()
/** Diff 模式：左侧「原始」文本 Model */
const originalEditor = ref(null)
/** Diff 模式：右侧「修改后」文本 Model */
const modifiedEditor = ref(null)

/**
 * 组件内部运行时状态（非 props，随编辑生命周期变化）
 */
const state = reactive({
  /** SQL 智能提示实例；lang=sql 时由 SQLSnippets 提供表/字段补全，其它语言为 null */
  sqlSnippets: null,
  /**
   * 编辑器当前内容的快照，用于与 props.value 比对
   * 避免父组件回写时触发 watch → setValue → 再次 emit 的循环
   */
  contentBackup: null,
  /**
   * 是否正在通过 setValue / watch 程序化写入内容
   * 为 true 时 onDidChangeModelContent 不向父组件 emit，防止脏循环
   */
  isSettingContent: false,
  /**
   * 光标所在位置的 JsonPath 字符串（仅 lang=json 时由 getJsonPath 计算）
   * 供右键「复制 JsonPath」使用
   */
  jsonPath: null,
  /**
   * 传给 monaco.editor.create / createDiffEditor 的默认配置
   * 初始化时与 props.options 合并，运行时可通过 setOptions 再覆盖
   */
  options: {
    /** 编辑器初始文本，与 props.value 同步 */
    value: props.value,
    /** 配色主题：vs / vs-dark / hc-black */
    theme: props.theme,
    /** 是否开启自动索引（历史配置项，具体行为依赖 Monaco 版本） */
    autoIndex: true,
    /** 语法高亮与补全所用的语言 id，与 props.lang 一致 */
    language: props.lang,
    /** Tab 键触发补全 */
    tabCompletion: 'on',
    /** 光标移动时平滑动画 */
    cursorSmoothCaretAnimation: true,
    /** 粘贴时自动格式化 */
    formatOnPaste: true,
    /**
     * 滚轮缩放：触底时把滚轮事件交给外层页面，避免编辑器吃掉滚动
     * 返回 false 表示禁用 Monaco 默认 Ctrl+滚轮缩放
     */
    mouseWheelZoom: function (e) {
      const editor = e.target;
      const isAtBottom = editor.getScrollTop() >= editor.getScrollHeight() - editor.getLayoutInfo().height;
      if (isAtBottom) {
        e.browserEvent.stopPropagation();
      }
      return false;
    },
    /** 是否显示代码折叠控件 */
    folding: true,
    /** 输入时自动补全括号 */
    autoClosingBrackets: 'always',
    /** 覆盖输入时自动补全括号 */
    autoClosingOvertype: 'always',
    /** 输入时自动补全引号 */
    autoClosingQuotes: 'always',
    /** 容器尺寸变化时自动 layout（适配 flex / 抽屉等动态布局） */
    automaticLayout: 'always',
  }
})

/**
 * 创建或重建 Monaco 编辑器
 * - 注册语言与补全（SQL 走 SQLSnippets）
 * - 根据 isDiff 创建单编辑器或 Diff 双栏
 * - 绑定内容变更、自定义右键菜单与光标事件
 */
const initEditor = () => {
  let options = {...state.options, ...props.options}
  if (props.lang === 'xml') {
    ensureXmlFormattingProviders()
  }
  state.sqlSnippets = new SQLSnippets(
      monaco,
      props.onInputField,
      props.onInputTableAlia,
      props.dbs
  )

  monaco.languages.register({id: props.lang})
  monaco.languages.registerCompletionItemProvider(
      props.lang,
      {
        async provideCompletionItems(model, position) {
          let suggestions = []
          switch (props.lang) {
            case "sql":
              return await state.sqlSnippets.provideCompletionItems(model, position)
            default:
              // language = pythonLanguage
              // language.keywords.forEach((item) => {
              //   suggestions.push({
              //     label: item,
              //     kind: monaco.languages.CompletionItemKind.Keyword,
              //     insertText: item
              //   });
              // })
              return {
                // suggestions: cloneDeep(vCompletion),//自定义代码补全
                suggestions: suggestions
              }
          }

        },
        triggerCharacters: ['.'],
      }
  )
  let modEditor
  if (props.isDiff) {
    editor.value = monaco.editor.createDiffEditor(monacoEditorRef.value, options)
    originalEditor.value = monaco.editor.createModel(props.value, props.lang)
    modifiedEditor.value = monaco.editor.createModel(props.oldString, props.lang)
    toRaw(editor.value).setModel({
      original: toRaw(originalEditor.value),
      modified: toRaw(modifiedEditor.value)
    })
    registerCustomEvent(editor.value.getModifiedEditor())
    registerCustomEvent(editor.value.getOriginalEditor())
    toRaw(editor.value.getModifiedEditor()).updateOptions({readOnly: props.readOnly});
    toRaw(editor.value.getOriginalEditor()).updateOptions({readOnly: props.readOnly});

    // setOptions()

  } else {
    if (props.readOnly) {
      options.readOnly = true
    }
    editor.value = monaco.editor.create(monacoEditorRef.value, options)
    modEditor = editor.value
    registerCustomEvent(modEditor)
    modEditor.onDidChangeModelContent(() => {
      if (state.isSettingContent)
        return;
      const content = getValue();
      state.contentBackup = content;
      emit("update:value", content)
    })
  }
}

/** 读取编辑器全文（供父组件 ref 调用或内部同步） */
const getValue = () => {
  return toRaw(editor.value).getValue()
}

/**
 * 用新字符串替换编辑器全部内容
 * 可编辑模式下通过 executeEdits 写入并保留 undo 栈；只读模式直接 setValue
 */
const setValue = (val) => {
  const isReadOnly = toRaw(editor.value).getRawOptions().readOnly;
  if (isReadOnly) {
    toRaw(editor.value).setValue(val)
  } else {
    const undoStack = getModel().undoStack;
    toRaw(editor.value).executeEdits("replaceText", [{
      range: getModel().getFullModelRange(),
      text: val,
      forceMoveMarkers: true
    }]);
    getModel().undoStack = undoStack;
  }
  setLineColor()
}

/** 返回当前选区内的文本；无选区时可能为空字符串 */
const getSelectionValue = () => {
  return toRaw(editor.value).getModel().getValueInRange(toRaw(editor.value).getSelection())
}

/**
 * 在光标处插入文本（有选区则替换选区）
 * 更新 contentBackup 并 emit update:value；Diff 模式与只读场景下不执行
 */
const insertAtCursor = (text) => {
  if (!text || !editor.value || props.isDiff) return
  const ed = toRaw(editor.value)
  const selection = ed.getSelection()
  ed.executeEdits('insertSnippet', [{
    range: selection,
    text,
    forceMoveMarkers: true,
  }])
  ed.focus()
  const content = ed.getValue()
  state.contentBackup = content
  emit('update:value', content)
}

/** 获取当前文档 Model（可访问 undoStack、offset 等底层 API） */
const getModel = () => {
  return toRaw(editor.value).getModel()
}

/** 折叠所有可折叠代码块 */
const foldAll = () => {
  toRaw(editor.value).getAction('editor.foldAll').run()
}

/** 展开所有已折叠代码块 */
const unfoldAll = () => {
  toRaw(editor.value).getAction('editor.unfoldAll').run()
}

/**
 * 为指定编辑器实例注册业务侧扩展能力
 * - JSON：右键复制 JsonPath、光标移动时计算 jsonPath / 上报 offset
 * - SQL：右键「执行」回调 props.executeHandle
 * - 通用：滚轮触底/触顶时事件冒泡给外层滚动容器
 */
const registerCustomEvent = (editor) => {
  if (props.lang === 'json') {
    editor.addAction({
      id: 'json-path', // action unique id
      label: '复制 JsonPath', // action 在右键时展示的名称
      precondition: null,
      keybindingContext: "editorLangId == 'json'",
      contextMenuGroupId: 'navigation',// 右键展示位置
      // keybindings: [
      //   monaco.KeyMod.chord(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyJ)
      // ],
      run: copyToClipboard
    })
  }

  if (props.lang === 'sql') {
    editor.addAction({
      id: 'executeSql', // action unique id
      label: '执行', // action 在右键时展示的名称
      precondition: null,
      keybindingContext: "editorLangId == 'sql'",
      contextMenuGroupId: 'navigation',// 右键展示位置
      run: () => {
        if (props.executeHandle) props.executeHandle()
      }
    })

  }

  editor.onDidChangeCursorPosition((event) => {
    if (!props.isDiff) {
      let value = getValue()
      let offSet = toRaw(getModel()).getOffsetAt(event.position)
      let language = props.lang;

      if (props.value !== value && language === 'json') {
        emit('on-cursor-change', {offSet: offSet})
      }
      if (language === 'json' && offSet !== 0) {
        state.jsonPath = getJsonPath(value, offSet)
        // emit('on-jsonpath-change', {jsonPath: state.jsonPath})
      }
    }
  })

  editor.onMouseWheel((e) => {
    const scrollTop = editor.getScrollTop();
    const scrollHeight = editor.getScrollHeight();
    const clientHeight = editor.getLayoutInfo().height;
    // 获取鼠标滚轮事件信息
    const deltaY = e.deltaY; // 获取滚轮的垂直滚动方向
    if ((deltaY > 0 && scrollTop + clientHeight >= scrollHeight) || (deltaY < 0 && scrollTop === 0)) {
      // 如果触底或触顶，则执行外部容器的滚动事件
      // 可以模拟滚动或者执行其他滚动事件相关的操作
      // 阻止编辑器默认的滚轮事件，以防止冲突
      e.stopPropagation();
      // e.preventDefault()

    }
  });


}

/** JSON 右键菜单：将 state.jsonPath 复制到剪贴板 */
const copyToClipboard = () => {
  if (state.jsonPath) {
    commonFunction().copyText(state.jsonPath, `复制成功 🎉  ${state.jsonPath}`)
  } else {
    $message.warning("没有可复制的路径...");
  }
}

/**
 * 为首行/次行添加高亮装饰（橙色背景）
 * 用于 setValue 后视觉标记变更区域，具体范围目前写死为 1～2 行
 */
const setLineColor = () => {
  toRaw(editor.value).createDecorationsCollection([
    {
      options: {
        // className: 'monaco-content-class',
        isWholeLine: true,
        backgroundColor: '#FFA500'
      },
      // 装饰位置
      range: {
        startColumn: 1,
        endColumn: 30,
        startLineNumber: 1,
        endLineNumber: 2
      }
    }
  ])
}

/**
 * 运行时合并并应用 Monaco 配置项（字体、只读、minimap 等）
 * @param {Object} options 本次要覆盖的选项，会与 props.options 一起传入 updateOptions
 */
const setOptions = (options = {}) => {
  toRaw(editor.value).updateOptions({
    ...props.options,
    ...options,
  });
}

/** 父组件 value 变化时同步到编辑器（与 contentBackup 比较，跳过由本组件触发的回写） */
watch(
    () => props.value,
    (newVal) => {
      if (state.contentBackup !== newVal) {
        try {
          state.isSettingContent = true;
          setValue(newVal)
        } finally {
          state.isSettingContent = false;
        }
        state.contentBackup = newVal;
      }

    },
    {deep: true}
)

/** 语言切换时更新 Model 的 languageId（Diff 模式暂未处理双栏） */
watch(
    () => props.lang,
    (newVal) => {
      if (newVal === 'xml') {
        ensureXmlFormattingProviders()
      }
      if (props.isDiff) {
        // toRaw(editor.value).getOriginalEditor().setModelLanguage(toRaw(editor.value).getOriginalEditor().getModel(), newVal)
        // toRaw(editor.value).getModifiedEditor().setModelLanguage(toRaw(editor.value).getModifiedEditor().getModel(), newVal)
      } else {
        monaco.editor.setModelLanguage(toRaw(editor.value).getModel(), newVal)
      }
    },
    {deep: true}
)
/** 主题变更时全局切换 Monaco 主题 */
watch(
    () => props.theme,
    () => {
      monaco.editor.setTheme(props.theme)

    },
    {deep: true}
)
/** Diff / 普通模式切换时销毁旧实例并重新 initEditor */
watch(
    () => props.isDiff,
    () => {
      toRaw(editor.value)?.dispose()
      initEditor()
    },
    {deep: true}
)
/** Diff 模式：左侧原始文本随 props.oldString 更新 */
watch(
    () => props.oldString,
    (newVal) => {
      toRaw(originalEditor.value).setValue(newVal)
    },
    {deep: true}
)
// watch(
//     () => props.newString,
//     (newVal) => {
//       toRaw(modifiedEditor.value).setValue(newVal)
//     },
//     {deep: true}
// )

/** 只读状态变化时同步到编辑器（单栏 / Diff 双栏） */
watch(
    () => props.readOnly,
    (readOnly) => {
      if (!editor.value) return
      if (props.isDiff) {
        toRaw(editor.value).getModifiedEditor()?.updateOptions({ readOnly })
        toRaw(editor.value).getOriginalEditor()?.updateOptions({ readOnly })
      } else {
        toRaw(editor.value).updateOptions({ readOnly })
      }
    }
)

/** SQL 场景：库表元数据变化时刷新补全数据源 */
watch(
    () => props.dbs,
    () => {
      state.sqlSnippets.setDbSchema(props.dbs)
    },
    {deep: true}
)

/** 当前实例挂载时压入的主题（卸载时据此回退） */
let pushedTheme = null

onMounted(() => {
  initEditor()
  pushedTheme = props.options?.theme ?? props.theme
  if (pushedTheme) {
    mountedEditorThemes.push(pushedTheme)
    monaco.editor.setTheme(pushedTheme)
  }
})

/** 组件卸载时释放编辑器实例，避免内存泄漏 */
onUnmounted(() => {
  toRaw(editor.value)?.dispose()
  if (pushedTheme) {
    const idx = mountedEditorThemes.lastIndexOf(pushedTheme)
    if (idx !== -1) mountedEditorThemes.splice(idx, 1)
    const top = mountedEditorThemes[mountedEditorThemes.length - 1]
    if (top) monaco.editor.setTheme(top)
  }
})

/** 供父组件通过 ref 调用的公开 API */
defineExpose({
  getValue,
  getModel,
  setValue,
  foldAll,
  unfoldAll,
  getSelectionValue,
  insertAtCursor,
})
</script>
<style>
.monaco-editor {
  width: 100%;
  height: 100%;
}

.monaco-content-class {
  background-color: #FFA500;
  opacity: 0.5;
}
</style>
