<template>
  <n-card :bordered="false" size="small" style="width: 100%;" class="quote-card">
    <n-form label-placement="left" label-width="100px">
      <n-form-item label="引用用例">
        <n-text>{{ displayName }}</n-text>
        <n-button
            v-if="onReselect"
            type="primary"
            quaternary
            size="small"
            style="margin-left: 8px;"
            @click="onReselect"
        >
          <template #icon>
            <TheIcon icon="material-symbols:refresh" :size="14"/>
          </template>
          重新选择
        </n-button>
      </n-form-item>
      <n-form-item v-if="quoteCaseId" label="用例 ID">
        <n-text>{{ quoteCaseId }}</n-text>
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'
import { NCard, NForm, NFormItem, NText, NButton } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  config: { type: Object, default: () => ({}) },
  step: { type: Object, default: () => ({}) },
  onReselect: { type: Function, default: null }
})

const displayName = computed(() => {
  return props.config?.step_name ?? props.step?.original?.step_name ?? props.step?.name ?? '引用公共用例'
})

const quoteCaseId = computed(() => {
  return props.config?.quote_case_id ?? props.step?.original?.quote_case_id ?? null
})
</script>

<style scoped>
.quote-card {
  margin: 8px 0;
  border-radius: 10px;
  box-shadow: 0 0 12px rgba(204, 204, 204, 0.99);
  border-left: 4px solid #18a058;
}
</style>
