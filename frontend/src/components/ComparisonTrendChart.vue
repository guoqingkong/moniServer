<script setup>
import * as echarts from 'echarts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  chart: {
    type: Object,
    required: true,
  },
})

const chartEl = ref(null)
let chartInstance

const summaryItems = computed(() => [
  {
    label: '当前均值',
    value: props.chart.currentWindow?.average,
    unit: props.chart.unit,
  },
  {
    label: '上一窗口均值',
    value: props.chart.previousWindow?.average,
    unit: props.chart.unit,
  },
  {
    label: '均值变化',
    value: props.chart.averageDelta,
    unit: props.chart.unit,
    signed: true,
  },
  {
    label: '峰值变化',
    value: props.chart.peakDelta,
    unit: props.chart.unit,
    signed: true,
  },
])

function formatValue(value, signed = false) {
  if (value === null || value === undefined) {
    return '--'
  }

  const prefix = signed && value > 0 ? '+' : ''
  return `${prefix}${Number(value).toFixed(2)}`
}

function formatRelativeLabel(ms, durationMs) {
  const totalMinutes = Math.round(ms / 60000)

  if (durationMs <= 30 * 60 * 1000) {
    return `${totalMinutes} 分`
  }

  if (durationMs <= 24 * 60 * 60 * 1000) {
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return minutes === 0 ? `${hours} 小时` : `${hours} 小时 ${minutes} 分`
  }

  const totalHours = Math.round(ms / (60 * 60 * 1000))
  if (durationMs <= 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(totalHours / 24)
    const hours = totalHours % 24
    return hours === 0 ? `${days} 天` : `${days} 天 ${hours} 小时`
  }

  return `${totalHours} 小时`
}

function buildRelativeAxis() {
  const maxPoints = Math.max(props.chart.currentSeries.points.length, props.chart.previousSeries.points.length, 2)
  const stepCount = Math.max(maxPoints - 1, 1)

  return Array.from({ length: maxPoints }, (_, index) => {
    const progress = index / stepCount
    return formatRelativeLabel(progress * props.chart.durationMs, props.chart.durationMs)
  })
}

function fillSeriesData(points, axisLength) {
  const data = new Array(axisLength).fill(null)
  points.forEach((point, index) => {
    if (index < axisLength) {
      data[index] = point.value
    }
  })
  return data
}

function renderChart() {
  if (!chartEl.value) {
    return
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }

  const xAxisData = buildRelativeAxis()
  const axisLength = xAxisData.length

  chartInstance.setOption({
    backgroundColor: 'transparent',
    grid: { left: 44, right: 24, top: 46, bottom: 42 },
    legend: {
      top: 4,
      textStyle: { color: '#cbd5e1' },
      data: ['当前窗口', '上一窗口'],
    },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null || value === undefined ? '--' : `${value} ${props.chart.unit}`),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLabel: { color: '#64748b' },
      data: xAxisData,
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.18)' } },
    },
    series: [
      {
        name: '当前窗口',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 3, color: '#14b8a6' },
        areaStyle: {
          color: 'rgba(20, 184, 166, 0.12)',
        },
        data: fillSeriesData(props.chart.currentSeries.points, axisLength),
      },
      {
        name: '上一窗口',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, type: 'dashed', color: '#f59e0b' },
        data: fillSeriesData(props.chart.previousSeries.points, axisLength),
      },
    ],
  })
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

watch(
  () => props.chart,
  () => {
    renderChart()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<template>
  <section class="analysis-chart-card">
    <div class="analysis-chart-header">
      <div>
        <p class="analysis-chart-eyebrow">{{ chart.resourceLabel }}</p>
        <h3>{{ chart.metricLabel }}</h3>
        <p class="analysis-chart-note">
          {{ chart.presetDescription }}
        </p>
      </div>
      <div class="analysis-summary-grid">
        <div v-for="item in summaryItems" :key="item.label" class="analysis-summary-item">
          <span>{{ item.label }}</span>
          <strong>{{ formatValue(item.value, item.signed) }} <small>{{ item.unit }}</small></strong>
        </div>
      </div>
    </div>

    <div ref="chartEl" class="analysis-chart-canvas"></div>
  </section>
</template>
