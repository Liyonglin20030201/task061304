<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>趋势预测</template>
          <div style="margin-bottom: 12px; display: flex; gap: 10px;">
            <el-select v-model="forecastStoreId" placeholder="选择门店" size="small" style="width: 200px;">
              <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-button type="primary" size="small" @click="loadForecast">预测</el-button>
          </div>
          <chart-panel :option="forecastOption" height="350px" />
          <div v-if="forecastMetrics.mape" style="margin-top: 8px; color: #909399; font-size: 12px;">
            MAPE: {{ forecastMetrics.mape }}% | 置信度: {{ forecastMetrics.confidence_level }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>缺失时间段检测</template>
          <div style="margin-bottom: 12px; display: flex; gap: 10px;">
            <el-select v-model="missingStoreId" placeholder="选择门店" size="small" style="width: 200px;">
              <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-button type="warning" size="small" @click="loadMissing">检测</el-button>
          </div>
          <el-alert v-if="missingData.total_missing_days > 0" type="warning" :title="`共缺失 ${missingData.total_missing_days} 天数据`" show-icon style="margin-bottom: 12px;" />
          <el-table :data="missingData.gaps || []" size="small" max-height="280">
            <el-table-column prop="start" label="开始日期" />
            <el-table-column prop="end" label="结束日期" />
            <el-table-column prop="days" label="缺失天数" width="90" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'
import { useAppStore } from '../stores/app'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)
const forecastStoreId = ref(null)
const missingStoreId = ref(null)
const forecastData = ref({ historical: [], forecast: [] })
const forecastMetrics = ref({})
const missingData = ref({ total_missing_days: 0, gaps: [] })

onMounted(() => { appStore.fetchStores() })

async function loadForecast() {
  if (!forecastStoreId.value) return
  const { data } = await api.get('/api/analytics/forecast', { params: { store_id: forecastStoreId.value, periods: 30 } })
  forecastData.value = data
  forecastMetrics.value = data.metrics || {}
}

async function loadMissing() {
  if (!missingStoreId.value) return
  const { data } = await api.get('/api/analytics/missing-periods', { params: { store_id: missingStoreId.value, data_type: 'sales' } })
  missingData.value = data
}

const forecastOption = computed(() => {
  const hist = forecastData.value.historical || []
  const fore = forecastData.value.forecast || []
  const allDates = [...hist.map(h => h.date), ...fore.map(f => f.date)]
  const histValues = hist.map(h => h.value)
  const foreValues = [...new Array(hist.length).fill(null), ...fore.map(f => f.value)]
  const lower = [...new Array(hist.length).fill(null), ...fore.map(f => f.lower)]
  const upper = [...new Array(hist.length).fill(null), ...fore.map(f => f.upper)]

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['历史', '预测', '置信下界', '置信上界'] },
    xAxis: { type: 'category', data: allDates },
    yAxis: { type: 'value' },
    series: [
      { name: '历史', type: 'line', data: [...histValues, ...new Array(fore.length).fill(null)], lineStyle: { color: '#409eff' } },
      { name: '预测', type: 'line', data: foreValues, lineStyle: { type: 'dashed', color: '#e6a23c' } },
      { name: '置信下界', type: 'line', data: lower, lineStyle: { type: 'dotted', color: '#c0c4cc' }, symbol: 'none' },
      { name: '置信上界', type: 'line', data: upper, lineStyle: { type: 'dotted', color: '#c0c4cc' }, symbol: 'none' },
    ],
  }
})
</script>
