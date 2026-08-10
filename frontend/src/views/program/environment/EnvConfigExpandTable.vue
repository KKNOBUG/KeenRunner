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

defineOptions({ name: '环境配置展开子表' })

const props = defineProps({
  /** 主表绑定行：{ id, project_id, env_name, env_type, ... } */
  envRow: { type: Object, required: true },
  /** 主表侧配置保存后递增，用于已展开子表即时刷新 */
  refreshKey: { type: Number, default: 0 },
})

const vPermission = resolveDirective('permission')
const userStore = useUserStore()
const envType = Number(props.envRow.env_type)

const EDIT_PERM = {
  1: '/autotest/config/app/update',
  2: '/autotest/config/file/update',
  3: '/autotest/config/database/update',
  4: '/autotest/config/redis/update',
}
const CREATE_PERM = {
  1: '/autotest/config/app/create',
  2: '/autotest/config/file/create',
  3: '/autotest/config/database/create',
  4: '/autotest/config/redis/create',
}

const rows = ref([])
const loading = ref(false)

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
  try {
    await api.deleteEnvConfig({ id: row.id, env_type: type, updated_user: currentMaintainer() })
    window.$message?.success?.('删除成功')
    await reload()
  } catch (e) {
    window.$message?.error?.(`删除失败：${e?.message || e}`)
  }
}

async function testConfig(row) {
  try {
    const res = await api.testDbConnection({
      id: row.id,
      project_id: String(props.envRow.project_id),
      env_name: props.envRow.env_name,
      config_name: row.config_name,
      db_name: row.db_name,
    })
    if (res?.code === '000000' && res?.status === 'success') {
      window.$message?.success?.(res?.message || '连接成功')
    } else {
      window.$message?.error?.(res?.message || '连接失败')
    }
  } catch (e) {
    window.$message?.error?.(`连接失败：${e?.message || e}`)
  }
}

function buildActionColumn(type) {
  return {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: type === 3 ? 140 : 120,
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
                          { size: 'tiny', quaternary: true, type: 'error', title: '删除' },
                          { icon: renderIcon('material-symbols:delete-outline', { size: 16 }) }
                      ),
                      [[vPermission, apiPermissionKey('post', '/autotest/config/delete')]]
                  ),
              default: () => h('div', {}, '确定删除该配置吗?'),
            }
        ),
      ]
      if (type === 3) {
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
    env_info_id: Number(props.envRow.project_id),
    env_name: props.envRow.env_name,
    env_type: type,
    page: 1,
    page_size: 50,
  })
  const list = res?.data || []
  // Redis列表字段与展示列对齐（ip/port/remark/maintainer）
  if (type === 4) {
    return list.map((r) => ({
      ...r,
      id: r.id ?? r.config_id,
      ip: r.ip ?? r.config_host,
      port: r.port ?? r.config_port,
      redis_db: r.redis_db ?? r.database_name ?? r.db_name,
      redis_username: r.redis_username ?? r.config_username,
      redis_password: r.redis_password ?? r.config_password,
      remark: r.remark ?? r.config_desc,
      maintainer: r.maintainer ?? r.updated_user,
    }))
  }
  return list
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
