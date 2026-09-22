<!--
  PerfSceneForm — 压测场景四步编辑抽屉（基础信息 → 选接口 → 请求项编排 → 判定目标）

  M1 编辑器不提供 journey 链路编排（后端契约保留，存量 journey 场景禁止在本表单打开）；
  接口项整体覆盖保存（与后端「一次提交全量结构」语义一致），前端预校验与
  perf_scene_schema 校验同口径，失败早返回并跳转到对应步骤。
-->
<template>
  <n-drawer v-model:show="show" :width="1100" placement="right">
    <n-drawer-content :title="drawerTitle" closable>
      <n-space vertical :size="16">
        <n-steps :current="current" size="small">
          <n-step v-for="title in stepTitles" :key="title" :title="title" />
        </n-steps>

        <!-- 步骤一：基础信息 -->
        <template v-if="current === 1">
          <n-card title="基础信息" size="small">
            <n-form
                ref="formRef"
                :model="form"
                label-placement="left"
                label-width="96"
                require-mark-placement="right-hanging"
            >
              <n-grid :cols="24" :x-gap="12">
                <n-gi :span="12">
                  <n-form-item label="所属应用" path="scene_project" :rule="projectRule">
                    <n-select
                        v-model:value="form.scene_project"
                        :options="projectOptions"
                        :disabled="isEdit"
                        placeholder="请选择所属应用"
                        clearable
                        filterable
                    />
                  </n-form-item>
                </n-gi>
                <n-gi :span="12">
                  <n-form-item label="场景名称" path="scene_name" :rule="{ required: true, message: '请输入场景名称' }">
                    <n-input v-model:value="form.scene_name" placeholder="请输入场景名称" clearable />
                  </n-form-item>
                </n-gi>
                <n-gi :span="12">
                  <n-form-item label="施压模式" path="run_mode">
                    <n-radio-group v-model:value="form.run_mode" name="run_mode">
                      <n-space>
                        <n-radio value="single">单接口</n-radio>
                        <n-radio value="mixed">混合流量</n-radio>
                      </n-space>
                    </n-radio-group>
                  </n-form-item>
                </n-gi>
                <n-gi :span="12">
                  <n-form-item label="场景描述" path="scene_desc">
                    <n-input v-model:value="form.scene_desc" placeholder="场景描述（可选）" clearable />
                  </n-form-item>
                </n-gi>
              </n-grid>
            </n-form>
            <n-alert :bordered="false" type="info">
              {{ runModeHint }}
            </n-alert>
          </n-card>
        </template>

        <!-- 步骤二：选择接口 -->
        <template v-else-if="current === 2">
          <n-card size="small">
            <template #header>
              <n-space align="center" :size="8">
                <span class="card-title">已选接口</span>
                <n-tag size="small" type="info" :bordered="false">{{ form.scene_items.length }} 项</n-tag>
              </n-space>
            </template>
            <template #header-extra>
              <n-button size="small" type="primary" :disabled="!form.scene_project" @click="openSelectPanel">
                添加接口
              </n-button>
            </template>
            <n-alert v-if="!form.scene_project" :bordered="false" type="warning" style="margin-bottom: 8px">
              请先在「基础信息」中选择所属应用
            </n-alert>
            <n-empty v-else-if="!form.scene_items.length" description="尚未选择接口，点击右上角「添加接口」" class="py-40" />
            <n-data-table
                v-else
                :columns="pickedColumns"
                :data="form.scene_items"
                :pagination="false"
                :row-key="(row) => row.api_code"
                size="small"
                :max-height="460"
                :scroll-x="620"
            />
          </n-card>
        </template>

        <!-- 步骤三：请求项编排 -->
        <template v-else-if="current === 3">
          <n-card title="请求项编排" size="small">
            <n-data-table
                :columns="itemColumns"
                :data="form.scene_items"
                :pagination="false"
                :row-key="(row) => row.api_code"
                size="small"
                :max-height="520"
                :scroll-x="1560"
            />
            <n-text depth="3" style="font-size: 12px">
              权重仅混合流量模式生效；思考时间为接口项执行前的停顿；数据集按策略将行分配给虚拟用户。
            </n-text>
          </n-card>
        </template>

        <!-- 步骤四：判定目标 -->
        <template v-else>
          <n-space vertical :size="16">
            <n-card size="small">
              <template #header>
                <n-space align="center" :size="8">
                  <span class="card-title">SLA 目标</span>
                  <n-text depth="3" style="font-size: 12px">逐条绝对判定，与熔断、基线退化相互独立</n-text>
                </n-space>
              </template>
              <template #header-extra>
                <n-button size="small" @click="addTarget">添加目标</n-button>
              </template>
              <n-empty v-if="!form.perf_targets.length" description="未配置 SLA 目标（报告仅呈现统计，不做达标判定）" class="py-20" />
              <n-space v-else vertical :size="12">
                <n-card v-for="(target, index) in form.perf_targets" :key="index" size="small">
                  <template #header>
                    <div class="item-card-header">
                      <span class="item-card-title">目标 {{ index + 1 }}</span>
                      <n-button size="tiny" type="error" quaternary @click="removeTarget(index)">删除</n-button>
                    </div>
                  </template>
                  <n-grid :cols="24" :x-gap="12">
                    <n-gi :span="6">
                      <n-form-item label="层级" :label-width="56" size="small">
                        <n-select v-model:value="target.scope" :options="PERF_TARGET_SCOPE_OPTIONS" @update:value="() => handleTargetScopeChange(target)" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="6">
                      <n-form-item label="指标" :label-width="56" size="small">
                        <n-select v-model:value="target.target" :options="PERF_TARGET_METRIC_OPTIONS" />
                      </n-form-item>
                    </n-gi>
                    <n-gi v-if="target.scope === 'api'" :span="6">
                      <n-form-item label="接口" :label-width="56" size="small">
                        <n-select v-model:value="target.api_code" :options="itemApiOptions" placeholder="场景内接口" filterable />
                      </n-form-item>
                    </n-gi>
                    <n-gi v-if="target.scope === 'transaction'" :span="6">
                      <n-form-item label="事务" :label-width="56" size="small">
                        <n-select v-model:value="target.transaction" :options="transactionOptions" placeholder="场景内事务" filterable tag />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="5">
                      <n-form-item label="判定" :label-width="56" size="small">
                        <n-input-group>
                          <n-select v-model:value="target.op" :options="PERF_TARGET_OP_OPTIONS" style="width: 74px" />
                          <n-input-number v-model:value="target.expect" placeholder="期望值" style="width: 100%" :show-button="false" />
                        </n-input-group>
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="5">
                      <n-form-item label="未达成" :label-width="56" size="small">
                        <n-select v-model:value="target.severity" :options="PERF_TARGET_SEVERITY_OPTIONS" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="7">
                      <n-form-item label="样本门槛" :label-width="66" size="small">
                        <n-input-group>
                          <n-input-number v-model:value="target.min_total_requests" placeholder="最小请求数" style="width: 100%" :show-button="false" clearable />
                          <n-input-number v-model:value="target.min_duration_seconds" placeholder="最小时长(秒)" style="width: 100%" :show-button="false" clearable />
                        </n-input-group>
                      </n-form-item>
                    </n-gi>
                  </n-grid>
                </n-card>
              </n-space>
            </n-card>

            <n-card title="基线与熔断" size="small">
              <n-grid :cols="24" :x-gap="12">
                <n-gi :span="12">
                  <n-form-item label="基线报告" path="baseline_report_code">
                    <n-input v-model:value="form.baseline_report_code" placeholder="基线报告标识（选填，配置退化阈值后参与判定）" clearable />
                  </n-form-item>
                </n-gi>
                <n-gi :span="4">
                  <n-form-item label="P95退化%" :label-width="70" size="small">
                    <n-input-number v-model:value="form.baseline_policy.p95_degrade_pct" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                  </n-form-item>
                </n-gi>
                <n-gi :span="4">
                  <n-form-item label="RPS退化%" :label-width="70" size="small">
                    <n-input-number v-model:value="form.baseline_policy.qps_degrade_pct" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                  </n-form-item>
                </n-gi>
                <n-gi :span="4">
                  <n-form-item label="错误率+%" :label-width="70" size="small">
                    <n-input-number v-model:value="form.baseline_policy.error_rate_increase" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                  </n-form-item>
                </n-gi>
                <n-gi :span="12">
                  <n-form-item label="熔断阈值" path="error_rate_threshold">
                    <n-input-number
                        v-model:value="form.error_rate_threshold"
                        style="width: 100%"
                        :min="0"
                        :max="100"
                        placeholder="错误率百分比，0 或留空=不熔断"
                        clearable
                    />
                  </n-form-item>
                </n-gi>
                <n-gi :span="12">
                  <n-form-item label="预热剔除" path="warmup_seconds">
                    <n-input-number
                        v-model:value="form.warmup_seconds"
                        style="width: 100%"
                        :min="0"
                        :max="300"
                        placeholder="秒；留空按加压节奏自动派生，0=不剔除"
                        clearable
                    />
                  </n-form-item>
                </n-gi>
              </n-grid>
            </n-card>

            <n-card title="断言与标记" size="small">
              <n-grid :cols="24" :x-gap="12">
                <n-gi :span="12">
                  <n-form-item label="断言口径" path="assert_mode">
                    <n-radio-group v-model:value="form.assert_mode" name="assert_mode">
                      <n-space>
                        <n-radio v-for="opt in PERF_ASSERT_MODE_OPTIONS" :key="opt.value" :value="opt.value">
                          {{ opt.label }}
                        </n-radio>
                      </n-space>
                    </n-radio-group>
                  </n-form-item>
                </n-gi>
                <n-gi v-if="form.assert_mode === 'sample_ratio'" :span="6">
                  <n-form-item label="采样比例%" path="sample_ratio" :label-width="76">
                    <n-input-number v-model:value="form.sample_ratio" style="width: 100%" :min="0.1" :max="100" />
                  </n-form-item>
                </n-gi>
                <n-gi :span="6">
                  <n-form-item label="压测标记" path="inject_perf_tag" :label-width="76">
                    <n-switch v-model:value="form.inject_perf_tag" />
                    <n-text depth="3" style="font-size: 12px; margin-left: 8px">注入 x-perf-batch 标记头</n-text>
                  </n-form-item>
                </n-gi>
              </n-grid>
            </n-card>
          </n-space>
        </template>
      </n-space>

      <template #footer>
        <n-space justify="end">
          <n-button @click="show = false">取 消</n-button>
          <n-button v-if="current > 1" @click="current -= 1">上一步</n-button>
          <n-button v-if="current < 4" type="primary" @click="handleNext">下一步</n-button>
          <n-button v-else type="primary" :loading="saving" @click="handleSave">保 存</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>

  <PerfApiSelectPanel ref="selectPanelRef" @confirm="handleApisConfirmed" />
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDrawer, NDrawerContent, NEmpty, NForm, NFormItem, NGi, NGrid,
  NInput, NInputGroup, NInputNumber, NRadio, NRadioGroup, NSelect, NSpace, NStep, NSteps, NSwitch,
  NTag, NText,
} from 'naive-ui'

import PerfApiSelectPanel from './PerfApiSelectPanel.vue'

import {
  PERF_API_ROLE_OPTIONS, PERF_ASSERT_MODE_OPTIONS, PERF_DATASET_STRATEGY_OPTIONS,
  PERF_DELAY_MODE_OPTIONS, PERF_TARGET_METRIC_OPTIONS, PERF_TARGET_OP_OPTIONS,
  PERF_TARGET_SCOPE_OPTIONS, PERF_TARGET_SEVERITY_OPTIONS,
} from '@/constants/perfApi'
import api from '@/api'

defineOptions({ name: 'PerfSceneForm' })

const emit = defineEmits(['saved'])

const show = defineModel('show', { type: Boolean, default: false })

const stepTitles = ['基础信息', '选择接口', '请求项编排', '判定目标']
const current = ref(1)

/** 编辑中的场景ID；null 表示新增 */
const editingId = ref(null)

const formRef = ref(null)
const selectPanelRef = ref(null)
const saving = ref(false)
const projectOptions = ref([])
/** 接口项数据集候选（key=api_id，只含归属该接口的数据集） */
const datasetOptionsByApi = ref({})

const emptyForm = () => ({
  scene_project: null,
  scene_name: null,
  scene_desc: null,
  run_mode: 'single',
  scene_items: [],
  perf_targets: [],
  baseline_report_code: null,
  baseline_policy: { p95_degrade_pct: null, qps_degrade_pct: null, error_rate_increase: null },
  warmup_seconds: null,
  error_rate_threshold: null,
  assert_mode: 'all',
  sample_ratio: 100,
  inject_perf_tag: true,
})

const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value != null)
const drawerTitle = computed(() => (isEdit.value ? `编辑压测场景 · ${form.scene_name || ''}` : '新增压测场景'))

/** 编辑模式应用归属锁定：跨应用迁移会让接口项引用与数据集绑定同时失效 */
const projectRule = computed(() =>
    isEdit.value ? undefined : { required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] },
)

const runModeHint = computed(() => (form.run_mode === 'mixed'
  ? '混合流量：多个被测接口按权重并发施压，各接口独立统计；准备/抽查项不计入业务指标。'
  : '单接口：仅一个被测接口计入业务指标，可搭配准备/抽查项构成完整业务前置换。'))

/** 场景内接口候选（SLA 目标 scope=api 的下拉） */
const itemApiOptions = computed(() => form.scene_items.map((item) => ({
  label: item.api_name,
  value: item.api_code,
})))

/** 场景内事务候选（来自请求项已填事务名，支持手输新值） */
const transactionOptions = computed(() => [...new Set(
    form.scene_items.map((item) => (item.transaction || '').trim()).filter(Boolean),
)].map((name) => ({ label: name, value: name })))

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 批量拉取接口项数据集候选（只含归属该接口的数据集，已拉取的接口跳过） */
async function loadDatasetsForApis(apiIds) {
  const pending = [...new Set(apiIds)].filter((id) => id != null && !(id in datasetOptionsByApi.value))
  if (!pending.length) return
  const results = await Promise.allSettled(
      pending.map((apiId) => api.listPerfDatasetsForApi({ api_id: apiId })),
  )
  const next = { ...datasetOptionsByApi.value }
  results.forEach((result, index) => {
    const apiId = pending[index]
    const rows = result.status === 'fulfilled'
        ? (result.value?.data || []).filter((row) => row.bind_api_id === apiId)
        : []
    next[apiId] = rows.map((row) => ({ label: row.ds_name, value: row.ds_code }))
  })
  datasetOptionsByApi.value = next
}

// ---------- 接口项 ----------

/** 接口选择面板确认 → 追加为请求项（seq 由 resequence 统一重排） */
function handleApisConfirmed(apiRows) {
  const existing = new Set(form.scene_items.map((item) => item.api_code))
  apiRows.forEach((row) => {
    if (existing.has(row.api_code)) return
    form.scene_items.push({
      seq: 0,
      api_code: row.api_code,
      api_id: row.api_id,
      api_name: row.api_name,
      step_type: row.step_type,
      request_url: row.request_url,
      role: 'measured',
      weight: 1,
      delay_mode: 'fixed',
      delay_ms: 0,
      delay_ms_min: null,
      delay_ms_max: null,
      transaction: null,
      ds_code: null,
      ds_name: null,
      dataset_strategy: 'round_robin',
      enabled: true,
    })
  })
  resequence()
  loadDatasetsForApis(apiRows.map((row) => row.api_id))
}

function resequence() {
  form.scene_items.forEach((item, index) => {
    item.seq = index + 1
  })
}

function moveItem(index, offset) {
  const target = index + offset
  if (target < 0 || target >= form.scene_items.length) return
  const [item] = form.scene_items.splice(index, 1)
  form.scene_items.splice(target, 0, item)
  resequence()
}

function removeItem(index) {
  form.scene_items.splice(index, 1)
  resequence()
}

function handleDelayModeChange(item, mode) {
  item.delay_mode = mode
  item.delay_ms = mode === 'fixed' ? (item.delay_ms || 0) : 0
  item.delay_ms_min = mode === 'uniform' ? item.delay_ms_min : null
  item.delay_ms_max = mode === 'uniform' ? item.delay_ms_max : null
}

function handleDsChange(item, dsCode) {
  item.ds_code = dsCode || null
  const matched = (datasetOptionsByApi.value[item.api_id] || []).find((opt) => opt.value === dsCode)
  item.ds_name = matched ? matched.label : null
  if (!dsCode) item.dataset_strategy = 'round_robin'
}

function openSelectPanel() {
  selectPanelRef.value?.open({
    excludedCodes: form.scene_items.map((item) => item.api_code),
  })
}

/** 步骤二已选接口简表（编排属性在步骤三） */
const pickedColumns = [
  { title: '#', key: 'seq', width: 50 },
  { title: '接口名称', key: 'api_name', minWidth: 160, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'step_type',
    width: 70,
    render: (row) => h(NTag, { size: 'small', type: row.step_type === 'TCP请求' ? 'warning' : 'info' },
        { default: () => (row.step_type === 'TCP请求' ? 'TCP' : 'HTTP') }),
  },
  { title: '地址', key: 'request_url', minWidth: 220, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 70,
    render: (_row, index) => h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => removeItem(index) },
        { default: () => '删除' }),
  },
]

/** 步骤三编排表格（全动态 render，行对象引用直接写回） */
const itemColumns = computed(() => [
  { title: '#', key: 'seq', width: 50, render: (row) => row.seq },
  {
    title: '接口',
    key: 'api_name',
    minWidth: 150,
    ellipsis: { tooltip: true },
    render: (row) => row.api_name,
  },
  {
    title: '角色',
    key: 'role',
    width: 160,
    render: (row) => h(NSelect, {
      value: row.role,
      options: PERF_API_ROLE_OPTIONS,
      size: 'small',
      style: { width: '100%' },
      'onUpdate:value': (v) => {
        row.role = v
      },
    }),
  },
  {
    title: '权重',
    key: 'weight',
    width: 110,
    render: (row) => h(NInputNumber, {
      value: row.weight,
      size: 'small',
      min: 1,
      max: 1000,
      style: { width: '100%' },
      'onUpdate:value': (v) => {
        row.weight = v || 1
      },
    }),
  },
  {
    title: '思考时间',
    key: 'delay',
    width: 300,
    render: (row) => h(NSpace, { vertical: true, size: 4 }, {
      default: () => [
        h(NSelect, {
          value: row.delay_mode,
          options: PERF_DELAY_MODE_OPTIONS,
          size: 'small',
          style: { width: '100%' },
          'onUpdate:value': (v) => handleDelayModeChange(row, v),
        }),
        row.delay_mode === 'fixed'
            ? h(NInputNumber, {
                value: row.delay_ms,
                size: 'small',
                min: 0,
                max: 600000,
                placeholder: '固定毫秒',
                style: { width: '100%' },
                'onUpdate:value': (v) => {
                  row.delay_ms = v ?? 0
                },
              })
            : h(NInputGroup, { size: 'small' }, {
              default: () => [
                h(NInputNumber, {
                  value: row.delay_ms_min,
                  size: 'small',
                  min: 0,
                  max: 600000,
                  placeholder: '下限ms',
                  style: { width: '50%' },
                  'onUpdate:value': (v) => {
                    row.delay_ms_min = v
                  },
                }),
                h(NInputNumber, {
                  value: row.delay_ms_max,
                  size: 'small',
                  min: 0,
                  max: 600000,
                  placeholder: '上限ms',
                  style: { width: '50%' },
                  'onUpdate:value': (v) => {
                    row.delay_ms_max = v
                  },
                }),
              ],
            }),
      ],
    }),
  },
  {
    title: '事务',
    key: 'transaction',
    width: 140,
    render: (row) => h(NInput, {
      value: row.transaction,
      size: 'small',
      placeholder: '如 Login',
      clearable: true,
      'onUpdate:value': (v) => {
        row.transaction = v
      },
    }),
  },
  {
    title: '数据集',
    key: 'dataset',
    width: 330,
    render: (row) => h(NSpace, { vertical: true, size: 4 }, {
      default: () => [
        h(NSelect, {
          value: row.ds_code,
          options: datasetOptionsByApi.value[row.api_id] || [],
          size: 'small',
          placeholder: '绑定数据集（可选）',
          clearable: true,
          filterable: true,
          style: { width: '100%' },
          'onUpdate:value': (v) => handleDsChange(row, v),
        }),
        ...(row.ds_code ? [
          h(NSelect, {
            value: row.dataset_strategy,
            options: PERF_DATASET_STRATEGY_OPTIONS,
            size: 'small',
            style: { width: '100%' },
            'onUpdate:value': (v) => {
              row.dataset_strategy = v
            },
          }),
        ] : []),
      ],
    }),
  },
  {
    title: '启用',
    key: 'enabled',
    width: 70,
    render: (row) => h(NSwitch, {
      value: row.enabled,
      size: 'small',
      'onUpdate:value': (v) => {
        row.enabled = v
      },
    }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    render: (_row, index) => h(NSpace, { size: 0, wrap: false }, {
      default: () => [
        h(NButton, { size: 'tiny', quaternary: true, disabled: index === 0, onClick: () => moveItem(index, -1) },
            { default: () => '↑' }),
        h(NButton, { size: 'tiny', quaternary: true, disabled: index === form.scene_items.length - 1, onClick: () => moveItem(index, 1) },
            { default: () => '↓' }),
        h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => removeItem(index) },
            { default: () => '删' }),
      ],
    }),
  },
])

// ---------- SLA 目标 ----------

function addTarget() {
  form.perf_targets.push({
    scope: 'global',
    target: 'avg_rt',
    api_code: null,
    transaction: null,
    op: 'le',
    expect: null,
    severity: 'fail',
    min_total_requests: null,
    min_duration_seconds: null,
  })
}

function removeTarget(index) {
  form.perf_targets.splice(index, 1)
}

function handleTargetScopeChange(target) {
  target.api_code = null
  target.transaction = null
}

// ---------- 校验（与 perf_scene_schema 同口径，失败定位到步骤） ----------

function validateStep(step) {
  if (step === 1) {
    if (!form.scene_project) return { step: 1, message: '请选择所属应用' }
    if (!(form.scene_name || '').trim()) return { step: 1, message: '请输入场景名称' }
    return null
  }
  if (step === 2 || step === 3) {
    if (!form.scene_items.length) return { step: 2, message: '请至少选择 1 个接口' }
    const enabled = form.scene_items.filter((item) => item.enabled)
    if (!enabled.length) return { step: 3, message: '至少需要 1 个启用状态的接口项' }
    const measured = enabled.filter((item) => item.role === 'measured')
    if (!measured.length) return { step: 3, message: '至少需要 1 个角色为被测(measured)的接口项（准备与抽查项不计业务指标）' }
    if (form.run_mode === 'single' && measured.length > 1) {
      return { step: 3, message: '单接口模式只允许 1 个被测项，多接口混合请改用混合流量模式' }
    }
    if (form.run_mode === 'mixed' && measured.length < 2) {
      return { step: 3, message: '混合流量模式需要至少 2 个被测项，否则请改用单接口模式' }
    }
    for (const item of form.scene_items) {
      if (item.enabled && item.role === 'measured' && item.delay_mode === 'uniform') {
        if (item.delay_ms_min === null || item.delay_ms_max === null) {
          return { step: 3, message: `接口[${item.api_name}]区间思考时间需填写上下限` }
        }
        if (item.delay_ms_min > item.delay_ms_max) {
          return { step: 3, message: `接口[${item.api_name}]思考时间下限不得大于上限` }
        }
      }
    }
    return null
  }
  for (let index = 0; index < form.perf_targets.length; index += 1) {
    const target = form.perf_targets[index]
    if (target.expect === null || target.expect === undefined) {
      return { step: 4, message: `第 ${index + 1} 条 SLA 目标缺少期望值` }
    }
    if (target.scope === 'api' && !target.api_code) {
      return { step: 4, message: `第 ${index + 1} 条 SLA 目标需选择接口` }
    }
    if (target.scope === 'transaction' && !target.transaction) {
      return { step: 4, message: `第 ${index + 1} 条 SLA 目标需填写事务` }
    }
  }
  if (form.assert_mode === 'sample_ratio' && (!form.sample_ratio || form.sample_ratio <= 0)) {
    return { step: 4, message: '抽样断言必须设置采样比例' }
  }
  return null
}

function handleNext() {
  const error = validateStep(current.value)
  if (error) {
    window.$message?.error(error.message)
    return
  }
  if (current.value === 1) {
    // 接口项确定后才能拉取各自名下的数据集候选
    loadDatasetsForApis(form.scene_items.map((item) => item.api_id))
  }
  current.value += 1
}

// ---------- 打开与保存 ----------

/** 后端详情 → 表单形态（scene_items 保留展示字段；journey 场景拒绝在本表单编辑） */
function applyDetail(detail) {
  if (detail.run_mode === 'journey') {
    window.$message?.warning('业务链路(journey)模式编辑器将在后续版本提供，暂不支持在该场景表单编辑')
    return false
  }
  Object.assign(form, emptyForm(), {
    ...detail,
    scene_items: (detail.scene_items || []).map((item) => ({ ...item, enabled: item.enabled !== false })),
    perf_targets: (detail.perf_targets || []).map((target) => ({ ...target })),
    baseline_policy: { ...emptyForm().baseline_policy, ...(detail.baseline_policy || {}) },
  })
  resequence()
  return true
}

/**
 * 打开抽屉。
 * @param {Object|null} payload null 新增；{ scene_id } 编辑
 */
async function open(payload = null) {
  editingId.value = null
  Object.assign(form, emptyForm())
  current.value = 1
  show.value = true
  if (!projectOptions.value.length) loadProjects()
  if (!payload) return
  try {
    const res = await api.getPerfScene({ scene_id: payload.scene_id })
    editingId.value = payload.scene_id
    if (!applyDetail(res.data || {})) {
      show.value = false
      return
    }
    loadDatasetsForApis(form.scene_items.map((item) => item.api_id))
  } catch (e) {
    show.value = false
  }
}

/** 表单形态 → PerfSceneCreate/Update payload（编排整体覆盖） */
function buildPayload() {
  const payload = {
    scene_project: form.scene_project,
    scene_name: (form.scene_name || '').trim(),
    scene_desc: (form.scene_desc || '').trim() || null,
    run_mode: form.run_mode,
    scene_items: form.scene_items.map((item) => ({
      seq: item.seq,
      api_code: item.api_code,
      api_id: item.api_id,
      api_name: item.api_name,
      role: item.role,
      weight: item.weight || 1,
      delay_mode: item.delay_mode,
      delay_ms: item.delay_mode === 'fixed' ? (item.delay_ms || 0) : 0,
      delay_ms_min: item.delay_mode === 'uniform' ? item.delay_ms_min : null,
      delay_ms_max: item.delay_mode === 'uniform' ? item.delay_ms_max : null,
      transaction: (item.transaction || '').trim() || null,
      ds_code: item.ds_code || null,
      ds_name: item.ds_name,
      dataset_strategy: item.dataset_strategy,
      override: null,
      enabled: item.enabled,
    })),
    perf_targets: form.perf_targets.length
      ? form.perf_targets.map((target) => ({
          scope: target.scope,
          target: target.target,
          api_code: target.scope === 'api' ? target.api_code : null,
          transaction: target.scope === 'transaction' ? target.transaction : null,
          op: target.op,
          expect: target.expect,
          severity: target.severity,
          min_total_requests: target.min_total_requests || null,
          min_duration_seconds: target.min_duration_seconds || null,
        }))
      : null,
    baseline_report_code: (form.baseline_report_code || '').trim() || null,
    baseline_policy: [
      form.baseline_policy.p95_degrade_pct,
      form.baseline_policy.qps_degrade_pct,
      form.baseline_policy.error_rate_increase,
    ].some((value) => value !== null && value !== undefined)
      ? { ...form.baseline_policy }
      : null,
    warmup_seconds: form.warmup_seconds ?? null,
    error_rate_threshold: form.error_rate_threshold ?? null,
    assert_mode: form.assert_mode,
    sample_ratio: form.sample_ratio,
    inject_perf_tag: form.inject_perf_tag,
  }
  if (isEdit.value) payload.scene_id = editingId.value
  return payload
}

async function handleSave() {
  // 四步串行校验，失败跳转到最早出错的步骤
  for (let step = 1; step <= 4; step += 1) {
    const error = validateStep(step)
    if (error) {
      current.value = error.step
      window.$message?.error(error.message)
      return
    }
  }
  try {
    saving.value = true
    const payload = buildPayload()
    if (isEdit.value) {
      await api.updatePerfScene(payload)
    } else {
      await api.createPerfScene(payload)
    }
    window.$message?.success('保存成功')
    show.value = false
    emit('saved')
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.card-title {
  font-weight: 600;
}

.item-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.item-card-title {
  font-weight: 600;
}
</style>
