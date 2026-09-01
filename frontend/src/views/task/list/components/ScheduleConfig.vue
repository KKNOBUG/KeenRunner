<script setup>
/**
 * 定时设置折叠卡片（结构化定时表达式 task_schedule_expr）
 * 周期模式：仅执行一次(默认)/永久有效；
 * 仅执行一次：触发日期(每月1~31号多选)×触发时间；永久有效：周期类型(日/周/月)×(触发星期/触发日期)×触发时间(最多3个)；
 * 执行预览(近10次)调用后端 /autotest/task/schedule_preview，与落库契约同源。
 * 卡片壳与折叠交互对齐步骤编辑器 .step-editor-card（参考 database_controller 请求配置项）。
 */
import { computed, ref, watch } from 'vue'
import { NButton, NCard, NCollapseTransition, NRadio, NRadioGroup, NSwitch } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import {
  CYCLE_MONTH,
  CYCLE_WEEK,
  PERIODIC_ONLY_ONCE,
  PERIODIC_UNBOUNDED,
  WEEK_LABELS,
  buildSchedulePayload,
  createEmptyScheduleState,
  formatFireTime,
  formatScheduleSummary,
} from '@/utils/common/schedule'
import TimeWheelPicker from './TimeWheelPicker.vue'

const props = defineProps({
  /** 编辑状态：{ periodic, cycle, monthDays, weeks, times } */
  modelValue: { type: Object, default: () => createEmptyScheduleState() },
  /** 展开/收起 */
  open: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'update:open'])

const state = computed(() => props.modelValue || createEmptyScheduleState())
const isUnbounded = computed(() => state.value.periodic === PERIODIC_UNBOUNDED)
const showMonthDays = computed(
  () => state.value.periodic === PERIODIC_ONLY_ONCE || (isUnbounded.value && state.value.cycle === CYCLE_MONTH),
)
const showWeeks = computed(() => isUnbounded.value && state.value.cycle === CYCLE_WEEK)

/** 收起态右侧摘要：与任务列表table「定时配置」列同一渲染 */
const summary = computed(() => {
  const payload = buildSchedulePayload(state.value)
  return payload ? formatScheduleSummary(payload.periodic, payload.schedule) : ''
})

function updateState(patch) {
  emit('update:modelValue', { ...state.value, ...patch })
}

function toggleOpen() {
  emit('update:open', !props.open)
}

/** 周期模式开关样式：执行一次=主题主色，永久有效=信息色 */
const periodicRailStyle = ({ checked }) =>
  checked ? { background: 'var(--primary-color)' } : { background: 'var(--info-color, #2080f0)' }

function setPeriodicBySwitch(v) {
  setPeriodic(v ? PERIODIC_ONLY_ONCE : PERIODIC_UNBOUNDED)
}

function setPeriodic(v) {
  const patch = { periodic: v }
  if (v && !(state.value.times || []).length) patch.times = ['']
  updateState(patch)
}

function setCycle(v) {
  updateState({ cycle: v })
}

function toggleIn(field, value) {
  const list = [...(state.value[field] || [])]
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)
  updateState({ [field]: list })
}

/** 触发日期：全选 / 取消已选 */
function selectAllMonthDays() {
  updateState({ monthDays: Array.from({ length: 31 }, (_, i) => i + 1) })
}

function clearMonthDays() {
  updateState({ monthDays: [] })
}

function setTime(idx, v) {
  const times = [...(state.value.times || [])]
  times[idx] = v || ''
  updateState({ times })
}

function removeTime(idx) {
  const times = [...(state.value.times || [])]
  if (times.length <= 1) return
  times.splice(idx, 1)
  updateState({ times })
}

function addTime() {
  const times = [...(state.value.times || [])]
  if (times.length >= 3) return
  times.push('')
  updateState({ times })
}

function handleClear() {
  emit('update:modelValue', createEmptyScheduleState())
  previewTimes.value = []
}

// ==================== 执行预览(近10次) ====================

const previewTimes = ref([])
let previewTimer = null

const payloadSignature = computed(() => JSON.stringify(buildSchedulePayload(state.value) || null))

watch(payloadSignature, (sig) => {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(() => fetchPreview(sig), 300)
})

async function fetchPreview(sig) {
  const payload = sig ? JSON.parse(sig) : null
  if (!payload) {
    previewTimes.value = []
    return
  }
  try {
    const res = await api.previewTaskSchedule({
      task_periodic_expr: payload.periodic,
      task_schedule_expr: payload.schedule,
    })
    previewTimes.value = Array.isArray(res?.data) ? res.data.slice(0, 10) : []
  } catch (e) {
    previewTimes.value = []
  }
}

fetchPreview(payloadSignature.value)
</script>

<template>
  <NCard :bordered="false" class="step-editor-card schedule-card" :class="{ 'is-collapsed': !open }">
    <template #header>
      <div class="card-header-row">
        <div
          class="panel-title panel-title-wrap"
          role="button"
          tabindex="0"
          @click="toggleOpen"
          @keydown.enter.prevent="toggleOpen"
        >
          <TheIcon
            class="panel-collapse-icon"
            :icon="open ? 'material-symbols:expand-more' : 'material-symbols:chevron-right'"
            :size="20"
          />
          定时设置
          <span class="schedule-hint">（非必输）</span>
        </div>
        <div class="card-header-actions">
          <span v-if="!open" class="schedule-summary" :title="summary">{{ summary || '未配置定时' }}</span>
          <NButton text size="tiny" @click="handleClear">清空</NButton>
          <NButton text size="tiny" class="collapse-tiny-btn" @click="toggleOpen">
            <template #icon>
              <TheIcon :icon="open ? 'material-symbols:expand-less' : 'material-symbols:expand-more'" :size="18" />
            </template>
            {{ open ? '收起' : '展开' }}
          </NButton>
        </div>
      </div>
    </template>

    <NCollapseTransition :show="open">
      <div class="schedule-body">
        <div class="schedule-row">
          <label class="schedule-label is-required">周期模式</label>
          <NSwitch
            class="periodic-switch"
            :value="state.periodic === PERIODIC_ONLY_ONCE"
            :rail-style="periodicRailStyle"
            @update:value="setPeriodicBySwitch"
          >
            <template #checked>执行一次</template>
            <template #unchecked>永久有效</template>
          </NSwitch>
        </div>

        <div v-if="isUnbounded" class="schedule-row">
          <label class="schedule-label is-required">周期类型</label>
          <NRadioGroup :value="state.cycle" @update:value="setCycle">
            <NRadio value="日">日</NRadio>
            <NRadio value="周">周</NRadio>
            <NRadio value="月">月</NRadio>
          </NRadioGroup>
        </div>

        <div v-if="showMonthDays" class="schedule-row">
          <label class="schedule-label is-required">触发日期</label>
          <div class="chip-grid">
            <button
              v-for="d in 31"
              :key="d"
              type="button"
              class="chip"
              :class="{ active: (state.monthDays || []).includes(d) }"
              @click="toggleIn('monthDays', d)"
            >
              {{ d }}号
            </button>
            <button type="button" class="chip chip--action" @click="selectAllMonthDays">全选</button>
            <button type="button" class="chip chip--action" @click="clearMonthDays">取消已选</button>
          </div>
        </div>

        <div v-if="showWeeks" class="schedule-row">
          <label class="schedule-label is-required">触发星期</label>
          <div class="chip-line">
            <button
              v-for="w in 7"
              :key="w"
              type="button"
              class="chip"
              :class="{ active: (state.weeks || []).includes(w) }"
              @click="toggleIn('weeks', w)"
            >
              {{ WEEK_LABELS[w] }}
            </button>
          </div>
        </div>

        <div v-if="state.periodic" class="schedule-row">
          <label class="schedule-label is-required">触发时间</label>
          <div class="time-list">
            <div v-for="(t, idx) in state.times" :key="idx" class="time-item">
              <TimeWheelPicker :value="t" @update:value="(v) => setTime(idx, v)" />
              <span class="time-actions">
                <button
                  v-if="(state.times || []).length > 1"
                  type="button"
                  class="icon-btn icon-btn--del"
                  title="删除该时间"
                  @click="removeTime(idx)"
                >
                  <TheIcon icon="material-symbols:cancel" :size="16" />
                </button>
                <button
                  v-if="idx === (state.times || []).length - 1 && (state.times || []).length < 3"
                  type="button"
                  class="icon-btn icon-btn--add"
                  title="新增时间"
                  @click="addTime"
                >
                  <TheIcon icon="material-symbols:add-circle" :size="16" />
                </button>
              </span>
            </div>
          </div>
        </div>

        <div class="schedule-row">
          <label class="schedule-label">执行预览</label>
          <div v-if="previewTimes.length" class="preview-wrap">
            <div class="preview-grid">
              <span v-for="(t, i) in previewTimes" :key="i" class="preview-chip">{{ formatFireTime(t) }}</span>
            </div>
            <div class="preview-tip">近10次执行时间</div>
          </div>
          <span v-else class="preview-empty">暂无可预览的执行时间</span>
        </div>
      </div>
    </NCollapseTransition>
  </NCard>
</template>

<style scoped>
.schedule-card :deep(.n-card__content) {
  padding: 12px 16px;
}

.schedule-hint {
  font-size: var(--step-editor-meta-size, 12px);
  font-weight: 400;
  color: var(--n-text-color-3);
}

.schedule-summary {
  max-width: 420px;
  font-size: var(--step-editor-meta-size, 12px);
  color: var(--n-text-color-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.schedule-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.schedule-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.schedule-label {
  flex: 0 0 64px;
  font-size: var(--step-editor-font-size, 13px);
  color: var(--n-text-color-1);
  line-height: 28px;
  white-space: nowrap;
}

.schedule-label.is-required::before {
  content: '*';
  color: var(--error-color, #d03050);
  margin-right: 2px;
}

/* 触发日期：每行 5 个，31号 自然单独一行；选中色统一系统主题主色 */
.chip-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.chip-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.chip {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  background: var(--n-color);
  color: var(--n-text-color-2);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.chip:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.chip.active {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: #fff;
}

/* 触发日期选中样式与执行预览一致：信息色浅底 */
.chip-grid .chip:hover {
  border-color: var(--info-color, #2080f0);
  color: var(--info-color, #2080f0);
}

.chip-grid .chip.active {
  border-color: var(--info-color, #2080f0);
  background: color-mix(in srgb, var(--info-color, #2080f0) 8%, transparent);
  color: var(--info-color, #2080f0);
}

.periodic-switch {
  margin-top: 4px;
}

/* 全选/取消已选：与日期 chip 同格同高，仅文字提示色区分 */
.chip--action {
  color: var(--n-text-color-3);
}

.chip--action:hover {
  border-color: var(--info-color, #2080f0);
  color: var(--info-color, #2080f0);
}

/* 触发时间：横向排列、每行 5 个；新增/删除按钮悬停对应时间项时再显示 */
.time-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.time-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.time-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  visibility: hidden;
}

.time-item:hover .time-actions {
  visibility: visible;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

.icon-btn--del {
  color: var(--error-color, #d03050);
}

.icon-btn--add {
  color: var(--info-color, #2080f0);
}

.preview-wrap {
  flex: 1;
  min-width: 0;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(5, max-content);
  gap: 8px 10px;
}

.preview-chip {
  padding: 4px 10px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--info-color, #2080f0) 8%, transparent);
  color: var(--info-color, #2080f0);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  white-space: nowrap;
}

.preview-tip {
  margin-top: 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.preview-empty {
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 28px;
}
</style>
