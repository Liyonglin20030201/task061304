<template>
  <div class="energy-gauge">
    <div ref="chartRef" :style="{ width: width, height: height }"></div>
    <div class="gauge-label">{{ label }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  value: { type: Number, default: 0 },
  max: { type: Number, default: 800 },
  label: { type: String, default: '' },
  unit: { type: String, default: 'kW' },
  width: { type: String, default: '200px' },
  height: { type: String, default: '200px' },
})

const chartRef = ref(null)
let chart = null

function getOption() {
  const percent = props.value / props.max
  let color = '#67c23a'
  if (percent > 0.8) color = '#f56c6c'
  else if (percent > 0.6) color = '#e6a23c'

  return {
    series: [{
      type: 'gauge',
      min: 0,
      max: props.max,
      progress: { show: true, width: 12 },
      axisLine: { lineStyle: { width: 12 } },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { width: 2 } },
      axisLabel: { distance: 20, fontSize: 10 },
      pointer: { length: '60%', width: 4 },
      detail: {
        valueAnimation: true,
        formatter: `{value} ${props.unit}`,
        fontSize: 14,
        offsetCenter: [0, '70%'],
      },
      data: [{ value: props.value }],
      itemStyle: { color },
    }],
  }
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  chart.setOption(getOption())
})

watch(() => props.value, () => {
  chart?.setOption(getOption())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.energy-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.gauge-label {
  margin-top: -10px;
  font-size: 13px;
  color: #606266;
}
</style>
