<template>
  <div class="product-lifecycle-container" style="padding: 20px;">
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6"><store-selector /></el-col>
      <el-col :span="6">
        <el-select v-model="category" placeholder="商品分类" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="食品" value="食品" />
          <el-option label="饮料" value="饮料" />
          <el-option label="日用品" value="日用品" />
          <el-option label="生鲜" value="生鲜" />
        </el-select>
      </el-col>
      <el-col :span="6">
        <el-select v-model="stageFilter" placeholder="生命周期阶段" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="引入期" value="introduction" />
          <el-option label="成长期" value="growth" />
          <el-option label="成熟期" value="maturity" />
          <el-option label="衰退期" value="decline" />
        </el-select>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover" style="border-left: 4px solid #909399;">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold;">{{ overview.introduction_count }}</div>
            <div style="font-size: 14px; color: #909399; margin-top: 4px;">引入期</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="border-left: 4px solid #409eff;">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #409eff;">{{ overview.growth_count }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 4px;">成长期</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="border-left: 4px solid #67c23a;">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #67c23a;">{{ overview.maturity_count }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 4px;">成熟期</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="border-left: 4px solid #f56c6c;">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #f56c6c;">{{ overview.decline_count }}</div>
            <div style="font-size: 14px; color: #666; margin-top: 4px;">衰退期</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="8">
        <el-card>
          <template #header><span>阶段分布</span></template>
          <chart-panel :option="pieOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card>
          <template #header><span>生命周期曲线 {{ selectedProduct ? '- ' + selectedProduct.item_name : '' }}</span></template>
          <chart-panel :option="curveOption" height="300px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header><span>近期阶段变化</span></template>
          <el-table :data="transitions" stripe max-height="300">
            <el-table-column prop="item_name" label="商品" min-width="120" />
            <el-table-column prop="from_stage" label="原阶段" width="90">
              <template #default="{ row }"><el-tag size="small">{{ stageLabel(row.from_stage) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="" width="40"><template #default><span>→</span></template></el-table-column>
            <el-table-column prop="to_stage" label="新阶段" width="90">
              <template #default="{ row }"><el-tag size="small" :type="stageType(row.to_stage)">{{ stageLabel(row.to_stage) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="transition_date" label="日期" width="110" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>淘汰建议</span></template>
          <el-table :data="recommendations" stripe max-height="300">
            <el-table-column prop="item_name" label="商品" min-width="120" />
            <el-table-column prop="recommendation" label="建议" width="90">
              <template #default="{ row }">
                <el-tag :type="row.recommendation === 'phase_out' ? 'danger' : row.recommendation === 'markdown' ? 'warning' : 'info'" size="small">
                  {{ recLabel(row.recommendation) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="80">
              <template #default="{ row }">{{ (row.confidence * 100).toFixed(0) }}%</template>
            </el-table-column>
            <el-table-column prop="impact_revenue_loss" label="周收入损失" width="100">
              <template #default="{ row }">¥{{ (row.impact_revenue_loss || 0).toFixed(0) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header><span>商品列表</span></template>
      <el-table :data="products.items" stripe border @row-click="selectProduct">
        <el-table-column prop="item_id" label="商品编号" width="120" />
        <el-table-column prop="item_name" label="商品名称" min-width="150" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="current_stage" label="阶段" width="90">
          <template #default="{ row }"><el-tag :type="stageType(row.current_stage)" size="small">{{ stageLabel(row.current_stage) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="weekly_revenue" label="周收入" width="100">
          <template #default="{ row }">¥{{ (row.weekly_revenue || 0).toFixed(0) }}</template>
        </el-table-column>
        <el-table-column prop="growth_rate" label="增长率" width="100">
          <template #default="{ row }">
            <span :style="{ color: (row.growth_rate || 0) > 0 ? '#67c23a' : '#f56c6c' }">
              {{ ((row.growth_rate || 0) * 100).toFixed(1) }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top: 16px; justify-content: center;"
        :current-page="products.page" :page-size="20" :total="products.total" @current-change="changePage" />
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
const category = ref('')
const stageFilter = ref('')
const selectedProduct = ref(null)

const overview = ref({ introduction_count: 0, growth_count: 0, maturity_count: 0, decline_count: 0, total_products: 0 })
const products = ref({ items: [], total: 0, page: 1 })
const curveData = ref({ weeks: [], revenues: [], stages: [], quantities: [] })
const transitions = ref([])
const recommendations = ref([])

const stageLabel = (s) => ({ introduction: '引入期', growth: '成长期', maturity: '成熟期', decline: '衰退期' }[s] || s)
const stageType = (s) => ({ introduction: 'info', growth: '', maturity: 'success', decline: 'danger' }[s] || '')
const recLabel = (r) => ({ phase_out: '淘汰', markdown: '降价', keep: '观察', replace: '替换' }[r] || r)

const pieOption = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie', radius: ['40%', '70%'],
    data: [
      { value: overview.value.introduction_count, name: '引入期', itemStyle: { color: '#909399' } },
      { value: overview.value.growth_count, name: '成长期', itemStyle: { color: '#409eff' } },
      { value: overview.value.maturity_count, name: '成熟期', itemStyle: { color: '#67c23a' } },
      { value: overview.value.decline_count, name: '衰退期', itemStyle: { color: '#f56c6c' } },
    ],
    label: { formatter: '{b}: {c}' },
  }],
}))

const stageColors = { introduction: '#909399', growth: '#409eff', maturity: '#67c23a', decline: '#f56c6c' }
const curveOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: curveData.value.weeks },
  yAxis: { type: 'value' },
  series: [{
    type: 'line', smooth: true, data: curveData.value.revenues, areaStyle: { opacity: 0.3 },
    itemStyle: { color: '#409eff' },
  }],
  visualMap: {
    show: false, dimension: 0, pieces: curveData.value.stages.map((s, i) => ({
      gte: i, lt: i + 1, color: stageColors[s] || '#409eff',
    })),
  },
}))

const selectProduct = async (row) => {
  selectedProduct.value = row
  const storeParam = appStore.selectedStoreIds.length > 0 ? `&store_ids=${appStore.selectedStoreIds.join(',')}` : ''
  try {
    const res = await api.get(`/api/product-lifecycle/curve/${row.id}?${storeParam}`)
    curveData.value = res.data
  } catch (e) {
    console.error('加载曲线失败', e)
  }
}

const changePage = (p) => { products.value.page = p; loadProducts() }

const loadProducts = async () => {
  const storeParam = appStore.selectedStoreIds.length > 0 ? `store_ids=${appStore.selectedStoreIds.join(',')}` : ''
  const catParam = category.value ? `&category=${category.value}` : ''
  const stgParam = stageFilter.value ? `&stage=${stageFilter.value}` : ''
  const res = await api.get(`/api/product-lifecycle/products?${storeParam}${catParam}${stgParam}&page=${products.value.page}`)
  products.value = res.data
}

const loadData = async () => {
  const storeParam = appStore.selectedStoreIds.length > 0 ? `store_ids=${appStore.selectedStoreIds.join(',')}` : ''
  const catParam = category.value ? `&category=${category.value}` : ''
  try {
    const [ovRes, transRes, recRes] = await Promise.all([
      api.get(`/api/product-lifecycle/overview?${storeParam}${catParam}`),
      api.get(`/api/product-lifecycle/transitions?${storeParam}&days=30`),
      api.get(`/api/product-lifecycle/retirement-recommendations?${storeParam}${catParam}`),
    ])
    overview.value = ovRes.data
    transitions.value = transRes.data
    recommendations.value = recRes.data
    await loadProducts()
    if (products.value.items.length > 0) {
      await selectProduct(products.value.items[0])
    }
  } catch (e) {
    console.error('加载生命周期数据失败', e)
  }
}

onMounted(loadData)
</script>
