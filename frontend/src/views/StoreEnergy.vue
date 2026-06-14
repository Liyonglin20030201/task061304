<template>
  <div class="store-energy-container">
    <div class="page-header">
      <h2>门店能耗管理</h2>
      <div class="filter-bar">
        <el-select v-model="selectedStoreId" placeholder="选择门店" style="width: 200px" clearable>
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 280px"
        />
        <el-button type="primary" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-click="onTabChange">
      <!-- Tab 1: 能耗概览 -->
      <el-tab-pane label="能耗概览" name="overview">
        <div class="kpi-cards">
          <el-card class="kpi-card">
            <div class="kpi-value">{{ overview.total_kwh?.toFixed(1) || '0' }}</div>
            <div class="kpi-label">总能耗(kWh)</div>
          </el-card>
          <el-card class="kpi-card">
            <div class="kpi-value">{{ overview.total_cost?.toFixed(2) || '0' }}</div>
            <div class="kpi-label">总费用(元)</div>
          </el-card>
          <el-card class="kpi-card">
            <div class="kpi-value">{{ overview.kwh_per_sqm?.toFixed(2) || '0' }}</div>
            <div class="kpi-label">坪效能耗(kWh/㎡)</div>
          </el-card>
          <el-card class="kpi-card">
            <div class="kpi-value">{{ overview.revenue_per_kwh?.toFixed(2) || '0' }}</div>
            <div class="kpi-label">营收能效(元/kWh)</div>
          </el-card>
          <el-card class="kpi-card">
            <div class="kpi-value" :class="overview.mom_change >= 0 ? 'red' : 'green'">
              {{ overview.mom_change?.toFixed(1) || '0' }}%
            </div>
            <div class="kpi-label">环比变化(%)</div>
          </el-card>
        </div>

        <el-row :gutter="20" style="margin-top: 20px">
          <el-col :span="16">
            <el-card>
              <template #header>能耗与费用趋势</template>
              <chart-panel :option="trendChartOption" height="350px" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card>
              <template #header>设备类型能耗占比</template>
              <chart-panel :option="equipmentPieOption" height="350px" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 2: 设备管理 -->
      <el-tab-pane label="设备管理" name="equipment">
        <div class="toolbar">
          <el-button type="primary" @click="showEquipmentDialog(null)">添加设备</el-button>
        </div>
        <el-table :data="equipmentList" stripe border style="margin-top: 12px">
          <el-table-column prop="equipment_code" label="设备编号" width="130" />
          <el-table-column prop="name" label="名称" width="150" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="brand" label="品牌" width="100" />
          <el-table-column prop="rated_power_kw" label="额定功率(kW)" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="installed_date" label="安装日期" width="120" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="showEquipmentDialog(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="equipmentDialogVisible" :title="editingEquipment ? '编辑设备' : '添加设备'" width="500px">
          <el-form :model="equipmentForm" label-width="110px">
            <el-form-item label="设备编号">
              <el-input v-model="equipmentForm.equipment_code" />
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="equipmentForm.name" />
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="equipmentForm.type" style="width: 100%">
                <el-option label="暖通空调" value="hvac" />
                <el-option label="照明" value="lighting" />
                <el-option label="制冷" value="refrigeration" />
                <el-option label="收银设备" value="pos" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
            <el-form-item label="额定功率(kW)">
              <el-input-number v-model="equipmentForm.rated_power_kw" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item label="品牌">
              <el-input v-model="equipmentForm.brand" />
            </el-form-item>
            <el-form-item label="型号">
              <el-input v-model="equipmentForm.model_no" />
            </el-form-item>
            <el-form-item label="安装日期">
              <el-date-picker v-model="equipmentForm.installed_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="equipmentDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitEquipment">确认</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 3: 能耗分析 -->
      <el-tab-pane label="能耗分析" name="analysis">
        <el-row :gutter="20">
          <el-col :span="24">
            <el-card>
              <template #header>24小时峰谷能耗分布</template>
              <chart-panel :option="peakHourChartOption" height="300px" />
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: 20px">
          <el-col :span="12">
            <el-card>
              <template #header>气温与能耗相关性</template>
              <chart-panel :option="weatherCorrelationOption" height="350px" />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>营收与能耗相关性</template>
              <chart-panel :option="salesCorrelationOption" height="350px" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 4: 智能调度 -->
      <el-tab-pane label="智能调度" name="scheduling">
        <div class="toolbar">
          <el-button type="primary" :loading="optimizing" @click="generateSchedule">生成优化方案</el-button>
        </div>

        <el-card v-if="scheduleSummary.total_saving_kwh" style="margin-top: 12px">
          <div class="summary-row">
            <span>预计每日节省: <strong>{{ scheduleSummary.total_saving_kwh?.toFixed(2) }} kWh</strong></span>
            <span style="margin-left: 24px">预计每日节省费用: <strong>{{ scheduleSummary.total_saving_yuan?.toFixed(2) }} 元</strong></span>
          </div>
        </el-card>

        <el-table :data="scheduleResults" stripe border style="margin-top: 12px">
          <el-table-column prop="equipment_name" label="设备名称" width="150" />
          <el-table-column prop="day_of_week" label="星期" width="80" />
          <el-table-column prop="hour" label="时段" width="70" />
          <el-table-column prop="current_level" label="当前水平" width="100" />
          <el-table-column prop="recommended_level" label="建议水平" width="100" />
          <el-table-column prop="reason" label="原因" />
          <el-table-column prop="estimated_saving" label="预计节省(kWh)" width="130" />
        </el-table>

        <el-card style="margin-top: 20px">
          <template #header>当前调度计划</template>
          <el-table :data="currentSchedules" stripe border>
            <el-table-column prop="equipment_name" label="设备名称" width="150" />
            <el-table-column prop="day_of_week" label="星期" width="80" />
            <el-table-column prop="hour" label="时段" width="70" />
            <el-table-column prop="power_level" label="功率水平" width="100" />
            <el-table-column prop="updated_at" label="更新时间" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Tab 5: 告警管理 -->
      <el-tab-pane label="告警管理" name="alerts">
        <el-card>
          <template #header>预算使用情况</template>
          <div class="budget-progress">
            <div class="budget-info">
              <span>当前用量: {{ budgetUsage.current_kwh?.toFixed(1) || 0 }} kWh</span>
              <span>预算: {{ budgetUsage.budget_kwh || 0 }} kWh</span>
            </div>
            <el-progress
              :percentage="budgetPercentage"
              :color="budgetColor"
              :stroke-width="20"
              style="margin-top: 8px"
            />
          </div>
        </el-card>

        <el-card style="margin-top: 20px">
          <template #header>告警列表</template>
          <el-table :data="alertList" stripe border>
            <el-table-column prop="alert_time" label="告警时间" width="170" />
            <el-table-column label="告警类型" width="120">
              <template #default="{ row }">
                <el-tag>{{ row.alert_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="告警级别" width="100">
              <template #default="{ row }">
                <el-tag :type="alertLevelType(row.alert_level)">{{ row.alert_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.is_acknowledged ? 'success' : 'danger'" size="small">
                  {{ row.is_acknowledged ? '已确认' : '未确认' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  :disabled="row.is_acknowledged"
                  @click="acknowledgeAlert(row)"
                >确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card style="margin-top: 20px">
          <template #header>预算设置</template>
          <el-form :model="budgetForm" label-width="100px" inline>
            <el-form-item label="月份">
              <el-date-picker v-model="budgetForm.year_month" type="month" value-format="YYYY-MM" placeholder="选择月份" />
            </el-form-item>
            <el-form-item label="预算(kWh)">
              <el-input-number v-model="budgetForm.budget_kwh" :min="0" :precision="0" />
            </el-form-item>
            <el-form-item label="预算(元)">
              <el-input-number v-model="budgetForm.budget_yuan" :min="0" :precision="2" />
            </el-form-item>
            <el-form-item label="告警阈值(%)">
              <el-input-number v-model="budgetForm.threshold" :min="50" :max="100" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveBudget">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useAppStore } from '../stores/app'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)

const activeTab = ref('overview')
const selectedStoreId = ref(null)
const dateRange = ref([])

// Overview data
const overview = ref({})
const trendData = ref([])
const equipmentTypeData = ref([])

// Equipment data
const equipmentList = ref([])
const equipmentDialogVisible = ref(false)
const editingEquipment = ref(null)
const equipmentForm = reactive({
  equipment_code: '',
  name: '',
  type: 'hvac',
  rated_power_kw: 0,
  brand: '',
  model_no: '',
  installed_date: '',
})

// Analysis data
const peakHourData = ref([])
const weatherCorrelation = ref({ points: [], r_squared: 0 })
const salesCorrelation = ref({ points: [] })

// Scheduling data
const optimizing = ref(false)
const scheduleResults = ref([])
const scheduleSummary = ref({})
const currentSchedules = ref([])

// Alert data
const alertList = ref([])
const budgetUsage = ref({})
const budgetForm = reactive({
  year_month: '',
  budget_kwh: 10000,
  budget_yuan: 8000,
  threshold: 80,
})

// Computed chart options
const trendChartOption = computed(() => {
  const data = trendData.value || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['能耗(kWh)', '费用(元)'] },
    xAxis: { type: 'category', data: data.map(d => d.date) },
    yAxis: [
      { type: 'value', name: 'kWh', position: 'left' },
      { type: 'value', name: '元', position: 'right' },
    ],
    series: [
      { name: '能耗(kWh)', type: 'line', data: data.map(d => d.kwh), smooth: true },
      { name: '费用(元)', type: 'line', yAxisIndex: 1, data: data.map(d => d.cost), smooth: true, lineStyle: { type: 'dashed' } },
    ],
  }
})

const equipmentPieOption = computed(() => {
  const data = equipmentTypeData.value || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} kWh ({d}%)' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data.map(d => ({ name: d.type, value: d.total_kwh })),
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
    }],
  }
})

const peakHourChartOption = computed(() => {
  const data = peakHourData.value || []
  const peakHours = [8, 9, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21]
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map(d => `${d.hour}:00`), name: '时段' },
    yAxis: { type: 'value', name: '平均能耗(kWh)' },
    series: [{
      type: 'bar',
      data: data.map(d => ({
        value: d.avg_kwh,
        itemStyle: { color: peakHours.includes(d.hour) ? '#F56C6C' : '#67C23A' },
      })),
    }],
  }
})

const weatherCorrelationOption = computed(() => {
  const points = weatherCorrelation.value.points || []
  const r2 = weatherCorrelation.value.r_squared || 0
  return {
    tooltip: { trigger: 'item', formatter: (p) => `温度: ${p.data[0]}°C<br/>能耗: ${p.data[1]} kWh` },
    title: { text: `R² = ${r2.toFixed(4)}`, right: 10, top: 10, textStyle: { fontSize: 12, color: '#909399' } },
    xAxis: { type: 'value', name: '温度(°C)' },
    yAxis: { type: 'value', name: '能耗(kWh)' },
    series: [
      {
        type: 'scatter',
        data: points.map(p => [p.temperature, p.kwh]),
        symbolSize: 8,
      },
      {
        type: 'line',
        data: computeRegressionLine(points.map(p => [p.temperature, p.kwh])),
        smooth: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#E6A23C' },
      },
    ],
  }
})

const salesCorrelationOption = computed(() => {
  const points = salesCorrelation.value.points || []
  return {
    tooltip: { trigger: 'item', formatter: (p) => `营收: ${p.data[0]} 元<br/>能耗: ${p.data[1]} kWh` },
    xAxis: { type: 'value', name: '日营收(元)' },
    yAxis: { type: 'value', name: '日能耗(kWh)' },
    series: [{
      type: 'scatter',
      data: points.map(p => [p.revenue, p.kwh]),
      symbolSize: 8,
      itemStyle: { color: '#409EFF' },
    }],
  }
})

const budgetPercentage = computed(() => {
  if (!budgetUsage.value.budget_kwh) return 0
  return Math.min(100, Math.round((budgetUsage.value.current_kwh / budgetUsage.value.budget_kwh) * 100))
})

const budgetColor = computed(() => {
  const pct = budgetPercentage.value
  if (pct >= 90) return '#F56C6C'
  if (pct >= 70) return '#E6A23C'
  return '#67C23A'
})

// Helper functions
function computeRegressionLine(points) {
  if (!points.length) return []
  const n = points.length
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0
  points.forEach(([x, y]) => { sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x })
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
  const intercept = (sumY - slope * sumX) / n
  const xs = points.map(p => p[0]).sort((a, b) => a - b)
  const minX = xs[0]
  const maxX = xs[xs.length - 1]
  return [[minX, slope * minX + intercept], [maxX, slope * maxX + intercept]]
}

function statusTagType(status) {
  const map = { active: 'success', inactive: 'info', maintenance: 'warning' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { active: '运行中', inactive: '停用', maintenance: '维护中' }
  return map[status] || status
}

function alertLevelType(level) {
  const map = { critical: 'danger', warning: 'warning', info: 'info' }
  return map[level] || 'info'
}

function getParams() {
  const params = {}
  if (selectedStoreId.value) params.store_id = selectedStoreId.value
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

// API calls
async function fetchOverview() {
  try {
    const { data } = await api.get('/api/store-energy/overview', { params: getParams() })
    overview.value = data.summary || data
    trendData.value = data.trend || []
    equipmentTypeData.value = data.equipment_types || []
  } catch (e) { console.error('能耗概览加载失败', e) }
}

async function fetchEquipment() {
  try {
    const params = {}
    if (selectedStoreId.value) params.store_id = selectedStoreId.value
    const { data } = await api.get('/api/store-energy/equipment', { params })
    equipmentList.value = data
  } catch (e) { console.error('设备列表加载失败', e) }
}

async function fetchAnalysis() {
  try {
    const params = getParams()
    const [peakRes, weatherRes, salesRes] = await Promise.all([
      api.get('/api/store-energy/peak-hours', { params }),
      api.get('/api/store-energy/weather-correlation', { params }),
      api.get('/api/store-energy/sales-correlation', { params }),
    ])
    peakHourData.value = peakRes.data
    weatherCorrelation.value = weatherRes.data
    salesCorrelation.value = salesRes.data
  } catch (e) { console.error('能耗分析加载失败', e) }
}

async function fetchSchedules() {
  try {
    const params = {}
    if (selectedStoreId.value) params.store_id = selectedStoreId.value
    const { data } = await api.get('/api/store-energy/schedules', { params })
    currentSchedules.value = data
  } catch (e) { console.error('调度计划加载失败', e) }
}

async function generateSchedule() {
  optimizing.value = true
  try {
    const { data } = await api.post('/api/store-energy/optimize-schedule', { store_id: selectedStoreId.value })
    scheduleResults.value = data.recommendations || []
    scheduleSummary.value = {
      total_saving_kwh: data.total_saving_kwh || 0,
      total_saving_yuan: data.total_saving_yuan || 0,
    }
    ElMessage.success('优化方案已生成')
  } catch (e) {
    ElMessage.error('优化方案生成失败')
    console.error(e)
  } finally {
    optimizing.value = false
  }
}

async function fetchAlerts() {
  try {
    const params = {}
    if (selectedStoreId.value) params.store_id = selectedStoreId.value
    const { data } = await api.get('/api/store-energy/alerts', { params })
    alertList.value = data
  } catch (e) { console.error('告警列表加载失败', e) }
}

async function fetchBudget() {
  try {
    const params = {}
    if (selectedStoreId.value) params.store_id = selectedStoreId.value
    const { data } = await api.get('/api/store-energy/budget', { params })
    budgetUsage.value = data
  } catch (e) { console.error('预算数据加载失败', e) }
}

async function acknowledgeAlert(row) {
  try {
    await api.put(`/api/store-energy/alerts/${row.id}/acknowledge`)
    row.is_acknowledged = true
    ElMessage.success('告警已确认')
  } catch (e) { ElMessage.error('操作失败') }
}

async function saveBudget() {
  try {
    await api.post('/api/store-energy/budget', {
      store_id: selectedStoreId.value,
      ...budgetForm,
    })
    ElMessage.success('预算设置已保存')
    fetchBudget()
  } catch (e) { ElMessage.error('保存失败') }
}

function showEquipmentDialog(row) {
  editingEquipment.value = row
  if (row) {
    Object.assign(equipmentForm, {
      equipment_code: row.equipment_code,
      name: row.name,
      type: row.type,
      rated_power_kw: row.rated_power_kw,
      brand: row.brand,
      model_no: row.model_no,
      installed_date: row.installed_date,
    })
  } else {
    Object.assign(equipmentForm, {
      equipment_code: '',
      name: '',
      type: 'hvac',
      rated_power_kw: 0,
      brand: '',
      model_no: '',
      installed_date: '',
    })
  }
  equipmentDialogVisible.value = true
}

async function submitEquipment() {
  try {
    const payload = { ...equipmentForm, store_id: selectedStoreId.value }
    if (editingEquipment.value) {
      await api.put(`/api/store-energy/equipment/${editingEquipment.value.id}`, payload)
      ElMessage.success('设备已更新')
    } else {
      await api.post('/api/store-energy/equipment', payload)
      ElMessage.success('设备已添加')
    }
    equipmentDialogVisible.value = false
    fetchEquipment()
  } catch (e) { ElMessage.error('操作失败') }
}

function onTabChange(tab) {
  const name = tab.paneName
  if (name === 'overview') fetchOverview()
  else if (name === 'equipment') fetchEquipment()
  else if (name === 'analysis') fetchAnalysis()
  else if (name === 'scheduling') fetchSchedules()
  else if (name === 'alerts') { fetchAlerts(); fetchBudget() }
}

async function refreshData() {
  const name = activeTab.value
  if (name === 'overview') await fetchOverview()
  else if (name === 'equipment') await fetchEquipment()
  else if (name === 'analysis') await fetchAnalysis()
  else if (name === 'scheduling') await fetchSchedules()
  else if (name === 'alerts') { await fetchAlerts(); await fetchBudget() }
  ElMessage.success('数据已刷新')
}

watch([selectedStoreId, dateRange], () => {
  refreshData()
})

onMounted(() => {
  appStore.fetchStores()
  fetchOverview()
})
</script>

<style scoped>
.store-energy-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.filter-bar { display: flex; gap: 12px; align-items: center; }
.kpi-cards { display: flex; gap: 16px; flex-wrap: wrap; }
.kpi-card { flex: 1; min-width: 150px; text-align: center; }
.kpi-value { font-size: 26px; font-weight: bold; color: #303133; }
.kpi-value.red { color: #F56C6C; }
.kpi-value.green { color: #67C23A; }
.kpi-label { font-size: 13px; color: #909399; margin-top: 4px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.budget-progress { padding: 12px 0; }
.budget-info { display: flex; justify-content: space-between; color: #606266; font-size: 14px; }
.summary-row { font-size: 16px; color: #303133; }
</style>
