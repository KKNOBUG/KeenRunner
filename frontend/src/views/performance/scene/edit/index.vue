<!--
  压测场景独立编辑页 — 左侧步骤导航 + 右侧内容区逐个向下编写

  路由 /performance/scene/edit?scene_id=xxx；新增时 scene_id 为空。
  保存时聚合为 PerfSceneWizardPayload 一次提交到 /perf/scene/save_wizard；
  负载预设步骤支持批量派生档位（拐点测试）与一键跑全部。

  UX 设计：
  - 页面采用 AppPage 全屏布局（对齐 api/edit 子页设计语言）
  - 左侧固定宽度导航面板，垂直步骤列表 + 完成态指示 + 进度概览
  - 右侧内容区以 n-card 分块呈现，对齐 step-editor-card 设计令牌
  - 底部固定操作栏，上一步/下一步引导顺序流
-->
<template>
  <AppPage>
    <div class="scene-wizard">
      <!-- ====== 左侧导航面板 ====== -->
      <aside class="scene-wizard__nav">
        <div class="scene-wizard__nav-header">
          <div class="scene-wizard__nav-title">场景配置</div>
          <div class="scene-wizard__nav-progress">
            {{ completedCount }}/{{ stepList.length }} 已完成
          </div>
        </div>

        <nav class="scene-wizard__nav-list">
          <div
              v-for="(step, idx) in stepList"
              :key="step.key"
              class="scene-wizard__nav-item"
              :class="{
                'is-active': currentStep === idx + 1,
                'is-completed': stepCompleted[idx],
                'is-upcoming': !stepCompleted[idx] && currentStep !== idx + 1,
              }"
              @click="currentStep = idx + 1"
          >
            <div class="scene-wizard__nav-indicator">
              <span v-if="stepCompleted[idx] && currentStep !== idx + 1" class="scene-wizard__nav-check">✓</span>
              <span v-else class="scene-wizard__nav-num">{{ idx + 1 }}</span>
            </div>
            <div class="scene-wizard__nav-content">
              <div class="scene-wizard__nav-label">{{ step.title }}</div>
              <div class="scene-wizard__nav-desc">{{ step.desc }}</div>
            </div>
          </div>
        </nav>

        <div class="scene-wizard__nav-footer">
          <n-button size="small" quaternary @click="handleBack">← 返回列表</n-button>
        </div>
      </aside>

      <!-- ====== 右侧主内容区 ====== -->
      <div class="scene-wizard__main">
        <!-- 内容滚动区 -->
        <div class="scene-wizard__content">
          <!-- 步骤一：基础信息 -->
          <section v-show="currentStep === 1" class="scene-wizard__section">
            <div class="scene-wizard__section-header">
              <h3 class="scene-wizard__section-title">基础信息</h3>
              <p class="scene-wizard__section-desc">定义场景归属与流量结构模式，后续步骤的接口候选与环境解析均依赖此处选择的应用。</p>
            </div>

            <n-card :bordered="false" class="scene-wizard__card">
              <n-form ref="basicFormRef" :model="form" label-placement="top" require-mark-placement="right-hanging">
                <n-grid :cols="2" :x-gap="24" :y-gap="4">
                  <n-gi>
                    <n-form-item label="所属应用" path="scene_project" :rule="projectRule">
                      <n-select
                          v-model:value="form.scene_project"
                          :options="projectOptions"
                          :disabled="isEdit"
                          placeholder="请选择所属应用"
                          clearable
                          filterable
                          @update:value="handleProjectChange"
                      />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="场景名称" path="scene_name" :rule="{ required: true, message: '请输入场景名称' }">
                      <n-input v-model:value="form.scene_name" placeholder="例如：订单核心链路压测" clearable />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="施压模式">
                      <n-radio-group v-model:value="form.run_mode" name="run_mode">
                        <n-radio-button value="single">单接口</n-radio-button>
                        <n-radio-button value="mixed">混合流量</n-radio-button>
                      </n-radio-group>
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="场景描述">
                      <n-input v-model:value="form.scene_desc" placeholder="简要说明压测目的（可选）" clearable />
                    </n-form-item>
                  </n-gi>
                </n-grid>
              </n-form>
            </n-card>

            <n-alert :bordered="false" type="info" class="scene-wizard__alert">
              {{ runModeHint }}
            </n-alert>
          </section>

          <!-- 步骤二：接口编排 -->
          <section v-show="currentStep === 2" class="scene-wizard__section">
            <div class="scene-wizard__section-header">
              <h3 class="scene-wizard__section-title">接口编排</h3>
              <p class="scene-wizard__section-desc">从压测接口资产中选择被测接口，配置角色、权重与思考时间。混合流量模式下多接口按权重并发施压。</p>
            </div>

            <n-card :bordered="false" class="scene-wizard__card">
              <template #header>
                <div class="scene-wizard__card-toolbar">
                  <n-space align="center" :size="8">
                    <n-tag size="small" :bordered="false" type="info">{{ form.scene_items.length }} 个接口项</n-tag>
                    <n-text v-if="!form.scene_project" depth="3" style="font-size: 12px">请先完成「基础信息」步骤选择所属应用</n-text>
                  </n-space>
                  <n-button size="small" type="primary" :disabled="!form.scene_project" @click="openSelectPanel">
                    + 添加接口
                  </n-button>
                </div>
              </template>

              <n-empty v-if="!form.scene_items.length" description="尚未选择被测接口，点击上方按钮添加" style="padding: 48px 0">
                <template #extra>
                  <n-button size="small" type="primary" :disabled="!form.scene_project" @click="openSelectPanel">添加接口</n-button>
                </template>
              </n-empty>
              <n-data-table
                  v-else
                  :columns="itemColumns"
                  :data="form.scene_items"
                  :pagination="false"
                  :row-key="(row) => row.api_code"
                  size="small"
                  :max-height="480"
                  :scroll-x="1560"
                  :bordered="false"
                  striped
              />
            </n-card>
          </section>

          <!-- 步骤三：判定口径 -->
          <section v-show="currentStep === 3" class="scene-wizard__section">
            <div class="scene-wizard__section-header">
              <h3 class="scene-wizard__section-title">判定口径</h3>
              <p class="scene-wizard__section-desc">配置 SLA 达标目标、熔断保护与断言策略。报告生成后按此口径自动判定通过/告警/失败。</p>
            </div>

            <!-- SLA 目标 -->
            <n-card :bordered="false" class="scene-wizard__card" title="SLA 目标">
              <template #header-extra>
                <n-button size="tiny" quaternary type="primary" @click="addTarget">+ 添加</n-button>
              </template>
              <n-text depth="3" style="font-size: 12px; display: block; margin-bottom: 12px">
                逐条绝对判定，与熔断、基线退化相互独立；未配置时报告仅呈现统计不做达标判定。
              </n-text>
              <n-empty v-if="!form.perf_targets.length" description="未配置 SLA 目标" size="small" style="padding: 24px 0" />
              <div v-else class="scene-wizard__target-list">
                <div v-for="(target, index) in form.perf_targets" :key="index" class="scene-wizard__target-row">
                  <span class="scene-wizard__target-idx">{{ index + 1 }}</span>
                  <n-grid :cols="24" :x-gap="8" class="scene-wizard__target-fields">
                    <n-gi :span="4">
                      <n-select v-model:value="target.scope" :options="PERF_TARGET_SCOPE_OPTIONS" size="small" placeholder="层级" @update:value="() => handleTargetScopeChange(target)" />
                    </n-gi>
                    <n-gi :span="4">
                      <n-select v-model:value="target.target" :options="PERF_TARGET_METRIC_OPTIONS" size="small" placeholder="指标" />
                    </n-gi>
                    <n-gi v-if="target.scope === 'api'" :span="4">
                      <n-select v-model:value="target.api_code" :options="itemApiOptions" placeholder="选择接口" size="small" filterable />
                    </n-gi>
                    <n-gi v-if="target.scope === 'transaction'" :span="4">
                      <n-select v-model:value="target.transaction" :options="transactionOptions" placeholder="选择事务" size="small" filterable tag />
                    </n-gi>
                    <n-gi :span="6">
                      <n-input-group size="small">
                        <n-select v-model:value="target.op" :options="PERF_TARGET_OP_OPTIONS" style="width: 70px" size="small" />
                        <n-input-number v-model:value="target.expect" placeholder="期望值" style="width: 100%" :show-button="false" size="small" />
                      </n-input-group>
                    </n-gi>
                    <n-gi :span="3">
                      <n-select v-model:value="target.severity" :options="PERF_TARGET_SEVERITY_OPTIONS" size="small" />
                    </n-gi>
                    <n-gi :span="3" style="display: flex; align-items: center">
                      <n-button size="tiny" type="error" quaternary @click="removeTarget(index)">删除</n-button>
                    </n-gi>
                  </n-grid>
                </div>
              </div>
            </n-card>

            <!-- 熔断与基线 -->
            <n-card :bordered="false" class="scene-wizard__card" title="熔断与基线退化">
              <n-form label-placement="left" label-width="90" size="small">
                <n-grid :cols="3" :x-gap="20" :y-gap="0">
                  <n-gi>
                    <n-form-item label="熔断阈值(%)">
                      <n-input-number v-model:value="form.error_rate_threshold" style="width: 100%" :min="0" :max="100" placeholder="0或留空=不熔断" clearable />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="预热剔除(秒)">
                      <n-input-number v-model:value="form.warmup_seconds" style="width: 100%" :min="0" :max="300" placeholder="留空自动派生" clearable />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="基线报告">
                      <n-input v-model:value="form.baseline_report_code" placeholder="报告标识（选填）" clearable />
                    </n-form-item>
                  </n-gi>
                </n-grid>
                <n-divider style="margin: 8px 0" />
                <n-grid :cols="3" :x-gap="20" :y-gap="0">
                  <n-gi>
                    <n-form-item label="P95 退化(%)">
                      <n-input-number v-model:value="form.baseline_policy.p95_degrade_pct" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="RPS 退化(%)">
                      <n-input-number v-model:value="form.baseline_policy.qps_degrade_pct" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="错误率+(%)">
                      <n-input-number v-model:value="form.baseline_policy.error_rate_increase" style="width: 100%" :min="0" :max="100" :show-button="false" clearable />
                    </n-form-item>
                  </n-gi>
                </n-grid>
              </n-form>
            </n-card>

            <!-- 断言策略 -->
            <n-card :bordered="false" class="scene-wizard__card" title="断言与标记">
              <n-form label-placement="left" label-width="90" size="small">
                <n-grid :cols="3" :x-gap="20">
                  <n-gi>
                    <n-form-item label="断言口径">
                      <n-radio-group v-model:value="form.assert_mode" name="assert_mode" size="small">
                        <n-radio-button v-for="opt in PERF_ASSERT_MODE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</n-radio-button>
                      </n-radio-group>
                    </n-form-item>
                  </n-gi>
                  <n-gi v-if="form.assert_mode === 'sample_ratio'">
                    <n-form-item label="采样比例(%)">
                      <n-input-number v-model:value="form.sample_ratio" style="width: 100%" :min="0.1" :max="100" />
                    </n-form-item>
                  </n-gi>
                  <n-gi>
                    <n-form-item label="压测标记头">
                      <n-switch v-model:value="form.inject_perf_tag" />
                    </n-form-item>
                  </n-gi>
                </n-grid>
              </n-form>
            </n-card>
          </section>

          <!-- 步骤四：负载预设 -->
          <section v-show="currentStep === 4" class="scene-wizard__section">
            <div class="scene-wizard__section-header">
              <h3 class="scene-wizard__section-title">负载预设</h3>
              <p class="scene-wizard__section-desc">每份预设定义一组负载参数（并发/阶梯/RPS）。同一场景下多份预设共享编排与判定口径，报告天然可比——即拐点测试的基本单位。</p>
            </div>

            <n-card :bordered="false" class="scene-wizard__card">
              <template #header>
                <div class="scene-wizard__card-toolbar">
                  <n-tag size="small" :bordered="false" type="info">{{ activePresetCount }} 份预设</n-tag>
                  <n-space :size="8">
                    <n-button size="small" :disabled="!form.presets.length" @click="openBatchDuplicate">批量派生</n-button>
                    <n-button size="small" type="success" :disabled="!isEdit || !form.presets.length" :loading="runningAll" @click="handleRunAll">一键跑全部</n-button>
                    <n-button size="small" type="primary" @click="addPreset">+ 新增预设</n-button>
                  </n-space>
                </div>
              </template>

              <n-empty v-if="!form.presets.length" description="尚未配置负载预设" style="padding: 48px 0">
                <template #extra>
                  <n-button size="small" type="primary" @click="addPreset">新增预设</n-button>
                </template>
              </n-empty>

              <div v-else class="scene-wizard__preset-list">
                <div
                    v-for="(preset, index) in form.presets"
                    :key="preset._key"
                    class="scene-wizard__preset-item"
                    :class="{ 'is-deleted': preset._delete }"
                >
                  <div class="scene-wizard__preset-head">
                    <div class="scene-wizard__preset-id">
                      <span class="scene-wizard__preset-num">{{ index + 1 }}</span>
                      <n-input
                          v-if="!preset._delete"
                          v-model:value="preset.preset_name"
                          size="small"
                          placeholder="预设名称"
                          style="width: 180px"
                          :bordered="false"
                          class="scene-wizard__preset-name"
                      />
                      <span v-else class="scene-wizard__preset-name-text">{{ preset.preset_name || '未命名' }}</span>
                      <n-tag v-if="preset._delete" size="tiny" type="error" :bordered="false">待删除</n-tag>
                      <n-tag v-else-if="preset.preset_id" size="tiny" type="success" :bordered="false">已保存</n-tag>
                      <n-tag v-else size="tiny" :bordered="false">新增</n-tag>
                    </div>
                    <n-space :size="4">
                      <n-button v-if="preset._delete" size="tiny" quaternary @click="restorePreset(index)">恢复</n-button>
                      <n-button v-else size="tiny" type="error" quaternary @click="markDeletePreset(index)">删除</n-button>
                    </n-space>
                  </div>

                  <div v-if="!preset._delete" class="scene-wizard__preset-body">
                    <n-grid :cols="4" :x-gap="16" :y-gap="0">
                      <n-gi>
                        <n-form-item label="施压环境" :label-width="64" size="small" :show-feedback="false">
                          <n-select
                              v-model:value="preset.env_name"
                              :options="envOptions"
                              :loading="envLoading"
                              clearable
                              filterable
                              placeholder="可留空"
                              size="small"
                              @update:value="(v) => handlePresetEnvChange(preset, v)"
                          />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="APP配置" :label-width="64" size="small" :show-feedback="false">
                          <n-select
                              v-model:value="preset.env_config_name"
                              :options="getConfigOptions(preset.env_name)"
                              :loading="configLoading"
                              :disabled="!preset.env_name"
                              clearable
                              filterable
                              placeholder="缺省配置"
                              size="small"
                          />
                        </n-form-item>
                      </n-gi>
                      <n-gi :span="2">
                        <n-form-item label="施压模式" :label-width="64" size="small" :show-feedback="false">
                          <n-radio-group v-model:value="preset.load_mode" size="small">
                            <n-radio-button value="fixed">固定并发</n-radio-button>
                            <n-radio-button value="stepped">阶梯加压</n-radio-button>
                            <n-radio-button value="rps">RPS</n-radio-button>
                          </n-radio-group>
                        </n-form-item>
                      </n-gi>
                    </n-grid>

                    <!-- fixed / rps 参数 -->
                    <n-grid v-if="preset.load_mode !== 'stepped'" :cols="4" :x-gap="16" :y-gap="0" class="scene-wizard__preset-params">
                      <n-gi>
                        <n-form-item label="并发" :label-width="40" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.concurrent_users" :min="1" :max="5000" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="速率" :label-width="40" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.spawn_rate" :min="1" :max="1000" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="时长(s)" :label-width="48" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.run_duration" :min="1" :max="28800" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi v-if="preset.load_mode === 'rps'">
                        <n-form-item label="RPS" :label-width="36" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.target_rps" :min="0.1" :max="1000000" :step="10" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                    </n-grid>

                    <!-- stepped 参数 -->
                    <n-grid v-else :cols="5" :x-gap="12" :y-gap="0" class="scene-wizard__preset-params">
                      <n-gi>
                        <n-form-item label="起始" :label-width="36" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.step_start_users" :min="1" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="递增" :label-width="36" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.step_increment" :min="1" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="档时长" :label-width="48" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.step_duration" :min="1" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="峰值" :label-width="36" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.step_max_users" :min="1" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                      <n-gi>
                        <n-form-item label="峰持续" :label-width="48" size="small" :show-feedback="false">
                          <n-input-number v-model:value="preset.step_sustain_duration" :min="1" size="small" style="width: 100%" />
                        </n-form-item>
                      </n-gi>
                    </n-grid>
                  </div>
                </div>
              </div>
            </n-card>
          </section>
        </div>

        <!-- ====== 底部操作栏 ====== -->
        <div class="scene-wizard__footer">
          <n-button v-if="currentStep > 1" @click="currentStep -= 1">
            ← 上一步
          </n-button>
          <span v-else />
          <n-space :size="12">
            <n-button v-if="currentStep < 4" type="primary" @click="handleNext">下一步 →</n-button>
            <n-button type="primary" :loading="saving" @click="handleSave">保 存</n-button>
          </n-space>
        </div>
      </div>
    </div>

    <PerfApiSelectPanel ref="selectPanelRef" @confirm="handleApisConfirmed" />

    <!-- 批量派生档位弹窗 -->
    <n-modal v-model:show="batchDuplicateShow" preset="dialog" title="批量派生负载档位" positive-text="派生" negative-text="取消" @positive-click="handleBatchDuplicate">
      <n-space vertical :size="12">
        <n-form-item label="基准预设" :label-width="70">
          <n-select v-model:value="batchDuplicateBase" :options="presetOptions" placeholder="选择基准预设" filterable />
        </n-form-item>
        <n-form-item label="并发列表" :label-width="70">
          <n-dynamic-tags v-model:value="batchDuplicateUsers" />
        </n-form-item>
        <n-form-item label="命名模板" :label-width="70">
          <n-input v-model:value="batchDuplicateTemplate" placeholder="{name}-{users}人" clearable />
        </n-form-item>
        <n-text depth="3" style="font-size: 12px">
          以基准预设为模板，仅覆盖并发用户数与预设名称；命名模板支持 {name}（基准名）与 {users}（并发数）占位符。
        </n-text>
      </n-space>
    </n-modal>
  </AppPage>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAlert, NButton, NCard, NDataTable, NDivider, NDynamicTags, NEmpty, NForm, NFormItem,
  NGi, NGrid, NInput, NInputGroup, NInputNumber, NModal, NPopconfirm, NRadio, NRadioButton,
  NRadioGroup, NSelect, NSpace, NSwitch, NTag, NText,
} from 'naive-ui'

import AppPage from '@/components/page/AppPage.vue'
import PerfApiSelectPanel from '../components/PerfApiSelectPanel.vue'

import {
  PERF_API_ROLE_OPTIONS, PERF_ASSERT_MODE_OPTIONS, PERF_DATASET_STRATEGY_OPTIONS,
  PERF_DELAY_MODE_OPTIONS, PERF_TARGET_METRIC_OPTIONS, PERF_TARGET_OP_OPTIONS,
  PERF_TARGET_SCOPE_OPTIONS, PERF_TARGET_SEVERITY_OPTIONS,
} from '@/constants/perfApi'
import api from '@/api'

defineOptions({ name: '场景编辑' })

const route = useRoute()
const router = useRouter()

// ---------- 步骤导航 ----------

const stepList = [
  { key: 'basic', title: '基础信息', desc: '应用归属与流量模式' },
  { key: 'items', title: '接口编排', desc: '被测接口与角色权重' },
  { key: 'targets', title: '判定口径', desc: 'SLA 目标与熔断策略' },
  { key: 'presets', title: '负载预设', desc: '并发档位与执行调度' },
]
const currentStep = ref(1)

/** 各步骤完成状态（实时追踪，驱动左侧导航勾选标记） */
const stepCompleted = computed(() => [
  !!(form.scene_project && (form.scene_name || '').trim()),
  form.scene_items.length > 0,
  true, // 判定口径为可选配置，始终视为"可跳过"
  form.presets.some((p) => !p._delete && (p.preset_name || '').trim()),
])

const completedCount = computed(() => stepCompleted.value.filter(Boolean).length)

const saving = ref(false)
const runningAll = ref(false)
const basicFormRef = ref(null)
const selectPanelRef = ref(null)

/** 编辑中的场景ID；null 表示新增 */
const editingId = computed(() => {
  const id = route.query.scene_id
  return id ? Number(id) : null
})
const isEdit = computed(() => editingId.value != null)
const pageTitle = computed(() => (isEdit.value ? `编辑压测场景 · ${form.scene_name || ''}` : '新增压测场景'))

// ---------- 表单数据 ----------

let presetKeySeq = 0
const emptyPreset = () => ({
  _key: `preset_${++presetKeySeq}`,
  _delete: false,
  preset_id: null,
  preset_code: null,
  preset_name: null,
  preset_desc: null,
  env_name: null,
  env_config_name: null,
  load_mode: 'fixed',
  concurrent_users: 1,
  spawn_rate: 1,
  run_duration: 60,
  step_start_users: null,
  step_increment: null,
  step_duration: null,
  step_max_users: null,
  step_sustain_duration: null,
  target_rps: null,
})

const emptyForm = () => ({
  scene_project: null,
  scene_name: null,
  scene_desc: null,
  run_mode: 'single',
  scene_items: [],
  perf_targets: [],
  baseline_report_code: null,
  baseline_policy: { p95_degrade_pct: null, qps_degrade_pct: null, error_rate_increase: null },
  warmup_seconds: null,
  error_rate_threshold: null,
  assert_mode: 'all',
  sample_ratio: 100,
  inject_perf_tag: true,
  presets: [],
})

const form = reactive(emptyForm())

const projectRule = computed(() =>
    isEdit.value ? undefined : { required: true, type: 'number', message: '请选择所属应用', trigger: ['change', 'blur'] },
)

const runModeHint = computed(() => (form.run_mode === 'mixed'
  ? '混合流量：多个被测接口按权重并发施压，各接口独立统计；准备/抽查项不计入业务指标。'
  : '单接口：仅一个被测接口计入业务指标，可搭配准备/抽查项构成完整业务前置换。'))

// ---------- 下拉选项 ----------

const projectOptions = ref([])
const envOptions = ref([])
const envLoading = ref(false)
const configOptionsByEnv = ref({})
const configLoading = ref(false)
const datasetOptionsByApi = ref({})

async function loadProjects() {
  try {
    const res = await api.getProjectList({ page_size: 9999 })
    projectOptions.value = (res.data || []).map((p) => ({ label: p.project_name, value: p.project_id }))
  } catch (e) {
    projectOptions.value = []
  }
}

async function loadEnvNames(projectId) {
  if (!projectId) { envOptions.value = []; return }
  envLoading.value = true
  try {
    const res = await api.queryAssignConfigEnvs({ project_id: projectId, env_type: 'app' })
    const names = Array.isArray(res?.data) ? res.data : []
    envOptions.value = names.map((name) => ({ label: name, value: name }))
  } catch (e) {
    envOptions.value = []
  } finally {
    envLoading.value = false
  }
}

async function loadConfigNames(projectId, envName) {
  if (!projectId || !envName) return
  const cacheKey = `${projectId}_${envName}`
  if (configOptionsByEnv.value[cacheKey]) return
  configLoading.value = true
  try {
    const res = await api.getEnvConfigList({ project_id: projectId, env_name: envName, env_type: 'app', page: 1, page_size: 100 })
    const rows = Array.isArray(res?.data) ? res.data : []
    configOptionsByEnv.value = { ...configOptionsByEnv.value, [cacheKey]: rows.map((r) => ({ label: r.config_name, value: r.config_name })) }
  } catch (e) {
    configOptionsByEnv.value = { ...configOptionsByEnv.value, [cacheKey]: [] }
  } finally {
    configLoading.value = false
  }
}

function getConfigOptions(envName) {
  if (!envName || !form.scene_project) return []
  return configOptionsByEnv.value[`${form.scene_project}_${envName}`] || []
}

function handlePresetEnvChange(preset, envName) {
  preset.env_config_name = null
  if (envName) loadConfigNames(form.scene_project, envName)
}

function handleProjectChange() {
  form.presets.forEach((p) => { p.env_name = null; p.env_config_name = null })
  envOptions.value = []
  configOptionsByEnv.value = {}
  loadEnvNames(form.scene_project)
}

async function loadDatasetsForApis(apiIds) {
  const pending = [...new Set(apiIds)].filter((id) => id != null && !(id in datasetOptionsByApi.value))
  if (!pending.length) return
  const results = await Promise.allSettled(pending.map((apiId) => api.listPerfDatasetsForApi({ api_id: apiId })))
  const next = { ...datasetOptionsByApi.value }
  results.forEach((result, index) => {
    const apiId = pending[index]
    const rows = result.status === 'fulfilled' ? (result.value?.data || []).filter((row) => row.bind_api_id === apiId) : []
    next[apiId] = rows.map((row) => ({ label: row.ds_name, value: row.ds_code }))
  })
  datasetOptionsByApi.value = next
}

// ---------- 接口项 ----------

const itemApiOptions = computed(() => form.scene_items.map((item) => ({ label: item.api_name, value: item.api_code })))
const transactionOptions = computed(() => [...new Set(form.scene_items.map((item) => (item.transaction || '').trim()).filter(Boolean))].map((name) => ({ label: name, value: name })))

function handleApisConfirmed(apiRows) {
  const existing = new Set(form.scene_items.map((item) => item.api_code))
  apiRows.forEach((row) => {
    if (existing.has(row.api_code)) return
    form.scene_items.push({
      seq: 0, api_code: row.api_code, api_id: row.api_id, api_name: row.api_name,
      step_type: row.step_type, request_url: row.request_url, role: 'measured', weight: 1,
      delay_mode: 'fixed', delay_ms: 0, delay_ms_min: null, delay_ms_max: null,
      transaction: null, ds_code: null, ds_name: null, dataset_strategy: 'round_robin', enabled: true,
    })
  })
  resequence()
  loadDatasetsForApis(apiRows.map((row) => row.api_id))
}

function resequence() { form.scene_items.forEach((item, index) => { item.seq = index + 1 }) }
function moveItem(index, offset) {
  const target = index + offset
  if (target < 0 || target >= form.scene_items.length) return
  const [item] = form.scene_items.splice(index, 1)
  form.scene_items.splice(target, 0, item)
  resequence()
}
function removeItem(index) { form.scene_items.splice(index, 1); resequence() }
function handleDelayModeChange(item, mode) {
  item.delay_mode = mode
  item.delay_ms = mode === 'fixed' ? (item.delay_ms || 0) : 0
  item.delay_ms_min = mode === 'uniform' ? item.delay_ms_min : null
  item.delay_ms_max = mode === 'uniform' ? item.delay_ms_max : null
}
function handleDsChange(item, dsCode) {
  item.ds_code = dsCode || null
  const matched = (datasetOptionsByApi.value[item.api_id] || []).find((opt) => opt.value === dsCode)
  item.ds_name = matched ? matched.label : null
  if (!dsCode) item.dataset_strategy = 'round_robin'
}
function openSelectPanel() { selectPanelRef.value?.open({ excludedCodes: form.scene_items.map((item) => item.api_code) }) }

const itemColumns = computed(() => [
  { title: '#', key: 'seq', width: 46, render: (row) => h('span', { class: 'scene-wizard__seq' }, row.seq) },
  { title: '接口名称', key: 'api_name', minWidth: 140, ellipsis: { tooltip: true }, render: (row) => row.api_name },
  { title: '角色', key: 'role', width: 140, render: (row) => h(NSelect, { value: row.role, options: PERF_API_ROLE_OPTIONS, size: 'small', style: { width: '100%' }, 'onUpdate:value': (v) => { row.role = v } }) },
  { title: '权重', key: 'weight', width: 90, render: (row) => h(NInputNumber, { value: row.weight, size: 'small', min: 1, max: 100, style: { width: '100%' }, showButton: false, 'onUpdate:value': (v) => { row.weight = v } }) },
  { title: '启用', key: 'enabled', width: 60, render: (row) => h(NSwitch, { value: row.enabled, size: 'small', 'onUpdate:value': (v) => { row.enabled = v } }) },
  { title: '思考时间', key: 'delay', width: 210, render: (row) => h(NSpace, { size: 4, wrap: false, align: 'center' }, { default: () => [h(NSelect, { value: row.delay_mode, options: PERF_DELAY_MODE_OPTIONS, size: 'small', style: { width: 86 }, 'onUpdate:value': (v) => handleDelayModeChange(row, v) }), row.delay_mode === 'fixed' ? h(NInputNumber, { value: row.delay_ms, size: 'small', min: 0, style: { width: 76 }, showButton: false, placeholder: 'ms', 'onUpdate:value': (v) => { row.delay_ms = v } }) : h(NInputGroup, null, { default: () => [h(NInputNumber, { value: row.delay_ms_min, size: 'small', min: 0, style: { width: 56 }, showButton: false, placeholder: 'min', 'onUpdate:value': (v) => { row.delay_ms_min = v } }), h(NInputNumber, { value: row.delay_ms_max, size: 'small', min: 0, style: { width: 56 }, showButton: false, placeholder: 'max', 'onUpdate:value': (v) => { row.delay_ms_max = v } })] })] }) },
  { title: '事务', key: 'transaction', width: 120, render: (row) => h(NInput, { value: row.transaction, size: 'small', placeholder: '选填', clearable: true, 'onUpdate:value': (v) => { row.transaction = v } }) },
  { title: '数据集', key: 'ds', width: 190, render: (row) => h(NSpace, { size: 4, wrap: false, align: 'center' }, { default: () => [h(NSelect, { value: row.ds_code, options: datasetOptionsByApi.value[row.api_id] || [], size: 'small', style: { width: 104 }, clearable: true, filterable: true, placeholder: '数据集', 'onUpdate:value': (v) => handleDsChange(row, v) }), row.ds_code ? h(NSelect, { value: row.dataset_strategy, options: PERF_DATASET_STRATEGY_OPTIONS, size: 'small', style: { width: 76 }, 'onUpdate:value': (v) => { row.dataset_strategy = v } }) : null] }) },
  { title: '', key: 'actions', width: 80, fixed: 'right', render: (_row, index) => h(NSpace, { size: 2, wrap: false }, { default: () => [h(NButton, { size: 'tiny', quaternary: true, disabled: index === 0, onClick: () => moveItem(index, -1) }, { default: () => '↑' }), h(NButton, { size: 'tiny', quaternary: true, disabled: index === form.scene_items.length - 1, onClick: () => moveItem(index, 1) }, { default: () => '↓' }), h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => removeItem(index) }, { default: () => '✕' })] }) },
])

// ---------- SLA 目标 ----------

function addTarget() {
  form.perf_targets.push({ scope: 'global', target: 'rps', api_code: null, transaction: null, op: 'ge', expect: null, severity: 'warn', min_total_requests: null, min_duration_seconds: null })
}
function removeTarget(index) { form.perf_targets.splice(index, 1) }
function handleTargetScopeChange(target) { target.api_code = null; target.transaction = null }

// ---------- 负载预设 ----------

const activePresetCount = computed(() => form.presets.filter((p) => !p._delete).length)
const presetOptions = computed(() => form.presets.filter((p) => !p._delete && p.preset_id).map((p) => ({ label: p.preset_name || `预设${p.preset_id}`, value: p.preset_id })))

function addPreset() {
  const preset = emptyPreset()
  preset.preset_name = `${form.scene_name || '场景'}-预设${activePresetCount.value + 1}`
  form.presets.push(preset)
}

function markDeletePreset(index) {
  const preset = form.presets[index]
  if (preset.preset_id) { preset._delete = true } else { form.presets.splice(index, 1) }
}

function restorePreset(index) { form.presets[index]._delete = false }

// ---------- 批量派生 ----------

const batchDuplicateShow = ref(false)
const batchDuplicateBase = ref(null)
const batchDuplicateUsers = ref([])
const batchDuplicateTemplate = ref('{name}-{users}人')

function openBatchDuplicate() {
  batchDuplicateBase.value = null
  batchDuplicateUsers.value = []
  batchDuplicateTemplate.value = '{name}-{users}人'
  batchDuplicateShow.value = true
}

async function handleBatchDuplicate() {
  if (!batchDuplicateBase.value || !batchDuplicateUsers.value.length) {
    window.$message?.warning('请选择基准预设并输入并发列表')
    return false
  }
  const usersList = batchDuplicateUsers.value.map((v) => Number(v)).filter((n) => n > 0)
  if (!usersList.length) { window.$message?.warning('并发列表需为正整数'); return false }
  try {
    const res = await api.batchDuplicatePerfPreset({
      base_preset_id: batchDuplicateBase.value,
      concurrent_users_list: usersList,
      name_template: batchDuplicateTemplate.value || null,
    })
    const created = res.data || []
    created.forEach((p) => {
      form.presets.push({ ...emptyPreset(), ...p, _key: `preset_${++presetKeySeq}`, _delete: false })
    })
    window.$message?.success(`已派生 ${created.length} 份负载预设`)
    batchDuplicateShow.value = false
  } catch (e) { /* 拦截器已提示 */ }
  return false
}

// ---------- 一键跑全部 ----------

async function handleRunAll() {
  if (!isEdit.value) return
  runningAll.value = true
  try {
    const res = await api.runAllPerfScenePresets({ scene_id: editingId.value })
    const data = res.data || {}
    window.$message?.success(res.message || `已下发 ${data.dispatched || 0}/${data.total || 0} 份负载预设`)
  } catch (e) { /* 拦截器已提示 */ } finally {
    runningAll.value = false
  }
}

// ---------- 步骤导航 ----------

function handleNext() {
  const error = validateStep(currentStep.value)
  if (error) { window.$message?.error(error.message); return }
  if (currentStep.value === 1) loadDatasetsForApis(form.scene_items.map((item) => item.api_id))
  currentStep.value += 1
}

function validateStep(step) {
  if (step === 1) {
    if (!form.scene_project) return { message: '请选择所属应用' }
    if (!(form.scene_name || '').trim()) return { message: '请输入场景名称' }
  }
  if (step === 2 && !form.scene_items.length) return { message: '请至少选择一个接口' }
  return null
}

// ---------- 打开与保存 ----------

function applyDetail(detail) {
  if (detail.run_mode === 'journey') {
    window.$message?.warning('业务链路(journey)模式编辑器将在后续版本提供，暂不支持在该页面编辑')
    return false
  }
  Object.assign(form, emptyForm(), {
    ...detail,
    scene_items: (detail.scene_items || []).map((item) => ({ ...item, enabled: item.enabled !== false })),
    perf_targets: (detail.perf_targets || []).map((target) => ({ ...target })),
    baseline_policy: { ...emptyForm().baseline_policy, ...(detail.baseline_policy || {}) },
    presets: [],
  })
  resequence()
  return true
}

async function loadPresets(sceneId) {
  try {
    const res = await api.getPerfLoadPresetList({ scene_id: sceneId, page_size: 200, state: 0 })
    const rows = res.data || []
    form.presets = rows.map((row) => ({ ...emptyPreset(), ...row, _key: `preset_${++presetKeySeq}`, _delete: false }))
  } catch (e) {
    form.presets = []
  }
}

async function initPage() {
  await loadProjects()
  if (!isEdit.value) return
  try {
    const res = await api.getPerfScene({ scene_id: editingId.value })
    if (!applyDetail(res.data || {})) { router.back(); return }
    await loadEnvNames(form.scene_project)
    await loadPresets(editingId.value)
    loadDatasetsForApis(form.scene_items.map((item) => item.api_id))
    form.presets.forEach((p) => { if (p.env_name) loadConfigNames(form.scene_project, p.env_name) })
  } catch (e) {
    router.back()
  }
}

function buildScenePayload() {
  const payload = {
    scene_project: form.scene_project,
    scene_name: (form.scene_name || '').trim(),
    scene_desc: (form.scene_desc || '').trim() || null,
    run_mode: form.run_mode,
    scene_items: form.scene_items.map((item) => ({
      seq: item.seq, api_code: item.api_code, api_id: item.api_id, api_name: item.api_name,
      role: item.role, weight: item.weight || 1, delay_mode: item.delay_mode,
      delay_ms: item.delay_mode === 'fixed' ? (item.delay_ms || 0) : 0,
      delay_ms_min: item.delay_mode === 'uniform' ? item.delay_ms_min : null,
      delay_ms_max: item.delay_mode === 'uniform' ? item.delay_ms_max : null,
      transaction: (item.transaction || '').trim() || null,
      ds_code: item.ds_code || null, ds_name: item.ds_name, dataset_strategy: item.dataset_strategy,
      override: null, enabled: item.enabled,
    })),
    perf_targets: form.perf_targets.length ? form.perf_targets.map((t) => ({
      scope: t.scope, target: t.target, api_code: t.scope === 'api' ? t.api_code : null,
      transaction: t.scope === 'transaction' ? t.transaction : null, op: t.op, expect: t.expect,
      severity: t.severity, min_total_requests: t.min_total_requests || null, min_duration_seconds: t.min_duration_seconds || null,
    })) : null,
    baseline_report_code: (form.baseline_report_code || '').trim() || null,
    baseline_policy: [form.baseline_policy.p95_degrade_pct, form.baseline_policy.qps_degrade_pct, form.baseline_policy.error_rate_increase].some((v) => v !== null && v !== undefined) ? { ...form.baseline_policy } : null,
    warmup_seconds: form.warmup_seconds ?? null,
    error_rate_threshold: form.error_rate_threshold ?? null,
    assert_mode: form.assert_mode,
    sample_ratio: form.sample_ratio,
    inject_perf_tag: form.inject_perf_tag,
  }
  if (isEdit.value) payload.scene_id = editingId.value
  return payload
}

function buildPresetsPayload() {
  return form.presets.map((p) => {
    if (p._delete) return { preset_id: p.preset_id, preset_code: p.preset_code, _delete: true }
    const stepped = p.load_mode === 'stepped'
    const rps = p.load_mode === 'rps'
    const item = {
      preset_project: form.scene_project,
      preset_name: (p.preset_name || '').trim(),
      preset_desc: (p.preset_desc || '').trim() || null,
      env_name: p.env_name || null,
      env_config_name: p.env_config_name || null,
      load_mode: p.load_mode,
      concurrent_users: p.concurrent_users || 1,
      spawn_rate: p.spawn_rate || 1,
      run_duration: p.run_duration || 60,
      step_start_users: stepped ? p.step_start_users : null,
      step_increment: stepped ? p.step_increment : null,
      step_duration: stepped ? p.step_duration : null,
      step_max_users: stepped ? p.step_max_users : null,
      step_sustain_duration: stepped ? p.step_sustain_duration : null,
      target_rps: rps ? p.target_rps : null,
    }
    if (p.preset_id) { item.preset_id = p.preset_id; item.preset_code = p.preset_code }
    return item
  })
}

function validateForm() {
  if (!form.scene_project) return { step: 1, message: '请选择所属应用' }
  if (!(form.scene_name || '').trim()) return { step: 1, message: '请输入场景名称' }
  if (!form.scene_items.length) return { step: 2, message: '请至少选择一个接口' }
  for (let i = 0; i < form.scene_items.length; i++) {
    const item = form.scene_items[i]
    if (item.delay_mode === 'uniform' && (item.delay_ms_min == null || item.delay_ms_max == null)) {
      return { step: 2, message: `第 ${i + 1} 项接口思考时间区间未填完整` }
    }
  }
  for (let i = 0; i < form.perf_targets.length; i++) {
    const t = form.perf_targets[i]
    if (t.expect == null) return { step: 3, message: `第 ${i + 1} 条 SLA 目标需填写期望值` }
    if (t.scope === 'api' && !t.api_code) return { step: 3, message: `第 ${i + 1} 条 SLA 目标需选择接口` }
    if (t.scope === 'transaction' && !t.transaction) return { step: 3, message: `第 ${i + 1} 条 SLA 目标需填写事务` }
  }
  if (form.assert_mode === 'sample_ratio' && (!form.sample_ratio || form.sample_ratio <= 0)) {
    return { step: 3, message: '抽样断言必须设置采样比例' }
  }
  const activePresets = form.presets.filter((p) => !p._delete)
  for (let i = 0; i < activePresets.length; i++) {
    const p = activePresets[i]
    if (!(p.preset_name || '').trim()) return { step: 4, message: `第 ${i + 1} 份负载预设需填写名称` }
  }
  return null
}

async function handleSave() {
  const error = validateForm()
  if (error) { currentStep.value = error.step; window.$message?.error(error.message); return }
  try {
    saving.value = true
    const payload = { scene: buildScenePayload(), presets: buildPresetsPayload() }
    const res = await api.savePerfSceneWizard(payload)
    window.$message?.success('保存成功')
    const sceneId = res.data?.scene?.scene_id
    if (sceneId && !isEdit.value) {
      router.replace({ path: '/performance/scene/edit', query: { scene_id: sceneId } })
    }
    if (sceneId) await loadPresets(sceneId)
  } catch (e) { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

function handleBack() { router.push('/performance/scene') }

onMounted(() => { initPage() })
</script>

<style scoped>
/* ===== 整体布局 ===== */
.scene-wizard {
  display: flex;
  gap: 0;
  width: 100%;
  min-height: calc(100vh - 120px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.03);
  overflow: hidden;
}

/* ===== 左侧导航面板 ===== */
.scene-wizard__nav {
  flex: 0 0 232px;
  display: flex;
  flex-direction: column;
  background: #fafbfd;
  border-right: 1px solid #f0f1f5;
}

.scene-wizard__nav-header {
  padding: 24px 20px 16px;
  border-bottom: 1px solid #f0f1f5;
}

.scene-wizard__nav-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 4px;
}

.scene-wizard__nav-progress {
  font-size: 12px;
  color: #86909c;
}

.scene-wizard__nav-list {
  flex: 1;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.scene-wizard__nav-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.scene-wizard__nav-item:hover {
  background: #f2f3f5;
}

.scene-wizard__nav-item.is-active {
  background: #e8f3ff;
  border-color: #bedaff;
}

.scene-wizard__nav-item.is-completed .scene-wizard__nav-indicator {
  background: #00b42a;
  border-color: #00b42a;
  color: #fff;
}

.scene-wizard__nav-item.is-active .scene-wizard__nav-indicator {
  background: #165dff;
  border-color: #165dff;
  color: #fff;
}

.scene-wizard__nav-indicator {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  border: 2px solid #e5e6eb;
  color: #86909c;
  background: #fff;
  transition: all 0.2s ease;
  margin-top: 1px;
}

.scene-wizard__nav-check {
  font-size: 11px;
  font-weight: 700;
}

.scene-wizard__nav-num {
  font-size: 11px;
}

.scene-wizard__nav-content {
  flex: 1;
  min-width: 0;
}

.scene-wizard__nav-label {
  font-size: 13px;
  font-weight: 500;
  color: #1d2129;
  line-height: 1.4;
  transition: color 0.2s;
}

.scene-wizard__nav-item.is-active .scene-wizard__nav-label {
  color: #165dff;
  font-weight: 600;
}

.scene-wizard__nav-desc {
  font-size: 11px;
  color: #86909c;
  line-height: 1.4;
  margin-top: 2px;
}

.scene-wizard__nav-footer {
  padding: 12px 16px;
  border-top: 1px solid #f0f1f5;
}

/* ===== 右侧主内容区 ===== */
.scene-wizard__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.scene-wizard__content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px 20px;
}

/* ===== 步骤区块 ===== */
.scene-wizard__section {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.scene-wizard__section-header {
  margin-bottom: 20px;
}

.scene-wizard__section-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 600;
  color: #1d2129;
  line-height: 1.4;
}

.scene-wizard__section-desc {
  margin: 0;
  font-size: 13px;
  color: #86909c;
  line-height: 1.6;
}

/* ===== 内容卡片 ===== */
.scene-wizard__card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  margin-bottom: 16px;
}

.scene-wizard__card :deep(.n-card-header) {
  padding: 14px 20px 10px;
}

.scene-wizard__card :deep(.n-card__content) {
  padding: 12px 20px 20px;
}

.scene-wizard__card-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.scene-wizard__alert {
  border-radius: 8px;
  margin-top: 4px;
}

/* ===== 底部操作栏 ===== */
.scene-wizard__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 32px;
  border-top: 1px solid #f0f1f5;
  background: #fafbfd;
  flex-shrink: 0;
}

/* ===== SLA 目标列表 ===== */
.scene-wizard__target-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-wizard__target-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 6px;
  border: 1px solid #f2f3f5;
  transition: border-color 0.2s;
}

.scene-wizard__target-row:hover {
  border-color: #e5e6eb;
}

.scene-wizard__target-idx {
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e8f3ff;
  color: #165dff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scene-wizard__target-fields {
  flex: 1;
}

/* ===== 负载预设列表 ===== */
.scene-wizard__preset-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scene-wizard__preset-item {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s ease;
}

.scene-wizard__preset-item:hover {
  border-color: #bedaff;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.06);
}

.scene-wizard__preset-item.is-deleted {
  opacity: 0.45;
  border-style: dashed;
  border-color: #e5e6eb;
}

.scene-wizard__preset-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f7f8fa;
  border-bottom: 1px solid #f2f3f5;
}

.scene-wizard__preset-id {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scene-wizard__preset-num {
  flex: 0 0 22px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #165dff;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scene-wizard__preset-name :deep(.n-input__input-el) {
  font-weight: 500;
  font-size: 13px;
}

.scene-wizard__preset-name-text {
  font-weight: 500;
  font-size: 13px;
  color: #86909c;
}

.scene-wizard__preset-body {
  padding: 14px 16px;
}

.scene-wizard__preset-params {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #f2f3f5;
}

/* ===== 表格序号 ===== */
.scene-wizard__seq {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: #f2f3f5;
  font-size: 11px;
  font-weight: 500;
  color: #4e5969;
}
</style>
