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
              <span class="extract-validator-title">{{ formatExtractCardTitle(item, mode) }}</span>
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
              <div class="step-ev-row step-ev-row--extract">
                <n-form-item label="提取名称" class="step-ev-fi step-ev-fi--span2">
                  <n-input
                      v-model:value="item.name"
                      placeholder="请输入提取名称"
                      clearable
                      :disabled="readonly"
                  />
                </n-form-item>

                <n-form-item v-if="isVariableSource" label="提取对象" class="step-ev-fi">
                  <n-select
                      v-model:value="item.source"
                      :options="sourceOptions"
                      placeholder="选择「请求」中配置的存储变量名（variable_name）"
                      filterable
                      clearable
                      :disabled="readonly || !sourceOptions.length"
                  />
                </n-form-item>
                <n-form-item v-else label="提取对象" class="step-ev-fi">
                  <n-select
                      v-model:value="item.object"
                      :options="RESPONSE_EXTRACT_OBJECT_OPTIONS"
                      placeholder="请选择提取对象"
                      :disabled="readonly"
                  />
                </n-form-item>
              </div>

              <div class="step-ev-row step-ev-row--extract">
                <n-form-item label="提取范围" class="step-ev-fi">
                  <div class="extract-scope-inline">
                    <n-radio-group
                        v-model:value="item.extractScope"
                        name="extractScope"
                        :disabled="readonly"
                    >
                      <n-radio value="部分提取">部分提取</n-radio>
                      <n-radio value="全部提取">全部提取</n-radio>
                    </n-radio-group>
                    <n-tooltip trigger="hover">
                      <template #trigger>
                        <TheIcon
                            class="extract-scope-help"
                            icon="material-symbols:help-outline"
                            :size="18"
                        />
                      </template>
                      {{
                        isVariableSource
                            ? variableScopeHint
                            : '选择提取范围：部分提取需要指定JSONPath/XPath等表达式，全部提取将提取整个请求/响应对象'
                      }}
                    </n-tooltip>
                  </div>
                </n-form-item>

                <n-form-item label="提取路径" class="step-ev-fi">
                  <n-input
                      v-model:value="item.jsonpath"
                      :placeholder="pathPlaceholder(item)"
                      clearable
                      :disabled="readonly || item.extractScope !== '部分提取'"
                  />
                </n-form-item>

                <n-form-item label="继续提取" class="step-ev-fi">
                  <n-space align="center" :wrap-item="false" :size="8">
                    <n-switch
                        v-model:value="item.extractContinue"
                        size="small"
                        :disabled="readonly || item.extractScope !== '部分提取'"
                    />
                    <n-input-number
                        v-model:value="item.extractIndex"
                        :min="0"
                        size="small"
                        style="width: 80px;"
                        :disabled="readonly || item.extractScope !== '部分提取' || !item.extractContinue"
                    />
                    <n-tooltip v-if="!isVariableSource" trigger="hover">
                      <template #trigger>
                        <TheIcon icon="material-symbols:help-outline" :size="18" style="cursor: help;" />
                      </template>
                      0 表示第1项，1表示第2项，-1表示倒数第1项，-2表示倒数第2项，以此类推
                    </n-tooltip>
                  </n-space>
                </n-form-item>
              </div>
            </div>
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
  EXTRACT_MODE_DATABASE,
  EXTRACT_MODE_REDIS,
  EXTRACT_MODE_RESPONSE,
  formatExtractCardTitle,
  getExtractPlaceholder,
  getNextDictKey,
  isVariableNameExtractMode,
  REDIS_JSONPATH_PLACEHOLDER,
  DB_JSONPATH_PLACEHOLDER,
  RESPONSE_EXTRACT_OBJECT_OPTIONS,
} from '@/utils/autotestExtractAssert'

const props = defineProps({
  /** response | database | redis */
  mode: {
    type: String,
    default: EXTRACT_MODE_RESPONSE,
    validator: (v) => [EXTRACT_MODE_RESPONSE, EXTRACT_MODE_DATABASE, EXTRACT_MODE_REDIS].includes(v),
  },
  readonly: { type: Boolean, default: false },
  /** database 模式：请求 Tab 中的 variable_name 选项 */
  sourceOptions: { type: Array, default: () => [] },
})

const model = defineModel({ type: Object, default: () => ({}) })

const isVariableSource = computed(() => isVariableNameExtractMode(props.mode))
const variableScopeHint = computed(() =>
    props.mode === EXTRACT_MODE_REDIS
        ? '部分提取需填写 JSONPath（相对所选 variable_name 的 redis_data）；全部提取取该 redis_data 整项'
        : '部分提取需填写 JSONPath（相对所选来源对应的那条执行结果对象外层字段）；全部提取取该对象整项（含 sql_data、sql_count、env_name 等）'
)

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

// 继续提取开关：ON → extractIndex 设为 0，OFF → extractIndex 设为 null
watch(model, (newVal) => {
  Object.values(newVal || {}).forEach((item) => {
    if (item.extractContinue === true) {
      if (item.extractIndex === null || item.extractIndex === undefined) {
        item.extractIndex = 0
      }
    } else if (item.extractContinue === false) {
      if (item.extractIndex !== null) {
        item.extractIndex = null
      }
    }
  })
}, { deep: true })

function defaultSource() {
  if (!isVariableSource.value) return null
  return props.sourceOptions[0]?.value ?? null
}

function pathPlaceholder(item) {
  if (props.mode === EXTRACT_MODE_REDIS) return REDIS_JSONPATH_PLACEHOLDER
  if (props.mode === EXTRACT_MODE_DATABASE) return DB_JSONPATH_PLACEHOLDER
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
  collapseState[newKey] = collapseState[key] ?? true
}

function toggleCollapse(key) {
  collapseState[key] = !collapseState[key]
}
</script>

<style scoped lang="scss">
@import './step-extract-assert-panel.scss';
</style>
