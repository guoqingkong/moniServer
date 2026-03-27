<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchDashboard, fetchMonitorConfig } from '../api/monitor'
import MetricCard from '../components/MetricCard.vue'
import MetricChart from '../components/MetricChart.vue'

const instanceId = ref('')
const instanceOptions = ref([])
const rangeHours = ref(6)
const loading = ref(false)
const errorMessage = ref('')
const dashboard = ref(null)

const quickRanges = [
  { label: '1 小时', value: 1 },
  { label: '6 小时', value: 6 },
  { label: '24 小时', value: 24 },
]

const lastUpdated = computed(() => {
  if (!dashboard.value?.endTime) {
    return '--'
  }
  return new Date(dashboard.value.endTime).toLocaleString('zh-CN')
})

async function loadConfig() {
  const config = await fetchMonitorConfig()
  instanceOptions.value = config.instances || []
  instanceId.value = config.defaultInstanceId || instanceId.value
  if (!instanceId.value && instanceOptions.value.length) {
    instanceId.value = instanceOptions.value[0].id
  }
  rangeHours.value = config.defaultRangeHours || rangeHours.value
}

async function loadDashboard() {
  if (!instanceId.value) {
    errorMessage.value = '请先在后端 .env 中配置 DEFAULT_INSTANCE_ID，或在页面输入实例 ID。'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    dashboard.value = await fetchDashboard({
      instanceId: instanceId.value,
      rangeHours: rangeHours.value,
    })
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || '监控数据加载失败，请检查后端配置或腾讯云接口返回。'
  } finally {
    loading.value = false
  }
}

async function initialize() {
  try {
    await loadConfig()
  } catch (error) {
    errorMessage.value = '初始化配置失败，请确认后端是否已启动。'
  }
  await loadDashboard()
}

onMounted(() => {
  initialize()
})
</script>

<template>
  <main class="dashboard-shell">
    <section class="hero-panel">
      <div class="hero-copy">
        <p class="eyebrow">Tencent Cloud CVM</p>
        <h1>实例运行监控面板</h1>
        <p class="hero-text">
          聚焦 CPU、内存、网络与存储四类指标，前端统一消费后端聚合接口，便于继续接告警、租户权限和大屏展示。
        </p>
      </div>
      <form class="control-panel" @submit.prevent="loadDashboard">
        <label>
          <span>实例 ID</span>
          <select v-if="instanceOptions.length" v-model="instanceId">
            <option v-for="item in instanceOptions" :key="item.id" :value="item.id">
              {{ item.name }} · {{ item.id }}
            </option>
          </select>
          <input v-else v-model.trim="instanceId" type="text" placeholder="ins-xxxxxxxx" />
        </label>
        <label>
          <span>时间范围</span>
          <div class="quick-range-list">
            <button
              v-for="item in quickRanges"
              :key="item.value"
              type="button"
              class="ghost-button"
              :class="{ active: rangeHours === item.value }"
              @click="rangeHours = item.value"
            >
              {{ item.label }}
            </button>
          </div>
        </label>
        <button class="primary-button" type="submit" :disabled="loading">
          {{ loading ? '加载中...' : '刷新数据' }}
        </button>
      </form>
    </section>

    <section class="status-bar">
      <span>最近刷新：{{ lastUpdated }}</span>
      <span>范围：最近 {{ rangeHours }} 小时</span>
    </section>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

    <section v-if="dashboard?.cards?.length" class="metric-grid">
      <MetricCard v-for="card in dashboard.cards" :key="card.key" :card="card" />
    </section>

    <section v-if="dashboard?.series?.length" class="chart-grid">
      <MetricChart v-for="item in dashboard.series" :key="item.key" :series="item" />
    </section>
  </main>
</template>
