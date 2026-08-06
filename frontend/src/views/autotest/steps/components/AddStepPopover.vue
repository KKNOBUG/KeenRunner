<!--
  AddStepPopover — 「添加步骤」菜单

  面板样式交给 NPopover 默认主题（背景 / 圆角 / 阴影），仅补充与条件步骤一致的左侧强调线。
-->
<template>
  <n-popover
      :show="show"
      trigger="click"
      placement="bottom"
      to="body"
      flip
      :width="330"
      :show-arrow="true"
      :content-style="popoverContentStyle"
      @update:show="handleShowUpdate"
  >
    <template #trigger>
      <n-button
          dashed
          size="small"
          class="add-step-trigger-btn"
          @click.stop="openPopover"
      >
        添加步骤
      </n-button>
    </template>
    <div class="add-step-menu-scroll overlay-scroll">
      <div class="add-step-menu">
        <section
            v-for="section in menuSections"
            :key="section.key"
            class="add-step-section"
        >
          <div class="add-step-section-title">{{ section.label }}</div>
          <div
              v-for="item in section.items"
              :key="item.key"
              class="add-step-item"
              :class="{ 'is-disabled': item.disabled }"
              @click="handleSelectItem(item)"
          >
            <TheIcon
                v-if="item.iconName"
                :icon="item.iconName"
                :size="16"
                class="add-step-item-icon"
                :class="item.iconClass"
            />
            <div class="add-step-item-body">
              <div class="add-step-item-title">{{ item.label }}</div>
              <div v-if="item.desc" class="add-step-item-desc">{{ item.desc }}</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </n-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { NButton, NPopover } from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'


/** 与 index.vue stepDefinitions / getStepIcon 一致 */
const STEP_ICON = {
  user_variables: 'gravity-ui:magic-wand',
  http: 'streamline-freehand:server-api-cloud',
  tcp: 'streamline-freehand:server-api-cloud',
  code: 'ph:file-py',
  database: 'ph:file-sql',
  redis: 'ph:file-rs',
  assert: 'material-symbols:rule',
  wait: 'gravity-ui:stopwatch',
  if: 'gravity-ui:shuffle',
  loop: 'gravity-ui:arrows-rotate-right',
  quote_public_script: 'gravity-ui:link',
}

/** 与 index.vue getStepIconClass 一致，用于图标着色 */
const STEP_ICON_CLASS = {
  user_variables: 'icon-user_variables',
  http: 'icon-http',
  tcp: 'icon-tcp',
  code: 'icon-code',
  database: 'icon-database',
  redis: 'icon-redis',
  assert: 'icon-assert',
  wait: 'icon-wait',
  if: 'icon-if',
  loop: 'icon-loop',
  quote_public_script: 'icon-quote',
  copy_steps: 'icon-quote',
  batch_upload_datasource: 'icon-datasource',
  summary_download_datasource: 'icon-datasource',
}

const props = defineProps({
  /** 当前用例属于「公共家族」（公共脚本/公共接口）时禁用「引用公共脚本」与数据驱动 */
  isPublicFamilyCase: { type: Boolean, default: false },
  /** 当前用例为「公共接口」时仅可添加 HTTP/TCP 请求步骤 */
  isPublicApiCase: { type: Boolean, default: false },
})

const emit = defineEmits(['select'])

const show = ref(false)

/** 限制弹层高度并在视口内可滚动，避免底部步骤树区域裁切导致首项「用户变量」不可点 */
const popoverContentStyle = {
  maxHeight: 'min(400px, calc(100vh - 112px))',
  boxSizing: 'border-box',
}

const buildItem = (key, { label, desc, iconName, disabled } = {}) => {
  const labels = {
    user_variables: '用户变量',
    http: 'HTTP请求',
    tcp: 'TCP请求',
    code: '代码请求(Python)',
    database: '数据库请求',
    redis: 'Redis请求',
    assert: '断言',
    wait: '等待控制',
    if: '条件分支',
    loop: '循环结构',
    quote_public_script: '引用公共脚本',
    copy_steps: '复制指定脚本',
    batch_upload_datasource: '批量上传数据源',
    summary_download_datasource: '汇总下载数据源',
  }
  return {
    key,
    label: label ?? labels[key] ?? key,
    desc: desc ?? '',
    iconName: iconName ?? STEP_ICON[key] ?? null,
    iconClass: STEP_ICON_CLASS[key] ?? '',
    disabled: !!disabled,
  }
}

const menuSections = computed(() => {
  const isPublic = props.isPublicFamilyCase
  // 公共接口：有且仅允许 1 个 HTTP/TCP 请求步骤，其余类型一律禁用
  const onlyHttpTcp = props.isPublicApiCase
  return [
    {
      key: 'basic',
      label: '基础步骤',
      items: [
        buildItem('user_variables', {
          desc: '创建全局变量，支持调用内置函数，供后续步骤引用',
          disabled: onlyHttpTcp,
        }),
        buildItem('http', {
          desc: '发送 HTTP/HTTPS 协议请求，验证或提取响应数据',
        }),
        buildItem('tcp', {
          desc: '发送 TCP 协议请，验证或提取响应数据',
        }),
        buildItem('code', {
          desc: '运行自定义的Python脚本，实现复杂的逻辑扩展',
          disabled: onlyHttpTcp,
        }),
        buildItem('database', {
          desc: '执行 SQL 语句，验证数据状态与完整性',
          disabled: onlyHttpTcp,
        }),
        buildItem('redis', {
          desc: '执行Redis命令操作以验证数据完整性',
          disabled: onlyHttpTcp,
        }),
        buildItem('assert', {
          desc: '对变量池或响应数据进行断言校验，比较符与 HTTP 断言一致',
          disabled: onlyHttpTcp,
        }),
      ],
    },
    {
      key: 'reuse',
      label: '复用步骤',
      items: [
        buildItem('quote_public_script', {
          desc: '调用公共脚本，复用已编写完成的测试脚本',
          disabled: isPublic,
        }),
        buildItem('copy_steps', {
          desc: '复制指定脚本，快速复用并创建自定义逻辑',
          iconName: 'material-symbols:content-copy-outline',
          disabled: onlyHttpTcp,
        }),
      ],
    },
    {
      key: 'control',
      label: '控制步骤',
      items: [
        buildItem('wait', {
          desc: '等待指定时间，再继续执行后续的步骤',
          disabled: onlyHttpTcp,
        }),
        buildItem('if', {
          desc: '根据条件判断结果，选择不同的执行路径',
          disabled: onlyHttpTcp,
        }),
        buildItem('loop', {
          desc: '重复执行一组步骤，直到满足退出条件',
          disabled: onlyHttpTcp,
        }),
      ],
    },
    {
      key: 'data_driven',
      label: '数据驱动',
      items: [
        buildItem('batch_upload_datasource', {
          desc: '为多个请求步骤上传数据源文件（以落库数据为准）',
          iconName: 'cuida:upload-outline',
          disabled: isPublic,
        }),
        buildItem('summary_download_datasource', {
          desc: '下载所有请求步骤的数据源文件（以落库数据为准）',
          iconName: 'cuida:download-outline',
          disabled: isPublic,
        }),
      ],
    },
  ]
})

const openPopover = () => {
  show.value = true
}

const handleShowUpdate = (v) => {
  show.value = v
}

const handleSelectItem = (item) => {
  if (item.disabled) return
  emit('select', item.key)
  show.value = false
}
</script>

<style scoped>
.add-step-trigger-btn {
  font-size: 12px;
  border-radius: 8px;
  width: 99%;
}

.add-step-menu-scroll {
  /* 添加步骤菜单：限高滚动，滚动条样式见全局 .overlay-scroll */
  max-height: min(400px, calc(100vh - 112px));
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.add-step-menu {
  width: 100%;
}

.add-step-section + .add-step-section {
  margin-top: 10px;
}

.add-step-section-title {
  padding: 1px 1px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.15;
}

.add-step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  margin-bottom: 1px;
  cursor: pointer;
}

.add-step-item:hover:not(.is-disabled) .add-step-item-title {
  color: #F4511E;
}

.add-step-item.is-disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.add-step-item-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.add-step-item-icon.icon-loop,
.add-step-item-icon.icon-if,
.add-step-item-icon.icon-wait,
.add-step-item-icon.icon-datasource,
.add-step-item-icon.icon-quote {
  color: #F4511E;
}

.add-step-item-icon.icon-code,
.add-step-item-icon.icon-database,
.add-step-item-icon.icon-redis,
.add-step-item-icon.icon-assert {
  color: #BA55D3;
}

.add-step-item-icon.icon-tcp,
.add-step-item-icon.icon-http {
  color: #2080F0;
}

/* 紫色：color: #BA55D3; */
.add-step-item-icon.icon-user_variables {
  color: #FF69B4;
}

.add-step-item-body {
  flex: 1;
  min-width: 0;
}

.add-step-item-title {
  font-size: 12px;
  line-height: 1.15;
  transition: color 0.15s;
}

.add-step-item-desc {
  margin-top: 5px;
  font-size: 11px;
  color: var(--n-text-color-3, #999);
  line-height: 1.15;
  word-break: break-word;
}
</style>
