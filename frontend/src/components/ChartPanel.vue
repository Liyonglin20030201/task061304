<template>
  <div ref="chartRef" :style="{ width: '100%', height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, default: () => ({}) },
  height: { type: String, default: '300px' },
})

const chartRef = ref(null)
let chart = null

onMounted(() => {
  chart = echarts.init(chartRef.value)
  if (props.option && Object.keys(props.option).length) {
    chart.setOption(props.option)
  }
  window.addEventListener('resize', handleResize)
})

watch(() => props.option, (newOption) => {
  if (chart && newOption && Object.keys(newOption).length) {
    chart.setOption(newOption, true)
  }
}, { deep: true })

function handleResize() {
  chart?.resize()
}

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>
