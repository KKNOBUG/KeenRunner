<!-- 在模板中直接定义KeyValueTable组件 -->
<template>
  <div class="key-value-table">
    <n-data-table
        :columns="columns"
        :data="modelValue"
        :pagination="false"
    >
      <template #body>
        <tbody>
        <tr v-for="(row, index) in modelValue" :key="index">
          <td>
            <n-input
                v-model:value="row.key"
                placeholder="键"
                @update:value="handleChange"
            />
          </td>
          <td>
            <n-input
                v-if="!enableFile"
                v-model:value="row.value"
                placeholder="值"
                @update:value="handleChange"
            />
            <n-upload
                v-else
                :show-file-list="false"
                @change="(file) => handleFileChange(file, index)"
            >
              <n-button v-if="!row.value">上传文件</n-button>
              <n-text v-else>{{ row.value.name }}</n-text>
            </n-upload>
          </td>
          <td v-if="showDescription">
            <n-input
                v-model:value="row.description"
                placeholder="描述"
                @update:value="handleChange"
            />
          </td>
          <td>
            <n-button @click="removeRow(index)" text type="error">删除</n-button>
          </td>
        </tr>
        </tbody>
      </template>
    </n-data-table>
    <n-button @click="addRow" class="add-btn">+ 添加参数</n-button>
  </div>
</template>

<script>
export default {
  props: ['modelValue', 'showBulkEdit', 'showDescription', 'enableFile'],
  computed: {
    columns() {
      return [
        { title: '键', key: 'key' },
        { title: '值', key: 'value' },
        ...(this.showDescription ? [{ title: '描述', key: 'description' }] : []),
        { title: '操作', key: 'actions' }
      ]
    }
  },
  methods: {
    addRow() {
      this.$emit('update:modelValue', [
        ...this.modelValue,
        { key: '', value: '', description: '' }
      ])
    },
    removeRow(index) {
      const newValue = [...this.modelValue]
      newValue.splice(index, 1)
      this.$emit('update:modelValue', newValue)
    },
    handleFileChange(file, index) {
      const newValue = [...this.modelValue]
      newValue[index].value = file.file
      this.$emit('update:modelValue', newValue)
    },
    handleChange() {
      this.$emit('update:modelValue', [...this.modelValue])
    }
  }
}
</script>
