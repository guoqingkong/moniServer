<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { fetchCosDashboard, fetchDashboard, fetchMonitorConfig, fetchRecentAlerts } from '../api/monitor'
import MetricCard from '../components/MetricCard.vue'
import MetricChart from '../components/MetricChart.vue'

const instanceOptions = ref([])
const cosBuckets = ref([])
const rangeHours = ref(6)
const loading = ref(false)
const errorMessage = ref('')
const dashboards = ref([])
const cosDashboards = ref([])
const recentAlerts = ref([])
const autoRefreshEnabled = ref(true)
const activeTab = ref('cvm')
const autoRefreshSeconds = 60
let refreshTimer = null

const quickRanges = [
  { label: '1 小时', value: 1 },
  { label: '6 小时', value: 6 },
  { label: '24 小时', value: 24 },
]

const lastUpdated = computed(() => {
  const timestamps = dashboards.value
    .map((item) => item.dashboard?.endTime)
    .concat(cosDashboards.value.map((item) => item.dashboard?.endTime))
    .filter(Boolean)

  if (!timestamps.length) {
    return '--'
  }

  const latestTime = timestamps.sort().at(-1)
  return new Date(latestTime).toLocaleString('zh-CN')
})

const comparisonRows = computed(() => {
  if (dashboards.value.length < 2) {
    return []
  }

  const [left, right] = dashboards.value
  const leftCards = Object.fromEntries((left.dashboard?.cards || []).map((card) => [card.key, card]))
  const rightCards = Object.fromEntries((right.dashboard?.cards || []).map((card) => [card.key, card]))

  return ['cpu', 'memory', 'network_in', 'network_out', 'disk_usage']
    .map((key) => {
      const leftCard = leftCards[key]
      const rightCard = rightCards[key]
      if (!leftCard || !rightCard) {
        return null
      }

      const leftValue = leftCard.latest ?? null
      const rightValue = rightCard.latest ?? null
      const delta =
        leftValue === null || rightValue === null
          ? null
          : Number((leftValue - rightValue).toFixed(2))

      return {
        key,
        label: leftCard.label,
        unit: leftCard.unit,
        leftName: left.instance.name,
        rightName: right.instance.name,
        leftValue,
        rightValue,
        delta,
        leader:
          delta === null || delta === 0 ? '持平' : delta > 0 ? left.instance.name : right.instance.name,
      }
    })
    .filter(Boolean)
})

function formatValue(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return Number(value).toFixed(2)
}

function startAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }

  refreshTimer = setInterval(() => {
    if (autoRefreshEnabled.value && !loading.value) {
      loadDashboard()
    }
  }, autoRefreshSeconds * 1000)
}

async function loadConfig() {
  const config = await fetchMonitorConfig()
  instanceOptions.value = config.instances || []
  cosBuckets.value = config.cosBuckets || []
  rangeHours.value = config.defaultRangeHours || rangeHours.value
}

async function loadDashboard() {
  if (!instanceOptions.value.length) {
    errorMessage.value = '当前没有可展示的实例，请先在后端配置实例列表。'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const [results, alerts, cosResults] = await Promise.all([
      Promise.all(
        instanceOptions.value.map(async (instance) => {
          const dashboard = await fetchDashboard({
            instanceId: instance.id,
            rangeHours: rangeHours.value,
          })

          return {
            instance,
            dashboard,
          }
        }),
      ),
      fetchRecentAlerts({ limit: 20 }),
      Promise.all(
        cosBuckets.value.map(async (bucket) => {
          const dashboard = await fetchCosDashboard({
            bucketName: bucket.name,
            rangeHours: Math.max(rangeHours.value, 24),
          })

          return {
            bucket,
            dashboard,
          }
        }),
      ),
    ])

    dashboards.value = results
    recentAlerts.value = alerts
    cosDashboards.value = cosResults
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
  startAutoRefresh()
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<template>
  <main class="dashboard-shell">
    <section class="hero-panel">
      <div class="hero-copy">
        <p class="eyebrow">Tencent Cloud CVM</p>
        <h1>实例运行监控面板</h1>
        <p class="hero-text">
          主机监控与对象存储监控共用一页，通过标签切换查看，既保留统一入口，也避免页面过长影响浏览效率。
        </p>
      </div>
      <form class="control-panel" @submit.prevent="loadDashboard">
        <label>
          <span>展示实例</span>
          <div class="instance-pill-list">
            <span v-for="item in instanceOptions" :key="item.id" class="instance-pill">
              {{ item.name }} · {{ item.id }}
            </span>
          </div>
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
        <label>
          <span>自动刷新</span>
          <button type="button" class="ghost-button auto-refresh-button" :class="{ active: autoRefreshEnabled }" @click="autoRefreshEnabled = !autoRefreshEnabled">
            {{ autoRefreshEnabled ? `已开启 · ${autoRefreshSeconds}s` : '已关闭' }}
          </button>
        </label>
        <button class="primary-button" type="submit" :disabled="loading">
          {{ loading ? '加载中...' : '刷新数据' }}
        </button>
      </form>
    </section>

    <section class="status-bar">
      <span>最近刷新：{{ lastUpdated }}</span>
      <span>范围：最近 {{ rangeHours }} 小时</span>
      <span>实例数：{{ dashboards.length }}</span>
      <span>COS 桶数：{{ cosDashboards.length }}</span>
    </section>

    <p v-if="errorMessage" class="error-banner">{{ errorMessage }}</p>

    <section class="view-tabs">
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cvm' }" @click="activeTab = 'cvm'">
        CVM 主机
      </button>
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cos' }" @click="activeTab = 'cos'">
        COS 存储
      </button>
    </section>

    <template v-if="activeTab === 'cvm'">
    <section v-if="comparisonRows.length" class="comparison-panel">
      <div class="comparison-title-row">
        <div>
          <p class="comparison-eyebrow">Dual Server Comparison</p>
          <h2>双机实时对比</h2>
        </div>
        <p class="comparison-note">按最新值对照入口层与数据层，快速发现负载偏移与瓶颈热点。</p>
      </div>

      <div class="comparison-grid">
        <article v-for="row in comparisonRows" :key="row.key" class="comparison-card">
          <div class="comparison-card-header">
            <h3>{{ row.label }}</h3>
            <span>{{ row.unit }}</span>
          </div>
          <div class="comparison-values">
            <div>
              <p>{{ row.leftName }}</p>
              <strong>{{ formatValue(row.leftValue) }}</strong>
            </div>
            <div>
              <p>{{ row.rightName }}</p>
              <strong>{{ formatValue(row.rightValue) }}</strong>
            </div>
          </div>
          <div class="comparison-footer">
            <span>领先：{{ row.leader }}</span>
            <span>差值：{{ row.delta === null ? '--' : formatValue(Math.abs(row.delta)) }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="instance-board">
      <article v-for="item in dashboards" :key="item.instance.id" class="instance-panel">
        <header class="instance-header">
          <div>
            <p class="instance-tag">{{ item.instance.region }}</p>
            <h2>{{ item.instance.name }}</h2>
            <p class="instance-meta">{{ item.instance.id }}</p>
          </div>
          <div class="instance-summary">
            <span>更新时间 {{ new Date(item.dashboard.endTime).toLocaleString('zh-CN') }}</span>
            <span class="status-chip">运行中</span>
            <strong>{{ item.dashboard.series?.length || 0 }} 个指标</strong>
          </div>
        </header>

        <section v-if="item.dashboard?.cards?.length" class="metric-grid">
          <MetricCard v-for="card in item.dashboard.cards" :key="`${item.instance.id}-${card.key}`" :card="card" />
        </section>

        <section v-if="item.dashboard?.series?.length" class="chart-grid">
          <MetricChart
            v-for="seriesItem in item.dashboard.series"
            :key="`${item.instance.id}-${seriesItem.key}`"
            :series="seriesItem"
          />
        </section>
      </article>
    </section>

    <section class="alerts-panel">
      <div class="alerts-header">
        <div>
          <p class="comparison-eyebrow">Recent Alerts</p>
          <h2>最近告警</h2>
        </div>
        <p class="comparison-note">只展示最近触发过的公网带宽阈值事件，便于快速回看异常时间点。</p>
      </div>

      <div v-if="recentAlerts.length" class="alerts-list">
        <article v-for="alert in recentAlerts" :key="`${alert.instanceId}-${alert.metricKey}-${alert.timestamp}`" class="alert-item">
          <div>
            <p class="alert-title">{{ alert.metricLabel }} 超阈值</p>
            <p class="alert-meta">{{ alert.instanceId }}</p>
          </div>
          <div class="alert-values">
            <strong>{{ formatValue(alert.currentValue) }} Mbps</strong>
            <span>阈值 {{ formatValue(alert.thresholdMbps) }} Mbps</span>
          </div>
          <time class="alert-time">{{ new Date(alert.timestamp).toLocaleString('zh-CN') }}</time>
        </article>
      </div>
      <p v-else class="alerts-empty">最近还没有超过 50 Mbps 的公网带宽告警。</p>
    </section>
    </template>

    <template v-else>
      <section class="alerts-panel cos-panel">
        <div class="alerts-header">
          <div>
            <p class="comparison-eyebrow">COS Storage Monitor</p>
            <h2>COS 存储监控</h2>
          </div>
          <p class="comparison-note">展示两个 COS bucket 的存储量、对象数、请求数和外网上下行带宽。</p>
        </div>

        <section class="instance-board">
          <article v-for="item in cosDashboards" :key="item.bucket.name" class="instance-panel">
            <header class="instance-header">
              <div>
                <p class="instance-tag">{{ item.bucket.region }}</p>
                <h2>{{ item.bucket.label }}</h2>
                <p class="instance-meta">{{ item.bucket.name }}</p>
              </div>
              <div class="instance-summary">
                <span>更新时间 {{ new Date(item.dashboard.endTime).toLocaleString('zh-CN') }}</span>
                <span class="status-chip">COS</span>
                <strong>{{ item.dashboard.series?.length || 0 }} 个指标</strong>
              </div>
            </header>

            <section v-if="item.dashboard?.cards?.length" class="metric-grid metric-grid-cos">
              <MetricCard v-for="card in item.dashboard.cards" :key="`${item.bucket.name}-${card.key}`" :card="card" />
            </section>

            <section v-if="item.dashboard?.series?.length" class="chart-grid">
              <MetricChart
                v-for="seriesItem in item.dashboard.series"
                :key="`${item.bucket.name}-${seriesItem.key}`"
                :series="seriesItem"
              />
            </section>
          </article>
        </section>
      </section>
    </template>
  </main>
</template>
