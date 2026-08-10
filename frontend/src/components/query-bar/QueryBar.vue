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
          <!-- 平铺：各操作独立按钮 -->
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

          <!-- 分裂按钮：左搜索 / 右更多；无搜索或无更多项时自动降级 -->
          <template v-else-if="actionMode === 'split'">
            <n-button-group v-if="addSearch && hasMoreMenuItems" size="small" class="query-bar-split">
              <n-button secondary type="primary" class="query-bar-split__main" @click="emit('search')">
                <span inline-flex items-center gap-4>
                  <TheIcon icon="material-symbols:search" :size="16" />
                  搜索
                </span>
              </n-button>
              <n-dropdown trigger="click" :options="moreMenuOptions" @select="onDropdownSelect">
                <n-button
                    secondary
                    type="primary"
                    class="query-bar-split__caret"
                    title="更多操作"
                    aria-label="更多操作"
                >
                  <TheIcon icon="material-symbols:expand-more" :size="16" />
                </n-button>
              </n-dropdown>
            </n-button-group>
            <n-button
                v-else-if="addSearch"
                secondary
                type="primary"
                size="small"
                @click="emit('search')"
            >
              <span inline-flex items-center gap-4>
                <TheIcon icon="material-symbols:search" :size="16" />
                搜索
              </span>
            </n-button>
            <n-dropdown
                v-else-if="hasMoreMenuItems"
                trigger="click"
                :options="moreMenuOptions"
                @select="onDropdownSelect"
            >
              <n-button secondary type="primary" size="small" title="更多操作">
                <span inline-flex items-center gap-6>
                  <TheIcon icon="material-symbols:more-horiz" :size="16" />
                  更多
                </span>
              </n-button>
            </n-dropdown>
          </template>

          <!-- 兼容：全部收纳进下拉（含搜索） -->
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
        <!-- 与操作区同排：如路由页的「刷新API」 -->
        <slot name="afterActions" />
      </n-space>
    </n-config-provider>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NButton, NButtonGroup, NConfigProvider, NDropdown, NSpace } from 'naive-ui'
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
   * 操作区布局：
   * inline 平铺；
   * split 左搜索+右更多（默认）；
   * dropdown 全部收纳进下拉（含搜索）
   */
  actionMode: {
    type: String,
    default: 'split',
    validator: (v) => ['inline', 'split', 'dropdown'].includes(v),
  },
  /**
   * 追加的自定义项：[{ label, key, icon?, disabled? }]
   * 选中后通过 action 事件回传 key
   */
  extraActions: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['search', 'reset', 'create', 'delete', 'action'])

/** 与 naive common heightSmall（28px）一致，使默认 medium 的输入/选择与 small 按钮同高 */
const queryBarThemeOverrides = {
  Input: {
    heightMedium: '28px',
    fontSizeMedium: '13px',
  },
  InternalSelection: {
    heightMedium: '28px',
    fontSizeMedium: '13px',
  },
}

const hasAnyAction = computed(
    () =>
      props.addReset ||
      props.addSearch ||
      props.addCreate ||
      props.addDelete ||
      (Array.isArray(props.extraActions) && props.extraActions.length > 0)
)

/** 除搜索外的菜单项（split 右侧下拉） */
const moreMenuOptions = computed(() => {
  const opts = []
  if (props.addReset) {
    opts.push({
      label: '重置',
      key: 'reset',
      icon: renderIcon('material-symbols:restart-alt', { size: 16 }),
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
  for (const item of props.extraActions || []) {
    if (!item?.key || !item?.label) continue
    opts.push({
      label: item.label,
      key: item.key,
      icon: item.icon,
      disabled: item.disabled,
    })
  }
  return opts
})

const hasMoreMenuItems = computed(() => moreMenuOptions.value.length > 0)

/** dropdown 模式：含搜索的全量菜单 */
const dropdownOptions = computed(() => {
  const opts = []
  if (props.addSearch) {
    opts.push({
      label: '搜索',
      key: 'search',
      icon: renderIcon('material-symbols:search', { size: 16 }),
    })
  }
  return [...opts, ...moreMenuOptions.value]
})

function onDropdownSelect(key) {
  if (key === 'reset') emit('reset')
  else if (key === 'search') emit('search')
  else if (key === 'create') emit('create')
  else if (key === 'delete') emit('delete')
  else emit('action', key)
}
</script>

<style scoped>
.query-bar-split :deep(.query-bar-split__main) {
  padding-left: 10px;
  padding-right: 10px;
}

.query-bar-split :deep(.query-bar-split__caret) {
  padding-left: 6px;
  padding-right: 6px;
  min-width: 28px;
}
</style>
