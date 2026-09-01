<script setup>
/**
 * 触发时间滚轮选择器：时/分/秒三段式
 * 滚轮向上递减（00 向上 → 59 回绕）、向下递增（00 向下 → 01 回绕）；
 * 点击段落切换激活段，滚轮只调整激活段；空值时点击/滚动从 00:00:00 开始。
 * wheel 需 passive:false 才能阻止抽屉滚动，模板绑定无法保证，故手动绑定。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /** 'HH:mm:ss'，空串表示未选择 */
  value: { type: String, default: '' },
})

const emit = defineEmits(['update:value'])

/** 时/分/秒取值上限 */
const RANGES = [24, 60, 60]

const segments = computed(() => {
  const m = String(props.value || '').match(/^(\d{2}):(\d{2}):(\d{2})$/)
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null
})

const activeIdx = ref(0)
const rootRef = ref(null)

const pad2 = (n) => String(n).padStart(2, '0')

function emitFromSegs(segs) {
  emit('update:value', segs.map(pad2).join(':'))
}

/** 按滚轮方向调整激活段：向上 -1 回绕、向下 +1 回绕 */
function adjust(delta) {
  const base = segments.value ? [...segments.value] : [0, 0, 0]
  const range = RANGES[activeIdx.value]
  base[activeIdx.value] = (base[activeIdx.value] + delta + range) % range
  emitFromSegs(base)
}

function handleWheel(e) {
  e.preventDefault()
  adjust(e.deltaY > 0 ? 1 : -1)
}

function handleRootClick() {
  if (!segments.value) emitFromSegs([0, 0, 0])
}

onMounted(() => {
  rootRef.value?.addEventListener('wheel', handleWheel, { passive: false })
})

onBeforeUnmount(() => {
  rootRef.value?.removeEventListener('wheel', handleWheel)
})
</script>

<template>
  <div ref="rootRef" class="time-wheel" title="点击选择时/分/秒，滚轮向上递减、向下递增（回绕）" @click="handleRootClick">
    <template v-if="segments">
      <template v-for="(n, i) in segments" :key="i">
        <span v-if="i > 0" class="time-wheel-colon">:</span>
        <span class="time-wheel-seg" :class="{ active: activeIdx === i }" @click.stop="activeIdx = i">
          {{ pad2(n) }}
        </span>
      </template>
    </template>
    <span v-else class="time-wheel-placeholder">-- : -- : --</span>
  </div>
</template>

<style scoped>
.time-wheel {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--n-border-color);
  border-radius: 3px;
  background: var(--n-color);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s;
}

.time-wheel:hover {
  border-color: var(--primary-color);
}

.time-wheel-seg {
  padding: 0 2px;
  border-radius: 2px;
  color: var(--n-text-color-1);
}

.time-wheel-seg.active {
  color: var(--primary-color);
  font-weight: 600;
  background: color-mix(in srgb, var(--primary-color) 12%, transparent);
}

.time-wheel-colon {
  color: var(--n-text-color-3);
}

.time-wheel-placeholder {
  color: var(--n-text-color-3);
}
</style>
