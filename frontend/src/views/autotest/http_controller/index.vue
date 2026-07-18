<template>
  <n-card :bordered="false" style="width: 100%;" :class="['step-editor-card', { 'is-collapsed': requestCardCollapsed }]">
    <template #header>
      <div class="card-header-row">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleRequestCardCollapsed"
            @keydown.enter.prevent="toggleRequestCardCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="requestCardCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">Request</div>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!requestCardCollapsed">
      <n-form
          :rules="rules"
          :model="state.form"
          label-placement="left"
          class="step-editor-form"
          label-width="80px"
          size="small"
          ref="formRef"
      >
        <!-- 第一行：请求方式20% + 请求地址（与调试同栏无缝）；第二行：步骤名称、所属应用、配置名称 -->
        <div class="http-request-rows">
          <div class="http-request-row http-request-row-bottom">
            <n-form-item label="请求方式" path="method" required class="http-field-method">
              <n-select
                  v-model:value="state.form.method"
                  placeholder="请选择请求方式"
                  :options="methodOptions"
                  :render-label="renderMethodLabel"
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
            <div class="http-url-debug-slot">
              <n-form-item
                  v-if="!props.readonly"
                  label="请求地址"
                  path="url"
                  required
                  class="http-field-url"
              >
                <div class="http-url-debug-inline">
                  <n-input
                      v-model:value="state.form.url"
                      placeholder="请输入请求地址"
                      clearable
                      class="request-toolbar-input-fill"
                      :disabled="props.readonly"
                  />
                  <n-button type="primary" size="small" class="http-debug-btn" @click="debugging" :loading="debugLoading">
                    调试
                  </n-button>
                </div>
              </n-form-item>
              <n-form-item
                  v-else
                  label="请求地址"
                  path="url"
                  required
                  class="http-field-url"
              >
                <n-input
                    v-model:value="state.form.url"
                    placeholder="请输入请求地址"
                    clearable
                    class="request-toolbar-input-fill"
                    :disabled="props.readonly"
                />
              </n-form-item>
            </div>
          </div>
          <div class="http-request-row http-request-row-top">
            <n-form-item label="步骤名称" path="step_name" required class="http-field-step-name">
              <n-input
                  v-model:value="state.form.step_name"
                  placeholder="请输入步骤名称"
                  clearable
                  class="request-step-name-input"
                  :disabled="props.readonly"
              />
            </n-form-item>
            <n-form-item label="所属应用" path="request_project_id" required class="http-field-project">
              <n-select
                  v-model:value="state.form.request_project_id"
                  placeholder="所属应用"
                  :options="projectOptions"
                  :loading="projectLoading"
                  clearable
                  filterable
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
            <n-form-item label="配置名称" path="request_config_name" required class="http-field-config">
              <n-select
                  v-model:value="state.form.request_config_name"
                  placeholder="配置名称"
                  :options="httpConfigNameOptions"
                  :loading="httpConfigNameLoading"
                  clearable
                  filterable
                  tag
                  class="request-toolbar-select"
                  :disabled="props.readonly"
              />
            </n-form-item>
          </div>
        </div>

        <!-- 步骤描述 -->
        <n-form-item label="步骤描述" path="description">
          <n-input
              type="textarea"
              v-model:value="state.form.description"
              placeholder="请输入步骤描述"
              clearable
              style="width: 100%; min-height: 6rem;"
              :disabled="props.readonly"
          />
        </n-form-item>
      </n-form>

      <!-- 请求配置 -->
      <n-tabs type="line" animated style="margin-top: 16px;">
        <n-tab-pane name="headers" tab="请求头">
          <template #tab>
            <n-badge :value="state.form.headers.length" :max="99" show-zero>
              <span>请求头</span>
            </n-badge>
          </template>
          <KeyValueEditor
              v-model:items="state.form.headers"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="params" tab="请求体">
          <template #tab>
            <n-badge :value="getBodyCount" :max="99" show-zero>
              <span>请求体</span>
            </n-badge>
          </template>
          <n-radio-group v-model:value="state.form.bodyType" name="bodyType" :disabled="props.readonly">
            <n-space>
              <n-radio value="none">none</n-radio>
              <n-radio value="params">params</n-radio>
              <n-radio value="form-data">form-data</n-radio>
              <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
              <n-radio value="json">json</n-radio>
              <n-radio value="raw">raw</n-radio>
            </n-space>
          </n-radio-group>
          <div v-if="state.form.bodyType === 'params'">
            <KeyValueEditor
                v-model:items="state.form.bodyForm"
                :body-type="'none'"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'form-data'">
            <KeyValueEditor
                v-model:items="state.form.bodyParams"
                :body-type="state.form.bodyType"
                :enableFile="true"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'x-www-form-urlencoded'">
            <KeyValueEditor
                v-model:items="state.form.bodyForm"
                :body-type="state.form.bodyType"
                :is-for-body="true"
                :available-variable-list="props.availableVariableList"
                :assist-functions="props.assistFunctions"
                :disabled="props.readonly"
            />
          </div>
          <div v-if="state.form.bodyType === 'json'">
            <monaco-editor
                v-model:value="state.form.jsonBody"
                lang="json"
                :options="monacoEditorOptionsForBody()"
                :read-only="props.readonly"
                class="json-editor"
                style="min-height: 400px; height: auto; margin-top: 12px;"
            />
          </div>
          <div v-if="state.form.bodyType === 'raw'">
            <n-input
                v-model:value="state.form.rawBody"
                type="textarea"
                placeholder="请输入 raw 请求体文本"
                :rows="12"
                style="margin-top: 12px;"
                :disabled="props.readonly"
            />
          </div>

        </n-tab-pane>
        <n-tab-pane name="defined_variables" tab="变量">
          <template #tab>
            <n-badge :value="state.form.defined_variables.length" :max="99" show-zero>
              <span>变量</span>
            </n-badge>
          </template>
          <KeyValueEditor
              v-model:items="state.form.defined_variables"
              :body-type="'none'"
              :is-for-body="false"
              :available-variable-list="props.availableVariableList"
              :assist-functions="props.assistFunctions"
              :disabled="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="extract_variables" tab="提取">
          <template #tab>
            <n-badge :value="extractCount" :max="99" show-zero>
              <span>提取</span>
            </n-badge>
          </template>
          <StepExtractPanel
              v-model="state.form.extract_variables"
              mode="response"
              :readonly="props.readonly"
          />
        </n-tab-pane>
        <n-tab-pane name="assert_validators" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <StepAssertPanel
              v-model="state.form.assert_validators"
              mode="response"
              :readonly="props.readonly"
          />
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <!-- DataSource卡片：位于 Request 下方、Response 上方 -->
  <n-card
      :bordered="false"
      style="width: 100%;"
      :class="['step-editor-card', { 'is-collapsed': dataSourceCollapsed }]"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleDataSourceCollapsed"
            @keydown.enter.prevent="toggleDataSourceCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="dataSourceCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">DataSource</div>
        </div>
        <div v-if="dataSourceCollapsed" class="card-header-actions">
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-text class="data-source-tip" depth="3" style="cursor: help;">
                {{ dataSourceTipText }}
              </n-text>
            </template>
            {{ dataSourceTipText }}
          </n-tooltip>
        </div>
      </div>
    </template>

    <n-collapse-transition :show="!dataSourceCollapsed">
      <div class="data-source-content">
        <n-tabs type="line" animated class="data-source-tabs">
          <n-tab-pane name="preview" tab="数据预览">
            <n-space vertical :size="12">
              <div class="data-source-toolbar-row">
                <n-space>
                  <n-button
                      size="small"
                      type="primary"
                      :disabled="props.readonly"
                      :loading="downloadStepDataTemplateLoading"
                      @click="downloadStepDataTemplate"
                  >导入模板下载</n-button>
                </n-space>
                <n-space>
                  <n-button
                      size="small"
                      type="warning"
                      :disabled="props.readonly"
                      :loading="dataSourceImportLoading"
                      @click="dataSourceImport"
                  >导入
                    <input
                        ref="dataSourceImportFileInputRef"
                        type="file"
                        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        style="display: none"
                        @change="onDataSourceImportFileChange"
                    /></n-button>
                  <n-button size="small" type="info" :disabled="props.readonly" :loading="dataSourceExportLoading" @click="dataSourceExport">导出</n-button>
                  <n-button size="small" type="error" :disabled="props.readonly" @click="dataSourceDelete">删除</n-button>
                  <n-button
                      size="small"
                      type="success"
                      :disabled="props.readonly"
                      :loading="dataSourceSaveLoading"
                      @click="dataSourceSave"
                  >保存</n-button>
                </n-space>
              </div>
              <n-data-table
                  :row-key="dataSourcePreviewRowKey"
                  :checked-row-keys="dataSourcePreviewKeysRef"
                  @update:checked-row-keys="dataSourcePreviewHandleCheck"
                  :columns="dataSourcePreviewColumns"
                  :data="dataSource.previewRows"
                  :row-class-name="dataSourcePreviewRowClassName"
                  :bordered="false"
                  :scroll-x="dataSourcePreviewScrollX"
                  size="small"
              />
            </n-space>
          </n-tab-pane>

          <n-tab-pane name="generate" tab="数据生成">
            <n-space vertical :size="12">
              <div class="data-source-row">
                <div class="data-source-row-label">接口文档：</div>
                <n-space>
                  <n-upload
                      :default-upload="false"
                      :show-file-list="false"
                      accept=".xlsx,.xls,.csv,.json,.yaml,.yml"
                      @change="onApiDocFileSelected"
                  >
                    <n-button size="small" type="primary" tertiary :disabled="props.readonly">上传</n-button>
                  </n-upload>
                  <n-button size="small" type="primary" tertiary :disabled="props.readonly"
                            @click="downloadApiDocTemplate">数据模板
                  </n-button>
                </n-space>
              </div>

              <div class="data-source-subtitle">数据校验点</div>
              <n-checkbox-group v-model:value="dataSource.validationPoints" :disabled="props.readonly">
                <n-space>
                  <n-checkbox value="required">必输性</n-checkbox>
                  <n-checkbox value="length">字段长度</n-checkbox>
                  <n-checkbox value="length">类型</n-checkbox>
                  <n-checkbox value="enum">枚举值</n-checkbox>
                  <n-checkbox value="decimal">小数点位数</n-checkbox>
                </n-space>
              </n-checkbox-group>

              <n-data-table
                  :row-key="dataSourceGeneratedRowKey"
                  :columns="dataSourceGeneratedColumns"
                  :data="dataSource.generatedRows"
                  :bordered="false"
                  :scroll-x="900"
                  size="small"
              />
            </n-space>
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-collapse-transition>
  </n-card>

  <!-- DataSource 行编辑弹窗 -->
  <n-modal
      v-model:show="dataSourceEditModalVisible"
      preset="dialog"
      title="编辑数据"
      positive-text="确定"
      negative-text="取消"
      @positive-click="confirmDataSourceEdit"
  >
    <div style="padding: 8px 0;">
      <n-space vertical :size="10">
        <div v-for="cell in dataSourceEditForm.cells" :key="cell.key">
          <div style="margin-bottom: 6px;">{{ cell.label }}：</div>
          <n-input v-model:value="cell.value" clearable/>
        </div>
      </n-space>
    </div>
  </n-modal>

  <!-- 响应结果卡片：在加载中或有响应数据时展示 -->
  <n-card
      v-if="response || debugLoading"
      :bordered="false"
      style="width: 100%; margin-top: 8px;"
      :class="['step-editor-card', { 'is-collapsed': responseCardCollapsed }]"
      ref="debugResultRef"
  >
    <template #header>
      <div class="card-header-row card-header-row--with-actions">
        <div
            class="panel-title-wrap"
            role="button"
            tabindex="0"
            @click="toggleResponseCardCollapsed"
            @keydown.enter.prevent="toggleResponseCardCollapsed"
        >
          <TheIcon
              class="panel-collapse-icon"
              :icon="responseCardCollapsed ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
              :size="20"
          />
          <div class="panel-title">Response</div>
        </div>
        <div class="card-header-actions">
          <n-space align="center" :wrap="false">
            <n-space v-if="response && !debugLoading" align="center" :wrap="false">
              <n-tag :type="responseStatusType" round size="small">Status: {{ response.status }}</n-tag>
              <n-tag :type="durationTagType" round size="small">Time: {{ response.duration }}ms</n-tag>
              <n-tag :type="sizeTagType" round size="small">Size: {{ response.size }}</n-tag>
              <n-tag round>Type: {{ contentType }}</n-tag>
            </n-space>
            <n-tag v-if="debugLoading" type="info" round size="small">
              <template #icon>
                <n-spin size="small"/>
              </template>
              请求中...
            </n-tag>
          </n-space>
        </div>
      </div>
    </template>
    <n-collapse-transition :show="!responseCardCollapsed">
      <!-- 加载状态 -->
      <div v-if="debugLoading" class="debug-loading">
        <n-spin size="large" description="正在发送请求，请稍候..."/>
      </div>
      <!-- 响应内容 -->
      <n-tabs v-else type="line" animated>
        <!-- 请求信息 -->
        <n-tab-pane name="requestInfo" tab="请求信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['requestBasic', 'requestHeaders', 'requestBody']">
              <n-collapse-item title="Basic" name="requestBasic">
                <n-space vertical :size="12">
                  <n-descriptions bordered :column="2" size="small">
                    <n-descriptions-item label="方法">
                      <n-tag :type="methodTagType">{{ requestInfo.method }}</n-tag>
                    </n-descriptions-item>
                    <n-descriptions-item label="URL">
                      <n-text copyable>{{ requestInfo.url }}</n-text>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Headers" name="requestHeaders">
                <n-space vertical :size="12">
                      <pre v-if="requestHeadersText"
                           @click="copyTextContent(requestHeadersText)">{{ requestHeadersText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Cookies" name="requestCookies">
                <n-space vertical :size="12">
                      <pre v-if="requestCookiesText"
                           @click="copyTextContent(requestCookiesText)">{{ requestCookiesText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item :title="`Body (${requestBodyType})`" name="requestBody">
                <div v-if="isRawRequest" class="request-raw-body">
                  <pre>{{ requestInfo.rawBody || '(空)' }}</pre>
                </div>
                <div v-else-if="isJsonRequest">
                  <monaco-editor
                      v-model:value="formattedRequestJson"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <n-data-table
                    v-else
                    :columns="[{title:'Key',key:'key'}, {title:'Value',key:'value'}]"
                    :data="requestBodyData"
                    size="small"
                />
              </n-collapse-item>
            </n-collapse>

          </n-space>

        </n-tab-pane>
        <!-- 响应信息 -->
        <n-tab-pane name="responseInfo" tab="响应信息">
          <n-space vertical :size="16" v-if="response">
            <n-collapse :default-expanded-names="['responseHeaders', 'responseCookies', 'responseBody']"
                        arrow-placement="right">
              <n-collapse-item title="Headers" name="responseHeaders">
                <n-space vertical :size="12">
                      <pre v-if="responseHeadersText"
                           @click="copyTextContent(responseHeadersText)">{{ responseHeadersText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item title="Cookies" name="responseCookies">
                <n-space vertical :size="12">
                      <pre v-if="responseCookiesText"
                           @click="copyTextContent(responseCookiesText)">{{ responseCookiesText }}</pre>
                </n-space>
              </n-collapse-item>
              <n-collapse-item :title="`Body (${contentType})`" name="responseBody">
                <div v-if="isJsonResponse">
                  <monaco-editor
                      v-model:value="formattedResponse"
                      :options="monacoEditorOptions(true)"
                      class="json-editor"
                      style="min-height: 400px; height: auto;"
                  />
                </div>
                <n-code
                    v-else
                    :code="typeof response.data === 'object'? JSON.stringify(response.data, null, 2) : response.data || ''"
                    :language="responseLanguage"
                    show-line-numbers
                    class="response-code"
                />
              </n-collapse-item>
            </n-collapse>
          </n-space>
        </n-tab-pane>
        <!-- 数据提取 -->
        <n-tab-pane name="extract_variables" tab="数据提取">
          <n-data-table
              v-if="response && response.extract_results && response.extract_results.length > 0"
              :columns="extractColumns"
              :data="response.extract_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无数据提取结果"/>
        </n-tab-pane>
        <!-- 断言结果 -->
        <n-tab-pane name="assert" tab="断言结果">
          <n-data-table
              v-if="response && response.validator_results && response.validator_results.length > 0"
              :columns="validatorColumns"
              :data="response.validator_results"
              size="small"
              :bordered="true"
          />
          <n-empty v-else description="暂无断言结果"/>
        </n-tab-pane>
        <!-- 执行日志 -->
        <n-tab-pane name="logs" tab="执行日志">
          <n-space vertical :size="12" v-if="response && response.logs && response.logs.length > 0">
                <pre
                    v-for="(log, index) in response.logs"
                    :key="index"
                    class="log-item"
                >{{ log }}</pre>
          </n-space>
          <n-empty v-else description="暂无执行日志"/>
        </n-tab-pane>
      </n-tabs>
    </n-collapse-transition>
  </n-card>

  <!-- 调试前选择执行环境 -->
  <n-modal
      v-model:show="debugModalVisible"
      preset="dialog"
      title="选择调试环境"
      positive-text="确定"
      negative-text="取消"
      @positive-click="confirmDebugModal"
  >
    <div style="padding: 8px 0;">
      <div style="margin-bottom: 8px;">执行环境：</div>
      <n-select
          v-model:value="selectedDebugEnvId"
          :options="envOptions"
          :loading="envLoading"
          placeholder="请选择执行环境"
          clearable
          filterable
          style="width: 100%;"
      />
    </div>
  </n-modal>
</template>

<script setup>
import {computed, h, nextTick, reactive, ref, watch} from 'vue'
import {
  NBadge,
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCode,
  NCollapse,
  NCollapseItem,
  NCollapseTransition,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopover,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  NText,
  NTooltip,
  NUpload,
} from 'naive-ui'
import api from "@/api";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";
import MonacoEditor from "@/components/monaco/index.vue";
import TheIcon from "@/components/icon/TheIcon.vue";
import StepExtractPanel from '@/components/autotest/StepExtractPanel.vue'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import {
  ASSERT_MODE_RESPONSE,
  buildAssertListFromDict,
  buildExtractListFromDict,
  countDictKeys,
  EXTRACT_MODE_RESPONSE,
  hydrateAssertDictFromBackend,
  hydrateExtractDictFromBackend,
  normalizeBackendList,
  validateAssertList,
  validateExtractList,
} from '@/utils/autotestExtractAssert'
import {useUserStore} from '@/store';
import {useRoute} from 'vue-router'

/**
 * HTTP 控制器组件 Props
 *
 * 数据接收说明：
 * 1. config: 从步骤树传递的配置数据（step.config），包含：
 *    - method, url, headers, params
 *    - data (JSON body), form_data, form_urlencoded
 *    - extract_variables, assert_validators, defined_variables
 *
 * 2. step: 完整的步骤对象，包含：
 *    - step.id: 步骤ID（step_code）
 *    - step.type: 步骤类型（'http'）
 *    - step.name: 步骤名称（step_name）
 *    - step.config: 配置数据（同 props.config）
 *    - step.original: 完整的原始后端步骤数据，包含所有字段：
 *      * step_code, step_name, step_desc, step_type
 *      * request_method, request_url, request_header, request_body, request_params
 *      * extract_variables, assert_validators, defined_variables
 *      * id, case_id, parent_step_id, children 等所有后端返回的字段
 *
 * 使用方式：
 * - 访问配置数据：props.config.method, props.config.url
 * - 访问原始数据：props.step.original.step_name, props.step.original.step_desc
 * - 访问步骤信息：props.step.name, props.step.id
 */
const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  },
  projectOptions: {
    type: Array,
    default: () => []
  },
  projectLoading: {
    type: Boolean,
    default: false
  },
  availableVariableList: {
    type: Array,
    default: () => []
  },
  assistFunctions: {
    type: Array,
    default: () => []
  },
  readonly: {type: Boolean, default: false}
})

const emit = defineEmits(['update:config'])

const formRef = ref(null);
const route = useRoute()

const requestCardCollapsed = ref(false)
const responseCardCollapsed = ref(false)
const toggleRequestCardCollapsed = () => {
  requestCardCollapsed.value = !requestCardCollapsed.value
}
const toggleResponseCardCollapsed = () => {
  responseCardCollapsed.value = !responseCardCollapsed.value
}

const dataSourceCollapsed = ref(true)
const toggleDataSourceCollapsed = () => {
  const wasCollapsed = dataSourceCollapsed.value
  dataSourceCollapsed.value = !dataSourceCollapsed.value
  if (wasCollapsed && !dataSourceCollapsed.value) {
    loadStepDataframePreview()
  }
}

const dataSourceTipText = computed(() => {
  const dsName = String(state.form?.data_source_name || '').trim()
  const dsDesc = String(state.form?.data_source_desc || '').trim()
  const name = String(state.form?.step_name || '').trim()
  const stepName = name || 'HTTP请求(本步骤)'
  if (dsName && dsDesc) return `${stepName}(本步骤) - ${dsName} (${dsDesc})`
  if (dsName) return `${stepName}(本步骤) - ${dsName}`
  return `${stepName}(本步骤) - 数据驱动文件上传或接口文档分析`
})

const ts = () => new Date().toISOString().slice(0, 19).replace('T', ' ')
const dataSource = reactive({
  apiDocFileName: '',
  validationPoints: [],
  previewRows: [],
  generatedRows: [
    {id: 'gen-1', name: '生成数据1', remark: '备注1', generatedAt: ts()},
    {id: 'gen-2', name: '生成数据2', remark: '备注2', generatedAt: ts()},
    {id: 'gen-3', name: '生成数据3', remark: '备注3', generatedAt: ts()}
  ]
})

const dataSourceEditModalVisible = ref(false)
const dataSourceEditForm = reactive({rowKey: null, type: 'generated', cells: []})
const previewEditingCell = reactive({
  rowKey: null,
  colKey: '',
  originalValue: ''
})

/** DataSource「数据生成」行编辑（当前仅占位打开弹窗，字段编辑后续接入） */
const openDataSourceEdit = (type, row) => {
  dataSourceEditForm.rowKey = row?.__rowKey ?? row?.id ?? null
  dataSourceEditForm.type = type
  dataSourceEditForm.cells = []
  dataSourceEditModalVisible.value = true
}

const confirmDataSourceEdit = () => {
  $message.success('已更新')
  dataSourceEditModalVisible.value = false
}

const removeDataSourceRow = (type, row) => {
  const list = type === 'generated' ? dataSource.generatedRows : dataSource.previewRows
  const idx = list.findIndex((x) => x.id === row?.id)
  if (idx >= 0) {
    list.splice(idx, 1)
    $message.success('已删除')
  }
}

const buildPreviewTableRowsByMatrix = (matrix) => {
  const safeMatrix = Array.isArray(matrix) ? matrix : []
  return safeMatrix.map((line, rowIndex) => {
    const rowObj = {__rowKey: String(rowIndex + 1), __rowNo: rowIndex + 1}
    const cells = Array.isArray(line) ? line : []
    cells.forEach((val, colIndex) => {
      rowObj[`c_${colIndex + 1}`] = val
    })
    return rowObj
  })
}

const isLockedKeywordRow = (row) => {
  const v = String(row?.c_1 ?? '').trim().toUpperCase()
  return v === 'HEAD' || v === 'BODY' || v === 'ASSERT'
}

const isProtectedPreviewRow = (row) => {
  // 第一行是字段名称行，固定保护；关键字行也保护
  return Number(row?.__rowNo || 0) === 1 || isLockedKeywordRow(row)
}

const renumberPreviewRows = () => {
  dataSource.previewRows = (dataSource.previewRows || []).map((row, idx) => ({
    ...row,
    __rowKey: String(idx + 1),
    __rowNo: idx + 1,
  }))
}

/** 将数据预览表格行转为后端 dataframe 二维矩阵（c_1..c_n → 每行数组，空单元为 null）。 */
const previewRowsToDataframeMatrix = (rows) => {
  const list = Array.isArray(rows) ? rows : []
  let maxCol = 0
  list.forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) {
        const n = Number(k.slice(2))
        if (Number.isFinite(n) && n > maxCol) maxCol = n
      }
    })
  })
  if (maxCol === 0) return []
  return list.map((row) => {
    const line = []
    for (let j = 1; j <= maxCol; j++) {
      const key = `c_${j}`
      const v = row[key]
      if (v === '' || v === undefined) line.push(null)
      else line.push(v)
    }
    return line
  })
}

/** 预览矩阵当前最大列序号（c_1 → 1），无数据列为 0 */
const getMaxPreviewColumnIndex = (rows) => {
  let max = 0
  for (const row of rows || []) {
    for (const k of Object.keys(row || {})) {
      if (k.startsWith('c_')) {
        const n = Number(k.slice(2))
        if (Number.isFinite(n) && n > max) max = n
      }
    }
  }
  return max
}

const buildPreviewColumnsByRows = (rows) => {
  const colSet = new Set()
  ;(rows || []).forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) colSet.add(k)
    })
  })
  const colKeys = Array.from(colSet).sort((a, b) => Number(a.slice(2)) - Number(b.slice(2)))
  const dynamicCols = []
  for (const colKey of colKeys) {
    const colIndex = Number(colKey.slice(2)) || 0
    const col = {
      title: () => h(
          'div',
          {style: 'display:flex;align-items:center;justify-content:center;gap:4px;'},
          [
            h('span', null, `列${colIndex}`)
            ,
            colKey === 'c_1'
                ? null
                : h(NCheckbox, {
                  checked: dataSourcePreviewColumnKeysRef.value.includes(colKey),
                  disabled: props.readonly,
                  onUpdateChecked: (checked) => {
                    const set = new Set(dataSourcePreviewColumnKeysRef.value || [])
                    if (checked) {
                      set.add(colKey)
                    } else {
                      set.delete(colKey)
                    }
                    dataSourcePreviewColumnKeysRef.value = Array.from(set)
                  }
                })
          ]
      ),
      key: colKey,
      align: 'center',
      ellipsis: {tooltip: true},
      minWidth: 150,
      render: (row) => {
        const editing = previewEditingCell.rowKey === row.__rowKey && previewEditingCell.colKey === colKey
        if (editing) {
          return h(NInput, {
            value: row[colKey] == null ? '' : String(row[colKey]),
            autofocus: true,
            onUpdateValue: (v) => {
              row[colKey] = v
            },
            onBlur: () => {
              previewEditingCell.rowKey = null
              previewEditingCell.colKey = ''
              previewEditingCell.originalValue = ''
            },
            onKeydown: (e) => {
              if (e.key === 'Enter') {
                previewEditingCell.rowKey = null
                previewEditingCell.colKey = ''
                previewEditingCell.originalValue = ''
              } else if (e.key === 'Escape') {
                row[colKey] = previewEditingCell.originalValue
                previewEditingCell.rowKey = null
                previewEditingCell.colKey = ''
                previewEditingCell.originalValue = ''
              }
            }
          })
        }
        const raw = row[colKey]
        const isEmpty = raw == null || raw === ''
        const displayText = isEmpty ? '\u00a0' : String(raw)
        return h('div', {
          style: {
            minHeight: '28px',
            width: '100%',
            minWidth: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'text',
            boxSizing: 'border-box',
          },
          onDblclick: (e) => {
            e.stopPropagation()
            if (props.readonly) return
            previewEditingCell.rowKey = row.__rowKey
            previewEditingCell.colKey = colKey
            previewEditingCell.originalValue = isEmpty ? '' : String(raw)
          },
        }, displayText)
      }
    }
    if (colKey === 'c_1') {
      col.fixed = 'left'
    }
    dynamicCols.push(col)
  }
  return dynamicCols
}

/** 数据预览表横向滚动宽度：固定列 + 每列至少 150px + 末尾「新增列」列，列多时自动超出容器出现滚动条 */
const dataSourcePreviewScrollX = computed(() => {
  const PREVIEW_FIXED_COL_WIDTH = 20 + 20 + 50
  const PREVIEW_COL_ADD_WIDTH = 32
  const MIN_DYNAMIC_COL_WIDTH = 100
  const colSet = new Set()
  ;(dataSource.previewRows || []).forEach((row) => {
    Object.keys(row || {}).forEach((k) => {
      if (k.startsWith('c_')) colSet.add(k)
    })
  })
  const n = colSet.size
  const content = PREVIEW_FIXED_COL_WIDTH + n * MIN_DYNAMIC_COL_WIDTH + PREVIEW_COL_ADD_WIDTH
  return Math.max(content, 1500)
})

const buildBlankPreviewRow = () => {
  const maxCol = getMaxPreviewColumnIndex(dataSource.previewRows || [])
  const blank = {}
  for (let j = 1; j <= maxCol; j++) {
    blank[`c_${j}`] = ''
  }
  return blank
}

/** 表头「+」：在右侧追加一列（所有行补齐新列；无任何行时插入一行作为表头行） */
const addPreviewColumn = (e) => {
  e?.stopPropagation?.()
  if (props.readonly) return
  let rows = [...(dataSource.previewRows || [])]
  if (rows.length === 0) {
    dataSource.previewRows = [{__rowKey: '1', __rowNo: 1, c_1: ''}]
    renumberPreviewRows()
    return
  }
  const maxCol = getMaxPreviewColumnIndex(rows)
  const nextKey = `c_${maxCol + 1}`
  dataSource.previewRows = rows.map((row) => ({...row, [nextKey]: ''}))
}

const insertBlankPreviewRowAfter = (row) => {
  if (props.readonly) return
  const idx = (dataSource.previewRows || []).findIndex((x) => x.__rowKey === row.__rowKey)
  if (idx < 0) return
  const blankRow = {
    __rowKey: `tmp-${Date.now()}`,
    __rowNo: 0,
    ...buildBlankPreviewRow(),
  }
  const next = [...(dataSource.previewRows || [])]
  next.splice(idx + 1, 0, blankRow)
  dataSource.previewRows = next
  renumberPreviewRows()
}

const loadStepDataframePreview = async () => {
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    dataSource.previewRows = []
    return
  }
  try {
    const res = await api.getDataSourceByCaseStep({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
    })
    const info = res?.data || {}
    const matrix = Array.isArray(info.dataframe) ? info.dataframe : []
    dataSource.previewRows = buildPreviewTableRowsByMatrix(matrix)
    renumberPreviewRows()
  } catch (_) {
    dataSource.previewRows = []
  }
}

const dataSourcePreviewColumns = computed(() => [
  {
    type: "selection",
    fixed: "left",
    width: 25,
    align: 'center',
    disabled: (row) => isProtectedPreviewRow(row)
  },
  {
    title: '#',
    key: '__rowNo',
    align: 'center',
    width: 25,
    fixed: 'left',
    render: (row) => String(row.__rowNo ?? '')
  },
  {
    title: '',
    key: '__rowAdd',
    align: 'center',
    width: 25,
    fixed: 'left',
    render: (row) => h(
        'div',
        {style: 'width:100%;display:flex;justify-content:center;align-items:center;'},
        h(NButton, {
          text: true,
          quaternary: true,
          size: 'tiny',
          disabled: props.readonly,
          title: Number(row?.__rowNo || 0) === 1 ? '在首行（字段行）下方插入空白行' : '在下方新增空白行',
          onClick: (e) => {
            e.stopPropagation()
            insertBlankPreviewRowAfter(row)
          }
        }, {
          icon: () => h(TheIcon, {icon: 'material-symbols-light:add-rounded', size: 14})
        })
    )
  },
  ...buildPreviewColumnsByRows(dataSource.previewRows),
  {
    title: () =>
        h(
            'div',
            {style: 'width:100%;display:flex;justify-content:center;align-items:center;'},
            h(NButton, {
              text: true,
              quaternary: true,
              size: 'tiny',
              disabled: props.readonly,
              title: '在右侧新增列',
              onClick: addPreviewColumn,
            }, {
              icon: () => h(TheIcon, {icon: 'material-symbols-light:add-rounded', size: 14}),
            }),
        ),
    key: '__colAdd',
    align: 'center',
    width: 25,
    fixed: 'right',
    render: () =>
        h('div', {
          style: 'min-height:28px;width:100%;',
        }),
  },
])


const dataSourcePreviewKeysRef = ref([]);
const dataSourcePreviewColumnKeysRef = ref([])

/**
 * DataSource「数据预览」表格行主键。
 * @param {object} row
 * @returns {string}
 */
function dataSourcePreviewRowKey(row) {
  return row.__rowKey;
}

/**
 * DataSource「数据预览」表格勾选行变更。
 * @param {string[]} rowKeys
 */
function dataSourcePreviewHandleCheck(rowKeys) {
  dataSourcePreviewKeysRef.value = rowKeys;
}

const dataSourcePreviewRowClassName = (row) => (isProtectedPreviewRow(row) ? 'locked-keyword-row' : '')


const dataSourceGeneratedColumns = [
  {
    title: () => h(NPopover, {
      trigger: 'click',
      placement: 'bottom',
      showArrow: true
    }, {
      default: () => h(NSpace, {vertical: true, size: 6, style: {minWidth: '60px'}}, {
        default: () => [
          h(NButton, {
            size: 'small',
            type: 'error',
            block: true,
            disabled: props.readonly,
            onClick: dataSourceDelete
          }, {default: () => '删除'}),
          h(NButton, {
            size: 'small',
            type: 'success',
            block: true,
            disabled: props.readonly,
            onClick: dataSourceSave
          }, {default: () => '保存'}),
        ]
      }),
      trigger: () => h(NButton, {
        text: true,
        quaternary: true,
        size: 'small',
        title: '更多操作'
      }, {
        icon: () => h(TheIcon, {icon: 'material-symbols:keyboard-command-key', size: 18})
      })
    }),
    key: '_toolbarToggle',
    width: 30,
    align: 'center'
  },
  {
    type: 'selection',
    fixed: 'left',
    width: 30,
    align: 'center'
  },
  {title: '名称', key: 'name', align: 'center', ellipsis: {tooltip: true}},
  {title: '备注', key: 'remark', align: 'center', ellipsis: {tooltip: true}},
  {title: '生成时间', key: 'generatedAt', align: 'center', ellipsis: {tooltip: true}},
  {
    title: '操作',
    key: 'actions',
    fixed: 'right',
    width: 90,
    render: (row) => h(NSpace, {size: 8}, {
      default: () => [
        h(NButton, {
          text: true,
          type: 'error',
          size: 'small',
          onClick: () => removeDataSourceRow('generated', row)
        }, {default: () => '删除'}),
        h(NButton, {
          text: true,
          type: 'info',
          size: 'small',
          onClick: () => openDataSourceEdit('generated', row)
        }, {default: () => '修改'})
      ]
    })
  }
]

/**
 * DataSource「数据生成」表格行主键。
 * @param {object} row
 * @returns {string}
 */
function dataSourceGeneratedRowKey(row) {
  return row.id;
}

/**
 * 选择接口文档文件（仅前端占位）。
 * @param {object} options
 */
const onApiDocFileSelected = (options) => {
  const file = options?.file?.file
  dataSource.apiDocFileName = file?.name || ''
  if (dataSource.apiDocFileName) {
    $message.info(`已选择接口文档：${dataSource.apiDocFileName}（后端暂未实现上传）`)
  }
}

/** 下载步骤测试数据导入模板（output/template 内置 xlsx）。 */
const downloadStepDataTemplateLoading = ref(false)
const downloadStepDataTemplate = async () => {
  if (downloadStepDataTemplateLoading.value) return
  try {
    downloadStepDataTemplateLoading.value = true
    const res = await api.downloadHttpStepDatasetImportTemplate()
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const fileName = m?.[1]
        ? decodeURIComponent(m[1])
        : '测试用例HTTP请求步骤数据源模板.xlsx'
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('下载成功')
  } catch (e) {
    $message.error(`下载失败：${e?.message || e}`)
  } finally {
    downloadStepDataTemplateLoading.value = false
  }
}
/** 下载接口文档模板（仅前端占位）。 */
const downloadApiDocTemplate = () => $message.info('后端暂未实现：下载接口文档模板')

const dataSourceImportFileInputRef = ref(null)
const dataSourceImportLoading = ref(false)

/** 单步骤数据集导入：需步骤已入库；先选文件，再确认后上传（避免确认框被文件选择器卡住无法关闭）。 */
const dataSourceImport = () => {
  if (props.readonly) return
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('当前步骤尚未保存入库，请先保存步骤树后再进行数据导入')
    return
  }
  dataSourceImportFileInputRef.value?.click()
}

const onDataSourceImportFileChange = (ev) => {
  const input = ev.target
  const file = input?.files?.[0]
  if (input) input.value = ''
  if (!file) return
  if (!String(file.name || '').toLowerCase().endsWith('.xlsx')) {
    $message.warning('仅支持 .xlsx 格式的数据驱动文件')
    return
  }
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('缺少步骤上下文，请先保存步骤树后再试')
    return
  }
  $dialog.confirm({
    title: '导入确认',
    type: 'warning',
    content:
        '上传成功后将覆盖本步骤在服务器端已保存的数据源及缓存，数据预览将以导入文件为准。是否继续？',
    async confirm() {
      if (dataSourceImportLoading.value) return false
      try {
        dataSourceImportLoading.value = true
        const formData = new FormData()
        formData.append('case_id', String(caseId))
        formData.append('step_id', String(stepId))
        formData.append('step_code', stepCode)
        formData.append('file', file)
        const res = await api.uploadSingleStepDataset(formData)
        const info = res?.data || {}
        if (info.file_name != null) state.form.data_source_name = String(info.file_name)
        if (info.file_desc != null) state.form.data_source_desc = String(info.file_desc || '')
        await loadStepDataframePreview()
        $message.success(res?.message || '导入成功')
        return true
      } catch (_) {
        /* 错误信息由 http 拦截器统一提示 */
        return false
      } finally {
        dataSourceImportLoading.value = false
      }
    },
  })
}
/** 导出数据：基于后端 dataframe 导出 xlsx（不依赖当前前端表格编辑态）。 */
const dataSourceExportLoading = ref(false)
const dataSourceExport = async () => {
  if (dataSourceExportLoading.value) return
  try {
    dataSourceExportLoading.value = true
    const caseId = route.query.case_id ? Number(route.query.case_id) : null
    const original = props.step?.original || {}
    const stepId = original.id ? Number(original.id) : null
    const stepCode = String(original.step_code || '').trim()
    if (!caseId || !stepId || !stepCode) {
      $message.warning('缺少步骤上下文，无法导出')
      return
    }
    const res = await api.exportDataSourceXlsx({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const cd = res?.headers?.['content-disposition'] || res?.headers?.['Content-Disposition'] || ''
    const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const fileName = m?.[1] ? decodeURIComponent(m[1]) : `dataset_${caseId}_${stepCode}.xlsx`
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    $message.success('导出成功')
  } catch (e) {
    $message.error(`导出失败：${e?.message || e}`)
  } finally {
    dataSourceExportLoading.value = false
  }
}
/** 删除数据：优先删除数据预览勾选行。 */
const dataSourceDelete = () => {
  if (props.readonly) return
  const selectedRows = new Set(dataSourcePreviewKeysRef.value || [])
  const selectedCols = new Set(dataSourcePreviewColumnKeysRef.value || [])
  if (selectedRows.size === 0 && selectedCols.size === 0) {
    $message.info('请先勾选要删除的行或列')
    return
  }
  const content = `确认删除已勾选的${selectedRows.size > 0 ? '行' : ''}${selectedRows.size > 0 && selectedCols.size > 0 ? '和' : ''}${selectedCols.size > 0 ? '列' : ''}吗？此操作不可撤销。`
  $dialog.confirm({
    title: '删除确认',
    type: 'warning',
    content,
    confirm() {
      let nextRows = (dataSource.previewRows || [])
      if (selectedRows.size > 0) {
        nextRows = nextRows.filter((row) => isProtectedPreviewRow(row) || !selectedRows.has(row.__rowKey))
      }
      if (selectedCols.size > 0) {
        nextRows = nextRows.map((row) => {
          const next = {...row}
          selectedCols.forEach((colKey) => {
            delete next[colKey]
          })
          return next
        })
      }
      dataSource.previewRows = nextRows
      renumberPreviewRows()
      // 清空已删除后的勾选状态，避免 UI 残留
      dataSourcePreviewKeysRef.value = []
      dataSourcePreviewColumnKeysRef.value = []
      $message.success(`已删除${selectedRows.size > 0 ? '行' : ''}${selectedRows.size > 0 && selectedCols.size > 0 ? '和' : ''}${selectedCols.size > 0 ? '列' : ''}`)
    }
  })
}
const dataSourceSaveLoading = ref(false)

/** 将当前数据预览表格提交后端，按 case_id + step_id + step_code 更新数据源（含解析后的 dataset）。 */
const dataSourceSave = async () => {
  if (props.readonly) return
  const caseId = route.query.case_id ? Number(route.query.case_id) : null
  const original = props.step?.original || {}
  const stepId = original.id ? Number(original.id) : null
  const stepCode = String(original.step_code || '').trim()
  if (!caseId || !stepId || !stepCode) {
    $message.warning('当前步骤尚未保存入库，请先保存步骤树后再保存数据')
    return
  }
  if (dataSourceSaveLoading.value) return
  try {
    dataSourceSaveLoading.value = true
    const dataframe = previewRowsToDataframeMatrix(dataSource.previewRows || [])
    const res = await api.updateDataSource({
      case_id: caseId,
      step_id: stepId,
      step_code: stepCode,
      dataframe,
    })
    const info = res?.data || {}
    if (info.file_name != null) state.form.data_source_name = String(info.file_name)
    if (info.file_desc != null) state.form.data_source_desc = String(info.file_desc || '')
    await loadStepDataframePreview()
    $message.success(res?.message || '保存成功')
  } catch (_) {
    /* 错误信息由 http 拦截器统一提示 */
  } finally {
    dataSourceSaveLoading.value = false
  }
}

watch(
    () => [route.query.case_id, props.step?.original?.id, props.step?.original?.step_code],
    async () => {
      if (!dataSourceCollapsed.value) {
        await loadStepDataframePreview()
      }
    },
    {deep: false}
)


// 请求方式下拉框
const methodOptions = [
  {label: 'GET', value: 'GET', color: '#2080F0'},
  {label: 'POST', value: 'POST', color: '#18A058'},
  {label: 'PUT', value: 'PUT', color: '#FCA130'},
  {label: 'DELETE', value: 'DELETE', color: '#F4511E'}
]
const renderMethodLabel = (option) => {
  return h(
      'span',
      {style: {color: option.color, fontWeight: '600'}},
      option.label
  )
}
// 表单验证规则
const rules = {
  method: [
    {
      required: true,
      message: '请选择请求方式',
      trigger: 'change'
    }
  ],
  url: [
    {
      required: true,
      message: '请输入请求地址',
      trigger: 'blur'
    }
  ],
  request_project_id: [
    {
      validator(_rule, value) {
        if (value === null || value === undefined || value === '') {
          return new Error('请选择所属应用')
        }
        return true
      },
      trigger: ['change', 'blur']
    }
  ],
  request_config_name: [
    {
      validator(_rule, value) {
        if (value === null || value === undefined || String(value).trim() === '') {
          return new Error('请填写或选择配置名称')
        }
        return true
      },
      trigger: ['change', 'blur']
    }
  ],
  step_name: [
    {
      required: true,
      message: '请输入步骤名称',
      trigger: 'blur'
    }
  ]
}

/* 表单状态管理：从步骤配置初始化，不写死默认值 */
const state = reactive({
  form: {
    url: '',
    method: 'GET',
    headers: [],
    bodyType: 'none',
    params: [],
    bodyParams: [],
    bodyForm: [],
    jsonBody: '',
    rawBody: '',
    step_name: '',
    description: '',
    request_project_id: null, // 请求项目ID（与 request_args_type 等一致，从 form 读写；无 UI 时由 init 从 config/original 带入）
    request_config_name: null, // 与 /autotest/config/config_names 中 api 类配置名一致
    data_source_name: '',
    data_source_desc: '',
    defined_variables: [],
    extract_variables: {},
    assert_validators: {},
  }
})

// 注意：不再使用 kvObjectToList 和 kvListToObject，所有字段都必须是列表格式

const initFromConfig = () => {
  const cfg = props.config || {}
  const step = props.step || {}
  const original = step.original || {}

  console.log('========== HTTP 控制器 - 接收到的数据 ==========')
  console.log('1. props.config (配置数据，从 step.config 传递):', cfg)
  console.log('2. props.step (完整的步骤对象):', step)
  console.log('3. props.step.original (原始后端步骤数据):', original)
  console.log('4. props.step.original 的所有 key:', original ? Object.keys(original) : [])

  // 打印原始数据中的关键字段
  if (original) {
    console.log('5. 原始步骤数据中的关键字段:')
    console.log('   - step_code:', original.step_code)
    console.log('   - step_name:', original.step_name)
    console.log('   - step_desc:', original.step_desc)
    console.log('   - step_type:', original.step_type)
    console.log('   - id:', original.id)
    console.log('   - case_id:', original.case_id)
    console.log('   - request_method:', original.request_method)
    console.log('   - request_url:', original.request_url)
    console.log('   - extract_variables:', original.extract_variables)
    console.log('   - assert_validators:', original.assert_validators)
    console.log('   - defined_variables:', original.defined_variables)
  }
  console.log('==================================================')

  // 从原始数据中获取步骤名称和描述
  // 优先使用 config（含 emit 回写），再回退到 original，避免失焦时被旧 original 覆盖
  state.form.step_name = cfg.step_name !== undefined
      ? cfg.step_name
      : (step.name || original.step_name || '')
  state.form.description = cfg.step_desc !== undefined ? (cfg.step_desc ?? '') : (original.step_desc || '')

  state.form.method = cfg.method || original.request_method || 'GET'
  state.form.url = cfg.url || original.request_url || ''
  // headers、params 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
  state.form.headers = Array.isArray(cfg.headers) ? cfg.headers : (Array.isArray(original.request_header) ? original.request_header : [])
  state.form.params = Array.isArray(cfg.params) ? cfg.params : (Array.isArray(original.request_params) ? original.request_params : [])
  state.form.request_project_id = cfg.request_project_id ?? original.request_project_id ?? null
  state.form.request_config_name = cfg.request_config_name ?? original.request_config_name ?? null
  state.form.data_source_name = cfg.data_source_name ?? original.data_source_name ?? ''
  state.form.data_source_desc = cfg.data_source_desc ?? original.data_source_desc ?? ''

  // 请求体类型（与后端 request_args_type 枚举一致：none, params, form-data, x-www-form-urlencoded, json, raw）
  // 请求体类型：统一用 request_args_type（与后端枚举一致），form 内用 bodyType 仅作 UI 绑定
  const requestArgsType = cfg.request_args_type ?? original.request_args_type
  if (requestArgsType) {
    state.form.bodyType = requestArgsType
  } else if (cfg.data) {
    state.form.bodyType = 'json'
  } else if (cfg.form_data) {
    state.form.bodyType = 'form-data'
  } else if (cfg.form_urlencoded) {
    state.form.bodyType = 'x-www-form-urlencoded'
  } else if (cfg.request_text != null && cfg.request_text !== '') {
    state.form.bodyType = 'raw'
  } else {
    state.form.bodyType = 'none'
  }
  state.form.rawBody = cfg.request_text ?? original.request_text ?? ''

  // form_data、form_urlencoded 必须是列表格式，每个元素包含 key、value、desc、type（form-data 需 type 供 KeyValueEditor 显示「数据」列）
  const bodyParamsRaw = Array.isArray(cfg.form_data) ? cfg.form_data : (Array.isArray(original.request_form_data) ? original.request_form_data : [])
  state.form.bodyParams = bodyParamsRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))
  const bodyFormRaw = Array.isArray(cfg.form_urlencoded) ? cfg.form_urlencoded : (Array.isArray(original.request_form_urlencoded) ? original.request_form_urlencoded : [])
  state.form.bodyForm = bodyFormRaw.map(item => ({
    key: item.key || '',
    value: item.value ?? '',
    desc: item.desc || '',
    type: item.type || 'text'
  }))

  // JSON 请求体：优先使用配置中的原始文本，避免格式错误时被清空
  const jsonBodyText = cfg.jsonBodyText
  if (jsonBodyText !== undefined && jsonBodyText !== null) {
    state.form.jsonBody = String(jsonBodyText)
  } else {
    try {
      const body = cfg.data ?? original.request_body
      if (body === null || body === undefined) {
        state.form.jsonBody = ''
      } else if (typeof body === 'string') {
        state.form.jsonBody = body
      } else {
        state.form.jsonBody = Object.keys(body).length ? JSON.stringify(body, null, 2) : ''
      }
    } catch {
      state.form.jsonBody = state.form.jsonBody ?? ''
    }
  }

  // defined_variables 必须是列表格式，每个元素包含 key、value、desc，不再兼容字典格式
  state.form.defined_variables = Array.isArray(cfg.defined_variables) ? cfg.defined_variables : (Array.isArray(original.defined_variables) ? original.defined_variables : [])

  state.form.extract_variables = hydrateExtractDictFromBackend(
      normalizeBackendList(cfg.extract_variables ?? original.extract_variables),
      EXTRACT_MODE_RESPONSE
  )
  state.form.assert_validators = hydrateAssertDictFromBackend(
      normalizeBackendList(cfg.assert_validators ?? original.assert_validators),
      ASSERT_MODE_RESPONSE
  )
}

initFromConfig()


const httpConfigNameOptions = ref([])
const httpConfigNameLoading = ref(false)
const loadHttpConfigNames = async (projectId) => {
  const pid = projectId != null && projectId !== '' ? Number(projectId) : null
  if (!pid) {
    httpConfigNameOptions.value = []
    return
  }
  httpConfigNameLoading.value = true
  try {
    const res = await api.getEnvConfigNameList({ project_id: pid, config_type: 'api' })
    const list = Array.isArray(res?.data) ? res.data : []
    httpConfigNameOptions.value = list.map((name) => ({ label: name, value: name }))
  } catch (e) {
    console.error('加载配置名称列表失败', e)
    httpConfigNameOptions.value = []
  } finally {
    httpConfigNameLoading.value = false
  }
}
watch(
    () => state.form.request_project_id,
    (pid, prev) => {
      void loadHttpConfigNames(pid)
      if (pid == null || pid === '') {
        state.form.request_config_name = null
      } else if (prev != null && Number(pid) !== Number(prev)) {
        state.form.request_config_name = null
      }
    },
    { immediate: true }
)


// 标记是否正在从外部更新，避免循环触发
let isExternalUpdate = false

// 仅在切换步骤或步骤原始数据变化时重新初始化，不监听 props.config，避免用户编辑（如请求地址全选删除/剪切）后被 config 回写覆盖
watch(
    () => [props.step?.id, props.step?.original, props.step?.name],
    ([stepId, original, stepName]) => {
      isExternalUpdate = true
      initFromConfig()
      const cfg = props.config || {}
      const step = props.step || {}
      const orig = step.original || {}
      state.form.step_name = cfg.step_name !== undefined
          ? cfg.step_name
          : (stepName || orig.step_name || '')
      nextTick(() => {
        isExternalUpdate = false
      })
    },
    {deep: true, immediate: false}
)

const buildExtractForBackend = () =>
    buildExtractListFromDict(state.form.extract_variables, EXTRACT_MODE_RESPONSE)

const buildValidatorsForBackend = () =>
    buildAssertListFromDict(state.form.assert_validators, ASSERT_MODE_RESPONSE)

const buildConfigFromState = () => {
  // 列表格式：每个元素包含 key、value、desc
  // 确保 headers、params、form_data、form_urlencoded、defined_variables 都是列表格式
  const headersList = Array.isArray(state.form.headers) ? state.form.headers : []
  const paramsList = Array.isArray(state.form.params) ? state.form.params : []
  const variablesList = Array.isArray(state.form.defined_variables) ? state.form.defined_variables : []

  // 确保每个元素都有 key、value、desc 字段；form-data 需保留 type 以便 re-init 后 Text/File 选择不丢失
  const normalizeList = (list) => {
    return list.map(item => ({
      key: item.key || '',
      value: item.value || '',
      desc: item.desc || ''
    }))
  }
  const normalizeBodyParams = (list) => {
    return (Array.isArray(list) ? list : []).map(item => ({
      key: item.key || '',
      value: item.value ?? '',
      desc: item.desc || '',
      type: item.type || 'text'
    }))
  }

  let data = null
  let request_text = null

  // 始终从当前表单带出 form_data / form_urlencoded，避免切到 none 再切回时被 initFromConfig 清空
  const form_data = normalizeBodyParams(state.form.bodyParams)
  const form_urlencoded = Array.isArray(state.form.bodyForm) ? normalizeList(state.form.bodyForm) : []

  let jsonBodyText = undefined
  switch (state.form.bodyType) {
    case 'json':
      try {
        data = state.form.jsonBody ? JSON.parse(state.form.jsonBody) : {}
      } catch {
        data = {}
      }
      jsonBodyText = state.form.jsonBody ?? ''
      break
    case 'raw':
      request_text = state.form.rawBody ?? ''
      break
    case 'none':
    default:
      break
  }

  return {
    step_name: state.form.step_name || '',
    step_desc: state.form.description ?? '',
    method: state.form.method,
    url: state.form.url,
    headers: normalizeList(headersList),
    params: normalizeList(paramsList),
    request_args_type: state.form.bodyType,
    request_project_id: state.form.request_project_id ?? null,
    request_config_name: state.form.request_config_name != null && String(state.form.request_config_name).trim() !== ''
        ? String(state.form.request_config_name).trim()
        : null,
    data_source_name: state.form.data_source_name || '',
    data_source_desc: state.form.data_source_desc || '',
    data,
    jsonBodyText,
    form_data,
    form_urlencoded,
    request_text,
    extract_variables: buildExtractForBackend(),
    assert_validators: buildValidatorsForBackend(),
    defined_variables: normalizeList(variablesList)
  }
}

// 使用防抖，避免频繁触发
let emitTimer = null
watch(
    () => [
      state.form.step_name, state.form.description, state.form.method,
      state.form.url, state.form.headers, state.form.params,
      state.form.bodyType, state.form.bodyParams, state.form.bodyForm,
      state.form.jsonBody, state.form.rawBody, state.form.request_project_id,
      state.form.request_config_name,
      state.form.data_source_name, state.form.data_source_desc,
      state.form.defined_variables, state.form.extract_variables, state.form.assert_validators
    ],
    () => {
      // 如果正在从外部更新，不触发 emit
      if (isExternalUpdate) return

      // 清除之前的定时器
      if (emitTimer) {
        clearTimeout(emitTimer)
      }

      // 使用防抖，延迟发送更新
      emitTimer = setTimeout(() => {
        emit('update:config', buildConfigFromState())
      }, 300) // 300ms 防抖延迟
    },
    {deep: true}
)


/* ======================================= */
/* =============== Request =============== */
/*  ====================================== */
/* 请求体数量计算 */
const getBodyCount = computed(() => {
  switch (state.form.bodyType) {
    case 'params':
    case 'x-www-form-urlencoded':
      return state.form.bodyForm.length
    case 'form-data':
      return state.form.bodyParams.length
    case 'json':
      return state.form.jsonBody.trim() ? 1 : 0
    case 'raw':
      return state.form.rawBody.trim() ? 1 : 0
    default:
      return 0
  }
})

watch(
    () => state.form.jsonBody,
    (newVal) => {
      if (newVal?.trim() && !['json'].includes(state.form.bodyType)) {
        state.form.bodyType = 'json'
      }
    },
    {deep: true}
)

const monacoEditorOptions = (readOnly) => {
  const options = {
    // 基础配置
    theme: 'vs-dark',
    language: 'json',
    fontSize: 14,
    tabSize: 4,
    // 布局与外观
    automaticLayout: true,
    minimap: {
      enabled: true
    },
    lineNumbers: 'on',
    renderLineHighlight: 'line',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    // 其他
    folding: true,
    foldingStrategy: 'auto',
    roundedSelection: false,
    cursorStyle: 'line',
  }
  if (readOnly) {
    options.readOnly = true
  }

  return options
}

// 请求体 JSON 编辑器：黑色背景 + JSON 语法校验（红色波浪线）
const monacoEditorOptionsForBody = () => {
  return {
    ...monacoEditorOptions(!!props.readonly),
  }
}

/* ======================================== */
/* =============== Response =============== */
/*  ======================================= */
const response = ref(null) // 存储调试响应结果
const debugLoading = ref(false) // 调试加载状态
const requestInfo = ref({  // 存储请求的详细信息
  url: '',
  method: '',
  headers: {},
  bodyType: 'none',
  jsonBody: ''
})

// 请求类型（不区分大小写匹配 Content-Type）
const contentType = computed(() => {
  const headers = response.value?.headers || {}
  // 不区分大小写地查找 content-type
  const contentTypeKey = Object.keys(headers).find(key => key.toLowerCase() === 'content-type')
  if (contentTypeKey) {
    return headers[contentTypeKey]?.split(';')[0] || 'text/plain'
  }
  return 'text/plain'
})

// 响应类型
const isJsonResponse = computed(() => {
  return contentType.value.includes('json')
})

const responseLanguage = computed(() => {
  const ct = contentType.value.toLowerCase()
  if (ct.includes('json')) return 'json'
  if (ct.includes('xml')) return 'xml'
  if (ct.includes('html')) return 'html'
  return 'text'
})
// 响应格式化
const formattedResponse = computed(() => {
  try {
    return JSON.stringify(response.value.data, null, 4)
  } catch {
    return response.value.data
  }
})

const responseHeadersText = computed(() => {
  return Object.entries(response.value?.headers || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const responseCookiesText = computed(() => {
  return Object.entries(response.value?.cookies || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const requestHeadersText = computed(() => {
  return Object.entries(requestInfo.value.headers || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const requestCookiesText = computed(() => {
  return Object.entries(requestInfo.value.cookies || {}).map(([name, value]) => `${name}: ${value}`).join('\n')
})
const copyTextContent = (text) => {
  navigator.clipboard.writeText(text).then(() => {
    $message.success('复制成功');
  }).catch((err) => {
    $message.error(`复制失败: ${err.message}`);
  });
}

const responseStatusType = computed(() => {
  if (!response.value) return 'default'
  if (response.value.status === 200) {
    return formattedResponse.value?.status === '000000' ? 'success' : 'error';
  }
  return response.value.status >= 400 ? 'error' : 'success'
})

const durationTagType = computed(() => {
  if (!response.value) return 'default'
  return response.value.duration > 1000 ? 'warning' : 'success'
})

const sizeTagType = computed(() => {
  if (!response.value) return 'default'
  return parseFloat(response.value.size) > 100 ? 'warning' : 'success'
})

// 响应-请求信息相关
const methodTagType = computed(() => {
  const method = requestInfo.value.method?.toUpperCase()
  return {
    GET: 'success',
    POST: 'warning',
    PUT: 'info',
    DELETE: 'error'
  }[method] || 'default'
})


const requestBodyType = computed(() => {
  const typeMap = {
    'none': 'None',
    'params': 'Params',
    'form-data': 'Form Data',
    'x-www-form-urlencoded': 'Form URL Encoded',
    'json': 'JSON',
    'raw': 'Raw'
  }
  return typeMap[requestInfo.value.bodyType] || 'Params'
})

const isJsonRequest = computed(() => requestInfo.value.bodyType === 'json')
const isRawRequest = computed(() => requestInfo.value.bodyType === 'raw')

const formattedRequestJson = computed(() => {
  try {
    return JSON.stringify(JSON.parse(requestInfo.value.jsonBody), null, 4)
  } catch {
    return requestInfo.value.jsonBody
  }
})

const requestBodyData = computed(() => {
  switch (requestInfo.value.bodyType) {
    case 'form-data':
      // 优先使用后端返回的处理后数据
      if (requestInfo.value.formData && typeof requestInfo.value.formData === 'object') {
        return Object.entries(requestInfo.value.formData).map(([key, value]) => ({key, value}))
      }
      return state.form.bodyParams.filter(item => item.key)
    case 'params':
    case 'x-www-form-urlencoded':
      // 优先使用后端返回的处理后数据
      if (requestInfo.value.formUrlencoded && typeof requestInfo.value.formUrlencoded === 'object') {
        return Object.entries(requestInfo.value.formUrlencoded).map(([key, value]) => ({key, value}))
      }
      return state.form.bodyForm.filter(item => item.key)
    default:
      return []
  }
})


const debugResultRef = ref(null)

const debugModalVisible = ref(false)
const envOptions = ref([])
const envLoading = ref(false)
/** 调试所选环境枚举 ID（下拉 label 为环境名称，与 schema 的 env_id 对应） */
const selectedDebugEnvId = ref(null)

const loadEnvNames = async () => {
  envLoading.value = true
  try {
    const res = await api.getEnvList()
    const list = res?.data ?? []
    envOptions.value = list.map((row) => ({
      label: row.env_name != null ? String(row.env_name) : String(row.env_id),
      value: row.env_id,
    }))
    if (envOptions.value.length > 0 && selectedDebugEnvId.value == null) {
      selectedDebugEnvId.value = envOptions.value[0].value
    }
  } catch (e) {
    console.error('加载环境列表失败', e)
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

const openDebugModal = () => {
  selectedDebugEnvId.value = null
  debugModalVisible.value = true
  loadEnvNames()
}

const confirmDebugModal = () => {
  debugModalVisible.value = false
  doDebugRequest(selectedDebugEnvId.value)
}

/* 调试方法：先选环境再发请求 */
const debugging = async () => {
  try {
    await formRef.value?.validate?.()
  } catch (_) {
    $message.warning("请填写必填字段")
    return
  }
  openDebugModal()
}

const doDebugRequest = async (env_id) => {
  const extractCheck = validateExtractList(buildExtractForBackend())
  if (!extractCheck.valid) {
    $message.error(extractCheck.message)
    return
  }
  const assertCheck = validateAssertList(buildValidatorsForBackend())
  if (!assertCheck.valid) {
    $message.error(assertCheck.message)
    return
  }

  const userStore = useUserStore()
  const currentUser = userStore.username
  debugLoading.value = true
  response.value = null

  try {
    const cfg = buildConfigFromState()

    const headersObj = cfg.headers.reduce((acc, {key, value}) => {
      if (key) acc[key] = value
      return acc
    }, {})
    const paramsObj = cfg.params.reduce((acc, {key, value}) => {
      if (key) acc[key] = value
      return acc
    }, {})

    requestInfo.value = {
      method: cfg.method,
      url: cfg.url,
      headers: headersObj,
      bodyType: cfg.request_args_type ?? 'none',
      jsonBody: state.form.jsonBody,
      rawBody: state.form.rawBody ?? '',
      formData: state.form.bodyType === 'form-data' ? state.form.bodyParams : null,
      formUrlencoded: (state.form.bodyType === 'params' || state.form.bodyType === 'x-www-form-urlencoded') ? state.form.bodyForm : null
    }

    const caseId = route.query.case_id ? Number(route.query.case_id) : null
    const original = props.step?.original || {}

    const debugPayload = {
      env_id: Number(env_id),
      case_id: caseId,
      step_type: original.step_type || 'HTTP/HTTPS协议网络请求',
      step_name: state.form.step_name || original.step_name || 'HTTP 调试',
      request_url: cfg.url,
      request_method: cfg.method,
      request_args_type: cfg.request_args_type ?? original.request_args_type ?? 'none',
      request_project_id: cfg.request_project_id ?? original.request_project_id ?? null,
      request_config_name:
          cfg.request_config_name != null && String(cfg.request_config_name).trim() !== ''
              ? String(cfg.request_config_name).trim()
              : (original.request_config_name != null && String(original.request_config_name).trim() !== ''
                  ? String(original.request_config_name).trim()
                  : ''),
      request_params: Array.isArray(cfg.params) && cfg.params.length > 0 ? cfg.params : null,
      request_body: cfg.data,
      request_form_data: Array.isArray(cfg.form_data) && cfg.form_data.length > 0 ? cfg.form_data : null,
      request_form_urlencoded: Array.isArray(cfg.form_urlencoded) && cfg.form_urlencoded.length > 0 ? cfg.form_urlencoded : null,
      request_text: cfg.request_text ?? null,
      request_header: Array.isArray(cfg.headers) && cfg.headers.length > 0 ? cfg.headers : null,
      defined_variables: Array.isArray(cfg.defined_variables) && cfg.defined_variables.length > 0 ? cfg.defined_variables : null,
      session_variables: Array.isArray(cfg.session_variables) && cfg.session_variables.length > 0 ? cfg.session_variables : null,
      extract_variables: buildExtractForBackend(),
      assert_validators: buildValidatorsForBackend(),
      created_user: currentUser,
      updated_user: currentUser
    }

    const responseData = await api.httpRequestDebugging(debugPayload);

    if (responseData.code === '000000') {
      response.value = responseData.data;
      // 确保 extract_results、validator_results、logs 等字段被正确保留
      if (responseData.data.extract_results) {
        response.value.extract_results = responseData.data.extract_results
      }
      if (responseData.data.validator_results) {
        response.value.validator_results = responseData.data.validator_results
      }
      if (responseData.data.logs) {
        response.value.logs = responseData.data.logs
      }
      // 从后端响应中获取处理后的请求信息（变量替换后的实际报文）
      if (responseData.data.request_info) {
        const reqInfo = responseData.data.request_info
        requestInfo.value = {
          method: reqInfo.method,
          url: reqInfo.url,
          headers: reqInfo.headers || {},
          cookies: reqInfo.cookies || {},
          bodyType: reqInfo.body_type || 'none',
          jsonBody: reqInfo.body_type === 'json' && reqInfo.body ? JSON.stringify(reqInfo.body, null, 2) : '',
          formData: reqInfo.body_type === 'form-data' ? reqInfo.body : null,
          formUrlencoded: (reqInfo.body_type === 'params' || reqInfo.body_type === 'x-www-form-urlencoded') ? reqInfo.body : null,
          rawBody: reqInfo.body_type === 'raw' && reqInfo.request_text != null ? reqInfo.request_text : (requestInfo.value.rawBody ?? '')
        }
      }
      $message.success('调试成功');
      // 滚动到调试结果区域
      nextTick(() => {
        debugResultRef.value?.$el?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      })
    } else {
      $message.error(`请求失败：${responseData.message}`);
    }
  } catch (error) {
    $message.error(`调试失败：${error.message}`);
  } finally {
    // 关闭加载状态
    debugLoading.value = false
  }
};

const extractCount = computed(() => countDictKeys(state.form.extract_variables))
const validatorsCount = computed(() => countDictKeys(state.form.assert_validators))

// 数据提取结果表格列定义
const extractColumns = [
  {
    title: '变量名',
    key: 'name',
    width: 120
  },
  {
    title: '提取来源',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Request Json': 'Request Json',
        'Request Text': 'Request Text',
        'Request XML': 'Request XML',
        'Request Header': 'Request Header',
        'Request Cookie': 'Request Cookie',
        'Response Json': 'Response Json',
        'Response Text': 'Response Text',
        'Response XML': 'Response XML',
        'Response Header': 'Response Header',
        'Response Cookie': 'Response Cookie'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '提取范围',
    key: 'scope',
    width: 120,
    render: (row) => (row.scope === 'ALL' ? '全部提取' : '部分提取')
  },
  {
    title: '提取路径',
    key: 'expr',
    width: 120,
    ellipsis: {tooltip: true}
  },
  {
    title: '提取值',
    key: 'extract_value',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.extract_value === null || row.extract_value === undefined) {
        return '-'
      }
      const value = typeof row.extract_value === 'object'
          ? JSON.stringify(row.extract_value)
          : String(row.extract_value)
      return value.length > 100 ? value.substring(0, 100) + '...' : value
    }
  },
  {
    title: '提取结果',
    key: 'success',
    width: 120,
    render: (row) => {
      return h(NTag, {
        type: row.success ? 'success' : 'error',
        round: true,
        size: 'small'
      }, {default: () => row.success ? 'pass' : 'fail'})
    }
  },
  {
    title: '错误信息',
    key: 'error',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => row.error || '-'
  }
]

// 断言结果表格列定义
const validatorColumns = [
  {
    title: '断言名称',
    key: 'name',
    width: 120,
    ellipsis: {tooltip: true}
  },
  {
    title: '断言对象',
    key: 'source',
    width: 120,
    render: (row) => {
      const sourceMap = {
        'Request Json': 'requestJson',
        'Request Text': 'requestText',
        'Request XML': 'requestXml',
        'Request Header': 'requestHeader',
        'Request Cookie': 'requestCookie',
        'Response Json': 'responseJson',
        'Response Text': 'responseText',
        'Response XML': 'responseXml',
        'Response Header': 'responseHeader',
        'Response Cookie': 'responseCookie',
        '变量池': '变量池'
      }
      return sourceMap[row.source] || row.source
    }
  },
  {
    title: '断言路径',
    key: 'expr',
    width: 130,
    ellipsis: {tooltip: true}
  },
  {
    title: '结果值',
    key: 'actual_value',
    width: 150,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.actual_value === null || row.actual_value === undefined) {
        return '-'
      }
      return String(row.actual_value)
    }
  },
  {
    title: '断言方式',
    key: 'operation',
    width: 100
  },
  {
    title: '期望值',
    key: 'expect_value',
    width: 120,
    ellipsis: {tooltip: true},
    render: (row) => {
      if (row.except_value === null || row.except_value === undefined) {
        return '-'
      }
      return String(row.except_value)
    }
  },
  {
    title: '断言结果',
    key: 'success',
    width: 100,
    render: (row) => {
      return h(NTag, {
        type: row.success ? 'success' : 'error',
        round: true,
        size: 'small'
      }, {default: () => row.success ? 'pass' : 'fail'})
    }
  },
  {
    title: '错误信息',
    key: 'error',
    ellipsis: {tooltip: true},
    render: (row) => row.error || '-'
  }
]

</script>

<style scoped>
/* 卡片壳见 styles/autotest-theme.scss .step-editor-card */

.http-request-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.http-request-row {
  width: 100%;
}

/* 第二行：步骤名称 40% / 所属应用 30% / 配置名称 30% */
.http-request-row-top {
  display: grid;
  grid-template-columns: 4fr 2.5fr 3.5fr;
  gap: 12px;
  align-items: start;
}

.http-request-row-top :deep(.n-form-item),
.http-request-row-bottom :deep(.n-form-item) {
  min-width: 0;
}

.http-field-step-name :deep(.n-input),
.http-field-project :deep(.n-select),
.http-field-config :deep(.n-select) {
  width: 100%;
}

.request-step-name-input {
  width: 100%;
}

.request-toolbar-select {
  width: 100%;
}

.request-toolbar-input-fill {
  width: 100%;
}

/* 第一行：请求方式约 20%，右侧为请求地址；调试按钮与输入框同一 form-item 内容区无缝并排（对齐 run_code 顶栏） */
.http-request-row-bottom {
  display: grid;
  grid-template-columns: minmax(0, 20%) minmax(0, 1fr);
  column-gap: 12px;
  align-items: start;
  width: 100%;
}

.http-url-debug-slot {
  min-width: 0;
}

.http-field-url :deep(.n-form-item-blank) {
  width: 100%;
}

.http-url-debug-inline {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
  width: 100%;
  min-width: 0;
}

.http-url-debug-inline .request-toolbar-input-fill {
  flex: 1;
  min-width: 0;
}

.http-debug-btn {
  flex-shrink: 0;
}

/* .panel-title 见 .step-editor-card */

.card-header-row {
  padding-right: 0;
}

.card-header-row--with-actions {
  padding-right: 220px; /* 预留右侧 status / tip 空间 */
}

.data-source-content {
  padding-top: 4px;
}

.data-source-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.data-source-row-label {
  min-width: 130px;
}

.data-source-subtitle {
  margin-top: 12px;
  margin-bottom: 8px;
  font-weight: 600;
}

.data-source-tabs {
  margin-top: 4px;
}

.data-source-toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.data-source-tip {
  display: inline-block;
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.json-editor {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  border-radius: 10px;
  overflow: hidden;
  transition: height 0.3s ease;
}

/* 确保编辑器容器可以自适应内容高度 */
.json-editor :deep(.monaco-editor) {
  min-height: 90px;
  height: auto !important;
}


/* 添加必要的布局样式 */
.response-code {
  max-height: 400px; /* 限制代码块高度 */
  overflow: auto; /* 添加滚动条 */
}

.debug-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 0;
}
</style>
