<script setup>
defineProps({
  card: {
    type: Object,
    required: true,
  },
})

function formatValue(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return Number(value).toFixed(2)
}
</script>

<template>
  <article class="metric-card">
    <p class="metric-label">{{ card.label }}</p>
    <p class="metric-value">{{ formatValue(card.latest) }} <span>{{ card.unit }}</span></p>
    <div class="metric-stats">
      <span>均值 {{ formatValue(card.average) }}</span>
      <span>峰值 {{ formatValue(card.peak) }}</span>
    </div>
  </article>
</template>
