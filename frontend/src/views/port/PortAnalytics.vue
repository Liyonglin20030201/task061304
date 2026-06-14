<template>
  <div class="port-analytics">
    <el-row :gutter="16" class="metrics-row" v-if="store.dashboard">
      <el-col :span="4"><el-statistic title="在场集装箱" :value="store.dashboard.current_containers" /></el-col>
      <el-col :span="4"><el-statistic title="今日吞吐" :value="store.dashboard.today_throughput"><template #suffix>TEU</template></el-statistic></el-col>
      <el-col :span="4"><el-statistic title="吊机利用率" :value="store.dashboard.avg_crane_util"><template #suffix>%</template></el-statistic></el-col>
      <el-col :span="4"><el-statistic title="AGV利用率" :value="store.dashboard.avg_agv_util"><template #suffix>%</template></el-statistic></el-col>
      <el-col :span="4"><el-statistic title="今日能耗" :value="store.dashboard.today_energy_kwh"><template #suffix>kWh</template></el-statistic></el-col>
      <el-col :span="4"><el-statistic title="能源成本" :value="store.dashboard.energy_cost"><template #prefix>&yen;</template></el-statistic></el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card header="吞吐量趋势">
          <div ref="throughputChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="设备利用率">
          <div ref="utilChartRef" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card header="能耗分布">
          <div ref="energyPieRef" style="height: 280px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="运营报表">
          <el-table :data="reportItems" stripe>
            <el-table-column prop="name" label="指标" />
            <el-table-column prop="value" label="数值" />
            <el-table-column prop="trend" label="趋势" width="80">
              <template #default="{ row }">
                <span :style="{ color: row.trend > 0 ? '#67c23a' : '#f56c6c' }">
                  {{ row.trend > 0 ? '+' : '' }}{{ row.trend }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { usePortAnalyticsStore } from '../../stores/portAnalytics'

const store = usePortAnalyticsStore()
const throughputChartRef = ref(null)
const utilChartRef = ref(null)
const energyPieRef = ref(null)
let throughputChart = null, utilChart = null, energyPie = null

const reportItems = computed(() => {
  if (!store.dashboard) return []
  return [
    { name: '日均吞吐 (TEU)', value: store.dashboard.today_throughput, trend: 5.2 },
    { name: '平均吊机利用率', value: `${store.dashboard.avg_crane_util}%`, trend: 2.1 },
    { name: '平均AGV利用率', value: `${store.dashboard.avg_agv_util}%`, trend: -1.3 },
    { name: '单箱能耗 (kWh)', value: store.dashboard.today_throughput > 0 ? (store.dashboard.today_energy_kwh / store.dashboard.today_throughput).toFixed(1) : '--', trend: -3.5 },
    { name: '在岗人员', value: store.dashboard.personnel_on_duty, trend: 0 },
  ]
})

function renderCharts() {
  if (throughputChart && store.throughput.length) {
    throughputChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: store.throughput.map(t => t.time_bucket) },
      yAxis: { type: 'value', name: 'TEU' },
      series: [{ name: '吞吐量', type: 'bar', data: store.throughput.map(t => t.teu_count), itemStyle: { color: '#409eff' } }],
    })
  }

  if (utilChart && store.utilization.length) {
    utilChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: store.utilization.map(u => u.equipment_code) },
      yAxis: { type: 'value', name: '%', max: 100 },
      series: [{
        name: '利用率',
        type: 'bar',
        data: store.utilization.map(u => u.utilization_percent ? parseFloat(u.utilization_percent).toFixed(1) : 0),
        itemStyle: {
          color: (params) => params.value > 80 ? '#f56c6c' : params.value > 50 ? '#e6a23c' : '#67c23a'
        },
      }],
    })
  }

  if (energyPie && store.utilization.length) {
    energyPie.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: store.utilization.slice(0, 8).map(u => ({
          name: u.equipment_code,
          value: parseFloat(u.operating_hours || 0).toFixed(1),
        })),
      }],
    })
  }
}

onMounted(async () => {
  throughputChart = echarts.init(throughputChartRef.value)
  utilChart = echarts.init(utilChartRef.value)
  energyPie = echarts.init(energyPieRef.value)

  await Promise.all([
    store.fetchDashboard(),
    store.fetchUtilization({}),
    store.fetchThroughput({}),
  ])
  renderCharts()
})

onUnmounted(() => {
  throughputChart?.dispose()
  utilChart?.dispose()
  energyPie?.dispose()
})
</script>

<style scoped>
.metrics-row { background: #fff; padding: 20px; border-radius: 4px; }
</style>
