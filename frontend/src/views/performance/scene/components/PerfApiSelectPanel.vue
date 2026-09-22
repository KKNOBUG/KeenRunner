<!--
  PerfApiSelectPanel — 场景编排的压测接口选择弹窗

  数据来自 /perf/api/list_for_scene（不分页 + 名称搜索，仅启用态）；
  父组件传入已引用的 api_code 集合做重复排除，确认后回传选中的接口行。
-->
<template>
  <n-modal v-model:show="show" preset="card" title="选择压测接口" style="width: 760px">
    <n-space vertical :size="12">
      <n-space :size="8" :wrap-item="false">
        <n-input
            v-model:value="queryName"
            placeholder="接口名称(模糊)"
            clearable
            style="width: 220px"
            @keypress.enter="loadApis"
        />
        <n-button size="small" type="primary" secondary @click="loadApis">查询</n-button>
        <n-text v-if="excludedCount" depth="3" style="font-size: 12px; line-height: 28px">
          已引用 {{ excludedCount }} 个接口不在候选中重复展示
        </n-text>
      </n-space>
      <n-data-table
          v-model:checked-row-keys="checkedKeys"
          :columns="columns"
          :data="apiRows"
          :loading="loading"
          :pagination="false"
          :row-key="(row) => row.api_code"
          size="small"
          :max-height="380"
          :scroll-x="620"
      />
    </n-space>
    <template #footer>
      <n-space justify="end">
        <n-button @click="show = false">取 消</n-button>
        <n-button type="primary" :disabled="!checkedKeys.length" @click="handleConfirm">
          确定{{ checkedKeys.length ? `（${checkedKeys.length}）` : '' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { NButton, NDataTable, NInput, NModal, NSpace, NTag, NText } from 'naive-ui'

import api from '@/api'

defineOptions({ name: 'PerfApiSelectPanel' })

const emit = defineEmits(['confirm'])

const show = defineModel('show', { type: Boolean, default: false })

/** 已被场景引用的接口标识（候选中排除，避免同接口重复编排） */
const excludedCodes = ref([])
const excludedCount = computed(() => excludedCodes.value.length)

const queryName = ref(null)
const apiRows = ref([])
const loading = ref(false)
const checkedKeys = ref([])

const columns = [
  { type: 'selection' },
  { title: '接口名称', key: 'api_name', minWidth: 150, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'step_type',
    width: 70,
    render: (row) => h(NTag, { size: 'small', type: row.step_type === 'tcp' ? 'warning' : 'info' },
        { default: () => (row.step_type === 'tcp' ? 'TCP' : 'HTTP') }),
  },
  {
    title: '请求定义',
    key: 'request_url',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => `${(row.request_method || 'TCP').toUpperCase()} ${row.request_url || '-'}`,
  },
]

async function loadApis() {
  loading.value = true
  try {
    const res = await api.getPerfApisForScene({
      api_name: queryName.value || null,
    })
    apiRows.value = (res.data || []).filter((row) => !excludedCodes.value.includes(row.api_code))
    checkedKeys.value = []
  } catch (e) {
    apiRows.value = []
  } finally {
    loading.value = false
  }
}

function handleConfirm() {
  const selected = apiRows.value.filter((row) => checkedKeys.value.includes(row.api_code))
  if (!selected.length) return
  emit('confirm', selected)
  show.value = false
}

/**
 * 打开弹窗（接口资产全局共享，不再按应用过滤）。
 * @param {Object} payload { excludedCodes }
 */
function open(payload = {}) {
  excludedCodes.value = [...(payload.excludedCodes || [])]
  queryName.value = null
  checkedKeys.value = []
  show.value = true
  loadApis()
}

defineExpose({ open })
</script>
