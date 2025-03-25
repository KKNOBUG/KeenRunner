<template>
  <AppPage>
    <!-- src/views/InterfaceManager.vue -->
    <n-layout has-sider>
      <!-- 左侧导航 -->
      <n-layout-sider bordered width="240">
        <n-menu
            :options="menuOptions"
            v-model:value="selectedKey"
            :root-indent="16"
        />
      </n-layout-sider>

      <!-- 中间主内容 -->
      <n-layout-content>
        <div class="request-container">
          <!-- 请求行 -->
          <div class="request-line">
            <n-select
                v-model:value="method"
                :options="methodOptions"
                style="width: 120px"
            />
            <n-input
                v-model:value="url"
                placeholder="输入请求URL"
                class="url-input"
            />
            <n-button @click="sendRequest" type="primary" class="send-btn">
              发送
            </n-button>
          </div>

          <!-- 参数选项卡 -->
          <n-tabs type="line" class="param-tabs">
            <n-tab-pane name="params" tab="Params">
              <key-value-table
                  v-model:data="queryParams"
                  show-bulk-edit
              />
            </n-tab-pane>

            <n-tab-pane name="headers" tab="Headers">
              <key-value-table
                  v-model:data="headers"
                  :show-description="true"
              />
            </n-tab-pane>

            <n-tab-pane name="body" tab="Body">
              <n-radio-group v-model:value="bodyType" name="bodytype">
                <n-radio value="none">none</n-radio>
                <n-radio value="form-data">form-data</n-radio>
                <n-radio value="json">JSON</n-radio>
              </n-radio-group>

              <div v-if="bodyType === 'form-data'" class="body-section">
                <key-value-table
                    v-model:data="formData"
                    :enable-file="true"
                />
              </div>

              <n-input
                  v-if="bodyType === 'json'"
                  v-model:value="jsonBody"
                  type="textarea"
                  rows="10"
                  placeholder="输入JSON内容"
              />
            </n-tab-pane>
          </n-tabs>
        </div>

        <!-- 响应区域 -->
        <div class="response-container">
          <!-- 状态栏 -->
          <div class="status-bar">
            <n-space>
              <n-tag type="info">状态: {{ response.status }}</n-tag>
              <n-text depth="3">时间: {{ response.duration }}ms</n-text>
              <n-text depth="3">大小: {{ response.size }}B</n-text>
            </n-space>
          </div>

          <!-- 响应内容选项卡 -->
          <n-tabs type="line">
            <n-tab-pane name="preview" tab="预览">
              <n-code
                  :code="formattedResponse"
                  language="json"
                  show-line-numbers
              />
            </n-tab-pane>
            <n-tab-pane name="raw" tab="原数据">
              <pre>{{ rawResponse }}</pre>
            </n-tab-pane>
          </n-tabs>
        </div>
      </n-layout-content>
    </n-layout>

  </AppPage>
</template>
<script setup>
import { ref, computed } from 'vue'
import { useMessage } from 'naive-ui'
// 左侧菜单配置
const menuOptions = [
  {
    label: '测试平台接口',
    key: 'test-platform',
    children: [
      { label: '获取用户列表', key: 'getUsers' },
      { label: '添加用户', key: 'addUser' },
      { label: '登录接口', key: 'login' }
    ]
  },
  {
    label: '第三方接口',
    key: 'third-party',
    children: [
      { label: '入会接口', key: 'join' },
      { label: '出会接口', key: 'leave' }
    ]
  }
]
// 组件定义
const KeyValueTable = {
  props: ['data', 'showBulkEdit', 'showDescription', 'enableFile'],
  template: `
    <n-data-table
      :columns="columns"
      :data="data"
      :pagination="false"
    >
      <template #action="{ index }">
        <n-button text @click="removeRow(index)">删除</n-button>
      </template>
    </n-data-table>
  `,
  setup(props) {
    const columns = computed(() => [
      { title: '键', key: 'key' },
      { title: '值', key: 'value' },
      ...(props.showDescription ? [{ title: '描述', key: 'description' }] : []),
      { title: '操作', key: 'actions', render: 'action' }
    ])
    return { columns }
  }
}

// 数据逻辑
const method = ref('GET')
const url = ref('http://route.showapi.com/2217-27')
const methodOptions = ['GET', 'POST', 'PUT', 'DELETE'].map(v => ({ label: v, value: v }))

const queryParams = ref([
  { key: 'showapi_appid', value: '693838', description: '' },
  { key: 'showapi_sign', value: '88d146ca828149a3bfa15551433c9c7d', description: '' }
])

const headers = ref([])
const bodyType = ref('none')
const formData = ref([])
const jsonBody = ref('')

const response = ref({
  status: '',
  duration: 0,
  size: 0,
  data: null
})

const rawResponse = computed(() => JSON.stringify(response.value.data, null, 2))
const formattedResponse = computed(() => {
  if (!response.value.data) return ''
  return JSON.stringify(response.value.data, null, 2)
})

async function sendRequest() {
  try {
    const startTime = Date.now()

    const res = await fetch(buildUrl(), {
      method: method.value,
      headers: Object.fromEntries(headers.value.map(h => [h.key, h.value])),
      body: buildBody()
    })

    const duration = Date.now() - startTime
    const data = await res.json()

    response.value = {
      status: `${res.status} ${res.statusText}`,
      duration,
      size: JSON.stringify(data).length,
      data
    }
  } catch (error) {
    useMessage().error('请求失败: ' + error.message)
  }
}

function buildUrl() {
  const urlObj = new URL(url.value)
  queryParams.value.forEach(param => {
    urlObj.searchParams.append(param.key, param.value)
  })
  return urlObj.toString()
}

function buildBody() {
  if (bodyType.value === 'form-data') {
    const form = new FormData()
    formData.value.forEach(item => {
      form.append(item.key, item.value)
    })
    return form
  }
  if (bodyType.value === 'json') return jsonBody.value
  return null
}
</script>


<style scoped>
.request-container {
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.request-line {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.url-input {
  flex: 1;
}

.send-btn {
  width: 100px;
}

.param-tabs {
  margin-top: 20px;
}

.response-container {
  padding: 20px;
}

.status-bar {
  padding: 10px;
  background: #f8f8f8;
  border-radius: 4px;
  margin-bottom: 20px;
}

.n-code {
  max-height: 500px;
  overflow: auto;
}
</style>
