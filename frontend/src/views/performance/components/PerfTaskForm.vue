<template>
  <div>
    <n-form ref="formRef" :model="form" label-placement="left" label-width="96" require-mark-placement="right-hanging">
      <n-space vertical :size="16">
        <!-- 基础信息 -->
        <n-card title="基础信息" size="small">
          <n-grid :cols="24" :x-gap="12">
            <n-gi :span="12">
              <n-form-item label="场景名称" path="perf_name" :rule="{ required: true, message: '请输入场景名称' }">
                <n-input v-model:value="form.perf_name" placeholder="请输入场景名称" clearable />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="所属应用" path="perf_project" :rule="{ required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] }">
                <n-select v-model:value="form.perf_project" :options="projectOptions" placeholder="请选择所属应用" clearable filterable />
              </n-form-item>
            </n-gi>
            <n-gi :span="24">
              <n-form-item label="场景描述" path="perf_desc">
                <n-input v-model:value="form.perf_desc" type="textarea" :rows="2" placeholder="场景描述（可选）" />
              </n-form-item>
            </n-gi>
          </n-grid>
        </n-card>

        <!-- 施压环境：与自动化测试同一套环境链，host/port 由后端执行时实时解析 -->
        <n-card title="施压环境" size="small">
          <n-grid :cols="24" :x-gap="12">
            <n-gi :span="8">
              <n-form-item label="环境名称" path="env_name" :rule="envRule">
                <n-select
                    v-model:value="form.env_name"
                    :options="envOptions"
                    :loading="envLoading"
                    :disabled="!form.perf_project"
                    clearable
                    filterable
                    placeholder="请先选择所属应用"
                    @update:value="handleEnvChange"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="缺省APP配置" path="env_config_name">
                <n-select
                    v-model:value="form.env_config_name"
                    :options="configOptions"
                    :loading="configLoading"
                    :disabled="!form.env_name"
                    clearable
                    filterable
                    placeholder="步骤未指定配置时使用"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-alert :bordered="false" type="info">
            用例里的请求地址通常是相对路径，执行时由后端按「所属应用 + 环境名称 + 步骤APP配置」解析出
            host/port 并组装完整地址，与自动化测试执行的取值口径一致；步骤已写全 http(s):// 地址时原样使用。
          </n-alert>
        </n-card>

        <!-- 场景来源：用例穿梭选择 + 施压步骤角色标注 -->
        <n-card title="场景来源" size="small">
          <PerfCaseSourcePanel
              v-if="loaded"
              ref="sourcePanelRef"
              v-model:quote-cases="form.quote_cases"
              v-model:execute-steps="form.execute_steps"
              :project-options="projectOptions"
              :perf-project="form.perf_project"
              :env-name="form.env_name"
              :env-config-name="form.env_config_name"
          />
        </n-card>

        <!-- 负载参数 -->
        <n-card title="负载参数" size="small">
          <n-form-item label="施压模式" path="load_mode">
            <n-radio-group v-model:value="form.load_mode">
              <n-radio value="fixed">固定并发</n-radio>
              <n-radio value="stepped">阶梯加压</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-grid v-if="form.load_mode === 'fixed'" :cols="24" :x-gap="12">
            <n-gi :span="8">
              <n-form-item label="并发用户" path="concurrent_users" :rule="{ required: true, message: '必填' }">
                <n-input-number v-model:value="form.concurrent_users" :min="1" :max="5000" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="启动速率" path="spawn_rate" :rule="{ required: true, message: '必填' }">
                <n-input-number v-model:value="form.spawn_rate" :min="1" :max="1000" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="持续(秒)" path="run_duration" :rule="{ required: true, message: '必填' }">
                <n-input-number v-model:value="form.run_duration" :min="1" :max="28800" style="width: 100%" />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-grid v-else :cols="24" :x-gap="12">
            <n-gi :span="8">
              <n-form-item label="起始并发" path="step_start_users" :rule="steppedRule">
                <n-input-number v-model:value="form.step_start_users" :min="1" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="每档递增" path="step_increment" :rule="steppedRule">
                <n-input-number v-model:value="form.step_increment" :min="1" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="每档秒数" path="step_duration" :rule="steppedRule">
                <n-input-number v-model:value="form.step_duration" :min="1" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="峰值并发" path="step_max_users" :rule="steppedRule">
                <n-input-number v-model:value="form.step_max_users" :min="1" style="width: 100%" />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="峰值持续" path="step_sustain_duration" :rule="steppedRule">
                <n-input-number v-model:value="form.step_sustain_duration" :min="1" style="width: 100%" />
              </n-form-item>
            </n-gi>
          </n-grid>
        </n-card>
      </n-space>
    </n-form>

    <!-- 操作按钮 -->
    <n-space justify="end" mt-20>
      <n-button @click="emit('cancel')">返 回</n-button>
      <n-button type="primary" :loading="saving" @click="handleSave">保 存</n-button>
    </n-space>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  NAlert, NButton, NCard, NForm, NFormItem, NGi, NGrid, NInput, NInputNumber,
  NRadio, NRadioGroup, NSelect, NSpace,
} from 'naive-ui'
import PerfCaseSourcePanel from './PerfCaseSourcePanel.vue'
import api from '@/api'

defineOptions({ name: 'PerfTaskForm' })

const props = defineProps({
  /** 编辑模式的任务ID；为空表示新增场景 */
  perfId: { type: Number, default: null },
})

const emit = defineEmits(['saved', 'cancel'])

/** 与后端 PERF_EXECUTE_STEPS_MAX/PERF_QUOTE_CASES_MAX 对齐的表单初值 */
const emptyForm = () => ({
  perf_id: null,
  perf_code: null,
  perf_name: null,
  perf_project: null,
  perf_desc: null,
  env_name: null,
  env_config_name: null,
  quote_cases: [],
  execute_steps: [],
  load_mode: 'fixed',
  concurrent_users: 1,
  spawn_rate: 1,
  run_duration: 60,
  step_start_users: null,
  step_increment: null,
  step_duration: null,
  step_max_users: null,
  step_sustain_duration: null,
})

const form = reactive(emptyForm())
/** 任务详情是否已就绪：编辑模式需等数据到位再挂载来源面板（其内部按快照回查用例与步骤） */
const loaded = ref(false)

const formRef = ref(null)
const saving = ref(false)
const sourcePanelRef = ref(null)

const steppedRule = computed(() =>
    form.load_mode === 'stepped' ? { required: true, message: '阶梯模式必填', type: 'number' } : undefined,
)
/** 存在相对路径步骤时必须选择施压环境（否则后端无法补齐 host） */
const hasRelativeUrl = computed(() =>
    (form.execute_steps || []).some((step) => !/^https?:\/\//i.test(String(step?.request_url || '').trim())),
)
const envRule = computed(() =>
    hasRelativeUrl.value ? { required: true, message: '步骤含相对地址，请选择施压环境' } : undefined,
)

const projectOptions = ref([])
async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    // 项目行主键被后端 replace_fields 重命名为 project_id（无 id 字段），对齐 tags 页先例
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

// ---------- 施压环境两级下拉（复用 autotest 环境链接口） ----------
const envOptions = ref([])
const envLoading = ref(false)
const configOptions = ref([])
const configLoading = ref(false)

async function loadEnvNames(projectId) {
  if (!projectId) {
    envOptions.value = []
    return
  }
  envLoading.value = true
  try {
    // 仅返回该应用挂载了 APP 配置的环境名称，与调试链路取数口径一致
    const res = await api.queryAssignConfigEnvs({ project_id: projectId, env_type: 'app' })
    const names = Array.isArray(res?.data) ? res.data : []
    envOptions.value = names.map((name) => ({ label: name, value: name }))
  } catch (e) {
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

async function loadConfigNames(projectId, envName) {
  if (!projectId || !envName) {
    configOptions.value = []
    return
  }
  configLoading.value = true
  try {
    const res = await api.getEnvConfigList({
      project_id: projectId,
      env_name: envName,
      env_type: 'app',
      page: 1,
      page_size: 100,
    })
    const rows = Array.isArray(res?.data) ? res.data : []
    configOptions.value = rows.map((row) => ({ label: row.config_name, value: row.config_name }))
  } catch (e) {
    configOptions.value = []
  } finally {
    configLoading.value = false
  }
}

function handleEnvChange() {
  form.env_config_name = null
}

watch(() => form.perf_project, (projectId, prevProjectId) => {
  loadEnvNames(projectId)
  // 应用变更原选择失效（环境/配置均按应用挂载）
  if (prevProjectId != null && Number(projectId) !== Number(prevProjectId)) {
    form.env_name = null
    form.env_config_name = null
  }
})

watch(() => [form.perf_project, form.env_name], ([projectId, envName]) => loadConfigNames(projectId, envName))

onMounted(async () => {
  loadProjects()
  if (props.perfId != null) {
    try {
      const res = await api.getPerfTask({ perf_id: props.perfId })
      Object.assign(form, emptyForm(), res.data || {})
    } catch (e) {
      /* 拦截器已提示，保持空白新增表单 */
    }
  }
  loaded.value = true
})

/** 表单值 → 后端 payload（脚手架与执行回写字段剔除） */
function buildPayload() {
  const payload = { ...form }
  delete payload.perf_code
  delete payload.created_time
  delete payload.updated_time
  delete payload.created_user
  delete payload.updated_user
  delete payload.last_execute_state
  delete payload.last_execute_time
  delete payload.last_execute_user
  delete payload.last_celery_id
  delete payload.last_execute_error
  if (props.perfId == null) delete payload.perf_id
  return payload
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  const invalidMessage = sourcePanelRef.value?.validate?.() || ''
  if (invalidMessage) {
    window.$message?.error(invalidMessage)
    return
  }
  try {
    saving.value = true
    const payload = buildPayload()
    if (props.perfId != null) {
      await api.updatePerfTask(payload)
    } else {
      await api.createPerfTask(payload)
    }
    window.$message?.success('保存成功')
    emit('saved')
  } catch (e) {
    /* 接口错误由拦截器统一提示 */
  } finally {
    saving.value = false
  }
}
</script>
