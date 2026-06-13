<template>
  <div class="replenishment-container">
    <div class="page-header">
      <h2>智能补货建议</h2>
      <div class="header-actions">
        <el-select v-model="selectedStore" placeholder="选择门店" style="width: 180px" @change="refreshData">
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-button type="primary" @click="generateSuggestions" :loading="generating">生成补货建议</el-button>
      </div>
    </div>

    <div class="kpi-cards">
      <el-card class="kpi-card">
        <div class="kpi-value danger">{{ dashboardData.items_below_rop }}</div>
        <div class="kpi-label">低于补货点</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.coverage_rate }}%</div>
        <div class="kpi-label">库存覆盖率</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value warning">¥{{ dashboardData.pending_orders_value?.toLocaleString() }}</div>
        <div class="kpi-label">待处理订单金额</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.pending_count }}</div>
        <div class="kpi-label">待审批建议</div>
      </el-card>
    </div>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>补货时间线</template>
          <chart-panel ref="timelineChart" :option="timelineOption" height="300px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>补货建议列表</span>
          <el-radio-group v-model="statusFilter" @change="fetchSuggestions" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="pending">待审批</el-radio-button>
            <el-radio-button label="approved">已批准</el-radio-button>
            <el-radio-button label="ordered">已下单</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="suggestions" stripe border>
        <el-table-column prop="item_name" label="商品名称" width="160" />
        <el-table-column prop="item_id" label="编码" width="100" />
        <el-table-column prop="current_stock" label="当前库存" width="90" />
        <el-table-column prop="safety_stock" label="安全库存" width="90" />
        <el-table-column prop="reorder_point" label="补货点" width="80" />
        <el-table-column prop="suggested_qty" label="建议数量" width="90">
          <template #default="{ row }">
            <span class="qty-highlight">{{ row.suggested_qty }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="optimal_order_date" label="建议下单日" width="110" />
        <el-table-column prop="estimated_cost" label="预估成本" width="100">
          <template #default="{ row }">¥{{ row.estimated_cost?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="demand_velocity" label="日均需求" width="90" />
        <el-table-column label="批量优惠" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.bulk_discount_applied" type="success" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="approveSuggestion(row)" v-if="row.status === 'pending'">批准</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAppStore } from '../stores/app'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)
const selectedStore = ref(null)
const statusFilter = ref('')
const generating = ref(false)
const suggestions = ref([])
const timeline = ref([])
const dashboardData = ref({
  items_below_rop: 0,
  coverage_rate: 0,
  pending_orders_value: 0,
  pending_count: 0,
  approved_count: 0,
})

const timelineOption = computed(() => {
  const items = timeline.value
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['当前库存', '日均消耗', '缺货天数'] },
    xAxis: { type: 'category', data: items.map(i => i.item_name), axisLabel: { rotate: 30 } },
    yAxis: [
      { type: 'value', name: '数量' },
      { type: 'value', name: '天数', position: 'right' },
    ],
    series: [
      { name: '当前库存', type: 'bar', data: items.map(i => i.current_stock) },
      { name: '日均消耗', type: 'bar', data: items.map(i => i.daily_consumption) },
      { name: '缺货天数', type: 'line', yAxisIndex: 1, data: items.map(i => i.days_until_stockout), itemStyle: { color: '#F56C6C' } },
    ],
  }
})

function statusType(s) {
  const map = { pending: 'warning', approved: 'success', ordered: '', completed: 'info' }
  return map[s] || 'info'
}
function statusLabel(s) {
  const map = { pending: '待审批', approved: '已批准', ordered: '已下单', completed: '已完成' }
  return map[s] || s
}

async function fetchDashboard() {
  try {
    const { data } = await api.get('/api/replenishment/dashboard')
    dashboardData.value = data
  } catch (e) { console.error(e) }
}

async function fetchSuggestions() {
  try {
    const params = { page_size: 50 }
    if (selectedStore.value) params.store_id = selectedStore.value
    if (statusFilter.value) params.status_filter = statusFilter.value
    const { data } = await api.get('/api/replenishment/suggestions', { params })
    suggestions.value = data
  } catch (e) { console.error(e) }
}

async function fetchTimeline() {
  if (!selectedStore.value) return
  try {
    const { data } = await api.get('/api/replenishment/timeline', {
      params: { store_id: selectedStore.value }
    })
    timeline.value = data
  } catch (e) { console.error(e) }
}

async function generateSuggestions() {
  if (!selectedStore.value) {
    ElMessage.warning('请先选择门店')
    return
  }
  generating.value = true
  try {
    const { data } = await api.post('/api/replenishment/suggestions/generate', {
      store_id: selectedStore.value,
    })
    ElMessage.success(data.message)
    await fetchSuggestions()
    await fetchTimeline()
  } catch (e) { ElMessage.error('生成失败') }
  finally { generating.value = false }
}

async function approveSuggestion(row) {
  try {
    await api.put(`/api/replenishment/suggestions/${row.id}/approve`)
    ElMessage.success('已批准')
    row.status = 'approved'
  } catch (e) { ElMessage.error('操作失败') }
}

function refreshData() {
  fetchDashboard()
  fetchSuggestions()
  fetchTimeline()
}

onMounted(() => {
  fetchDashboard()
  fetchSuggestions()
  if (stores.value.length > 0) {
    selectedStore.value = stores.value[0].id
    fetchTimeline()
  }
})
</script>

<style scoped>
.replenishment-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-actions { display: flex; gap: 12px; }
.kpi-cards { display: flex; gap: 16px; }
.kpi-card { flex: 1; text-align: center; }
.kpi-value { font-size: 28px; font-weight: bold; color: #303133; }
.kpi-value.danger { color: #F56C6C; }
.kpi-value.warning { color: #E6A23C; }
.kpi-label { font-size: 14px; color: #909399; margin-top: 4px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.qty-highlight { font-weight: bold; color: #409EFF; }
</style>
