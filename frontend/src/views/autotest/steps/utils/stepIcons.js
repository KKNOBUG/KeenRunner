/**
 * 步骤树图标集中配置：步骤类型图标、「添加步骤」菜单专属图标与树内操作图标统一在此维护，替换图标只改本文件。
 * 消费方：steps/index.vue（stepDefinitions / 树内操作按钮）、RecursiveStepChildren.vue、AddStepPopover.vue
 */

/**
 * 步骤类型 → iconify 图标名
 * 顺序与 backend/enums/autotest_enum.py AutoTestStepType 一致；步骤树叶子图标与「添加步骤」菜单共用
 */
export const STEP_TYPE_ICONS = {
    user_variables: 'gravity-ui:magic-wand', // 用户变量
    if: 'gravity-ui:shuffle', // 条件分支
    wait: 'gravity-ui:alarm', // 等待控制
    loop: 'gravity-ui:arrows-rotate-right', // 循环结构
    tcp: 'gravity-ui:abbr-api', // TCP请求
    http: 'gravity-ui:abbr-api', // HTTP请求（与 TCP 共用同一云服务图标）
    code: 'fluent:code-py-16-filled', // 代码请求(Python)
    database: 'gravity-ui:abbr-sql', // 数据库请求
    redis: 'carbon:database-redis', // Redis请求
    quote_public_script: 'gravity-ui:route', // 引用公共脚本
    quote_public_api: 'gravity-ui:plug-connection', // 引用公共接口
    assert: 'gravity-ui:list-check', // 断言
    extract: 'gravity-ui:list-check-lock', // 提取
}

/**
 * 「添加步骤」菜单专属动作项 → iconify 图标名（非步骤类型，仅出现在 AddStepPopover 菜单）
 */
export const ADD_STEP_MENU_ICONS = {
    copy_steps: 'gravity-ui:copy', // 复制指定脚本
    batch_upload_datasource: 'gravity-ui:arrow-up-from-square', // 批量上传数据源
    summary_download_datasource: 'gravity-ui:arrow-down-to-square', // 汇总下载数据源
    template_download_datasource: 'gravity-ui:arrow-down-to-square', // 下载所有的模板（与汇总下载共用）
}

/** 步骤类型 → 图标着色类名（颜色统一定义见 styles/autotest-theme.scss「步骤图标着色」节，页面内不得本地重定义） */
export const STEP_TYPE_ICON_CLASSES = {
    user_variables: 'icon-user_variables', // 用户变量
    if: 'icon-if', // 条件分支
    wait: 'icon-wait', // 等待控制
    loop: 'icon-loop', // 循环结构
    tcp: 'icon-tcp', // TCP请求
    http: 'icon-http', // HTTP请求
    code: 'icon-code', // 代码请求(Python)
    database: 'icon-database', // 数据库请求
    redis: 'icon-redis', // Redis请求
    quote_public_script: 'icon-quote', // 引用公共脚本
    quote_public_api: 'icon-quote', // 引用公共接口（与脚本共用引用色）
    assert: 'icon-assert', // 断言
    extract: 'icon-extract', // 提取
}

/**
 * 「添加步骤」菜单专属动作项 → 图标着色类名（与 ADD_STEP_MENU_ICONS 一一对应）
 */
export const ADD_STEP_MENU_ICON_CLASSES = {
    copy_steps: 'icon-quote', // 复制指定脚本（复用引用色）
    batch_upload_datasource: 'icon-datasource', // 批量上传数据源
    summary_download_datasource: 'icon-datasource', // 汇总下载数据源
    template_download_datasource: 'icon-datasource', // 下载所有的模板
}

/**
 * 步骤树操作图标
 */
export const STEP_TREE_ACTION_ICONS = {
    /** 树卡片头部「展开/折叠全部」开关 */
    toggleAll: {expanded: 'gravity-ui:chevron-up', collapsed: 'gravity-ui:chevron-down'},
    /** 单个步骤 / 引用步骤 / 分支组的展开折叠 */
    expand: {expanded: 'gravity-ui:chevron-up', collapsed: 'gravity-ui:chevron-down'},
    /** 注释(跳过执行)/恢复执行 */
    skip: {skipped: 'gravity-ui:eye', normal: 'gravity-ui:eye-slash'},
    /** 复制当前步骤 */
    copy: 'gravity-ui:copy',
    /** 删除当前步骤 */
    remove: 'gravity-ui:trash-bin',
}

/** 步骤类型对应的图标名（未知类型回退到通用代码图标） */
export const getStepTypeIcon = (type) => STEP_TYPE_ICONS[type] || 'gravity-ui:terminal-line'

/** 步骤类型对应的图标 CSS 类名（未知类型不着色） */
export const getStepTypeIconClass = (type) => STEP_TYPE_ICON_CLASSES[type] || ''

/** 展开/折叠状态对应的图标名 */
export const stepExpandIcon = (expanded) => (expanded ? STEP_TREE_ACTION_ICONS.expand.expanded : STEP_TREE_ACTION_ICONS.expand.collapsed)

/** 注释(跳过)状态对应的图标名 */
export const stepSkipIcon = (skipped) => (skipped ? STEP_TREE_ACTION_ICONS.skip.skipped : STEP_TREE_ACTION_ICONS.skip.normal)

/** 「展开/折叠全部」开关状态对应的图标名 */
export const toggleAllExpandIcon = (expanded) => (expanded ? STEP_TREE_ACTION_ICONS.toggleAll.expanded : STEP_TREE_ACTION_ICONS.toggleAll.collapsed)
