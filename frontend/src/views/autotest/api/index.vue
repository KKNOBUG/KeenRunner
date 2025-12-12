<template>
  <AppPage>
    <n-grid :cols="24" :x-gap="16">
      <n-gi :span="7">
        <n-card size="small" hoverable>
          <template #header>
            <div class="step-header">
              <span class="step-count">{{ totalStepsCount }}个步骤</span>
              <n-button
                  text
                  size="small"
                  @click="toggleAllExpand"
                  class="collapse-btn"
              >
                <template #icon>
                  <TheIcon
                      :icon="isAllExpanded ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"/>
                </template>
              </n-button>
            </div>
          </template>
          <div class="step-tree-container">
            <div
                v-for="(step, index) in steps"
                :key="step.id"
                class="step-item"
                :class="{ 'is-selected': selectedKeys.includes(step.id) }"
                :draggable="true"
                @dragstart="handleDragStart($event, step.id, null, index)"
                @dragover.prevent="handleDragOver($event)"
                @drop="handleDrop($event, step.id, null, index)"
                @click="handleSelect([step.id])"
            >
              <div class="step-item-distance">
                  <span class="step-name" :title="step.name">
                    <TheIcon
                        :icon="getStepIcon(step.type)"
                        :size="18"
                        class="step-icon"
                        :class="getStepIconClass(step.type)"
                    />
                    <span class="step-name-text">{{ getStepDisplayName(step.name, step.id) }}</span>
                    <span class="step-actions">
                      <span class="step-number">#{{ getStepNumber(step.id) }}</span>
                      <n-button
                          text
                          size="tiny"
                          @click.stop="handleCopyStep(step.id)"
                          class="action-btn"
                      >
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="16"/>
                        </template>
                      </n-button>
                      <n-popconfirm @positive-click="handleDeleteStep(step.id)" @click.stop>
                        <template #trigger>
                          <n-button text size="tiny" type="error" class="action-btn">
                            <template #icon>
                              <TheIcon icon="material-symbols:delete" :size="16"/>
                            </template>
                          </n-button>
                        </template>
                        确认删除该步骤?
                      </n-popconfirm>
                    </span>
                    </span>
                <div v-if="stepDefinitions[step.type]?.allowChildren">
                  <div
                      v-for="(child, childIndex) in step.children"
                      :key="child.id"
                      class="step-item"
                      :class="{ 'is-selected': selectedKeys.includes(child.id) }"
                      :draggable="true"
                      @dragstart.stop="handleDragStart($event, child.id, step.id, childIndex)"
                      @dragover.prevent.stop="handleDragOver($event)"
                      @drop.stop="handleDrop($event, child.id, step.id, childIndex)"
                      @click.stop="handleSelect([child.id])"
                  >
                    <div class="step-item-child">
                        <span class="step-name" :title="child.name">
                          <TheIcon
                              :icon="getStepIcon(child.type)"
                              :size="18"
                              class="step-icon"
                              :class="getStepIconClass(child.type)"
                          />
                          <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
                          <span class="step-actions">
                            <span class="step-number">#{{ getStepNumber(child.id) }}</span>
                            <n-button text size="tiny" @click.stop="handleCopyStep(child.id)" class="action-btn">
                              <template #icon>
                                <TheIcon icon="material-symbols:content-copy" :size="16"/>
                              </template>
                            </n-button>
                            <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
                              <template #trigger>
                                <n-button text size="tiny" type="error" class="action-btn">
                                  <template #icon>
                                    <TheIcon icon="material-symbols:delete" :size="14"/>
                                  </template>
                                </n-button>
                              </template>
                              确认删除该步骤?
                            </n-popconfirm>
                          </span>
                      </span>
                    </div>
                  </div>
                  <div class="step-add-btn">
                    <n-dropdown
                        trigger="click"
                        :options="addOptions"
                        :render-label="renderDropdownLabel"
                        @select="(key) => handleAddStep(key, step.id)"
                    >
                      <n-button dashed size="small" class="add-step-btn" @click.stop>添加步骤</n-button>
                    </n-dropdown>
                  </div>
                </div>
              </div>
            </div>
            <n-dropdown
                trigger="click"
                :options="addOptions"
                :render-label="renderDropdownLabel"
                @select="(key) => handleAddStep(key, null)"
            >
              <n-button dashed size="small" class="add-step-btn">添加步骤</n-button>
            </n-dropdown>
          </div>
        </n-card>
      </n-gi>
      <n-gi :span="17">
        <n-card :title="currentStepTitle" size="small" hoverable>
          <component
              v-if="currentStep"
              :is="editorComponent"
              :config="currentStep.config"
              @update:config="(val) => updateStepConfig(currentStep.id, val)"
          />
          <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
        </n-card>
      </n-gi>
    </n-grid>
  </AppPage>
</template>

<script setup>
import {computed, h, ref, onMounted, nextTick, watch, onUpdated} from 'vue'
import {NButton, NCard, NDropdown, NEmpty, NGi, NGrid, NPopconfirm} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import AppPage from "@/components/page/AppPage.vue";
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";

const stepDefinitions = {
  loop: {label: '循环结构', allowChildren: true, icon: 'streamline:arrow-reload-horizontal-2'},
  code: {label: '执行代码', allowChildren: false, icon: 'teenyicons:python-outline'},
  http: {label: 'HTTP 请求', allowChildren: false, icon: 'streamline-freehand:worldwide-web-network-www'},
  if: {label: '分支条件', allowChildren: true, icon: 'tabler:arrow-loop-right-2'},
  wait: {label: '等待控制', allowChildren: false, icon: 'meteor-icons:alarm-clock'},
  database: {label: '数据库请求', allowChildren: false, icon: 'material-symbols:database-search-outline'}
}

const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  http: ApiHttpEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor
}

let seed = 1000
const genId = () => `step-${seed++}`

const buildDefaultSteps = () => ([
  {
    id: genId(),
    type: 'loop',
    name: '循环 3 次',
    config: {mode: 'times', times: 3, interval: 0},
    children: [
      {
        id: genId(),
        type: 'code',
        name: '执行代码 - 创建随机变量1',
        config: {}
      }
    ]
  },
  {
    id: genId(),
    type: 'http',
    name: '登录ZERORUNNER系统',
    config: {}
  },
  {
    id: genId(),
    type: 'if',
    name: 'If ${token} not_none',
    config: {left: '${token}', operator: 'not_empty', remark: '判断token是否获取成功'},
    children: [
      {id: genId(), type: 'code', name: '执行代码—创建随机变量2', config: {}},
      {id: genId(), type: 'wait', name: 'Wait 等待 2 秒', config: {seconds: 2}},
      {id: genId(), type: 'http', name: 'AP POST 查询测试用例信息列表', config: {}}
    ]
  }
])

const steps = ref(buildDefaultSteps())
const selectedKeys = ref([steps.value[0]?.id].filter(Boolean))
const dragState = ref({draggingId: null, dragOverId: null, dragOverParent: null, dragOverIndex: null})

const addOptions = Object.entries(stepDefinitions).map(([value, item]) => ({
  label: item.label,
  key: value,
  icon: item.icon
}))

// 计算总步骤数（包括子步骤）
const totalStepsCount = computed(() => {
  const countSteps = (list) => {
    let count = 0
    for (const step of list) {
      count++
      if (step.children && step.children.length) {
        count += countSteps(step.children)
      }
    }
    return count
  }
  return countSteps(steps.value)
})

// 判断是否全部展开（简化处理，这里假设总是展开的）
const isAllExpanded = ref(true)

const toggleAllExpand = () => {
  // 这里可以实现折叠/展开逻辑，暂时简化处理
  isAllExpanded.value = !isAllExpanded.value
}

const findStep = (id, list = steps.value) => {
  for (const step of list) {
    if (step.id === id) return step
    if (step.children && step.children.length) {
      const found = findStep(id, step.children)
      if (found) return found
    }
  }
  return null
}

const findStepParent = (id, list = steps.value, parent = null) => {
  for (const step of list) {
    if (step.id === id) return parent
    if (step.children && step.children.length) {
      const found = findStepParent(id, step.children, step)
      if (found !== null) return found
    }
  }
  return null
}

const handleSelect = (keys) => {
  selectedKeys.value = keys
}

const currentStep = computed(() => {
  const key = selectedKeys.value?.[0]
  if (!key) return null
  return findStep(key)
})

const editorComponent = computed(() => {
  const step = currentStep.value
  if (!step) return null
  return editorMap[step.type] || null
})

const currentStepTitle = computed(() => {
  if (!currentStep.value) return '步骤配置'
  return stepDefinitions[currentStep.value.type]?.label || '步骤配置'
})

const insertStep = (parentId, type, index = null) => {
  const def = stepDefinitions[type]
  if (!def) return null
  const newStep = {
    id: genId(),
    type,
    name: `${def.label}-${new Date().getTime()}`,
    config: {},
    children: def.allowChildren ? [] : undefined
  }
  if (!parentId) {
    // 添加到根级别
    if (index !== null) {
      steps.value.splice(index, 0, newStep)
    } else {
      steps.value.push(newStep)
    }
    return newStep
  }
  // 添加到父步骤的子级
  const parent = findStep(parentId)
  if (parent && stepDefinitions[parent.type]?.allowChildren) {
    // 父步骤允许有子步骤，添加到其children中
    parent.children = parent.children || []
    if (index !== null) {
      parent.children.splice(index, 0, newStep)
    } else {
      parent.children.push(newStep)
    }
    return newStep
  }
  return null
}

const handleAddStep = (type, parentId) => {
  // 如果parentId存在，说明是要添加到某个父步骤的子级
  // 如果parentId为null，说明是要添加到根级别
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    // 更新显示名称
    updateStepDisplayNames()
  }
}

const removeStep = (id, list = steps.value) => {
  const idx = list.findIndex(item => item.id === id)
  if (idx !== -1) {
    list.splice(idx, 1)
    return true
  }
  for (const item of list) {
    if (item.children && item.children.length) {
      const removed = removeStep(id, item.children)
      if (removed) return true
    }
  }
  return false
}

const handleDeleteStep = (id) => {
  removeStep(id)
  if (selectedKeys.value[0] === id) {
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  }
}

const handleCopyStep = (id) => {
  const step = findStep(id)
  if (!step) return
  const copiedStep = JSON.parse(JSON.stringify(step))
  copiedStep.id = genId()
  copiedStep.name = `${copiedStep.name} (副本)`
  // 递归更新子步骤ID
  const updateIds = (node) => {
    node.id = genId()
    if (node.children && node.children.length) {
      node.children.forEach(updateIds)
    }
  }
  updateIds(copiedStep)

  const parent = findStepParent(id)
  if (parent) {
    const parentStep = findStep(parent.id)
    if (parentStep && parentStep.children) {
      const index = parentStep.children.findIndex(s => s.id === id)
      parentStep.children.splice(index + 1, 0, copiedStep)
    }
  } else {
    const index = steps.value.findIndex(s => s.id === id)
    steps.value.splice(index + 1, 0, copiedStep)
  }
  selectedKeys.value = [copiedStep.id]
}

const updateStepConfig = (id, config) => {
  const step = findStep(id)
  if (step) {
    step.config = {...step.config, ...config}
    // 根据配置更新步骤名称
    if (step.type === 'loop') {
      if (config.mode === 'times') {
        step.name = `Loop 循环 ${config.times || 3} 次`
      } else if (config.mode === 'for') {
        step.name = `Loop For ${config.forVar || 'i'}`
      } else {
        step.name = `Loop 条件循环`
      }
    } else if (step.type === 'http') {
      const method = config.method || 'POST'
      const name = config.name || 'HTTP请求'
      step.name = `API ${method} ${name}`
    } else if (step.type === 'if') {
      const left = config.left || ''
      const operator = config.operator || 'not_empty'
      const operatorMap = {
        'not_empty': 'not_none',
        'empty': 'is_none',
        'eq': '==',
        'ne': '!='
      }
      step.name = `If ${left} ${operatorMap[operator] || operator}`
    } else if (step.type === 'wait') {
      step.name = `Wait 等待 ${config.seconds || 2} 秒`
    } else if (step.type === 'code') {
      step.name = config.name || '执行代码'
    }
    // 更新显示名称
    updateStepDisplayNames()
  }
}

const getStepIcon = (type) => {
  return stepDefinitions[type]?.icon || 'material-symbols:code'
}

const getStepIconClass = (type) => {
  const classMap = {
    loop: 'icon-loop',
    code: 'icon-code',
    http: 'icon-http',
    if: 'icon-if',
    wait: 'icon-wait'
  }
  return classMap[type] || ''
}

// 拖拽相关
const handleDragStart = (event, stepId, parentId, index) => {
  dragState.value.draggingId = stepId
  dragState.value.dragOverParent = parentId
  dragState.value.dragOverIndex = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', stepId)
}

const handleDragOver = (event) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
}

const handleDrop = (event, targetId, targetParentId, targetIndex) => {
  event.preventDefault()
  const draggingId = dragState.value.draggingId
  if (!draggingId || draggingId === targetId) return

  const draggingStep = findStep(draggingId)
  if (!draggingStep) return

  // 移除原位置的步骤
  const removeFromList = (list, id) => {
    const idx = list.findIndex(item => item.id === id)
    if (idx !== -1) {
      list.splice(idx, 1)
      return true
    }
    for (const item of list) {
      if (item.children && item.children.length) {
        if (removeFromList(item.children, id)) return true
      }
    }
    return false
  }

  // 移除原位置
  removeFromList(steps.value, draggingId)

  // 插入到新位置
  if (targetParentId) {
    const parent = findStep(targetParentId)
    if (parent && parent.children) {
      const insertIndex = targetIndex !== null ? targetIndex : parent.children.length
      parent.children.splice(insertIndex, 0, draggingStep)
    }
  } else {
    const insertIndex = targetIndex !== null ? targetIndex : steps.value.length
    steps.value.splice(insertIndex, 0, draggingStep)
  }

  dragState.value = {draggingId: null, dragOverId: null, dragOverParent: null, dragOverIndex: null}
}

// 计算步骤编号（按深度优先遍历）
const stepNumberMap = computed(() => {
  const map = new Map()
  let counter = 0

  const traverse = (list) => {
    for (const step of list) {
      counter++
      map.set(step.id, counter)
      if (step.children && step.children.length) {
        traverse(step.children)
      }
    }
  }

  traverse(steps.value)
  return map
})

const getStepNumber = (stepId) => {
  return stepNumberMap.value.get(stepId) || 0
}

// 存储每个步骤的显示名称（用于中间省略）
const stepDisplayNames = ref(new Map())

// 计算文本中间省略（保留开头和结尾）
const truncateTextMiddle = (text, maxChars = 20) => {
  if (!text || text.length <= maxChars) return text
  // 计算开头和结尾的长度（为省略号留出空间）
  const halfLen = Math.floor((maxChars - 3) / 2)
  const start = text.substring(0, halfLen)
  const end = text.substring(text.length - halfLen)
  return `${start}...${end}`
}

// 获取步骤显示名称（中间省略）
const getStepDisplayName = (name, stepId) => {
  if (!name) return ''
  // 如果已经计算过，返回计算后的名称
  if (stepDisplayNames.value.has(stepId)) {
    return stepDisplayNames.value.get(stepId)
  }
  // 如果还没有计算过，先进行简单处理
  const maxDisplayLength = 22
  if (name.length > maxDisplayLength) {
    return truncateTextMiddle(name, maxDisplayLength)
  }
  return name
}

// 更新步骤显示名称（根据容器宽度动态计算）
const updateStepDisplayNames = () => {
  nextTick(() => {
    const nameMap = new Map()
    // 考虑到操作按钮的宽度（步骤编号 + 复制 + 删除按钮），设置合理的文本长度限制
    // 操作按钮大约需要 80-100px，文本区域大约可以显示 20-25 个字符
    const maxDisplayLength = 22

    const updateNames = (list) => {
      for (const step of list) {
        const stepName = step.name || ''
        // 根据步骤名称长度决定是否需要中间省略
        if (stepName.length > maxDisplayLength) {
          nameMap.set(step.id, truncateTextMiddle(stepName, maxDisplayLength))
        } else {
          nameMap.set(step.id, stepName)
        }
        if (step.children && step.children.length) {
          updateNames(step.children)
        }
      }
    }
    updateNames(steps.value)
    stepDisplayNames.value = nameMap
  })
}

// 监听steps变化，更新显示名称
watch(() => steps.value, () => {
  updateStepDisplayNames()
}, { deep: true })

onMounted(() => {
  updateStepDisplayNames()
})

onUpdated(() => {
  // 组件更新后重新计算显示名称
  updateStepDisplayNames()
})

const renderDropdownLabel = (option) => {
  const iconClass = getStepIconClass(option.key)
  return h('div', {style: {display: 'flex', alignItems: 'center', gap: '8px'}}, [
    h(TheIcon, {
      icon: option.icon,
      size: 16,
      class: ['step-icon', iconClass]
    }),
    h('span', option.label)
  ])
}
</script>

<style scoped>
.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
}

.step-count {
  font-weight: 600;
  font-size: 14px;
}

.collapse-btn {
  padding: 4px;
}

.step-tree-container {
  padding: 8px 0;
}

.step-name {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  font-size: 14px;
  font-weight: 300;
  background-color: #f5f5f5;
  padding: 8px 8px;
  border-radius: 10px;
  box-sizing: border-box;
  position: relative;
  min-width: 0; /* 允许flex子元素收缩 */
}

.step-name:hover {
  color: #F4511E; /* 字体变为红色 */
}

.step-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  /* 确保文本不会挤压操作按钮 */
  margin-right: auto;
  /* 为操作按钮预留空间 */
  padding-right: 8px;
  /* 文本显示：由于已经在JavaScript中处理了中间省略，这里不需要text-overflow */
  display: inline-block;
}

.step-actions {
  display: none;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  margin-left: auto;
  padding-left: 8px;
}

.step-name:hover .step-actions {
  display: flex;
}

.step-number {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-right: 4px;
}

.step-item {
  border: 1px solid transparent;
  border-radius: 10px;
  transition: all .2s;
  cursor: pointer;
  padding-top: 5px;
  padding-bottom: 5px;
}

.step-item.is-selected {
  /* 红色虚线外轮廓：宽度 + 样式 + 颜色 */
  border: 1px dashed #F4511E; /* 匹配背景色的红色虚线 */
}

.step-item[draggable="true"] {
  cursor: move;
}


.step-item-child {
  padding-left: 12px;
  padding-right: 12px;
}

.step-item-distance {
  padding-bottom: 5px;
}


.step-add-btn {
  padding-top: 5px;
  padding-left: 12px;
  padding-right: 12px;
}

.step-icon {
  font-size: 18px;
  flex-shrink: 0;
  align-items: center;
}

.step-icon.icon-loop {
  color: #F4511E;
}

.step-icon.icon-code {
  color: #3363e0;
}

.step-icon.icon-http {
  color: #3363e0;
}

.step-icon.icon-if {
  color: #F4511E;
  /*
  transform: rotate(90deg);
  关键：确保旋转生效（行内元素默认不支持transform）
  display: inline-block; 或 block/flex，根据布局调整
   */
}

.step-icon.icon-wait {
  color: #48d024;
}

.action-btn {
  padding: 2px 1px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.action-btn:hover {
  opacity: 1;
}

/* 下拉菜单中的图标样式 */
:deep(.n-dropdown-menu .step-icon) {
  flex-shrink: 0;
}

.add-step-btn {
  width: 100%;
  margin-bottom: 10px;
}

</style>
