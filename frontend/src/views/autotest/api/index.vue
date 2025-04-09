<template>
  <AppPage>
    <n-space vertical :size="24">
      <!-- 接口信息卡片 -->
      <n-card title="Basic" size="small" hoverable>
        <n-form
            :rules="rules"
            :model="state.form"
            label-width="auto"
            label-align="right"
            label-placement="left"
            ref="formRef"
        >
          <!-- 测试用例调试信息 -->
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
                    @blur="handleUrlBlur"
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

          <!-- 测试用例应用信息 -->
          <n-grid :cols="24" :x-gap="24">
            <n-gi :span="8">
              <n-form-item label="应用系统" path="project_id">
                <n-select
                    v-model:value="state.form.project_id"
                    placeholder="请输入应用系统"
                    :options="projectOptions"
                    @update:value="filterModulesAndEnvs"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="应用模块" path="module_id">
                <n-select
                    v-model:value="state.form.module_id"
                    placeholder="请选择应用模块"
                    :options="moduleOptions"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="应用环境" path="env_id">
                <n-select
                    v-model:value="state.form.env_id"
                    placeholder="请选择应用环境"
                    :options="envOptions"
                />
              </n-form-item>
            </n-gi>

          </n-grid>

          <!-- 测试用例基础信息 -->
          <n-grid :cols="24" :x-gap="24">
            <n-gi :span="8">
              <n-form-item label="用例名称" path="testcase_name">
                <n-input
                    v-model:value="state.form.testcase_name"
                    placeholder="请输入测试用例名称"
                    clearable
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="优先等级" path="priority">
                <n-select
                    v-model:value="state.form.priority"
                    placeholder="请选择优等级"
                    :options="priorityOptions"
                    :render-label="renderPriorityLabel"
                />
              </n-form-item>
            </n-gi>
            <n-gi :span="8">
              <n-form-item label="用例标签" path="testcase_tags">
                <n-input
                    v-model:value="state.form.testcase_tags"
                    placeholder="请输入测试用例标签"
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
                    :rows="5"
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
          <n-tab-pane name="request_headers" tab="请求头">
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
          <n-tab-pane name="request_body" tab="请求体">
            <template #tab>
              <n-badge :value="getBodyCount" :max="99" show-zero>
                <span>请求体</span>
              </n-badge>
            </template>
            <n-radio-group v-model:value="state.form.request_body_type" name="request_body_type">
              <n-space>
                <n-radio value="none">none</n-radio>
                <n-radio value="params">params</n-radio>
                <n-radio value="form-data">form-data</n-radio>
                <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
                <n-radio value="json">json</n-radio>
              </n-space>
            </n-radio-group>
            <n-button v-if="state.form.request_body_type === 'json'" @click="formatJson" class="ml-10" size="tiny" round
                      text
                      type="primary">美化
            </n-button>
            <template v-if="state.form.request_body_type === 'params'">
              <KeyValueEditor
                  v-model:items="state.form.params"
                  :body-type="state.form.request_body_type"
                  :is-for-body="true"
              />
            </template>
            <template v-if="state.form.request_body_type === 'form-data'">
              <KeyValueEditor
                  v-model:items="state.form.form_data"
                  :body-type="state.form.request_body_type"
                  :enableFile="true"
                  :is-for-body="true"
              />
            </template>
            <template v-if="state.form.request_body_type === 'x-www-form-urlencoded'">
              <KeyValueEditor
                  v-model:items="state.form.x_www_form_urlencoded"
                  :body-type="state.form.request_body_type"
                  :is-for-body="true"
              />
            </template>
            <template v-if="state.form.request_body_type === 'json'">
              <monaco-editor
                  v-model:value="state.form.json_body"
                  :options="monacoEditorOptions(false)"
                  class="json-editor"
                  style="min-height: 400px; height: auto;"
              />
            </template>

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
      <n-card ref="debugResultRef" title="调试结果" size="small" hoverable>
        <!-- 在卡片标题右侧添加响应状态信息 -->
        <template #header-extra>
          <n-space v-if="response" align="center">
            <n-tag :type="responseStatusType" round size="small">Status: {{ response.status }}</n-tag>
            <n-tag :type="durationTagType" round size="small">Time: {{ response.duration }}ms</n-tag>
            <n-tag :type="sizeTagType" round size="small">Size: {{ response.size }}</n-tag>
            <n-tag round>Type: {{ contentType }}</n-tag>
          </n-space>
        </template>
        <n-tabs type="line" animated>
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
                <n-collapse-item title="Body" name="responseBody">
                  <n-space vertical :size="12">
                    <div v-if="isJsonResponse">
                      <monaco-editor
                          v-model:value="response.data"
                          :options="monacoEditorOptions(true)"
                          class="json-editor"
                          style="min-height: 400px; height: auto;"
                      />
                    </div>
                    <n-code
                        v-else
                        :code="typeof response.data === 'object'? JSON.stringify(response.data) : response.data || ''"
                        :language="responseLanguage"
                        show-line-numbers
                        class="response-code"
                    />
                  </n-space>
                </n-collapse-item>
              </n-collapse>
            </n-space>
          </n-tab-pane>

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
                  <div v-if="isJsonRequest">
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
          <n-tab-pane name="extract" tab="数据提取">数据提取</n-tab-pane>
          <n-tab-pane name="assert" tab="断言结果">断言结果</n-tab-pane>
          <n-tab-pane name="logs" tab="执行日志">执行日志</n-tab-pane>
        </n-tabs>
      </n-card>
    </n-space>
  </AppPage>
</template>

<script setup>
import {computed, h, onMounted, reactive, ref} from 'vue'
import {NDataTable, NDescriptions, NDescriptionsItem, NTag, NText} from 'naive-ui'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import api from "@/api";
import AppPage from "@/components/page/AppPage.vue";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";
import MonacoEditor from "@/components/monaco/index.vue";
import {useUserStore} from '@/store';


// 注册JSON高亮
hljs.registerLanguage('json', json)
const formRef = ref(null);
const projectOptions = ref([])  // 应用系统下拉选项
const moduleOptions = ref([])   // 应用模块下拉选项
const envOptions = ref([])     // 应用环境下拉选项
const response = ref(null) // 存储调试响应结果
const requestInfo = ref({  // 存储请求的详细信息
  url: '',
  method: '',
  headers: {},
  request_body_type: 'none',
  json_body: ''
})


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
  project_id: [
    {
      required: true,
      type: 'number',
      message: '请选择应用系统',
      trigger: ['blur', 'change']
    }
  ],
  module_id: [
    {
      required: false,
      type: 'number',
      message: '请选择应用模块',
      trigger: 'blur'
    }
  ],
  env_id: [
    {
      required: true,
      type: 'number',
      message: '请选择应用环境',
      trigger: ['blur', 'change']
    }
  ],
  testcase_name: [
    {
      required: true,
      message: '请输入测试用例名称',
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
  testcase_tags: [
    {
      required: false,
      message: '请输入测试用例标签',
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

/* 表单状态管理 */
const state = reactive({
  form: {
    url: 'http://192.168.94.229:8518/base/auth/access_token',
    method: 'POST',
    headers: [
      {key: 'Accept', value: '*/*'},
      {key: 'Accept-Encoding', value: 'gzip, deflate, br'},
      {key: 'Connection', value: 'keep-alive'},
      {key: 'Content-Type', value: '*/*'},
    ],
    request_body_type: 'json',
    params: [],
    form_data: [],
    x_www_form_urlencoded: [],
    json_body: '{"password": "123456", "username": "admin"}',
    priority: '低',
    testcase_name: '测试',
    testcase_tags: '',
    description: '测试',
    project_id: 1,
    module_id: 1,
    env_id: 1,
    variables: [],
  }
})


/* 生命周期钩子 */
onMounted(async () => {
  try {
    // 初始化加载项目列表
    const response = await api.getProjectList({page: 1, page_size: 1000})
    projectOptions.value = response.data.map(item => ({label: item.name, value: Number(item.id)}))
  } catch (error) {
    $message.error(`错误：\n${error.response?.data?.message || error.message}`)
  }
})

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

/* 根据项目ID过滤模块和环境 */
const filterModulesAndEnvs = async (projectId) => {
  try {
    // 获取模块列表
    const moduleResponse = await api.getModuleList({page: 1, page_size: 999, project_id: projectId})
    moduleOptions.value = moduleResponse.data.map(item => ({label: item.name, value: Number(item.id)}))
    // 获取环境列表
    const envResponse = await api.getEnvList({page: 1, page_size: 999, project_id: projectId})
    envOptions.value = envResponse.data.map(item => ({label: item.name, value: Number(item.id)}))
  } catch (error) {
    $message.error(`错误：\n${error.response?.data?.message || error.message}`)
  }
}

/* 请求体数量计算 */
const getBodyCount = computed(() => {
  switch (state.form.request_body_type) {
    case 'params':
      return state.form.params.length
    case 'form-data':
      return state.form.form_data.length
    case 'x-www-form-urlencoded':
      return state.form.x_www_form_urlencoded.length
    case 'json':
      return state.form.json_body.trim() ? 1 : 0 // JSON内容存在则计1
    default:
      return 0
  }
})

watch(
    () => state.form.json_body,
    (newVal) => {
      if (newVal?.trim() && !['json'].includes(state.form.request_body_type)) {
        state.form.request_body_type = 'json'
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
    wordWrap: 'off',
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


// 请求类型
const contentType = computed(() => {
  return response.value?.headers?.['Content-Type']?.split(';')[0] || 'text/plain'
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
    POST: 'info',
    PUT: 'warning',
    DELETE: 'error'
  }[method] || 'default'
})


const requestBodyType = computed(() => {
  const typeMap = {
    'form-data': 'Form Data',
    'x-www-form-urlencoded': 'Form URL Encoded',
    'json': 'JSON'
  }
  return typeMap[requestInfo.value.request_body_type] || 'Params'
})

const isJsonRequest = computed(() => requestInfo.value.request_body_type === 'json')

const formattedRequestJson = computed(() => {
  try {
    return JSON.stringify(JSON.parse(requestInfo.value.json_body), null, 4)
  } catch {
    return requestInfo.value.json_body
  }
})

const requestBodyData = computed(() => {
  switch (requestInfo.value.request_body_type) {
    case 'params':
      return state.form.form_data.filter(item => item.key)
    case 'form-data':
      return state.form.form_data.filter(item => item.key)
    case 'x-www-form-urlencoded':
      return state.form.x_www_form_urlencoded.filter(item => item.key)
    default:
      return []
  }
})


const debugResultRef = ref(null)

const handleParamsRequest = (params) => {
  return params
      .filter(item => item.key)
      .reduce((acc, {key, value}) => {
        acc[key] = value;
        return acc;
      }, {});
}

const handleFormDataRequest = async (formData) => {
  const processedData = {};
  for (const item of formData) {
    if (item.key) {
      if (item.type === 'file' && item.value instanceof File) {
        // 处理文件上传
        const reader = new FileReader();
        const fileContent = await new Promise((resolve) => {
          reader.onload = () => resolve(reader.result);
          reader.readAsDataURL(item.value);
        });

        processedData[item.key] = {
          file: fileContent,
          filename: item.value.name,
          type: item.value.type,
          size: item.value.size
        };
      } else {
        // 处理普通字段
        processedData[item.key] = item.value;
      }
    }
  }
  return processedData;
}

const handleUrlEncodedRequest = (data) => {
  return data.reduce((acc, {key, value}) => {
    if (key) acc[key] = value;
    return acc;
  }, {});
}

const handleJsonRequest = (jsonString) => {
  try {
    return JSON.parse(jsonString || '{}');
  } catch (e) {
    throw new Error('JSON格式错误，请检查输入');
  }
}

const processHeaders = (headers) => {
  return headers.reduce((acc, {key, value}) => {
    if (key) acc[key] = value;
    return acc;
  }, {});
}

const processVariables = (variables) => {
  return variables.reduce((acc, {key, value}) => {
    if (key) acc[key] = value;
    return acc;
  }, {});
}

// ----------------------

// Function to parse query parameters from a URL
const parseQueryParams = (url) => {
  const params = new URLSearchParams(url.split('?')[1] || '');
  return Array.from(params.entries()).map(([key, value]) => ({
    key: decodeURIComponent(key),
    value: decodeURIComponent(value)
  }));
};

// Function to update the URL based on params
const updateUrlFromParams = () => {
  const url = new URL(state.form.url.split('?')[0], window.location.origin);
  state.form.params.forEach(({key, value}) => {
    if (key) {
      url.searchParams.set(encodeURIComponent(key), encodeURIComponent(value));
    }
  });
  state.form.url = url.toString(); // 移除 decodeURIComponent
};

// Watcher to handle changes in the method
watch(
    () => state.form.method,
    (newMethod) => {
      if (newMethod === 'GET') {
        state.form.params = parseQueryParams(state.form.url);
      }
    },
    {immediate: true}
);

// Watcher to handle changes in params
watch(
    () => state.form.params,
    (newParams) => {
      if (state.form.method === 'GET') {
        updateUrlFromParams();
      }
    },
    {deep: true}
);

// Function to handle URL input blur event
const handleUrlBlur = () => {
  if (state.form.method === 'GET') {
    state.form.params = parseQueryParams(state.form.url);
  }
};


// -----
const downloadFile = (blob, filename) => {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

const extractFilename = (contentDisposition) => {
  const match = contentDisposition.match(/filename\*=(?:UTF-8'')?(.+)/i);
  if (match) {
    return decodeURIComponent(match[1]);
  }
  // 获取当前日期和时间
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0'); // 月份从0开始
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}${month}${day}${hours}${minutes}${seconds}_DOWNLOAD`;
};
// ----------------------


/* 调试方法 */
const debugging = async () => {
  const userStore = useUserStore();
  const currentUser = userStore.username;
  const valid = await formRef.value.validate();
  if (!valid) {
    $message.warning("请填写必填字段");
    return;
  }

  try {
    // 保存请求信息用于显示
    requestInfo.value = {
      method: state.form.method,
      url: state.form.url,
      headers: processHeaders(state.form.headers),
      request_body_type: state.form.request_body_type,
      json_body: state.form.json_body
    };

    // 构造请求数据，匹配后端 ApiTestCaseCreate 模型
    const data = {
      url: state.form.url,
      method: state.form.method,
      headers: processHeaders(state.form.headers),

      // 根据请求体类型设置对应的字段
      params: state.form.request_body_type === 'params' ?
          handleParamsRequest(state.form.params) : {},

      json_body: state.form.request_body_type === 'json' ?
          handleJsonRequest(state.form.json_body) : {},

      form_data: state.form.request_body_type === 'form-data' ?
          await handleFormDataRequest(state.form.form_data) : {},

      x_www_form_urlencoded: state.form.request_body_type === 'x-www-form-urlencoded' ?
          handleUrlEncodedRequest(state.form.x_www_form_urlencoded) : {},

      // 测试用例基本信息
      project_id: state.form.project_id,
      module_id: state.form.module_id,
      env_id: state.form.env_id,
      priority: state.form.priority,
      testcase_name: state.form.testcase_name,
      testcase_tags: state.form.testcase_tags,
      description: state.form.description,

      // 变量和用户信息
      variables: processVariables(state.form.variables),
      created_user: currentUser,
      updated_user: currentUser,
    };

    const responseData = await api.debugging(data);

    if (responseData.code === '000000') {
      response.value = responseData.data;

      // 检查响应是否为文件类型
      const contentType = response.value.headers['Content-Type'];
      if (contentType && contentType.includes('application/octet-stream')) {
        const blob = new Blob([response.value.data], { type: contentType });
        const contentDisposition = response.value.headers['Content-Disposition'];
        const filename = extractFilename(contentDisposition);
        downloadFile(blob, filename);
      } else {
        // 自动格式化JSON
        if (isJsonResponse.value) {
          response.value.data = formattedResponse.value;
        }
        $message.success('调试成功');
      }

      // 滚动到调试结果区域
      nextTick(() => {
        debugResultRef.value?.$el?.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      });
    } else {
      $message.error(`请求失败：${responseData.message}`);
    }
  } catch (error) {
    $message.error(`调试失败：${error.message}`);
  }
};

const updateOrCreate = async () => {
  // 获取当前登录用户信息
  const userStore = useUserStore();
  const currentUser = userStore.username;

  // 表单验证
  await formRef.value?.validate();

  try {
    // 构造请求数据
    const data = {
      url: state.form.url,
      method: state.form.method,
      // 处理 headers，转换为对象格式
      headers: state.form.headers.reduce((acc, {key, value}) => {
        if (key) acc[key] = value;
        return acc;
      }, {}),

      // 根据请求体类型设置对应的参数
      params: state.form.request_body_type === 'params' ?
          handleParamsRequest(state.form.params) : {},

      json_body: state.form.request_body_type === 'json' ?
          handleJsonRequest(state.form.json_body) : {},

      form_data: state.form.request_body_type === 'form-data' ?
          state.form.form_data.reduce((acc, {key, value}) => {
            if (key) acc[key] = value;
            return acc;
          }, {}) : {},

      x_www_form_urlencoded: state.form.request_body_type === 'x-www-form-urlencoded' ?
          state.form.x_www_form_urlencoded.reduce((acc, {key, value}) => {
            if (key) acc[key] = value;
            return acc;
          }, {}) : {},

      // 基本信息
      priority: state.form.priority,
      project_id: state.form.project_id,
      module_id: state.form.module_id,
      env_id: state.form.env_id,
      testcase_name: state.form.testcase_name,
      testcase_tags: state.form.testcase_tags,
      description: state.form.description,

      // 变量和用户信息
      variables: state.form.variables.reduce((acc, {key, value}) => {
        if (key) acc[key] = value;
        return acc;
      }, {}),
      created_user: currentUser,
      updated_user: currentUser,
    };

    // 调用 api 中的保存接口
    console.log("请求数据:", data);
    const backend_response = await api.updateOrCreate(data);
    $message.success('保存成功');
  } catch (error) {
    console.error('请求失败：', error);
    $message.error(error.message);
  }
};


const formatJson = () => {
  const inputJson = state.form.json_body.trim();
  if (inputJson === '') {
    $message.warning('输入的 JSON 为空，请输入有效的 JSON 内容。');
    return;
  }

  try {
    const jsonData = JSON.parse(inputJson);
    state.form.json_body = JSON.stringify(jsonData, null, 2);
  } catch (parseError) {
    try {
      // 尝试使用 eval 处理可能不规范的 JSON
      const jsonData = eval('(' + inputJson + ')');
      state.form.json_body = JSON.stringify(jsonData, null, 2);
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

.json-editor {
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  border-radius: 15px;
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

:root {
  --pre-bg-color: #f4f4f4;
  --pre-text-color: #333;
}

@media (prefers-color-scheme: dark) {
  :root {
    --pre-bg-color: #222;
    --pre-text-color: #eee;
  }
}

pre {
  background-color: var(--pre-bg-color);
  color: var(--pre-text-color);
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
