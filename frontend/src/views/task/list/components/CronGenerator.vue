<script setup>
/**
 * Crontab 可视化生成器
 * 秒/分：-1～59；时：-1～23；日：0～31；月：0～12；周：0～7
 * runMode: once → datetime 提交；repeat → cron 提交
 */
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { NInput, NInputNumber, NPopover, NRadio, NRadioGroup, NSlider } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getCronNextRunTimes, normalizeCronParts } from '@/utils/common/cron'

const props = defineProps({
  modelValue: { type: String, default: '' },
  /** once | repeat */
  runMode: { type: String, default: 'once' },
})

const emit = defineEmits(['update:modelValue', 'update:runMode', 'change'])

const values = reactive({
  second: 0,
  minute: -1,
  hour: -1,
  day: 0,
  month: 0,
  week: 0,
})

const cronExpr = ref(props.modelValue || '')
const nextRunTimes = ref([])
const syncingFromExpr = ref(false)
/** 含步进/列表/区间等复杂字段时，保留输入框原文，避免滑块反写冲掉 */
const preserveManualExpr = ref(false)
const localRunMode = ref(props.runMode || 'once')

watch(
  () => props.runMode,
  (v) => {
    if (v && v !== localRunMode.value) localRunMode.value = v
  },
)

const TIME_FIELDS = [
  { key: 'second', label: '秒', min: -1, max: 59, wildcardAt: -1, rangeText: '-1 ~ 59' },
  { key: 'minute', label: '分', min: -1, max: 59, wildcardAt: -1, rangeText: '-1 ~ 59' },
  { key: 'hour', label: '时', min: -1, max: 23, wildcardAt: -1, rangeText: '-1 ~ 23' },
]

const DATE_FIELDS = [
  { key: 'day', label: '日', min: 0, max: 31, wildcardAt: 0, rangeText: '0 ~ 31' },
  { key: 'month', label: '月', min: 0, max: 12, wildcardAt: 0, rangeText: '0 ~ 12' },
  { key: 'week', label: '周', min: 0, max: 7, wildcardAt: 0, rangeText: '0 ~ 7' },
]

const COMMON_CRON_EXAMPLES = [
  { label: '每月1号凌晨0时0分0秒执行一次', expr: '0 0 0 1 * *' },
  { label: '每周五晚上23时59分59秒执行一次', expr: '59 59 23 * * 5' },
  { label: '每天中午11时59分59秒执行一次', expr: '59 59 11 * * *' },
  { label: '每5个小时执行一次', expr: '0 0 */5 * * *' },
  { label: '每10分钟执行一次', expr: '0 */10 * * * *' },
  { label: '每30秒执行一次', expr: '*/30 * * * * *' },
]

const examplesPopoverShow = ref(false)

const nextRunLabel = computed(() =>
  localRunMode.value === 'once' ? '最近 1 次执行时间：' : '最近 10 次执行时间：',
)

function applyCommonExpr(expr) {
  examplesPopoverShow.value = false
  onCronInput(expr)
}

function onRunModeChange(v) {
  localRunMode.value = v
  emit('update:runMode', v)
}

function sliderToField(v, max, wildcardAt) {
  if (v == null || v === wildcardAt) return '*'
  if (wildcardAt === -1 && v < 0) return '*'
  const n = Math.min(Math.max(0, Math.floor(v)), max)
  if (wildcardAt === 0 && n === 0) return '*'
  return String(n)
}

function fieldToSlider(field, max, wildcardAt) {
  const s = String(field ?? '').trim()
  if (!s || s === '*' || s === '?') return wildcardAt
  if (/^\d+$/.test(s)) {
    const n = Number(s)
    if (n >= 0 && n <= max && !(wildcardAt === 0 && n === 0)) return n
  }
  return wildcardAt
}

/** 滑块无法完整表达的字段（如步进、区间、列表） */
function isSimpleCronField(field) {
  const s = String(field ?? '').trim()
  return !s || s === '*' || s === '?' || /^\d+$/.test(s)
}

function toStoredExpr(parts, hasSecond) {
  return hasSecond
    ? `${parts[1]} ${parts[2]} ${parts[3]} ${parts[4]} ${parts[5]}`
    : parts.slice(0, 5).join(' ')
}

function getPreviewExpr() {
  if (preserveManualExpr.value && cronExpr.value.trim()) return cronExpr.value.trim()
  return buildDisplayExpr()
}

function getStoredExpr() {
  if (preserveManualExpr.value && cronExpr.value.trim()) {
    const normalized = normalizeCronParts(cronExpr.value)
    if (normalized) return toStoredExpr(normalized.parts, normalized.hasSecond)
  }
  return buildStoredExpr()
}

function displayValue(v, wildcardAt) {
  return v === wildcardAt ? '*' : String(v)
}

function fmtTip(v, wildcardAt) {
  return v === wildcardAt ? '*' : String(v)
}

const fieldParts = computed(() => ({
  second: sliderToField(values.second, 59, -1),
  minute: sliderToField(values.minute, 59, -1),
  hour: sliderToField(values.hour, 23, -1),
  day: sliderToField(values.day, 31, 0),
  month: sliderToField(values.month, 12, 0),
  week: sliderToField(values.week, 7, 0),
}))

function buildStoredExpr() {
  const p = fieldParts.value
  return `${p.minute} ${p.hour} ${p.day} ${p.month} ${p.week}`
}

function buildDisplayExpr() {
  const p = fieldParts.value
  return `${p.second} ${p.minute} ${p.hour} ${p.day} ${p.month} ${p.week}`
}

function refreshNextRuns(expr) {
  const preview = (expr || '').trim() || getPreviewExpr()
  const count = localRunMode.value === 'once' ? 1 : 10
  nextRunTimes.value = getCronNextRunTimes(preview, count)
}

function buildScheduleResult() {
  const crontab = getStoredExpr()
  const display = getPreviewExpr()
  if (localRunMode.value === 'once') {
    const times = getCronNextRunTimes(display, 1)
    const dt = times[0] || null
    return {
      ok: !!dt,
      error: dt ? null : '无法计算最近一次执行时间',
      runMode: 'once',
      scheduler: 'datetime',
      task_crontabs_expr: crontab,
      task_datetime_expr: dt,
    }
  }
  return {
    ok: true,
    runMode: 'repeat',
    scheduler: 'cron',
    task_crontabs_expr: crontab,
    task_datetime_expr: null,
  }
}

function emitScheduleChange(fromControls = true) {
  if (syncingFromExpr.value) return
  // 用户拖动滑块后，放弃保留复杂原文，改回由控件生成
  if (fromControls && preserveManualExpr.value) {
    preserveManualExpr.value = false
  }
  const stored = fromControls ? buildStoredExpr() : getStoredExpr()
  if (fromControls) cronExpr.value = buildDisplayExpr()
  emit('update:modelValue', stored)
  refreshNextRuns(getPreviewExpr())
  const result = buildScheduleResult()
  emit('change', { ...result, ok: result.ok !== false })
}

watch(values, () => {
  if (!syncingFromExpr.value) emitScheduleChange(true)
})

watch(localRunMode, () => {
  if (!syncingFromExpr.value) {
    refreshNextRuns(getPreviewExpr())
    const result = buildScheduleResult()
    emit('change', { ...result, ok: result.ok !== false })
  }
})

watch(
  () => props.modelValue,
  (v) => {
    if (v == null) return
    if (v.trim() === getStoredExpr()) return
    if (v.trim() === cronExpr.value.trim()) return
    applyFromExpr(v, { silent: true })
  },
)

function reverseParse(expr, opts = {}) {
  const raw = (expr || '').trim()
  if (!raw) {
    if (!opts.silent) window.$message?.warning?.('请先输入 Cron 表达式')
    return false
  }
  const normalized = normalizeCronParts(raw)
  if (!normalized) {
    if (!opts.silent) window.$message?.warning?.('表达式格式无效')
    return false
  }
  const { parts, hasSecond } = normalized
  const complex = parts.some((p) => !isSimpleCronField(p))
  syncingFromExpr.value = true
  try {
    if (hasSecond) {
      values.second = fieldToSlider(parts[0], 59, -1)
      values.minute = fieldToSlider(parts[1], 59, -1)
      values.hour = fieldToSlider(parts[2], 23, -1)
      values.day = fieldToSlider(parts[3], 31, 0)
      values.month = fieldToSlider(parts[4], 12, 0)
      values.week = fieldToSlider(parts[5], 7, 0)
    } else {
      values.second = 0
      values.minute = fieldToSlider(parts[0], 59, -1)
      values.hour = fieldToSlider(parts[1], 23, -1)
      values.day = fieldToSlider(parts[2], 31, 0)
      values.month = fieldToSlider(parts[3], 12, 0)
      values.week = fieldToSlider(parts[4], 7, 0)
    }
    cronExpr.value = raw
    preserveManualExpr.value = complex
    const stored = toStoredExpr(parts, hasSecond)
    emit('update:modelValue', stored)
    refreshNextRuns(raw)
    const result = buildScheduleResult()
    emit('change', { ...result, ok: result.ok !== false })
    return true
  } finally {
    // 延后解除同步锁，避免 values 变更触发的 watch 用滑块覆盖 */N 等原文
    nextTick(() => {
      syncingFromExpr.value = false
    })
  }
}

function onCronInput(v) {
  cronExpr.value = v
  const normalized = normalizeCronParts(v)
  if (!normalized) {
    preserveManualExpr.value = false
    emit('update:modelValue', (v || '').trim())
    nextRunTimes.value = []
    return
  }
  reverseParse(v, { silent: true })
}

function generate() {
  preserveManualExpr.value = false
  emitScheduleChange(true)
  return resolveSchedule()
}

function resolveSchedule() {
  const crontab = getStoredExpr()
  if (!crontab.trim()) return { ok: false, error: '请配置或输入 Crontab 表达式' }
  const result = buildScheduleResult()
  if (!result.ok) return { ok: false, error: result.error || '无法计算执行时间' }
  return result
}

function reset() {
  syncingFromExpr.value = true
  values.second = 0
  values.minute = -1
  values.hour = -1
  values.day = 0
  values.month = 0
  values.week = 0
  cronExpr.value = ''
  nextRunTimes.value = []
  localRunMode.value = 'once'
  preserveManualExpr.value = false
  nextTick(() => {
    syncingFromExpr.value = false
  })
  emit('update:modelValue', '')
  emit('update:runMode', 'once')
}

function applyFromExpr(expr, opts = {}) {
  if (!expr?.trim()) {
    reset()
    return
  }
  reverseParse(expr, { silent: opts.silent !== false })
}

defineExpose({ generate, resolveSchedule, reset, applyFromExpr })

refreshNextRuns(props.modelValue || buildStoredExpr())
if (props.modelValue?.trim()) {
  applyFromExpr(props.modelValue, { silent: true })
} else {
  emitScheduleChange(true)
}
</script>

<template>
  <div class="cron-generator">
    <div class="cron-columns">
      <section class="cron-section">
        <header class="cron-section-head">
          <span class="cron-section-title">时间</span>
          <span class="cron-section-desc">(不指定，则设为-1)</span>
        </header>
        <div class="cron-section-body">
          <div v-for="f in TIME_FIELDS" :key="f.key" class="cron-field">
            <div class="cron-field-meta">
              <span class="cron-field-name">{{ f.label }}</span>
              <span
                class="cron-field-chip"
                :class="{ 'is-wildcard': values[f.key] === f.wildcardAt }"
              >
                {{ displayValue(values[f.key], f.wildcardAt) }}
              </span>
            </div>
            <NSlider
              v-model:value="values[f.key]"
              class="cron-field-slider"
              :min="f.min"
              :max="f.max"
              :step="1"
              :format-tooltip="(v) => fmtTip(v, f.wildcardAt)"
            />
            <NInputNumber
              v-model:value="values[f.key]"
              class="cron-field-num"
              size="small"
              :min="f.min"
              :max="f.max"
              :show-button="false"
            />
          </div>
        </div>
      </section>

      <section class="cron-section">
        <header class="cron-section-head">
          <span class="cron-section-title">日期</span>
          <span class="cron-section-desc">(不指定，则设为0)</span>
        </header>
        <div class="cron-section-body">
          <div v-for="f in DATE_FIELDS" :key="f.key" class="cron-field">
            <div class="cron-field-meta">
              <span class="cron-field-name">{{ f.label }}</span>
              <span
                class="cron-field-chip"
                :class="{ 'is-wildcard': values[f.key] === f.wildcardAt }"
              >
                {{ displayValue(values[f.key], f.wildcardAt) }}
              </span>
            </div>
            <NSlider
              v-model:value="values[f.key]"
              class="cron-field-slider"
              :min="f.min"
              :max="f.max"
              :step="1"
              :format-tooltip="(v) => fmtTip(v, f.wildcardAt)"
            />
            <NInputNumber
              v-model:value="values[f.key]"
              class="cron-field-num"
              size="small"
              :min="f.min"
              :max="f.max"
              :show-button="false"
            />
          </div>
        </div>
      </section>
    </div>

    <section class="cron-section cron-section--result">
      <div class="cron-expr-bar">
        <span class="cron-expr-label">Crontab表达式</span>
        <NInput
          :value="cronExpr"
          class="cron-expr-input"
          clearable
          placeholder="秒 分 时 日 月 周"
          @update:value="onCronInput"
        />
        <NRadioGroup
          :value="localRunMode"
          size="small"
          class="cron-run-mode"
          @update:value="onRunModeChange"
        >
          <NRadio value="once">执行 1 次</NRadio>
          <NRadio value="repeat">执行 N 次</NRadio>
        </NRadioGroup>
        <NPopover
          v-model:show="examplesPopoverShow"
          trigger="click"
          placement="bottom-end"
          :width="360"
        >
          <template #trigger>
            <button type="button" class="cron-help-btn" title="常用表达式">
              <TheIcon icon="material-symbols:help-outline" :size="18" />
            </button>
          </template>
          <div class="cron-examples">
            <div class="cron-examples-title">常用表达式</div>
            <div
              v-for="(item, idx) in COMMON_CRON_EXAMPLES"
              :key="item.expr"
              class="cron-example-item"
              @click="applyCommonExpr(item.expr)"
            >
              <span class="cron-example-idx">{{ idx + 1 }}.</span>
              <div class="cron-example-body">
                <div class="cron-example-label">{{ item.label }}</div>
                <code class="cron-example-expr">{{ item.expr }}</code>
              </div>
            </div>
          </div>
        </NPopover>
      </div>

      <div class="cron-next">
        <div class="cron-next-label">{{ nextRunLabel }}</div>
        <div v-if="nextRunTimes.length" class="cron-next-grid">
          <div v-for="(t, i) in nextRunTimes" :key="i" class="cron-next-item">
            <span class="cron-next-idx">{{ i + 1 }}</span>
            <span class="cron-next-time">{{ t }}</span>
          </div>
        </div>
        <div v-else class="cron-next-empty">暂无可用执行时间</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cron-generator {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cron-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: stretch;
}

.cron-section {
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color);
  overflow: hidden;
  min-width: 0;
}

.cron-section-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid var(--n-border-color);
}

.cron-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.cron-section-desc {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.cron-section-body {
  display: flex;
  flex-direction: column;
  padding: 4px 12px 8px;
}

.cron-field {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 52px;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.cron-field:last-child {
  border-bottom: none;
}

.cron-field-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.cron-field-name {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.cron-field-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #18a058;
  background: rgba(24, 160, 88, 0.12);
}

.cron-field-chip.is-wildcard {
  color: var(--n-text-color-3);
  background: rgba(0, 0, 0, 0.06);
}

.cron-field-slider {
  min-width: 0;
}

.cron-field-num {
  width: 52px;
}

.cron-field-num :deep(.n-input__input-el) {
  text-align: center;
  font-variant-numeric: tabular-nums;
  padding: 0 4px;
}

.cron-expr-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  flex-wrap: wrap;
}

.cron-expr-label {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
  white-space: nowrap;
}

.cron-expr-input {
  flex: 1;
  min-width: 160px;
}

.cron-expr-input :deep(.n-input__input-el) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  letter-spacing: 0.04em;
}

.cron-run-mode {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.cron-run-mode :deep(.n-radio) {
  margin-right: 0;
}

.cron-help-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--n-text-color-3);
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}

.cron-help-btn:hover {
  color: #18a058;
  background: rgba(24, 160, 88, 0.1);
}

.cron-examples-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--n-text-color-1);
}

.cron-example-item {
  display: flex;
  gap: 6px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.cron-example-item:hover {
  background: rgba(24, 160, 88, 0.08);
}

.cron-example-idx {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-3);
  line-height: 1.5;
}

.cron-example-body {
  flex: 1;
  min-width: 0;
}

.cron-example-label {
  font-size: 12px;
  color: var(--n-text-color-1);
  line-height: 1.5;
}

.cron-example-expr {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #18a058;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.cron-next {
  padding: 0 14px 14px;
}

.cron-next-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 8px;
  white-space: nowrap;
}

.cron-next-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
}

.cron-next-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  width: max-content;
  max-width: 100%;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.03);
}

.cron-next-idx {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: #18a058;
}

.cron-next-time {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--n-text-color-1);
}

.cron-next-empty {
  font-size: 12px;
  color: var(--n-text-color-3);
}

@media (max-width: 860px) {
  .cron-columns {
    grid-template-columns: 1fr;
  }
}
</style>
