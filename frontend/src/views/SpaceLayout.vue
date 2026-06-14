<template>
  <div class="space-layout-container">
    <!-- Filter bar -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select v-model="selectedStoreId" placeholder="选择门店" @change="handleStoreChange">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="refreshData"
          />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" :icon="Refresh" @click="refreshData">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Tabs -->
    <el-card style="margin-top: 16px">
      <el-tabs v-model="activeTab">
        <!-- Tab 1: 区域管理 -->
        <el-tab-pane label="区域管理" name="zones">
          <div class="tab-toolbar">
            <el-button type="primary" @click="openAddZoneDialog">+ 新增区域</el-button>
          </div>
          <el-table :data="zones" stripe border v-loading="zonesLoading" empty-text="暂无区域数据">
            <el-table-column prop="zone_code" label="区域编号" width="120" />
            <el-table-column prop="zone_name" label="区域名称" width="140" />
            <el-table-column prop="zone_type" label="区域类型" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ zoneTypeLabel(row.zone_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="area_sqm" label="面积(㎡)" width="100" />
            <el-table-column prop="category_assignment" label="品类分配" min-width="140" />
            <el-table-column prop="floor" label="楼层" width="80" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="openEditZoneDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="deleteZone(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 2: 区域绩效 -->
        <el-tab-pane label="区域绩效" name="kpis">
          <div class="kpi-cards">
            <el-card class="kpi-card">
              <div class="kpi-value">{{ kpiSummary.total_zones }}</div>
              <div class="kpi-label">区域总数</div>
            </el-card>
            <el-card class="kpi-card">
              <div class="kpi-value">{{ kpiSummary.total_area }} ㎡</div>
              <div class="kpi-label">总面积</div>
            </el-card>
            <el-card class="kpi-card">
              <div class="kpi-value highlight">¥{{ kpiSummary.avg_revenue_per_sqm?.toFixed(2) }}</div>
              <div class="kpi-label">平均坪效(元/㎡)</div>
            </el-card>
            <el-card class="kpi-card">
              <div class="kpi-value success">{{ kpiSummary.top_zone_name }}</div>
              <div class="kpi-label">最佳绩效区域</div>
            </el-card>
          </div>
          <el-table
            :data="kpiData"
            stripe
            border
            v-loading="kpiLoading"
            style="margin-top: 16px"
            :default-sort="{ prop: 'revenue_per_sqm', order: 'descending' }"
          >
            <el-table-column prop="zone_name" label="区域名称" width="140" />
            <el-table-column prop="zone_type" label="区域类型" width="120">
              <template #default="{ row }">{{ zoneTypeLabel(row.zone_type) }}</template>
            </el-table-column>
            <el-table-column prop="area_sqm" label="面积(㎡)" width="100" sortable />
            <el-table-column prop="revenue" label="营收(元)" width="120" sortable>
              <template #default="{ row }">¥{{ row.revenue?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column prop="transaction_count" label="交易次数" width="100" sortable />
            <el-table-column prop="revenue_per_sqm" label="坪效(元/㎡)" width="130" sortable>
              <template #default="{ row }">
                <span class="highlight-value">¥{{ row.revenue_per_sqm?.toFixed(2) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="items_per_sqm" label="商品密度(/㎡)" width="130" sortable />
            <el-table-column prop="traffic_conversion" label="转化率(%)" width="110" sortable>
              <template #default="{ row }">{{ (row.traffic_conversion * 100)?.toFixed(1) }}%</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 3: 销售热力图 -->
        <el-tab-pane label="销售热力图" name="heatmap">
          <div v-loading="heatmapLoading" class="heatmap-wrapper">
            <chart-panel :option="heatmapOption" height="500px" />
          </div>
        </el-tab-pane>

        <!-- Tab 4: 趋势分析 -->
        <el-tab-pane label="趋势分析" name="trend">
          <div class="trend-toolbar">
            <el-select v-model="selectedZoneId" placeholder="选择区域" style="width: 200px" @change="fetchTrend">
              <el-option v-for="z in zones" :key="z.id" :label="z.zone_name" :value="z.id" />
            </el-select>
          </div>
          <div v-loading="trendLoading">
            <chart-panel :option="trendOption" height="380px" />
          </div>
        </el-tab-pane>

        <!-- Tab 5: 优化建议 -->
        <el-tab-pane label="优化建议" name="recommendations">
          <div class="tab-toolbar">
            <el-button type="primary" @click="fetchRecommendations" :loading="recsLoading">刷新建议</el-button>
          </div>
          <div v-if="recommendations.length === 0 && !recsLoading" class="empty-state">
            <el-empty description="暂无优化建议" />
          </div>
          <el-row :gutter="16" v-else>
            <el-col :span="8" v-for="rec in recommendations" :key="rec.id" style="margin-bottom: 16px">
              <el-card shadow="hover" class="rec-card">
                <template #header>
                  <div class="rec-header">
                    <span class="rec-zone">{{ rec.zone_name }}</span>
                    <el-tag :type="priorityTagType(rec.priority)" size="small">
                      {{ priorityLabel(rec.priority) }}
                    </el-tag>
                  </div>
                </template>
                <div class="rec-body">
                  <p class="rec-issue"><strong>问题：</strong>{{ rec.issue }}</p>
                  <p class="rec-suggestion"><strong>建议：</strong>{{ rec.suggestion }}</p>
                  <p class="rec-impact"><strong>预估影响：</strong>{{ rec.estimated_impact }}</p>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Zone Form Dialog -->
    <el-dialog
      v-model="zoneDialogVisible"
      :title="isEditMode ? '编辑区域' : '新增区域'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="zoneForm" :rules="zoneRules" ref="zoneFormRef" label-width="100px">
        <el-form-item label="区域编号" prop="zone_code">
          <el-input v-model="zoneForm.zone_code" placeholder="如: Z001" />
        </el-form-item>
        <el-form-item label="区域名称" prop="zone_name">
          <el-input v-model="zoneForm.zone_name" placeholder="如: 生鲜区" />
        </el-form-item>
        <el-form-item label="面积(㎡)" prop="area_sqm">
          <el-input-number v-model="zoneForm.area_sqm" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="区域类型" prop="zone_type">
          <el-select v-model="zoneForm.zone_type" placeholder="选择类型" style="width: 100%">
            <el-option label="销售区" value="sales" />
            <el-option label="促销区" value="promotion" />
            <el-option label="仓储区" value="storage" />
            <el-option label="通道" value="aisle" />
            <el-option label="收银区" value="checkout" />
            <el-option label="服务区" value="service" />
          </el-select>
        </el-form-item>
        <el-form-item label="品类分配" prop="category_assignment">
          <el-input v-model="zoneForm.category_assignment" placeholder="如: 水果、蔬菜" />
        </el-form-item>
        <el-form-item label="楼层" prop="floor">
          <el-input-number v-model="zoneForm.floor" :min="-2" :max="20" style="width: 100%" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="X坐标" prop="position_x">
              <el-input-number v-model="zoneForm.position_x" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Y坐标" prop="position_y">
              <el-input-number v-model="zoneForm.position_y" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="宽度" prop="width">
              <el-input-number v-model="zoneForm.width" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="高度" prop="height">
              <el-input-number v-model="zoneForm.height" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="zoneDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitZoneForm" :loading="zoneSubmitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)

// --- State ---
const selectedStoreId = ref(null)
const dateRange = ref([])
const activeTab = ref('zones')

// Zone management
const zones = ref([])
const zonesLoading = ref(false)
const zoneDialogVisible = ref(false)
const isEditMode = ref(false)
const zoneSubmitting = ref(false)
const zoneFormRef = ref(null)
const editingZoneId = ref(null)

const zoneForm = reactive({
  zone_code: '',
  zone_name: '',
  area_sqm: 0,
  zone_type: '',
  category_assignment: '',
  floor: 1,
  position_x: 0,
  position_y: 0,
  width: 0,
  height: 0,
})

const zoneRules = {
  zone_code: [{ required: true, message: '请输入区域编号', trigger: 'blur' }],
  zone_name: [{ required: true, message: '请输入区域名称', trigger: 'blur' }],
  area_sqm: [{ required: true, message: '请输入面积', trigger: 'blur' }],
  zone_type: [{ required: true, message: '请选择区域类型', trigger: 'change' }],
}

// KPI
const kpiData = ref([])
const kpiLoading = ref(false)
const kpiSummary = computed(() => {
  const data = kpiData.value
  if (!data.length) return { total_zones: 0, total_area: 0, avg_revenue_per_sqm: 0, top_zone_name: '-' }
  const totalArea = data.reduce((sum, z) => sum + (z.area_sqm || 0), 0)
  const totalRevenue = data.reduce((sum, z) => sum + (z.revenue || 0), 0)
  const topZone = [...data].sort((a, b) => (b.revenue_per_sqm || 0) - (a.revenue_per_sqm || 0))[0]
  return {
    total_zones: data.length,
    total_area: totalArea.toFixed(1),
    avg_revenue_per_sqm: totalArea > 0 ? totalRevenue / totalArea : 0,
    top_zone_name: topZone?.zone_name || '-',
  }
})

// Heatmap
const heatmapData = ref({ plan_width: 100, plan_height: 100, cells: [] })
const heatmapLoading = ref(false)

const heatmapOption = computed(() => {
  const items = heatmapData.value.cells || []
  if (!items.length) return {}
  const maxIntensity = Math.max(...items.map(d => d.intensity || 0), 1)

  // Use authoritative floor plan dimensions from backend
  const planWidth = heatmapData.value.plan_width || 100
  const planHeight = heatmapData.value.plan_height || 100

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const d = params.data
        return `${d.zone_name}<br/>营收: ¥${d.revenue?.toLocaleString() || 0}<br/>强度: ${d.intensity?.toFixed(2)}`
      },
    },
    visualMap: {
      min: 0,
      max: maxIntensity,
      inRange: { color: ['#313695', '#4575b4', '#74add1', '#fee090', '#f46d43', '#d73027', '#a50026'] },
      text: ['高', '低'],
      calculable: true,
      orient: 'vertical',
      right: 10,
      top: 'center',
    },
    series: [{
      type: 'custom',
      coordinateSystem: undefined,
      renderItem: (params, bindApi) => {
        const item = items[params.dataIndex]
        if (!item) return null
        const chartWidth = bindApi.getWidth()
        const chartHeight = bindApi.getHeight()
        // Reserve padding (5% each side) so zones don't clip at edges
        const pad = 0.05
        const drawWidth = chartWidth * (1 - 2 * pad)
        const drawHeight = chartHeight * (1 - 2 * pad)
        const offsetX = chartWidth * pad
        const offsetY = chartHeight * pad
        // Map zone coordinates using floor plan physical dimensions
        // preserving aspect ratio
        const scaleX = drawWidth / planWidth
        const scaleY = drawHeight / planHeight
        const uniformScale = Math.min(scaleX, scaleY)
        const shiftX = (drawWidth - planWidth * uniformScale) / 2
        const shiftY = (drawHeight - planHeight * uniformScale) / 2
        return {
          type: 'rect',
          shape: {
            x: offsetX + shiftX + (item.position_x || 0) * uniformScale,
            y: offsetY + shiftY + (item.position_y || 0) * uniformScale,
            width: (item.width || 1) * uniformScale,
            height: (item.height || 1) * uniformScale,
          },
          style: {
            fill: bindApi.visual('color'),
            stroke: '#fff',
            lineWidth: 1,
          },
        }
      },
      data: items.map(d => ({
        value: d.intensity || 0,
        zone_name: d.zone_name,
        revenue: d.revenue,
        intensity: d.intensity,
        position_x: d.position_x,
        position_y: d.position_y,
        width: d.width,
        height: d.height,
      })),
    }],
  }
})

// Trend
const selectedZoneId = ref(null)
const trendData = ref([])
const trendLoading = ref(false)

const trendOption = computed(() => {
  const data = trendData.value
  if (!data.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['坪效(元/㎡)', '营收(元)', '交易次数', '商品销量'] },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLabel: { rotate: 30 },
    },
    yAxis: [
      { type: 'value', name: '金额(元)' },
      { type: 'value', name: '数量', position: 'right' },
    ],
    series: [
      { name: '坪效(元/㎡)', type: 'line', data: data.map(d => d.revenue_per_sqm), smooth: true },
      { name: '营收(元)', type: 'line', data: data.map(d => d.revenue), smooth: true },
      { name: '交易次数', type: 'line', yAxisIndex: 1, data: data.map(d => d.transaction_count), smooth: true },
      { name: '商品销量', type: 'line', yAxisIndex: 1, data: data.map(d => d.items_sold), smooth: true },
    ],
  }
})

// Recommendations
const recommendations = ref([])
const recsLoading = ref(false)

// --- Helpers ---
function zoneTypeLabel(type) {
  const map = { sales: '销售区', promotion: '促销区', storage: '仓储区', aisle: '通道', checkout: '收银区', service: '服务区' }
  return map[type] || type
}

function priorityTagType(priority) {
  const map = { high: 'danger', medium: 'warning', low: 'success' }
  return map[priority] || 'info'
}

function priorityLabel(priority) {
  const map = { high: '高优先级', medium: '中优先级', low: '低优先级' }
  return map[priority] || priority
}

function getDateParams() {
  const params = {}
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

// --- API Calls ---
async function fetchZones() {
  if (!selectedStoreId.value) return
  zonesLoading.value = true
  try {
    const { data } = await api.get('/api/space-layout/zones', {
      params: { store_id: selectedStoreId.value },
    })
    zones.value = data
  } catch (e) {
    ElMessage.error('加载区域数据失败')
  } finally {
    zonesLoading.value = false
  }
}

async function fetchKPIs() {
  if (!selectedStoreId.value) return
  kpiLoading.value = true
  try {
    const { data } = await api.get('/api/space-layout/kpis', {
      params: { store_id: selectedStoreId.value, ...getDateParams() },
    })
    kpiData.value = data
  } catch (e) {
    ElMessage.error('加载绩效数据失败')
  } finally {
    kpiLoading.value = false
  }
}

async function fetchHeatmap() {
  if (!selectedStoreId.value) return
  heatmapLoading.value = true
  try {
    const { data } = await api.get('/api/space-layout/heatmap', {
      params: { store_id: selectedStoreId.value, ...getDateParams() },
    })
    heatmapData.value = data
  } catch (e) {
    ElMessage.error('加载热力图数据失败')
  } finally {
    heatmapLoading.value = false
  }
}

async function fetchTrend() {
  if (!selectedStoreId.value || !selectedZoneId.value) return
  trendLoading.value = true
  try {
    const { data } = await api.get('/api/space-layout/trend', {
      params: { store_id: selectedStoreId.value, zone_id: selectedZoneId.value, ...getDateParams() },
    })
    trendData.value = data
  } catch (e) {
    ElMessage.error('加载趋势数据失败')
  } finally {
    trendLoading.value = false
  }
}

async function fetchRecommendations() {
  if (!selectedStoreId.value) return
  recsLoading.value = true
  try {
    const { data } = await api.get('/api/space-layout/recommendations', {
      params: { store_id: selectedStoreId.value, ...getDateParams() },
    })
    recommendations.value = data
  } catch (e) {
    ElMessage.error('加载优化建议失败')
  } finally {
    recsLoading.value = false
  }
}

// --- Zone CRUD ---
function resetZoneForm() {
  Object.assign(zoneForm, {
    zone_code: '',
    zone_name: '',
    area_sqm: 0,
    zone_type: '',
    category_assignment: '',
    floor: 1,
    position_x: 0,
    position_y: 0,
    width: 0,
    height: 0,
  })
}

function openAddZoneDialog() {
  isEditMode.value = false
  editingZoneId.value = null
  resetZoneForm()
  zoneDialogVisible.value = true
}

function openEditZoneDialog(row) {
  isEditMode.value = true
  editingZoneId.value = row.id
  Object.assign(zoneForm, {
    zone_code: row.zone_code,
    zone_name: row.zone_name,
    area_sqm: row.area_sqm,
    zone_type: row.zone_type,
    category_assignment: row.category_assignment,
    floor: row.floor,
    position_x: row.position_x || 0,
    position_y: row.position_y || 0,
    width: row.width || 0,
    height: row.height || 0,
  })
  zoneDialogVisible.value = true
}

async function submitZoneForm() {
  if (!zoneFormRef.value) return
  await zoneFormRef.value.validate()
  zoneSubmitting.value = true
  try {
    const payload = { ...zoneForm, store_id: selectedStoreId.value }
    if (isEditMode.value) {
      await api.put(`/api/space-layout/zones/${editingZoneId.value}`, payload)
      ElMessage.success('区域更新成功')
    } else {
      await api.post('/api/space-layout/zones', payload)
      ElMessage.success('区域创建成功')
    }
    zoneDialogVisible.value = false
    await fetchZones()
  } catch (e) {
    ElMessage.error(isEditMode.value ? '更新失败' : '创建失败')
  } finally {
    zoneSubmitting.value = false
  }
}

async function deleteZone(row) {
  try {
    await ElMessageBox.confirm(`确定删除区域"${row.zone_name}"吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await api.delete(`/api/space-layout/zones/${row.id}`)
    ElMessage.success('删除成功')
    await fetchZones()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// --- Actions ---
function handleStoreChange() {
  refreshData()
}

function refreshData() {
  fetchZones()
  fetchKPIs()
  fetchHeatmap()
  fetchRecommendations()
  if (selectedZoneId.value) {
    fetchTrend()
  }
}

// --- Watchers ---
watch(activeTab, (tab) => {
  if (tab === 'kpis' && kpiData.value.length === 0) fetchKPIs()
  if (tab === 'heatmap' && (!heatmapData.value.cells || heatmapData.value.cells.length === 0)) fetchHeatmap()
  if (tab === 'recommendations' && recommendations.value.length === 0) fetchRecommendations()
})

// --- Init ---
onMounted(() => {
  appStore.fetchStores()
  if (stores.value.length > 0) {
    selectedStoreId.value = stores.value[0].id
    refreshData()
  } else {
    const unwatch = watch(stores, (newStores) => {
      if (newStores.length > 0) {
        selectedStoreId.value = newStores[0].id
        refreshData()
        unwatch()
      }
    })
  }
})
</script>

<style scoped>
.space-layout-container {
  padding: 20px;
}

.filter-card .el-row {
  align-items: center;
}

.tab-toolbar {
  margin-bottom: 16px;
}

.kpi-cards {
  display: flex;
  gap: 16px;
}

.kpi-card {
  flex: 1;
  text-align: center;
}

.kpi-value {
  font-size: 26px;
  font-weight: bold;
  color: #303133;
}

.kpi-value.highlight {
  color: #409EFF;
}

.kpi-value.success {
  color: #67C23A;
}

.kpi-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.highlight-value {
  font-weight: bold;
  color: #409EFF;
}

.heatmap-wrapper {
  min-height: 500px;
}

.trend-toolbar {
  margin-bottom: 16px;
}

.rec-card {
  height: 100%;
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rec-zone {
  font-weight: bold;
}

.rec-body p {
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.5;
  color: #606266;
}

.rec-issue {
  color: #F56C6C !important;
}

.rec-suggestion {
  color: #409EFF !important;
}

.rec-impact {
  color: #67C23A !important;
}

.empty-state {
  padding: 40px 0;
  text-align: center;
}
</style>
