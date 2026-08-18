<template>
  <div class="exec-config-panel-root">
    <!-- 任务向导：扁平工具栏（无「应用环境配置」折叠，数据源为是否开启单选） -->
    <div v-if="panel.taskWizardLayout" class="exec-config-task-toolbar">
      <div class="exec-config-task-toolbar-row">
        <div class="exec-config-datasource-radio">
          <span class="exec-config-datasource-radio-label">是否启用数据源：</span>
          <n-switch
              v-model:value="panel.debugExecDataSourceEnabled"
              size="small"
              class="exec-config-datasource-switch"
          >
            <template #checked>已开启</template>
            <template #unchecked>未开启</template>
          </n-switch>
          <span v-if="panel.debugExecDataSourceEnabled && panel.debugExecDatasetLoading" class="exec-config-datasource-tip">
            正在查询数据源…
          </span>
          <span
              v-else-if="panel.debugExecDataSourceEnabled && panel.debugExecDatasetSelectedCount > 0"
              class="exec-config-datasource-tip"
          >
            已自动纳入 {{ panel.debugExecDatasetSelectedCount }} 个数据源
          </span>
          <span
              v-else-if="panel.debugExecDataSourceEnabled && !panel.debugExecDatasetLoading"
              class="exec-config-datasource-tip is-warn"
          >
            未查询到可用数据源
          </span>
        </div>
        <span class="exec-config-global-env-label">全局环境：</span>
        <n-select
            v-model:value="panel.debugGlobalEnvId"
            :options="panel.debugEnvOptions"
            :loading="panel.envLoading"
            placeholder="全局环境"
            size="small"
            clearable
            filterable
            class="exec-config-global-env-select"
        />
        <div class="exec-config-mode">
          <n-button
              tertiary
              size="small"
              :type="panel.debugEnvMode === 'single' ? 'primary' : 'default'"
              @click="panel.debugEnvMode = 'single'"
          >
            单环境
          </n-button>
          <n-button
              tertiary
              size="small"
              :type="panel.debugEnvMode === 'multi' ? 'primary' : 'default'"
              @click="panel.debugEnvMode = 'multi'"
          >
            多环境
          </n-button>
        </div>
      </div>
    </div>

    <n-collapse
        v-model:expanded-names="panel.execConfigCollapseExpanded"
        class="exec-config-collapse"
        :class="{ 'exec-config-collapse--flat': panel.taskWizardLayout }"
        arrow-placement="right"
    >
      <n-collapse-item title="应用环境配置" name="env" class="exec-config-env-collapse-item">
        <template v-if="!panel.taskWizardLayout" #header-extra>
          <div class="exec-config-env-header-extra" @click.stop>
            <n-switch
                v-model:value="panel.debugExecDataSourceEnabled"
                size="small"
                class="exec-config-datasource-switch"
            >
              <template #checked>请选择数据源</template>
              <template #unchecked>未启用数据源</template>
            </n-switch>
            <div class="exec-config-env-header-controls">
              <span class="exec-config-global-env-label">全局环境：</span>
              <n-select
                  v-model:value="panel.debugGlobalEnvId"
                  :options="panel.debugEnvOptions"
                  :loading="panel.envLoading"
                  placeholder="全局环境"
                  size="small"
                  clearable
                  filterable
                  class="exec-config-global-env-select"
              />
              <div class="exec-config-mode">
                <n-button
                    tertiary size="small"
                    :type="panel.debugEnvMode === 'single' ? 'primary' : 'default'"
                    @click="panel.debugEnvMode = 'single'"
                >
                  单环境
                </n-button>
                <n-button
                    tertiary size="small"
                    :type="panel.debugEnvMode === 'multi' ? 'primary' : 'default'"
                    @click="panel.debugEnvMode = 'multi'"
                >
                  多环境
                </n-button>
              </div>
            </div>
          </div>
        </template>
        <div class="exec-config-modal">
          <div class="exec-config-left">
            <div class="exec-config-app-list overlay-scroll">
              <div
                  v-for="app in panel.debugApps"
                  :key="String(app.project_id)"
                  class="exec-config-app-item"
                  :class="{ 'is-active': String(app.project_id) === String(panel.debugSelectedProjectId) }"
                  @click="panel.debugSelectedProjectId = app.project_id"
              >
                <div class="exec-config-app-name">{{ app.label }}</div>
                <div class="exec-config-app-count">{{ app.totalCount }}条配置</div>
              </div>
              <div v-if="panel.debugApps.length === 0" class="exec-config-empty">
                暂无可配置的请求步骤
              </div>
            </div>
          </div>

          <div class="exec-config-right overlay-scroll">
            <div v-if="!panel.debugSelectedProjectId" class="exec-config-empty">请选择应用</div>
            <template v-else>
              <div v-if="panel.debugApiRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  API
                  <n-tag size="small" type="info">{{ panel.debugApiRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body overlay-scroll">
                    <div v-for="(row, idx) in panel.debugApiRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="panel.debugEnvOptions"
                            size="small"
                            :disabled="!panel.debugGlobalEnvId || panel.debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.request_config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="panel.getRowAddrPreview(row, 'app')"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="panel.debugDbRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  DataBase
                  <n-tag size="small" type="warning">{{ panel.debugDbRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-db">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col config">数据库名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body overlay-scroll">
                    <div v-for="(row, idx) in panel.debugDbRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="panel.debugEnvOptions"
                            size="small"
                            :disabled="!panel.debugGlobalEnvId || panel.debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col config">
                        <n-input
                            :value="panel.getDbDatabaseDisplay(row)"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="panel.getRowAddrPreview(row, row.config_bucket || 'database')"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="panel.debugRedisRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  Redis
                  <n-tag size="small" type="error">{{ panel.debugRedisRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-db">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col config">库编号</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body overlay-scroll">
                    <div v-for="(row, idx) in panel.debugRedisRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="panel.debugEnvOptions"
                            size="small"
                            :disabled="!panel.debugGlobalEnvId || panel.debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col config">
                        <n-input
                            :value="panel.getDbDatabaseDisplay(row)"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="panel.getRowAddrPreview(row, 'redis')"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="panel.debugFileRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  File Server
                  <n-tag size="small" type="success">{{ panel.debugFileRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div class="exec-config-table-body overlay-scroll">
                    <div v-for="(row, idx) in panel.debugFileRowsForSelected" :key="row.key" class="exec-config-table-row">
                      <div class="col idx">{{ idx + 1 }}</div>
                      <div class="col env">
                        <n-select
                            v-model:value="row.env_id"
                            :options="panel.debugEnvOptions"
                            size="small"
                            :disabled="!panel.debugGlobalEnvId || panel.debugEnvMode === 'single'"
                            placeholder="请先选择全局环境"
                            clearable
                        />
                      </div>
                      <div class="col config">
                        <n-input :value="row.config_name || ''" size="small" disabled placeholder="未填写配置名" />
                      </div>
                      <div class="col addr">
                        <n-input
                            :value="panel.getRowAddrPreview(row, 'file')"
                            size="small"
                            disabled
                            :placeholder="panel.debugGlobalEnvId ? '' : '请先选择全局环境'"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </n-collapse-item>

      <n-collapse-item
          v-if="!panel.taskWizardLayout && panel.debugExecDataSourceEnabled"
          title="数据驱动配置"
          name="dataset"
      >
        <div class="exec-config-dataset-wrap">
          <div class="exec-config-dataset-table">
            <div class="exec-config-dataset-header">
              <div class="col check"></div>
              <div class="col idx">#</div>
              <div class="col name">数据驱动场景名称</div>
            </div>
            <div v-if="panel.debugExecDatasetLoading" class="exec-config-dataset-empty">
              <n-spin size="medium" description="加载数据源列表..." />
            </div>
            <div v-else-if="!panel.debugExecDatasetRows.length" class="exec-config-dataset-empty">
              <n-empty description="暂无数据, 请先上传数据源或确认用例已保存" />
            </div>
            <div v-else class="exec-config-dataset-body overlay-scroll">
              <div
                  v-for="(row, idx) in panel.debugExecDatasetRows"
                  :key="row.id"
                  class="exec-config-dataset-row"
              >
                <div class="col check">
                  <n-checkbox
                      size="small"
                      :checked="panel.debugExecDatasetSelectedIds.includes(row.id)"
                      @update:checked="(v) => panel.toggleDebugExecDatasetRow(row.id, v)"
                  />
                </div>
                <div class="col idx">{{ idx + 1 }}</div>
                <div class="col name">{{ row.name }}</div>
              </div>
            </div>
          </div>
          <div class="exec-config-dataset-footer">
            <div class="exec-config-dataset-footer-inner">
              <n-space :size="8">
                <n-button
                    size="tiny"
                    quaternary
                    :disabled="panel.debugExecDatasetBatchDisabled"
                    @click="panel.selectAllDebugExecDatasets"
                >
                  全选
                </n-button>
                <n-button
                    size="tiny"
                    quaternary
                    :disabled="panel.debugExecDatasetBatchDisabled"
                    @click="panel.clearDebugExecDatasetSelection"
                >
                  取消全选
                </n-button>
              </n-space>
              <div class="exec-config-dataset-footer-count">
                已选 {{ panel.debugExecDatasetSelectedCount }} 项
                <span v-if="panel.execConfigMode === 'debug'" class="exec-config-dataset-mode-tip">(调试模式仅可选 1 条)</span>
              </div>
            </div>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import {
  NButton,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NEmpty,
  NInput,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
} from 'naive-ui'

const panel = inject('execConfigPanel')
if (!panel) {
  throw new Error('ExecConfigPanelBody requires execConfigPanel inject')
}
</script>

<style scoped>
.exec-config-panel-root {
  width: 100%;
}

.exec-config-task-toolbar {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  background: var(--n-color);
}

.exec-config-task-toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
}

.exec-config-datasource-radio {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.exec-config-datasource-radio-label {
  font-size: 13px;
  color: var(--n-text-color-2);
  white-space: nowrap;
}

.exec-config-datasource-tip {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.exec-config-datasource-tip.is-warn {
  color: var(--n-warning-color);
}

.exec-config-collapse--flat :deep(.n-collapse-item__header) {
  display: none !important;
}

.exec-config-collapse--flat :deep(.n-collapse-item) {
  border: none !important;
  margin: 0 !important;
}

.exec-config-collapse--flat :deep(.n-collapse-item__content-inner) {
  padding-top: 0 !important;
}
</style>
