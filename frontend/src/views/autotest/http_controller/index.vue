<template>
  <div>
    <n-space style="margin-bottom: 16px;">
      <n-select
          v-model:value="form.method"
          :options="methodOptions"
          style="width: 120px;"
      />
      <n-input
          v-model:value="form.url"
          placeholder="请输入请求地址"
          clearable
          style="flex: 1;"
      />
      <n-button type="primary" @click="$emit('debug')">调试</n-button>
    </n-space>

    <n-form-item label="请求名称:">
      <n-input v-model:value="form.name" placeholder="请输入请求名称" />
    </n-form-item>

    <n-tabs type="line" animated>
      <n-tab-pane name="request_body" tab="请求体">
        <n-radio-group v-model:value="form.request_body_type" name="request_body_type">
          <n-space>
            <n-radio value="none">none</n-radio>
            <n-radio value="form-data">form-data</n-radio>
            <n-radio value="x-www-form-urlencoded">x-www-form-urlencoded</n-radio>
            <n-radio value="json">json</n-radio>
            <n-radio value="raw">raw</n-radio>
          </n-space>
        </n-radio-group>
        <template v-if="form.request_body_type === 'json'">
          <monaco-editor
              v-model:value="form.json_body"
              :options="monacoEditorOptions"
              class="json-editor"
              style="min-height: 400px; height: auto; margin-top: 12px;"
          />
        </template>
        <template v-else-if="form.request_body_type === 'form-data'">
          <KeyValueEditor
              v-model:items="form.form_data"
              :body-type="form.request_body_type"
              :enableFile="true"
              :is-for-body="true"
          />
        </template>
        <template v-else-if="form.request_body_type === 'x-www-form-urlencoded'">
          <KeyValueEditor
              v-model:items="form.x_www_form_urlencoded"
              :body-type="form.request_body_type"
              :is-for-body="true"
          />
        </template>
      </n-tab-pane>
      <n-tab-pane name="request_headers" tab="请求头">
        <KeyValueEditor
            v-model:items="form.headers"
            :body-type="'none'"
            :is-for-body="false"
        />
      </n-tab-pane>
      <n-tab-pane name="variables" tab="变量">
        <KeyValueEditor
            v-model:items="form.variables"
            :body-type="'none'"
            :is-for-body="false"
        />
      </n-tab-pane>
      <n-tab-pane name="extract" tab="提取">
        <KeyValueEditor
            v-model:items="form.extracts"
            :body-type="'none'"
            :is-for-body="false"
        />
      </n-tab-pane>
      <n-tab-pane name="code" tab="Code">Code</n-tab-pane>
      <n-tab-pane name="hook" tab="Hook">Hook</n-tab-pane>
      <n-tab-pane name="assert" tab="断言规则">断言规则</n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import {reactive, watch} from 'vue'
import {NButton, NFormItem, NInput, NRadio, NRadioGroup, NSelect, NSpace, NTabs, NTabPane} from 'naive-ui'
import MonacoEditor from "@/components/monaco/index.vue";
import KeyValueEditor from "@/components/common/KeyValueEditor.vue";

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:config', 'debug'])

const methodOptions = [
  {label: 'GET', value: 'GET'},
  {label: 'POST', value: 'POST'},
  {label: 'PUT', value: 'PUT'},
  {label: 'DELETE', value: 'DELETE'},
  {label: 'PATCH', value: 'PATCH'}
]

const defaults = {
  method: 'POST',
  url: '',
  name: '',
  request_body_type: 'json',
  json_body: '{\n  "password": "123456",\n  "username": "${username}"\n}',
  form_data: [],
  x_www_form_urlencoded: [],
  headers: [],
  variables: [],
  extracts: []
}

const form = reactive({...defaults, ...props.config})

const monacoEditorOptions = {
  theme: 'vs-dark',
  language: 'json',
  fontSize: 14,
  tabSize: 2,
  automaticLayout: true,
  minimap: {enabled: true},
  lineNumbers: 'on',
  wordWrap: 'off',
  scrollBeyondLastLine: false,
  folding: true,
}

watch(
    () => props.config,
    (val) => Object.assign(form, defaults, val || {}),
    {deep: true, immediate: true}
)

watch(
    form,
    () => emit('update:config', {...form}),
    {deep: true}
)
</script>

<style scoped>
.json-editor {
  font-family: 'Fira Code', monospace;
  border-radius: 4px;
  overflow: hidden;
}
</style>
