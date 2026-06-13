<template>
  <div class="supply-chain-container">
    <div class="page-header">
      <h2>供应链协同分析</h2>
      <el-button type="primary" @click="refreshData">刷新数据</el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-click="onTabChange">
      <el-tab-pane label="健康仪表盘" name="dashboard">
        <div class="kpi-cards">
          <el-card class="kpi-card">
            <div class="kpi-value">{{ dashboard.summary.total_suppliers || 0 }}</div>
            <div class="kpi-label">供应商总数</div>
          </el-card>
          <el-card class="kpi-card green">
            <div class="kpi-value">{{ dashboard.summary.green || 0 }}</div>
            <div class="kpi-label">健康 (≥80)</div>
          </el-card>
          <el-card class="kpi-card yellow">
            <div class="kpi-value">{{ dashboard.summary.yellow || 0 }}</div>
            <div class="kpi-label">预警 (60-79)</div>
          </el-card>
          <el-card class="kpi-card red">
            <div class="kpi-value">{{ dashboard.summary.red || 0 }}</div>
            <div class="kpi-label">异常 (<60)</div>
          </el-card>
        </div>

        <el-row :gutter="20" style="margin-top: 20px">
          <el-col :span="12">
            <el-card>
              <template #header>供应商健康度评分</template>
              <chart-panel ref="healthChart" :option="healthChartOption" height="350px" />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>准时交付率趋势</template>
              <chart-panel ref="trendChart" :option="trendChartOption" height="350px" />
            </el-card>
          </el-col>
        </el-row>

        <el-card style="margin-top: 20px">
          <template #header>供应商绩效明细</template>
          <el-table :data="dashboard.suppliers" stripe border>
            <el-table-column prop="supplier_name" label="供应商" width="150" />
            <el-table-column prop="on_time_rate" label="准时率(%)" width="100" sortable />
            <el-table-column prop="fulfillment_rate" label="履约率(%)" width="100" sortable />
            <el-table-column prop="quality_score" label="质量分" width="100" sortable />
            <el-table-column prop="overall_score" label="综合评分" width="100" sortable />
            <el-table-column label="健康度" width="100">
              <template #default="{ row }">
                <el-tag :type="healthTagType(row.health_level)">
                  {{ healthLabel(row.health_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total_orders" label="总订单" width="80" />
            <el-table-column prop="late_deliveries" label="延迟" width="80" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="采购订单" name="orders">
        <div class="toolbar">
          <el-select v-model="orderFilter.status" placeholder="状态筛选" clearable style="width: 120px">
            <el-option label="待确认" value="pending" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="运输中" value="shipped" />
            <el-option label="已交付" value="delivered" />
          </el-select>
          <el-button type="primary" @click="showCreateOrder = true">新建订单</el-button>
        </div>
        <el-table :data="orders" stripe border style="margin-top: 12px">
          <el-table-column prop="order_no" label="订单号" width="140" />
          <el-table-column prop="supplier_id" label="供应商ID" width="100" />
          <el-table-column prop="store_id" label="门店ID" width="90" />
          <el-table-column prop="order_date" label="下单日期" width="110" />
          <el-table-column prop="expected_delivery_date" label="预计到货" width="110" />
          <el-table-column prop="actual_delivery_date" label="实际到货" width="110" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="orderStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_amount" label="总金额" width="100" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="receiveOrder(row)" v-if="row.status !== 'delivered'">收货</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="缺货分析" name="stockout">
        <el-card>
          <template #header>缺货热点分析 (近30天)</template>
          <chart-panel ref="stockoutChart" :option="stockoutChartOption" height="400px" />
        </el-card>
        <el-table :data="stockoutData" stripe border style="margin-top: 12px">
          <el-table-column prop="store_id" label="门店ID" width="90" />
          <el-table-column prop="item_id" label="商品编码" width="120" />
          <el-table-column prop="item_name" label="商品名称" width="180" />
          <el-table-column prop="stockout_days" label="缺货天数" width="100" sortable />
          <el-table-column prop="total_days" label="统计天数" width="100" />
          <el-table-column prop="stockout_rate" label="缺货率(%)" width="110" sortable />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="调整建议" name="recommendations">
        <el-table :data="recommendations" stripe border>
          <el-table-column prop="store_id" label="门店ID" width="90" />
          <el-table-column prop="item_name" label="商品名称" width="180" />
          <el-table-column prop="current_stock" label="当前库存" width="100" />
          <el-table-column prop="recommended_action" label="建议操作" width="120">
            <template #default="{ row }">
              <el-tag :type="actionTagType(row.recommended_action)">
                {{ actionLabel(row.recommended_action) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="recommended_qty" label="建议数量" width="100" />
          <el-table-column prop="reason" label="原因" />
          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <el-tag :type="priorityType(row.priority)" size="small">{{ row.priority }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showCreateOrder" title="新建采购订单" width="600px">
      <el-form :model="newOrder" label-width="100px">
        <el-form-item label="供应商ID">
          <el-input-number v-model="newOrder.supplier_id" :min="1" />
        </el-form-item>
        <el-form-item label="门店ID">
          <el-input-number v-model="newOrder.store_id" :min="1" />
        </el-form-item>
        <el-form-item label="订单号">
          <el-input v-model="newOrder.order_no" />
        </el-form-item>
        <el-form-item label="下单日期">
          <el-date-picker v-model="newOrder.order_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="预计到货">
          <el-date-picker v-model="newOrder.expected_delivery_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateOrder = false">取消</el-button>
        <el-button type="primary" @click="submitOrder">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

const activeTab = ref('dashboard')
const dashboard = ref({ suppliers: [], summary: {} })
const orders = ref([])
const stockoutData = ref([])
const recommendations = ref([])
const showCreateOrder = ref(false)

const orderFilter = reactive({ status: '' })
const newOrder = reactive({
  supplier_id: null,
  store_id: null,
  order_no: '',
  order_date: '',
  expected_delivery_date: '',
  items: [{ item_id: 'ITEM001', item_name: '默认商品', quantity: 100, unit_cost: 10 }],
})

const healthChartOption = computed(() => {
  const suppliers = dashboard.value.suppliers || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: suppliers.map(s => s.supplier_name || `#${s.supplier_id}`), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', max: 100, name: '评分' },
    series: [{
      type: 'bar',
      data: suppliers.map(s => ({
        value: s.overall_score,
        itemStyle: { color: s.health_level === 'green' ? '#67C23A' : s.health_level === 'yellow' ? '#E6A23C' : '#F56C6C' }
      })),
    }],
  }
})

const trendChartOption = computed(() => {
  const suppliers = dashboard.value.suppliers || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: suppliers.map(s => s.supplier_name || `#${s.supplier_id}`) },
    yAxis: { type: 'value', max: 100, name: '%' },
    legend: { data: ['准时率', '履约率', '质量分'] },
    series: [
      { name: '准时率', type: 'bar', data: suppliers.map(s => s.on_time_rate) },
      { name: '履约率', type: 'bar', data: suppliers.map(s => s.fulfillment_rate) },
      { name: '质量分', type: 'bar', data: suppliers.map(s => s.quality_score) },
    ],
  }
})

const stockoutChartOption = computed(() => {
  const data = (stockoutData.value || []).slice(0, 20)
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map(d => d.item_name), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '缺货率(%)' },
    series: [{ type: 'bar', data: data.map(d => d.stockout_rate), itemStyle: { color: '#F56C6C' } }],
  }
})

function healthTagType(level) {
  return level === 'green' ? 'success' : level === 'yellow' ? 'warning' : 'danger'
}
function healthLabel(level) {
  return level === 'green' ? '健康' : level === 'yellow' ? '预警' : '异常'
}
function orderStatusType(status) {
  const map = { pending: 'info', confirmed: '', shipped: 'warning', delivered: 'success', cancelled: 'danger' }
  return map[status] || 'info'
}
function actionTagType(action) {
  return action === 'urgent_replenish' ? 'danger' : action === 'replenish' ? 'warning' : 'info'
}
function actionLabel(action) {
  const map = { urgent_replenish: '紧急补货', replenish: '补货', monitor: '监控' }
  return map[action] || action
}
function priorityType(p) {
  return p === 'critical' ? 'danger' : p === 'high' ? 'warning' : 'info'
}

async function fetchDashboard() {
  try {
    const { data } = await api.get('/api/supply-chain/health-dashboard')
    dashboard.value = data
  } catch (e) { console.error(e) }
}

async function fetchOrders() {
  try {
    const params = {}
    if (orderFilter.status) params.status = orderFilter.status
    const { data } = await api.get('/api/supply-chain/orders', { params })
    orders.value = data
  } catch (e) { console.error(e) }
}

async function fetchStockout() {
  try {
    const { data } = await api.get('/api/supply-chain/stockout-analysis')
    stockoutData.value = data
  } catch (e) { console.error(e) }
}

async function fetchRecommendations() {
  try {
    const { data } = await api.get('/api/supply-chain/recommendations')
    recommendations.value = data
  } catch (e) { console.error(e) }
}

async function refreshData() {
  await Promise.all([fetchDashboard(), fetchOrders(), fetchStockout(), fetchRecommendations()])
  ElMessage.success('数据已刷新')
}

function onTabChange(tab) {
  if (tab.paneName === 'orders') fetchOrders()
  else if (tab.paneName === 'stockout') fetchStockout()
  else if (tab.paneName === 'recommendations') fetchRecommendations()
}

async function submitOrder() {
  try {
    await api.post('/api/supply-chain/orders', newOrder)
    ElMessage.success('订单创建成功')
    showCreateOrder.value = false
    fetchOrders()
  } catch (e) { ElMessage.error('创建失败') }
}

async function receiveOrder(row) {
  try {
    await api.put(`/api/supply-chain/orders/${row.id}/receive`, {
      actual_delivery_date: new Date().toISOString().split('T')[0],
      items: [],
    })
    ElMessage.success('收货确认成功')
    fetchOrders()
  } catch (e) { ElMessage.error('操作失败') }
}

onMounted(() => {
  fetchDashboard()
  fetchOrders()
})
</script>

<style scoped>
.supply-chain-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.kpi-cards { display: flex; gap: 16px; }
.kpi-card { flex: 1; text-align: center; }
.kpi-value { font-size: 28px; font-weight: bold; color: #303133; }
.kpi-label { font-size: 14px; color: #909399; margin-top: 4px; }
.kpi-card.green .kpi-value { color: #67C23A; }
.kpi-card.yellow .kpi-value { color: #E6A23C; }
.kpi-card.red .kpi-value { color: #F56C6C; }
.toolbar { display: flex; gap: 12px; align-items: center; }
</style>
