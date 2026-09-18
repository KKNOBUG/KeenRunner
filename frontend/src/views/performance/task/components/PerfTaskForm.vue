<!--
  PerfTaskForm — 压测任务编辑抽屉（场景引用 + 施压环境 + 负载参数）

  任务不定义流量结构与判定口径（一律来自所选场景）；施压环境复用 autotest
  环境三级链（与功能调试同源接口）；阶梯参数仅 load_mode=stepped 时启用，
  目标吞吐仅 load_mode=rps 时启用（引擎按 并发上限÷目标RPS 做每虚拟用户节流）。
-->
<template>
  <n-drawer v-model:show="show" :width="720" placement="right">
    <n-drawer-content :title="drawerTitle" closable>
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
                <n-form-item label="所属应用" path="perf_project" :rule="projectRule">
                  <n-select
                      v-model:value="form.perf_project"
                      :options="projectOptions"
                      :disabled="isEdit"
                      placeholder="请选择所属应用"
                      clearable
                      filterable
                      @update:value="handleProjectChange"
                  />
                </n-form-item>
              </n-gi>
              <n-gi :span="12">
                <n-form-item label="任务名称" path="perf_name" :rule="{ required: true, message: '请输入任务名称' }">
                  <n-input v-model:value="form.perf_name" placeholder="请输入任务名称" clearable />
                </n-form-item>
              </n-gi>
              <n-gi :span="24">
                <n-form-item label="任务描述" path="perf_desc">
                  <n-input v-model:value="form.perf_desc" type="textarea" :rows="2" placeholder="任务描述（可选）" />
                </n-form-item>
              </n-gi>
            </n-grid>
          </n-card>

          <!-- 施压场景 -->
          <n-card title="施压场景" size="small">
            <n-form-item label="压测场景" path="scene_code" :rule="{ required: true, message: '请选择压测场景' }">
              <n-select
                  v-model:value="form.scene_code"
                  :options="sceneOptions"
                  :loading="sceneLoading"
                  :disabled="!form.perf_project"
                  placeholder="请先选择所属应用"
                  clearable
                  filterable
                  @update:value="handleSceneChange"
              />
            </n-form-item>
            <n-space v-if="selectedScene" :size="8">
              <n-tag size="small" :type="selectedScene.run_mode === 'mixed' ? 'warning' : 'info'" :bordered="false">
                {{ selectedScene.run_mode === 'mixed' ? '混合流量' : '单接口' }}
              </n-tag>
              <n-tag size="small" :bordered="false">{{ selectedScene.item_count }} 个接口项</n-tag>
              <n-text depth="3" style="font-size: 12px">流量结构与 SLA 判定口径来自场景编排，任务只负责负载与调度</n-text>
            </n-space>
          </n-card>

          <!-- 施压环境：与自动化测试同一套环境链，host/port 由后端执行时实时解析 -->
          <n-card title="施压环境" size="small">
            <n-grid :cols="24" :x-gap="12">
              <n-gi :span="12">
                <n-form-item label="环境名称" path="env_name">
                  <n-select
                      v-model:value="form.env_name"
                      :options="envOptions"
                      :loading="envLoading"
                      :disabled="!form.perf_project"
                      clearable
                      filterable
                      placeholder="场景内接口全为绝对地址时可留空"
                      @update:value="handleEnvChange"
                  />
                </n-form-item>
              </n-gi>
              <n-gi :span="12">
                <n-form-item label="缺省APP配置" path="env_config_name">
                  <n-select
                      v-model:value="form.env_config_name"
                      :options="configOptions"
                      :loading="configLoading"
                      :disabled="!form.env_name"
                      clearable
                      filterable
                      placeholder="接口未指定配置时使用"
                  />
                </n-form-item>
              </n-gi>
            </n-grid>
            <n-alert :bordered="false" type="info">
              接口请求地址为相对路径时，执行时由后端按「所属应用 + 环境名称 + APP配置」解析出
              host/port 组装完整地址，与自动化测试取值口径一致；写全 http(s):// 地址时原样使用。
            </n-alert>
          </n-card>

          <!-- 负载参数 -->
          <n-card title="负载参数" size="small">
            <n-form-item label="施压模式" path="load_mode">
              <n-radio-group v-model:value="form.load_mode" name="load_mode">
                <n-space>
                  <n-radio value="fixed">固定并发</n-radio>
                  <n-radio value="stepped">阶梯加压</n-radio>
                  <n-radio value="rps">RPS 吞吐</n-radio>
                </n-space>
              </n-radio-group>
            </n-form-item>
            <!-- fixed 与 rps 共用用户池三参数; rps 追加目标吞吐(引擎节流基准) -->
            <n-grid v-if="form.load_mode !== 'stepped'" :cols="24" :x-gap="12">
              <n-gi :span="8">
                <n-form-item label="并发用户" path="concurrent_users" :rule="fixedRule">
                  <n-input-number v-model:value="form.concurrent_users" :min="1" :max="5000" style="width: 100%" />
                </n-form-item>
              </n-gi>
              <n-gi :span="8">
                <n-form-item label="启动速率" path="spawn_rate" :rule="fixedRule">
                  <n-input-number v-model:value="form.spawn_rate" :min="1" :max="1000" style="width: 100%" />
                </n-form-item>
              </n-gi>
              <n-gi :span="8">
                <n-form-item label="持续(秒)" path="run_duration" :rule="fixedRule">
                  <n-input-number v-model:value="form.run_duration" :min="1" :max="28800" style="width: 100%" />
                </n-form-item>
              </n-gi>
              <n-gi v-if="form.load_mode === 'rps'" :span="8">
                <n-form-item label="目标RPS" path="target_rps" :rule="targetRpsRule">
                  <n-input-number
                      v-model:value="form.target_rps"
                      :min="0.1"
                      :max="1000000"
                      :step="10"
                      placeholder="稳态每秒请求数"
                      style="width: 100%"
                  />
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
            <n-space vertical :size="4">
              <n-text depth="3" style="font-size: 12px">
                并发上限 5000、持续上限 8 小时（受消息可见性与任务硬时限约束）；阶梯模式按档位爬坡至峰值并发。
              </n-text>
              <n-text v-if="form.load_mode === 'rps'" depth="3" style="font-size: 12px">
                吞吐模式：每个虚拟用户按「并发上限 ÷ 目标RPS」节流迭代间隔（与思考时间合并取最大），
                稳态吞吐≈目标RPS；并发池不足以跑出目标吞吐时按并发上限全速施压。
              </n-text>
            </n-space>
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
import { computed, reactive, ref, watch } from 'vue'
import {
  NAlert, NButton, NCard, NDrawer, NDrawerContent, NForm, NFormItem, NGi, NGrid, NInput,
  NInputNumber, NRadio, NRadioGroup, NSelect, NSpace, NTag, NText,
} from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfTaskForm' })

const emit = defineEmits(['saved'])

const show = defineModel('show', { type: Boolean, default: false })

/** 编辑中的任务ID；null 表示新增 */
const editingId = ref(null)

const formRef = ref(null)
const saving = ref(false)
const projectOptions = ref([])
const sceneOptions = ref([])
const sceneLoading = ref(false)

const emptyForm = () => ({
  perf_project: null,
  perf_name: null,
  perf_desc: null,
  scene_code: null,
  env_name: null,
  env_config_name: null,
  load_mode: 'fixed',
  concurrent_users: 1,
  spawn_rate: 1,
  run_duration: 60,
  step_start_users: null,
  step_increment: null,
  step_duration: null,
  step_max_users: null,
  step_sustain_duration: null,
  target_rps: null,
})

const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value != null)
const drawerTitle = computed(() => (isEdit.value ? `编辑压测任务 · ${form.perf_name || ''}` : '新增压测任务'))

/** 编辑模式应用归属锁定：跨应用迁移会让场景引用与环境解析同时失效 */
const projectRule = computed(() =>
    isEdit.value ? undefined : { required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] },
)
const fixedRule = computed(() =>
    form.load_mode !== 'stepped' ? { required: true, type: 'number', message: '必填' } : undefined,
)
const steppedRule = computed(() =>
    form.load_mode === 'stepped' ? { required: true, type: 'number', message: '阶梯模式必填' } : undefined,
)
const targetRpsRule = computed(() =>
    form.load_mode === 'rps' ? { required: true, type: 'number', message: '吞吐模式必填' } : undefined,
)

/** 当前选中场景行（携带 run_mode/item_count 展示口径） */
const selectedScene = computed(() =>
    sceneOptions.value.find((opt) => opt.value === form.scene_code)?.raw || null,
)

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

/** 场景候选只列同应用启用场景（任务保存期会回查场景归属） */
async function loadSceneOptions() {
  if (!form.perf_project) {
    sceneOptions.value = []
    return
  }
  sceneLoading.value = true
  try {
    const res = await api.searchPerfSceneList({ scene_project: form.perf_project, page_size: 100, state: 0 })
    sceneOptions.value = (res.data || []).map((row) => ({
      label: row.scene_name,
      value: row.scene_code,
      raw: row,
    }))
    // 已选场景不在当前应用候选中则清空，避免提交后触发后端回查失败
    if (form.scene_code && !sceneOptions.value.some((opt) => opt.value === form.scene_code)) {
      form.scene_code = null
    }
  } catch (e) {
    sceneOptions.value = []
  } finally {
    sceneLoading.value = false
  }
}

/** 新增态切换应用：场景与环境选择随应用失效（编辑态应用锁定，不会触发） */
function handleProjectChange() {
  form.scene_code = null
  form.env_name = null
  form.env_config_name = null
  loadSceneOptions()
  loadEnvNames(form.perf_project)
}

function handleSceneChange() {
  /* 场景仅作为引用切换，无联动清空项 */
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

watch(() => [form.perf_project, form.env_name], ([projectId, envName]) => loadConfigNames(projectId, envName))

// ---------- 打开与保存 ----------

/** 后端详情 → 表单形态（阶梯字段按当前模式显隐，数值原样回填） */
function applyDetail(detail) {
  Object.assign(form, emptyForm(), {
    ...detail,
    scene_code: detail.scene_code || null,
  })
  // 编辑态场景候选按已载入的应用加载，依赖「不在候选则清空」兜底失效引用
  loadSceneOptions()
  loadEnvNames(form.perf_project)
}

/**
 * 打开抽屉。
 * @param {Object|null} payload null 新增；{ perf_id } 编辑
 */
async function open(payload = null) {
  editingId.value = null
  Object.assign(form, emptyForm())
  sceneOptions.value = []
  envOptions.value = []
  configOptions.value = []
  show.value = true
  if (!projectOptions.value.length) loadProjects()
  if (!payload) return
  try {
    const res = await api.getPerfTask({ perf_id: payload.perf_id })
    editingId.value = payload.perf_id
    applyDetail(res.data || {})
  } catch (e) {
    show.value = false
  }
}

/** 表单形态 → PerfTaskCreate/Update payload（负载字段整体覆盖） */
function buildPayload() {
  const stepped = form.load_mode === 'stepped'
  const rps = form.load_mode === 'rps'
  const payload = {
    perf_project: form.perf_project,
    perf_name: (form.perf_name || '').trim(),
    perf_desc: (form.perf_desc || '').trim() || null,
    scene_code: form.scene_code,
    env_name: form.env_name || null,
    env_config_name: form.env_config_name || null,
    load_mode: form.load_mode,
    concurrent_users: form.concurrent_users || 1,
    spawn_rate: form.spawn_rate || 1,
    run_duration: form.run_duration || 60,
    step_start_users: stepped ? form.step_start_users : null,
    step_increment: stepped ? form.step_increment : null,
    step_duration: stepped ? form.step_duration : null,
    step_max_users: stepped ? form.step_max_users : null,
    step_sustain_duration: stepped ? form.step_sustain_duration : null,
    target_rps: rps ? form.target_rps : null,
  }
  if (isEdit.value) payload.perf_id = editingId.value
  return payload
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  try {
    saving.value = true
    const payload = buildPayload()
    if (isEdit.value) {
      await api.updatePerfTask(payload)
    } else {
      await api.createPerfTask(payload)
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
