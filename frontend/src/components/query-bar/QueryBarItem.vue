<template>
  <div flex items-center>
    <label
        v-if="!isNullOrWhitespace(label)"
        w-80
        flex-shrink-0
        text-14
        :style="{ width: labelWidth + 'px' }"
    >
      {{ label }}
    </label>
    <div class="query-bar-item__field">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { isNullOrWhitespace } from '@/utils'

defineProps({
  label: {
    type: String,
    default: '',
  },
  labelWidth: {
    type: Number,
    default: 80,
  },
  contentWidth: {
    type: Number,
    default: 220,
  },
})
</script>

<style>
/* 与 label（14px）视觉对齐：略低于默认 medium（约 34px），接近 small */
.query-bar-item__field :deep(.n-input) {
  --n-height: 14px;
  --n-font-size: 14px;
}

.query-bar-item__field :deep(.n-base-selection) {
  --n-height: 14px;
  --n-font-size: 14px;
}
</style>
