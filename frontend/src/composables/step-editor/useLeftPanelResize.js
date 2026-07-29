import { ref, onUnmounted } from 'vue'

const STORAGE_KEY = 'autotest-steps-left-panel-width'
const WIDTH_DEFAULT = 350
const WIDTH_MIN = 200
const WIDTH_MAX = 600

/**
 * 左侧步骤树面板拖拽调宽 + 折叠/展开 + localStorage 持久化
 */
export function useLeftPanelResize() {
    const leftPanelWidth = ref(WIDTH_DEFAULT)
    const leftPanelCollapsed = ref(false)
    const leftPanelResizing = ref(false)

    let startX = 0
    let startWidth = WIDTH_DEFAULT

    const clamp = (w) => Math.min(WIDTH_MAX, Math.max(WIDTH_MIN, w))

    const loadWidth = () => {
        try {
            const raw = localStorage.getItem(STORAGE_KEY)
            if (raw == null) return
            const parsed = Number(raw)
            if (!Number.isFinite(parsed)) return
            leftPanelWidth.value = clamp(parsed)
        } catch { /* ignore */ }
    }

    const saveWidth = () => {
        try {
            localStorage.setItem(STORAGE_KEY, String(leftPanelWidth.value))
        } catch { /* ignore */ }
    }

    const onMove = (event) => {
        leftPanelWidth.value = clamp(startWidth + event.clientX - startX)
    }

    const stopResize = () => {
        leftPanelResizing.value = false
        saveWidth()
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', stopResize)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
    }

    const startResize = (event) => {
        if (event.button !== 0) return
        if (event.detail > 1) return
        leftPanelResizing.value = true
        startX = event.clientX
        startWidth = leftPanelWidth.value
        document.body.style.cursor = 'col-resize'
        document.body.style.userSelect = 'none'
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', stopResize)
    }

    const collapse = () => {
        stopResize()
        leftPanelCollapsed.value = true
    }

    const expand = () => {
        leftPanelCollapsed.value = false
    }

    onUnmounted(() => {
        stopResize()
    })

    return {
        leftPanelWidth,
        leftPanelCollapsed,
        leftPanelResizing,
        loadLeftPanelWidth: loadWidth,
        startResizeLeftPanel: startResize,
        collapseLeftPanel: collapse,
        expandLeftPanel: expand,
    }
}
