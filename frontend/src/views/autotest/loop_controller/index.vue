<template>
  <!-- 新增Card包裹整个表单，设置内边距和间距 -->
  <n-card :bordered="true" style="width: 100%;" class="loop-card">
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
            <!-- 修复：补充placeholder，确保min=1生效，绑定值为数字类型 -->
            <n-input-number
                v-model:value="form.times"
                :min="1"
                placeholder="请输入循环次数"
                style="width: 100%;"
            />
          </n-form-item>
          <n-form-item label="循环间隔">
            <n-input-number
                v-model:value="form.interval"
                :min="0"
                suffix="秒"
                placeholder="请输入循环间隔（秒）"
                style="width: 100%;"
            />
          </n-form-item>
        </template>

        <template v-else-if="form.mode === 'for'">
          <n-form-item label="变量名">
            <n-input
                v-model:value="form.forVar"
                placeholder="例如: i"
                style="width: 100%;"
            />
          </n-form-item>
          <n-form-item label="起始值">
            <n-input-number
                v-model:value="form.forStart"
                placeholder="请输入起始值"
                style="width: 100%;"
            />
          </n-form-item>
          <n-form-item label="结束值">
            <n-input-number
                v-model:value="form.forEnd"
                placeholder="请输入结束值"
                style="width: 100%;"
            />
          </n-form-item>
          <n-form-item label="循环间隔">
            <n-input-number
                v-model:value="form.interval"
                :min="0"
                suffix="秒"
                placeholder="请输入循环间隔（秒）"
                style="width: 100%;"
            />
          </n-form-item>
        </template>

        <template v-else>
          <n-form-item label="循环条件">
            <n-input
                v-model:value="form.condition"
                type="textarea"
                placeholder="填写循环退出条件表达式，如 ${count} &lt; 3"
                style="width: 100%;"
                rows="3"
            />
          </n-form-item>
          <n-form-item label="循环间隔">
            <n-input-number
                v-model:value="form.interval"
                :min="0"
                suffix="秒"
                placeholder="请输入循环间隔（秒）"
                style="width: 100%;"
            />
          </n-form-item>
        </template>
      </div>
    </n-form>
  </n-card>
</template>

<script setup>
import { reactive, watch } from 'vue'
// 新增导入NCard组件
import { NForm, NFormItem, NInput, NInputNumber, NRadio, NRadioGroup, NSpace, NCard } from 'naive-ui'

const props = defineProps({
  config: {
    type: Object,
    default: () => ({})
  },
  step: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:config'])

const defaults = {
  mode: 'times',
  times: 3, // 初始值为数字类型，确保加减功能正常
  interval: 0,
  forVar: 'i',
  forStart: 0,
  forEnd: 3,
  condition: ''
}

// 确保form中的值为数字类型（避免字符串导致加减失效）
const form = reactive({
  ...defaults,
  ...props.config,
  times: Number(props.config.times || defaults.times),
  interval: Number(props.config.interval || defaults.interval),
  forStart: Number(props.config.forStart || defaults.forStart),
  forEnd: Number(props.config.forEnd || defaults.forEnd)
})

watch(
    () => [props.step?.id, props.config],
    ([stepId, val]) => {
      // 监听props变化时，强制转换为数字类型
      const newVal = { ...defaults, ...val || {} }
      newVal.times = Number(newVal.times)
      newVal.interval = Number(newVal.interval)
      newVal.forStart = Number(newVal.forStart)
      newVal.forEnd = Number(newVal.forEnd)
      Object.assign(form, newVal)
    },
    { deep: true, immediate: true }
)

watch(
    form,
    () => emit('update:config', { ...form }),
    { deep: true }
)
</script>

<style scoped>
/* 卡片整体样式 */
.loop-card {
  margin: 8px 0;
}
/* 表单区域间距 */
.section {
  margin-top: 16px;
}
/* 表单项目间距优化 */
:deep(.n-form-item) {
  margin-bottom: 12px;
}
/* 单选框区域间距 */
:deep(.n-radio-group) {
  padding: 4px 0;
}
</style>
