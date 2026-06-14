<template>
  <div class="data-quality-container" style="padding: 20px;">
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <store-selector />
      </el-col>
      <el-col :span="6">
        <el-select v-model="targetTable" placeholder="选择数据表" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="销售数据" value="sales" />
          <el-option label="库存数据" value="inventory" />
          <el-option label="客流数据" value="traffic" />
          <el-option label="会员数据" value="members" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="runCheck" :loading="checking">执行检查</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center;">
            <chart-panel :option="gaugeOption" height="200px" />
            <div style="font-size: 14px; color: #666;">综合健康分数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 40px 0;">
            <div :style="{fontSize: '36px', fontWeight: 'bold', color: getScoreColor(health.completeness_score)}">{{ health.completeness_score }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">完整性</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 40px 0;">
            <div :style="{fontSize: '36px', fontWeight: 'bold', color: getScoreColor(health.accuracy_score)}">{{ health.accuracy_score }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">准确性</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 40px 0;">
            <div :style="{fontSize: '36px', fontWeight: 'bold', color: getScoreColor(health.timeliness_score)}">{{ health.timeliness_score }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 8px;">时效性</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="14">
        <el-card>
          <template #header><span>质量趋势</span></template>
          <chart-panel :option="trendOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header><span>各表质量热力图</span></template>
          <chart-panel :option="heatmapOption" height="300px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>预警列表</span>
          <div>
            <el-tag :type="alerts.total > 0 ? 'danger' : 'success'">{{ alerts.total }} 条预警</el-tag>
          </div>
        </div>
      </template>
      <el-table :data="alerts.items" stripe border>
        <el-table-column prop="severity" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : row.severity === 'error' ? 'warning' : 'info'" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_table" label="数据表" width="100" />
        <el-table-column prop="dimension" label="维度" width="100" />
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="metric_value" label="指标值" width="100">
          <template #default="{ row }">{{ row.metric_value ? (row.metric_value * 100).toFixed(1) + '%' : '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'open' ? 'danger' : row.status === 'acknowledged' ? 'warning' : 'success'" size="small">
              {{ row.status === 'open' ? '待处理' : row.status === 'acknowledged' ? '已确认' : '已解决' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button v-if="row.status === 'open'" size="small" @click="acknowledgeAlert(row.id)">确认</el-button>
            <el-button v-if="row.status !== 'resolved'" size="small" type="success" @click="resolveAlert(row.id)">解决</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="isAdmin">
      <template #header><span>质量规则管理</span></template>
      <el-table :data="rules" stripe border>
        <el-table-column prop="rule_name" label="规则名称" min-width="150" />
        <el-table-column prop="target_table" label="目标表" width="100" />
        <el-table-column prop="dimension" label="维度" width="100" />
        <el-table-column prop="check_type" label="检查类型" width="120" />
        <el-table-column prop="threshold_warn" label="警告阈值" width="100">
          <template #default="{ row }">{{ (row.threshold_warn * 100).toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column prop="threshold_error" label="错误阈值" width="100">
          <template #default="{ row }">{{ (row.threshold_error * 100).toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import ChartPanel from '@/components/ChartPanel.vue'
import StoreSelector from '@/components/StoreSelector.vue'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const appStore = useAppStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

const targetTable = ref('')
const checking = ref(false)
const health = ref({ overall_score: 0, completeness_score: 0, accuracy_score: 0, timeliness_score: 0, alerts_open: 0, alerts_critical: 0 })
const alerts = ref({ items: [], total: 0 })
const trendData = ref([])
const scores = ref([])
const rules = ref([])

const getScoreColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const gaugeOption = computed(() => ({
  series: [{
    type: 'gauge',
    startAngle: 210,
    endAngle: -30,
    min: 0,
    max: 100,
    progress: { show: true, width: 18 },
    axisLine: { lineStyle: { width: 18 } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    pointer: { show: true },
    detail: { fontSize: 28, offsetCenter: [0, '60%'], formatter: '{value}' },
    data: [{ value: health.value.overall_score, name: '' }],
    color: [[0.6, '#f56c6c'], [0.8, '#e6a23c'], [1, '#67c23a']],
  }],
}))

const trendOption = computed(() => {
  const dims = ['completeness', 'accuracy', 'timeliness']
  const dimNames = { completeness: '完整性', accuracy: '准确性', timeliness: '时效性' }
  const colors = { completeness: '#409eff', accuracy: '#67c23a', timeliness: '#e6a23c' }
  const dates = [...new Set(trendData.value.map(d => d.score_date))].sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: dims.map(d => dimNames[d]) },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', min: 0, max: 100 },
    series: dims.map(dim => ({
      name: dimNames[dim],
      type: 'line',
      smooth: true,
      data: dates.map(date => {
        const item = trendData.value.find(d => d.score_date === date && d.dimension === dim)
        return item ? item.avg_score : null
      }),
      itemStyle: { color: colors[dim] },
    })),
  }
})

const heatmapOption = computed(() => {
  const tables = ['sales', 'inventory', 'traffic', 'members']
  const tableNames = { sales: '销售', inventory: '库存', traffic: '客流', members: '会员' }
  const dims = ['completeness', 'accuracy', 'timeliness']
  const dimNames = ['完整性', '准确性', '时效性']
  const data = []
  scores.value.forEach(s => {
    const x = dims.indexOf(s.dimension)
    const y = tables.indexOf(s.target_table)
    if (x >= 0 && y >= 0) data.push([x, y, s.score])
  })
  return {
    tooltip: { formatter: p => `${tableNames[tables[p.data[1]]]}-${dimNames[p.data[0]]}: ${p.data[2]}分` },
    xAxis: { type: 'category', data: dimNames },
    yAxis: { type: 'category', data: tables.map(t => tableNames[t]) },
    visualMap: { min: 0, max: 100, inRange: { color: ['#f56c6c', '#e6a23c', '#67c23a'] } },
    series: [{ type: 'heatmap', data, label: { show: true } }],
  }
})

const loadData = async () => {
  const storeParam = appStore.selectedStoreIds.length > 0 ? `store_ids=${appStore.selectedStoreIds.join(',')}` : ''
  const tableParam = targetTable.value ? `&target_table=${targetTable.value}` : ''
  try {
    const [healthRes, alertsRes, trendRes, scoresRes, rulesRes] = await Promise.all([
      api.get(`/api/data-quality/health?${storeParam}`),
      api.get(`/api/data-quality/alerts?${storeParam}&page=1&page_size=20`),
      api.get(`/api/data-quality/scores/trend?${storeParam}${tableParam}&days=30`),
      api.get(`/api/data-quality/scores?${storeParam}${tableParam}`),
      api.get(`/api/data-quality/rules`),
    ])
    health.value = healthRes.data
    alerts.value = alertsRes.data
    trendData.value = trendRes.data
    scores.value = scoresRes.data
    rules.value = rulesRes.data
  } catch (e) {
    console.error('加载数据质量数据失败', e)
  }
}

const runCheck = async () => {
  checking.value = true
  try {
    const storeParam = appStore.selectedStoreIds.length > 0 ? `store_ids=${appStore.selectedStoreIds.join(',')}` : ''
    await api.post(`/api/data-quality/run-check?${storeParam}`)
    ElMessage.success('质量检查完成')
    await loadData()
  } catch (e) {
    ElMessage.error('检查执行失败')
  } finally {
    checking.value = false
  }
}

const acknowledgeAlert = async (id) => {
  await api.put(`/api/data-quality/alerts/${id}/acknowledge`)
  await loadData()
}

const resolveAlert = async (id) => {
  await api.put(`/api/data-quality/alerts/${id}/resolve`)
  await loadData()
}

onMounted(loadData)
</script>
