<!--
  ScriptSelectDrawer — 脚本选择抽屉（纯 UI 壳）

  业务逻辑在父组件 index.vue：
  - 引用模式（quote_public_script / quote_public_api）：表格列 onSelect → onSelectPublicScript（单选插入对应类型引用步骤）
  - copy 模式：多选 selectedForCopy，底部「确定复制」→ confirmCopySteps

  父组件传入 columns、getData（getScriptListForDrawer），本组件只负责展示与查询。
-->
<template>
  <n-drawer
      v-model:show="showModel"
      :width="'61%'"
      placement="right"
      :trap-focus="false"
      block-scroll
  >
    <n-drawer-content :title="drawerTitle" closable>
      <CrudTable
          ref="tableRef"
          v-model:query-items="queryItemsModel"
          :is-pagination="true"
          :columns="columns"
          :get-data="getData"
          :row-key="'case_id'"
      >
        <template #queryBar>
          <QueryBarItem v-if="scriptDrawerMode === 'copy'" label="用例类型：" :label-width="90">
            <n-select
                v-model:value="queryItemsModel.case_type"
                :options="caseTypeOptionsForCopy"
                placeholder="全部"
                clearable
                style="min-width: 120px;"
                @update:value="tableRef?.handleSearch?.()"
            />
          </QueryBarItem>
          <QueryBarItem label="用例名称：" :label-width="90">
            <n-input
                v-model:value="queryItemsModel.case_name"
                clearable
                placeholder="请输入用例名称"
                class="query-input"
                @keypress.enter="tableRef?.handleSearch?.()"
            />
          </QueryBarItem>
          <QueryBarItem label="创建人员：" :label-width="90">
            <n-input
                v-model:value="queryItemsModel.created_user"
                clearable
                placeholder="请输入创建人员"
                class="query-input"
                @keypress.enter="tableRef?.handleSearch?.()"
            />
          </QueryBarItem>
        </template>
      </CrudTable>
      <div v-if="scriptDrawerMode === 'copy'" class="script-drawer-footer">
        <span>已选 {{ selectedForCopy.length }} 个脚本</span>
        <n-button type="primary" :disabled="selectedForCopy.length === 0" @click="emit('confirm-copy')">
          确定复制
        </n-button>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
/**
 * Props（均由 index.vue 传入）：
 * - scriptDrawerMode: 'quote_public_script' | 'quote_public_api' | 'copy'
 * - columns: 表格列（含行点击选脚本逻辑）
 * - getData: 拉取用例列表，一般为 getScriptListForDrawer
 * - caseTypeOptionsForCopy / selectedForCopy: 仅 copy 模式使用
 *
 * v-model:show / v-model:queryItems — 与父双向绑定
 *
 * defineExpose.handleSearch — 抽屉打开时父组件 nextTick 后刷新表格
 */
import { computed, ref } from 'vue'
import { NButton, NDrawer, NDrawerContent, NInput, NSelect } from 'naive-ui'
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'

const props = defineProps({
  scriptDrawerMode: { type: String, default: 'quote_public_script' },
  columns: { type: Array, required: true },
  getData: { type: Function, required: true },
  caseTypeOptionsForCopy: { type: Array, default: () => [] },
  selectedForCopy: { type: Array, default: () => [] },
})

const emit = defineEmits(['confirm-copy'])

/** 抽屉标题：按引用类型区分公共脚本/公共接口 */
const drawerTitle = computed(() => {
  if (props.scriptDrawerMode === 'copy') return '选择复制脚本'
  if (props.scriptDrawerMode === 'quote_public_api') return '选择公共接口'
  return '选择公共脚本'
})

const showModel = defineModel('show', { type: Boolean, default: false })
const queryItemsModel = defineModel('queryItems', { type: Object, required: true })

const tableRef = ref(null)

defineExpose({
  handleSearch: () => tableRef.value?.handleSearch?.(),
})
</script>

<style scoped>
.query-input {
  width: 200px;
}

.script-drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  margin-top: 12px;
  border-top: 1px solid var(--n-border-color);
}

:deep(.case-tags-cell-trigger) {
  max-width: 100%;
}

:deep(.case-tags-more) {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-2);
}

:deep(.case-tags-tooltip-inner) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 320px;
  justify-content: flex-start;
}
</style>
