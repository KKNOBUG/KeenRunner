<!--
  PerfComparisonCreateModal — 多记录对比/汇总创建弹窗

  选 2~20 份已完成报告，按模式创建结论快照（创建时后端一次性计算，之后不可修改）：
  compare 横向对比指定基准逐份看变化；merge 同场景汇总聚合；hybrid 两者兼出。
-->
<template>
  <n-modal v-model:show="show" preset="card" title="新建对比/汇总" style="width: 720px">
    <n-form label-placement="left" label-width="90">
      <n-form-item label="名称" required>
        <n-input v-model:value="form.comparison_name" placeholder="对比结论名称(如: 下单链路并发梯度对比)" maxlength="64" show-count />
      </n-form-item>
      <n-form-item label="模式" required>
        <n-radio-group v-model:value="form.comparison_mode">
          <n-radio v-for="item in MODE_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</n-radio>
        </n-radio-group>
      </n-form-item>
      <n-form-item :label="' '">
        <n-text depth="3" style="font-size: 12px">{{ modeHint }}</n-text>
      </n-form-item>
      <n-form-item label="参与报告" required>
        <n-select
            v-model:value="form.report_codes"
            :options="reportOptions"
            :loading="optionsLoading"
            :max-tag-count="3"
            multiple
            filterable
            placeholder="选择 2~20 份已完成报告(输入编码过滤)"
            @update:value="normalizeBaseline"
        />
      </n-form-item>
      <n-form-item v-if="needBaseline" label="基准报告" required>
        <n-select
            v-model:value="form.baseline_code"
            :options="baselineOptions"
            placeholder="从参与报告中选定基准"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input v-model:value="form.comparison_desc" type="textarea" :rows="2" placeholder="对比目的、结论口径等(选填)" maxlength="200" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="show = false">取 消</n-button>
        <n-button type="primary" :loading="creating" @click="handleCreate">创 建</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NRadio, NRadioGroup, NSelect, NSpace, NText } from 'naive-ui'

import { formatDateTime } from '@/utils'
import api from '@/api'

defineOptions({ name: 'PerfComparisonCreateModal' })

const emit = defineEmits(['saved'])

const MODE_OPTIONS = [
  { label: '横向对比', value: 'compare' },
  { label: '汇总合并', value: 'merge' },
  { label: '对比+汇总', value: 'hybrid' },
]
const MODE_HINTS = {
  compare: '指定基准报告，逐份输出相对基准的指标变化与配置差异（不限同场景）',
  merge: '同场景多份报告视为并行实例聚合成一份视图（计数累加、延迟按请求数加权）',
  hybrid: '横向对比与汇总合并同时输出',
}

const show = ref(false)
const creating = ref(false)
const optionsLoading = ref(false)
const reportOptions = ref([])

const form = reactive({
  comparison_name: '',
  comparison_mode: 'compare',
  report_codes: [],
  baseline_code: null,
  comparison_desc: '',
})

const modeHint = computed(() => MODE_HINTS[form.comparison_mode] || '')
/** compare/hybrid 必选基准；merge 免基准 */
const needBaseline = computed(() => form.comparison_mode !== 'merge')

/** 基准候选 = 已选参与报告（schema 层校验基准必须归属清单） */
const baselineOptions = computed(() =>
    reportOptions.value.filter((option) => form.report_codes.includes(option.value)))

/** 已选报告变化时校正基准归属（基准被移出清单则清空，防越界提交被 schema 拒绝） */
function normalizeBaseline() {
  if (form.baseline_code && !form.report_codes.includes(form.baseline_code)) {
    form.baseline_code = null
  }
}

/** 拉取已完成报告作为参与候选（对比仅认 completed 口径，与后端校验一致） */
async function loadReportOptions() {
  optionsLoading.value = true
  try {
    const res = await api.getPerfReportList({ state: 0, status: 'completed', page: 1, page_size: 100 })
    const rows = Array.isArray(res?.data) ? res.data : []
    reportOptions.value = rows.map((row) => ({
      label: `${row.report_code}（${row.scene_name || '-'} · 并发${row.concurrent_users ?? '-'} · ${formatDateTime(row.created_time)}）`,
      value: row.report_code,
    }))
  } catch (e) {
    reportOptions.value = []
  } finally {
    optionsLoading.value = false
  }
}

async function handleCreate() {
  if (!form.comparison_name.trim()) {
    window.$message?.warning('请填写对比名称')
    return
  }
  if (form.report_codes.length < 2 || form.report_codes.length > 20) {
    window.$message?.warning('请选择 2~20 份参与报告')
    return
  }
  if (needBaseline.value && !form.baseline_code) {
    window.$message?.warning('请选定基准报告')
    return
  }
  creating.value = true
  try {
    await api.createPerfComparison({
      comparison_name: form.comparison_name.trim(),
      comparison_mode: form.comparison_mode,
      report_codes: form.report_codes,
      baseline_code: needBaseline.value ? form.baseline_code : null,
      comparison_desc: form.comparison_desc.trim() || null,
    })
    window.$message?.success('对比记录创建成功')
    show.value = false
    emit('saved')
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    creating.value = false
  }
}

function open() {
  Object.assign(form, {
    comparison_name: '',
    comparison_mode: 'compare',
    report_codes: [],
    baseline_code: null,
    comparison_desc: '',
  })
  show.value = true
  loadReportOptions()
}

defineExpose({ open })
</script>
