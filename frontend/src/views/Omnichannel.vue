<template>
  <div class="omnichannel-container">
    <div class="page-header">
      <h2>全渠道经营分析</h2>
      <div class="filter-bar">
        <el-select v-model="selectedStoreId" placeholder="选择门店" style="width: 180px" clearable>
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-select v-model="channelFilter" placeholder="渠道" style="width: 120px">
          <el-option label="全部" value="all" />
          <el-option label="线上" value="online" />
          <el-option label="线下" value="offline" />
          <el-option label="O2O" value="o2o" />
        </el-select>
        <el-select v-model="attributionModel" placeholder="归因模型" style="width: 150px">
          <el-option label="末次触点" value="last_touch" />
          <el-option label="首次触点" value="first_touch" />
          <el-option label="线性归因" value="linear" />
          <el-option label="时间衰减" value="time_decay" />
        </el-select>
        <el-button type="primary" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <!-- Row 1: Channel KPI Cards -->
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="channel-card online">
          <template #header><span class="channel-title online-title">线上渠道</span></template>
          <div class="channel-kpis">
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.online.gmv) }}</div>
              <div class="channel-kpi-label">GMV(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.online.order_count || 0 }}</div>
              <div class="channel-kpi-label">订单数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.online.avg_order_value) }}</div>
              <div class="channel-kpi-label">客单价(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.online.member_count || 0 }}</div>
              <div class="channel-kpi-label">会员数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value" :class="channelKpi.online.growth_rate >= 0 ? 'positive' : 'negative'">
                {{ channelKpi.online.growth_rate?.toFixed(1) || 0 }}%
              </div>
              <div class="channel-kpi-label">增速</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="channel-card offline">
          <template #header><span class="channel-title offline-title">线下渠道</span></template>
          <div class="channel-kpis">
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.offline.gmv) }}</div>
              <div class="channel-kpi-label">GMV(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.offline.order_count || 0 }}</div>
              <div class="channel-kpi-label">订单数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.offline.avg_order_value) }}</div>
              <div class="channel-kpi-label">客单价(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.offline.member_count || 0 }}</div>
              <div class="channel-kpi-label">会员数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value" :class="channelKpi.offline.growth_rate >= 0 ? 'positive' : 'negative'">
                {{ channelKpi.offline.growth_rate?.toFixed(1) || 0 }}%
              </div>
              <div class="channel-kpi-label">增速</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="channel-card o2o">
          <template #header><span class="channel-title o2o-title">O2O渠道</span></template>
          <div class="channel-kpis">
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.o2o.gmv) }}</div>
              <div class="channel-kpi-label">GMV(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.o2o.order_count || 0 }}</div>
              <div class="channel-kpi-label">订单数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ formatNumber(channelKpi.o2o.avg_order_value) }}</div>
              <div class="channel-kpi-label">客单价(元)</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value">{{ channelKpi.o2o.member_count || 0 }}</div>
              <div class="channel-kpi-label">会员数</div>
            </div>
            <div class="channel-kpi">
              <div class="channel-kpi-value" :class="channelKpi.o2o.growth_rate >= 0 ? 'positive' : 'negative'">
                {{ channelKpi.o2o.growth_rate?.toFixed(1) || 0 }}%
              </div>
              <div class="channel-kpi-label">增速</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 2: Charts Row -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>渠道GMV趋势</template>
          <chart-panel :option="channelTrendOption" height="350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>渠道GMV占比</template>
          <chart-panel :option="channelShareOption" height="350px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 3: Analysis -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>转化漏斗</template>
          <chart-panel :option="funnelOption" height="350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>渠道归因分析</template>
          <chart-panel :option="attributionOption" height="350px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 4: Member Insights -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>会员渠道分布</template>
          <chart-panel :option="memberOverlapOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>统一会员指标</template>
          <el-table :data="memberStats" stripe border size="small">
            <el-table-column prop="channel" label="渠道" width="100" />
            <el-table-column prop="member_count" label="会员数" width="100" />
            <el-table-column prop="avg_frequency" label="平均频次" width="100" />
            <el-table-column prop="avg_spend" label="平均消费(元)" width="120" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 5: Inventory (collapsible) -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="inventory-header" @click="inventoryCollapsed = !inventoryCollapsed" style="cursor: pointer">
          <span>库存全渠道视图</span>
          <el-icon><component :is="inventoryCollapsed ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
        </div>
      </template>
      <div v-show="!inventoryCollapsed">
        <div style="margin-bottom: 12px">
          <el-select v-model="inventoryStoreId" placeholder="选择门店" style="width: 200px" @change="fetchInventory">
            <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </div>
        <el-table :data="inventoryData" stripe border size="small">
          <el-table-column prop="item_id" label="商品编号" width="120" />
          <el-table-column prop="online_available" label="线上可用" width="100" />
          <el-table-column prop="offline_available" label="线下可用" width="100" />
          <el-table-column prop="online_reserved" label="线上预留" width="100" />
          <el-table-column prop="offline_reserved" label="线下预留" width="100" />
          <el-table-column prop="total" label="总计" width="100" />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import api from '../api'
import { useAppStore } from '../stores/app'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)

const selectedStoreId = ref(null)
const dateRange = ref([])
const channelFilter = ref('all')
const attributionModel = ref('last_touch')

// Data
const channelKpi = ref({
  online: {},
  offline: {},
  o2o: {},
})
const trendData = ref([])
const shareData = ref([])
const funnelData = ref([])
const attributionData = ref([])
const memberOverlap = ref({ online_only: 0, offline_only: 0, both: 0 })
const memberStats = ref([])
const inventoryData = ref([])
const inventoryStoreId = ref(null)
const inventoryCollapsed = ref(true)

// Helpers
function formatNumber(val) {
  if (!val) return '0'
  if (val >= 10000) return (val / 10000).toFixed(2) + '万'
  return val.toFixed(2)
}

function getParams() {
  const params = {}
  if (selectedStoreId.value) params.store_id = selectedStoreId.value
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  if (channelFilter.value && channelFilter.value !== 'all') params.channel = channelFilter.value
  params.attribution_model = attributionModel.value
  return params
}

// Chart Options
const channelTrendOption = computed(() => {
  const data = trendData.value || []
  const dates = [...new Set(data.map(d => d.date))].sort()
  const channels = { online: '线上', offline: '线下', o2o: 'O2O' }
  const colors = { online: '#409EFF', offline: '#67C23A', o2o: '#9B59B6' }
  const series = Object.entries(channels).map(([key, name]) => ({
    name,
    type: 'line',
    smooth: true,
    data: dates.map(date => {
      const item = data.find(d => d.date === date && d.channel === key)
      return item ? item.gmv : 0
    }),
    lineStyle: { color: colors[key] },
    itemStyle: { color: colors[key] },
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: Object.values(channels) },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'GMV(元)' },
    series,
  }
})

const channelShareOption = computed(() => {
  const data = shareData.value || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 元 ({d}%)' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data.map(d => ({
        name: d.channel === 'online' ? '线上' : d.channel === 'offline' ? '线下' : 'O2O',
        value: d.gmv,
        itemStyle: { color: d.channel === 'online' ? '#409EFF' : d.channel === 'offline' ? '#67C23A' : '#9B59B6' },
      })),
    }],
  }
})

const funnelOption = computed(() => {
  const data = funnelData.value || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}' },
    series: [{
      type: 'funnel',
      left: '10%',
      top: 60,
      bottom: 60,
      width: '80%',
      min: 0,
      max: data.length ? data[0].value : 100,
      minSize: '0%',
      maxSize: '100%',
      sort: 'descending',
      gap: 2,
      label: { show: true, position: 'inside', formatter: '{b}\n{c}' },
      data: data.map(d => ({ name: d.stage, value: d.value })),
      itemStyle: {
        borderWidth: 1,
        borderColor: '#fff',
      },
    }],
  }
})

const attributionOption = computed(() => {
  const data = attributionData.value || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', name: '归因GMV(元)' },
    yAxis: {
      type: 'category',
      data: data.map(d => d.channel === 'online' ? '线上' : d.channel === 'offline' ? '线下' : 'O2O'),
    },
    series: [{
      type: 'bar',
      data: data.map(d => ({
        value: d.attributed_gmv,
        itemStyle: { color: d.channel === 'online' ? '#409EFF' : d.channel === 'offline' ? '#67C23A' : '#9B59B6' },
      })),
    }],
  }
})

const memberOverlapOption = computed(() => {
  const overlap = memberOverlap.value
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['仅线上', '仅线下', '双渠道'] },
    yAxis: { type: 'value', name: '会员数' },
    series: [{
      type: 'bar',
      data: [
        { value: overlap.online_only, itemStyle: { color: '#409EFF' } },
        { value: overlap.offline_only, itemStyle: { color: '#67C23A' } },
        { value: overlap.both, itemStyle: { color: '#9B59B6' } },
      ],
      barWidth: '40%',
    }],
  }
})

// API calls
async function fetchChannelKpi() {
  try {
    const { data } = await api.get('/api/omnichannel/kpi', { params: getParams() })
    channelKpi.value = {
      online: data.online || {},
      offline: data.offline || {},
      o2o: data.o2o || {},
    }
  } catch (e) { console.error('渠道KPI加载失败', e) }
}

async function fetchTrend() {
  try {
    const { data } = await api.get('/api/omnichannel/trend', { params: getParams() })
    trendData.value = data
  } catch (e) { console.error('趋势数据加载失败', e) }
}

async function fetchShare() {
  try {
    const { data } = await api.get('/api/omnichannel/share', { params: getParams() })
    shareData.value = data
  } catch (e) { console.error('占比数据加载失败', e) }
}

async function fetchFunnel() {
  try {
    const { data } = await api.get('/api/omnichannel/funnel', { params: getParams() })
    funnelData.value = data
  } catch (e) { console.error('漏斗数据加载失败', e) }
}

async function fetchAttribution() {
  try {
    const { data } = await api.get('/api/omnichannel/attribution', { params: getParams() })
    attributionData.value = data
  } catch (e) { console.error('归因数据加载失败', e) }
}

async function fetchMemberOverlap() {
  try {
    const { data } = await api.get('/api/omnichannel/member-overlap', { params: getParams() })
    memberOverlap.value = data.overlap || data
  } catch (e) { console.error('会员重叠数据加载失败', e) }
}

async function fetchMemberStats() {
  try {
    const { data } = await api.get('/api/omnichannel/member-stats', { params: getParams() })
    memberStats.value = data
  } catch (e) { console.error('会员指标加载失败', e) }
}

async function fetchInventory() {
  if (!inventoryStoreId.value) return
  try {
    const { data } = await api.get('/api/omnichannel/inventory', { params: { store_id: inventoryStoreId.value } })
    inventoryData.value = data
  } catch (e) { console.error('库存数据加载失败', e) }
}

async function loadAllData() {
  await Promise.all([
    fetchChannelKpi(),
    fetchTrend(),
    fetchShare(),
    fetchFunnel(),
    fetchAttribution(),
    fetchMemberOverlap(),
    fetchMemberStats(),
  ])
}

async function refreshData() {
  await loadAllData()
  ElMessage.success('数据已刷新')
}

watch([selectedStoreId, dateRange, channelFilter, attributionModel], () => {
  loadAllData()
})

onMounted(() => {
  appStore.fetchStores()
  loadAllData()
})
</script>

<style scoped>
.omnichannel-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }

.channel-card { height: 100%; }
.channel-title { font-weight: bold; font-size: 15px; }
.online-title { color: #409EFF; }
.offline-title { color: #67C23A; }
.o2o-title { color: #9B59B6; }

.channel-kpis { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; }
.channel-kpi { text-align: center; flex: 1; min-width: 70px; }
.channel-kpi-value { font-size: 18px; font-weight: bold; color: #303133; }
.channel-kpi-value.positive { color: #F56C6C; }
.channel-kpi-value.negative { color: #67C23A; }
.channel-kpi-label { font-size: 12px; color: #909399; margin-top: 2px; }

.channel-card.online { border-top: 3px solid #409EFF; }
.channel-card.offline { border-top: 3px solid #67C23A; }
.channel-card.o2o { border-top: 3px solid #9B59B6; }

.inventory-header { display: flex; justify-content: space-between; align-items: center; }
</style>
