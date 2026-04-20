<template>
  <AppPage :show-footer="showFooter">
    <header
        v-if="showHeader && ($slots.header || $slots.action)"
        mb-15
        min-h-45
        flex
        items-center
        px-15
        :class="$slots.header ? 'justify-between' : 'justify-end'"
    >
      <slot v-if="$slots.header" name="header" />
      <slot v-else name="action" />
    </header>

    <div flex-1 min-h-0 min-w-0 flex flex-col>
      <slot />
    </div>
  </AppPage>
</template>

<script setup>
defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
  /**
   * 是否预留顶部栏区域；仅在有 #header 或 #action 时渲染。
   * 为 false 时即使有 #action 也不显示（如个人中心整页自定义布局）。
   */
  showHeader: {
    type: Boolean,
    default: true,
  },
  /** 保留 props 以兼容旧代码，不再渲染子页标题 */
  title: {
    type: String,
    default: undefined,
  },
})
</script>
