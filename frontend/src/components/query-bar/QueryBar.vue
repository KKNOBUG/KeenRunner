<template>
  <div
      bg="#fafafc"
      min-h-60
      flex
      items-start
      justify-between
      b-1
      rounded-8
      p-15
      bc-ccc
      dark:bg-black
  >
    <!-- 与操作按钮 size=small（heightSmall 28px）对齐：表单控件默认 medium 改为同高 -->
    <n-config-provider abstract :theme-overrides="queryBarThemeOverrides">
      <n-space wrap align="center" :size="[35, 15]">
        <slot />
        <div v-if="hasAnyAction" flex items-center :class="actionMode === 'inline' ? 'gap-20' : ''">
          <template v-if="actionMode === 'inline'">
            <n-button v-if="addReset" secondary type="primary" size="small" @click="emit('reset')">
              重置
            </n-button>
            <n-button v-if="addSearch" secondary type="primary" size="small" @click="emit('search')">
              搜索
            </n-button>
            <n-button v-if="addCreate" secondary type="primary" size="small" @click="emit('create')">
              新增
            </n-button>
            <n-button v-if="addDelete" secondary type="primary" size="small" @click="emit('delete')">
              删除
            </n-button>
          </template>
          <n-dropdown
              v-else
              trigger="click"
              :options="dropdownOptions"
              @select="onDropdownSelect"
          >
            <n-button secondary type="primary" size="small">
              <span inline-flex items-center gap-6>
                <TheIcon icon="material-symbols:more-horiz" :size="16" />
                操作
              </span>
            </n-button>
          </n-dropdown>
        </div>
      </n-space>
    </n-config-provider>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NButton, NConfigProvider, NDropdown, NSpace } from 'naive-ui'
import { renderIcon } from '@/utils'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  /** 显示「重置」 */
  addReset: { type: Boolean, default: true },
  /** 显示「搜索」 */
  addSearch: { type: Boolean, default: true },
  /** 显示「新增」 */
  addCreate: { type: Boolean, default: false },
  /** 显示「删除」 */
  addDelete: { type: Boolean, default: false },
  /**
   * 操作区布局：inline 平铺；dropdown 合并为「更多」下拉
   */
  actionMode: {
    type: String,
    default: 'inline',
    validator: (v) => ['inline', 'dropdown'].includes(v),
  },
})

const emit = defineEmits(['search', 'reset', 'create', 'delete'])

/** 与 naive common heightSmall（28px）一致，使默认 medium 的输入/选择与 small 按钮同高 */
const queryBarThemeOverrides = {
  Input: {
    heightMedium: '28px',
    fontSizeMedium: '14px',
  },
  InternalSelection: {
    heightMedium: '28px',
    fontSizeMedium: '14px',
  },
}

const hasAnyAction = computed(
    () => props.addReset || props.addSearch || props.addCreate || props.addDelete
)

const dropdownOptions = computed(() => {
  const opts = []
  if (props.addReset) {
    opts.push({
      label: '重置',
      key: 'reset',
      icon: renderIcon('material-symbols:restart-alt', { size: 16 }),
    })
  }
  if (props.addSearch) {
    opts.push({
      label: '搜索',
      key: 'search',
      icon: renderIcon('material-symbols:search', { size: 16 }),
    })
  }
  if (props.addCreate) {
    opts.push({
      label: '新增',
      key: 'create',
      icon: renderIcon('material-symbols:add', { size: 16 }),
    })
  }
  if (props.addDelete) {
    opts.push({
      label: '删除',
      key: 'delete',
      icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
    })
  }
  return opts
})

function onDropdownSelect(key) {
  if (key === 'reset') emit('reset')
  else if (key === 'search') emit('search')
  else if (key === 'create') emit('create')
  else if (key === 'delete') emit('delete')
}
</script>
