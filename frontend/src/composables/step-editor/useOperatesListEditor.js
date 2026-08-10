import { computed, reactive, ref } from 'vue'
import api from '@/api'

/** 按 project_id 从应用选项反查应用名（纯函数，供 hydrate 与 composable 共用） */
export const findProjectNameById = (projectOptions, id) => {
    if (id == null || id === '') return ''
    const o = (projectOptions || []).find((x) => x.value === id)
    return o ? String(o.label ?? '').trim() : ''
}

/** 按应用名从应用选项反查 project_id（纯函数，供 hydrate 与 composable 共用） */
export const findProjectIdByName = (projectOptions, name) => {
    const s = String(name ?? '').trim()
    if (!s) return null
    const o = (projectOptions || []).find((x) => String(x.label ?? '').trim() === s)
    return o ? o.value : null
}

/**
 * 数据库 / Redis 步骤的「操作项列表」编辑共享逻辑
 *
 * database_controller 与 redis_controller 的操作项编辑（CRUD、折叠、标题内联编辑、
 * 配置名加载、应用联动）逐行同构，仅以下四处不同，通过参数注入：
 * - operatesField：表单中操作项字典的字段名（database_operates / redis_operates）
 * - labelPrefix：操作项默认标题前缀（数据库请求 / Redis请求）
 * - configType：环境配置类型（database / redis）
 * - emptyOp：空操作项工厂（database 含 desc 且 database_name 默认 ''；redis 无 desc 且默认 '0'）
 *
 * @param {object} options
 * @param {object} options.props          - 组件 props（须含 projectOptions / readonly）
 * @param {object} options.form           - useStepEditorForm 返回的响应式表单
 * @param {string} options.operatesField  - form 中操作项字典的键名
 * @param {string} options.labelPrefix    - 操作项默认标题前缀
 * @param {string} options.configType     - 环境配置类型
 * @param {function} options.emptyOp      - 空操作项工厂函数
 */
export function useOperatesListEditor({
    props,
    form,
    operatesField,
    labelPrefix,
    configType,
    emptyOp,
}) {
    /** 正在编辑卡片标题（item.name）的操作项 key（字符串） */
    const editingOpKey = ref('')
    const opCollapseState = reactive({})
    const configCache = reactive({})
    /** project_id -> 去重后的配置名称列表（与 getEnvConfigNameList 一致） */
    const configNameListByProject = reactive({})

    const projectNameFromId = (id) => findProjectNameById(props.projectOptions, id)
    const projectIdFromName = (name) => findProjectIdByName(props.projectOptions, name)

    const opKeys = computed(() =>
        Object.keys(form[operatesField] || {})
            .map((k) => parseInt(k, 10))
            .filter((n) => !isNaN(n))
            .sort((a, b) => a - b)
    )

    /** 「请求」里各条操作的存储变量名 variable_name（与后端响应列表项匹配） */
    const storageVariableSelectOptions = computed(() => {
        const seen = new Set()
        const opts = []
        for (const k of opKeys.value) {
            const row = form[operatesField][k] || {}
            const vn = String(row.variable_name || '').trim()
            if (!vn || seen.has(vn)) continue
            seen.add(vn)
            opts.push({ label: vn, value: vn })
        }
        return opts
    })

    const ensureCollapseKeys = () => {
        opKeys.value.forEach((k) => {
            if (opCollapseState[k] === undefined) opCollapseState[k] = true
        })
    }

    const toggleOpCollapse = (key) => {
        opCollapseState[key] = !opCollapseState[key]
    }

    const opDefaultTitle = (key) => {
        const i = opKeys.value.indexOf(Number(key))
        const n = i >= 0 ? i + 1 : Number(key) + 1
        return `${labelPrefix} ${n}`
    }

    const opDisplayTitle = (item, key) => {
        const n = String(item?.name ?? '').trim()
        return n || opDefaultTitle(key)
    }

    /** 生成未与当前各条「操作名称」重复的名称（用于新增 / 复制） */
    const nextUniqueOpName = () => {
        const used = new Set()
        for (const k of opKeys.value) {
            const t = String(form[operatesField][k]?.name ?? '').trim()
            if (t) used.add(t)
        }
        let n = 1
        let candidate = `${labelPrefix} ${n}`
        while (used.has(candidate)) {
            n += 1
            candidate = `${labelPrefix} ${n}`
        }
        return candidate
    }

    const startEditOpTitle = (key) => {
        if (props.readonly) return
        editingOpKey.value = String(key)
    }

    const endEditOpTitle = () => {
        editingOpKey.value = ''
    }

    const loadConfigsForProject = async (projectId, force = false) => {
        const pid = projectId != null ? Number(projectId) : null
        if (!pid) return []
        if (configCache[pid] && !force) return configCache[pid]
        try {
            const [resNames, res] = await Promise.all([
                api.getEnvConfigNameList({ project_id: pid, env_type: configType }),
                api.searchEnvConfig({
                    project_id: pid,
                    env_type: configType,
                    page: 1,
                    page_size: 500,
                    state: 0
                })
            ])
            const nameList = Array.isArray(resNames?.data) ? resNames.data : []
            configNameListByProject[pid] = nameList
            const rows = Array.isArray(res?.data) ? res.data : []
            configCache[pid] = rows
            return rows
        } catch (e) {
            console.error(`加载${labelPrefix}配置失败`, e)
            configNameListByProject[pid] = []
            configCache[pid] = []
            return []
        }
    }

    const configOptionsForRow = (item) => {
        const pid = item?.project_id
        const fromList = configNameListByProject[pid]
        if (Array.isArray(fromList) && fromList.length) {
            return fromList.map((name) => ({ label: name, value: name }))
        }
        const rows = configCache[pid] || []
        const names = [...new Set(rows.map((r) => r.config_name).filter(Boolean))]
        return names.map((label) => ({ label, value: label }))
    }

    const addOp = () => {
        editingOpKey.value = ''
        const keys = opKeys.value
        const newKey = keys.length ? Math.max(...keys) + 1 : 0
        const row = emptyOp()
        row.name = nextUniqueOpName()
        form[operatesField][newKey] = row
        opCollapseState[newKey] = false
    }

    const removeOp = (key) => {
        const k = String(key)
        if (editingOpKey.value === k) editingOpKey.value = ''
        delete form[operatesField][k]
        delete opCollapseState[k]
    }

    const duplicateOp = (key) => {
        const row = form[operatesField][key]
        if (!row) return
        editingOpKey.value = ''
        const keys = opKeys.value
        const newKey = keys.length ? Math.max(...keys) + 1 : 0
        form[operatesField][newKey] = {
            ...row,
            name: nextUniqueOpName()
        }
        opCollapseState[newKey] = false
    }

    const onProjectChange = async (item) => {
        item.project_name = projectNameFromId(item.project_id) || ''
        item.config_name = ''
        item.database_name = emptyOp().database_name
        if (item.project_id) await loadConfigsForProject(item.project_id, true)
    }

    const onConfigNameChange = async (item) => {
        const pid = item.project_id
        if (!pid) return
        const rows = await loadConfigsForProject(pid)
        const names = [
            ...new Set(
                rows.filter((r) => r.config_name === item.config_name).map((r) => r.database_name).filter(Boolean)
            )
        ]
        if (names.length === 1) {
            item.database_name = names[0]
        }
    }

    return {
        editingOpKey,
        opCollapseState,
        configCache,
        configNameListByProject,
        opKeys,
        storageVariableSelectOptions,
        ensureCollapseKeys,
        toggleOpCollapse,
        opDefaultTitle,
        opDisplayTitle,
        nextUniqueOpName,
        startEditOpTitle,
        endEditOpTitle,
        projectNameFromId,
        projectIdFromName,
        loadConfigsForProject,
        configOptionsForRow,
        addOp,
        removeOp,
        duplicateOp,
        onProjectChange,
        onConfigNameChange,
    }
}
