<template>
  <n-form label-placement="left" label-width="auto" :model="form">
    <n-radio-group v-model:value="form.mode" name="loop-mode">
      <n-space>
        <n-radio value="times">循环次数</n-radio>
        <n-radio value="for">For 循环</n-radio>
        <n-radio value="condition">循环条件</n-radio>
      </n-space>
    </n-radio-group>

    <div class="section">
      <template v-if="form.mode === 'times'">
        <n-form-item label="循环次数">
          <n-input-number v-model:value="form.times" :min="1" />
        </n-form-item>
        <n-form-item label="循环间隔">
          <n-input-number v-model:value="form.interval" :min="0" suffix="秒" />
        </n-form-item>
      </template>

      <template v-else-if="form.mode === 'for'">
        <n-form-item label="变量名">
          <n-input v-model:value="form.forVar" placeholder="例如: i" />
        </n-form-item>
        <n-form-item label="起始值">
          <n-input-number v-model:value="form.forStart" />
        </n-form-item>
        <n-form-item label="结束值">
          <n-input-number v-model:value="form.forEnd" />
        </n-form-item>
        <n-form-item label="循环间隔">
          <n-input-number v-model:value="form.interval" :min="0" suffix="秒" />
        </n-form-item>
      </template>

      <template v-else>
        <n-form-item label="循环条件">
          <n-input
              v-model:value="form.condition"
              type="textarea"
              placeholder="填写循环退出条件表达式，如 ${count} &lt; 3"
          />
        </n-form-item>
        <n-form-item label="循环间隔">
          <n-input-number v-model:value="form.interval" :min="0" suffix="秒" />
        </n-form-item>
      </template>
    </div>
  </n-form>
</template>

<script setup>
import {reactive, watch} from 'vue'
import {NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioGroup, NSpace} from 'naive-ui'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:config'])

const defaults = {
  mode: 'times',
  times: 3,
  interval: 0,
  forVar: 'i',
  forStart: 0,
  forEnd: 3,
  condition: ''
}

const form = reactive({...defaults, ...props.config})

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
.section {
  margin-top: 12px;
}
</style>
