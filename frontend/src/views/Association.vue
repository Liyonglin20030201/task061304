<template>
  <div class="association-container">
    <el-card class="filter-bar">
      <div class="filter-row">
        <el-select v-model="storeId" placeholder="选择门店" clearable style="width: 180px;">
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 260px;"
        />
        <el-select v-model="category" placeholder="商品类别" clearable style="width: 150px;">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
        <div class="slider-group">
          <span class="slider-label">最小支持度:</span>
          <el-slider v-model="minSupport" :min="0.01" :max="0.5" :step="0.01" style="width: 120px;" />
          <el-input-number v-model="minSupport" :min="0.01" :max="0.5" :step="0.01" :precision="2" size="small" style="width: 100px;" />
        </div>
        <div class="slider-group">
          <span class="slider-label">最小置信度:</span>
          <el-slider v-model="minConfidence" :min="0.1" :max="1.0" :step="0.05" style="width: 120px;" />
          <el-input-number v-model="minConfidence" :min="0.1" :max="1.0" :step="0.05" :precision="2" size="small" style="width: 100px;" />
        </div>
        <el-button type="primary" @click="runAnalysis" :loading="analyzing">运行分析</el-button>
      </div>
    </el-card>

    <el-tabs v-model="activeTab" style="margin-top: 20px;">
      <!-- Tab 1: Association Rules -->
      <el-tab-pane label="关联规则" name="rules">
        <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 10px;">
          <span>最小提升度:</span>
          <el-input-number v-model="minLiftFilter" :min="0" :step="0.1" :precision="1" size="small" style="width: 120px;" />
        </div>
        <el-table :data="filteredRules" stripe border v-loading="rulesLoading" empty-text="暂无数据，请运行分析">
          <el-table-column label="前项" min-width="180">
            <template #default="{ row }">{{ row.antecedent_names.join(', ') }}</template>
          </el-table-column>
          <el-table-column label="后项" min-width="180">
            <template #default="{ row }">{{ row.consequent_names.join(', ') }}</template>
          </el-table-column>
          <el-table-column label="支持度" width="100" sortable :sort-method="(a, b) => a.support - b.support">
            <template #default="{ row }">{{ (row.support * 100).toFixed(2) }}%</template>
          </el-table-column>
          <el-table-column label="置信度" width="100" sortable :sort-method="(a, b) => a.confidence - b.confidence">
            <template #default="{ row }">{{ (row.confidence * 100).toFixed(2) }}%</template>
          </el-table-column>
          <el-table-column label="提升度" width="100" sortable :sort-method="(a, b) => a.lift - b.lift">
            <template #default="{ row }">{{ row.lift.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="transaction_count" label="交易数" width="100" sortable />
        </el-table>
        <el-pagination
          v-if="rules.length > pageSize"
          style="margin-top: 16px; justify-content: center; display: flex;"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="paginationTotal"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </el-tab-pane>

      <!-- Tab 2: Network Graph -->
      <el-tab-pane label="网络关系图" name="network">
        <div v-if="!rules.length" class="empty-state">暂无数据，请先运行分析</div>
        <chart-panel v-else :option="networkOption" height="550px" />
      </el-tab-pane>

      <!-- Tab 3: Co-occurrence Heatmap -->
      <el-tab-pane label="共现热力图" name="heatmap">
        <div v-if="!heatmapData.matrix || !heatmapData.matrix.length" class="empty-state">
          <span v-if="heatmapLoading">加载中...</span>
          <span v-else>暂无数据，请先运行分析</span>
        </div>
        <chart-panel v-else :option="heatmapOption" height="550px" />
      </el-tab-pane>

      <!-- Tab 4: Bundle Recommendations -->
      <el-tab-pane label="捆绑推荐" name="bundle">
        <div style="margin-bottom: 16px;">
          <el-input
            v-model="bundleSearchKeyword"
            placeholder="搜索商品名称"
            prefix-icon="Search"
            style="width: 300px;"
            @keyup.enter="searchBundles"
          >
            <template #append>
              <el-button @click="searchBundles" :loading="bundleLoading">搜索</el-button>
            </template>
          </el-input>
        </div>
        <div v-if="!bundleResults.length" class="empty-state">
          输入商品名称搜索捆绑推荐
        </div>
        <div v-else class="bundle-cards">
          <el-card v-for="(bundle, idx) in bundleResults" :key="idx" class="bundle-card">
            <template #header>
              <div class="bundle-header">
                <span class="bundle-source">{{ bundle.source_item }}</span>
                <el-tag type="success" size="small">推荐捆绑销售</el-tag>
              </div>
            </template>
            <div class="bundle-list">
              <div v-for="(item, i) in bundle.recommendations" :key="i" class="bundle-item">
                <span class="bundle-item-name">{{ item.item_name }}</span>
                <span class="bundle-item-metrics">
                  置信度: {{ (item.confidence * 100).toFixed(1) }}% | 提升度: {{ item.lift.toFixed(2) }}
                </span>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- Tab 5: Layout Suggestions -->
      <el-tab-pane label="布局建议" name="layout">
        <div v-if="!layoutSuggestions.length" class="empty-state">
          <span v-if="layoutLoading">加载中...</span>
          <span v-else>暂无数据，请先运行分析</span>
        </div>
        <div v-else class="layout-cards">
          <el-card v-for="(cluster, idx) in layoutSuggestions" :key="idx" class="layout-card">
            <template #header>
              <div class="layout-header">
                <span>聚类 {{ idx + 1 }}</span>
                <el-tag type="warning" size="small">建议相邻摆放</el-tag>
              </div>
            </template>
            <div class="layout-items">
              <el-tag v-for="item in cluster.items" :key="item" style="margin: 4px;">{{ item }}</el-tag>
            </div>
            <div class="layout-metrics">
              <span>平均提升度: <strong>{{ cluster.avg_lift.toFixed(2) }}</strong></span>
            </div>
            <div v-if="cluster.suggestion" class="layout-suggestion">
              {{ cluster.suggestion }}
            </div>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

// Filter state
const stores = ref([])
const storeId = ref(null)
const dateRange = ref([])
const category = ref('')
const categories = ref([])
const minSupport = ref(0.01)
const minConfidence = ref(0.3)
const analyzing = ref(false)

// Tab state
const activeTab = ref('rules')

// Rules tab
const rules = ref([])
const rulesLoading = ref(false)
const minLiftFilter = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

// Heatmap tab
const heatmapData = ref({ matrix: [], items: [] })
const heatmapLoading = ref(false)

// Bundle tab
const bundleSearchKeyword = ref('')
const bundleResults = ref([])
const bundleLoading = ref(false)

// Layout tab
const layoutSuggestions = ref([])
const layoutLoading = ref(false)

// Computed: filtered and paginated rules
const liftFilteredRules = computed(() => {
  if (!minLiftFilter.value) return rules.value
  return rules.value.filter(r => r.lift >= minLiftFilter.value)
})

const paginationTotal = computed(() => liftFilteredRules.value.length)

const filteredRules = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return liftFilteredRules.value.slice(start, start + pageSize.value)
})

function handlePageChange(page) {
  currentPage.value = page
}

// Network graph option
const networkOption = computed(() => {
  if (!rules.value.length) return {}

  const nodeMap = new Map()
  const categorySet = new Set()

  rules.value.forEach(rule => {
    rule.antecedent_names.forEach(name => {
      if (!nodeMap.has(name)) {
        nodeMap.set(name, { name, value: 0, category: rule.antecedent_category || '默认' })
      }
      nodeMap.get(name).value += rule.transaction_count || 1
    })
    rule.consequent_names.forEach(name => {
      if (!nodeMap.has(name)) {
        nodeMap.set(name, { name, value: 0, category: rule.consequent_category || '默认' })
      }
      nodeMap.get(name).value += rule.transaction_count || 1
    })
  })

  const nodes = []
  nodeMap.forEach((node) => {
    categorySet.add(node.category)
    nodes.push(node)
  })

  const categoryList = [...categorySet].map(c => ({ name: c }))
  const categoryIndex = Object.fromEntries([...categorySet].map((c, i) => [c, i]))

  const maxVal = Math.max(...nodes.map(n => n.value), 1)
  const formattedNodes = nodes.map(n => ({
    name: n.name,
    symbolSize: Math.max(10, (n.value / maxVal) * 50),
    category: categoryIndex[n.category] || 0,
    value: n.value,
  }))

  const edges = rules.value.slice(0, 100).map(rule => ({
    source: rule.antecedent_names[0],
    target: rule.consequent_names[0],
    value: rule.lift,
    lineStyle: {
      width: Math.min(Math.max(rule.lift, 1), 8),
    },
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter(params) {
        if (params.dataType === 'node') {
          return `${params.name}<br/>交易次数: ${params.value}`
        }
        if (params.dataType === 'edge') {
          return `${params.data.source} → ${params.data.target}<br/>提升度: ${params.data.value.toFixed(2)}`
        }
        return ''
      },
    },
    legend: {
      data: categoryList.map(c => c.name),
      orient: 'vertical',
      left: 'left',
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: formattedNodes,
      links: edges,
      categories: categoryList,
      roam: true,
      label: {
        show: true,
        position: 'right',
        fontSize: 10,
      },
      force: {
        repulsion: 200,
        edgeLength: [80, 200],
        gravity: 0.1,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 5 },
      },
    }],
  }
})

// Heatmap option
const heatmapOption = computed(() => {
  const { matrix, items } = heatmapData.value
  if (!matrix || !matrix.length || !items || !items.length) return {}

  const data = []
  let minVal = Infinity
  let maxVal = -Infinity
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < matrix[i].length; j++) {
      const val = matrix[i][j]
      data.push([j, i, val])
      if (val > maxVal) maxVal = val
      if (val < minVal) minVal = val
    }
  }

  return {
    tooltip: {
      position: 'top',
      formatter(params) {
        const x = items[params.value[0]] || ''
        const y = items[params.value[1]] || ''
        const count = params.value[2]
        return `${y} + ${x}: ${count}次共同购买`
      },
    },
    grid: {
      top: '10%',
      left: '15%',
      right: '10%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category',
      data: items,
      axisLabel: { rotate: 45, fontSize: 10 },
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: items,
      axisLabel: { fontSize: 10 },
      splitArea: { show: true },
    },
    visualMap: {
      min: minVal,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#f5f5f5', '#fdae6b', '#e6550d'],
      },
    },
    series: [{
      type: 'heatmap',
      data,
      label: { show: false },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
      },
    }],
  }
})

// Fetch stores
async function fetchStores() {
  try {
    const { data } = await api.get('/api/stores')
    stores.value = Array.isArray(data) ? data : (data.stores || [])
  } catch (e) {
    console.error('Failed to fetch stores:', e)
  }
}

// Run analysis
async function runAnalysis() {
  analyzing.value = true
  try {
    const payload = {
      min_support: minSupport.value,
      min_confidence: minConfidence.value,
    }
    if (storeId.value) payload.store_id = storeId.value
    if (dateRange.value && dateRange.value.length === 2) {
      payload.start_date = dateRange.value[0]
      payload.end_date = dateRange.value[1]
    }
    if (category.value) payload.category = category.value

    const { data } = await api.post('/api/association/analyze', payload)
    const rulesCount = data.rules_count || (data.rules ? data.rules.length : 0)
    ElMessage.success(`分析完成，发现 ${rulesCount} 条关联规则`)
    await fetchRules()
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    analyzing.value = false
  }
}

// Fetch rules
async function fetchRules() {
  rulesLoading.value = true
  try {
    const params = {}
    if (storeId.value) params.store_id = storeId.value
    const { data } = await api.get('/api/association/rules', { params })
    rules.value = Array.isArray(data) ? data : (data.rules || [])
    currentPage.value = 1
  } catch (e) {
    console.error('Failed to fetch rules:', e)
  } finally {
    rulesLoading.value = false
  }
}

// Fetch heatmap data
async function fetchHeatmap() {
  heatmapLoading.value = true
  try {
    const params = { top_n: 20 }
    if (storeId.value) params.store_id = storeId.value
    const { data } = await api.get('/api/association/heatmap', { params })
    heatmapData.value = data
  } catch (e) {
    console.error('Failed to fetch heatmap:', e)
  } finally {
    heatmapLoading.value = false
  }
}

// Search bundles
async function searchBundles() {
  if (!bundleSearchKeyword.value.trim()) return
  bundleLoading.value = true
  try {
    const params = { keyword: bundleSearchKeyword.value.trim() }
    if (storeId.value) params.store_id = storeId.value
    const { data } = await api.get('/api/association/bundles', { params })
    bundleResults.value = Array.isArray(data) ? data : (data.bundles || [])
    if (!bundleResults.value.length) {
      ElMessage.info('未找到相关捆绑推荐')
    }
  } catch (e) {
    ElMessage.error('查询失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    bundleLoading.value = false
  }
}

// Fetch layout suggestions
async function fetchLayout() {
  layoutLoading.value = true
  try {
    const params = {}
    if (storeId.value) params.store_id = storeId.value
    const { data } = await api.get('/api/association/layout', { params })
    layoutSuggestions.value = Array.isArray(data) ? data : (data.clusters || [])
  } catch (e) {
    console.error('Failed to fetch layout:', e)
  } finally {
    layoutLoading.value = false
  }
}

// Watch tab changes to load data
watch(activeTab, (tab) => {
  if (tab === 'heatmap' && !heatmapData.value.matrix?.length) {
    fetchHeatmap()
  }
  if (tab === 'layout' && !layoutSuggestions.value.length) {
    fetchLayout()
  }
})

// Set default date range (last 30 days)
function setDefaultDateRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 30)
  const fmt = (d) => d.toISOString().split('T')[0]
  dateRange.value = [fmt(start), fmt(end)]
}

onMounted(() => {
  fetchStores()
  setDefaultDateRange()
})
</script>

<style scoped>
.association-container {
  padding: 20px;
}

.filter-bar {
  margin-bottom: 0;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.slider-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  padding: 60px 0;
  color: #909399;
  font-size: 14px;
}

.bundle-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

.bundle-card {
  border-radius: 8px;
}

.bundle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.bundle-source {
  font-weight: bold;
  font-size: 15px;
}

.bundle-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bundle-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.bundle-item-name {
  font-weight: 500;
  color: #303133;
}

.bundle-item-metrics {
  font-size: 12px;
  color: #909399;
}

.layout-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.layout-card {
  border-radius: 8px;
}

.layout-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.layout-items {
  margin-bottom: 12px;
}

.layout-metrics {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.layout-suggestion {
  font-size: 13px;
  color: #409eff;
  padding: 8px;
  background: #ecf5ff;
  border-radius: 4px;
}
</style>
