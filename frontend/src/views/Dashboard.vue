<template>
  <div>
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6" v-for="card in kpiCards" :key="card.label">
        <el-card shadow="hover">
          <div style="text-align: center;">
            <div style="font-size: 28px; font-weight: bold; color: #409eff;">{{ card.value }}</div>
            <div style="color: #909399; margin-top: 8px;">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>销售趋势</template>
          <chart-panel :option="salesTrendOption" height="350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>门店排名 TOP10</template>
          <chart-panel :option="rankingOption" height="350px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header>消费者分群</template>
          <chart-panel :option="segmentOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>异常检测</template>
          <el-table :data="anomalies" size="small" max-height="300">
            <el-table-column prop="store_name" label="门店" width="100" />
            <el-table-column prop="date" label="日期" width="110" />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="severity" label="严重度" width="80">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'high' ? 'danger' : 'warning'" size="small">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="value" label="值" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()
const kpi = ref({})
const ranking = ref([])
const segments = ref([])
const anomalies = ref([])

const today = new Date()
const startDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0]
const endDate = today.toISOString().split('T')[0]

onMounted(async () => {
  try {
    const [kpiRes, rankRes, segRes, anomRes] = await Promise.all([
      api.get('/api/analytics/kpi', { params: { start_date: startDate, end_date: endDate } }),
      api.get('/api/analytics/ranking', { params: { start_date: startDate, end_date: endDate, metric: 'gmv' } }),
      api.get('/api/analytics/segmentation'),
      api.get('/api/analytics/anomalies', { params: { start_date: startDate, end_date: endDate } }),
    ])
    kpi.value = kpiRes.data
    ranking.value = rankRes.data || []
    segments.value = segRes.data?.segments || []
    anomalies.value = (anomRes.data?.anomalies || []).slice(0, 10)
  } catch (e) {
    console.error('Failed to load dashboard data', e)
  }
})

const kpiCards = computed(() => [
  { label: 'GMV (元)', value: (kpi.value.gmv || 0).toLocaleString() },
  { label: '订单数', value: (kpi.value.total_orders || 0).toLocaleString() },
  { label: '客单价 (元)', value: (kpi.value.avg_ticket || 0).toFixed(2) },
  { label: '坪效 (元/㎡)', value: (kpi.value.sqm_efficiency || 0).toFixed(2) },
])

const salesTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ranking.value.map(r => r.store_code) },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: ranking.value.map(r => r.gmv), itemStyle: { color: '#409eff' } }],
}))

const rankingOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'value' },
  yAxis: { type: 'category', data: ranking.value.slice(0, 10).map(r => r.store_name).reverse() },
  series: [{ type: 'bar', data: ranking.value.slice(0, 10).map(r => r.gmv).reverse(), itemStyle: { color: '#67c23a' } }],
}))

const segmentOption = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: segments.value.map(s => ({ name: s.segment, value: s.count })),
  }],
}))
</script>
