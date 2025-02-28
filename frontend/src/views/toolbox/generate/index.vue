<template>
  <AppPage>
    <n-card style="margin-bottom: 16px">
      <n-tabs default-value="person" justify-content="space-evenly" type="line">
        <n-tab-pane name="person" tab="人员信息">
          <n-form
              ref="formRef"
              :model="model"
              :rules="rules"
              label-placement="left"
              label-width="auto"
              require-mark-placement="right-hanging"
              size="medium"
              :style="{ maxWidth: '650px' }"
          >
            <n-form-item label="生成数量：" path="number">
              <n-input-number v-model:value="model.number" clearable min="1"/>
            </n-form-item>
            <n-form-item label="生成年龄：" path="age">
              <n-input pair separator="-" type="number" clearable
                       :placeholder="placeholder" v-model:value="model.age"/>
            </n-form-item>
            <n-form-item label="生成选择：" path="option">
              <n-transfer v-model:value="model.option" :options="generalOptions"/>
            </n-form-item>
            <n-button type="primary" size="large" @click="generateBtn">
              生成数据
            </n-button>
          </n-form>
          <!-- 结果展示区域 -->
          <n-divider/>
          <div v-if="showResult" class="result-container">
            <n-card>
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                <n-button @click="copyResult">复制结果</n-button>
              </div>
              <pre ref="jsonPre">{{ JSON.stringify(resultData, null, 4) }}</pre>
            </n-card>
          </div>
        </n-tab-pane>
        <n-tab-pane name="datetime" tab="时间日期">
          时间日期2
        </n-tab-pane>
        <n-tab-pane name="jay chou" tab="随机数">
          随机数3
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </AppPage>
</template>

<script>
import {defineComponent, ref} from "vue";
import { useMessage } from "naive-ui";
import hljs from "highlight.js";
import "highlight.js/styles/default.css";
import api from "@/api";

export default defineComponent({
  setup() {
    const formRef = ref(null);
    const model = ref({number: 1, age: null, option: null})
    const showResult = ref(false);
    const resultData = ref([]);
    const jsonPre = ref(null);
    const message = useMessage();


    // 验证输入的年龄区间
    const inputAgeRangeValid = (rule, value, callback) => {
      if (!value || value.length !== 2) {
        callback(new Error("请输入有效的年龄范围"));
      } else {
        const [minAge, maxAge] = value.map(Number);
        if (isNaN(minAge) || isNaN(maxAge) || minAge <= 0 || maxAge <= 0) {
          callback(new Error("请输入大于0的正整数"));
        } else if (maxAge < minAge) {
          callback(new Error("最小年龄必须小于等于最大年龄"));
        } else {
          callback();
        }
      }
    };

    // 定义输入框的规则
    const rules = {
      number: {
        type: "integer",
        required: true,
        trigger: ["blur", "change"],
        message: "请输入大于0的正整数",
      },
      age: {
        required: true,
        validator: inputAgeRangeValid,
        trigger: ["blur", "change"],
      },
      option: {
        required: true,
        trigger: ["blur", "change"],
        validator: (rule, value, callback) => {
          if (!value || value.length === 0) {
            callback(new Error("请选择生成选项"));
          } else {
            callback();
          }
        }
      }
    };
    // 请求后端
    const generateBtn = async () => {
      try {
        // 解构 age 列表为 minAge 和 maxAge
        const { age, ...rest } = model.value;
        const [minAge, maxAge] = age || [];
        const requestData = {
          ...rest,
          minAge,
          maxAge
        };
        const response = await api.fakerPerson(requestData);
        console.log("提交成功", response.data);
        // 处理接口返回数据
        setResultData(response.data);
        setShowResult(true);
        // 使用 nextTick 确保 DOM 更新后再高亮
        nextTick(() => {
          highlightJson();
        });
      } catch (error) {
        console.error("提交失败", error);
        setShowResult(false);
      }
    };

    const setShowResult = (value) => {
      showResult.value = value;
    };
    const setResultData = (data) => {
      resultData.value = data;
    };

    onMounted(() => {
      highlightJson();
    });

    const highlightJson = () => {
      if (jsonPre.value) {
        // 手动指定 JSON 语法模式
        jsonPre.value.innerHTML = hljs.highlight(jsonPre.value.textContent, {language: 'json'}).value;
      }
    };

    const copyResult = async () => {
      try {
        const jsonStr = JSON.stringify(resultData.value, null, 4);
        await navigator.clipboard.writeText(jsonStr);
        message.success('复制成功');
      } catch (error) {
        console.error('复制失败', error);
        message.error('复制失败');
      }
    };
    return {
      model,
      rules,
      formRef,
      generateBtn,
      size: ref("small"),
      placeholder: ["最小年龄", "最大年龄"],
      generalOptions: [
        "中文姓名",
        "英文姓名",
        "年龄",
        "性别",
        "证件号码",
        "银行卡号",
        "手机号码",
        "电子邮箱",
        "家庭住址",
        "公司名称",
        "公司地址",
        "工作职位",
        "出生年月(Ymd)",
        "出生年月(Y-m-d)"
      ].map((v) => ({
        label: v,
        value: v
      })),
      showResult,
      resultData,
      highlightJson,
      jsonPre,
      copyResult,
      message
    };
  }
});
</script>
