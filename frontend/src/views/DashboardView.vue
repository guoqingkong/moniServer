<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  fetchCosDashboard,
  fetchCollectorStatus,
  fetchDashboard,
  fetchMetricComparison,
  fetchMetricHistory,
  fetchMonitorConfig,
  fetchRecentAlerts,
} from '../api/monitor'
import ComparisonTrendChart from '../components/ComparisonTrendChart.vue'
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
const metricComparisons = ref([])
const cosMetricComparisons = ref([])
const autoRefreshEnabled = ref(true)
const activeTab = ref('cvm-monitor')
const cvmAnalysisPreset = ref('30m')
const cosAnalysisPreset = ref('30m')
const analysisLoading = ref(false)
const cosAnalysisLoading = ref(false)
const collectorStatus = ref(null)
const collectorCountdown = ref('--')
const autoRefreshSeconds = 60
let refreshTimer = null
let countdownTimer = null

const quickRanges = [
  { label: '1 小时', value: 1 },
  { label: '6 小时', value: 6 },
  { label: '24 小时', value: 24 },
]

const analysisPresets = [
  {
    key: '30m',
    label: '30 分钟趋势',
    durationMs: 30 * 60 * 1000,
    description: '看短时波动和突发流量，适合排查刚发生的抖动。',
  },
  {
    key: '6h',
    label: '6 小时趋势',
    durationMs: 6 * 60 * 60 * 1000,
    description: '看半天内的负载起伏，适合观察班次或业务波峰。',
  },
  {
    key: 'day',
    label: '日对比',
    durationMs: 24 * 60 * 60 * 1000,
    description: '把最近 24 小时和前 24 小时对照，更容易看出全天形态变化。',
  },
  {
    key: 'week',
    label: '周对比',
    durationMs: 7 * 24 * 60 * 60 * 1000,
    description: '看近 7 天和前 7 天的容量与请求变化，适合做趋势判断。',
  },
]

const metricMeta = {
  cvm: {
    cpu: { label: 'CPU 使用率', unit: '%' },
    memory: { label: '内存使用率', unit: '%' },
    network_in: { label: '公网入带宽', unit: 'Mbps' },
    network_out: { label: '公网出带宽', unit: 'Mbps' },
    disk_usage: { label: '磁盘使用率', unit: '%' },
  },
  cos: {
    storage_size: { label: '标准存储容量', unit: 'MB' },
    object_count: { label: '标准对象数量', unit: '个' },
    network_in: { label: '外网上行带宽', unit: 'Mbps' },
    network_out: { label: '外网下行带宽', unit: 'Mbps' },
    request_get: { label: 'GET 请求数', unit: '次' },
    request_put: { label: 'PUT 请求数', unit: '次' },
  },
}

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

function formatValue(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return Number(value).toFixed(2)
}

function toIsoString(date) {
  return new Date(date.getTime() - date.getMilliseconds()).toISOString().replace('Z', '+00:00')
}

function formatDelta(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${value > 0 ? '+' : ''}${Number(value).toFixed(2)}`
}

function formatDateTime(value) {
  if (!value) {
    return '--'
  }
  return new Date(value).toLocaleString('zh-CN')
}

function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return '--'
  }

  if (seconds <= 0) {
    return '即将执行'
  }

  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(remainSeconds).padStart(2, '0')}`
}

function updateCollectorCountdown() {
  if (!collectorStatus.value?.nextRunAt) {
    collectorCountdown.value = '--'
    return
  }

  const diffSeconds = Math.max(0, Math.floor((new Date(collectorStatus.value.nextRunAt).getTime() - Date.now()) / 1000))
  collectorCountdown.value = formatSeconds(diffSeconds)
}

function getPresetConfig(key) {
  return analysisPresets.find((item) => item.key === key) || analysisPresets[0]
}

function buildAnalysisWindows(presetKey) {
  const preset = getPresetConfig(presetKey)
  const end = new Date()
  const currentStart = new Date(end.getTime() - preset.durationMs)
  const previousStart = new Date(currentStart.getTime() - preset.durationMs)

  return {
    preset,
    end,
    currentStart,
    previousStart,
  }
}

function buildAnalysisChart(resourceLabel, comparison, currentSeries, previousSeries, preset) {
  return {
    resourceLabel,
    metricKey: comparison.metricKey,
    metricLabel: comparison.metricLabel,
    unit: comparison.unit,
    currentWindow: comparison.currentWindow,
    previousWindow: comparison.previousWindow,
    averageDelta: comparison.averageDelta,
    peakDelta: comparison.peakDelta,
    currentSeries,
    previousSeries,
    durationMs: preset.durationMs,
    presetDescription: preset.description,
  }
}

function buildEmptySeries(resourceType, resourceId, metricKey, startTime, endTime) {
  const meta = metricMeta[resourceType]?.[metricKey] || { label: metricKey, unit: '' }
  return {
    resourceType,
    resourceId,
    metricKey,
    metricLabel: meta.label,
    unit: meta.unit,
    startTime: toIsoString(startTime),
    endTime: toIsoString(endTime),
    points: [],
    latest: null,
    average: null,
    peak: null,
  }
}

function buildEmptyComparison(resourceType, resourceId, metricKey, presetWindow) {
  const meta = metricMeta[resourceType]?.[metricKey] || { label: metricKey, unit: '' }
  return {
    resourceType,
    resourceId,
    metricKey,
    metricLabel: meta.label,
    unit: meta.unit,
    currentWindow: {
      startTime: toIsoString(presetWindow.currentStart),
      endTime: toIsoString(presetWindow.end),
      latest: null,
      average: null,
      peak: null,
      pointCount: 0,
    },
    previousWindow: {
      startTime: toIsoString(presetWindow.previousStart),
      endTime: toIsoString(presetWindow.currentStart),
      latest: null,
      average: null,
      peak: null,
      pointCount: 0,
    },
    averageDelta: null,
    peakDelta: null,
  }
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

function startCollectorCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }

  updateCollectorCountdown()
  countdownTimer = setInterval(updateCollectorCountdown, 1000)
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
    collectorStatus.value = await fetchCollectorStatus().catch(() => null)
    updateCollectorCountdown()
    await refreshVisibleAnalysis()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || '监控数据加载失败，请检查后端配置或腾讯云接口返回。'
  } finally {
    loading.value = false
  }
}

async function loadMetricComparisons() {
  const presetWindow = buildAnalysisWindows(cvmAnalysisPreset.value)
  analysisLoading.value = true
  const metricKeys = ['cpu', 'memory', 'network_in', 'network_out', 'disk_usage']

  const results = await Promise.all(
    instanceOptions.value.map(async (instance) => {
      const metrics = await Promise.all(
        metricKeys.map((metricKey) =>
          loadAnalysisMetricBundle({
            resourceType: 'cvm',
            resourceId: instance.id,
            metricKey,
            resourceLabel: instance.name,
            presetWindow,
          }),
        ),
      )

      return {
        instance,
        metrics,
      }
    }),
  )

  analysisLoading.value = false
  return results
}

async function loadCosMetricComparisons() {
  const presetWindow = buildAnalysisWindows(cosAnalysisPreset.value)
  cosAnalysisLoading.value = true
  const metricKeys = ['storage_size', 'object_count', 'network_in', 'network_out', 'request_get', 'request_put']

  const results = await Promise.all(
    cosBuckets.value.map(async (bucket) => {
      const metrics = await Promise.all(
        metricKeys.map((metricKey) =>
          loadAnalysisMetricBundle({
            resourceType: 'cos',
            resourceId: bucket.name,
            metricKey,
            resourceLabel: bucket.label,
            presetWindow,
          }),
        ),
      )

      return {
        bucket,
        metrics,
      }
    }),
  )

  cosAnalysisLoading.value = false
  return results
}

async function loadAnalysisMetricBundle({ resourceType, resourceId, metricKey, resourceLabel, presetWindow }) {
  const [comparison, currentSeries, previousSeries] = await Promise.all([
    fetchMetricComparison({
      resourceType,
      resourceId,
      metricKey,
      currentStart: toIsoString(presetWindow.currentStart),
      currentEnd: toIsoString(presetWindow.end),
      previousStart: toIsoString(presetWindow.previousStart),
      previousEnd: toIsoString(presetWindow.currentStart),
    }).catch(() => buildEmptyComparison(resourceType, resourceId, metricKey, presetWindow)),
    fetchMetricHistory({
      resourceType,
      resourceId,
      metricKey,
      startTime: toIsoString(presetWindow.currentStart),
      endTime: toIsoString(presetWindow.end),
    }).catch(() => buildEmptySeries(resourceType, resourceId, metricKey, presetWindow.currentStart, presetWindow.end)),
    fetchMetricHistory({
      resourceType,
      resourceId,
      metricKey,
      startTime: toIsoString(presetWindow.previousStart),
      endTime: toIsoString(presetWindow.currentStart),
    }).catch(() => buildEmptySeries(resourceType, resourceId, metricKey, presetWindow.previousStart, presetWindow.currentStart)),
  ])

  return buildAnalysisChart(resourceLabel, comparison, currentSeries, previousSeries, presetWindow.preset)
}

async function refreshVisibleAnalysis() {
  if (activeTab.value === 'cvm-analysis' || metricComparisons.value.length) {
    metricComparisons.value = await loadMetricComparisons()
  }

  if (activeTab.value === 'cos-analysis' || cosMetricComparisons.value.length) {
    cosMetricComparisons.value = await loadCosMetricComparisons()
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
  startCollectorCountdown()
})

watch(activeTab, async (tab) => {
  if (tab === 'cvm-analysis' && !metricComparisons.value.length) {
    metricComparisons.value = await loadMetricComparisons()
  }

  if (tab === 'cos-analysis' && !cosMetricComparisons.value.length) {
    cosMetricComparisons.value = await loadCosMetricComparisons()
  }
})

watch(cvmAnalysisPreset, async () => {
  if (activeTab.value === 'cvm-analysis' || metricComparisons.value.length) {
    metricComparisons.value = await loadMetricComparisons()
  }
})

watch(cosAnalysisPreset, async () => {
  if (activeTab.value === 'cos-analysis' || cosMetricComparisons.value.length) {
    cosMetricComparisons.value = await loadCosMetricComparisons()
  }
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
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
          主机监控、主机分析、对象存储监控和对象存储分析分开呈现，实时运行态和时间窗对比各看各的，版面会更清楚。
        </p>
        <p class="hero-meta-line">
          最后一次采集 {{ formatDateTime(collectorStatus?.finishedAt || collectorStatus?.startedAt) }}
          · 下一次采集 {{ collectorCountdown }}
          · 本轮写入 {{ collectorStatus?.pointsWritten ?? '--' }} 点
          · 状态 {{ collectorStatus?.status || '--' }}
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
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cvm-monitor' }" @click="activeTab = 'cvm-monitor'">
        CVM 监控
      </button>
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cvm-analysis' }" @click="activeTab = 'cvm-analysis'">
        CVM 分析
      </button>
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cos-monitor' }" @click="activeTab = 'cos-monitor'">
        COS 存储
      </button>
      <button type="button" class="tab-button" :class="{ active: activeTab === 'cos-analysis' }" @click="activeTab = 'cos-analysis'">
        COS 存储分析
      </button>
    </section>

    <template v-if="activeTab === 'cvm-monitor'">
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
    </template>

    <template v-else-if="activeTab === 'cvm-analysis'">
      <section class="analysis-toolbar">
        <div>
          <p class="comparison-eyebrow">CVM Analysis</p>
          <h2>趋势与窗口分析</h2>
        </div>
        <div class="analysis-preset-list">
          <button
            v-for="preset in analysisPresets"
            :key="preset.key"
            type="button"
            class="ghost-button"
            :class="{ active: cvmAnalysisPreset === preset.key }"
            @click="cvmAnalysisPreset = preset.key"
          >
            {{ preset.label }}
          </button>
        </div>
        <p class="comparison-note">{{ getPresetConfig(cvmAnalysisPreset).description }}</p>
      </section>

      <p v-if="analysisLoading" class="analysis-empty">分析图表加载中...</p>
      <section v-for="entry in metricComparisons" :key="entry.instance.id" class="analysis-resource-section">
        <div class="analysis-resource-header">
          <div>
            <p class="instance-tag">cvm</p>
            <h2>{{ entry.instance.name }}</h2>
            <p class="instance-meta">{{ entry.instance.id }}</p>
          </div>
        </div>
        <div class="analysis-chart-grid">
          <ComparisonTrendChart
            v-for="metric in entry.metrics"
            :key="`${entry.instance.id}-${metric.metricKey}`"
            :chart="metric"
          />
        </div>
      </section>
      <p v-if="!analysisLoading && !metricComparisons.length" class="analysis-empty">当前时间窗下还没有可用于分析的 CVM 历史数据。</p>

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

    <template v-else-if="activeTab === 'cos-monitor'">
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

    <template v-else>
      <section class="analysis-toolbar">
        <div>
          <p class="comparison-eyebrow">COS Analysis</p>
          <h2>存储与流量分析</h2>
        </div>
        <div class="analysis-preset-list">
          <button
            v-for="preset in analysisPresets"
            :key="preset.key"
            type="button"
            class="ghost-button"
            :class="{ active: cosAnalysisPreset === preset.key }"
            @click="cosAnalysisPreset = preset.key"
          >
            {{ preset.label }}
          </button>
        </div>
        <p class="comparison-note">{{ getPresetConfig(cosAnalysisPreset).description }}</p>
      </section>

      <p v-if="cosAnalysisLoading" class="analysis-empty">分析图表加载中...</p>
      <section v-for="entry in cosMetricComparisons" :key="entry.bucket.name" class="analysis-resource-section">
        <div class="analysis-resource-header">
          <div>
            <p class="instance-tag">cos</p>
            <h2>{{ entry.bucket.label }}</h2>
            <p class="instance-meta">{{ entry.bucket.name }}</p>
          </div>
        </div>
        <div class="analysis-chart-grid">
          <ComparisonTrendChart
            v-for="metric in entry.metrics"
            :key="`${entry.bucket.name}-${metric.metricKey}`"
            :chart="metric"
          />
        </div>
      </section>
      <p v-if="!cosAnalysisLoading && !cosMetricComparisons.length" class="analysis-empty">当前时间窗下还没有可用于分析的 COS 历史数据。</p>
    </template>
  </main>
</template>
