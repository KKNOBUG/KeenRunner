<template>
  <AppPage :show-footer="false">
    <div flex-1>
      <!--   信息栏   -->
      <n-card rounded-10>
        <div flex items-center justify-between>
          <div flex items-center>
            <img rounded-full width="80" :src="userStore.avatar"/>
            <div ml-10>
              <p text-20 font-semibold>
                {{ $t('views.workbench.text_hello', {timer: currentTimePeriod(regards=true), alias: userStore.alias, username: userStore.username}) }}
              </p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_welcome', {welcome: welcomeMessage}) }}</p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_last_login', {lastLogin: userStore.lastLogin}) }}</p>
            </div>
          </div>
          <div class="statistic-container">
          <n-space :size="20" :wrap="false">
            <n-card v-for="item in statisticData" :key="item.id" class="statistic-card">
              <n-statistic v-bind="item"></n-statistic>
            </n-card>
          </n-space>
          </div>
        </div>
      </n-card>

      <!--   项目栏   -->
      <n-card
          :title="$t('views.workbench.label_project')"
          size="small"
          :segmented="true"
          mt-15
          rounded-10>
        <template #header-extra>
          <n-button text type="primary">{{ $t('views.workbench.label_more') }}</n-button>
        </template>
        <div flex flex-wrap justify-between>
          <n-card
              v-for="i in 12"
              :key="i"
              class="mb-10 mt-10 w-300 cursor-pointer"
              hover:card-shadow
              title="Krun test management system"
              size="small">
            <p op-60>{{ dummyText }}</p>
          </n-card>
        </div>
      </n-card>
    </div>
  </AppPage>
</template>

<script setup>
import {useUserStore} from '@/store'
import {useI18n} from 'vue-i18n'
import {currentTimePeriod} from "@/utils";

const dummyText = '一个基于 Vue3.0、FastAPI、Naive UI 的轻量级后台管理模板'
const {t} = useI18n({useScope: 'global'})

// 生成 1 到 100 之间的随机数字字符串
const randomNumber = Math.floor(Math.random() * 100) + 1
const randomNumberStr = randomNumber.toString()

// 拼接字符串
const welcomeMessage = computed(() => {
  return t(`welcome.${randomNumberStr}`)
})

const statisticData = computed(() => [
  {
    id: 0,
    label: t('views.workbench.label_number_of_items'),
    value: '2',
  },
  {
    id: 1,
    label: t('views.workbench.label_number_of_apis'),
    value: '107',
  },
  {
    id: 2,
    label: t('views.workbench.label_number_of_ui_cases'),
    value: '288',
  },
  {
    id: 3,
    label: t('views.workbench.label_number_of_api_cases'),
    value: '25',
  },
  {
    id: 4,
    label: t('views.workbench.label_number_of_tasks'),
    value: '25',
  },
])

const userStore = useUserStore()
</script>

<style scoped>
.statistic-container {
  max-width: 65%; /* 设置最大宽度 */
  overflow-x: auto; /* 超出宽度时显示横向滚动条 */
}

/* 定义统计卡片的默认样式 */
.statistic-card {
  width: 150px; /* 固定宽度 */
  border: 1px solid #e5e5e5; /* 移除默认边框 */
  border-radius: 12px; /* 圆角边框 */
  background-color: #f9f9f9; /* 背景颜色 */
  box-shadow: 5px 5px 5px rgba(0, 0, 0, 0.01); /* 阴影效果 */
  padding: 5px; /* 内边距 */
  transition: border-color 0.3s; /* 过渡动画 */
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* 定义统计卡片的悬浮样式 */
.statistic-card:hover {
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2); /* 悬停时阴影加深 */
  border-color: #F4511E; /* 悬浮时的边框颜色，这里使用蓝色作为示例 */
}
</style>
