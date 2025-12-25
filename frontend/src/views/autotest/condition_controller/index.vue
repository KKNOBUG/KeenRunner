<template>
  <n-form label-placement="left" label-width="auto" :model="form">
    <n-form-item label="条件值">
      <n-input v-model:value="form.left" placeholder="例如: ${token}" />
    </n-form-item>
    <n-form-item label="比对条件">
      <n-select
          v-model:value="form.operator"
          :options="operatorOptions"
          placeholder="请选择比对条件"
      />
    </n-form-item>
    <n-form-item label="比对值">
      <n-input
          v-model:value="form.right"
          placeholder="字符串或者变量,例如:${var}"
      />
    </n-form-item>
    <n-form-item label="备注">
      <n-input
          v-model:value="form.remark"
          placeholder="请输入备注"
      />
    </n-form-item>
  </n-form>
</template>

<script setup>
import {reactive, watch} from 'vue'
import {NForm, NFormItem, NInput, NSelect} from 'naive-ui'

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

const operatorOptions = [
  {label: '等于', value: 'eq'},
  {label: '不等于', value: 'ne'},
  {label: '大于', value: 'gt'},
  {label: '大于等于', value: 'gte'},
  {label: '小于', value: 'lt'},
  {label: '小于等于', value: 'lte'},
  {label: '包含', value: 'contains'},
  {label: '不包含', value: 'not_contains'},
  {label: '非空', value: 'not_empty'},
  {label: '为空', value: 'empty'},
  {label: '正则匹配', value: 'regex'}
]

const defaults = {
  left: '',
  operator: 'not_empty',
  right: '',
  remark: ''
}

const form = reactive({...defaults, ...props.config})

watch(
    () => [props.step?.id, props.config],
    ([stepId, val]) => {
      // 当步骤变化时，重新初始化表单
      Object.assign(form, defaults, val || {})
    },
    {deep: true, immediate: true}
)

watch(
    form,
    () => emit('update:config', {...form}),
    {deep: true}
)
</script>
