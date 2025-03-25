<template>
  <n-card :bordered="false" size="small">
    <div class="key-value-editor">
      <!-- 标题行 -->
      <n-grid :cols="24" :x-gap="10">
        <n-gi :span="6">
          <n-text strong>键</n-text>
        </n-gi>
        <n-gi :span="8">
          <n-text strong>值</n-text>
        </n-gi>
        <n-gi :span="8">
          <n-text strong>描述</n-text>
        </n-gi>
        <n-gi :span="2">
          <n-button @click="openBatchAddModal" type="primary" tertiary>
            批量
          </n-button>
        </n-gi>
      </n-grid>

      <!-- 数据行 -->
      <div v-for="(item, index) in items" :key="index" class="key-value-row">
        <n-grid :cols="24" :x-gap="10">
          <n-gi :span="6">
            <n-input v-model:value="item.key" placeholder="Key" clearable/>
          </n-gi>
          <n-gi :span="8">
            <n-input v-model:value="item.value" placeholder="Value" clearable/>
          </n-gi>
          <n-gi :span="8">
            <n-input v-model:value="item.description" placeholder="Description" clearable/>
          </n-gi>
          <n-gi :span="2">
            <n-button @click="handleRemove(index)" type="primary" tertiary>
              删除
            </n-button>
          </n-gi>
        </n-grid>
      </div>

      <!-- 操作行 -->
      <div class="add-button-container">
        <n-button @click="handleAdd" type="primary" dashed block class="add-button">
          添加
        </n-button>
      </div>

      <!-- 批量添加模态框 -->
      <n-modal v-model:show="isBatchAddModalVisible">
        <n-card
            :bordered="false"
            role="dialog"
            size="small"
            aria-modal="true"
            style="width: 600px;"
        >
          <n-input
              type="textarea"
              v-model:value="batchInput"
              placeholder="按 key:value:description 格式输入"
              :rows="10"
              class="custom-textarea"
          />
          <template #footer>
            <n-space justify="end">
              <n-button @click="isBatchAddModalVisible = false" type="primary" tertiary color="#000000">取消</n-button>
              <n-button @click="handleBatchAdd" type="primary" tertiary>确定</n-button>
            </n-space>
          </template>
        </n-card>
      </n-modal>

    </div>

  </n-card>
</template>

<script setup>
import {defineEmits, defineProps} from 'vue';

const props = defineProps(['items']);
const emit = defineEmits(['add', 'remove', 'update:items']);
const isBatchAddModalVisible = ref(false);
const batchInput = ref('');

const handleAdd = () => {
  const newItems = [...props.items, {key: '', value: ''}];
  emit('update:items', newItems);
  emit('add');
};

const handleRemove = (index) => {
  const newItems = props.items.filter((_, i) => i !== index);
  emit('update:items', newItems);
  emit('remove', index);
};

const openBatchAddModal = () => {
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  batchInput.value = props.items.map(item => {
    if (item.description) {
      return `${item.key}:${item.value}:${item.description}`;
    }
    return `${item.key}:${item.value}`;
  }).join('\n');
  isBatchAddModalVisible.value = true;
};

const handleBatchAdd = () => {
  const lines = batchInput.value.split('\n');
  const newItems = [];
  lines.forEach((line) => {
    const parts = line.split(':');
    if (parts.length === 2) {
      const key = parts[0].trim();
      const value = parts[1].trim();
      newItems.push({key, value, description: ''});
    } else if (parts.length === 3) {
      const key = parts[0].trim();
      const value = parts[1].trim();
      const desc = parts[2].trim();
      newItems.push({key, value, description: desc});
    }
  });
  emit('update:items', newItems);
  emit('add');
  isBatchAddModalVisible.value = false;
  batchInput.value = '';
};
</script>


<style scoped>
.key-value-row {
  margin-top: 10px;
}

.add-button-container {
  margin-top: 24px;
  padding: 0;
  width: 98.6%;
}

.custom-textarea {
  border-radius: 8px;
}
</style>
