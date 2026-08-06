<template>
  <n-space vertical :size="8" class="extract-validator-list">
    <div v-for="(item, key) in model" :key="key" class="validator-item">
      <n-card
          size="small"
          hoverable
          :class="{ 'is-item-collapsed': collapseState[key] }"
      >
        <template #header>
          <div class="extract-validator-card-header">
            <div
                class="extract-validator-title-wrap"
                role="button"
                tabindex="0"
                @click="toggleCollapse(key)"
                @keydown.enter.prevent="toggleCollapse(key)"
            >
              <TheIcon
                  class="extract-validator-collapse-icon"
                  :icon="collapseState[key] ? 'material-symbols:chevron-right' : 'material-symbols:expand-more'"
                  :size="20"
              />
              <span class="extract-validator-title">{{ formatAssertCardTitle(item, mode) }}</span>
            </div>
            <n-space @click.stop>
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
              label-width="90px"
              label-placement="left"
              size="small"
              class="step-ev-form"
          >
            <div class="step-ev-rows">
              <div class="step-ev-row step-ev-row--assert">
                <n-form-item label="断言名称" class="step-ev-fi step-ev-fi--span2">
                  <n-input
                      v-model:value="item.name"
                      placeholder="请输入断言名称"
                      clearable
                      :disabled="readonly"
                  />
                </n-form-item>

                <n-form-item v-if="isVariableSource" label="断言对象" class="step-ev-fi">
                  <n-select
                      v-model:value="item.source"
                      :options="sourceOptions"
                      placeholder="选择「请求」中的存储变量名（variable_name）"
                      filterable
                      clearable
                      :disabled="readonly || !sourceOptions.length"
                  />
                </n-form-item>
                <n-form-item v-else-if="!isPython" label="断言对象" class="step-ev-fi">
                  <n-select
                      v-model:value="item.object"
                      :options="RESPONSE_ASSERT_OBJECT_OPTIONS"
                      placeholder="请选择断言对象"
                      :disabled="readonly"
                  />
                </n-form-item>
                <n-form-item v-else label="断言对象" class="step-ev-fi">
                  <n-select
                      v-model:value="item.object"
                      :options="PYTHON_ASSERT_OBJECT_OPTIONS"
                      placeholder="变量池"
                      :disabled="readonly || lockObject"
                  />
                </n-form-item>
              </div>

              <div class="step-ev-row step-ev-row--assert">
                <n-form-item label="断言表达式" class="step-ev-fi">
                  <n-input
                      v-model:value="item.jsonpath"
                      :placeholder="exprPlaceholder(item)"
                      clearable
                      :disabled="readonly"
                  />
                </n-form-item>
                <n-form-item label="断言操作符" class="step-ev-fi">
                  <n-select
                      v-model:value="item.assertion"
                      :options="assertionOptions"
                      placeholder="请选择断言方法"
                      :disabled="readonly"
                  />
                </n-form-item>
                <n-form-item label="断言预期值" class="step-ev-fi">
                  <n-input
                      v-model:value="item.value"
                      placeholder="请输入预期值"
                      clearable
                      :disabled="readonly"
                  />
                </n-form-item>
              </div>
            </div>
          </n-form>
        </div>
      </n-card>
    </div>
    <n-button type="primary" block dashed :disabled="readonly" @click="addItem">添加断言</n-button>
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
  NSelect,
  NSpace,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import {
  assertionOptions,
  ASSERT_MODE_DATABASE,
  ASSERT_MODE_PYTHON,
  ASSERT_MODE_REDIS,
  ASSERT_MODE_RESPONSE,
  createEmptyAssertItem,
  formatAssertCardTitle,
  getAssertPlaceholder,
  getNextDictKey,
  isVariableNameAssertMode,
  PYTHON_ASSERT_OBJECT_OPTIONS,
  RESPONSE_ASSERT_OBJECT_OPTIONS,
} from '@/utils/autotestExtractAssert'

const props = defineProps({
  /** response | database | redis | python */
  mode: {
    type: String,
    default: ASSERT_MODE_RESPONSE,
    validator: (v) => [ASSERT_MODE_RESPONSE, ASSERT_MODE_DATABASE, ASSERT_MODE_REDIS, ASSERT_MODE_PYTHON].includes(v),
  },
  readonly: { type: Boolean, default: false },
  sourceOptions: { type: Array, default: () => [] },
  /** response 模式下新建断言的默认断言对象（如独立断言步骤默认「变量池」） */
  defaultObject: { type: String, default: null },
  /** 锁定断言对象不可切换（独立断言步骤固定「变量池」并置灰） */
  lockObject: { type: Boolean, default: false },
})

const model = defineModel({ type: Object, default: () => ({}) })

const isVariableSource = computed(() => isVariableNameAssertMode(props.mode))
const isPython = computed(() => props.mode === ASSERT_MODE_PYTHON)

const collapseState = reactive({})

function syncCollapseKeys() {
  const keys = new Set(Object.keys(model.value || {}))
  Object.keys(collapseState).forEach((k) => {
    if (!keys.has(k)) delete collapseState[k]
  })
  keys.forEach((k) => {
    // 默认折叠；用户主动展开后会保留在 collapseState 中
    if (collapseState[k] === undefined) collapseState[k] = true
  })
}

watch(model, syncCollapseKeys, { deep: true, immediate: true })

function defaultSource() {
  if (!isVariableSource.value) return null
  return props.sourceOptions[0]?.value ?? null
}

function exprPlaceholder(item) {
  if (isVariableSource.value) return getAssertPlaceholder(null, props.mode)
  return getAssertPlaceholder(item?.object, props.mode)
}

function addItem() {
  const key = getNextDictKey(model.value)
  model.value[key] = createEmptyAssertItem(props.mode, defaultSource(), props.defaultObject)
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
  collapseState[newKey] = collapseState[key] ?? true
}

function toggleCollapse(key) {
  collapseState[key] = !collapseState[key]
}
</script>

<style scoped lang="scss">
@import './step-extract-assert-panel.scss';
</style>
