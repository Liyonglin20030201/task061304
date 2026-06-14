<template>
  <div class="energy-dashboard">
    <el-row :gutter="16" class="status-bar">
      <el-col :span="4">
        <el-statistic title="总实时功率">
          <template #default>
            <span class="stat-value">{{ totalPower }}</span>
            <span class="stat-unit">kW</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="4">
        <el-statistic title="运行设备">
          <template #default>
            <span class="stat-value">{{ activeCount }}</span>
            <span class="stat-unit">/ {{ store.equipmentList.length }}</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="4">
        <el-statistic title="链路延迟">
          <template #default>
            <span class="stat-value" :class="{ 'lag-warn': store.latencyMs > 1000 }">{{ store.latencyMs }}</span>
            <span class="stat-unit">ms</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="4">
        <el-statistic title="序号/丢帧">
          <template #default>
            <span class="stat-value">{{ store.lastSeq }}</span>
            <span v-if="store.droppedFrames" class="dropped"> / {{ store.droppedFrames }}</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="4">
        <el-statistic title="累计能耗">
          <template #default>
            <span class="stat-value">{{ totalCumulativeKwh }}</span>
            <span class="stat-unit">kWh</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="4">
        <el-statistic title="连接状态">
          <template #default>
            <el-tag :type="store.connected ? 'success' : 'danger'" size="small">
              {{ store.connected ? '实时' : '断开' }}
            </el-tag>
          </template>
        </el-statistic>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="16">
        <el-card header="实时功率趋势 (1s刷新)">
          <div ref="trendChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="设备功率仪表">
          <div class="gauge-grid">
            <EnergyGauge
              v-for="equip in cranes"
              :key="equip.id"
              :value="getReading(equip.id)"
              :max="equip.max_power_kw"
              :label="equip.name"
              width="160px"
              height="160px"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card header="能耗成本分析">
          <div ref="costChartRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="设备状态">
          <EquipmentStatus :equipment="store.equipmentList" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { usePortEnergyStore } from '../../stores/portEnergy'
import EnergyGauge from '../../components/port/EnergyGauge.vue'
import EquipmentStatus from '../../components/port/EquipmentStatus.vue'

const store = usePortEnergyStore()
const trendChartRef = ref(null)
const costChartRef = ref(null)
let trendChart = null
let costChart = null
let rafId = null
let lastRenderTs = 0

const cranes = computed(() => store.equipmentList.filter(e => e.equipment_type === 'crane'))

const totalPower = computed(() => {
  return Math.round(Object.values(store.readings).reduce((s, r) => s + (r.power_kw || 0), 0))
})

const activeCount = computed(() => {
  return Object.values(store.readings).filter(r => r.state !== 'idle').length
})

const totalCumulativeKwh = computed(() => {
  const sum = Object.values(store.readings).reduce((s, r) => s + (r.cumulative_kwh || 0), 0)
  return sum.toFixed(2)
})

function getReading(id) {
  return Math.round(store.readings[id]?.power_kw || 0)
}

function renderLoop(timestamp) {
  rafId = requestAnimationFrame(renderLoop)
  if (timestamp - lastRenderTs < 1000) return
  lastRenderTs = timestamp
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart || !store.equipmentList.length) return
  const series = []
  const legend = []
  for (const equip of store.equipmentList.slice(0, 4)) {
    const buffer = store.trendBuffer[equip.id] || []
    legend.push(equip.name)
    series.push({
      name: equip.name,
      type: 'line',
      smooth: false,
      showSymbol: false,
      data: buffer,
    })
  }
  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: legend, top: 0 },
    grid: { top: 30, bottom: 30 },
    xAxis: { type: 'time', splitNumber: 8, axisLabel: { formatter: '{HH}:{mm}:{ss}' } },
    yAxis: { type: 'value', name: 'kW', nameLocation: 'end' },
    series,
    animation: false,
  })
}

function updateCostChart() {
  if (!costChart || !store.costSummary.length) return
  costChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['能耗 (kWh)', '成本 (元)'] },
    xAxis: { type: 'category', data: store.costSummary.map(s => s.equipment_code) },
    yAxis: [
      { type: 'value', name: 'kWh' },
      { type: 'value', name: '元' },
    ],
    series: [
      { name: '能耗 (kWh)', type: 'bar', data: store.costSummary.map(s => s.total_kwh) },
      { name: '成本 (元)', type: 'line', yAxisIndex: 1, data: store.costSummary.map(s => s.cost_yuan) },
    ],
  })
}

onMounted(async () => {
  store.connect()
  await store.fetchEquipment()
  await store.fetchCostSummary({})

  trendChart = echarts.init(trendChartRef.value)
  costChart = echarts.init(costChartRef.value)
  updateCostChart()

  rafId = requestAnimationFrame(renderLoop)
})

onUnmounted(() => {
  store.disconnect()
  if (rafId) cancelAnimationFrame(rafId)
  trendChart?.dispose()
  costChart?.dispose()
})
</script>

<style scoped>
.energy-dashboard { padding: 0; }
.status-bar { background: #fff; padding: 20px; border-radius: 4px; }
.stat-value { font-size: 24px; font-weight: bold; color: #303133; }
.stat-unit { font-size: 14px; color: #909399; margin-left: 4px; }
.lag-warn { color: #f56c6c; }
.dropped { font-size: 12px; color: #f56c6c; }
.gauge-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  justify-items: center;
}
</style>
