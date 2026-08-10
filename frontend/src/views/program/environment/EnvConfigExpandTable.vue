<template>
  <div class="env-config-expand">
    <NDataTable
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="false"
        size="small"
        :bordered="false"
        :single-line="true"
        :row-key="(row) => row.config_id"
    />

    <EnvConfigModal
        v-model:show="modalShow"
        :mode="modalMode"
        :config-type="modalType"
        :env-row="envRow"
        :config-row="modalRow"
        @saved="reload"
    />
  </div>
</template>

<script setup>
import { computed, h, onMounted, ref, resolveDirective, watch, withDirectives } from 'vue'
import { NButton, NDataTable, NPopconfirm, NSpace } from 'naive-ui'
import api from '@/api'
import { apiPermissionKey, renderIcon } from '@/utils'
import { useUserStore } from '@/store'
import { buildConfigDisplayColumns } from './envConfigColumns'
import EnvConfigModal from './EnvConfigModal.vue'
import { CREATE_CONFIG_PERM, ENV_TYPE, UPDATE_CONFIG_PERM } from './envType'

defineOptions({ name: '环境配置展开子表' })

const props = defineProps({
  /** 主表绑定行：{ id, project_id, env_name, env_type, ... } */
  envRow: { type: Object, required: true },
  /** 主表侧配置保存后递增，用于已展开子表即时刷新 */
  refreshKey: { type: Number, default: 0 },
})

const vPermission = resolveDirective('permission')
const userStore = useUserStore()
const envType = props.envRow.env_type || ENV_TYPE.API

const EDIT_PERM = UPDATE_CONFIG_PERM
const CREATE_PERM = CREATE_CONFIG_PERM

const rows = ref([])
const loading = ref(false)
/** 防止 Popconfirm / 展开区重复挂载导致同一次删除打两次接口 */
const deletingIds = new Set()

const modalShow = ref(false)
const modalMode = ref('create')
const modalType = ref(envType)
const modalRow = ref(null)

function currentMaintainer() {
  return userStore.username || 'ADMIN'
}

function openEdit(type, row) {
  modalMode.value = 'edit'
  modalType.value = type
  modalRow.value = row
  modalShow.value = true
}

function openCopy(type, row) {
  modalMode.value = 'copy'
  modalType.value = type
  modalRow.value = row
  modalShow.value = true
}

async function deleteConfig(type, row) {
  const configId = row?.config_id
  if (configId == null || deletingIds.has(configId)) {
    return false
  }
  deletingIds.add(configId)
  try {
    await api.deleteEnvConfig({
      config_id: configId,
      config_type: type,
      updated_user: currentMaintainer(),
    })
    window.$message?.success?.('删除成功')
    rows.value = rows.value.filter((item) => item.config_id !== configId)
  } catch (_) {
    // 错误提示已由请求拦截器统一弹出
  } finally {
    deletingIds.delete(configId)
  }
}

async function testConfig(row) {
  try {
    const res = await api.testDbConnection({
      config_id: row.config_id,
      project_id: Number(props.envRow.project_id),
      env_name: props.envRow.env_name,
      config_name: row.config_name,
      database_name: row.database_name,
    })
    window.$message?.success?.(res?.message || '连接成功')
  } catch (e) {
    // 失败提示由请求拦截器统一处理；此处仅兜底无message场景
    if (!e?.message) window.$message?.error?.('连接失败')
  }
}

function buildActionColumn(type) {
  return {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: type === ENV_TYPE.DB ? 140 : 120,
    fixed: 'right',
    render(row) {
      const btns = [
        withDirectives(
            h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'info',
                  title: '编辑',
                  onClick: () => openEdit(type, row),
                },
                { icon: renderIcon('material-symbols:edit-outline', { size: 16 }) }
            ),
            [[vPermission, apiPermissionKey('post', EDIT_PERM[type])]]
        ),
        withDirectives(
            h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'primary',
                  title: '复制',
                  onClick: () => openCopy(type, row),
                },
                { icon: renderIcon('material-symbols:content-copy-outline', { size: 16 }) }
            ),
            [[vPermission, apiPermissionKey('post', CREATE_PERM[type])]]
        ),
        h(
            NPopconfirm,
            { onPositiveClick: () => deleteConfig(type, row) },
            {
              trigger: () =>
                  withDirectives(
                      h(
                          NButton,
                          {
                            size: 'tiny',
                            quaternary: true,
                            type: 'error',
                            title: '删除',
                            disabled: deletingIds.has(row.config_id),
                          },
                          { icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }
                      ),
                      [[vPermission, apiPermissionKey('post', '/autotest/config/delete')]]
                  ),
              default: () => h('div', {}, '确定删除该配置吗?'),
            }
        ),
      ]
      if (type === ENV_TYPE.DB) {
        btns.push(
            h(
                NButton,
                {
                  size: 'tiny',
                  quaternary: true,
                  type: 'warning',
                  title: '测试',
                  onClick: () => testConfig(row),
                },
                { icon: renderIcon('material-symbols:network-check', { size: 16 }) }
            )
        )
      }
      return h(NSpace, { size: 2, justify: 'center' }, { default: () => btns })
    },
  }
}

const columns = computed(() => [...buildConfigDisplayColumns(envType), buildActionColumn(envType)])

async function loadTypeRows(type) {
  const res = await api.getEnvConfigList({
    project_id: Number(props.envRow.project_id),
    env_name: props.envRow.env_name,
    config_type: type,
    page: 1,
    page_size: 50,
  })
  return res?.data || []
}

async function reload() {
  loading.value = true
  try {
    rows.value = await loadTypeRows(envType)
  } catch (_) {
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(reload)

watch(
    () => props.refreshKey,
    (val, oldVal) => {
      if (val !== oldVal) reload()
    }
)

defineExpose({ reload })
</script>

<style scoped>
.env-config-expand {
  padding: 8px 12px 8px 44px;
}
</style>
