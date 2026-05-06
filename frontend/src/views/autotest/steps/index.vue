<template>
  <AppPage>
    <n-card size="small" class="case-info-card" title="用例信息">
      <!-- 与步骤子页一致：n-form-item + 固定 label-width，必填星号由组件统一排版 -->
      <n-form
          :model="caseForm"
          label-placement="left"
          label-width="80px"
          class="case-info-form"
      >
        <div class="case-info-fields">
          <div class="case-field">
            <n-form-item label="所属应用" path="case_project" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_project"
                  :options="projectOptions"
                  :loading="projectLoading"
                  clearable
                  filterable
                  placeholder="所属应用"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例名称" path="case_name" required :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_name"
                  size="small"
                  placeholder="请输入用例名称"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="所属标签" path="case_tags" required :show-feedback="false">
              <n-popover
                  v-model:show="tagPopoverShow"
                  trigger="click"
                  placement="bottom-start"
                  :style="{ width: '400px' }"
              >
                <template #trigger>
                  <n-input
                      :value="getSelectedTagNames()"
                      clearable
                      readonly
                      placeholder="请选择所属标签"
                      size="small"
                      class="case-field-input"
                      @clear="caseForm.case_tags = []"
                      @click="tagPopoverShow = !tagPopoverShow"
                  />
                </template>
                <template #default>
                  <div style="display: flex; height: 300px; width: 400px;">
                    <div style="width: 45%; overflow-y: auto;">
                      <n-list v-if="Object.keys(tagModeGroups).length > 0">
                        <n-list-item
                            v-for="(tags, mode) in tagModeGroups"
                            :key="mode"
                            :class="{ 'tag-mode-selected': selectedTagMode === mode, 'tag-mode-item': true }"
                            @click="selectedTagMode = mode"
                        >
                          <span class="tag-mode-text" :title="mode">{{ mode }}</span>
                        </n-list-item>
                      </n-list>
                      <div v-else style="padding: 20px; text-align: center; color: #999;">
                        {{ tagLoading ? '加载中...' : '暂无标签数据' }}
                      </div>
                    </div>
                    <div style="width: 50%; overflow-y: auto;">
                      <n-list v-if="selectedTagMode && currentTagNames.length > 0">
                        <n-list-item
                            v-for="tag in currentTagNames"
                            :key="tag.tag_id"
                            :class="{ 'tag-name-selected': isTagSelected(tag.tag_id) }"
                            class="tag-list-item"
                            @click="handleTagSelect(tag.tag_id)"
                        >
                          <span class="tag-checkbox">{{ isTagSelected(tag.tag_id) ? '✓ ' : '' }}</span>
                          <span class="tag-name-text" :title="tag.tag_name">{{ tag.tag_name }}</span>
                        </n-list-item>
                      </n-list>
                      <div v-else style="padding: 20px; text-align: center; color: #999;">
                        {{ selectedTagMode ? '该分类下暂无标签' : '请先选择左侧分类' }}
                      </div>
                    </div>
                  </div>
                </template>
              </n-popover>
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例属性" path="case_attr" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_attr"
                  :options="caseAttrOptions"
                  clearable
                  placeholder="请选择用例属性"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field">
            <n-form-item label="用例类型" path="case_type" required :show-feedback="false">
              <n-select
                  v-model:value="caseForm.case_type"
                  :options="caseTypeOptions"
                  clearable
                  placeholder="请选择用例类型"
                  size="small"
                  class="case-field-input"
              />
            </n-form-item>
          </div>

          <div class="case-field case-field-full">
            <n-form-item label="用例描述" path="case_desc" :show-feedback="false">
              <n-input
                  v-model:value="caseForm.case_desc"
                  size="small"
                  type="textarea"
                  placeholder="请输入用例描述"
              />
            </n-form-item>
          </div>

          <!-- 按钮：不占标签列，右对齐 -->
          <div class="case-field case-field-full case-field-buttons">
            <n-space justify="end">
              <n-button type="info" :loading="runLoading" @click="handleRun">执行</n-button>
              <n-button type="primary" :loading="debugLoading" @click="handleDebug">调试</n-button>
              <n-button type="success" :loading="saveLoading" @click="handleSaveAll">保存</n-button>
            </n-space>
          </div>
        </div>
      </n-form>
    </n-card>
    <div class="page-container">
      <n-grid :cols="24" :x-gap="16" class="grid-container">
        <n-gi :span="7" class="left-column">
          <n-card size="small" hoverable class="step-card">
            <template #header>
              <div class="step-header">
                <span class="step-count">{{ totalStepsCount }}个步骤</span>
                <n-button
                    text
                    size="small"
                    @click="toggleAllExpand"
                    :title="isAllExpanded ? '折叠所有步骤' : '展开所有步骤'"
                >
                  <template #icon>
                    <TheIcon
                        :icon="isAllExpanded ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"/>
                  </template>
                </n-button>
              </div>
            </template>
            <div class="step-tree-container">
              <template v-for="(step, index) in steps" :key="step.id">
                <div
                    class="step-item"
                    :class="{
                    'is-selected': selectedKeys.includes(step.id),
                    'is-drag-target': dragState.draggingId && stepDefinitions[step.type]?.allowChildren, // 所有 loop/if 步骤的普通高亮
                    'is-drag-over': dragState.dragOverId === step.id && stepDefinitions[step.type]?.allowChildren // 焦点高亮
                  }"
                    :draggable="true"
                    @dragstart="handleDragStart($event, step.id, null, index)"
                    @dragover.prevent="handleDragOver($event, step.id, null)"
                    @dragleave="handleDragLeave($event, step.id)"
                    @drop="handleDrop($event, step.id, null, index)"
                    @click="handleSelect([step.id])"
                >
                  <div class="step-item-distance">
                    <!-- 父级步骤名称-->
                    <span class="step-name" :title="step.name">
                    <TheIcon
                        :icon="getStepIcon(step.type)"
                        :size="18"
                        class="step-icon"
                        :class="getStepIconClass(step.type)"
                    />
                    <span class="step-name-text">{{ getStepDisplayName(step.name, step.id) }}</span>
                    <span class="step-actions">
                      <span class="step-number">#{{ getStepNumber(step.id) }}</span>
                      <n-button
                          v-if="stepDefinitions[step.type]?.allowChildren"
                          text
                          size="tiny"
                          @click.stop="toggleStepExpand(step.id, $event)"
                          class="action-btn"
                          :title="isStepExpanded(step.id) ? '折叠当前步骤' : '展开当前步骤'"
                      >
                        <template #icon>
                          <TheIcon
                              :icon="isStepExpanded(step.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"
                              :size="16"
                          />
                        </template>
                      </n-button>
                      <n-button
                          text
                          size="tiny"
                          @click.stop="handleCopyStep(step.id)"
                          class="action-btn"
                          title="复制当前步骤"
                      >
                        <template #icon>
                          <TheIcon icon="material-symbols:content-copy" :size="16"/>
                        </template>
                      </n-button>
                      <n-popconfirm @positive-click="handleDeleteStep(step.id)" @click.stop>
                        <template #trigger>
                          <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                            <template #icon>
                              <TheIcon icon="material-symbols:delete" :size="16"/>
                            </template>
                          </n-button>
                        </template>
                        确认删除该步骤?
                      </n-popconfirm>
                    </span>
                  </span>
                    <div v-if="stepDefinitions[step.type]?.allowChildren">
                      <div
                          v-show="isStepExpanded(step.id)"
                          @dragover.prevent="handleDragOverInChildrenArea($event, step.id)"
                          @dragleave="handleDragLeaveInChildrenArea($event, step.id)"
                      >
                        <!-- 无子女时显示空的拖拽区域 -->
                        <div
                            v-if="!step.children || step.children.length === 0"
                            class="step-drop-zone"
                            :class="{ 'is-drag-over': dragState.dragOverId === step.id }"
                            @drop="handleDrop($event, step.id, step.id, 0)"
                        >
                          <div class="step-drop-zone-hint">拖拽步骤到这里</div>
                        </div>
                        <template v-for="(child, childIndex) in (step.children || [])" :key="child.id">
                          <!-- 插入位置指示器：在子步骤之前 -->
                          <div
                              v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === child.id && dragState.insertPosition === 'before'"
                              class="step-insert-indicator"
                          ></div>
                          <div
                              class="step-item"
                              :class="{ 'is-selected': selectedKeys.includes(child.id) }"
                              :draggable="true"
                              @dragstart.stop="handleDragStart($event, child.id, step.id, childIndex)"
                              @dragover.prevent.stop="handleDragOverOnChild($event, child.id, step.id, childIndex)"
                              @dragleave.stop="handleDragLeaveOnChild($event, child.id)"
                              @drop.stop="handleDrop($event, child.id, step.id, childIndex)"
                              @click.stop="handleSelect([child.id])"
                          >
                            <div class="step-item-child">
                            <span class="step-name" :title="child.name">
                              <TheIcon
                                  :icon="getStepIcon(child.type)"
                                  :size="18"
                                  class="step-icon"
                                  :class="getStepIconClass(child.type)"
                              />
                              <!-- 子级步骤名称 -->
                              <span class="step-name-text">{{ getStepDisplayName(child.name, child.id) }}</span>
                              <span class="step-actions">
                                <span class="step-number">#{{ getStepNumber(child.id) }}</span>
                                <n-button
                                    v-if="stepDefinitions[child.type]?.allowChildren"
                                    text
                                    size="tiny"
                                    @click.stop="toggleStepExpand(child.id, $event)"
                                    class="action-btn"
                                    :title="!isStepExpanded(step.id) ? '折叠当前步骤' : '展开当前步骤'"
                                >
                                  <template #icon>
                                    <TheIcon
                                        :icon="isStepExpanded(child.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down'"
                                        :size="16"
                                    />
                                  </template>
                                </n-button>
                                <n-button text size="tiny" @click.stop="handleCopyStep(child.id)" class="action-btn"
                                          title="复制当前步骤">
                                  <template #icon>
                                    <TheIcon icon="material-symbols:content-copy" :size="16"/>
                                  </template>
                                </n-button>
                                <n-popconfirm @positive-click="handleDeleteStep(child.id)" @click.stop>
                                  <template #trigger>
                                    <n-button text size="tiny" type="error" class="action-btn" title="删除当前步骤">
                                      <template #icon>
                                        <TheIcon icon="material-symbols:delete" :size="14"/>
                                      </template>
                                    </n-button>
                                  </template>
                                  确认删除该步骤?
                                </n-popconfirm>
                              </span>
                            </span>
                              <!-- 使用递归组件渲染子步骤 -->
                              <RecursiveStepChildren
                                  v-if="stepDefinitions[child.type]?.allowChildren"
                                  :step="child"
                                  :parent-id="step.id"
                              />
                            </div>
                          </div>
                          <!-- 插入位置指示器：在子步骤之后 -->
                          <div
                              v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === child.id && dragState.insertPosition === 'after'"
                              class="step-insert-indicator"
                          ></div>
                        </template>
                        <!-- 插入位置指示器：在最后一个子步骤之后（无子女时显示在空拖拽区域） -->
                        <div
                            v-if="dragState.draggingId && dragState.dragOverId === step.id && dragState.insertTargetId === null && dragState.insertPosition === 'after' && step.children && step.children.length > 0"
                            class="step-insert-indicator"
                        ></div>
                        <div class="step-add-btn">
                          <n-dropdown
                              trigger="click"
                              :options="addOptions"
                              :render-label="renderDropdownLabel"
                              @select="(key) => handleAddStep(key, step.id)"
                          >
                            <n-button dashed size="small" class="add-step-btn" @click.stop>添加步骤</n-button>
                          </n-dropdown>
                        </div>
                      </div>
                    </div>
                    <!-- 引用步骤：展示公共脚本内的步骤（只读、递归子级，不参与保存） -->
                    <div v-if="step.type === 'quote'" class="quote-inner-steps">
                      <div class="quote-inner-list">
                        <div
                            v-for="(item, idx) in getQuoteStepsFlattened(quoteStepsMap[step.id] || [])"
                            :key="'quote-' + step.id + '-' + idx + '-' + (item.step.id || '')"
                            class="step-item quote-inner-item"
                            :class="{ 'is-selected': selectedKeys.includes(getQuoteInnerKey(step.id, idx)) }"
                            :style="{ marginLeft: (item.depth * 14) + 'px' }"
                            @click.stop="handleSelect([getQuoteInnerKey(step.id, idx)])"
                        >
                          <span class="step-name">
                            <TheIcon
                                :icon="getStepIcon(item.step.type)"
                                :size="16"
                                class="step-icon"
                                :class="getStepIconClass(item.step.type)"
                            />
                            <span class="step-name-text">{{ item.step.name || '步骤' }}</span>
                            <span class="step-number">#{{ idx + 1 }}</span>
                          </span>
                        </div>
                        <div v-if="!getQuoteStepsFlattened(quoteStepsMap[step.id] || []).length" class="quote-inner-empty">暂无步骤</div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
              <n-dropdown
                  trigger="click"
                  :options="addOptions"
                  :render-label="renderDropdownLabel"
                  @select="(key) => handleAddStep(key, null)"
              >
                <n-button dashed size="small" class="add-step-btn">添加步骤</n-button>
              </n-dropdown>
            </div>
          </n-card>
        </n-gi>
        <n-gi :span="17" class="right-column">
          <n-card size="small" hoverable class="config-card">
            <component
                v-if="currentStep"
                :key="currentStep.id + (currentStep.isQuoteInner ? '-readonly' : '')"
                :is="editorComponent"
                :config="currentStep.config"
                :step="currentStep"
                :project-options="(currentStep?.type === 'http' || currentStep?.type === 'tcp' || currentStep?.type === 'database' || currentStep?.type === 'quote') ? projectOptions : []"
                :project-loading="(currentStep?.type === 'http' || currentStep?.type === 'tcp' || currentStep?.type === 'database' || currentStep?.type === 'quote') ? projectLoading : false"
                :available-variable-list="availableVariableList"
                :assist-functions="assistFunctionsList"
                :on-reselect="currentStep?.isQuoteInner ? undefined : handleQuoteReselect"
                :readonly="!!currentStep?.isQuoteInner"
                @update:config="(val) => { if (!currentStep?.isQuoteInner) updateStepConfig(currentStep.id, val) }"
            />
            <n-empty v-else description="请选择左侧步骤或添加新步骤"/>
          </n-card>
        </n-gi>
      </n-grid>
    </div>

    <!-- 引用公共脚本 / 复制指定脚本 共用抽屉 -->
    <n-drawer
        v-model:show="quotePublicScriptDrawerVisible"
        :width="'61%'"
        placement="right"
        :trap-focus="false"
        block-scroll
    >
      <n-drawer-content :title="scriptDrawerMode === 'copy' ? '选择复制脚本' : '选择公共脚本'" closable>
        <CrudTable
            ref="quotePublicScriptTableRef"
            v-model:query-items="quotePublicScriptQueryItems"
            :is-pagination="true"
            :columns="quotePublicScriptColumns"
            :get-data="getScriptListForDrawer"
            :row-key="'case_id'"
        >
          <template #queryBar>
            <QueryBarItem v-if="scriptDrawerMode === 'copy'" label="用例类型：" :label-width="90">
              <n-select
                  v-model:value="quotePublicScriptQueryItems.case_type"
                  :options="caseTypeOptionsForCopy"
                  placeholder="全部"
                  clearable
                  style="min-width: 120px;"
                  @update:value="quotePublicScriptTableRef?.handleSearch?.()"
              />
            </QueryBarItem>
            <QueryBarItem label="用例名称：" :label-width="90">
              <n-input
                  v-model:value="quotePublicScriptQueryItems.case_name"
                  clearable
                  placeholder="请输入用例名称"
                  class="query-input"
                  @keypress.enter="quotePublicScriptTableRef?.handleSearch?.()"
              />
            </QueryBarItem>
            <QueryBarItem label="创建人员：" :label-width="90">
              <n-input
                  v-model:value="quotePublicScriptQueryItems.created_user"
                  clearable
                  placeholder="请输入创建人员"
                  class="query-input"
                  @keypress.enter="quotePublicScriptTableRef?.handleSearch?.()"
              />
            </QueryBarItem>
          </template>
        </CrudTable>
        <div v-if="scriptDrawerMode === 'copy'" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; margin-top: 12px; border-top: 1px solid var(--n-border-color);">
          <span>已选 {{ selectedForCopy.length }} 个脚本</span>
          <n-button type="primary" :disabled="selectedForCopy.length === 0" @click="confirmCopySteps">
            确定复制
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- 调试 / 执行：脚本执行配置 -->
    <n-modal
        v-model:show="debugConfigModalVisible"
        preset="card"
        title="脚本执行配置"
        :style="{ width: '70%' }"
        :bordered="false"
        :segmented="{ content: true, footer: true }"
        @after-enter="onDebugModalAfterEnter"
    >
      <div class="exec-config-toolbar-row">
        <div class="exec-config-toolbar-inner">
          <n-space align="center" wrap :size="[8, 12]">
            <span class="exec-config-global-env-label">全局环境：</span>
            <n-select
                v-model:value="debugGlobalEnvId"
                :options="debugEnvOptions"
                :loading="envLoading"
                placeholder="全局环境"
                clearable
                filterable
                style="width: 220px;"
            />
            <div class="exec-config-mode">
              <n-button
                  size="small"
                  :type="debugEnvMode === 'single' ? 'primary' : 'default'"
                  @click="debugEnvMode = 'single'"
              >
                单环境
              </n-button>
              <n-button
                  size="small"
                  :type="debugEnvMode === 'multi' ? 'primary' : 'default'"
                  @click="debugEnvMode = 'multi'"
              >
                多环境
              </n-button>
            </div>
          </n-space>
          <n-switch
              v-model:value="debugExecDataSourceEnabled"
              size="large"
              :rail-style="debugExecDataSourceRailStyle"
          >
            <template #checked>
              请选择数据源
            </template>
            <template #unchecked>
              未启用数据源
            </template>
          </n-switch>
        </div>
      </div>

      <n-card size="small" title="应用与环境配置" :segmented="{ content: true }" class="exec-config-main-card">
        <template #header-extra>
          <n-button quaternary size="small" @click="execConfigMainCardExpanded = !execConfigMainCardExpanded">
            {{ execConfigMainCardExpanded ? '折叠' : '展开' }}
          </n-button>
        </template>
        <div v-show="execConfigMainCardExpanded" class="exec-config-modal">
          <div class="exec-config-left">
            <div class="exec-config-left-head">
              共 {{ debugApps.length }} 个应用
            </div>
            <div class="exec-config-app-list">
              <div
                  v-for="app in debugApps"
                  :key="String(app.project_id)"
                  class="exec-config-app-item"
                  :class="{ 'is-active': String(app.project_id) === String(debugSelectedProjectId) }"
                  @click="debugSelectedProjectId = app.project_id"
              >
                <div class="exec-config-app-name">{{ app.label }}</div>
                <div class="exec-config-app-count">{{ app.totalCount }}条配置</div>
              </div>
              <div v-if="debugApps.length === 0" class="exec-config-empty">
                暂无可配置的请求步骤（HTTP/TCP/数据库）
              </div>
            </div>
          </div>

          <div class="exec-config-right">
            <div v-if="!debugSelectedProjectId" class="exec-config-empty">
              请先在左侧选择一个应用
            </div>

            <template v-else>
              <div v-if="debugApiRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  API
                  <n-tag size="small" type="info">{{ debugApiRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-api">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div v-for="(row, idx) in debugApiRowsForSelected" :key="row.key" class="exec-config-table-row">
                    <div class="col idx">{{ idx + 1 }}</div>
                    <div class="col env">
                      <n-select
                          v-model:value="row.env_id"
                          :options="debugEnvOptions"
                          size="small"
                          :disabled="debugEnvMode === 'single'"
                          placeholder="请选择"
                          clearable
                      />
                    </div>
                    <div class="col config">
                      <n-select
                          v-model:value="row.request_config_name"
                          size="small"
                          filterable
                          tag
                          clearable
                          placeholder="选择或输入配置名"
                          :disabled="!debugGlobalEnvId"
                          :options="getApiConfigOptions(row)"
                      />
                    </div>
                    <div class="col addr">
                      <n-input
                          :value="getRowAddrPreview(row, 'api')"
                          size="small"
                          disabled
                          placeholder="请先选择全局环境和配置"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="debugDbRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  DB
                  <n-tag size="small" type="warning">{{ debugDbRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-db">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col config">数据库名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div v-for="(row, idx) in debugDbRowsForSelected" :key="row.key" class="exec-config-table-row">
                    <div class="col idx">{{ idx + 1 }}</div>
                    <div class="col env">
                      <n-select
                          v-model:value="row.env_id"
                          :options="debugEnvOptions"
                          size="small"
                          :disabled="debugEnvMode === 'single'"
                          placeholder="请选择"
                          clearable
                      />
                    </div>
                    <div class="col config">
                      <n-select
                          v-model:value="row.config_name"
                          size="small"
                          filterable
                          tag
                          clearable
                          placeholder="配置名"
                          :disabled="!debugGlobalEnvId"
                          :options="getDbConfigOptions(row)"
                      />
                    </div>
                    <div class="col config">
                      <n-select
                          v-model:value="row.database_name"
                          size="small"
                          filterable
                          tag
                          clearable
                          placeholder="库名"
                          :disabled="!debugGlobalEnvId"
                          :options="getDbNameOptions(row)"
                      />
                    </div>
                    <div class="col addr">
                      <n-input
                          :value="getRowAddrPreview(row, 'database')"
                          size="small"
                          disabled
                          placeholder="请先选择全局环境和配置"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="debugFileRowsForSelected.length" class="exec-config-section">
                <div class="exec-config-section-title">
                  FILE
                  <n-tag size="small" type="success">{{ debugFileRowsForSelected.length }}条</n-tag>
                </div>
                <div class="exec-config-table is-file">
                  <div class="exec-config-table-header">
                    <div class="col idx">#</div>
                    <div class="col env">环境</div>
                    <div class="col config">配置名</div>
                    <div class="col addr">IP/端口</div>
                  </div>
                  <div v-for="(row, idx) in debugFileRowsForSelected" :key="row.key" class="exec-config-table-row">
                    <div class="col idx">{{ idx + 1 }}</div>
                    <div class="col env">
                      <n-select
                          v-model:value="row.env_id"
                          :options="debugEnvOptions"
                          size="small"
                          :disabled="debugEnvMode === 'single'"
                          placeholder="请选择"
                          clearable
                      />
                    </div>
                    <div class="col config">
                      <n-select
                          v-model:value="row.config_name"
                          size="small"
                          filterable
                          tag
                          clearable
                          placeholder="选择或输入配置名"
                          :disabled="!debugGlobalEnvId"
                          :options="getFileConfigOptions(row)"
                      />
                    </div>
                    <div class="col addr">
                      <n-input
                          :value="getRowAddrPreview(row, 'file')"
                          size="small"
                          disabled
                          placeholder="请先选择全局环境和配置"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </n-card>

      <n-card
          v-if="debugExecDataSourceEnabled"
          size="small"
          title="数据源配置"
          :segmented="{ content: true }"
          class="exec-config-dataset-card"
      >
        <template #header-extra>
          <n-button quaternary size="small" @click="execDatasetCardExpanded = !execDatasetCardExpanded">
            {{ execDatasetCardExpanded ? '折叠' : '展开' }}
          </n-button>
        </template>
        <div v-show="execDatasetCardExpanded" class="exec-config-dataset-wrap">
          <div class="exec-config-dataset-table">
            <div class="exec-config-dataset-header">
              <div class="col idx">序号</div>
              <div class="col name">数据集名称</div>
            </div>
            <div v-if="!debugExecDatasetRows.length" class="exec-config-dataset-empty">
              <n-empty description="暂无数据" />
            </div>
            <div v-else class="exec-config-dataset-body">
              <div
                  v-for="(row, idx) in debugExecDatasetRows"
                  :key="row.id"
                  class="exec-config-dataset-row"
              >
                <div class="col idx">{{ idx + 1 }}</div>
                <div class="col name">{{ row.name }}</div>
              </div>
            </div>
          </div>
          <div class="exec-config-dataset-footer">
            已选 {{ debugExecDatasetSelectedCount }} 项
          </div>
        </div>
      </n-card>

      <template #footer>
        <n-space justify="end" size="medium">
          <n-button @click="debugConfigModalVisible = false">取消</n-button>
          <n-button
              type="primary"
              :loading="execConfigMode === 'run' ? runLoading : debugLoading"
              @click="confirmExecConfigAndAction"
          >
            {{ execConfigMode === 'run' ? '确定并执行' : '确定并调试' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </AppPage>
</template>

<script setup>
defineOptions({ name: '步骤编辑' })
import {computed, defineComponent, h, nextTick, onMounted, onUpdated, reactive, ref, watch} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {
  NButton,
  NCard,
  NDrawer,
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NGi,
  NGrid,
  NInput,
  NList,
  NListItem,
  NModal,
  NPopconfirm,
  NPopover,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
  useMessage
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {formatDateTime, renderIcon} from '@/utils'
import AppPage from "@/components/page/AppPage.vue";
import ApiLoopEditor from "@/views/autotest/loop_controller/index.vue";
import ApiCodeEditor from "@/views/autotest/run_code_controller/index.vue";
import ApiHttpEditor from "@/views/autotest/http_controller/index.vue";
import ApiTcpEditor from "@/views/autotest/tcp_controller/index.vue";
import ApiDatabaseEditor from "@/views/autotest/database_controller/index.vue";
import ApiIfEditor from "@/views/autotest/condition_controller/index.vue";
import ApiWaitEditor from "@/views/autotest/wait_controller/index.vue";
import ApiUserVariablesEditor from "@/views/autotest/user_variables_controller/index.vue";
import ApiQuoteEditor from "@/views/autotest/quote_controller/index.vue";
import CrudTable from '@/components/table/CrudTable.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import api from "@/api";
import {useUserStore, useAutotestStore} from '@/store';

const message = useMessage()
const notifyError = (msg) => {
  if (typeof window !== 'undefined' && typeof window.$message?.error === 'function') {
    window.$message.error(msg)
  } else {
    message.error(msg)
  }
}

// 顺序与 backend/enums/autotest_enum.py AutoTestStepType 一致
const stepDefinitions = {
  user_variables: {label: '用户变量', allowChildren: false, icon: 'gravity-ui:magic-wand'},
  if: {label: '条件分支', allowChildren: true, icon: 'tabler:arrow-loop-right-2'},
  wait: {label: '等待控制', allowChildren: false, icon: 'meteor-icons:alarm-clock'},
  loop: {label: '循环结构', allowChildren: true, icon: 'streamline:arrow-reload-horizontal-2'},
  tcp: {label: 'TCP请求', allowChildren: false, icon: 'carbon:content-delivery-network'},
  http: {label: 'HTTP请求', allowChildren: false, icon: 'streamline-freehand:worldwide-web-network-www'},
  code: {label: '代码请求(Python)', allowChildren: false, icon: 'teenyicons:python-outline'},
  database: {label: '数据库请求', allowChildren: false, icon: 'material-symbols:database-search-outline'},
  quote: {label: '引用公共脚本', allowChildren: false, icon: 'material-symbols:link'},
}

const editorMap = {
  loop: ApiLoopEditor,
  code: ApiCodeEditor,
  tcp: ApiTcpEditor,
  http: ApiHttpEditor,
  database: ApiDatabaseEditor,
  if: ApiIfEditor,
  wait: ApiWaitEditor,
  user_variables: ApiUserVariablesEditor,
  quote: ApiQuoteEditor,
}

let seed = 1000
const genId = () => `step-${seed++}`

const steps = ref([])
const selectedKeys = ref([])
const route = useRoute()
const router = useRouter()
const autotestStore = useAutotestStore()
const caseId = computed(() => route.query.case_id || null)
const caseCode = computed(() => route.query.case_code || null)

// 从路由参数中解析用例信息并填充表单
const initCaseInfoFromRoute = () => {
  if (route.query.case_info) {
    try {
      const caseInfo = JSON.parse(route.query.case_info)
      // 填充表单数据
      // case_project 是对象，提取 project_id
      if (caseInfo.case_project) {
        caseForm.case_project = typeof caseInfo.case_project === 'object'
            ? caseInfo.case_project.project_id
            : caseInfo.case_project
      }
      caseForm.case_name = caseInfo.case_name || ''
      // case_tags 是对象数组，提取 tag_id 数组
      if (Array.isArray(caseInfo.case_tags) && caseInfo.case_tags.length > 0) {
        caseForm.case_tags = caseInfo.case_tags.map(tag => {
          return typeof tag === 'object' ? tag.tag_id : tag
        }).filter(id => id !== undefined && id !== null)
      } else {
        caseForm.case_tags = []
      }
      caseForm.case_desc = caseInfo.case_desc || ''
      caseForm.case_attr = caseInfo.case_attr || ''
      caseForm.case_type = caseInfo.case_type || ''
    } catch (error) {
      console.error('解析用例信息失败:', error)
    }
  }
}

/**
 * 【用例管理「复制」】从复制数据（case_info 含 is_copy 和 steps）加载步骤树
 *
 * 数据来源：用例管理页 handleCopyCase 调用 copyCaseStepTree 后，将 { case, steps, is_copy } 通过
 * router 的 case_info query 传入。本函数在 loadSteps 中检测到 case_info.is_copy 且 steps 非空时调用。
 *
 * 与「复制指定脚本」的区别：
 *   - 本函数：加载「整用例复制」的步骤树（case_info 来自路由）
 *   - 复制指定脚本：仅将 steps 插入当前用例的步骤树，不涉及 case_info
 */
const loadStepsFromCopy = (caseInfo) => {
  if (!caseInfo?.is_copy || !Array.isArray(caseInfo?.steps) || caseInfo.steps.length === 0) return false
  hydrateCaseInfo(caseInfo.steps)
  steps.value = caseInfo.steps.map(mapBackendStep).filter(Boolean)
  selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  loadQuoteStepsForAllQuoteSteps()
  return true
}

const caseForm = reactive({
  case_project: '',
  case_name: '',
  case_tags: [],
  case_desc: '',
  case_attr: '',
  case_type: ''
})

// 项目列表（复用用例管理页面的数据源）
const projectOptions = ref([])
const projectLoading = ref(false)

// 标签相关（复用用例管理页面的数据源）
const tagOptions = ref([])
const tagLoading = ref(false)
const selectedTagMode = ref(null)
const tagPopoverShow = ref(false)

// 用例属性选项（复用用例管理页面的数据源）
const caseAttrOptions = [
  {label: '正用例', value: '正用例'},
  {label: '反用例', value: '反用例'}
]

// 用例类型选项
const caseTypeOptions = [
  {label: '用户脚本', value: '用户脚本'},
  {label: '公共脚本', value: '公共脚本'}
]

// 引用公共脚本 / 复制指定脚本 共用抽屉（mode: 'quote' | 'copy'）
// quote: 引用公共脚本（单选，插入 quote 步骤）；copy: 复制指定脚本（多选，调用 copyCaseStepTree 获取 steps 并插入）
const scriptDrawerMode = ref('quote')
const quotePublicScriptDrawerVisible = ref(false)
const quotePublicScriptParentId = ref(null)
const quotePublicScriptReplaceStepId = ref(null)
const quotePublicScriptTableRef = ref(null)
// 引用步骤内展示的公共脚本步骤（仅展示，不参与保存）：quoteStepId -> 前端树节点数组
const quoteStepsMap = ref({})
// 从「用户脚本」切到「公共脚本」时暂存的引用步骤，切回「用户脚本」时可恢复
const stashedQuoteStepsWhenPublic = ref([])
// 复制模式：已选待复制的用例列表
const selectedForCopy = ref([])
const quotePublicScriptQueryItems = ref({
  case_name: '',
  case_type: '公共脚本',
  created_user: ''
})

// 复制模式用例类型选项（支持全部、公共脚本、用户脚本）
const caseTypeOptionsForCopy = [
  { label: '全部', value: '' },
  { label: '公共脚本', value: '公共脚本' },
  { label: '用户脚本', value: '用户脚本' }
]

// 请求前规范化入参：quote 模式仅查公共脚本；copy 模式支持 case_type（全部/公共/用户），并排除当前用例（不可复制自己）
const getScriptListForDrawer = (params) => {
  const body = {...params}
  if (scriptDrawerMode.value === 'quote') {
    body.case_type = '公共脚本'
  }
  if (scriptDrawerMode.value === 'copy' && caseId.value) {
    body.exclude_case_id = Number(caseId.value)
  }
  if (body.case_name === '') delete body.case_name
  if (body.created_user === '') delete body.created_user
  if (body.case_type === '') delete body.case_type
  return api.getApiTestcaseList(body)
}
/** 从脚本选择抽屉行构造引用脚本用例快照，供右侧「用例信息」只读展示（与步骤树接口 quote_case 字段对齐） */
const snapshotQuoteCaseFromScriptRow = (row) => {
  if (!row || row.case_id == null) return null
  return {
    case_id: row.case_id,
    case_code: row.case_code,
    case_name: row.case_name || '',
    case_project: row.case_project,
    case_tags: row.case_tags,
    case_desc: row.case_desc || '',
    case_attr: row.case_attr || '',
    case_type: row.case_type || ''
  }
}

const onSelectPublicScript = (row) => {
  const replaceId = quotePublicScriptReplaceStepId.value
  const quoteCaseSnapshot = snapshotQuoteCaseFromScriptRow(row)
  const config = { quote_case_id: row.case_id, step_name: row.case_name || '引用公共脚本' }
  if (replaceId) {
    updateStepConfig(replaceId, config)
    const updated = findStep(replaceId)
    if (updated) {
      updated.original = { ...(updated.original || {}), quote_case: quoteCaseSnapshot }
      loadQuoteStepsForStep(updated)
    }
    quotePublicScriptReplaceStepId.value = null
  } else {
    const parentId = quotePublicScriptParentId.value
    const created = insertStep(parentId, 'quote', null, config)
    if (created) {
      created.original = { ...(created.original || {}), quote_case: quoteCaseSnapshot }
      selectedKeys.value = [created.id]
      updateStepDisplayNames()
      loadQuoteStepsForStep(created)
    }
    quotePublicScriptParentId.value = null
  }
  quotePublicScriptDrawerVisible.value = false
}

// 复制模式：将用例加入待复制列表
const addToCopySelection = (row) => {
  if (selectedForCopy.value.some((r) => r.case_id === row.case_id)) return
  selectedForCopy.value = [...selectedForCopy.value, row]
}

// 复制模式：从待复制列表移除
const removeFromCopySelection = (row) => {
  selectedForCopy.value = selectedForCopy.value.filter((r) => r.case_id !== row.case_id)
}

/**
 * 【步骤明细「复制指定脚本」】确认复制：调用 copyCaseStepTree 获取 steps 并插入当前用例步骤树
 *
 * 与用例管理「复制」的区别：
 *   - 本功能：仅使用 steps，将步骤插入当前正在编辑的用例步骤树中（多选可插入多个脚本的步骤）
 *   - 用例管理「复制」：使用 case + steps，创建新用例编辑页（路由跳转）
 *
 * 实现原理：
 * 1. 对每个选中的脚本调用 copyCaseStepTree(case_id)（与用例管理「复制」共用同一后端接口）
 * 2. 仅使用返回的 steps，忽略 case（用例信息来自当前编辑页）
 * 3. mapBackendStep 将后端步骤转为前端树节点格式
 * 4. insertStepFromMapped 将步骤插入到 parentId 下或根级
 */
const confirmCopySteps = async () => {
  const rows = selectedForCopy.value
  if (!rows.length) {
    window.$message?.warning?.('请至少选择一个脚本')
    return
  }
  const parentId = quotePublicScriptParentId.value
  let insertedCount = 0
  let lastInsertedId = null
  try {
    for (const row of rows) {
      const res = await api.copyCaseStepTree({ case_id: row.case_id })
      const stepsData = res?.data?.steps || res?.steps || []
      const mapped = stepsData.map(mapBackendStep).filter(Boolean)
      for (const step of mapped) {
        insertStepFromMapped(parentId, step)
        lastInsertedId = step.id
        insertedCount++
      }
    }
    if (insertedCount > 0) {
      updateStepDisplayNames()
      loadQuoteStepsForAllQuoteSteps()
      if (lastInsertedId) selectedKeys.value = [lastInsertedId]
      window.$message?.success?.(`已复制 ${insertedCount} 个步骤`)
    }
    quotePublicScriptDrawerVisible.value = false
    selectedForCopy.value = []
  } catch (error) {
    console.error('复制步骤失败', error)
    window.$message?.error?.(error?.message || error?.data?.message || '复制失败')
  }
}

/**
 * 将 mapBackendStep 后的步骤插入当前用例的步骤树（含子步骤、展开状态）
 * 用于「复制指定脚本」：将后端 strip 后的步骤转为前端格式后插入
 */
const insertStepFromMapped = (parentId, mappedStep) => {
  if (stepDefinitions[mappedStep.type]?.allowChildren) {
    stepExpandStates.value.set(mappedStep.id, true)
  }
  if (parentId) {
    const parent = findStep(parentId)
    if (parent && stepDefinitions[parent.type]?.allowChildren) {
      parent.children = parent.children || []
      parent.children.push(mappedStep)
    }
  } else {
    steps.value.push(mappedStep)
  }
}

const handleQuoteReselect = () => {
  if (!currentStep.value?.id) return
  scriptDrawerMode.value = 'quote'
  quotePublicScriptReplaceStepId.value = currentStep.value.id
  quotePublicScriptParentId.value = null
  quotePublicScriptQueryItems.value.case_type = '公共脚本'
  quotePublicScriptDrawerVisible.value = true
}

watch(quotePublicScriptDrawerVisible, (visible) => {
  if (visible) {
    nextTick(() => {
      quotePublicScriptTableRef.value?.handleSearch?.()
    })
  }
})

/** 选择公共脚本 / 复制脚本 抽屉表格「所属标签」：单行展示，悬停看全部 */
const renderQuoteDrawerCaseTagsCompact = (row) => {
  const tags = Array.isArray(row.case_tags) ? row.case_tags.filter((t) => t && t.tag_name) : []
  if (!tags.length) return h('span', '')
  const trigger = h(
      'div',
      {
        class: 'case-tags-cell-trigger',
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          maxWidth: '100%',
          minHeight: '22px'
        }
      },
      [
        h(NTag, {type: 'info', size: 'small', bordered: true}, {default: () => tags[0].tag_name}),
        tags.length > 1
            ? h('span', {class: 'case-tags-more'}, `+${tags.length - 1}`)
            : null
      ].filter(Boolean)
  )
  if (tags.length === 1) return trigger
  return h(NTooltip, {placement: 'top', trigger: 'hover', showArrow: true}, {
    trigger: () => trigger,
    default: () =>
        h(
            'div',
            {class: 'case-tags-tooltip-inner'},
            tags.map((tag) =>
                h(NTag, {type: 'info', size: 'small', bordered: true, style: {margin: '2px'}}, {default: () => tag.tag_name})
            )
        )
  })
}

const quotePublicScriptColumns = [
  {
    title: '所属应用',
    key: 'case_project',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
    render(row) {
      // case_project 现在是对象，显示 project_name
      return h('span', row.case_project?.project_name || '')
    },
  },
  {
    title: '所属标签',
    key: 'case_tags',
    width: 150,
    align: 'center',
    render(row) {
      return renderQuoteDrawerCaseTagsCompact(row)
    },
  },
  {
    title: '用例名称',
    key: 'case_name',
    width: 300,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例属性',
    key: 'case_attr',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例类型',
    key: 'case_type',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例步骤',
    key: 'case_steps',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '用例版本',
    key: 'case_version',
    width: 100,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建人员',
    key: 'created_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '更新人员',
    key: 'updated_user',
    width: 150,
    align: 'center',
    ellipsis: {tooltip: true},
  },
  {
    title: '创建时间',
    key: 'created_time',
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.created_time))
    },
  },
  {
    title: '更新时间',
    key: 'updated_time',
    width: 200,
    align: 'center',
    render(row) {
      return h('span', formatDateTime(row.updated_time))
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    render: (row) => {
      if (scriptDrawerMode.value === 'copy') {
        const isSelected = selectedForCopy.value.some((r) => r.case_id === row.case_id)
        return h(NButton, {
          size: 'small',
          type: isSelected ? 'default' : 'primary',
          onClick: () => isSelected ? removeFromCopySelection(row) : addToCopySelection(row)
        }, {default: () => isSelected ? '移除' : '加入'})
      }
      return h(NButton, {
        size: 'small',
        type: 'primary',
        onClick: () => onSelectPublicScript(row)
      }, {default: () => '选择'})
    }
  }
]

// 标签按模式分组
const tagModeGroups = computed(() => {
  const groups = {}
  tagOptions.value.forEach(tag => {
    const mode = tag.tag_mode || '未分类'
    if (!groups[mode]) {
      groups[mode] = []
    }
    groups[mode].push(tag)
  })
  return groups
})

// 当前选中模式下的标签列表
const currentTagNames = computed(() => {
  if (!selectedTagMode.value) return []
  return tagModeGroups.value[selectedTagMode.value] || []
})

// 加载项目列表（复用用例管理页面的数据源）
const loadProjects = async () => {
  try {
    projectLoading.value = true
    const res = await api.getProjectList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      projectOptions.value = res.data.map(item => ({
        label: item.project_name,
        value: item.project_id
      }))
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  } finally {
    projectLoading.value = false
  }
}

// 加载标签列表（复用用例管理页面的数据源）
const loadTags = async (projectId = null) => {
  try {
    tagLoading.value = true
    const res = await api.getTagList({
      page: 1,
      page_size: 1000,
      state: 0
    })
    if (res?.data) {
      // 如果选择了项目，则过滤该项目的标签；否则显示所有标签
      if (projectId) {
        tagOptions.value = res.data.filter(tag => tag.tag_project === projectId)
      } else {
        tagOptions.value = res.data
      }
      selectedTagMode.value = null
    }
  } catch (error) {
    console.error('加载标签列表失败:', error)
    tagOptions.value = []
  } finally {
    tagLoading.value = false
  }
}

// 获取选中的标签名称（用于显示）
const getSelectedTagNames = () => {
  const tags = caseForm.case_tags
  if (!Array.isArray(tags) || tags.length === 0) {
    return ''
  }
  const names = tags
      .map(tagId => tagOptions.value.find(t => t.tag_id === tagId)?.tag_name)
      .filter(name => name)
  return names.join(', ')
}

// 判断标签是否被选中
const isTagSelected = (tagId) => {
  const tags = caseForm.case_tags
  return Array.isArray(tags) && tags.includes(tagId)
}

// 选择标签（支持多选）
const handleTagSelect = (tagId) => {
  if (!Array.isArray(caseForm.case_tags)) {
    caseForm.case_tags = []
  }
  const index = caseForm.case_tags.indexOf(tagId)
  if (index > -1) {
    // 如果已选中，则取消选择
    caseForm.case_tags.splice(index, 1)
  } else {
    // 如果未选中，则添加
    caseForm.case_tags.push(tagId)
  }
}

// 所属应用变化时刷新标签选项；immediate 覆盖首屏（initCaseInfoFromRoute 已先执行，避免 onMounted 里再调 loadTags 导致重复请求）
initCaseInfoFromRoute()
watch(
    () => caseForm.case_project,
    (newVal) => {
      loadTags(newVal || null)
    },
    {immediate: true},
)

// 确保 case_tags 始终是数组
watch(() => caseForm.case_tags, (newVal) => {
  if (!Array.isArray(newVal)) {
    caseForm.case_tags = []
  }
}, {immediate: true})

// 当用例类型改为「公共脚本」时，自动移除步骤树中所有「引用公共脚本」步骤；若从「用户脚本」切来则暂存，切回「用户脚本」时可恢复
watch(() => caseForm.case_type, (newType, oldType) => {
  if (newType === '公共脚本') {
    const fromUserScript = oldType === '用户脚本'
    if (fromUserScript) {
      const toStash = collectQuoteStepsWithPosition()
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        stashedQuoteStepsWhenPublic.value = toStash
        window.$message?.warning?.(`切换为公共脚本，已临时移除 ${removedCount} 个「引用公共脚本」步骤（若误操作，可切回用户脚本恢复）`)
      }
    } else {
      const removedCount = removeAllQuoteSteps()
      if (removedCount > 0) {
        window.$message?.warning?.(`切换为公共脚本，已自动移除 ${removedCount} 个「引用公共脚本」步骤（公共脚本不可引用其他脚本）`)
      }
    }
  } else if (newType === '用户脚本' && stashedQuoteStepsWhenPublic.value.length > 0) {
    const restoredCount = restoreStashedQuoteSteps()
    if (restoredCount > 0) {
      window.$message?.info?.(`已恢复 ${restoredCount} 个「引用公共脚本」步骤。`)
    }
  }
})

const runLoading = ref(false)
const debugLoading = ref(false)
const saveLoading = ref(false)
// 执行/调试共用「脚本执行配置」弹窗：执行时以“DB已保存的步骤树”作为聚合来源
const execConfigMode = ref('debug') // 'debug' | 'run'
const execSourceSteps = ref(null) // 执行时用于聚合/执行的步骤树（前端映射后的结构）
const dragState = ref({
  draggingId: null,
  dragOverId: null, // 当前拖拽进入的 loop/if 步骤 ID（焦点高亮）
  dragOverParent: null,
  dragOverIndex: null,
  insertPosition: null, // 'before' | 'after' | null，用于指示插入位置
  insertTargetId: null // 插入目标步骤 ID（用于显示指示器）
})

// 下拉展示“引用公共脚本”；quote 仅用于后端步骤类型与展示
// 当用例类型为“公共脚本”时，“引用公共脚本”置灰，防止循环引用
const addOptions = computed(() => {
  const isPublicScript = caseForm.case_type === '公共脚本'
  return [
    ...Object.entries(stepDefinitions)
        .filter(([key]) => key !== 'quote')
        .map(([value, item]) => ({
          label: item.label,
          key: value,
          icon: renderIcon(item.icon, {size: 16})
        })),
    {
      label: '引用公共脚本',
      key: 'quote_public_script',
      icon: renderIcon('material-symbols:library-books-outline', {size: 16}),
      disabled: isPublicScript
    },
    // 【复制指定脚本】多选其他脚本，将步骤插入当前用例（与用例管理「复制」共用 copyCaseStepTree 接口，仅用 steps）
    {
      label: '复制指定脚本',
      key: 'copy_steps',
      icon: renderIcon('material-symbols:content-copy-outline', {size: 16})
    }
  ]
})


// 计算总步骤数（包括子步骤）
const totalStepsCount = computed(() => {
  const countSteps = (list) => {
    let count = 0
    for (const step of list) {
      count++
      if (step.children && step.children.length) {
        count += countSteps(step.children)
      }
    }
    return count
  }
  return countSteps(steps.value)
})

// 判断是否全部展开（简化处理，这里假设总是展开的）
const isAllExpanded = ref(true)

const toggleAllExpand = () => {
  // 切换全局展开/折叠状态
  isAllExpanded.value = !isAllExpanded.value

  // 批量设置所有步骤的展开状态为全局状态
  const setAllStepsExpandState = (list, state) => {
    for (const step of list) {
      if (stepDefinitions[step.type]?.allowChildren) {
        stepExpandStates.value.set(step.id, state)
        if (step.children && step.children.length) {
          setAllStepsExpandState(step.children, state)
        }
      }
    }
  }

  setAllStepsExpandState(steps.value, isAllExpanded.value)
}

// 存储每个步骤的展开/折叠状态
const stepExpandStates = ref(new Map())

// 获取步骤的展开状态（默认为true，即展开）
const isStepExpanded = (stepId) => {
  if (!stepExpandStates.value.has(stepId)) {
    // 如果还没有设置过，默认展开
    stepExpandStates.value.set(stepId, true)
  }
  return stepExpandStates.value.get(stepId)
}

// 切换单个步骤的展开/折叠状态
const toggleStepExpand = (stepId, event) => {
  event?.stopPropagation()
  const currentState = stepExpandStates.value.get(stepId) ?? true
  stepExpandStates.value.set(stepId, !currentState)
}

// 初始化所有允许子步骤的步骤的展开状态（默认为展开）
const initializeStepExpandStates = () => {
  const initializeStates = (list) => {
    for (const step of list) {
      if (stepDefinitions[step.type]?.allowChildren) {
        if (!stepExpandStates.value.has(step.id)) {
          stepExpandStates.value.set(step.id, true)
        }
        if (step.children && step.children.length) {
          initializeStates(step.children)
        }
      }
    }
  }
  initializeStates(steps.value)
}

const findStep = (id, list = steps.value) => {
  for (const step of list) {
    if (step.id === id) return step
    if (step.children && step.children.length) {
      const found = findStep(id, step.children)
      if (found) return found
    }
  }
  return null
}

const findStepParent = (id, list = steps.value, parent = null) => {
  for (const step of list) {
    if (step.id === id) return parent
    if (step.children && step.children.length) {
      const found = findStepParent(id, step.children, step)
      if (found !== null) return found
    }
  }
  return null
}

/** 前序遍历步骤树，对每个步骤执行 fn（不包含引用步骤内加载的虚拟子步骤） */
const forEachStep = (list, fn) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children && step.children.length) forEachStep(step.children, fn)
  }
}

/**
 * 前序遍历步骤树，对每个步骤执行 fn（可选：包含「引用公共脚本」加载的内部步骤）。
 * 说明：
 * - 引用脚本内部步骤来自 quoteStepsMap，仅用于聚合/展示，不写入当前用例
 * - 为避免嵌套引用导致循环，这里默认不继续展开「被引用脚本」内部的 quote 步骤
 */
const forEachStepWithQuote = (list, fn, { includeQuoteInner = true } = {}) => {
  if (!list || !Array.isArray(list)) return
  for (const step of list) {
    fn(step)
    if (step.children && step.children.length) forEachStepWithQuote(step.children, fn, { includeQuoteInner })
    if (includeQuoteInner && step?.type === 'quote') {
      const inner = quoteStepsMap.value?.[step.id] || []
      if (Array.isArray(inner) && inner.length) {
        // 被引用脚本内部：不再展开其 quote，避免循环引用
        forEachStepWithQuote(inner, fn, { includeQuoteInner: false })
      }
    }
  }
}

/** 加载单个引用步骤对应的公共脚本步骤树（仅用于展示，不写入当前用例） */
const loadQuoteStepsForStep = async (step) => {
  if (step.type !== 'quote' || !step.config?.quote_case_id) {
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
    return
  }
  try {
    const res = await api.getAutoTestStepTree({ case_id: step.config.quote_case_id })
    const data = Array.isArray(res?.data) ? res.data : []
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: data.map(mapBackendStep).filter(Boolean) }
  } catch (e) {
    console.error('加载引用脚本步骤失败', e)
    quoteStepsMap.value = { ...quoteStepsMap.value, [step.id]: [] }
  }
}

/** 加载所有引用步骤的公共脚本步骤 */
const loadQuoteStepsForAllQuoteSteps = () => {
  forEachStep(steps.value, (step) => {
    if (step.type === 'quote') loadQuoteStepsForStep(step)
  })
}

/** 执行模式/外部树：加载指定步骤树中的所有引用脚本步骤 */
const loadQuoteStepsForAllQuoteStepsFromList = async (list) => {
  const quoteSteps = []
  forEachStep(list, (s) => {
    if (s?.type === 'quote') quoteSteps.push(s)
  })
  if (!quoteSteps.length) return
  await Promise.all(quoteSteps.map((s) => loadQuoteStepsForStep(s)))
}

/**
 * 从缓存的 rawData 中提取 quote_steps 填充 quoteStepsMap，避免为每个引用步骤重复请求
 * 用于切换页签使用缓存时，不再调用 loadQuoteStepsForAllQuoteSteps（会触发接口）
 */
const fillQuoteStepsMapFromRawData = (rawList, mappedList) => {
  if (!rawList?.length || !mappedList?.length) return
  for (let i = 0; i < rawList.length; i++) {
    const raw = rawList[i]
    const mapped = mappedList[i]
    if (!raw || !mapped) continue
    if (raw.quote_steps?.length) {
      quoteStepsMap.value = {
        ...quoteStepsMap.value,
        [mapped.id]: raw.quote_steps.map(mapBackendStep).filter(Boolean)
      }
    }
    if (raw.children?.length && mapped.children?.length) {
      fillQuoteStepsMapFromRawData(raw.children, mapped.children)
    }
  }
}

/** 将引用脚本步骤树前序扁平化，得到带层级的列表（用于只读展示，含递归子级） */
const getQuoteStepsFlattened = (list, depth = 0, out = []) => {
  if (!list || !Array.isArray(list)) return out
  for (const step of list) {
    out.push({ step, depth })
    if (step.children && step.children.length) {
      getQuoteStepsFlattened(step.children, depth + 1, out)
    }
  }
  return out
}

const QUOTE_INNER_PREFIX = 'quote-inner:'
const getQuoteInnerKey = (quoteStepId, flatIndex) => `${QUOTE_INNER_PREFIX}${quoteStepId}:${flatIndex}`
const parseQuoteInnerKey = (key) => {
  if (!key || typeof key !== 'string' || !key.startsWith(QUOTE_INNER_PREFIX)) return null
  const rest = key.slice(QUOTE_INNER_PREFIX.length)
  const colon = rest.indexOf(':')
  if (colon === -1) return null
  const quoteStepId = rest.slice(0, colon)
  const flatIndex = parseInt(rest.slice(colon + 1), 10)
  if (Number.isNaN(flatIndex)) return null
  return { quoteStepId, flatIndex }
}

/** 根据 quote-inner key 解析出对应的步骤对象（用于右侧只读展示） */
const getQuoteInnerStep = (key) => {
  const parsed = parseQuoteInnerKey(key)
  if (!parsed) return null
  const list = quoteStepsMap.value[parsed.quoteStepId] || []
  const flat = getQuoteStepsFlattened(list)
  const item = flat[parsed.flatIndex]
  if (!item) return null
  return { ...item.step, isQuoteInner: true }
}

/** 前序遍历步骤树，得到扁平列表（用于计算当前步骤之前的可用变量） */
const flattenStepsPreOrder = (list, out = []) => {
  if (!list || !list.length) return out
  for (const step of list) {
    out.push(step)
    if (step.children && step.children.length) {
      flattenStepsPreOrder(step.children, out)
    }
  }
  return out
}

/** 从单个步骤中收集变量名：session_variables.key、defined_variables.key、extract_variables.name */
const collectVariableNamesFromStep = (step) => {
  const names = []
  if (!step) return names
  const cfg = step.config || {}
  const orig = step.original || {}
  const sv = cfg.session_variables ?? orig.session_variables
  const dv = cfg.defined_variables ?? orig.defined_variables
  const ev = cfg.extract_variables ?? orig.extract_variables
  if (Array.isArray(sv)) {
    sv.forEach((x) => {
      if (x && x.key) names.push(String(x.key).trim())
    })
  }
  if (Array.isArray(dv)) {
    dv.forEach((x) => {
      if (x && x.key) names.push(String(x.key).trim())
    })
  }
  if (Array.isArray(ev)) {
    ev.forEach((x) => {
      if (x && x.name) names.push(String(x.name).trim())
    })
  } else if (ev && typeof ev === 'object') {
    Object.values(ev).forEach((x) => {
      if (x && x.name) names.push(String(x.name).trim())
    })
  }
  const dbOps = cfg.database_operates ?? orig.database_operates
  if (Array.isArray(dbOps)) {
    dbOps.forEach((x) => {
      if (x && x.variable_name) names.push(String(x.variable_name).trim())
    })
  }
  return names
}

const flattenedSteps = computed(() => flattenStepsPreOrder(steps.value))

const currentStepIndex = computed(() => {
  const step = currentStep.value
  if (!step) return -1
  const list = flattenedSteps.value
  const idx = list.findIndex((s) => s.id === step.id)
  return idx
})

/** 当前步骤之前所有步骤中的可用变量名（去重，保持顺序） */
const availableVariableList = computed(() => {
  const list = flattenedSteps.value
  const idx = currentStepIndex.value
  if (idx <= 0) return []
  const seen = new Set()
  const result = []
  for (let i = 0; i < idx; i++) {
    collectVariableNamesFromStep(list[i]).forEach((name) => {
      if (name && !seen.has(name)) {
        seen.add(name)
        result.push(name)
      }
    })
  }
  return result
})

const assistFunctionsList = ref([])

const backendTypeToLocal = (step_type) => {
  switch (step_type) {
    case '用户变量':
      return 'user_variables'
    case 'TCP请求':
      return 'tcp'
    case 'HTTP请求':
      return 'http'
    case '代码请求(Python)':
    case '代码请求(Python)':
      return 'code'
    case '条件分支':
      return 'if'
    case '等待控制':
      return 'wait'
    case '循环结构':
      return 'loop'
    case '引用公共脚本':
      return 'quote'
    case '数据库请求':
      return 'database'
    default:
      return 'code'
  }
}

const parseJsonSafely = (val) => {
  if (!val) return null
  if (typeof val === 'object') return val
  try {
    return JSON.parse(val)
  } catch (e) {
    return null
  }
}

/**
 * 将后端返回的步骤数据转换为前端使用的格式
 *
 * 数据传递流程：
 * 1. 后端 API (getStepTree) 返回完整的步骤数据，包含所有字段：
 *    - step_code, step_name, step_desc, step_type
 *    - request_method, request_url, request_header, request_body, request_params
 *    - extract_variables, validators, defined_variables
 *    - id, case_id, parent_step_id, children 等
 *
 * 2. mapBackendStep 函数将后端数据转换为前端格式：
 *    - base.id: 使用 step_code 作为唯一标识
 *    - base.type: 转换为前端类型（http/loop/code/if/wait）
 *    - base.name: 使用 step_name
 *    - base.config: 提取配置数据（根据类型不同提取不同字段）
 *    - base.original: 保留完整的原始后端数据（所有字段）
 *
 * 3. 传递给编辑器组件时：
 *    - :config="currentStep.config" - 传递配置数据
 *    - :step="currentStep" - 传递完整步骤对象（包含 original）
 *
 * 4. 编辑器组件中可以通过 props.step.original 访问所有原始数据：
 *    - props.step.original.step_name - 步骤名称
 *    - props.step.original.step_desc - 步骤描述
 *    - props.step.original.step_code - 步骤代码
 *    - props.step.original.request_method - 请求方法
 *    - 等等所有后端返回的字段
 */
const mapBackendStep = (step) => {
  if (!step || !step.step_type) return null
  const localType = backendTypeToLocal(step.step_type)
  const stepId = step.step_code || (step.step_id != null ? `step-${step.step_id}` : (step.id != null ? `step-${step.id}` : genId()))
  const base = {
    id: stepId,
    type: localType,
    name: step.step_name || step.step_type || '步骤',
    config: {},
    // 保留完整的原始后端步骤数据，供编辑器组件使用
    // 这样编辑器组件可以通过 props.step.original 访问所有原始字段
    // 注意：后端返回的 step_id 对应数据库主键，需要映射到 original.id（用于更新时传递 step_id）
    original: {
      ...step,
      // 确保 id 字段被正确映射（后端返回的 step_id 对应数据库主键，用于更新时的 step_id）
      // 后端使用 replace_fields={"id": "step_id"}，所以返回的是 step_id 而不是 id
      id: step.step_id || step.id || null, // 数据库主键，用于更新（优先使用 step_id）
      step_code: step.step_code || null, // 步骤代码，用于更新
      // 确保 children 和 quote_steps 也被保留（但需要递归处理）
      children: undefined, // 先设为 undefined，后面单独处理
      quote_steps: step.quote_steps || []
    }
  }

  if (localType === 'loop') {
    base.config = {
      loop_mode: step.loop_mode || '次数循环',
      loop_on_error: step.loop_on_error || '继续下一次循环',
      loop_maximums: step.loop_maximums ? Number(step.loop_maximums) : null,
      loop_interval: step.loop_interval ? Number(step.loop_interval) : 0,
      loop_iterable: step.loop_iterable || '',
      loop_timeout: step.loop_timeout ? Number(step.loop_timeout) : 0
    }
    // 条件循环：conditions 与后端 ConditionsBase 一致
    if (step.conditions && typeof step.conditions === 'object' && !Array.isArray(step.conditions)) {
      const condition = step.conditions
      base.config.condition_expr = condition.condition_expr != null ? String(condition.condition_expr) : ''
      base.config.condition_compare = condition.condition_compare || '非空'
      base.config.condition_value = condition.condition_value != null ? String(condition.condition_value) : ''
    } else {
      base.config.condition_expr = ''
      base.config.condition_compare = '非空'
      base.config.condition_value = ''
    }
    base.children = []
  } else if (localType === 'code') {
    base.config = {
      step_name: step.step_name || '',
      code: step.code || '',
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : []
    }
  } else if (localType === 'tcp') {
    // TCP：请求体仅编辑器格式化；落库为 raw + request_text；兼容历史 json 步骤
    const argsType = (step.request_args_type || '').toString().toLowerCase()
    const payloadStr = argsType === 'json'
        ? JSON.stringify(step.request_body || {}, null, 2)
        : (step.request_text || '')
    let body_format_mode = 'xml'
    if (!String(payloadStr).trim()) body_format_mode = 'xml'
    else if (argsType === 'json') body_format_mode = 'json'
    else if (/^\s*</.test(String(payloadStr))) body_format_mode = 'xml'
    else body_format_mode = 'text'
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      host: step.request_url || '',
      port: step.request_port != null && step.request_port !== '' ? String(step.request_port) : '',
      body_format_mode,
      request_args_type: 'raw',
      request_payload: payloadStr,
      request_text: step.request_text || null,
      data: {},
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : [],
    }
  } else if (localType === 'http') {
    base.config = {
      method: step.request_method || 'POST',
      url: step.request_url || '',
      request_args_type: step.request_args_type || 'none',
      request_project_id: step.request_project_id ?? null,
      request_config_name: step.request_config_name ?? null,
      data_source_name: step.data_source_name || '',
      data_source_desc: step.data_source_desc || '',
      params: Array.isArray(step.request_params) ? step.request_params : [],
      data: step.request_body || {},
      headers: Array.isArray(step.request_header) ? step.request_header : [],
      form_data: Array.isArray(step.request_form_data) ? step.request_form_data : [],
      form_urlencoded: Array.isArray(step.request_form_urlencoded) ? step.request_form_urlencoded : [],
      request_text: step.request_text || null,
      extract: step.extract_variables || {},
      validators: step.validators || {}
    }
  } else if (localType === 'if') {
    const raw = step.conditions
    const condition = (raw != null && typeof raw === 'object' && !Array.isArray(raw)) ? raw : {}
    const cond = {
      condition_expr: condition.condition_expr != null ? String(condition.condition_expr) : '',
      condition_compare: condition.condition_compare || '非空',
      condition_value: condition.condition_value != null ? String(condition.condition_value) : '',
      condition_desc: condition.condition_desc != null ? String(condition.condition_desc) : ''
    }
    base.config = {
      conditions: { ...cond }
    }
    base.children = []
  } else if (localType === 'wait') {
    base.config = {
      seconds: step.wait || 0
    }
  } else if (localType === 'user_variables') {
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      session_variables: Array.isArray(step.session_variables) ? step.session_variables : []
    }
  } else if (localType === 'quote') {
    base.config = {
      quote_case_id: step.quote_case_id ?? null,
      step_name: step.step_name || (step.quote_case?.case_name || '引用公共脚本')
    }
  } else if (localType === 'database') {
    const ops = Array.isArray(step.database_operates) ? step.database_operates : []
    base.config = {
      step_name: step.step_name || '',
      step_desc: step.step_desc || '',
      database_searched: !!step.database_searched,
      database_operates: ops.length ? ops : [],
      extract_variables: Array.isArray(step.extract_variables) ? step.extract_variables : [],
      assert_validators: Array.isArray(step.assert_validators) ? step.assert_validators : []
    }
  }

  if (step.children && step.children.length && stepDefinitions[localType]?.allowChildren) {
    base.children = step.children.map(mapBackendStep).filter(Boolean)
    // 保留原始 children 数据到 original 中
    base.original.children = step.children
  }

  if (!stepDefinitions[localType]?.allowChildren) {
    delete base.children
    base.original.children = step.children || []
  } else if (!base.children) {
    base.children = []
    base.original.children = []
  }

  return base
}

const hydrateCaseInfo = (data) => {
  const firstStepCase = data?.[0]?.case
  if (firstStepCase) {
    caseForm.case_project = firstStepCase.case_project || ''
    caseForm.case_name = firstStepCase.case_name || ''
    caseForm.case_tags = firstStepCase.case_tags ?? (Array.isArray(firstStepCase.case_tags) ? firstStepCase.case_tags : [])
    caseForm.case_desc = firstStepCase.case_desc || ''
    caseForm.case_attr = firstStepCase.case_attr || ''
    caseForm.case_type = firstStepCase.case_type || ''
  } else if (Array.isArray(data) && data.length > 0) {
    // 有步骤但首条无 case 信息时才清空（例如接口返回异常）
    caseForm.case_project = ''
    caseForm.case_name = ''
    caseForm.case_tags = []
    caseForm.case_desc = ''
    caseForm.case_attr = ''
    caseForm.case_type = ''
  }
  // 当 data 为空（如新增用例保存后尚未有步骤）时保留当前 caseForm，不清空用户刚填写的内容
}

// 将前端类型转换为后端类型
const localTypeToBackend = (localType) => {
  const typeMap = {
    'user_variables': '用户变量',
    'tcp': 'TCP请求',
    'http': 'HTTP请求',
    'code': '代码请求(Python)',
    'if': '条件分支',
    'loop': '循环结构',
    'wait': '等待控制',
    'quote': '引用公共脚本',
    'database': '数据库请求'
  }
  return typeMap[localType] || '代码请求(Python)'
}

// 按照树的前序遍历顺序分配 step_no（确保唯一且按顺序递增）
// 返回一个 Map<step对象, stepNo>，用于在转换时获取正确的 step_no
const assignStepNumbers = (steps) => {
  const stepNoMap = new Map()
  let stepNoCounter = 1

  // 前序遍历函数：先访问节点，再递归访问子节点
  const traverse = (step) => {
    // 访问当前节点，分配 step_no
    stepNoMap.set(step, stepNoCounter++)

    // 递归访问子节点
    if (step.children && step.children.length > 0) {
      step.children.forEach(child => {
        traverse(child)
      })
    }
  }

  // 遍历所有根步骤
  steps.forEach(step => {
    traverse(step)
  })

  return stepNoMap
}

// 键值对列表去空：只保留 key 非空（trim 后）的项，避免 Key 为空时被保存
const filterKeyValueList = (list) => {
  if (!Array.isArray(list)) return []
  return list.filter((item) => item && String(item.key ?? '').trim() !== '')
}

// 将前端步骤格式转换为后端格式
// stepNoMap: Map<step对象, stepNo>，用于获取正确的 step_no
const convertStepToBackend = (step, parentStepId = null, stepNoMap = null) => {
  // 从 stepNoMap 获取 step_no，如果没有则使用默认值
  const stepNo = stepNoMap ? (stepNoMap.get(step) || 1) : 1
  const original = step.original || {}
  const config = step.config || {}

  // 判断是新增还是更新：根据后端逻辑
  // 如果 original.id 和 original.step_code 都存在，则是更新；否则是新增
  // 注意：original.id 对应后端的 step_id（数据库主键），original.step_code 对应后端的 step_code
  const hasStepId = original.id !== undefined && original.id !== null
  const hasStepCode = original.step_code !== undefined && original.step_code !== null && original.step_code !== ''
  const isUpdate = hasStepId && hasStepCode

  // 调试日志：帮助排查问题
  if (process.env.NODE_ENV === 'development') {
    console.log(`[convertStepToBackend] Step ${step.name}:`, {
      hasStepId,
      hasStepCode,
      isUpdate,
      originalId: original.id,
      originalStepCode: original.step_code,
      stepNo
    })
  }

  // 基础字段（step_desc 优先用 config，来自 HTTP 等编辑器的 emit）
  const backendStep = {
    step_name: step.name || original.step_name || '',
    step_desc: config.step_desc !== undefined ? (config.step_desc ?? '') : (original.step_desc || ''),
    step_type: localTypeToBackend(step.type),
    step_no: stepNo,
    case_id: original.case_id || caseId.value || null,
    parent_step_id: parentStepId,
    quote_case_id: original.quote_case_id || null,
    // case_type 从用例信息中获取，必填字段（新增步骤时）
    case_type: caseForm.case_type || original.case_type || '用户脚本'
  }

  // 只有更新时才传递 step_id 和 step_code（两个都必须存在）
  // 新增时不传递这两个字段（设置为undefined，让后端排除）
  if (isUpdate) {
    backendStep.step_id = original.id
    backendStep.step_code = original.step_code
  }
  // 新增时不设置 step_id 和 step_code，让它们为 undefined，后端会自动排除

  // 根据类型设置特定字段
  if (step.type === 'tcp') {
    // TCP：请求应用 + 请求地址 + 请求端口；亦可仅选应用由执行环境解析 host/port
    backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
    backendStep.request_config_name = config.request_config_name !== undefined
        ? (config.request_config_name || null)
        : (original.request_config_name || null)
    backendStep.request_url = config.host ?? original.request_url ?? ''
    const p = config.port
    backendStep.request_port =
        p !== undefined && p !== null && String(p).trim() !== ''
            ? p
            : (original.request_port ?? null)
    backendStep.request_args_type = 'raw'
    backendStep.request_text =
        config.request_text != null && config.request_text !== ''
            ? config.request_text
            : (config.request_payload ?? original.request_text ?? null)
    backendStep.request_body = {}

    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }

    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  }
  if (step.type === 'http') {
    backendStep.request_method = config.method || original.request_method || 'POST'
    backendStep.request_url = config.url || original.request_url || ''
    backendStep.request_args_type = config.request_args_type ?? original.request_args_type ?? 'none'
    backendStep.request_text = config.request_text ?? original.request_text ?? null
    backendStep.request_project_id = config.request_project_id ?? original.request_project_id ?? null
    backendStep.request_config_name = config.request_config_name !== undefined
        ? (config.request_config_name || null)
        : (original.request_config_name || null)
    backendStep.request_header = filterKeyValueList(Array.isArray(config.headers) ? config.headers : (Array.isArray(original.request_header) ? original.request_header : []))
    backendStep.request_params = filterKeyValueList(Array.isArray(config.params) ? config.params : (Array.isArray(original.request_params) ? original.request_params : []))
    backendStep.request_form_data = filterKeyValueList(Array.isArray(config.form_data) ? config.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : []))
    backendStep.request_form_urlencoded = filterKeyValueList(Array.isArray(config.form_urlencoded) ? config.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : []))
    backendStep.request_body = config.data || original.request_body || {}
    backendStep.data_source_name = config.data_source_name !== undefined
        ? (config.data_source_name || null)
        : (original.data_source_name || null)
    backendStep.data_source_desc = config.data_source_desc !== undefined
        ? (config.data_source_desc || null)
        : (original.data_source_desc || null)

    // extract_variables、assert_validators 须为数组，否则为 null
    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }

    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }

    // defined_variables 必须是列表格式，每个元素包含 key、value、desc；Key 为空的项不保存
    backendStep.defined_variables = filterKeyValueList(Array.isArray(config.defined_variables) ? config.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : []))
  } else if (step.type === 'code') {
    backendStep.code = config.code !== undefined ? config.code : (original.code || '')
    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  } else if (step.type === 'loop') {
    // 循环模式必填（与 loop_controller 默认一致）
    backendStep.loop_mode = config.loop_mode || original.loop_mode || '次数循环'
    // 错误处理策略必填（默认与 loop_controller 一致：中断循环）
    backendStep.loop_on_error = config.loop_on_error || original.loop_on_error || '中断循环'
    // 循环间隔（所有模式都需要）
    backendStep.loop_interval = config.loop_interval !== undefined ? Number(config.loop_interval) : (original.loop_interval ? Number(original.loop_interval) : 0)

    // 根据循环模式设置特定字段
    if (backendStep.loop_mode === '次数循环') {
      // 最大循环次数默认 5，与 loop_controller 一致
      backendStep.loop_maximums = config.loop_maximums !== undefined ? Number(config.loop_maximums) : (original.loop_maximums != null ? Number(original.loop_maximums) : 5)
    } else if (backendStep.loop_mode === '列表循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
    } else if (backendStep.loop_mode === '字典循环') {
      backendStep.loop_iterable = config.loop_iterable !== undefined ? config.loop_iterable : (original.loop_iterable || '')
    } else if (backendStep.loop_mode === '条件循环') {
      const fromConfigDict = config.conditions && typeof config.conditions === 'object' && !Array.isArray(config.conditions)
          ? config.conditions
          : null
      if (fromConfigDict) {
        backendStep.conditions = {
          condition_expr: fromConfigDict.condition_expr != null ? String(fromConfigDict.condition_expr) : '',
          condition_compare: fromConfigDict.condition_compare || '非空',
          condition_value: fromConfigDict.condition_value != null ? String(fromConfigDict.condition_value) : ''
        }
      } else if (
          config.condition_expr !== undefined ||
          config.condition_compare !== undefined ||
          config.condition_value !== undefined
      ) {
        backendStep.conditions = {
          condition_expr: config.condition_expr != null ? String(config.condition_expr) : '',
          condition_compare: config.condition_compare || '非空',
          condition_value: config.condition_value != null ? String(config.condition_value) : ''
        }
      } else if (original.conditions && typeof original.conditions === 'object' && !Array.isArray(original.conditions)) {
        const oc = original.conditions
        backendStep.conditions = {
          condition_expr: oc.condition_expr != null ? String(oc.condition_expr) : '',
          condition_compare: oc.condition_compare || '非空',
          condition_value: oc.condition_value != null ? String(oc.condition_value) : ''
        }
      } else {
        backendStep.conditions = null
      }
      backendStep.loop_timeout = config.loop_timeout !== undefined ? Number(config.loop_timeout) : (original.loop_timeout ? Number(original.loop_timeout) : 0)
    }
  } else if (step.type === 'if') {
    const fromConfig = config.conditions && typeof config.conditions === 'object' && !Array.isArray(config.conditions)
        ? config.conditions
        : null
    const fromOriginal = original.conditions && typeof original.conditions === 'object' && !Array.isArray(original.conditions)
        ? original.conditions
        : null
    const conditionObj = fromConfig || fromOriginal
    backendStep.conditions = conditionObj
        ? {
          condition_expr: conditionObj.condition_expr != null ? String(conditionObj.condition_expr) : '',
          condition_compare: conditionObj.condition_compare || '非空',
          condition_value: conditionObj.condition_value != null ? String(conditionObj.condition_value) : '',
          condition_desc: conditionObj.condition_desc != null ? String(conditionObj.condition_desc) : ''
        }
        : {
          condition_expr: '',
          condition_compare: '非空',
          condition_value: '',
          condition_desc: ''
        }
  } else if (step.type === 'wait') {
    backendStep.wait = config.seconds || original.wait || 0
  } else if (step.type === 'user_variables') {
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || '')
    backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
    const sv = config.session_variables ?? original.session_variables
    const list = Array.isArray(sv) ? sv : []
    backendStep.session_variables = filterKeyValueList(list.map(item => ({
      key: item.key || '',
      value: item.value ?? '',
      desc: item.desc ?? item.description ?? ''
    })))
  } else if (step.type === 'quote') {
    backendStep.quote_case_id = config.quote_case_id ?? original.quote_case_id ?? null
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
  } else if (step.type === 'database') {
    backendStep.step_name = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
    backendStep.step_desc = config.step_desc !== undefined ? config.step_desc : (original.step_desc ?? null)
    backendStep.database_searched = !!(config.database_searched ?? original.database_searched)
    const ops = config.database_operates ?? original.database_operates
    backendStep.database_operates = Array.isArray(ops) ? ops : null
    if (config.extract_variables !== undefined) {
      backendStep.extract_variables = Array.isArray(config.extract_variables) ? config.extract_variables : null
    } else if (original.extract_variables != null) {
      backendStep.extract_variables = Array.isArray(original.extract_variables) ? original.extract_variables : null
    } else {
      backendStep.extract_variables = null
    }
    if (config.assert_validators !== undefined) {
      backendStep.assert_validators = Array.isArray(config.assert_validators) ? config.assert_validators : null
    } else if (original.assert_validators != null) {
      backendStep.assert_validators = Array.isArray(original.assert_validators) ? original.assert_validators : null
    } else {
      backendStep.assert_validators = null
    }
  }

  // 处理子步骤（递归处理）
  if (step.children && step.children.length > 0) {
    // 如果是更新，使用当前步骤的id作为父步骤id；如果是新增，先传null，后端会处理
    const parentIdForChildren = isUpdate ? original.id : null
    // 递归转换子步骤，传递 stepNoMap 以获取正确的 step_no
    backendStep.children = step.children.map((child) => {
      return convertStepToBackend(child, parentIdForChildren, stepNoMap)
    })
  }

  // 添加 case 信息（每个步骤都需要包含 case 信息）
  // 如果 original.case 存在，使用它；否则从 caseForm 构建
  if (original.case) {
    backendStep.case = original.case
  } else {
    // 从 caseForm 构建 case 信息
    backendStep.case = {
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      case_name: caseForm.case_name || '',
      case_project: caseForm.case_project || null,
      case_tags: Array.isArray(caseForm.case_tags) ? caseForm.case_tags : [],
      case_type: caseForm.case_type || null,
      case_attr: caseForm.case_attr || null,
      case_desc: caseForm.case_desc || null
    }
  }

  // 清理字段：确保新增时不传递step_id和step_code，更新时必须同时传递
  // 根据后端逻辑：如果step_id和step_code都不存在，则是新增；如果都存在，则是更新；如果只存在一个，会报错
  const cleanedStep = {}
  for (const key in backendStep) {
    const value = backendStep[key]
    // 如果是新增步骤，完全排除step_id和step_code字段（不添加到cleanedStep中）
    if (!isUpdate && (key === 'step_id' || key === 'step_code')) {
      continue
    }
    // 如果是更新步骤，必须同时有step_id和step_code
    if (isUpdate && (key === 'step_id' || key === 'step_code')) {
      if (value === undefined || value === null) {
        // 更新时如果step_id或step_code为空，跳过（不应该发生）
        continue
      }
    }
    // 保留所有非undefined的值（包括null，因为null可能是有意义的）
    if (value !== undefined) {
      cleanedStep[key] = value
    }
  }

  return cleanedStep
}


// 检查键值对列表中是否存在 key 为空（trim 后）的项
const hasEmptyKeyInList = (list) => {
  if (!Array.isArray(list)) return false
  return list.some((item) => item != null && String(item.key ?? '').trim() === '' && String(item.value ?? '').trim() !== '')
}

/** 与 database_controller 一致：database_operates 可为数组或「序号→行」对象 */
const normalizeDatabaseOperatesList = (ops) => {
  if (ops == null) return []
  if (Array.isArray(ops)) return ops
  if (typeof ops === 'object') {
    const keys = Object.keys(ops).map((k) => parseInt(k, 10)).filter((n) => !isNaN(n)).sort((a, b) => a - b)
    return keys.map((k) => ops[k])
  }
  return []
}

const validateDatabaseSteps = (stepList) => {
  for (const step of stepList) {
    if (step.type === 'database') {
      const config = step.config || {}
      const original = step.original || {}
      const rawOps = config.database_operates ?? original.database_operates
      const stepName = step.name || original.step_name || '未命名步骤'

      if (rawOps != null && typeof rawOps !== 'object') {
        return {valid: false, message: `步骤「${stepName}」数据库请求配置格式无效，请重新打开步骤编辑或删除后添加。`}
      }

      const list = normalizeDatabaseOperatesList(rawOps)
      if (!list.length) {
        return {
          valid: false,
          message: `步骤「${stepName}」数据库请求须配置「请求配置」：请至少添加一条数据库操作（所属应用、配置名称、数据库名称、SQL 语句、存储变量均必填）。`
        }
      }

      for (let i = 0; i < list.length; i++) {
        const o = list[i] || {}
        const idxLabel = `第 ${i + 1} 条`
        const pid = o.project_id
        const hasApp =
            String(o.project_name ?? '').trim() !== ''
            || (pid != null && pid !== '' && String(pid).trim() !== '')
        if (!hasApp) {
          return {
            valid: false,
            message: `步骤「${stepName}」数据库请求「请求配置」${idxLabel}：请选择所属应用。`
          }
        }
        if (!String(o.config_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤「${stepName}」数据库请求「请求配置」${idxLabel}：请填写配置名称。`
          }
        }
        if (!String(o.database_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤「${stepName}」数据库请求「请求配置」${idxLabel}：请填写数据库名称。`
          }
        }
        if (!String(o.expr ?? '').trim()) {
          return {
            valid: false,
            message: `步骤「${stepName}」数据库请求「请求配置」${idxLabel}：请填写 SQL 语句。`
          }
        }
        if (!String(o.variable_name ?? '').trim()) {
          return {
            valid: false,
            message: `步骤「${stepName}」数据库请求「请求配置」${idxLabel}：请填写存储变量（变量名）。`
          }
        }
      }
    }
    if (step.children && step.children.length > 0) {
      const child = validateDatabaseSteps(step.children)
      if (!child.valid) return child
    }
  }
  return {valid: true}
}

/** HTTP：所属应用、配置名称、请求地址必填；TCP：另含请求端口必填（取值与 convertStepToBackend 一致） */
const validateHttpTcpStepsRequired = (stepList) => {
  const walk = (list) => {
    if (!Array.isArray(list)) return {valid: true}
    for (const step of list) {
      const stepLabel = step.name || step.original?.step_name || '未命名步骤'
      const config = step.config || {}
      const original = step.original || {}

      if (step.type === 'http') {
        const projectId = config.request_project_id ?? original.request_project_id ?? null
        const emptyProject = projectId === null || projectId === undefined || projectId === ''

        let cfgName = ''
        if (config.request_config_name !== undefined) {
          cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
        } else {
          cfgName = String(original.request_config_name ?? '').trim()
        }

        const url = String(config.url ?? original.request_url ?? '').trim()

        if (emptyProject) {
          return {valid: false, message: `步骤「${stepLabel}」HTTP请求：请选择所属应用后再保存。`}
        }
        if (!cfgName) {
          return {valid: false, message: `步骤「${stepLabel}」HTTP请求：请填写配置名称后再保存。`}
        }
        if (!url) {
          return {valid: false, message: `步骤「${stepLabel}」HTTP请求：请填写请求地址后再保存。`}
        }
      }

      if (step.type === 'tcp') {
        const projectId = config.request_project_id ?? original.request_project_id ?? null
        const emptyProject = projectId === null || projectId === undefined || projectId === ''

        let cfgName = ''
        if (config.request_config_name !== undefined) {
          cfgName = config.request_config_name == null ? '' : String(config.request_config_name).trim()
        } else {
          cfgName = String(original.request_config_name ?? '').trim()
        }

        const host = String(config.host ?? original.request_url ?? '').trim()

        let portStr = ''
        const p = config.port
        if (p !== undefined && p !== null && String(p).trim() !== '') {
          portStr = String(p).trim()
        } else if (original.request_port != null && original.request_port !== '') {
          portStr = String(original.request_port).trim()
        }

        if (emptyProject) {
          return {valid: false, message: `步骤「${stepLabel}」TCP请求：请选择所属应用后再保存。`}
        }
        if (!cfgName) {
          return {valid: false, message: `步骤「${stepLabel}」TCP请求：请填写配置名称后再保存。`}
        }
        if (!host) {
          return {valid: false, message: `步骤「${stepLabel}」TCP请求：请填写请求地址后再保存。`}
        }
        if (!portStr) {
          return {valid: false, message: `步骤「${stepLabel}」TCP请求：请填写请求端口后再保存。`}
        }
      }

      if (step.children && step.children.length > 0) {
        const child = walk(step.children)
        if (!child.valid) return child
      }
    }
    return {valid: true}
  }
  return walk(stepList)
}

// 递归校验步骤树中是否存在“键为空”的键值对（请求头/请求体/变量/用户变量等），若存在则不允许保存
const validateEmptyKeyInSteps = (stepList) => {
  for (const step of stepList) {
    const config = step.config || {}
    const original = step.original || {}
    const getList = (key) => (Array.isArray(config[key]) ? config[key] : Array.isArray(original[key]) ? original[key] : [])
    let listName = ''
    if (step.type === 'http') {
      if (hasEmptyKeyInList(getList('headers')) || hasEmptyKeyInList(getList('request_header'))) listName = '请求头'
      else if (hasEmptyKeyInList(getList('params')) || hasEmptyKeyInList(getList('request_params'))) listName = '请求体 params'
      else if (hasEmptyKeyInList(getList('form_data')) || hasEmptyKeyInList(getList('request_form_data'))) listName = '请求体 form-data'
      else if (hasEmptyKeyInList(getList('form_urlencoded')) || hasEmptyKeyInList(getList('request_form_urlencoded'))) listName = '请求体 x-www-form-urlencoded'
      else if (hasEmptyKeyInList(getList('defined_variables'))) listName = '变量'
    } else if (step.type === 'user_variables') {
      if (hasEmptyKeyInList(getList('session_variables'))) listName = '用户变量'
    }
    if (listName) {
      return {valid: false, stepName: step.name || step.original?.step_name || '未命名步骤', listName}
    }
    if (step.children && step.children.length > 0) {
      const childResult = validateEmptyKeyInSteps(step.children)
      if (!childResult.valid) return childResult
    }
  }
  return {valid: true}
}

// 递归校验步骤树中所有 HTTP 步骤：若请求体为 json，则校验 JSON 语法
const validateJsonBodyInSteps = (stepList) => {
  for (const step of stepList) {
    if (step.type === 'http') {
      const config = step.config || {}
      const requestArgsType = config.request_args_type ?? 'none'
      if (requestArgsType === 'json') {
        const raw = config.jsonBodyText ?? (config.data != null ? JSON.stringify(config.data) : '')
        const trimmed = (raw || '').trim()
        if (trimmed !== '') {
          try {
            JSON.parse(trimmed)
          } catch (e) {
            const stepName = step.name || config.step_name || '未命名步骤'
            return {valid: false, message: e.message || 'JSON 格式错误', stepName}
          }
        }
      }
    }
    if (step.children && step.children.length > 0) {
      const childResult = validateJsonBodyInSteps(step.children)
      if (!childResult.valid) return childResult
    }
  }
  return {valid: true}
}

// 校验用例信息必填项（所属应用、用例名称、所属标签、用例属性、用例类型）
const validateCaseForm = () => {
  if (!caseForm.case_project) {
    return {valid: false, message: '请选择所属应用'}
  }
  if (!caseForm.case_name || !String(caseForm.case_name).trim()) {
    return {valid: false, message: '请输入用例名称'}
  }
  if (!Array.isArray(caseForm.case_tags) || caseForm.case_tags.length === 0) {
    return {valid: false, message: '请选择所属标签'}
  }
  if (!caseForm.case_attr) {
    return {valid: false, message: '请选择用例属性'}
  }
  if (!caseForm.case_type) {
    return {valid: false, message: '请选择用例类型'}
  }
  return {valid: true}
}

// 将后端返回的 success_detail（前序顺序）写回步骤树，使下次保存走更新而非新增，避免重复保存产生重复步骤
const mergeStepTreeWithSuccessDetail = (stepList, detailList) => {
  if (!Array.isArray(detailList) || detailList.length === 0) return
  let idx = 0
  const traverse = (list) => {
    if (!Array.isArray(list)) return
    for (const step of list) {
      const detail = detailList[idx]
      if (detail && (detail.step_id != null || detail.step_code != null)) {
        if (!step.original) step.original = {}
        if (detail.step_id != null) step.original.id = detail.step_id
        if (detail.step_code != null) step.original.step_code = detail.step_code
      }
      idx += 1
      if (step.children && step.children.length > 0) traverse(step.children)
    }
  }
  traverse(stepList)
}

const handleSaveAll = async () => {
  if (saveLoading.value) return
  if (!steps.value?.length) {
    window.$message?.warning?.('请至少添加一个步骤后再点击保存')
    return
  }
  saveLoading.value = true
  try {
    // 用例信息必填项校验
    const caseValidation = validateCaseForm()
    if (!caseValidation.valid) {
      window.$message?.error?.(caseValidation.message)
      return
    }

    const stepNameValidation = validateStepNamesInSteps(steps.value)
    if (!stepNameValidation.valid) {
      notifyError(stepNameValidation.message)
      return
    }

    const httpTcpRequired = validateHttpTcpStepsRequired(steps.value)
    if (!httpTcpRequired.valid) {
      notifyError(httpTcpRequired.message)
      return
    }

    // 请求体为 json 时校验 JSON 语法，有错误则提示并阻止保存
    const jsonValidation = validateJsonBodyInSteps(steps.value)
    if (!jsonValidation.valid) {
      window.$message?.error?.(
          `步骤「${jsonValidation.stepName}」请求体 JSON 格式错误，请修正后再保存。}`
      )
      return
    }

    const dbValidation = validateDatabaseSteps(steps.value)
    if (!dbValidation.valid) {
      window.$message?.error?.(dbValidation.message)
      return
    }

    // 键值对去空校验：存在 Key 为空的项时不允许保存
    const emptyKeyValidation = validateEmptyKeyInSteps(steps.value)
    if (!emptyKeyValidation.valid) {
      window.$message?.error?.(
          `步骤 [${emptyKeyValidation.stepName}] : [${emptyKeyValidation.listName}] 存在键为空的项，请填写或删除后再保存。`
      )
      return
    }

    // 获取当前用户信息（用于 updated_user 字段）
    const userStore = useUserStore()
    const currentUser = userStore.username || ''

    // 计算总步骤数（包括子步骤）
    const countTotalSteps = (stepList) => {
      let count = 0
      for (const step of stepList) {
        count++
        if (step.children && step.children.length > 0) {
          count += countTotalSteps(step.children)
        }
      }
      return count
    }
    const totalSteps = countTotalSteps(steps.value)

    // 构建用例信息（AutoTestApiCaseUpdate 格式）
    const caseInfo = {
      // 根据是否有caseId或caseCode判断是新增还是更新
      case_id: caseId.value || null,
      case_code: caseCode.value || null,
      case_name: caseForm.case_name || '',
      case_project: caseForm.case_project || null,
      case_tags: Array.isArray(caseForm.case_tags) ? caseForm.case_tags : [],
      case_type: caseForm.case_type || null,
      case_attr: caseForm.case_attr || null,
      case_desc: caseForm.case_desc || null,
      case_steps: totalSteps, // 用例步骤数量(含所有子级步骤)
      session_variables: null, // 如果需要可以从其他地方获取
      updated_user: currentUser
    }

    // 按照树的前序遍历顺序分配 step_no，确保唯一且按顺序递增
    const stepNoMap = assignStepNumbers(steps.value)

    // 转换步骤数据，使用分配好的 step_no，并保持树结构
    const backendSteps = steps.value.map((step) => {
      return convertStepToBackend(step, null, stepNoMap)
    })

    // 构建请求体（AutoTestStepTreeUpdateList 格式）
    const payload = {
      case: caseInfo,
      steps: backendSteps
    }

    // 调用新的后端接口
    const res = await api.updateOrCreateStepTree(payload)
    if (res?.code === '000000' || res?.code === 200 || res?.code === 0) {
      window.$message?.success?.(res?.message || '保存成功')

      // 将本次保存返回的 step_id/step_code 写回当前步骤树，避免重复点击保存时再次被当作新增
      const stepDetail = res?.data?.steps?.success_detail
      if (Array.isArray(stepDetail) && stepDetail.length > 0) {
        mergeStepTreeWithSuccessDetail(steps.value, stepDetail)
      }

      // 新增用例保存成功后，将 case_id / case_code 写入 URL，以便后续加载和刷新保留
      if (res?.data?.cases?.success_detail && res.data.cases.success_detail.length > 0) {
        const savedCase = res.data.cases.success_detail[0]
        if (savedCase.case_id && !caseId.value) {
          await router.replace({
            path: route.path,
            query: {...route.query, case_id: String(savedCase.case_id), case_code: savedCase.case_code || ''}
          })
        }
      }

      // 保存成功后清除缓存，确保下次加载获取最新数据
      autotestStore.clearStepTreeCache(caseId.value, caseCode.value)
      // 重新加载数据（URL 已更新，loadSteps 会带上 case_id；若无步骤，hydrateCaseInfo 会保留当前 caseForm）
      await loadSteps()
    } else {
      window.$message?.error?.(res?.message || '保存失败')
    }
  } catch (error) {
    console.error('Failed to save step tree', error)
    window.$message?.error?.(error?.response?.data?.message || error?.message || '保存失败')
  } finally {
    saveLoading.value = false
  }
}

const handleRun = async () => {
  if (!caseId.value && !caseCode.value) {
    window.$message?.warning?.('请先选择或创建测试用例')
    return
  }

  // 执行：以“DB已保存的步骤树”为准（避免用例管理页执行时拿不到本地步骤树）
  try {
    runLoading.value = true
    const params = {}
    if (caseId.value) params.case_id = caseId.value
    if (caseCode.value) params.case_code = caseCode.value
    const res = await api.getAutoTestStepTree(params)
    const data = Array.isArray(res?.data) ? res.data : []
    execSourceSteps.value = data.map(mapBackendStep).filter(Boolean)
    // 执行模式也要加载引用公共脚本内部步骤（用于聚合）
    await loadQuoteStepsForAllQuoteStepsFromList(execSourceSteps.value)
    execConfigMode.value = 'run'
    debugEnvMode.value = 'single'
    execConfigMainCardExpanded.value = true
    execDatasetCardExpanded.value = true
    debugExecDataSourceEnabled.value = false
    debugExecDatasetRows.value = []
    debugExecDatasetSelectedIds.value = []
    debugGlobalEnvId.value = null
    debugSelectedProjectId.value = null
    debugEnvConfigDict.value = {}
    debugRows.value = collectDebugRows(execSourceSteps.value)
    debugConfigModalVisible.value = true
    loadDebugEnvEnums()
  } catch (e) {
    console.error('加载已保存步骤树失败', e)
    window.$message?.error?.(e?.message || '加载步骤树失败')
  } finally {
    runLoading.value = false
  }
}

const handleDebug = () => {
  if (!steps.value || steps.value.length === 0) {
    window.$message?.warning?.('请先添加测试步骤')
    return
  }
  openDebugConfigModal()
}

const envLoading = ref(false)

// 调试弹窗使用 env_id（用于查询环境配置），并通过映射得到 env_name（用于 executeStepTree）
const debugEnvOptions = ref([]) // [{ label: env_name, value: env_id }]
const debugEnvIdToName = ref(new Map())

const loadDebugEnvEnums = async () => {
  envLoading.value = true
  try {
    const res = await api.getEnvList({ page: 1, page_size: 9999, state: 0 })
    const list = Array.isArray(res?.data) ? res.data : []
    debugEnvOptions.value = list
        .map((x) => ({ label: x.env_name, value: x.env_id }))
        .filter((x) => x.value != null)
    const m = new Map()
    list.forEach((x) => {
      if (x?.env_id != null) m.set(String(x.env_id), x.env_name)
    })
    debugEnvIdToName.value = m
  } catch (e) {
    console.error('加载环境枚举失败', e)
    debugEnvOptions.value = []
    debugEnvIdToName.value = new Map()
  } finally {
    envLoading.value = false
  }
}

// -----------------------------
// 调试：脚本执行配置（实时从步骤树聚合）
// -----------------------------
const debugConfigModalVisible = ref(false)
const execConfigMainCardExpanded = ref(true)
const execDatasetCardExpanded = ref(true)
const debugExecDataSourceEnabled = ref(false)
const debugExecDatasetRows = ref([])
const debugExecDatasetSelectedIds = ref([])
const debugExecDatasetSelectedCount = computed(() => debugExecDatasetSelectedIds.value.length)

const debugExecDataSourceRailStyle = ({ focused, checked }) => {
  const style = {}
  if (checked) {
    style.background = '#F4511E'
    if (focused) {
      style.boxShadow = '0 0 0 2px #d0305040'
    }
  } else {
    style.background = '#2080f0'
    if (focused) {
      style.boxShadow = '0 0 0 2px #2080f040'
    }
  }
  return style
}

watch(debugExecDataSourceEnabled, (on) => {
  if (!on) {
    debugExecDatasetSelectedIds.value = []
  }
})

const debugEnvMode = ref('single') // 'single' | 'multi'
const debugGlobalEnvId = ref(null)
const debugSelectedProjectId = ref(null)
const debugEnvConfigDict = ref({}) // project_id -> env_id -> type -> config_name -> info

const projectLabelMap = computed(() => {
  const m = new Map()
  const list = Array.isArray(projectOptions.value) ? projectOptions.value : []
  list.forEach((x) => {
    if (x && x.value != null) m.set(String(x.value), x.label ?? String(x.value))
  })
  return m
})

/**
 * 「调试」按钮 → 打开「脚本执行配置」弹窗时的核心：从步骤树实时聚合右侧表格数据。
 *
 * 设计目标：
 * - 右侧不按“步骤”逐条展示，而是按“配置”聚合（去重）：
 *   - API：同一应用(project_id)下同一配置名(config_name)只展示一行
 *   - DB：同一应用(project_id)下同一 (config_name + database_name) 只展示一行
 *   - FILE：目前步骤树尚无明确字段来源，先保留空列表（后续补齐来源字段即可接入同一套聚合/拆分机制）
 *
 * 为什么要保留 targets：
 * - UI 层只展示“聚合后的一行配置”，但后端执行前替换必须精确知道该配置要作用到哪些步骤。
 * - 因此每一行都会收集它命中的所有“目标步骤”targets，并在「确定并调试」时再拆分为：
 *   steps_execute_config: { step_id 或 @@step_name: { config detail } }
 *
 * target 的 key 规则（与后端约定）：
 * - 已落库步骤：使用后端 step_id（前端映射为 step.original.id）
 * - 未落库新增步骤：使用 @@{step_name}（避免没有 step_id 时后端无法定位）
 */
const collectDebugRows = (sourceSteps = null) => {
  const apiRows = []
  const dbRows = []
  const fileRows = []

  // 将步骤转换为“后端可识别”的 key：step_id 或 @@step_name
  const getBackendKeyFromStep = (step) => {
    const sid = step?.original?.id
    if (sid != null) return String(sid)
    const n = step?.name || step?.original?.step_name || ''
    return `@@${String(n).trim() || '未命名步骤'}`
  }

  /**
   * 将一个 target 追加到某个聚合行中（并做去重）。
   * - groupKey 决定“哪些步骤算同一行配置”
   * - row.targets 记录该行配置要作用到哪些步骤（用于提交时拆分回单步配置映射）
   */
  const addToGroup = (map, groupKey, rowFactory, target) => {
    if (!map.has(groupKey)) map.set(groupKey, rowFactory())
    const row = map.get(groupKey)
    row.targets = row.targets || []
    // 避免同一 target 重复加入（尤其 DB 同一步骤多次遍历时）
    const tkey = `${target.backend_key}#${target.local_step_id}#${target.op_index ?? ''}`
    if (!row._targetKeySet) row._targetKeySet = new Set()
    if (!row._targetKeySet.has(tkey)) {
      row._targetKeySet.add(tkey)
      row.targets.push(target)
    }
    return row
  }

  const apiGroup = new Map()
  const dbGroup = new Map()
  const fileGroup = new Map()
  const apiConfigNameSetByProject = new Map() // projectId -> Set(configName)
  const dbConfigNameSetByProject = new Map()
  const dbNameSetByProject = new Map()
  const fileConfigNameSetByProject = new Map()

  const pushSet = (map, k, v) => {
    if (!k) return
    const key = String(k)
    if (!map.has(key)) map.set(key, new Set())
    if (v != null && String(v).trim() !== '') map.get(key).add(String(v))
  }

  const walk = Array.isArray(sourceSteps) ? sourceSteps : (steps.value || [])
  // 聚合包含引用公共脚本内部步骤（quoteStepsMap 中的虚拟树）
  forEachStepWithQuote(walk, (step) => {
    if (!step) return
    if (step.type === 'http' || step.type === 'tcp') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const project_id = cfg.request_project_id ?? orig.request_project_id ?? null
      if (!project_id) return
      const request_config_name = cfg.request_config_name ?? orig.request_config_name ?? null
      pushSet(apiConfigNameSetByProject, project_id, request_config_name)
      const backend_key = getBackendKeyFromStep(step)
      const normalizedName = request_config_name != null ? String(request_config_name).trim() : ''
      // 去重策略（API）：
      // - 若配置名非空：同一应用 + 同一配置名 => 聚合成一行
      // - 若配置名为空：按步骤维度保留（避免把“未配置/待选择”的多步骤误合并）
      const groupKey = normalizedName ? `p:${project_id}|n:${normalizedName}` : `p:${project_id}|step:${backend_key}`
      addToGroup(
          apiGroup,
          groupKey,
          () => ({
            key: `api:${groupKey}`,
            project_id,
            request_config_name: normalizedName || null,
            env_id: null,
            targets: [],
          }),
          { local_step_id: step.id, backend_key }
      )
      // FILE：目前步骤树内暂无明确字段可区分 file 配置，先保留空列表（只展示分类与样式）
    } else if (step.type === 'database') {
      const cfg = step.config || {}
      const orig = step.original || {}
      const ops = cfg.database_operates ?? orig.database_operates
      const list = Array.isArray(ops) ? ops : []
      list.forEach((op, idx) => {
        if (!op) return
        const project_id = op.project_id ?? null
        if (!project_id) return
        pushSet(dbConfigNameSetByProject, project_id, op.config_name)
        pushSet(dbNameSetByProject, project_id, op.database_name)
        const backend_key = getBackendKeyFromStep(step)
        const cfgName = op.config_name != null ? String(op.config_name).trim() : ''
        const dbName = op.database_name != null ? String(op.database_name).trim() : ''
        // 去重策略（DB）：
        // - 若 config_name + database_name 都存在：同一应用 + 同一(config_name+database_name) => 聚合成一行
        // - 若缺失：按“步骤 + 操作索引”保留（避免把不同操作误合并）
        const groupKey = (cfgName && dbName)
            ? `p:${project_id}|c:${cfgName}|d:${dbName}`
            : `p:${project_id}|step:${backend_key}|op:${idx}`
        addToGroup(
            dbGroup,
            groupKey,
            () => ({
              key: `db:${groupKey}`,
              project_id,
              config_name: cfgName || null,
              database_name: dbName || null,
              env_id: null,
              targets: [],
            }),
            { local_step_id: step.id, backend_key, op_index: idx }
        )
      })
    }
  })

  const buildOptions = (set) => Array.from(set || []).map((x) => ({ label: x, value: x }))
  Array.from(apiGroup.values()).forEach((r) => {
    const set = apiConfigNameSetByProject.get(String(r.project_id))
    r._configNameSeed = buildOptions(set)
  })
  Array.from(dbGroup.values()).forEach((r) => {
    const s1 = dbConfigNameSetByProject.get(String(r.project_id))
    const s2 = dbNameSetByProject.get(String(r.project_id))
    r._configNameSeed = buildOptions(s1)
    r._dbNameSeed = buildOptions(s2)
  })
  Array.from(fileGroup.values()).forEach((r) => {
    const s = fileConfigNameSetByProject.get(String(r.project_id))
    r._configNameSeed = buildOptions(s)
  })

  apiRows.push(...Array.from(apiGroup.values()).map((r) => {
    delete r._targetKeySet
    return r
  }))
  dbRows.push(...Array.from(dbGroup.values()).map((r) => {
    delete r._targetKeySet
    return r
  }))
  fileRows.push(...Array.from(fileGroup.values()).map((r) => {
    delete r._targetKeySet
    return r
  }))

  return { apiRows, dbRows, fileRows }
}

const debugRows = ref({ apiRows: [], dbRows: [], fileRows: [] })

const debugApps = computed(() => {
  const byProject = new Map()
  const addCount = (pid, incApi = 0, incDb = 0) => {
    const k = String(pid)
    if (!byProject.has(k)) byProject.set(k, { project_id: pid, api: 0, db: 0 })
    const item = byProject.get(k)
    item.api += incApi
    item.db += incDb
  }
  debugRows.value.apiRows.forEach((r) => addCount(r.project_id, 1, 0))
  debugRows.value.dbRows.forEach((r) => addCount(r.project_id, 0, 1))
  debugRows.value.fileRows.forEach((r) => addCount(r.project_id, 1, 0))

  const list = Array.from(byProject.values()).map((x) => {
    const label = projectLabelMap.value.get(String(x.project_id)) || `应用${String(x.project_id)}`
    return {
      project_id: x.project_id,
      label,
      apiCount: x.api,
      dbCount: x.db,
      totalCount: x.api + x.db,
    }
  })
  list.sort((a, b) => String(a.project_id).localeCompare(String(b.project_id)))
  return list
})

const debugApiRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.apiRows.filter((r) => String(r.project_id) === String(pid))
})

const debugDbRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.dbRows.filter((r) => String(r.project_id) === String(pid))
})

const debugFileRowsForSelected = computed(() => {
  const pid = debugSelectedProjectId.value
  if (!pid) return []
  return debugRows.value.fileRows.filter((r) => String(r.project_id) === String(pid))
})

const openDebugConfigModal = () => {
  execConfigMode.value = 'debug'
  execSourceSteps.value = null
  debugEnvMode.value = 'single'
  execConfigMainCardExpanded.value = true
  execDatasetCardExpanded.value = true
  debugExecDataSourceEnabled.value = false
  debugExecDatasetRows.value = []
  debugExecDatasetSelectedIds.value = []
  debugGlobalEnvId.value = null
  debugSelectedProjectId.value = null
  debugEnvConfigDict.value = {}
  debugRows.value = collectDebugRows()
  debugConfigModalVisible.value = true
  loadDebugEnvEnums()
}

const onDebugModalAfterEnter = () => {
  // 默认选中第一个应用
  if (!debugSelectedProjectId.value && debugApps.value.length > 0) {
    debugSelectedProjectId.value = debugApps.value[0].project_id
  }
  // 默认选中第一个环境
  if (!debugGlobalEnvId.value && debugEnvOptions.value.length > 0) {
    debugGlobalEnvId.value = debugEnvOptions.value[0].value
  }

  // 拉取配置：按当前步骤树聚合出的应用列表
  const project_ids = debugApps.value.map((x) => Number(x.project_id)).filter((x) => !Number.isNaN(x))
  if (project_ids.length) loadEnvConfigByProjects(project_ids)
}

// 全局环境切换：默认替换所有行的环境选择（单环境/多环境都生效；多环境下用户仍可再手动改单行）
watch(() => debugGlobalEnvId.value, (envId) => {
  if (!envId) return
  const apply = (rows) => {
    rows.forEach((r) => { r.env_id = envId })
  }
  apply(debugRows.value.apiRows || [])
  apply(debugRows.value.dbRows || [])
  apply(debugRows.value.fileRows || [])
})

const loadEnvConfigByProjects = async (project_ids) => {
  try {
    const res = await api.queryEnvConfigClassifiedByProjects({ project_ids })
    // 后端返回第一层 key 为 int，axios 会转为 string；这里同时兼容两者
    debugEnvConfigDict.value = res?.data || {}
  } catch (e) {
    console.error('加载环境配置失败', e)
    debugEnvConfigDict.value = {}
  }
}

const getEffectiveEnvIdForRow = (row) => {
  return debugEnvMode.value === 'single'
      ? (debugGlobalEnvId.value || null)
      : (row.env_id || debugGlobalEnvId.value || null)
}

const getBucket = (row, configType) => {
  const dict = debugEnvConfigDict.value || {}
  const envId = getEffectiveEnvIdForRow(row)
  if (envId == null) return {}
  const p = dict?.[row.project_id] || dict?.[String(row.project_id)] || {}
  const e = p?.[envId] || p?.[String(envId)] || {}
  return e?.[configType] || {}
}

const getApiConfigOptions = (row) => {
  const bucket = getBucket(row, 'api')
  const names = Object.keys(bucket || {})
  return names.length ? names.map((x) => ({ label: x, value: x })) : (row._configNameSeed || [])
}

const getDbConfigOptions = (row) => {
  const bucket = getBucket(row, 'database')
  const names = Object.keys(bucket || {})
  return names.length ? names.map((x) => ({ label: x, value: x })) : (row._configNameSeed || [])
}

const getDbNameOptions = (row) => {
  const bucket = getBucket(row, 'database')
  const dbNames = Object.values(bucket || {})
      .map((x) => x?.database_name)
      .filter((x) => x != null && String(x).trim() !== '')
  const uniq = Array.from(new Set(dbNames))
  return uniq.length ? uniq.map((x) => ({ label: x, value: x })) : (row._dbNameSeed || [])
}

const getFileConfigOptions = (row) => {
  const bucket = getBucket(row, 'file')
  const names = Object.keys(bucket || {})
  return names.length ? names.map((x) => ({ label: x, value: x })) : (row._configNameSeed || [])
}

const getRowAddrPreview = (row, configType) => {
  const bucket = getBucket(row, configType)
  const name =
      configType === 'api'
          ? row.request_config_name
          : (configType === 'database' ? row.config_name : row.config_name)
  const info = name ? bucket?.[name] : null
  return info?.config_host ? `${info.config_host}${info.config_port ? `:${info.config_port}` : ''}` : ''
}

const applyDebugConfigToSteps = () => {
  const apiRows = debugRows.value.apiRows
  const dbRows = debugRows.value.dbRows

  // API：回写到 http/tcp 步骤的 config 中（统一通过步骤树实时数据）
  apiRows.forEach((r) => {
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      if (!step.config) step.config = {}
      step.config.request_project_id = r.project_id ?? step.config.request_project_id
      step.config.request_config_name = r.request_config_name ?? step.config.request_config_name
    })
  })

  // DB：回写到 database_operates
  dbRows.forEach((r) => {
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      const step = findStep(t.local_step_id)
      if (!step) return
      const cfg = step.config || {}
      const ops = Array.isArray(cfg.database_operates) ? cfg.database_operates : []
      const idx = t.op_index
      if (idx == null || !ops[idx]) return
      ops[idx].project_id = r.project_id ?? ops[idx].project_id
      ops[idx].config_name = r.config_name ?? ops[idx].config_name
      ops[idx].database_name = r.database_name ?? ops[idx].database_name
    })
  })
}

/**
 * 将“聚合后的配置行”拆分为“按步骤定位的配置映射”，用于后端执行前替换。
 *
 * 输出结构（提交给后端的 steps_execute_config）：
 * {
 *   "步骤ID1": {},
 *   "步骤ID2": { env_name, config_type, config_name, config_host, config_port, database_name },
 *   "@@新增步骤名称": { ... },
 * }
 *
 * 说明：
 * - 即使某些步骤最终没有配置覆盖，也会预填一个空对象，方便后端区分“未配置”与“不存在该 key”。
 * - 一条聚合行可能命中多个 targets（多个步骤），拆分时会把同一份配置复制到每个 target key 下。
 */
const buildStepExecConfigMap = (env_name) => {
  const map = {}
  // 预填：所有可配置步骤都要有 key（即便最终为空 {}）
  const prefill = (rows) => {
    rows.forEach((r) => {
      const targets = Array.isArray(r.targets) ? r.targets : []
      targets.forEach((t) => { map[String(t.backend_key)] = {} })
    })
  }
  prefill(debugRows.value.apiRows || [])
  prefill(debugRows.value.dbRows || [])
  prefill(debugRows.value.fileRows || [])

  // 填充：API（将同一行配置复制到该行命中的所有 targets）
  debugRows.value.apiRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'api')
    const name = r.request_config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      map[String(t.backend_key)] = {
        env_name,
        config_type: 'api',
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? null,
      }
    })
  })

  // 填充：DB（将同一行配置复制到该行命中的所有 targets）
  debugRows.value.dbRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'database')
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      map[String(t.backend_key)] = {
        env_name,
        config_type: 'database',
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: r.database_name || info.database_name || null,
      }
    })
  })

  // 填充：FILE（将同一行配置复制到该行命中的所有 targets）
  debugRows.value.fileRows.forEach((r) => {
    const envId = getEffectiveEnvIdForRow(r)
    const bucket = getBucket({ ...r, env_id: envId }, 'file')
    const name = r.config_name
    const info = name ? bucket?.[name] : null
    if (!env_name || !name || !info) return
    const targets = Array.isArray(r.targets) ? r.targets : []
    targets.forEach((t) => {
      map[String(t.backend_key)] = {
        env_name,
        config_type: 'file',
        config_name: name,
        config_host: info.config_host,
        config_port: info.config_port,
        database_name: info.database_name ?? null,
      }
    })
  })

  return map
}

const confirmDebugConfigAndRun = async () => {
  if (!debugGlobalEnvId.value) {
    window.$message?.warning?.('请选择全局环境')
    return
  }
  const env_name = debugEnvIdToName.value.get(String(debugGlobalEnvId.value)) || null
  if (!env_name) {
    window.$message?.warning?.('全局环境无效，请重新选择')
    return
  }

  // 校验：已选择环境 + 配置名但无法解析到 host/port（或 DB 缺数据库名）时，阻止调试
  const missing = []
  const checkRow = (row, type) => {
        const cfgName = type === 'api' ? row.request_config_name : row.config_name
        const envId = getEffectiveEnvIdForRow(row)
        if (!envId) return
        if (!cfgName || !String(cfgName).trim()) {
          missing.push({ type, project_id: row.project_id, name: '(未选择配置名)' })
          return
        }
        const bucket = getBucket({ ...row, env_id: envId }, type === 'db' ? 'database' : type)
        const info = bucket?.[cfgName]
        if (!info || !info.config_host) {
          missing.push({ type, project_id: row.project_id, name: String(cfgName) })
          return
        }
        if (type === 'db') {
          const dbName = row.database_name || info.database_name
          if (!dbName || !String(dbName).trim()) {
            missing.push({ type, project_id: row.project_id, name: `${String(cfgName)}(缺数据库名)` })
          }
        }
      }
  ;(debugRows.value.apiRows || []).forEach((r) => checkRow(r, 'api'))
  ;(debugRows.value.dbRows || []).forEach((r) => checkRow(r, 'db'))
  ;(debugRows.value.fileRows || []).forEach((r) => checkRow(r, 'file'))

  if (missing.length) {
    const sample = missing.slice(0, 6).map((x) => `${x.type.toUpperCase()}·${x.name}`).join('，')
    window.$message?.error?.(`存在配置缺失（共${missing.length}条），请补全后再调试：${sample}${missing.length > 6 ? '…' : ''}`)
    return
  }

  applyDebugConfigToSteps()
  debugConfigModalVisible.value = false
  const step_exec_config_map = buildStepExecConfigMap(env_name)
  await doDebug(env_name, step_exec_config_map)
}

// 弹窗 footer 统一入口：根据当前模式分发到「执行」或「调试」
const confirmExecConfigAndAction = async () => {
  if (execConfigMode.value === 'run') {
    await confirmRunConfigAndExecute()
  } else {
    await confirmDebugConfigAndRun()
  }
}

const confirmRunConfigAndExecute = async () => {
  if (!debugGlobalEnvId.value) {
    window.$message?.warning?.('请选择全局环境')
    return
  }
  const env_name = debugEnvIdToName.value.get(String(debugGlobalEnvId.value)) || null
  if (!env_name) {
    window.$message?.warning?.('全局环境无效，请重新选择')
    return
  }

  // 复用同一套「缺失配置」校验逻辑
  const missing = []
  const checkRow = (row, type) => {
        const cfgName = type === 'api' ? row.request_config_name : row.config_name
        const envId = getEffectiveEnvIdForRow(row)
        if (!envId) return
        if (!cfgName || !String(cfgName).trim()) {
          missing.push({ type, project_id: row.project_id, name: '(未选择配置名)' })
          return
        }
        const bucket = getBucket({ ...row, env_id: envId }, type === 'db' ? 'database' : type)
        const info = bucket?.[cfgName]
        if (!info || !info.config_host) {
          missing.push({ type, project_id: row.project_id, name: String(cfgName) })
          return
        }
        if (type === 'db') {
          const dbName = row.database_name || info.database_name
          if (!dbName || !String(dbName).trim()) {
            missing.push({ type, project_id: row.project_id, name: `${String(cfgName)}(缺数据库名)` })
          }
        }
      }
  ;(debugRows.value.apiRows || []).forEach((r) => checkRow(r, 'api'))
  ;(debugRows.value.dbRows || []).forEach((r) => checkRow(r, 'db'))
  ;(debugRows.value.fileRows || []).forEach((r) => checkRow(r, 'file'))

  if (missing.length) {
    const sample = missing.slice(0, 6).map((x) => `${x.type.toUpperCase()}·${x.name}`).join('，')
    window.$message?.error?.(`存在配置缺失（共${missing.length}条），请补全后再执行：${sample}${missing.length > 6 ? '…' : ''}`)
    return
  }

  debugConfigModalVisible.value = false
  const step_exec_config_map = buildStepExecConfigMap(env_name)
  await doExecuteFromSavedTree(env_name, step_exec_config_map)
}

const doExecuteFromSavedTree = async (env_name, step_exec_config_map = null) => {
  const source = Array.isArray(execSourceSteps.value) ? execSourceSteps.value : []
  if (!source.length) {
    window.$message?.warning?.('暂无已保存的步骤树可执行，请先保存后再执行')
    return
  }
  runLoading.value = true
  try {
    const stepNoMap = assignStepNumbers(source)
    const backendSteps = source.map((step) => convertStepToBackend(step, null, stepNoMap))
    const res = await api.executeStepTree({
      case_id: caseId.value ? Number(caseId.value) : null,
      steps: backendSteps,
      initial_variables: [],
      env_name,
      steps_execute_config: step_exec_config_map || undefined
    })
    if (res?.code === 200 || res?.code === 0 || res?.code === '000000') {
      window.$message?.success?.(res?.message || '执行成功')
    } else {
      window.$message?.error?.(res?.message || '执行失败')
    }
  } catch (error) {
    console.error('Failed to execute step tree', error)
    window.$message?.error?.(error?.message || '执行失败')
  } finally {
    runLoading.value = false
  }
}

const doDebug = async (env_name, step_exec_config_map = null) => {
  debugLoading.value = true
  try {
    const stepNoMap = assignStepNumbers(steps.value)
    const backendSteps = steps.value.map((step) => convertStepToBackend(step, null, stepNoMap))
    const res = await api.executeStepTree({
      case_id: caseId.value ? Number(caseId.value) : null,
      steps: backendSteps,
      initial_variables: [],
      env_name,
      steps_execute_config: step_exec_config_map || undefined
    })
    if (res?.code === '000000') {
      const msg = res.message
      window.$message?.success?.(msg)
    } else {
      window.$message?.error?.(res?.message || '调试失败')
    }
  } catch (error) {
    console.error('Failed to debug step tree', error)
    window.$message?.error?.(error?.message || '调试失败')
  } finally {
    debugLoading.value = false
  }
}

const loadSteps = async () => {
  stepExpandStates.value = new Map()
  stashedQuoteStepsWhenPublic.value = []
  if (!caseId.value && !caseCode.value) {
    // 检查是否为复制进入：case_info 含 is_copy 和 steps
    const caseInfoStr = route.query.case_info
    if (caseInfoStr) {
      try {
        const caseInfo = JSON.parse(caseInfoStr)
        if (loadStepsFromCopy(caseInfo)) return
      } catch (_) {}
    }
    steps.value = []
    selectedKeys.value = []
    hydrateCaseInfo([])
    return
  }
  // 缓存：切换页签时使用缓存，不重复请求；从用例管理「编辑」新建页签时需请求
  const cached = autotestStore.getStepTreeCache(caseId.value, caseCode.value)
  if (cached) {
    hydrateCaseInfo(cached.rawData)
    steps.value = JSON.parse(JSON.stringify(cached.steps)).filter(Boolean)
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
    quoteStepsMap.value = {}
    fillQuoteStepsMapFromRawData(cached.rawData, steps.value)
    return
  }
  try {
    const params = {}
    if (caseId.value) params.case_id = caseId.value
    if (caseCode.value) params.case_code = caseCode.value
    const res = await api.getAutoTestStepTree(params)
    const data = Array.isArray(res?.data) ? res.data : []
    hydrateCaseInfo(data)
    const mappedSteps = data.map(mapBackendStep).filter(Boolean)
    steps.value = mappedSteps
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
    loadQuoteStepsForAllQuoteSteps()
    autotestStore.setStepTreeCache(caseId.value, caseCode.value, { rawData: data, steps: mappedSteps })
  } catch (error) {
    console.error('Failed to load step tree', error)
    steps.value = []
    selectedKeys.value = []
    hydrateCaseInfo([])
    quoteStepsMap.value = {}
  }
}

const handleSelect = (keys) => {
  selectedKeys.value = keys
}

const currentStep = computed(() => {
  const key = selectedKeys.value?.[0]
  if (!key) return null
  const quoteInner = getQuoteInnerStep(key)
  if (quoteInner) return quoteInner
  return findStep(key)
})

const editorComponent = computed(() => {
  const step = currentStep.value
  if (!step) return null
  return editorMap[step.type] || null
})

const insertStep = (parentId, type, index = null, extraConfig = null) => {
  const def = stepDefinitions[type]
  if (!def) return null

  const defaultConfig = type === 'loop'
      ? {loop_mode: '次数循环', loop_on_error: '中断循环', loop_maximums: 5}
      : type === 'wait'
          ? {seconds: 2}
          : type === 'user_variables'
              ? {step_name: '用户定义变量'}
              : type === 'quote'
                  ? {quote_case_id: null, step_name: '引用公共脚本'}
                  : type === 'database'
                      ? {
                        step_name: '数据库请求',
                        step_desc: '',
                        database_searched: false,
                        database_operates: [],
                        extract_variables: [],
                        assert_validators: []
                      }
                      : {}
  const defaultName = type === 'loop'
      ? '循环结构(次数循环)'
      : type === 'wait'
          ? '控制等待(2秒)'
          : type === 'user_variables'
              ? '用户定义变量'
              : type === 'database'
                  ? '数据库请求'
                  : type === 'quote' && extraConfig?.step_name
                      ? extraConfig.step_name
                      : `${def.label}`
  const config = extraConfig ? {...defaultConfig, ...extraConfig} : defaultConfig
  const newStep = {
    id: genId(),
    type,
    name: type === 'quote' && config.step_name ? config.step_name : defaultName,
    config
  }
  if (type === 'quote') {
    newStep.original = {
      quote_case_id: newStep.config.quote_case_id ?? null,
      step_name: newStep.config.step_name || newStep.name,
      step_code: null,
      id: null
    }
  }

  // 只有 loop/if 类型才有 children 字段（即使是空数组）
  if (def.allowChildren) {
    newStep.children = []
    // 如果新步骤允许有子步骤，初始化展开状态为true
    stepExpandStates.value.set(newStep.id, true)
  }
  // 非 loop/if 类型不设置 children 字段

  if (!parentId) {
    // 添加到根级别
    if (index !== null) {
      steps.value.splice(index, 0, newStep)
    } else {
      steps.value.push(newStep)
    }
    return newStep
  }
  // 添加到父步骤的子级
  const parent = findStep(parentId)
  if (parent && stepDefinitions[parent.type]?.allowChildren) {
    // 父步骤允许有子步骤，添加到其children中
    parent.children = parent.children || []
    if (index !== null) {
      parent.children.splice(index, 0, newStep)
    } else {
      parent.children.push(newStep)
    }
    return newStep
  }
  return null
}

const handleAddStep = (type, parentId) => {
  if (type === 'quote_public_script') {
    scriptDrawerMode.value = 'quote'
    quotePublicScriptParentId.value = parentId
    quotePublicScriptReplaceStepId.value = null
    quotePublicScriptQueryItems.value.case_type = '公共脚本'
    quotePublicScriptDrawerVisible.value = true
    return
  }
  // 【复制指定脚本】打开抽屉：多选脚本，确定复制后调用 copyCaseStepTree 获取 steps 并插入当前步骤树
  if (type === 'copy_steps') {
    scriptDrawerMode.value = 'copy'
    quotePublicScriptParentId.value = parentId
    quotePublicScriptReplaceStepId.value = null
    selectedForCopy.value = []
    quotePublicScriptQueryItems.value.case_type = ''
    quotePublicScriptDrawerVisible.value = true
    return
  }
  const created = insertStep(parentId, type)
  if (created) {
    selectedKeys.value = [created.id]
    updateStepDisplayNames()
  }
}

const removeStep = (id, list = steps.value) => {
  const idx = list.findIndex(item => item.id === id)
  if (idx !== -1) {
    list.splice(idx, 1)
    return true
  }
  for (const item of list) {
    if (item.children && item.children.length) {
      const removed = removeStep(id, item.children)
      if (removed) return true
    }
  }
  return false
}

const handleDeleteStep = (id) => {
  // 清理被删除步骤及其子步骤的展开状态
  const step = findStep(id)
  if (step) {
    const cleanupExpandStates = (stepId) => {
      stepExpandStates.value.delete(stepId)
      const stepToClean = findStep(stepId)
      if (stepToClean?.children) {
        stepToClean.children.forEach(child => cleanupExpandStates(child.id))
      }
    }
    cleanupExpandStates(id)
  }

  removeStep(id)
  if (selectedKeys.value[0] === id) {
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  }
}

/** 当用例类型改为「公共脚本」时，移除步骤树中所有「引用公共脚本」步骤，防止循环引用。返回被移除的步骤数量。 */
const removeAllQuoteSteps = () => {
  const quoteIds = []
  forEachStep(steps.value, (step) => {
    if (step.type === 'quote' || step.type === 'quote_public_script') {
      quoteIds.push(step.id)
    }
  })
  if (quoteIds.length === 0) return 0
  quoteIds.forEach((id) => {
    const step = findStep(id)
    if (step) {
      stepExpandStates.value.delete(id)
      removeStep(id)
    }
  })
  quoteIds.forEach((id) => {
    quoteStepsMap.value = { ...quoteStepsMap.value, [id]: [] }
  })
  if (quoteIds.includes(selectedKeys.value?.[0])) {
    selectedKeys.value = [steps.value[0]?.id].filter(Boolean)
  }
  updateStepDisplayNames()
  return quoteIds.length
}

/** 收集所有「引用公共脚本」步骤及其位置（用于暂存，切回用户脚本时可恢复） */
const collectQuoteStepsWithPosition = () => {
  const list = []
  forEachStep(steps.value, (step) => {
    if (step.type !== 'quote' && step.type !== 'quote_public_script') return
    const parent = findStepParent(step.id)
    const parentId = parent?.id ?? null
    const siblings = parentId === null ? steps.value : (parent?.children || [])
    const index = siblings.findIndex((s) => s.id === step.id)
    if (index === -1) return
    list.push({
      step: JSON.parse(JSON.stringify(step)),
      parentId,
      index
    })
  })
  return list
}

/** 将暂存的引用步骤恢复回步骤树 */
const restoreStashedQuoteSteps = () => {
  const stashed = stashedQuoteStepsWhenPublic.value
  if (!stashed || stashed.length === 0) return 0
  const sorted = [...stashed].sort((a, b) => {
    const pa = a.parentId ?? ''
    const pb = b.parentId ?? ''
    if (pa !== pb) return String(pa).localeCompare(String(pb))
    return a.index - b.index
  })
  for (const { step, parentId, index } of sorted) {
    const list = parentId === null ? steps.value : (findStep(parentId)?.children || null)
    if (!list) continue
    const safeIndex = Math.min(index, list.length)
    list.splice(safeIndex, 0, step)
  }
  stashedQuoteStepsWhenPublic.value = []
  updateStepDisplayNames()
  loadQuoteStepsForAllQuoteSteps()
  return sorted.length
}

/** 条件分支 / 循环结构在步骤树上的固定展示名（与 updateStepConfig 规则一致）；其它类型返回 null */
const getFixedBranchStepDisplayName = (step) => {
  if (!step?.type) return null
  if (step.type === 'if') {
    return '条件分支(根据判断结果, 执行不同的路径)'
  }
  if (step.type === 'loop') {
    const mode = (step.config && step.config.loop_mode) || '次数循环'
    if (mode === '次数循环') return '循环结构(次数循环)'
    if (mode === '列表循环') return '循环结构(列表循环)'
    if (mode === '字典循环') return '循环结构(字典循环)'
    if (mode === '条件循环') return '循环结构-(条件循环)'
    return '循环结构'
  }
  return null
}

/** 与 convertStepToBackend 写入后端的 step_name 一致，用于保存前校验重复 */
const getStepNameAsWillPersist = (step) => {
  const original = step.original || {}
  const config = step.config || {}
  const fixed = getFixedBranchStepDisplayName(step)
  if (fixed) return String(fixed).trim()

  if (step.type === 'user_variables') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || '')
    return String(v ?? '').trim()
  }
  if (step.type === 'quote' || step.type === 'quote_public_script') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '引用公共脚本')
    return String(v ?? '').trim()
  }
  if (step.type === 'database') {
    const v = config.step_name !== undefined ? config.step_name : (original.step_name || step.name || '')
    return String(v ?? '').trim()
  }

  return String(step.name || original.step_name || '').trim()
}

/** 编辑器已向 config 写入 step_name 且用户清空时视为未填写（HTTP/TCP/代码等） */
const isStepNameExplicitlyEmptyInEditor = (step) => {
  const config = step.config || {}
  if (!Object.prototype.hasOwnProperty.call(config, 'step_name')) return false
  return String(config.step_name ?? '').trim() === ''
}

/** 步骤名称必填；除 loop / if 外全局不可重复（前序遍历） */
const validateStepNamesInSteps = (stepList) => {
  const usedNames = new Map()

  const walk = (list) => {
    if (!Array.isArray(list)) return {valid: true}
    for (const step of list) {
      const typeLabel = stepDefinitions[step.type]?.label
          || (step.type === 'quote_public_script' ? '引用公共脚本' : (step.type || '步骤'))

      if (isStepNameExplicitlyEmptyInEditor(step)) {
        return {
          valid: false,
          message: `「${typeLabel}」步骤的步骤名称不能为空，请填写后再保存。`
        }
      }

      const name = getStepNameAsWillPersist(step)
      if (!name) {
        return {
          valid: false,
          message: `「${typeLabel}」步骤的步骤名称不能为空，请填写后再保存。`
        }
      }

      const exemptDuplicate = step.type === 'loop' || step.type === 'if'
      if (!exemptDuplicate) {
        if (usedNames.has(name)) {
          return {
            valid: false,
            message: `步骤名称「${name}」重复，除循环结构、条件分支外步骤名称不可重复，请修改后再保存。`
          }
        }
        usedNames.set(name, true)
      }
      if (step.children && step.children.length > 0) {
        const child = walk(step.children)
        if (!child.valid) return child
      }
    }
    return {valid: true}
  }

  return walk(stepList)
}

const handleCopyStep = (id) => {
  const step = findStep(id)
  if (!step) return
  const copiedStep = JSON.parse(JSON.stringify(step))
  copiedStep.id = genId()
  const fixedName = getFixedBranchStepDisplayName(copiedStep)
  copiedStep.name = fixedName ?? `${copiedStep.name}(copy)`

  // 复制的步骤是新增的，需要删除 original 中的 id 和 step_code
  // 这样 convertStepToBackend 会将其识别为新增步骤
  if (copiedStep.original) {
    delete copiedStep.original.id
    delete copiedStep.original.step_code
    // 保留其他 original 字段（如 case_id, step_type 等），但清除标识字段
  }

  // 确保结构规范：非 loop/if 类型不应该有 children 字段
  const def = stepDefinitions[copiedStep.type]
  if (def && !def.allowChildren && copiedStep.children !== undefined) {
    // 删除不应该存在的 children 字段
    delete copiedStep.children
  } else if (def && def.allowChildren && !copiedStep.children) {
    // 确保 loop/if 类型有 children 字段（即使是空数组）
    copiedStep.children = []
  }

  // 递归更新子步骤ID，并确保子步骤结构规范，同时删除子步骤的 original.id 和 original.step_code
  const updateIds = (node) => {
    node.id = genId()
    // 删除子步骤的 original.id 和 original.step_code（复制的子步骤也是新增的）
    if (node.original) {
      delete node.original.id
      delete node.original.step_code
    }
    const nodeDef = stepDefinitions[node.type]
    // 确保每个子步骤的结构规范
    if (nodeDef && !nodeDef.allowChildren && node.children !== undefined) {
      delete node.children
    } else if (nodeDef && nodeDef.allowChildren && !node.children) {
      node.children = []
    }
    if (node.children && node.children.length) {
      node.children.forEach(updateIds)
    }
  }
  updateIds(copiedStep)

  // 如果复制的步骤允许有子步骤，初始化展开状态
  if (def && def.allowChildren) {
    stepExpandStates.value.set(copiedStep.id, true)
  }

  const parent = findStepParent(id)
  if (parent) {
    const parentStep = findStep(parent.id)
    if (parentStep && parentStep.children) {
      const index = parentStep.children.findIndex(s => s.id === id)
      parentStep.children.splice(index + 1, 0, copiedStep)
    }
  } else {
    const index = steps.value.findIndex(s => s.id === id)
    steps.value.splice(index + 1, 0, copiedStep)
  }
  selectedKeys.value = [copiedStep.id]
}

const updateStepConfig = (id, config) => {
  const step = findStep(id)
  if (step) {
    step.config = {...step.config, ...config}
    // 根据配置更新步骤名称
    const branchFixed = getFixedBranchStepDisplayName(step)
    if (branchFixed) {
      step.name = branchFixed
    } else if (step.type === 'http') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined && config.step_name.length > 0) {
        step.name = String(config.step_name).trim() || 'HTTP请求(发送请求并验证响应数据)'
      } else {
        // 否则自动生成步骤名称
        step.name = `HTTP请求(发送请求并验证响应数据)`
      }
    } else if (step.type === 'tcp') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || 'TCP请求'
      }
    } else if (step.type === 'wait') {
      step.name = `控制等待(${config.seconds ?? 2}秒)`
    } else if (step.type === 'user_variables') {
      // 用户变量：步骤名称必填，修改时同步到步骤树（与等待控制一致）
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '用户定义变量'
      }
    } else if (step.type === 'code') {
      // 如果提供了 step_name，使用用户输入的步骤名称
      if (config.step_name !== undefined) {
        step.name = String(config.step_name).trim() || '代码请求(Python)'
      }
    } else if (step.type === 'database') {
      if (config.step_name !== undefined && String(config.step_name).trim()) {
        step.name = String(config.step_name).trim()
      } else if (!String(step.name || '').trim()) {
        step.name = '数据库请求'
      }
    } else if (step.type === 'quote' || step.type === 'quote_public_script') {
      if (config.step_name !== undefined && config.step_name !== null) {
        step.name = String(config.step_name).trim() || '引用公共脚本'
      }
    }
    // 更新显示名称
    updateStepDisplayNames()
  }
}

const getStepIcon = (type) => {
  return stepDefinitions[type]?.icon || 'material-symbols:code'
}

const getStepIconClass = (type) => {
  const classMap = {
    loop: 'icon-loop',
    code: 'icon-code',
    tcp: 'icon-tcp',
    http: 'icon-http',
    if: 'icon-if',
    wait: 'icon-wait',
    database: 'icon-database',
    user_variables: 'icon-user_variables',
    quote: 'icon-quote',
    quote_public_script: 'icon-quote',
  }
  return classMap[type] || ''
}

// 拖拽相关
const handleDragStart = (event, stepId, parentId, index) => {
  dragState.value.draggingId = stepId
  dragState.value.dragOverParent = parentId
  dragState.value.dragOverIndex = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', stepId)
}

const handleDragOver = (event, targetId, targetParentId) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  // 如果正在拖拽，检查目标步骤是否为 if/loop 类型
  if (dragState.value.draggingId && targetId) {
    const targetStep = findStep(targetId)
    if (targetStep && stepDefinitions[targetStep.type]?.allowChildren) {
      // 如果是 if 或 loop 类型，设置 dragOverId 用于焦点高亮
      dragState.value.dragOverId = targetId
      dragState.value.dragOverParent = targetParentId
    }
  }
}

// 处理在 if/loop 步骤的子步骤区域内的拖拽
const handleDragOverInChildrenArea = (event, parentId) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  if (!dragState.value.draggingId || !parentId) {
    return
  }

  const parentStep = findStep(parentId)
  if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) {
    return
  }

  // 设置焦点高亮
  dragState.value.dragOverId = parentId
  dragState.value.dragOverParent = parentId

  // 如果子步骤区域为空，设置插入位置为第一个位置
  if (!parentStep.children || parentStep.children.length === 0) {
    dragState.value.insertTargetId = null
    dragState.value.insertPosition = 'before'
    dragState.value.dragOverIndex = 0
    return
  }

  // 如果子步骤区域不为空，让子步骤的 dragover 事件来处理
  // 这里不做任何处理，让事件继续传播到子步骤
}

const handleDragLeaveInChildrenArea = (event, parentId) => {
  // 当离开子步骤区域时，清除插入位置指示器
  if (dragState.value.dragOverId === parentId) {
    setTimeout(() => {
      // 检查是否真的离开了该区域
      if (dragState.value.dragOverId === parentId) {
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
        dragState.value.dragOverIndex = null
      }
    }, 50)
  }
}

// 处理在子步骤上的拖拽
const handleDragOverOnChild = (event, childId, parentId, childIndex) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'

  if (!dragState.value.draggingId || !parentId) {
    return
  }

  const parentStep = findStep(parentId)
  if (!parentStep || !stepDefinitions[parentStep.type]?.allowChildren) {
    return
  }

  // 设置焦点高亮
  dragState.value.dragOverId = parentId
  dragState.value.dragOverParent = parentId

  // 计算鼠标在子步骤中的相对位置，判断是插入到之前还是之后
  const rect = event.currentTarget.getBoundingClientRect()
  const mouseY = event.clientY
  const stepCenterY = rect.top + rect.height / 2

  // 如果鼠标在步骤的上半部分，插入到之前；否则插入到之后
  const position = mouseY < stepCenterY ? 'before' : 'after'

  dragState.value.insertTargetId = childId
  dragState.value.insertPosition = position
  dragState.value.dragOverIndex = position === 'before' ? childIndex : childIndex + 1
}

const handleDragLeaveOnChild = (event, childId) => {
  // 当离开子步骤时，清除插入位置指示器（延迟清除，避免快速移动时闪烁）
  if (dragState.value.insertTargetId === childId) {
    setTimeout(() => {
      if (dragState.value.insertTargetId === childId) {
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
      }
    }, 3000)
  }
}

const handleDragLeave = (event, targetId) => {
  // 当离开拖拽目标时，清除焦点高亮（延迟清除，避免快速移动时闪烁）
  if (dragState.value.dragOverId === targetId) {
    // 使用 setTimeout 延迟清除，避免在移动到子元素时误清除
    setTimeout(() => {
      if (dragState.value.dragOverId === targetId) {
        dragState.value.dragOverId = null
        dragState.value.insertTargetId = null
        dragState.value.insertPosition = null
        dragState.value.dragOverIndex = null
      }
    }, 50)
  }
}

const handleDrop = (event, targetId, targetParentId, targetIndex) => {
  event.preventDefault()
  const draggingId = dragState.value.draggingId
  if (!draggingId || draggingId === targetId) {
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  const draggingStep = findStep(draggingId)
  if (!draggingStep) {
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  // 从原位置移除
  const removeFromList = (list, id) => {
    const idx = list.findIndex(item => item.id === id)
    if (idx !== -1) {
      list.splice(idx, 1)
      return true
    }
    for (const item of list) {
      if (item.children && item.children.length) {
        if (removeFromList(item.children, id)) return true
      }
    }
    return false
  }
  removeFromList(steps.value, draggingId)

  // 如果 dragOverId 存在且是 if/loop 类型，说明是拖拽到 if/loop 步骤的子步骤区域
  if (dragState.value.dragOverId) {
    const parentStep = findStep(dragState.value.dragOverId)
    if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
      // 确保 children 数组存在
      if (!parentStep.children) {
        parentStep.children = []
      }

      // 使用 dragState 中的插入位置信息
      const insertIndex = dragState.value.dragOverIndex !== null ? dragState.value.dragOverIndex : parentStep.children.length
      parentStep.children.splice(insertIndex, 0, draggingStep)
      dragState.value = {
        draggingId: null,
        dragOverId: null,
        dragOverParent: null,
        dragOverIndex: null,
        insertPosition: null,
        insertTargetId: null
      }
      return
    }
  }

  // 原有的拖拽逻辑：拖拽到其他步骤的位置
  const targetStep = findStep(targetId)
  // 如果目标是 if/loop 类型且允许子步骤，且是拖拽到步骤本身的空区域（targetId === targetParentId）
  if (targetStep && stepDefinitions[targetStep.type]?.allowChildren && targetId === targetParentId) {
    // 确保 children 数组存在
    if (!targetStep.children) {
      targetStep.children = []
    }
    // 添加到目标步骤的 children 中
    targetStep.children.push(draggingStep)
    dragState.value = {
      draggingId: null,
      dragOverId: null,
      dragOverParent: null,
      dragOverIndex: null,
      insertPosition: null,
      insertTargetId: null
    }
    return
  }

  // 如果 targetParentId 是 if/loop 类型，说明是拖拽到 if/loop 步骤的子步骤位置
  if (targetParentId) {
    const parentStep = findStep(targetParentId)
    if (parentStep && stepDefinitions[parentStep.type]?.allowChildren) {
      // 确保 children 数组存在
      if (!parentStep.children) {
        parentStep.children = []
      }
      // 插入到指定位置
      const insertIndex = targetIndex !== null ? targetIndex : parentStep.children.length
      parentStep.children.splice(insertIndex, 0, draggingStep)
      dragState.value = {
        draggingId: null,
        dragOverId: null,
        dragOverParent: null,
        dragOverIndex: null,
        insertPosition: null,
        insertTargetId: null
      }
      return
    }
  }

  // 插入到新位置（根级别）
  const insertIndex = targetIndex !== null ? targetIndex : steps.value.length
  steps.value.splice(insertIndex, 0, draggingStep)
  dragState.value = {
    draggingId: null,
    dragOverId: null,
    dragOverParent: null,
    dragOverIndex: null,
    insertPosition: null,
    insertTargetId: null
  }
}

// 计算步骤编号（按深度优先遍历）
const stepNumberMap = computed(() => {
  const map = new Map()
  let counter = 0

  const traverse = (list) => {
    for (const step of list) {
      counter++
      map.set(step.id, counter)
      if (step.children && step.children.length) {
        traverse(step.children)
      }
    }
  }

  traverse(steps.value)
  return map
})

const getStepNumber = (stepId) => {
  return stepNumberMap.value.get(stepId) || 0
}

// 存储每个步骤的显示名称（用于中间省略）
const stepDisplayNames = ref(new Map())

// 计算文本中间省略（保留开头和结尾）
const truncateTextMiddle = (text, maxChars = 20) => {
  if (!text || text.length <= maxChars) return text
  // 计算开头和结尾的长度（为省略号留出空间）
  const halfLen = Math.floor((maxChars - 3) / 2)
  const start = text.substring(0, halfLen)
  const end = text.substring(text.length - halfLen)
  return `${start}...${end}`
}

// 获取步骤显示名称（中间省略）
const getStepDisplayName = (name, stepId) => {
  if (!name) return ''
  // 如果已经计算过，返回计算后的名称
  if (stepDisplayNames.value.has(stepId)) {
    return stepDisplayNames.value.get(stepId)
  }
  // 如果还没有计算过，先进行简单处理
  const maxDisplayLength = 22
  if (name.length > maxDisplayLength) {
    return truncateTextMiddle(name, maxDisplayLength)
  }
  return name
}

// 更新步骤显示名称（根据容器宽度动态计算）
const updateStepDisplayNames = () => {
  nextTick(() => {
    const nameMap = new Map()
    // 考虑到操作按钮的宽度（步骤编号 + 复制 + 删除按钮），设置合理的文本长度限制
    // 操作按钮大约需要 80-100px，文本区域大约可以显示 20-25 个字符
    const maxDisplayLength = 22

    const updateNames = (list) => {
      for (const step of list) {
        const stepName = step.name || ''
        // 根据步骤名称长度决定是否需要中间省略
        if (stepName.length > maxDisplayLength) {
          nameMap.set(step.id, truncateTextMiddle(stepName, maxDisplayLength))
        } else {
          nameMap.set(step.id, stepName)
        }
        if (step.children && step.children.length) {
          updateNames(step.children)
        }
      }
    }
    updateNames(steps.value)
    stepDisplayNames.value = nameMap
  })
}

// 监听steps变化，更新显示名称和展开状态
watch(() => steps.value, () => {
  updateStepDisplayNames()
  initializeStepExpandStates()
}, {deep: true})

// 同页切换用例（仅 query 变化、组件未销毁）时需重新解析 case_info 并拉步骤树
watch([() => caseId.value, () => caseCode.value], () => {
  initCaseInfoFromRoute()
  loadSteps()
})

onMounted(async () => {
  loadProjects()
  // 用例表单与标签：initCaseInfoFromRoute + loadTags 已在 setup 中通过 watch(case_project, { immediate }) 处理，避免进入页时请求两次标签列表
  loadSteps()
  // 辅助函数列表（用于用户变量/关联数据）
  try {
    const res = await api.getAssistFuncList()
    const data = res?.data ?? res
    assistFunctionsList.value = Array.isArray(data) ? data : (data?.data ?? [])
  } catch (e) {
    console.warn('获取辅助函数列表失败', e)
    assistFunctionsList.value = []
  }
})

onUpdated(() => {
  // 组件更新后重新计算显示名称
  updateStepDisplayNames()
})

const renderDropdownLabel = (option) => {
  return h('div', {style: {display: 'flex', alignItems: 'center', gap: '8px'}}, [
    h('span', option.label)
  ])
}

// 递归子步骤组件
const RecursiveStepChildren = defineComponent({
  name: 'RecursiveStepChildren',
  props: {
    step: {
      type: Object,
      required: true
    },
    parentId: {
      type: String,
      default: null
    }
  },
  setup(props) {
    // 捕获所有需要的变量和函数，确保能够通过闭包访问
    const capturedStepDefinitions = stepDefinitions
    const capturedIsStepExpanded = isStepExpanded
    const capturedToggleStepExpand = toggleStepExpand
    const capturedSelectedKeys = selectedKeys
    const capturedGetStepIcon = getStepIcon
    const capturedGetStepIconClass = getStepIconClass
    const capturedGetStepDisplayName = getStepDisplayName
    const capturedGetStepNumber = getStepNumber
    const capturedHandleSelect = handleSelect
    const capturedHandleDragStart = handleDragStart
    const capturedHandleDragOver = handleDragOver
    const capturedHandleDragLeave = handleDragLeave
    const capturedHandleDragOverInChildrenArea = handleDragOverInChildrenArea
    const capturedHandleDragLeaveInChildrenArea = handleDragLeaveInChildrenArea
    const capturedHandleDragOverOnChild = handleDragOverOnChild
    const capturedHandleDragLeaveOnChild = handleDragLeaveOnChild
    const capturedHandleDrop = handleDrop
    const capturedHandleCopyStep = handleCopyStep
    const capturedHandleDeleteStep = handleDeleteStep
    const capturedAddOptions = addOptions
    const capturedRenderDropdownLabel = renderDropdownLabel
    const capturedHandleAddStep = handleAddStep
    const capturedDragState = dragState

    return () => {
      const {step, parentId} = props
      if (!capturedStepDefinitions[step.type]?.allowChildren) return null

      // 局部展开优先于全局状态：如果步骤被局部展开，就显示，不管全局状态如何
      const shouldShow = capturedIsStepExpanded(step.id)
      if (!shouldShow) return null

      return h('div', {
        onDragover: (e) => {
          e.preventDefault()
          e.stopPropagation()
          capturedHandleDragOverInChildrenArea(e, step.id)
        },
        onDragleave: (e) => {
          e.stopPropagation()
          capturedHandleDragLeaveInChildrenArea(e, step.id)
        }
      }, [
        // 无子女时显示空的拖拽区域
        (!step.children || step.children.length === 0) ? h('div', {
          class: ['step-drop-zone', {'is-drag-over': capturedDragState.value.dragOverId === step.id}],
          onDrop: (e) => {
            e.stopPropagation()
            capturedHandleDrop(e, step.id, step.id, 0)
          }
        }, [
          h('div', {
            class: 'step-drop-zone-hint'
          }, '拖拽步骤到这里')
        ]) : null,
        ...(step.children || []).map((child, childIndex) => [
          // 插入位置指示器：在子步骤之前
          h('div', {
            key: `indicator-before-${child.id}`,
            class: 'step-insert-indicator',
            style: {
              display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === child.id && capturedDragState.value.insertPosition === 'before' ? 'block' : 'none'
            }
          }),
          h('div', {
            key: child.id,
            class: [
              'step-item',
              {
                'is-selected': capturedSelectedKeys.value.includes(child.id),
                'is-drag-target': capturedDragState.value.draggingId && capturedStepDefinitions[child.type]?.allowChildren
              }
            ],
            draggable: true,
            onClick: (e) => {
              e.stopPropagation()
              capturedHandleSelect([child.id])
            },
            onDragstart: (e) => {
              e.stopPropagation()
              capturedHandleDragStart(e, child.id, step.id, childIndex)
            },
            onDragover: (e) => {
              e.preventDefault()
              e.stopPropagation()
              capturedHandleDragOverOnChild(e, child.id, step.id, childIndex)
            },
            onDragleave: (e) => {
              e.stopPropagation()
              capturedHandleDragLeaveOnChild(e, child.id)
            },
            onDrop: (e) => {
              e.stopPropagation()
              capturedHandleDrop(e, child.id, step.id, childIndex)
            }
          }, [
            h('div', {
              class: 'step-item-child'
            }, [
              h('span', {
                class: 'step-name',
                title: child.name
              }, [
                h(TheIcon, {
                  icon: capturedGetStepIcon(child.type),
                  size: 18,
                  class: ['step-icon', capturedGetStepIconClass(child.type)]
                }),
                h('span', {
                  class: 'step-name-text'
                }, capturedGetStepDisplayName(child.name, child.id)),
                h('span', {
                  class: 'step-actions'
                }, [
                  h('span', {
                    class: 'step-number'
                  }, `#${capturedGetStepNumber(child.id)}`),
                  capturedStepDefinitions[child.type]?.allowChildren ? h(NButton, {
                    text: true,
                    size: 'tiny',
                    class: 'action-btn',
                    onClick: (e) => {
                      e.stopPropagation()
                      capturedToggleStepExpand(child.id, e)
                    }
                  }, {
                    icon: () => h(TheIcon, {
                      icon: capturedIsStepExpanded(child.id) ? 'material-symbols:keyboard-arrow-up' : 'material-symbols:keyboard-arrow-down',
                      size: 16
                    })
                  }) : null,
                  h(NButton, {
                    text: true,
                    size: 'tiny',
                    class: 'action-btn',
                    title: '复制当前步骤',
                    onClick: (e) => {
                      e.stopPropagation()
                      capturedHandleCopyStep(child.id)
                    }
                  }, {
                    icon: () => h(TheIcon, {
                      icon: 'material-symbols:content-copy',
                      size: 16,
                    })
                  }),
                  h(NPopconfirm, {
                    onPositiveClick: () => capturedHandleDeleteStep(child.id),
                    onClick: (e) => e.stopPropagation()
                  }, {
                    trigger: () => h(NButton, {
                      text: true,
                      size: 'tiny',
                      type: 'error',
                      title: '删除当前步骤',
                      class: 'action-btn'
                    }, {
                      icon: () => h(TheIcon, {
                        icon: 'material-symbols:delete',
                        size: 14
                      })
                    }),
                    default: () => '确认删除该步骤?'
                  })
                ])
              ]),
              // 递归渲染子步骤（只有当子步骤允许有子步骤时才渲染）
              capturedStepDefinitions[child.type]?.allowChildren ? h(RecursiveStepChildren, {
                step: child,
                parentId: step.id
              }) : null
            ])
          ]),
          // 插入位置指示器：在子步骤之后
          h('div', {
            key: `indicator-after-${child.id}`,
            class: 'step-insert-indicator',
            style: {
              display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === child.id && capturedDragState.value.insertPosition === 'after' ? 'block' : 'none'
            }
          })
        ]).flat(),
        // 插入位置指示器：在最后一个子步骤之后
        h('div', {
          class: 'step-insert-indicator',
          style: {
            display: capturedDragState.value.draggingId && capturedDragState.value.dragOverId === step.id && capturedDragState.value.insertTargetId === null && capturedDragState.value.insertPosition === 'after' && step.children && step.children.length > 0 ? 'block' : 'none'
          }
        }),
        h('div', {
          class: 'step-add-btn'
        }, [
          h(NDropdown, {
            trigger: 'click',
            options: capturedAddOptions.value,
            renderLabel: capturedRenderDropdownLabel,
            onSelect: (key) => {
              capturedHandleAddStep(key, step.id)
            }
          }, {
            default: () => h(NButton, {
              dashed: true,
              size: 'small',
              class: 'add-step-btn',
              onClick: (e) => e.stopPropagation()
            }, {
              default: () => '添加步骤'
            })
          })
        ])
      ])
    }
  }
})
</script>

<style scoped>
/* 页面容器：限制最大高度为视口高度 */
.page-container {
  height: 100%;
  max-height: calc(100vh - 100px); /* 减去 AppPage 的 padding 和其他空间，可根据实际情况调整 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0; /* 允许容器缩小 */
}

.case-info-card {
  margin-bottom: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.case-info-form {
  width: 100%;
}
.exec-config-mode {
  display: flex;
  align-items: center;
  gap: 8px;
}
.case-info-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px 24px;
}

.case-field {
  min-width: 0;
}

.case-field :deep(.n-form-item) {
  width: 100%;
}

.case-field-full {
  grid-column: 1 / -1;
}

.case-field-full.case-field-buttons {
  display: flex;
  justify-content: flex-end;
}

.case-field-input {
  width: 100%;
  transition: border-color 0.3s ease;
}

.case-field-input:hover {
  border-color: #F4511E;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .case-info-fields {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}

@media (min-width: 1200px) {
  .case-info-fields {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/* Grid 容器：使用 flex 布局，占满可用高度 */
.grid-container {
  height: 100%;
  flex: 1;
  min-height: 0; /* 重要：允许 flex 子元素缩小 */
}

/* 确保 n-grid 内部元素正确布局 */
.grid-container :deep(.n-grid) {
  height: 100%;
}

.grid-container :deep(.n-grid-item) {
  height: 100%;
}

/* 左侧列：使用 flex 布局 */
.left-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 右侧列：使用 flex 布局 */
.right-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 步骤卡片：使用 flex 布局，占满可用高度 */
.step-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

/* 步骤卡片 header：固定不滚动 */
.step-card :deep(.n-card__header) {
  flex-shrink: 0;
}

/* 步骤卡片内容区域：可滚动 */
.step-card :deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

/* 配置卡片：使用 flex 布局，占满可用高度 */
.config-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

/* 配置卡片内容区域：允许滚动 */
.config-card :deep(.n-card__content) {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
}

/* 步骤树容器：固定高度，超出时滚动 */
.step-tree-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0; /* 重要：允许 flex 子元素缩小 */
  padding: 8px 0;
}

/* -----------------------------
 * 调试：脚本执行配置弹窗（对齐项目主题色，避免使用截图中的纯蓝）
 * ----------------------------- */
.exec-config-toolbar-row {
  margin-bottom: 12px;
}

.exec-config-toolbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.exec-config-toolbar-inner :deep(.n-switch) {
  flex-shrink: 0;
}

.exec-config-main-card {
  margin-top: 0;
}

.exec-config-main-card :deep(.n-card-header) {
  align-items: center;
}

.exec-config-dataset-card {
  margin-top: 12px;
}

.exec-config-dataset-card :deep(.n-card-header) {
  align-items: center;
}

.exec-config-modal,
.exec-config-dataset-wrap {
  /* 原 min-height 620px / max-height 80vh 整体缩减 20% */
  min-height: calc(620px * 0.8);
  max-height: calc(80vh * 0.8);
}

.exec-config-dataset-wrap {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.exec-config-dataset-table {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--n-color);
}

.exec-config-dataset-header {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 0;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-2);
  background: var(--n-color-modal);
  border-bottom: 1px solid var(--n-border-color);
}

.exec-config-dataset-header .col,
.exec-config-dataset-row .col {
  min-width: 0;
}

.exec-config-dataset-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  padding: 24px 16px;
}

.exec-config-dataset-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.exec-config-dataset-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  padding: 10px 12px;
  font-size: 13px;
  border-bottom: 1px solid var(--n-border-color);
}

.exec-config-dataset-row:last-child {
  border-bottom: none;
}

.exec-config-dataset-footer {
  flex-shrink: 0;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--n-border-color);
  text-align: right;
  font-size: 13px;
  color: var(--n-text-color-2);
}

.exec-config-modal {
  display: flex;
  overflow: hidden;
}

.exec-config-left {
  width: 200px;
  flex: 0 0 200px;
  border-right: 2px solid var(--n-border-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 左侧标题区（合并原 left-header + left-title，减少一层 div） */
.exec-config-left-head {
  flex-shrink: 0;
  padding: 12px 12px 8px;
  font-size: 14px;
  font-weight: 600;
}

.exec-config-app-list {
  padding: 8px;
  overflow-y: auto;
  min-height: 0;
}

.exec-config-app-item {
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  border: 1px solid transparent;
  background: var(--n-color);
  transition: all 0.15s ease;
  margin-bottom: 8px;
}

.exec-config-app-item:hover {
  background: var(--n-color-hover);
}

.exec-config-app-item.is-active {
  border-color: #F45E11;
  background: color-mix(in srgb, var(--n-primary-color) 10%, var(--n-color) 90%);
}

.exec-config-app-name {
  font-size: 14px;
  font-weight: 600;
}

.exec-config-app-count {
  margin-top: 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.exec-config-empty {
  color: var(--n-text-color-3);
  padding: 16px 12px;
  font-size: 13px;
}

.exec-config-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 0 0 14px;
}

.exec-config-global-env-label {
  color: var(--n-text-color-2);
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
}

.exec-config-section {
  margin-top: 12px;
}

.exec-config-section + .exec-config-section {
  margin-top: 16px;
}

.exec-config-section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 800;
  font-size: 16px;
  color: var(--n-text-color);
}

.exec-config-table {
  border: 1px solid var(--n-border-color);
  border-radius: 10px;
  overflow: hidden;
}

.exec-config-table-header,
.exec-config-table-row {
  display: grid;
  /*
   * 与 5% / 15% / 30% / 50% 同比例；使用 fr 而非 %，避免「列宽总和 100% + gap」超出容器导致 IP/端口列溢出。
   */
  grid-template-columns: 5fr 15fr 30fr 50fr;
  gap: 8px;
  align-items: center;
  padding: 10px 10px;
}

.exec-config-table.is-db .exec-config-table-header,
.exec-config-table.is-db .exec-config-table-row {
  /* 与 5% / 15% / 30% / 20% / 30% 同比例 */
  grid-template-columns: 5fr 15fr 30fr 20fr 30fr;
}

.exec-config-table .col {
  min-width: 0;
}

.exec-config-table .col.addr {
  overflow: hidden;
}

.exec-config-table .col.addr :deep(.n-input-wrapper) {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.exec-config-table .col.addr :deep(input) {
  min-width: 0;
}

.exec-config-table .col > .n-select,
.exec-config-table .col > .n-input {
  width: 100%;
  max-width: 100%;
}

.exec-config-table-header {
  background: var(--n-color-embedded);
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-2);
  white-space: nowrap;
}

.exec-config-table-row {
  background: var(--n-color);
  border-top: 1px solid var(--n-border-color);
}

.exec-config-table-row:hover {
  background: var(--n-color-hover);
}

/* 自定义滚动条样式（可选，提升用户体验） */
.step-tree-container::-webkit-scrollbar {
  width: 4px;
}

.step-tree-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 5px;
}

.step-tree-container::-webkit-scrollbar-thumb {
  background: #a8a8a8;
  border-radius: 5px;
}

.step-tree-container::-webkit-scrollbar-thumb:hover {
  background: #F4511E;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
  flex-shrink: 0; /* 防止 header 被压缩 */
}

.step-count {
  font-weight: 600;
  font-size: 14px;
}

/* 下拉菜单中的图标样式 */
:deep(.n-dropdown-menu .step-icon) {
  flex-shrink: 0;
}

.add-step-btn {
  width: 100%;
  margin-bottom: 10px;
  border-radius: 10px;
}

/* 样式穿透：确保递归组件中所有嵌套层级的样式都能正确应用 */
:deep(.step-item) {
  border: 1px solid transparent;
  border-radius: 10px;
  transition: all .2s;
  cursor: pointer;
  padding-top: 5px;
  padding-bottom: 5px;
}

:deep(.step-item.is-selected) {
  border: 1px dashed #F4511E;
}

/* 所有 loop/if 步骤的普通高亮（拖拽时） */
:deep(.step-item.is-drag-target) {
  border: 2px solid rgba(244, 81, 30, 0.3);
  background-color: rgba(244, 81, 30, 0.05);
}

/* 焦点高亮（拖拽进入目标区域时） */
:deep(.step-item.is-drag-over) {
  border: 2px solid #F4511E;
  background-color: rgba(244, 81, 30, 0.15);
  box-shadow: 0 0 12px rgba(244, 81, 30, 0.4);
}

/* 插入位置指示器 */
:deep(.step-insert-indicator) {
  height: 2px;
  background-color: #F4511E;
  margin: 4px 12px;
  border-radius: 1px;
  box-shadow: 0 0 4px rgba(244, 81, 30, 0.6);
}

:deep(.step-item[draggable="true"]) {
  cursor: move;
}

:deep(.step-drop-zone) {
  min-height: 40px;
  border: 2px dashed #ccc;
  border-radius: 8px;
  margin: 8px 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background-color: #fafafa;
}

:deep(.step-drop-zone.is-drag-over) {
  border-color: #F4511E;
  background-color: rgba(244, 81, 30, 0.1);
  box-shadow: 0 0 8px rgba(244, 81, 30, 0.3);
}

:deep(.step-drop-zone-hint) {
  color: #999;
  font-size: 12px;
  padding: 8px;
}

:deep(.step-drop-zone.is-drag-over .step-drop-zone-hint) {
  color: #F4511E;
  font-weight: 500;
}

:deep(.step-item-child) {
  padding-left: 12px;
}

:deep(.step-name) {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  font-size: 14px;
  font-weight: 300;
  background-color: rgba(222, 222, 222, 0.20);
  padding: 8px 8px;
  border-radius: 10px;
  box-sizing: border-box;
  position: relative;
  min-width: 0;
}

:deep(.step-name:hover) {
  color: #F4511E;
}

:deep(.step-name-text) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  margin-right: auto;
  padding-right: 8px;
  display: inline-block;
}

:deep(.step-actions) {
  display: none;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  margin-left: auto;
  padding-left: 8px;
}

:deep(.step-name:hover .step-actions) {
  display: flex;
}

:deep(.step-number) {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-right: 4px;
}

:deep(.step-icon) {
  font-size: 18px;
  flex-shrink: 0;
  align-items: center;
}

:deep(.step-icon.icon-loop) {
  color: #F4511E;
}

:deep(.step-icon.icon-code) {
  color: #2080f0;
}


:deep(.step-icon.icon-tcp) {
  color: #2080f0;
}

:deep(.step-icon.icon-http) {
  color: #2080f0;
}

:deep(.step-icon.icon-database) {
  color: #2080f0;
}

:deep(.step-icon.icon-if) {
  color: #F4511E;
}

:deep(.step-icon.icon-wait) {
  color: #48d024;
}

:deep(.step-icon.icon-user_variables) {
  color: #FF69B4;
}

:deep(.step-icon.icon-quote) {
  color: #18a058;
}

:deep(.action-btn) {
  padding: 2px 1px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

:deep(.action-btn:hover) {
  opacity: 1;
}

:deep(.step-add-btn) {
  padding-top: 5px;
  padding-left: 12px;
}

/* 引用步骤：脚本内步骤展示（只读，含递归子级） */
:deep(.quote-inner-steps) {
  margin-top: 6px;
  margin-left: 12px;
  border-left: 2px solid #18a058;
  padding-left: 8px;
}
:deep(.quote-inner-list) {
  margin-top: 6px;
}
:deep(.quote-inner-item) {
  padding: 4px 8px;
  margin-bottom: 2px;
  background: rgba(24, 160, 88, 0.06);
  border-radius: 6px;
  cursor: pointer;
  border: none;
}
:deep(.quote-inner-item:hover) {
  background: rgba(24, 160, 88, 0.12);
}
:deep(.quote-inner-item .step-name) {
  display: flex;
  align-items: center;
  gap: 6px;
}
:deep(.quote-inner-item .step-number) {
  margin-left: auto;
}
:deep(.quote-inner-empty) {
  font-size: 12px;
  color: #999;
  padding: 6px 0;
}

:deep(.add-step-btn) {
  width: 100%;
  margin-bottom: 10px;
}

/* 标签选择器样式 */
.tag-mode-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

.tag-name-selected {
  background-color: #e3f2fd;
  font-weight: 500;
}

.tag-mode-item {
  cursor: pointer;
  padding: 8px 12px;
}

.tag-mode-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.tag-list-item {
  cursor: pointer;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tag-checkbox {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  color: #18a058;
  font-weight: bold;
}

.tag-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.n-list-item) {
  transition: background-color 0.2s;
}

:deep(.n-list-item:hover) {
  background-color: #f5f5f5;
}

/* 抽屉内用例列表「所属标签」紧凑展示（与测试用例列表一致） */
.case-tags-cell-trigger {
  max-width: 100%;
}

.case-tags-more {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--n-text-color-2);
}

.case-tags-tooltip-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 320px;
  justify-content: flex-start;
}

</style>
