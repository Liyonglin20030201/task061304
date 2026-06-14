<template>
  <div class="energy-dashboard">
    <el-row :gutter="16" class="status-bar">
      <el-col :span="5">
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
      <el-col :span="5">
        <el-statistic title="WebSocket">
          <template #default>
            <el-tag :type="store.connected ? 'success' : 'danger'" size="small">
              {{ store.connected ? '已连接' : '断开' }}
            </el-tag>
            <span v-if="store.droppedFrames" class="dropped">(丢帧:{{ store.droppedFrames }})</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="5">
        <el-statistic title="采样序号">
          <template #default>
            <span class="stat-value">{{ store.lastSeq }}</span>
            <span class="stat-unit">seq</span>
          </template>
        </el-statistic>
      </el-col>
      <el-col :span="5">
        <el-statistic title="今日能耗估算">
          <template #default>
            <span class="stat-value">{{ dailyEstimate }}</span>
            <span class="stat-unit">kWh</span>
          </template>
        </el-statistic>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="16">
        <el-card header="实时功率趋势">
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
let trendTimer = null

const cranes = computed(() => store.equipmentList.filter(e => e.equipment_type === 'crane'))

const totalPower = computed(() => {
  const sum = Object.values(store.readings).reduce((acc, r) => acc + (r.power_kw || 0), 0)
  return Math.round(sum)
})

const activeCount = computed(() => {
  return Object.values(store.readings).filter(r => r.operational_state !== 'idle').length
})

const dailyEstimate = computed(() => {
  return Math.round(totalPower.value * 0.6 * 24)
})

function getReading(id) {
  return Math.round(store.readings[id]?.power_kw || 0)
}

function updateTrendChart() {
  if (!trendChart) return
  const series = []
  const legend = []
  for (const equip of store.equipmentList.slice(0, 4)) {
    const buffer = store.trendBuffer[equip.id] || []
    legend.push(equip.name)
    series.push({
      name: equip.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: buffer.map(p => [new Date(p.time).getTime(), p.power]),
    })
  }
  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: legend },
    xAxis: { type: 'time', splitNumber: 6 },
    yAxis: { type: 'value', name: '功率 (kW)' },
    series,
    animation: false,
  })
}

function updateCostChart() {
  if (!costChart || !store.costSummary.length) return
  costChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: store.costSummary.map(s => s.equipment_code) },
    yAxis: [
      { type: 'value', name: '能耗 (kWh)' },
      { type: 'value', name: '成本 (元)' },
    ],
    series: [
      { name: '能耗', type: 'bar', data: store.costSummary.map(s => s.total_energy_kwh) },
      { name: '成本', type: 'line', yAxisIndex: 1, data: store.costSummary.map(s => s.cost) },
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

  trendTimer = setInterval(updateTrendChart, 2000)
})

onUnmounted(() => {
  store.disconnect()
  trendChart?.dispose()
  costChart?.dispose()
  if (trendTimer) clearInterval(trendTimer)
})
</script>

<style scoped>
.energy-dashboard { padding: 0; }
.status-bar { background: #fff; padding: 20px; border-radius: 4px; }
.stat-value { font-size: 24px; font-weight: bold; color: #303133; }
.stat-unit { font-size: 14px; color: #909399; margin-left: 4px; }
.gauge-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  justify-items: center;
}
.dropped { font-size: 11px; color: #f56c6c; margin-left: 4px; }
</style>
