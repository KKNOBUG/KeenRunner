<template>
  <AppPage>
    <n-space vertical :size="24">
      <!-- 接口信息卡片 -->
      <n-card title="Basic" size="small" hoverable>
        <n-form :model="state.form" label-placement="left" label-width="auto" :rules="rules" label-align="right"
                ref="formRef">
          <n-grid :cols="24" :x-gap="24">
            <n-gi :span="5">
              <n-form-item label="请求方式" path="method">
                <n-select
                    v-model:value="state.form.method"
                    placeholder="请选择请求方式"
                    :options="methodOptions"
                    :render-label="renderMethodLabel"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="15">
              <n-form-item label="请求地址" path="url">
                <n-input
                    v-model:value="state.form.url"
                    placeholder="请输入请求地址"
                    clearable
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="4">
              <n-space>
                <n-button type="primary" @click="debugging">调试</n-button>
                <n-button type="info" @click="updateOrCreate">保存</n-button>
              </n-space>
            </n-gi>
          </n-grid>

          <n-grid :cols="24" :x-gap="24">
            <n-gi :span="5">
              <n-form-item label="优先级" path="priority">
                <n-select
                    v-model:value="state.form.priority"
                    placeholder="请选择优先级"
                    :options="priorityOptions"
                    :render-label="renderPriorityLabel"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="9">
              <n-form-item label="应用系统" path="project">
                <n-input
                    v-model:value="state.form.project"
                    placeholder="请输入应用系统"
                    clearable
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="10">
              <n-form-item label="接口名称" path="testcase_name">
                <n-input
                    v-model:value="state.form.testcase_name"
                    placeholder="请输入接口名称"
                    clearable
                />
              </n-form-item>
            </n-gi>
          </n-grid>

          <n-grid :cols="24" :x-gap="24">
            <n-gi :span="24">
              <n-form-item label="接口描述" path="description">
                <n-input
                    type="textarea"
                    v-model:value="state.form.description"
                    placeholder="请输入接口描述"
                    clearable
                    :rows="3"
                    style="min-height: 6rem;"
                />
              </n-form-item>
            </n-gi>
          </n-grid>

        </n-form>
      </n-card>

      <!-- 请求配置卡片 -->
      <n-card title="Request" size="small" hoverable>
        <n-tabs type="line" animated>
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
            />
          </n-tab-pane>
          <n-tab-pane name="params" tab="请求体">
            <template #tab>
              <n-badge :value="getBodyCount" :max="99" show-zero>
                <span>请求体</span>
              </n-badge>
            </template>
            <n-radio-group v-model:value="state.form.bodyType" name="bodyType">
              <n-space>
                <n-radio value="none">none</n-radio>
                <n-radio value="form-data">form-data</n-radio>
                <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
                <n-radio value="json">json</n-radio>
              </n-space>
            </n-radio-group>
            <n-button v-if="state.form.bodyType === 'json'" @click="formatJson" class="ml-10" size="tiny" round text
                      type="primary">美化
            </n-button>
            <div v-if="state.form.bodyType === 'form-data'">
              <KeyValueEditor
                  v-model:items="state.form.bodyParams"
                  :body-type="state.form.bodyType"
                  :enableFile="true"
                  :is-for-body="true"
              />
            </div>
            <div v-if="state.form.bodyType === 'x-www-form-urlencoded'">
              <KeyValueEditor
                  v-model:items="state.form.bodyForm"
                  :body-type="state.form.bodyType"
                  :is-for-body="true"
              />
            </div>
            <div v-if="state.form.bodyType === 'json'">
              <monaco-editor
                  v-model:value="state.form.jsonBody"
                  :options="editorOptions"
                  class="json-editor"
                  style="min-height: 300px; height: auto;"
              />
            </div>

          </n-tab-pane>
          <n-tab-pane name="variables" tab="变量">
            <template #tab>
              <n-badge :value="state.form.variables.length" :max="99" show-zero>
                <span>变量</span>
              </n-badge>
            </template>
            <KeyValueEditor
                v-model:items="state.form.variables"
                :body-type="'none'"
                :is-for-body="false"
            />
          </n-tab-pane>
        </n-tabs>
      </n-card>

      <!-- 响应结果卡片 -->
      <n-card title="Response" size="small" hoverable>
        <div v-if="response">
          <n-space vertical :size="12">
            <div>
              <n-tag :type="responseStatusType" round>
                状态: {{ response.status }} {{ response.statusText }}
              </n-tag>
              <n-tag :type="sizeTagType" round>
                大小: {{ response.size }}
              </n-tag>
              <n-tag :type="durationTagType" round>
                耗时: {{ response.duration }}ms
              </n-tag>
            </div>
            <n-tabs type="line">
              <n-tab-pane name="body" tab="Body">
                <div v-if="isJsonResponse">
                  <monaco-editor
                      v-model:value="response.data"
                      :options="responseEditorOptions"
                      class="json-editor"
                      readonly
                      style="height: 400px"
                  />
                </div>
              </n-tab-pane>
              <n-tab-pane name="headers" tab="Headers">
                <KeyValueView :items="response.headers"/>
              </n-tab-pane>
              <n-tab-pane v-if="response.cookies" name="cookies" tab="Cookies">
                <n-data-table
                    :columns="cookieColumns"
                    :data="cookieData"
                    :bordered="false"
                />
              </n-tab-pane>
            </n-tabs>
          </n-space>
        </div>
        <div v-else class="empty-response">
          <n-empty description="点击调试按钮发送请求查看响应结果"/>
        </div>
      </n-card>

    </n-space>
  </AppPage>
</template>

<script setup>
import {computed, h, reactive, ref} from 'vue'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import {NCode, NTag} from 'naive-ui'
import api from "@/api";
import AppPage from "@/components/page/AppPage.vue";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";
import MonacoEditor from "@/components/monaco/index.vue";
import { useUserStore } from '@/store';


// 注册JSON高亮
hljs.registerLanguage('json', json)
const formRef = ref(null);


const editorOptions = {
  theme: 'vs-dark',
  language: 'json',
  automaticLayout: true,
  minimap: {
    enabled: true
  },
  folding: true,
  foldingStrategy: 'auto',
  scrollBeyondLastLine: false,
  fontSize: 14,
  lineNumbers: 'on',
  roundedSelection: false,
  readOnly: false,
  cursorStyle: 'line',
  tabSize: 4,
  wordWrap: 'on'
}

// 键值对查看组件
const KeyValueView = {
  props: ['items'],
  template: `
    <div class="key-value-view">
    <div v-for="(item, index) in items" :key="index" class="view-row">
      <n-text strong class="key">{{ item.key }}:</n-text>
      <n-text class="value">{{ item.value }}</n-text>
    </div>
    </div>
  `
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
  project: [
    {
      required: true,
      message: '请选择应用系统',
      trigger: 'blur'
    }
  ],
  testcase_name: [
    {
      required: true,
      message: '请输入测试案例名称',
      trigger: 'blur'
    }
  ],
  priority: [
    {
      required: true,
      message: '请选择测试案例优先级',
      trigger: 'blur'
    }
  ],
  description: [
    {
      required: false,
      message: '请输入测试案例描述',
      trigger: 'blur'
    }
  ]
}

// 状态管理
const state = reactive({
  form: {
    url: 'http://192.168.94.231:8518/base/auth/access_token',
    method: 'POST',
    headers: [
      {key: 'Accept', value: '*/*'},
      {key: 'Accept-Encoding', value: 'gzip, deflate, br'},
      {key: 'Connection', value: 'keep-alive'},
      {key: 'Content-Type', value: 'application/json'},
    ],
    params: [],
    variables: [],
    bodyType: 'none',
    bodyForm: [],
    bodyParams: [],
    jsonBody: '{"password": "123456", "username": "admin"}',
    priority: '中',
    project: 'cs',
    testcase_name: 'cs',
    description: '',
    module: 'cs'
  }
})

// 响应结果
const response = ref(null)

// 请求方式下拉框
const methodOptions = [
  {label: 'GET', value: 'GET', color: '#49CC90'},
  {label: 'POST', value: 'POST', color: '#61AFFE'},
  {label: 'PUT', value: 'PUT', color: '#FFA500'},
  {label: 'DELETE', value: 'DELETE', color: '#F4511E'}
]
const renderMethodLabel = (option) => {
  return h(
      'span',
      {style: {color: option.color, fontWeight: '600'}},
      option.label
  )
}


// 优先级下拉框
const priorityOptions = [
  {label: '低', value: '低', color: '#49CC90'},
  {label: '中', value: '中', color: '#61AFFE'},
  {label: '高', value: '高', color: '#FFA500'},
  {label: '危', value: '危', color: '#F4511E'}
]
const renderPriorityLabel = (option) => {
  return h(
      'span',
      {style: {color: option.color, fontWeight: '600'}},
      option.label
  )
}
// 请求体属性数量计算
const getBodyCount = computed(() => {
  switch (state.form.bodyType) {
    case 'form-data':
      return state.form.bodyParams.length
    case 'x-www-form-urlencoded':
      return state.form.bodyForm.length
    case 'json':
      return state.form.jsonBody ? 1 : 0 // JSON内容存在则计1
    default:
      return 0
  }
})


const isJsonResponse = computed(() => {
  return response.value?.headers?.['Content-Type']?.includes('json')
})

const formattedResponse = computed(() => {
  try {
    return JSON.stringify(response.value.data, null, 2)
  } catch {
    return response.value.data
  }
})

const headerColumns = [
  { title: 'Header Name', key: 'name' },
  { title: 'Value', key: 'value' }
]

const headerData = computed(() => {
  return Object.entries(response.value?.headers || {}).map(([name, value]) => ({
    name,
    value
  }))
})

const cookieColumns = [
  { title: 'Cookie Name', key: 'name' },
  { title: 'Value', key: 'value' }
]

const cookieData = computed(() => {
  return Object.entries(response.value?.cookies || {}).map(([name, value]) => ({
    name,
    value
  }))
})

const responseStatusType = computed(() => {
  if (!response.value) return 'default'
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

// 更新响应编辑器配置
const responseEditorOptions = reactive({
  ...editorOptions,
  readOnly: true,
  minimap: {
    enabled: true
  }
})
const debugging = async () => {
  const valid = await formRef.value.validate();
  if (!valid) {
    $message.warning("请填写必填字段");
    return;
  }

  try {
    // 构造请求参数
    const params = state.form.params
        .filter(item => item.key)
        .reduce((acc, { key, value }) => {
          acc[key] = value;
          return acc;
        }, {});

    // 处理不同请求体类型
    let formData = null;
    let jsonBody = null;

    switch (state.form.bodyType) {
      case 'form-data':
        formData = state.form.bodyParams.reduce((acc, { key, value, type }) => {
          if (key) {
            // 处理文件类型
            if (type === 'file' && value instanceof File) {
              acc[key] = {
                file: value,
                filename: value.name
              };
            } else {
              acc[key] = value;
            }
          }
          return acc;
        }, {});
        break;
      case 'x-www-form-urlencoded':
        formData = state.form.bodyForm.reduce((acc, { key, value }) => {
          if (key) acc[key] = value;
          return acc;
        }, {});
        break;
      case 'json':
        try {
          jsonBody = JSON.parse(state.form.jsonBody || '{}');
        } catch (e) {
          $message.error('JSON格式错误，请检查输入');
          return;
        }
        break;
    }

    const data = {
      url: state.form.url,
      method: state.form.method,
      headers: state.form.headers.reduce((acc, { key, value }) => {
        if (key) acc[key] = value;
        return acc;
      }, {}),
      params: Object.keys(params).map(k => `${k}=${params[k]}`).join('&'),
      json_body: jsonBody,
      form_data: formData,
      priority: state.form.priority,
      project: state.form.project,
      module: state.form.project,
      testcase_name: state.form.testcase_name,
      description: state.form.description,
      variables: state.form.variables.reduce((acc, { key, value }) => {
        if (key) acc[key] = value;
        return acc;
      }, {}),
      created_user: useUserStore().username,
    };

    const responseData = await api.debugging(data);

    if (responseData.code === '000000') {
      response.value = responseData.data;
      // 自动格式化JSON
      if (isJsonResponse.value) {
        response.value.data = formattedResponse.value;
      }
      $message.success('调试成功');
    } else {
      $message.error(`请求失败：${responseData.message}`);
    }
  } catch (error) {
    $message.error(`调试失败：${error.message}`);
  }
};

const updateOrCreate = async () => {
  const userStore = useUserStore(); // 获取用户状态管理 store
  const currentUser = userStore.username; // 获取当前登录用户信息
  const valid = await formRef.value.validate();
  if (!valid){
    $message.warning("请填写必填字段")
    return;
  }
  try {
    // 构造请求数据
    const data = {
      url: state.form.url,
      method: state.form.method,
      headers: state.form.headers.reduce((acc, {key, value}) => {
        if (key) acc[key] = value
        return acc
      }, {}),
      params: JSON.stringify(state.form.params.reduce((acc, {key, value}) => {
        if (key) acc[key] = value
        return acc
      }, {})),
      json_body: state.form.bodyType === 'json' ? JSON.parse(state.form.jsonBody || '{}') : null,
      form_data: state.form.bodyType === 'form-data' ? state.form.bodyParams.reduce((acc, {key, value}) => {
        if (key) acc[key] = value
        return acc
      }, {}) : null,
      priority: state.form.priority,
      project: state.form.project,
      module: state.form.project,
      testcase_name: state.form.testcase_name,
      description: state.form.description,
      created_user: currentUser,
      updated_user: currentUser,
      variables: state.form.variables.reduce((acc, {key, value}) => {
        if (key) acc[key] = value
        return acc
      }, {})
    }

    // 调用 api 中的保存接口
    console.log("请求数据:", data);
    const backend_response = await api.updateOrCreate(data);
    $message.success('保存成功');
  } catch (error) {
    console.error('请求失败：', error);
    $message.error(error.message);
  }
}

const formatJson = () => {
  const inputJson = state.form.jsonBody.trim();
  if (inputJson === '') {
    $message.warning('输入的 JSON 为空，请输入有效的 JSON 内容。');
    return;
  }

  try {
    const jsonData = JSON.parse(inputJson);
    state.form.jsonBody = JSON.stringify(jsonData, null, 2);
  } catch (parseError) {
    try {
      // 尝试使用 eval 处理可能不规范的 JSON
      const jsonData = eval('(' + inputJson + ')');
      state.form.jsonBody = JSON.stringify(jsonData, null, 2);
    } catch (evalError) {
      $message.error(`JSON 格式化失败，请检查输入的 JSON 格式是否正确。详细错误信息：${parseError.message}`);
      console.error('JSON 格式化失败，解析错误:', parseError);
      console.error('JSON 格式化失败，eval 处理也失败:', evalError);
    }
  }
}

</script>

<style scoped>
.key-value-editor .key-value-row {
  display: grid;
  grid-template-columns: 1fr 1fr 100px;
  gap: 12px;
  margin-bottom: 12px;
}

.json-editor {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
}

.key-value-view .view-row {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.key-value-view .key {
  min-width: 200px;
  color: #1f2937;
}

.key-value-view .value {
  color: #4b5563;
  word-break: break-all;
}

.empty-response {
  padding: 40px 0;
  text-align: center;
}

.json-editor {
  border: 1px solid #eee;
  border-radius: 15px;
  overflow: hidden;
  transition: height 0.3s ease;
}

/* 确保编辑器容器可以自适应内容高度 */
.json-editor :deep(.monaco-editor) {
  min-height: 90px;
  height: auto !important;
}
</style>
