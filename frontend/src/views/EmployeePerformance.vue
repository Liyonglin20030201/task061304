<template>
  <div class="employee-performance-container" style="padding: 20px;">
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6"><store-selector /></el-col>
      <el-col :span="8">
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
          start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" @change="loadData" />
      </el-col>
      <el-col :span="4">
        <el-select v-model="position" placeholder="岗位" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="收银" value="cashier" />
          <el-option label="销售" value="sales" />
          <el-option label="店长" value="manager" />
          <el-option label="仓管" value="stock" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="loadData">查询</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 32px; font-weight: bold; color: #409eff;">{{ dashboard.avg_score }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">平均绩效分</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 18px; font-weight: bold; color: #67c23a;">{{ dashboard.top_performer || '-' }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">最佳员工 ({{ dashboard.top_score }}分)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 32px; font-weight: bold; color: #e6a23c;">{{ dashboard.avg_attendance_rate }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">平均出勤分</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 32px; font-weight: bold; color: #909399;">{{ dashboard.total_employees }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">员工总数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header><span>能力雷达图</span></template>
          <chart-panel :option="radarOption" height="350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>绩效趋势</span></template>
          <chart-panel :option="trendOption" height="350px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header><span>绩效排名</span></template>
      <el-table :data="ranking" stripe border @row-click="selectEmployee">
        <el-table-column prop="rank_in_store" label="排名" width="70" />
        <el-table-column prop="employee_name" label="姓名" width="100" />
        <el-table-column prop="position" label="岗位" width="80" />
        <el-table-column prop="composite_score" label="综合分" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.composite_score >= 80 ? '#67c23a' : row.composite_score >= 60 ? '#e6a23c' : '#f56c6c', fontWeight: 'bold' }">
              {{ row.composite_score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sales_score" label="销售" width="80" />
        <el-table-column prop="service_score" label="服务" width="80" />
        <el-table-column prop="attendance_score" label="考勤" width="80" />
        <el-table-column prop="training_score" label="培训" width="80" />
        <el-table-column prop="trend" label="趋势" width="80">
          <template #default="{ row }">
            <el-icon v-if="row.trend === 'up'" style="color: #67c23a;"><Top /></el-icon>
            <el-icon v-else-if="row.trend === 'down'" style="color: #f56c6c;"><Bottom /></el-icon>
            <el-icon v-else style="color: #909399;"><Minus /></el-icon>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import ChartPanel from '@/components/ChartPanel.vue'
import StoreSelector from '@/components/StoreSelector.vue'

const appStore = useAppStore()
const today = new Date()
const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)
const dateRange = ref([thirtyDaysAgo.toISOString().slice(0, 10), today.toISOString().slice(0, 10)])
const position = ref('')
const selectedEmployee = ref(null)

const dashboard = ref({ avg_score: 0, top_performer: null, top_score: 0, improvement_rate: 0, avg_attendance_rate: 0, total_employees: 0 })
const ranking = ref([])
const trendData = ref([])
const comparison = ref(null)

const radarOption = computed(() => {
  if (!comparison.value) {
    return { radar: { indicator: [] }, series: [] }
  }
  return {
    legend: { data: ['个人', '门店均值'] },
    radar: {
      indicator: comparison.value.dimensions.map(d => ({ name: d, max: 100 })),
    },
    series: [{
      type: 'radar',
      data: [
        { value: comparison.value.employee_scores, name: '个人', areaStyle: { opacity: 0.2 } },
        { value: comparison.value.store_avg_scores, name: '门店均值', lineStyle: { type: 'dashed' } },
      ],
    }],
  }
})

const trendOption = computed(() => {
  const months = trendData.value.map(d => d.month)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['综合分', '销售', '服务', '考勤', '培训'] },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', min: 0, max: 100 },
    series: [
      { name: '综合分', type: 'line', data: trendData.value.map(d => d.composite_score), lineStyle: { width: 3 } },
      { name: '销售', type: 'line', data: trendData.value.map(d => d.sales_score), lineStyle: { type: 'dashed' } },
      { name: '服务', type: 'line', data: trendData.value.map(d => d.service_score), lineStyle: { type: 'dashed' } },
      { name: '考勤', type: 'line', data: trendData.value.map(d => d.attendance_score), lineStyle: { type: 'dashed' } },
      { name: '培训', type: 'line', data: trendData.value.map(d => d.training_score), lineStyle: { type: 'dashed' } },
    ],
  }
})

const selectEmployee = async (row) => {
  selectedEmployee.value = row.employee_id
  const [start, end] = dateRange.value
  try {
    const [compRes, trendRes] = await Promise.all([
      api.get(`/api/employee-performance/comparison/${row.employee_id}?start_date=${start}&end_date=${end}&scope=store`),
      api.get(`/api/employee-performance/trend/${row.employee_id}?months=6`),
    ])
    comparison.value = compRes.data
    trendData.value = trendRes.data
  } catch (e) {
    console.error('加载员工详情失败', e)
  }
}

const loadData = async () => {
  if (!dateRange.value || dateRange.value.length < 2) return
  const [start, end] = dateRange.value
  const storeParam = appStore.selectedStoreIds.length > 0 ? `store_ids=${appStore.selectedStoreIds.join(',')}` : ''
  const posParam = position.value ? `&position=${position.value}` : ''
  try {
    const [dashRes, rankRes] = await Promise.all([
      api.get(`/api/employee-performance/dashboard?${storeParam}&start_date=${start}&end_date=${end}`),
      api.get(`/api/employee-performance/ranking?${storeParam}&start_date=${start}&end_date=${end}${posParam}&top_n=20`),
    ])
    dashboard.value = dashRes.data
    ranking.value = rankRes.data
    if (ranking.value.length > 0) {
      await selectEmployee(ranking.value[0])
    }
  } catch (e) {
    console.error('加载绩效数据失败', e)
  }
}

onMounted(loadData)
</script>
