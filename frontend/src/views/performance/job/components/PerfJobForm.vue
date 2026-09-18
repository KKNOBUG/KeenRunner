<!--
  PerfJobForm — 数据作业新增抽屉（带外作业：prepare造数 / verify校验 / cleanup清理）

  作业执行复用 autotest 功能链跑脚本用例 N 轮；prepare 每轮从执行明细提取
  extract_fields 组一行数据，全部成功后回写数据集（归属接口由 bind_api 派生）。
  契约无 update 端点（配置变更重建），本抽屉只承载新增。
-->
<template>
  <n-drawer v-model:show="show" :width="640" placement="right">
    <n-drawer-content title="新增数据作业" closable>
      <n-form
          ref="formRef"
          :model="form"
          label-placement="left"
          label-width="96"
          require-mark-placement="right-hanging"
      >
        <n-space vertical :size="16">
          <!-- 基础信息 -->
          <n-card title="基础信息" size="small">
            <n-grid :cols="24" :x-gap="12">
              <n-gi :span="12">
                <n-form-item label="作业名称" path="job_name" :rule="{ required: true, message: '请输入作业名称' }">
                  <n-input v-model:value="form.job_name" placeholder="请输入作业名称" clearable />
                </n-form-item>
              </n-gi>
              <n-gi :span="12">
                <n-form-item label="作业类型" path="job_type">
                  <n-radio-group v-model:value="form.job_type" name="job_type">
                    <n-space>
                      <n-radio value="prepare">造数</n-radio>
                      <n-radio value="verify">校验</n-radio>
                      <n-radio value="cleanup">清理</n-radio>
                    </n-space>
                  </n-radio-group>
                </n-form-item>
              </n-gi>
              <n-gi :span="24">
                <n-form-item label="作业描述" path="job_desc">
                  <n-input v-model:value="form.job_desc" type="textarea" :rows="2" placeholder="作业描述（可选）" />
                </n-form-item>
              </n-gi>
            </n-grid>
          </n-card>

          <!-- 执行定义：复用功能用例的 DB/Redis/HTTP/断言能力 -->
          <n-card title="执行定义" size="small">
            <n-grid :cols="24" :x-gap="12">
              <n-gi :span="24">
                <n-form-item label="脚本用例" path="quote_case_id" :rule="{ required: true, type: 'number', message: '请选择脚本用例' }">
                  <n-select
                      v-model:value="form.quote_case_id"
                      :options="caseOptions"
                      :loading="caseLoading"
                      placeholder="公共脚本/用户脚本(具备造数与查库断言能力)"
                      clearable
                      filterable
                  />
                </n-form-item>
              </n-gi>
              <n-gi :span="12">
                <n-form-item label="执行轮数" path="loop_times">
                  <n-input-number v-model:value="form.loop_times" :min="1" :max="1000" style="width: 100%" />
                </n-form-item>
              </n-gi>
              <n-gi :span="12">
                <n-form-item label="功能数据源" path="dataset_name">
                  <n-input v-model:value="form.dataset_name" placeholder="功能参数化数据源名称(可选)" clearable />
                </n-form-item>
              </n-gi>
            </n-grid>
            <n-text depth="3" style="font-size: 12px">
              顺序执行 N 轮，每轮一次完整功能执行并独立出报告；任一轮失败即中止，不产出半成品数据。
            </n-text>
          </n-card>

          <!-- 产出与联动：仅造数作业需要 -->
          <n-card v-if="isPrepare" title="产出与联动" size="small">
            <n-grid :cols="24" :x-gap="12">
              <n-gi :span="24">
                <n-form-item label="归属接口" path="bind_api_id" :rule="prepareRequiredNumber">
                  <n-select
                      v-model:value="form.bind_api_id"
                      :options="apiOptions"
                      :loading="apiLoading"
                      placeholder="产出数据集归属的压测接口"
                      clearable
                      filterable
                  />
                </n-form-item>
              </n-gi>
              <n-gi :span="24">
                <n-form-item label="提取列" path="extract_fields" :rule="prepareRequiredFields">
                  <n-dynamic-tags v-model:value="form.extract_fields" :max="50" />
                </n-form-item>
              </n-gi>
            </n-grid>
            <n-alert :bordered="false" type="info">
              提取列与脚本用例的提取变量名(或会话变量键)一致，如 orderId、token；
              每轮执行各提取一列取值组成一行数据，全部轮次成功后回写数据集供场景消费。
            </n-alert>
          </n-card>

          <n-card title="场景联动" size="small">
            <n-form-item label="关联场景" path="bind_scene_id">
              <n-select
                  v-model:value="form.bind_scene_id"
                  :options="sceneOptions"
                  :loading="sceneLoading"
                  placeholder="关联压测场景(可选, 供施压链路联动触发)"
                  clearable
                  filterable
              />
            </n-form-item>
            <n-text depth="3" style="font-size: 12px">
              校验/清理作业关联场景后，可在施压后自动触发；造数作业关联后可在施压前自动铺底（联动逐步开放）。
            </n-text>
          </n-card>
        </n-space>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button @click="show = false">取 消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">保 存</n-button>
        </n-space>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDrawer, NDrawerContent, NDynamicTags, NForm, NFormItem,
  NGi, NGrid, NInput, NInputNumber, NRadio, NRadioGroup, NSelect, NSpace, NText,
} from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfJobForm' })

const emit = defineEmits(['saved'])

const show = defineModel('show', { type: Boolean, default: false })

const formRef = ref(null)
const saving = ref(false)
const caseOptions = ref([])
const caseLoading = ref(false)
const apiOptions = ref([])
const apiLoading = ref(false)
const sceneOptions = ref([])
const sceneLoading = ref(false)

const emptyForm = () => ({
  job_name: null,
  job_desc: null,
  job_type: 'prepare',
  quote_case_id: null,
  loop_times: 1,
  dataset_name: null,
  bind_api_id: null,
  bind_scene_id: null,
  extract_fields: [],
})

const form = reactive(emptyForm())

const isPrepare = computed(() => form.job_type === 'prepare')

/** 造数专属必填规则（校验/清理类型不要求，字段隐藏） */
const prepareRequiredNumber = computed(() =>
    isPrepare.value ? { required: true, type: 'number', message: '造数作业需选择归属接口' } : undefined,
)
const prepareRequiredFields = computed(() =>
    isPrepare.value
        ? {
            required: true,
            type: 'array',
            message: '造数作业需声明提取列',
            trigger: ['change', 'blur'],
            validator: (_rule, value) => Array.isArray(value) && value.length > 0,
          }
        : undefined,
)

/** 脚本用例候选：公共脚本/用户脚本均可（执行链按 case_id 定位） */
async function loadCaseOptions() {
  caseLoading.value = true
  try {
    const res = await api.getApiTestcaseList({ page: 1, page_size: 200, state: 0 })
    caseOptions.value = (res.data || []).map((row) => ({
      label: row.case_name,
      value: row.case_id,
    }))
  } catch (e) {
    caseOptions.value = []
  } finally {
    caseLoading.value = false
  }
}

/** 归属接口候选：压测接口为人工维护资产，一次拉取后本地过滤 */
async function loadApiOptions() {
  apiLoading.value = true
  try {
    const res = await api.searchPerfApiList({ page: 1, page_size: 200, state: 0 })
    apiOptions.value = (res.data || []).map((row) => ({
      label: row.api_name,
      value: row.api_id,
    }))
  } catch (e) {
    apiOptions.value = []
  } finally {
    apiLoading.value = false
  }
}

/** 关联场景候选：对齐任务表单的场景拉取口径 */
async function loadSceneOptions() {
  sceneLoading.value = true
  try {
    const res = await api.searchPerfSceneList({ page: 1, page_size: 100, state: 0 })
    sceneOptions.value = (res.data || []).map((row) => ({
      label: row.scene_name,
      value: row.scene_id,
    }))
  } catch (e) {
    sceneOptions.value = []
  } finally {
    sceneLoading.value = false
  }
}

/** 打开抽屉（仅新增语义） */
function open() {
  Object.assign(form, emptyForm())
  formRef.value?.restoreValidation()
  show.value = true
  if (!caseOptions.value.length) loadCaseOptions()
  if (!apiOptions.value.length) loadApiOptions()
  if (!sceneOptions.value.length) loadSceneOptions()
}

/** 表单形态 → PerfJobCreate payload */
function buildPayload() {
  return {
    job_name: (form.job_name || '').trim(),
    job_desc: (form.job_desc || '').trim() || null,
    job_type: form.job_type,
    quote_case_id: form.quote_case_id,
    loop_times: form.loop_times || 1,
    dataset_name: (form.dataset_name || '').trim() || null,
    bind_api_id: form.bind_api_id || null,
    bind_scene_id: form.bind_scene_id || null,
    extract_fields: isPrepare.value
        ? form.extract_fields.map((name) => String(name).trim()).filter(Boolean)
        : [],
  }
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  try {
    saving.value = true
    await api.createPerfJob(buildPayload())
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
