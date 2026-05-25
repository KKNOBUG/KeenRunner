<template>
  <n-space vertical :size="8" class="extract-validator-list">
    <div v-for="(item, key) in model" :key="key" class="extract_variables-item">
      <n-card
        size="small"
        hoverable
        :class="{ 'is-item-collapsed': collapseState[key] }"
      >
        <template #header>
          <div class="extract-validator-card-header">
            <span>{{ formatExtractCardTitle(item, extractMode) }}</span>
            <n-space>
              <n-button text size="small" :disabled="readonly" @click="toggleCollapse(key)">
                <template #icon>
                  <TheIcon
                    :icon="collapseState[key] ? 'material-symbols:expand-more' : 'material-symbols:expand-less'"
                    :size="18"
                  />
                </template>
              </n-button>
              <n-button text type="info" size="small" :disabled="readonly" @click="duplicateItem(key)">
                <template #icon>
                  <TheIcon icon="material-symbols:content-copy" :size="18" />
                </template>
              </n-button>
              <n-button text type="error" size="small" :disabled="readonly" @click="removeItem(key)">
                <template #icon>
                  <TheIcon icon="material-symbols:delete-outline" :size="18" />
                </template>
              </n-button>
            </n-space>
          </div>
        </template>
        <div v-show="!collapseState[key]">
          <n-form
            :model="item"
            label-width="auto"
            label-placement="left"
            size="small"
            class="step-ev-form"
          >
            <n-form-item label="提取名称">
              <n-input
                v-model:value="item.name"
                placeholder="请输入提取名称"
                clearable
                :disabled="readonly"
              />
            </n-form-item>

            <n-form-item v-if="isDatabase" label="提取来源">
              <n-space vertical :size="4" style="width: 100%;">
                <n-select
                  v-model:value="item.source"
                  :options="sourceOptions"
                  placeholder="选择「请求」中配置的存储变量名（variable_name）"
                  filterable
                  clearable
                  :disabled="readonly || !sourceOptions.length"
                />
                <span class="autotest-hint-text">{{ DB_SOURCE_HINT }}</span>
              </n-space>
            </n-form-item>
            <n-form-item v-else label="提取对象">
              <n-select
                v-model:value="item.object"
                :options="RESPONSE_EXTRACT_OBJECT_OPTIONS"
                placeholder="请选择提取对象"
                :disabled="readonly"
              />
            </n-form-item>

            <n-form-item label="提取范围">
              <n-space align="center" :wrap-item="false">
                <n-radio-group
                  v-model:value="item.extractScope"
                  name="extractScope"
                  :disabled="readonly"
                >
                  <n-space>
                    <n-radio value="部分提取">部分提取</n-radio>
                    <n-radio value="全部提取">全部提取</n-radio>
                  </n-space>
                </n-radio-group>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <TheIcon
                      icon="material-symbols:help-outline"
                      :size="18"
                      style="cursor: help; margin-left: 8px;"
                    />
                  </template>
                  {{
                    isDatabase
                      ? '部分提取需填写 JSONPath（相对所选来源对应的那条执行结果对象）；全部提取取该对象整项（含 sql_data、sql_count 等）'
                      : '选择提取范围：部分提取需要指定JSONPath/XPath等表达式，全部提取将提取整个响应内容'
                  }}
                </n-tooltip>
              </n-space>
            </n-form-item>

            <n-form-item v-if="item.extractScope === '部分提取'" label="提取路径">
              <n-space align="center" :wrap-item="false" style="width: 100%;">
                <n-input
                  v-model:value="item.jsonpath"
                  :placeholder="pathPlaceholder(item)"
                  clearable
                  style="flex: 1;"
                  :disabled="readonly"
                />
                <template v-if="!isDatabase">
                  <n-button text type="primary" :disabled="readonly" @click="onContinueExtract(key)">
                    继续提取
                    <template #icon>
                      <TheIcon icon="material-symbols:dataset-linked-outline" :size="18" />
                    </template>
                  </n-button>
                </template>
                <n-switch v-model:value="item.continueExtract" size="small" :disabled="readonly" />
                <n-input-number
                  v-model:value="item.extractIndex"
                  :min="0"
                  size="small"
                  :style="{ width: isDatabase ? '88px' : '80px' }"
                  :disabled="readonly"
                />
                <n-tooltip v-if="!isDatabase" trigger="hover">
                  <template #trigger>
                    <TheIcon icon="material-symbols:help-outline" :size="18" style="cursor: help;" />
                  </template>
                  0 表示第1项，1表示第2项，-1表示倒数第1项，-2表示倒数第2项，以此类推
                </n-tooltip>
              </n-space>
            </n-form-item>
          </n-form>
        </div>
      </n-card>
    </div>
    <n-button type="primary" block dashed :disabled="readonly" @click="addItem">添加提取</n-button>
  </n-space>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NSwitch,
  NTooltip,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  createEmptyExtractItem,
  DB_JSONPATH_PLACEHOLDER,
  DB_SOURCE_HINT,
  EXTRACT_MODE_DATABASE,
  EXTRACT_MODE_RESPONSE,
  formatExtractCardTitle,
  getExtractPlaceholder,
  getNextDictKey,
  RESPONSE_EXTRACT_OBJECT_OPTIONS,
} from '@/utils/autotestExtractAssert'

const props = defineProps({
  /** response | database */
  mode: {
    type: String,
    default: EXTRACT_MODE_RESPONSE,
    validator: (v) => [EXTRACT_MODE_RESPONSE, EXTRACT_MODE_DATABASE].includes(v),
  },
  readonly: { type: Boolean, default: false },
  /** database 模式：请求 Tab 中的 variable_name 选项 */
  sourceOptions: { type: Array, default: () => [] },
})

const model = defineModel({ type: Object, default: () => ({}) })

const extractMode = computed(() => props.mode)
const isDatabase = computed(() => props.mode === EXTRACT_MODE_DATABASE)

const collapseState = reactive({})

function syncCollapseKeys() {
  const keys = new Set(Object.keys(model.value || {}))
  Object.keys(collapseState).forEach((k) => {
    if (!keys.has(k)) delete collapseState[k]
  })
  keys.forEach((k) => {
    if (collapseState[k] === undefined) collapseState[k] = false
  })
}

watch(model, syncCollapseKeys, { deep: true, immediate: true })

function defaultSource() {
  if (!isDatabase.value) return null
  return props.sourceOptions[0]?.value ?? null
}

function pathPlaceholder(item) {
  if (isDatabase.value) return DB_JSONPATH_PLACEHOLDER
  return getExtractPlaceholder(item?.object)
}

function addItem() {
  const key = getNextDictKey(model.value)
  model.value[key] = createEmptyExtractItem(props.mode, defaultSource())
  collapseState[key] = false
}

function removeItem(key) {
  delete model.value[key]
  delete collapseState[key]
}

function duplicateItem(key) {
  const item = model.value[key]
  if (!item) return
  const newKey = getNextDictKey(model.value)
  model.value[newKey] = {
    ...JSON.parse(JSON.stringify(item)),
    name: item.name ? `${item.name}_副本` : '',
  }
  collapseState[newKey] = collapseState[key] ?? false
}

function toggleCollapse(key) {
  collapseState[key] = !collapseState[key]
}

function onContinueExtract() {
  window.$message?.info?.('继续提取功能待实现')
}

defineExpose({
  resetCollapse() {
    Object.keys(collapseState).forEach((k) => delete collapseState[k])
    syncCollapseKeys()
  },
})
</script>

<style scoped lang="scss">
@import './step-extract-assert-panel.scss';
</style>
