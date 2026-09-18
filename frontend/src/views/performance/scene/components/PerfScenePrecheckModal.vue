<!--
  PerfScenePrecheckModal — 场景连通性预检弹窗

  对场景内启用接口逐个发 1 次真实请求（复用调试链口径，结论同步回写接口调试状态），
  连通/业务两列分开回显便于区分「网络不通」与「业务不达标」；接口地址为绝对地址时环境可留空。
-->
<template>
  <n-modal v-model:show="show" preset="card" title="场景连通性预检" style="width: 960px">
    <n-space vertical :size="12">
      <n-alert type="info" :show-icon="true">
        预检会对每个启用接口各发 1 次真实请求（请求构造与环境解析口径与施压一致），结论同步回写接口调试状态；
        全部连通且业务通过后即可满足施压闸门「引用接口均有调试通过结论」的要求。
      </n-alert>

      <n-space :size="8" :wrap-item="false">
        <n-select
            v-model:value="envName"
            :options="envOptions"
            :loading="envLoading"
            :disabled="!sceneProject"
            placeholder="预检环境(绝对地址可留空)"
            clearable
            filterable
            style="width: 220px"
            @update:value="handleEnvChange"
        />
        <n-select
            v-model:value="envConfigName"
            :options="configOptions"
            :loading="configLoading"
            :disabled="!envName"
            placeholder="缺省APP配置(可选)"
            clearable
            filterable
            style="width: 200px"
        />
        <n-button type="primary" secondary :loading="checking" @click="handleRun">开始预检</n-button>
        <n-text v-if="sceneName" depth="3" style="font-size: 12px; line-height: 28px">{{ sceneName }}</n-text>
      </n-space>

      <n-space v-if="summary" :size="8" :wrap-item="false">
        <n-tag size="small" :bordered="false">接口项 {{ summary.total }}</n-tag>
        <n-tag size="small" type="info" :bordered="false">启用 {{ summary.enabled_total }}</n-tag>
        <n-tag size="small" :type="summary.connected_count === summary.enabled_total ? 'success' : 'warning'" :bordered="false">
          连通 {{ summary.connected_count }}
        </n-tag>
        <n-tag size="small" :type="summary.success_count === summary.enabled_total ? 'success' : 'warning'" :bordered="false">
          业务通过 {{ summary.success_count }}
        </n-tag>
      </n-space>

      <n-data-table
          :columns="columns"
          :data="items"
          :loading="checking"
          :pagination="false"
          :row-key="(row) => `${row.seq}-${row.api_code}`"
          size="small"
          :max-height="420"
          :scroll-x="900"
      />
    </n-space>
    <template #footer>
      <n-space justify="end">
        <n-button @click="show = false">关 闭</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { h, ref, watch } from 'vue'
import { NAlert, NButton, NDataTable, NModal, NSelect, NSpace, NTag, NText } from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfScenePrecheckModal' })

const show = defineModel('show', { type: Boolean, default: false })

// ---------- 预检目标与结果状态 ----------
const sceneId = ref(null)
const sceneName = ref(null)
const sceneProject = ref(null)
const checking = ref(false)
const summary = ref(null)
const items = ref([])

const ROLE_LABELS = { measured: '被测', prepare: '准备', verify: '抽查' }
const ROLE_TAG_TYPES = { measured: 'info', prepare: 'default', verify: 'warning' }

const columns = [
  { title: '序号', key: 'seq', width: 60 },
  { title: '接口名称', key: 'api_name', minWidth: 150, ellipsis: { tooltip: true } },
  {
    title: '角色',
    key: 'role',
    width: 70,
    render: (row) => h(NTag, { size: 'small', type: ROLE_TAG_TYPES[row.role] || 'default', bordered: false },
        { default: () => ROLE_LABELS[row.role] || row.role || '-' }),
  },
  {
    title: '连通',
    key: 'connected',
    width: 76,
    render: (row) => {
      if (row.skipped) return h(NText, { depth: 3 }, { default: () => '—' })
      const ok = row.connected
      return h(NTag, { size: 'small', type: ok ? 'success' : 'error' }, { default: () => (ok ? '连通' : '不通') })
    },
  },
  {
    title: '业务',
    key: 'success',
    width: 76,
    render: (row) => {
      if (row.skipped) return h(NText, { depth: 3 }, { default: () => '—' })
      const ok = row.success
      return h(NTag, { size: 'small', type: ok ? 'success' : 'error' }, { default: () => (ok ? '通过' : '未过') })
    },
  },
  {
    title: '状态码',
    key: 'status_code',
    width: 76,
    render: (row) => (row.skipped || row.status_code === null || row.status_code === undefined ? '—' : row.status_code),
  },
  {
    title: '耗时(ms)',
    key: 'elapsed_ms',
    width: 90,
    render: (row) => (row.skipped || row.elapsed_ms === null || row.elapsed_ms === undefined ? '—' : row.elapsed_ms),
  },
  { title: '请求地址', key: 'request_url', minWidth: 200, ellipsis: { tooltip: true }, render: (row) => row.request_url || '—' },
  { title: '错误信息', key: 'error', minWidth: 150, ellipsis: { tooltip: true }, render: (row) => row.error || '—' },
]

// ---------- 施压环境两级下拉（复用 autotest 环境链接口，口径与任务表单一致） ----------
const envName = ref(null)
const envConfigName = ref(null)
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

async function loadConfigNames(projectId, name) {
  if (!projectId || !name) {
    configOptions.value = []
    return
  }
  configLoading.value = true
  try {
    const res = await api.getEnvConfigList({
      project_id: projectId,
      env_name: name,
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
  envConfigName.value = null
}

watch([sceneProject, envName], ([projectId, name]) => loadConfigNames(projectId, name))

async function handleRun() {
  checking.value = true
  try {
    const res = await api.precheckPerfScene({
      scene_id: sceneId.value,
      env_name: envName.value || null,
      env_config_name: envConfigName.value || null,
    })
    const data = res.data || {}
    summary.value = {
      total: data.total ?? 0,
      enabled_total: data.enabled_total ?? 0,
      connected_count: data.connected_count ?? 0,
      success_count: data.success_count ?? 0,
    }
    items.value = data.items || []
    window.$message?.success(`预检完成：连通 ${summary.value.connected_count}/${summary.value.enabled_total}，业务通过 ${summary.value.success_count}/${summary.value.enabled_total}`)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    checking.value = false
  }
}

/**
 * 打开弹窗。
 * @param {Object} payload { scene_id, scene_name, scene_project }
 */
function open(payload = {}) {
  sceneId.value = payload.scene_id ?? null
  sceneName.value = payload.scene_name || null
  sceneProject.value = payload.scene_project ?? null
  envName.value = null
  envConfigName.value = null
  summary.value = null
  items.value = []
  show.value = true
  loadEnvNames(sceneProject.value)
}

defineExpose({ open })
</script>
