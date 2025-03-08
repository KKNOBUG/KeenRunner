<template>
  <AppPage>
<!--    <n-layout has-sider class="h-screen">-->
    <n-layout content-style="padding: 25px;" :native-scrollbar="false">
      <n-layout-sider bordered collapse-mode="width" :width="sideWidth">
        <n-space vertical class="p-4" size="large">

          <!-- 代码编辑器容器 -->
          <div class="editor-container">
            <Codemirror
                ref="codeEditorRef"
                v-model="code"
                :placeholder="code"
                :autofocus="true"
                :indent-with-tab="true"
                :tab-size="2"
                :full-screen="true"
                :extensions="extensions"
            />
          </div>

          <n-space>
            <n-button type="primary" size="large" @click="runCode" :loading="isLoading">
              运行代码
            </n-button>
            <n-button type="primary" size="large" @click="formatCode">
              格式化
            </n-button>
          </n-space>

          <n-divider/>
          <div class="editor-container" v-if="result">
            <Codemirror
                ref="resultEditorRef"
                v-model="result"
                :placeholder="result"
                :disabled="false"
                :autofocus="true"
                :indent-with-tab="true"
                :tab-size="2"
                :extensions="extensions"
                :full-screen="true"
            />
          </div>
        </n-space>
      </n-layout-sider>
    </n-layout>
  </AppPage>
</template>

<script setup>
import {ref} from 'vue'
import {Codemirror} from 'vue-codemirror'
import {python} from '@codemirror/lang-python'
import {oneDark} from '@codemirror/theme-one-dark'
import AppPage from "@/components/page/AppPage.vue";
import api from "@/api";

// 根据窗口宽度计算侧边栏宽度
const sideWidth = computed(() => {
  const screenWidth = window.innerWidth;
  if (screenWidth >= 1600) {
    return 1200;
  } else {
    return screenWidth * 0.8; // 占屏幕宽度的80%
  }
});

// 编辑器实例
const code = ref('print("Hello World")')
const result = ref('')
const codeEditorRef = ref(null)
const resultEditorRef = ref(null)
const isLoading = ref(false)
const extensions = [python(), oneDark]

// 格式化代码
const formatCode = () => {
  // 添加格式化逻辑
  console.log('格式化代码')
}

// 运行代码逻辑
const runCode = async () => {
  try {
    isLoading.value = true
    const response = await api.runcodePython({
      code: code.value
    })
    result.value = response.data.result || response.data.error
  } catch (error) {
    result.value = `错误：\n${error.response?.data?.message || error.message}`
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
/*
  编辑器容器样式设置
  - 高度设置为视口高度的 50%，以适应两个编辑器的布局
  - 为容器添加 1px 宽的 #F4511E 颜色边框
  - 设置容器的圆角为 10px，使外观更圆润
  - 隐藏溢出容器的内容
  - 为容器底部添加 20px 的外边距，用于分隔不同的编辑器容器
*/
:deep(.editor-container) {
  height: 50vh;
  border: 1px solid #F4511E;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 20px;
}

/*
  编辑器主体样式设置
  - 高度设置为 100%，使其填满父容器（编辑器容器）
  - 设置编辑器的背景颜色为 #282c34
  - 设置编辑器内文本的颜色为 #abb2bf
*/
:deep(.cm-editor) {
  height: 100%;
  background: #282c34;
  color: #abb2bf;
}

/*
  编辑器滚动区域样式设置
  - 设置编辑器内文本的字体为 'Fira Code' 等宽字体
  - 设置行高为 1.6，使文本行间距更舒适
  - 去除滚动区域的内边距
*/
:deep(.cm-editor .cm-scroller) {
  font-family: 'Fira Code', monospace;
  line-height: 1.6;
  padding: 0;
}

/*
  编辑器行号区域样式设置
  - 设置行号区域的背景颜色为 #282c34
  - 为行号区域右侧添加 1px 宽的 #3e4451 颜色分隔线
  - 设置行号文本的颜色为 #5c6370
*/
:deep(.cm-editor .cm-gutters) {
  background: #282c34;
  border-right: 1px solid #3e4451;
  color: #5c6370;
}

/*
  编辑器聚焦行号区域样式设置
  - 当某一行被聚焦时，设置该行号区域的背景颜色为 #2c313a
*/
:deep(.cm-editor .cm-activeLineGutter) {
  background-color: #2c313a;
}

/*
  编辑器聚焦行样式设置
  - 当某一行被聚焦时，设置该行的背景颜色为 #2c313a
*/
:deep(.cm-editor .cm-activeLine) {
  background-color: #2c313a;
}

/*
  编辑器光标样式设置
  - 设置编辑器光标的样式为 2px 宽的 #F4511E 颜色的左侧边框
*/
:deep(.cm-editor .cm-cursor) {
  border-left: 2px solid #F4511E;
}

/*
  编辑器容器内滚动条样式设置（WebKit 内核浏览器）
  - 设置纵向滚动条的宽度为 0.5px，使其更细
  - 设置横向滚动条的高度为 0.5px，使其更细
*/
:deep(.cm-editor .cm-scroller::-webkit-scrollbar) {
  width: 5px;
  height: 5px;
}

/*
  编辑器容器内滚动条滑块样式设置（WebKit 内核浏览器）
  - 设置滚动条滑块的背景颜色为 #F4511E
  - 设置滚动条滑块的圆角为 10px，使其外观更圆润
  - 为滚动条滑块添加 1px 宽的 #282c34 颜色边框
*/
:deep(.cm-editor .cm-scroller::-webkit-scrollbar-thumb) {
  background-color: #F4511E;
  border-radius: 10px;
  border: 1px solid #282c34;
}

/*
  编辑器容器内滚动条轨道样式设置（WebKit 内核浏览器）
  - 设置滚动条轨道的背景颜色为 #282c34
*/
:deep(.cm-editor .cm-scroller::-webkit-scrollbar-track) {
  background-color: #282c34;
}

/*
  编辑器容器内滚动条样式设置（Firefox 浏览器）
  - 设置滚动条的宽度为 thin，使其更细
  - 设置滚动条滑块的颜色为 #F4511E，轨道颜色为 #282c34
*/
:deep(.cm-editor .cm-scroller) {
  scrollbar-width: thin;
  scrollbar-color: #F4511E #282c34;
}

/*
  编辑器容器内文本全选样式设置
  - 当在编辑器内全选文本时，设置选中区域的背景颜色为 #3e4451
  - 设置选中区域内文本的颜色为 #fff
*/
:deep(.cm-editor .cm-content ::selection) {
  background-color: #3e4451;
  color: #fff;
}
</style>
