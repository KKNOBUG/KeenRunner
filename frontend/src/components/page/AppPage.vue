<template>
  <transition name="fade-slide" mode="out-in" appear>
    <section class="cus-scroll-y wh-full flex-col bg-[#f5f6fb] p-15 dark:bg-hex-121212">
      <slot />
      <!-- 支持 named footer slot: 优先渲染父组件传入的 footer 内容 -->
      <slot name="footer">
        <AppFooter v-if="showFooter" mt-15 />
      </slot>
      <n-back-top :bottom="20" />
    </section>
  </transition>
</template>

<script setup>
import AppFooter from "@/components/common/AppFooter.vue";

defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
})
</script>
