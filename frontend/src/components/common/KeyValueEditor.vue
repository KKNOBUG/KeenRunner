<template>
  <n-card :bordered="false" size="small">
    <!-- 标题行 -->
    <n-grid :cols="24" :x-gap="10" class="header-row">
      <n-gi :span="isFormDataAndForBody ? 2 : 8">
        <n-text strong v-if="isFormDataAndForBody">类型</n-text>
        <n-text strong v-else>变量</n-text>
      </n-gi>
      <n-gi :span="isFormDataAndForBody ? 6 : 0">
        <n-text strong v-if="isFormDataAndForBody">变量</n-text>
      </n-gi>
      <n-gi :span="8">
        <n-text strong>数据</n-text>
      </n-gi>
      <n-gi :span="6">
        <n-text strong>描述</n-text>
      </n-gi>
      <n-gi :span="2">
        <n-button v-if="!disabled" @click="openBatchAddModal" type="primary" tertiary>
          批量
        </n-button>
      </n-gi>
    </n-grid>

    <!-- 数据行，使用 v-for 指令遍历 items 数组，为每个元素生成一行 -->
    <div v-for="(item, index) in items" :key="index" class="key-value-row">
      <n-grid :cols="24" :x-gap="10">
        <!-- Key 列，根据是否为 form-data 模式且是请求体部分，显示不同内容 -->
        <n-gi :span="isFormDataAndForBody ? 2 : 8">
          <!-- 如果不是 form-data 模式且是请求体部分，显示输入框用于输入变量名称 -->
          <n-space align="center" :wrap-item="false">
            <n-input
                v-if="!isFormDataAndForBody"
                v-model:value="item.key"
                placeholder="请输入变量名称"
                clearable
                style="flex: 1;"
                :disabled="disabled"
            />
            <!-- 如果是 form-data 模式且是请求体部分，显示下拉选择框用于选择类型 -->
            <n-space v-else align="center" :wrap-item="false" style="flex: 1;">
              <n-select
                  v-model:value="item.type"
                  :options="[
                    { label: 'Text', value: 'text' },
                    { label: 'File', value: 'file' }
                  ]"
                  size="medium"
                  style="width: 80px; flex-shrink: 0;"
                  :disabled="disabled"
                  @update:value="(value) => handleTypeChange(value, index)"
              />
            </n-space>
          </n-space>
        </n-gi>
        <!-- 只有在 form-data 模式且是请求体部分时显示该列，显示输入框用于输入变量数据 -->
        <n-gi :span="isFormDataAndForBody ? 6 : 0">
          <n-input
              v-if="isFormDataAndForBody"
              v-model:value="item.key"
              placeholder="请输入变量数据"
              clearable
              style="flex: 1;"
              :disabled="disabled"
          />
        </n-gi>

        <!-- Value列：根据类型显示不同内容 -->
        <n-gi :span="8">
          <!-- 如果不是 form-data 模式且是请求体部分或者类型为 text，显示输入框和关联数据按钮 -->
          <div v-if="!isFormDataAndForBody || item.type === 'text'" class="text-input-wrapper">
            <n-input
                v-model:value="item.value"
                placeholder="请输入变量数据"
                clearable
                style="flex: 1;"
                :disabled="disabled"
            />
            <n-popover
                v-if="!disabled"
                :show="associationTargetIndex === index"
                @update:show="(v) => handleAssociationPopoverShow(v, index)"
                trigger="click"
                placement="bottom-start"
                :width="560"
            >
              <template #trigger>
                <n-tooltip trigger="hover" placement="top">
                  <template #trigger>
                    <n-button
                        circle
                        tertiary
                        type="primary"
                        size="small"
                        class="join-button"
                        @click="openAssociationPopover(index)"
                    >
                      <template #icon>
                        <TheIcon icon="material-symbols:dataset-linked-outline" :size="18"/>
                      </template>
                    </n-button>
                  </template>
                  使用全局变量或调用内置函数
                </n-tooltip>
              </template>
              <div class="association-menu">
                <n-input
                    v-model:value="associationSearch"
                    placeholder="搜索变量名称或函数名称、注释"
                    clearable
                    size="small"
                    class="association-search"
                />
                <div class="association-menu-body">
                  <div class="association-sidebar">
                    <div
                        v-if="availableVariableList.length > 0"
                        class="association-sidebar-item"
                        :class="{ active: associationTab === 'variables' }"
                        @click="associationTab = 'variables'"
                    >
                      全局变量({{ availableVariableList.length }}个)
                    </div>
                    <div
                        v-if="assistFunctions.length > 0"
                        class="association-sidebar-item"
                        :class="{ active: associationTab === 'functions' }"
                        @click="associationTab = 'functions'"
                    >
                      内置函数({{ assistFunctions.length }}个)
                    </div>
                  </div>
                  <div class="association-list-panel">
                    <n-scrollbar style="max-height: 300px;">
                      <template v-if="associationTab === 'variables'">
                        <div
                            v-for="(name, i) in filteredVariableList"
                            :key="'v-' + i"
                            class="association-list-item"
                            :class="{ selected: associationPreview === wrapPlaceholder(name) }"
                            @click="selectAssociationVariable(name)"
                        >
                          <div class="association-list-item-name">{{ name }}</div>
                        </div>
                        <div v-if="!filteredVariableList.length" class="association-empty">
                          {{ associationSearch ? '无匹配的全局变量' : '暂无全局变量' }}
                        </div>
                      </template>
                      <template v-else-if="associationTab === 'functions'">
                        <div
                            v-for="(fn, i) in filteredAssistFunctions"
                            :key="'f-' + i"
                            class="association-list-item association-list-item-fn"
                            :class="{ selected: associationPreview === wrapPlaceholder(fn.name || fn) }"
                            @click="selectAssociationFunction(fn)"
                        >
                          <div class="association-list-item-name">{{ fn.name || fn }}</div>
                          <pre v-if="fn.desc" class="association-list-item-desc">{{ fn.desc }}</pre>
                        </div>
                        <div v-if="!filteredAssistFunctions.length" class="association-empty">
                          {{ associationSearch ? '无匹配的内置函数' : '暂无内置函数' }}
                        </div>
                      </template>
                      <div
                          v-else-if="!availableVariableList.length && !assistFunctions.length"
                          class="association-empty"
                      >
                        暂无可用变量或内置函数
                      </div>
                    </n-scrollbar>
                  </div>
                </div>
                <div class="association-preview-wrap">
                  <span class="association-preview-label">预览：</span>
                  <n-input
                      v-model:value="associationPreview"
                      type="textarea"
                      placeholder="可选择全局变量、内置函数或手动输入..."
                      :autosize="{ minRows: 2, maxRows: 4 }"
                      class="association-preview-input"
                  />
                </div>
                <n-button type="primary" block class="association-confirm-btn" @click="confirmAssociationValue(index)">
                  确定
                </n-button>
              </div>
            </n-popover>
          </div>
          <!-- 如果是 form-data 模式且是请求体部分并且类型为 file，显示文件上传按钮和清除文件按钮 -->
          <div v-else-if="isFormDataAndForBody && item.type === 'file'" class="file-upload-wrapper">
            <n-upload
                :show-file-list="false"
                @change="({ file }) => handleFileChange(file, index)"
                class="file-upload"
            >
              <n-button block class="upload-button" :disabled="disabled">
                <template #icon>
                  <TheIcon icon="material-symbols:upload-file" :size="18"/>
                </template>
                <!-- 显示文件名，如果文件名过长会进行格式化处理 -->
                <span class="file-name">{{ formatFileName(item.value) }}</span>
              </n-button>
            </n-upload>
            <!-- 点击清除文件按钮，触发 handleClearFile 方法 -->
            <n-button
                v-if="!disabled"
                circle
                tertiary
                type="primary"
                size="small"
                @click="handleClearFile(index)"
                class="join-button"
            >
              <template #icon>
                <TheIcon icon="ri:delete-bin-5-line" :size="18"/>
              </template>
            </n-button>
          </div>

        </n-gi>

        <!-- Description列 -->
        <n-gi :span="6">
          <n-input v-model:value="item.desc" placeholder="请输入变量描述" clearable :disabled="disabled"/>
        </n-gi>

        <!-- 删除列，显示“删除”按钮，点击后触发 handleRemove 方法 -->
        <n-gi :span="2">
          <n-button v-if="!disabled" @click="handleRemove(index)" type="primary" tertiary>
            删除
          </n-button>
        </n-gi>
      </n-grid>
    </div>

    <!-- 操作行，显示“添加”按钮，点击后触发 handleAdd 方法 -->
    <div v-if="!disabled" class="add-button-container">
      <n-button @click="handleAdd" type="primary" dashed block class="add-button">
        添加
      </n-button>
    </div>

    <!-- 批量添加模态框 -->
    <n-modal
        v-model:show="isBatchAddModalVisible"
        preset="dialog"
        :title="null"
        :show-icon="false"
        :header-style="{ display: 'none' }"
        positive-text="确认"
        @positive-click="handleBatchAdd"
        style="width: 600px;"
    >
      <n-input
          type="textarea"
          v-model:value="batchInput"
          placeholder="按 key:value:desc 格式输入，每行一个"
          :rows="10"
          style="min-height: 6rem; margin-bottom: 1rem;"
          resize="vertical"
      />
    </n-modal>

  </n-card>
</template>

<script setup>
import {computed, defineEmits, defineProps, ref, watch} from 'vue';
import TheIcon from "@/components/icon/TheIcon.vue";


const props = defineProps({
  // 接收一个数组，包含键值对信息
  items: {
    type: Array,
    required: true
  },
  // 请求体类型，默认为 'none'
  bodyType: {
    type: String,
    default: 'none'
  },
  // 判断是否是请求体部分，默认为 false
  isForBody: {
    type: Boolean,
    default: false
  },
  // 当前步骤之前可用的变量名列表，用于“关联数据”插入 ${xxx}
  availableVariableList: {
    type: Array,
    default: () => []
  },
  // 内置函数列表 [{ name, desc }]，desc 为后端完整 docstring（含参数说明）
  assistFunctions: {
    type: Array,
    default: () => []
  },
  // 只读/置灰，不编辑（如引用脚本步骤查看）
  disabled: {
    type: Boolean,
    default: false
  }
});
// 定义组件的自定义事件
const emit = defineEmits(['add', 'remove', 'update:items']);
// 控制批量添加模态框的显示与隐藏
const isBatchAddModalVisible = ref(false);
// 存储批量输入的内容
const batchInput = ref('');
// 当前打开“关联数据”弹层的行索引，-1 表示未打开
const associationTargetIndex = ref(-1);
// 关联菜单：variables | functions
const associationTab = ref('variables');
const associationSearch = ref('');
const associationPreview = ref('');

const wrapPlaceholder = (inner) => '${' + inner + '}';

const matchAssociationSearch = (text, query) => {
  if (!query?.trim()) return true;
  const q = query.trim().toLowerCase();
  return String(text ?? '').toLowerCase().includes(q);
};

const filteredVariableList = computed(() =>
    props.availableVariableList.filter((name) => matchAssociationSearch(name, associationSearch.value))
);

const filteredAssistFunctions = computed(() =>
    props.assistFunctions.filter((fn) => {
      const name = fn?.name ?? fn ?? '';
      const desc = fn?.desc ?? '';
      return matchAssociationSearch(name, associationSearch.value)
          || matchAssociationSearch(desc, associationSearch.value);
    })
);

const resetAssociationMenuState = (index) => {
  associationSearch.value = '';
  const hasVars = props.availableVariableList.length > 0;
  const hasFns = props.assistFunctions.length > 0;
  associationTab.value = hasVars ? 'variables' : (hasFns ? 'functions' : 'variables');
  const cur = props.items[index]?.value ?? '';
  associationPreview.value = typeof cur === 'string' ? cur : '';
};

const openAssociationPopover = (index) => {
  associationTargetIndex.value = index;
  resetAssociationMenuState(index);
};

const handleAssociationPopoverShow = (visible, index) => {
  if (visible) {
    associationTargetIndex.value = index;
    resetAssociationMenuState(index);
  } else {
    associationTargetIndex.value = -1;
  }
};

const selectAssociationVariable = (name) => {
  associationPreview.value = wrapPlaceholder(name);
};

const selectAssociationFunction = (fn) => {
  associationPreview.value = wrapPlaceholder(fn?.name ?? fn);
};

watch(associationTab, () => {
  associationSearch.value = '';
});

// 计算是否为 form-data 模式且是请求体部分
const isFormDataAndForBody = computed(() => props.bodyType === 'form-data' && props.isForBody);

// 处理添加键值对的方法
const handleAdd = () => {
  // 创建一个新的键值对对象，包含 key、value、desc 字段
  const newItems = [...props.items, {key: '', value: '', desc: '', type: 'text'}];
  // 触发 update:items 事件，更新父组件的 items 数据
  emit('update:items', newItems);
  // 触发 add 事件
  emit('add');
};

// 处理删除键值对的方法
const handleRemove = (index) => {
  // 过滤掉要删除的键值对
  const newItems = props.items.filter((_, i) => i !== index);
  // 触发 update:items 事件，更新父组件的 items 数据
  emit('update:items', newItems);
  // 触发 remove 事件
  emit('remove', index);
};

// 打开批量添加模态框的方法
const openBatchAddModal = () => {
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  $message.warning('该动作会覆盖原有Key-Value内容，请三思！');
  // 将当前的键值对信息格式化为 key:value:desc 格式，填充到批量输入框中
  const nonEmptyItems = props.items.filter(item => item.key || item.value);
  batchInput.value = nonEmptyItems.map(item => {
    if (item.desc) {
      return `${item.key}:${item.value}:${item.desc}`;
    }
    return `${item.key}:${item.value}`;
  }).join('\n');
  isBatchAddModalVisible.value = true;
};

// 处理批量添加的方法
const handleBatchAdd = () => {
  const lines = batchInput.value.split('\n');
  const newItems = [];
  lines.forEach((line) => {
    const parts = line.split(':');
    if (parts.length === 2) {
      const key = parts[0].trim();
      const value = parts[1].trim();
      newItems.push({key, value, desc: '', type: "text"});
    } else if (parts.length === 3) {
      const key = parts[0].trim();
      const value = parts[1].trim();
      const desc = parts[2].trim();
      newItems.push({key, value, desc, type: "text"});
    }
  });
  emit('update:items', newItems);
  emit('add');
  isBatchAddModalVisible.value = false;
  batchInput.value = '';
};

// 处理文件选择的方法
const handleFileChange = (file, index) => {
  const newItems = [...props.items];
  // 更新指定索引的键值对的 value 为选择的文件
  newItems[index].value = file.file;
  emit('update:items', newItems);
};

// 处理清除文件的方法
const handleClearFile = (index) => {
  const newItems = [...props.items];
  // 将指定索引的键值对的 value 清空
  newItems[index].value = '';
  emit('update:items', newItems);
};

// 格式化文件名的方法，如果文件名过长，隐藏中间部分
const formatFileName = (file) => {
  if (!file) return '请选择上传文件';
  if (file instanceof File) {
    const name = file.name;
    if (name.length > 20) {
      const ext = name.split('.').pop();
      const nameWithoutExt = name.slice(0, -(ext.length + 1));
      const firstPart = nameWithoutExt.slice(0, 8);
      const lastPart = nameWithoutExt.slice(-8);
      return `${firstPart}...${lastPart}.${ext}`;
    }
    return name;
  }
  return '请选择上传文件';
};

// 处理类型变化的方法，当类型切换到 text 时，清空文件值
const handleTypeChange = (value, index) => {
  const newItems = [...props.items];
  newItems[index].type = value;
  if (value === 'text') {
    newItems[index].value = '';
  }
  emit('update:items', newItems);
};

// 将预览内容写入指定行 value 并关闭弹层
const confirmAssociationValue = (index) => {
  const newItems = [...props.items];
  newItems[index] = { ...newItems[index], value: associationPreview.value ?? '' };
  emit('update:items', newItems);
  associationTargetIndex.value = -1;
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

/* 确保文件上传按钮与垃圾桶在同一行 */
.file-upload-wrapper,
.text-input-wrapper {
  display: flex;
  align-items: center;
  gap: 5px;
  width: 100%;
}

/* 确保文件上传按钮与输入框宽度一致 */
.file-upload :deep(.n-upload-trigger) {
  width: 100%;
}

.upload-button:hover {
  border-color: #F4511E;
  color: #F4511E;
}

.upload-button:active {
  border-color: #0c7a43;
  color: #0c7a43;
}

/* 确保清除文件&关联数据图标不会移位 */
.join-button {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.association-menu {
  padding: 4px 0 0;
  min-width: 520px;
}

.association-search {
  margin-bottom: 10px;
}

.association-menu-body {
  display: flex;
  min-height: 300px;
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 10px;
}

.association-sidebar {
  flex-shrink: 0;
  width: 128px;
  border-right: 1px solid var(--n-border-color);
  background: var(--n-color-modal);
  padding: 6px 0;
}

.association-sidebar-item {
  padding: 10px 8px 10px 8px;
  font-size: 12px;
  line-height: 1.35;
  word-break: break-all;
  cursor: pointer;
  color: var(--n-text-color-2);
  border-left: 3px solid transparent;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.association-sidebar-item:hover {
  color: #F4511E;
  background: var(--n-color-hover);
}

.association-sidebar-item.active {
  color: #F4511E;
  font-weight: 500;
  border-left-color: #F4511E;
  background: var(--n-color-hover);
}

.association-list-panel {
  flex: 1;
  min-width: 0;
  background: var(--n-color);
}

.association-list-item {
  padding: 8px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--n-border-color);
  transition: background 0.15s;
}

.association-list-item:last-child {
  border-bottom: none;
}

.association-list-item:hover,
.association-list-item.selected {
  background: var(--n-color-hover);
}

.association-list-item:hover .association-list-item-name,
.association-list-item.selected .association-list-item-name {
  color: #F4511E;
}

.association-list-item-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}

.association-list-item-fn .association-list-item-desc {
  margin: 6px 0 0;
  padding: 0;
  font-family: inherit;
  font-size: 10px;
  line-height: 1.5;
  color: #999;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: visible;
  text-overflow: unset;
}

.association-preview-wrap {
  margin-bottom: 10px;
}

.association-preview-label {
  display: block;
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 6px;
}

.association-preview-input :deep(.n-input__textarea-el) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.association-confirm-btn {
  margin-top: 2px;
}

.association-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--n-text-color-3);
  font-size: 13px;
}

</style>
