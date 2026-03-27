<script setup>
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  series: {
    type: Object,
    required: true,
  },
})

const chartEl = ref(null)
let chart

function renderChart() {
  if (!chartEl.value) {
    return
  }

  if (!chart) {
    chart = echarts.init(chartEl.value)
  }

  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null || value === undefined ? '--' : `${value} ${props.series.unit}`),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLabel: { color: '#64748b' },
      data: props.series.points.map((point) =>
        new Date(point.timestamp).toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      ),
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.18)' } },
    },
    series: [
      {
        name: props.series.label,
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 3, color: '#0f766e' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(15, 118, 110, 0.35)' },
              { offset: 1, color: 'rgba(15, 118, 110, 0.02)' },
            ],
          },
        },
        data: props.series.points.map((point) => point.value),
      },
    ],
  })
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

watch(
  () => props.series,
  () => {
    renderChart()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<template>
  <section class="chart-card">
    <div class="chart-header">
      <div>
        <h3>{{ series.label }}</h3>
        <p>{{ series.unit }} · 粒度 {{ series.period }}s</p>
      </div>
      <strong>{{ series.latest === null || series.latest === undefined ? '--' : Number(series.latest).toFixed(2) }}</strong>
    </div>
    <div ref="chartEl" class="chart-canvas"></div>
  </section>
</template>
