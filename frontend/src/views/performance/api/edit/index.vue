<!--
  压测接口编辑子页 — 新增/编辑/导入草稿确认共用（隐藏菜单，query 传 api_id）

  编辑入口由抽屉改为独立子页（跳转模式同 autotest 步骤编辑页）；
  请求块字段与 krun_autotest_step 逐字对齐（从功能资产导入退化为纯字段搬运）；
  请求体按 args_type 切换编辑器，json 走 Monaco（文本↔对象转换），xml/raw 走文本；
  参数化数据集由 PerfApiDatasetPanel 内联管理（保存接口后可用）；
  导入草稿队列经 sessionStorage 传递（key=perf_api_draft_queue），保存成功自动进入下一条。
-->
<template>
  <AppPage show-footer>
    <n-space vertical :size="16">
      <!-- 基础信息 -->
      <n-card title="基础信息" size="small">
        <n-grid :cols="24" :x-gap="12">
          <n-gi :span="12">
            <n-form-item label="所属应用" path="api_project" :rule="projectRule">
              <n-select
                  v-model:value="form.api_project"
                  :options="projectOptions"
                  :disabled="isEdit"
                  placeholder="请选择所属应用"
                  clearable
                  filterable
              />
            </n-form-item>
          </n-gi>
          <n-gi :span="12">
            <n-form-item label="接口名称" path="api_name" :rule="{ required: true, message: '请输入接口名称' }">
              <n-input v-model:value="form.api_name" placeholder="请输入接口名称" clearable />
            </n-form-item>
          </n-gi>
          <n-gi :span="24">
            <n-form-item label="接口描述" path="api_desc">
              <n-input v-model:value="form.api_desc" type="textarea" :rows="2" placeholder="接口描述（可选）" />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-card>

      <!-- 请求定义 -->
      <n-card title="请求定义" size="small">
        <n-form
            ref="formRef"
            :model="form"
            label-placement="left"
            label-width="96"
            require-mark-placement="right-hanging"
        >
          <n-form-item label="请求类型" path="step_type">
            <n-radio-group v-model:value="form.step_type" name="step_type">
              <!-- 值与后端 AutoTestStepType 中文枚举一致, 英文缩写会被 schema 校验拒绝 -->
              <n-radio value="HTTP请求">HTTP请求</n-radio>
              <n-radio value="TCP请求">TCP请求</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-grid :cols="24" :x-gap="12">
            <n-gi v-if="isHttp" :span="6">
              <n-form-item label="请求方式" path="request_method" :rule="{ required: true, message: '必选' }">
                <n-select
                    v-model:value="form.request_method"
                    :options="methodOptions"
                    :render-label="renderMethodLabel"
                    placeholder="方式"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="isHttp ? 14 : 20">
              <n-form-item
                  label="请求地址"
                  path="request_url"
                  :rule="{ required: true, message: '请输入请求地址', trigger: ['blur', 'change'] }"
              >
                <n-input v-model:value="form.request_url" placeholder="支持相对路径与 ${} 占位符" clearable />
              </n-form-item>
            </n-gi>
            <n-gi :span="4">
              <n-form-item label="端口" path="request_port" :label-width="46">
                <n-input v-model:value="form.request_port" placeholder="缺省" clearable />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="目标应用" path="request_project_id">
                <n-select
                    v-model:value="form.request_project_id"
                    :options="projectOptions"
                    placeholder="缺省随任务施压环境"
                    clearable
                    filterable
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="12">
              <n-form-item label="目标配置" path="request_config_name">
                <n-input
                    v-model:value="form.request_config_name"
                    placeholder="APP节点配置名（缺省随任务）"
                    clearable
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-alert v-if="!isHttp" :bordered="false" type="warning">
            当前引擎仅支持 HTTP 施压：TCP 接口允许保存与编排，执行前闸门会拒绝下发。
          </n-alert>

          <n-tabs type="line" animated style="margin-top: 8px">
            <n-tab-pane name="header" tab="请求头">
              <KeyValueEditor v-model:items="form.request_header" :body-type="'none'" :is-for-body="false" />
            </n-tab-pane>

            <n-tab-pane name="body" tab="请求体">
              <n-radio-group v-model:value="bodyType" name="bodyType">
                <n-space>
                  <n-radio value="none">none</n-radio>
                  <n-radio value="params">params</n-radio>
                  <n-radio value="form-data">form-data</n-radio>
                  <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
                  <n-radio value="json">json</n-radio>
                  <n-radio value="xml">xml</n-radio>
                  <n-radio value="raw">raw</n-radio>
                </n-space>
              </n-radio-group>
              <div v-if="bodyType === 'params'" class="body-editor">
                <KeyValueEditor v-model:items="form.request_params" :body-type="'none'" :is-for-body="true" />
              </div>
              <div v-if="bodyType === 'form-data'" class="body-editor">
                <KeyValueEditor v-model:items="form.request_form_data" :body-type="'form-data'" :is-for-body="true" />
              </div>
              <div v-if="bodyType === 'x-www-form-urlencoded'" class="body-editor">
                <KeyValueEditor
                    v-model:items="form.request_form_urlencoded"
                    :body-type="'x-www-form-urlencoded'"
                    :is-for-body="true"
                />
              </div>
              <monaco-editor
                  v-if="bodyType === 'json'"
                  v-model:value="jsonBodyText"
                  lang="json"
                  :options="monacoBodyOptions"
                  class="body-editor"
                  style="min-height: 320px"
              />
              <monaco-editor
                  v-if="bodyType === 'xml'"
                  v-model:value="form.request_text"
                  lang="xml"
                  :options="monacoBodyOptions"
                  class="body-editor"
                  style="min-height: 320px"
              />
              <n-input
                  v-if="bodyType === 'raw'"
                  v-model:value="form.request_text"
                  type="textarea"
                  placeholder="请输入 raw 请求体文本"
                  :rows="10"
                  class="body-editor"
              />
            </n-tab-pane>

            <n-tab-pane name="assert" tab="断言">
              <n-space vertical :size="8">
                <n-card v-for="(item, index) in form.assert_validators" :key="index" size="small" hoverable>
                  <template #header>
                    <div class="item-card-header">
                      <span class="item-card-title">{{ item.name || `断言 ${index + 1}` }}</span>
                      <n-button text type="error" size="small" @click="form.assert_validators.splice(index, 1)">
                        删除
                      </n-button>
                    </div>
                  </template>
                  <n-grid :cols="24" :x-gap="12">
                    <n-gi :span="8">
                      <n-form-item label="名称" :label-width="56" size="small">
                        <n-input v-model:value="item.name" placeholder="断言名称" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="来源" :label-width="56" size="small">
                        <n-select v-model:value="item.source" :options="PERF_SOURCE_GROUP_OPTIONS" placeholder="取值来源" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="表达式" :label-width="56" size="small">
                        <n-input v-model:value="item.expr" placeholder="如 $.code" clearable />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="比较" :label-width="56" size="small">
                        <n-select v-model:value="item.operation" :options="assertionOptions" placeholder="比较方式" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="16">
                      <n-form-item label="期望值" :label-width="56" size="small">
                        <n-input v-model:value="item.except_value" placeholder="期望值（比较符为空/不为空时可留空）" clearable />
                      </n-form-item>
                    </n-gi>
                  </n-grid>
                </n-card>
                <n-button type="primary" block dashed @click="addAssert">添加断言</n-button>
              </n-space>
            </n-tab-pane>

            <n-tab-pane name="extract" tab="提取">
              <n-space vertical :size="8">
                <n-card v-for="(item, index) in form.extract_variables" :key="index" size="small" hoverable>
                  <template #header>
                    <div class="item-card-header">
                      <span class="item-card-title">${{ `{` }}{{ item.name || `变量${index + 1}` }}{{ `}` }}</span>
                      <n-button text type="error" size="small" @click="form.extract_variables.splice(index, 1)">
                        删除
                      </n-button>
                    </div>
                  </template>
                  <n-grid :cols="24" :x-gap="12">
                    <n-gi :span="8">
                      <n-form-item label="变量名" :label-width="56" size="small">
                        <n-input v-model:value="item.name" placeholder="存入变量池的名称" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="来源" :label-width="56" size="small">
                        <n-select v-model:value="item.source" :options="PERF_SOURCE_GROUP_OPTIONS" placeholder="取值来源" />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="表达式" :label-width="56" size="small">
                        <n-input v-model:value="item.expr" placeholder="如 $.data.token" clearable />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="范围" :label-width="56" size="small">
                        <n-select
                            v-model:value="item.scope"
                            :options="[{ label: '首个匹配(SOME)', value: 'SOME' }, { label: '全部匹配(ALL)', value: 'ALL' }]"
                            placeholder="SOME"
                            clearable
                        />
                      </n-form-item>
                    </n-gi>
                    <n-gi :span="8">
                      <n-form-item label="索引" :label-width="56" size="small">
                        <n-input-number v-model:value="item.index" placeholder="多匹配取第几个" style="width: 100%" clearable />
                      </n-form-item>
                    </n-gi>
                  </n-grid>
                </n-card>
                <n-button type="primary" block dashed @click="addExtract">添加提取</n-button>
              </n-space>
            </n-tab-pane>
          </n-tabs>
        </n-form>
      </n-card>

      <!-- 参数化数据集（接口落库后可管理） -->
      <PerfApiDatasetPanel :api-row="apiRow" />
    </n-space>

    <PerfApiDebugDrawer ref="debugRef" />

    <template #footer>
      <n-space justify="center" :size="16">
        <n-button @click="handleBack">返回列表</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave">保 存</n-button>
        <n-button v-if="isEdit" type="success" secondary @click="debugRef?.open(apiRow)">调 试</n-button>
      </n-space>
    </template>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAlert, NButton, NCard, NForm, NFormItem, NGi, NGrid, NInput, NInputNumber,
  NRadio, NRadioGroup, NSelect, NSpace, NTabPane, NTabs,
} from 'naive-ui'

import AppPage from '@/components/page/AppPage.vue'
import KeyValueEditor from '@/components/common/KeyValueEditor.vue'
import MonacoEditor from '@/components/monaco/index.vue'
import PerfApiDatasetPanel from '../components/PerfApiDatasetPanel.vue'
import PerfApiDebugDrawer from '../components/PerfApiDebugDrawer.vue'

import { assertionOperationSelectOptions } from '@/constants/autotestAssertionOperation'
import { PERF_SOURCE_GROUP_OPTIONS } from '@/constants/perfApi'
import api from '@/api'

// 组件名需与菜单管理中页面项 name 一致（KeepAlive include 按 componentName 匹配）
defineOptions({ name: '压测接口编辑' })

const route = useRoute()
const router = useRouter()

/** 导入草稿队列在 sessionStorage 的键（列表页导入后写入，本页逐条消费） */
const DRAFT_QUEUE_KEY = 'perf_api_draft_queue'

const formRef = ref(null)
const debugRef = ref(null)
const saving = ref(false)
const projectOptions = ref([])

/** 编辑中的接口详情（含 api_id，参数化数据集卡据此开关） */
const apiRow = ref(null)

/** 与后端 AutoTestReqArgsType / HTTPMethod 取值一致（方式下拉沿用 http_controller 四色口径） */
const methodOptions = [
  { label: 'GET', value: 'GET', color: '#2080F0' },
  { label: 'POST', value: 'POST', color: '#18A058' },
  { label: 'PUT', value: 'PUT', color: '#FCA130' },
  { label: 'DELETE', value: 'DELETE', color: '#F4511E' },
]
const assertionOptions = assertionOperationSelectOptions

const monacoBodyOptions = {
  minimap: { enabled: false },
  fontSize: 13,
  automaticLayout: true,
  tabSize: 2,
  scrollBeyondLastLine: false,
}

const emptyForm = () => ({
  api_id: null,
  api_code: null,
  api_project: null,
  api_name: null,
  api_desc: null,
  step_type: 'HTTP请求',
  request_url: null,
  request_port: null,
  request_method: 'GET',
  request_header: [],
  request_params: [],
  request_form_data: [],
  request_form_urlencoded: [],
  request_text: '',
  request_body: null,
  request_args_type: 'none',
  request_project_id: null,
  request_config_name: null,
  extract_variables: [],
  assert_validators: [],
})

const form = reactive(emptyForm())

/** 请求体编辑形态与 request_args_type 一一对应；json/xml/raw 的载体字段见 buildPayload */
const bodyType = ref('none')
const jsonBodyText = ref('')

const isHttp = computed(() => form.step_type === 'HTTP请求')
const isEdit = computed(() => form.api_id != null)

/** 编辑模式应用归属锁定：跨应用迁移会让场景引用与环境解析同时失效 */
const projectRule = computed(() =>
    isEdit.value ? undefined : { required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] },
)

function renderMethodLabel(option) {
  return h('span', { style: { color: option.color, fontWeight: '600' } }, option.label)
}

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

function addAssert() {
  form.assert_validators.push({ name: '', expr: '', source: 'response json', operation: '等于', except_value: '' })
}

function addExtract() {
  form.extract_variables.push({ name: '', expr: '', source: 'response json', scope: 'SOME', index: null })
}

/** 后端详情/导入草稿 → 表单形态（请求体对象转 JSON 文本，容器 null 归空数组） */
function applyDetail(detail) {
  Object.assign(form, emptyForm(), {
    ...detail,
    request_header: detail.request_header || [],
    request_params: detail.request_params || [],
    request_form_data: detail.request_form_data || [],
    request_form_urlencoded: detail.request_form_urlencoded || [],
    request_text: detail.request_text || '',
    extract_variables: detail.extract_variables || [],
    assert_validators: detail.assert_validators || [],
  })
  const argsType = detail.request_args_type || 'none'
  bodyType.value = argsType === 'none' && detail.request_body ? 'json' : argsType
  jsonBodyText.value = detail.request_body ? JSON.stringify(detail.request_body, null, 2) : ''
}

async function loadApi(apiId) {
  try {
    const res = await api.getPerfApi({ api_id: apiId })
    applyDetail(res.data || {})
    apiRow.value = res.data || {}
    // 刷新地址栏，刷新页面后仍能回到本接口（同 autotest 步骤编辑页约定）
    router.replace({ path: route.path, query: { api_id: String(apiId) } })
  } catch (e) {
    handleBack()
  }
}

/** 从队列弹出下一条导入草稿（无剩余返回 null） */
function shiftDraft() {
  let queue = []
  try {
    queue = JSON.parse(sessionStorage.getItem(DRAFT_QUEUE_KEY) || '[]')
  } catch (e) {
    queue = []
  }
  const draft = queue.shift() || null
  sessionStorage.setItem(DRAFT_QUEUE_KEY, JSON.stringify(queue))
  return draft
}

function remainDraftCount() {
  try {
    return (JSON.parse(sessionStorage.getItem(DRAFT_QUEUE_KEY) || '[]')).length
  } catch (e) {
    return 0
  }
}

async function initFromRoute() {
  const apiId = route.query.api_id ? Number(route.query.api_id) : null
  if (apiId) {
    await loadApi(apiId)
    return
  }
  if (route.query.draft) {
    const draft = shiftDraft()
    if (draft) {
      // 导入草稿：结构与详情同构，但无 id/code，用户补全名称后走 create
      applyDetail(draft)
      return
    }
  }
}

onMounted(() => {
  loadProjects()
  initFromRoute()
})

/** 表单形态 → PerfApiCreate/Update payload（按 bodyType 归位载体字段） */
function buildPayload() {
  const payload = {
    ...form,
    request_args_type: bodyType.value,
    api_source: form.api_source || 'manual',
  }
  switch (bodyType.value) {
    case 'none':
      payload.request_body = null
      payload.request_text = null
      break
    case 'json':
      payload.request_body = JSON.parse(jsonBodyText.value)
      payload.request_text = null
      break
    case 'xml':
    case 'raw':
      payload.request_body = null
      break
    default:
      payload.request_body = null
      payload.request_text = null
  }
  delete payload.api_code
  delete payload.created_time
  delete payload.updated_time
  delete payload.created_user
  delete payload.updated_user
  delete payload.debug_state
  delete payload.debug_time
  delete payload.version
  if (!isEdit.value) delete payload.api_id
  return payload
}

/** 保存成功后的去向：草稿队列还有剩余则进入下一条，否则返回列表 */
function afterSaved() {
  if (remainDraftCount() > 0) {
    window.$dialog?.info({
      title: '继续下一条草稿',
      content: `还有 ${remainDraftCount()} 条导入草稿待确认保存`,
      positiveText: '继 续',
      negativeText: '稍后(留在本页)',
      onPositiveClick: () => {
        const draft = shiftDraft()
        if (draft) {
          apiRow.value = null
          applyDetail(draft)
        }
      },
    })
    return
  }
  router.replace('/performance/api')
}

async function handleSave() {
  try {
    await formRef.value?.validate()
  } catch (e) {
    return
  }
  if (bodyType.value === 'json') {
    try {
      JSON.parse(jsonBodyText.value)
    } catch (e) {
      window.$message?.error('请求体 JSON 格式不合法，请修正后再保存')
      return
    }
  }
  // 空卡片直接提交会触发后端 422，早失败并定位到具体 Tab
  const blankAssert = form.assert_validators.findIndex((item) => !(item.name || '').trim())
  if (blankAssert >= 0) {
    window.$message?.error(`第 ${blankAssert + 1} 条断言缺少名称`)
    return
  }
  const blankExtract = form.extract_variables.findIndex((item) => !(item.name || '').trim())
  if (blankExtract >= 0) {
    window.$message?.error(`第 ${blankExtract + 1} 条提取缺少变量名`)
    return
  }
  try {
    saving.value = true
    const payload = buildPayload()
    if (isEdit.value) {
      await api.updatePerfApi(payload)
      window.$message?.success('保存成功')
    } else {
      const res = await api.createPerfApi(payload)
      window.$message?.success('保存成功')
      // 新增落库后补 api_id，参数化数据集卡与调试按钮随即解锁
      await loadApi(res.data?.api_id || payload.api_id)
    }
    afterSaved()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

function handleBack() {
  const remain = remainDraftCount()
  if (remain > 0) {
    window.$dialog?.warning({
      title: '放弃剩余草稿',
      content: `还有 ${remain} 条导入草稿未确认保存，返回列表将放弃这些草稿`,
      positiveText: '放弃并返回',
      negativeText: '留在本页',
      onPositiveClick: () => {
        sessionStorage.removeItem(DRAFT_QUEUE_KEY)
        router.replace('/performance/api')
      },
    })
    return
  }
  router.replace('/performance/api')
}
</script>

<style scoped>
.body-editor {
  margin-top: 12px;
}

.item-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.item-card-title {
  font-weight: 600;
}
</style>
