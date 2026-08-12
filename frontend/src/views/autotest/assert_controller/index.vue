<template>
  <div class="assert-container">
    <n-card :bordered="false" class="step-editor-card">
      <template #header>
        <div class="card-header-row">
          <div class="panel-title">断言</div>
        </div>
      </template>

      <div class="top-bar">
        <n-form class="step-editor-form assert-name-form" label-placement="left" label-width="80px" size="small">
          <n-form-item label="步骤名称" :show-feedback="false">
            <n-input
                v-model:value="form.step_name"
                placeholder="断言"
                class="step-name-input"
                :disabled="props.readonly"
            />
          </n-form-item>
        </n-form>
      </div>

      <n-tabs type="line" animated class="assert-tabs">
        <n-tab-pane name="assert_validators" tab="断言">
          <template #tab>
            <n-badge :value="validatorsCount" :max="99" show-zero>
              <span>断言</span>
            </n-badge>
          </template>
          <div class="hint-box step-editor-hint">
            <div class="hint-title">使用说明</div>
            <div class="hint-content">
              <p>• 断言对象固定为<code>变量池</code>；表达式须为 JSONPath，且以 <code>$</code> 开头</p>
              <p>• 取普通变量：<code>$.token</code>（不要只写 <code>token</code>）</p>
              <p>• 变量值为对象时：<code>$.user.name</code>；为数组时：<code>$.list[0].name</code>、<code>$.list[*].id</code></p>
            </div>
          </div>
          <StepAssertPanel
              v-model="form.assert_validators"
              mode="python"
              lock-object
              :readonly="props.readonly"
          />
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import {
  NBadge,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NTabPane,
  NTabs,
} from 'naive-ui'
import StepAssertPanel from '@/components/autotest/StepAssertPanel.vue'
import {
  ASSERT_MODE_PYTHON,
  buildAssertListFromDict,
  countDictKeys,
  hydrateAssertDictFromBackend,
  normalizeBackendList,
} from '@/utils/autotestExtractAssert'
import { useStepEditorForm } from '@/composables/step-editor'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({}),
  },
  step: {
    type: Object,
    default: () => ({}),
  },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:config'])

const mergeConfigAndOriginal = (config, original, stepName) => {
  const validatorsRaw = config.assert_validators ?? original?.assert_validators
  return {
    step_name: config.step_name !== undefined
        ? config.step_name
        : (stepName || original?.step_name || ''),
    assert_validators: hydrateAssertDictFromBackend(
        normalizeBackendList(validatorsRaw),
        ASSERT_MODE_PYTHON,
    ),
  }
}

const { form } = useStepEditorForm({
  props,
  emit,
  defaults: () => ({ step_name: '', assert_validators: {} }),
  hydrate: (p) => mergeConfigAndOriginal(p.config || {}, p.step?.original, p.step?.name),
  buildConfig: (f) => ({
    step_name: f.step_name || '',
    assert_validators: buildAssertListFromDict(f.assert_validators, ASSERT_MODE_PYTHON),
  }),
  watchFields: (f) => [f.step_name, f.assert_validators],
})

/** 确保断言对象始终为「变量池」（兼容历史配置误选其它对象） */
watch(
    () => form.assert_validators,
    (dict) => {
      if (!dict || typeof dict !== 'object') return
      Object.values(dict).forEach((item) => {
        if (item && item.object !== '变量池') item.object = '变量池'
      })
    },
    { deep: true, immediate: true },
)

const validatorsCount = computed(() => countDictKeys(form.assert_validators))
</script>

<style scoped>
.assert-container {
  width: 100%;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.assert-name-form {
  flex: 1;
  min-width: 0;
}

.step-name-input {
  max-width: 420px;
}

.assert-tabs {
  margin-top: 4px;
}

.hint-box {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--n-color-embedded, #fafafa) 88%, transparent);
  border: 1px solid var(--n-border-color);
}

.hint-title {
  font-size: var(--step-editor-font-size, 13px);
  font-weight: 600;
  margin-bottom: 6px;
}

.hint-content {
  font-size: var(--step-editor-meta-size, 12px);
  color: var(--n-text-color-2);
  line-height: 1.55;
}

.hint-content p {
  margin: 0 0 4px;
}

.hint-content p:last-child {
  margin-bottom: 0;
}

.hint-content code {
  padding: 0 4px;
  border-radius: 4px;
  font-size: 11px;
  background: color-mix(in srgb, var(--n-border-color) 35%, transparent);
}
</style>
