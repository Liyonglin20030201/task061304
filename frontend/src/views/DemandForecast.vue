<template>
  <div class="demand-forecast-container" style="padding: 20px;">
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6"><store-selector /></el-col>
      <el-col :span="5">
        <el-select v-model="selectedStore" placeholder="选择门店" @change="loadData">
          <el-option v-for="s in stores" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-col>
      <el-col :span="5">
        <el-slider v-model="periods" :min="7" :max="90" :step="1" show-input @change="loadData" />
      </el-col>
      <el-col :span="4">
        <el-select v-model="category" placeholder="分类" clearable @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="食品" value="食品" />
          <el-option label="饮料" value="饮料" />
          <el-option label="日用品" value="日用品" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-button type="primary" @click="triggerTune" :loading="tuning">自动调优</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #909399;">{{ accuracyBaseline }}%</div>
            <div style="font-size: 13px; color: #666; margin-top: 4px;">基线MAPE</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #409eff;">{{ accuracyEnhanced }}%</div>
            <div style="font-size: 13px; color: #666; margin-top: 4px;">增强MAPE</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 15px 0;">
            <div :style="{fontSize: '28px', fontWeight: 'bold', color: improvement > 0 ? '#67c23a' : '#f56c6c'}">
              {{ improvement > 0 ? '+' : '' }}{{ improvement }}%
            </div>
            <div style="font-size: 13px; color: #666; margin-top: 4px;">精度提升</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center; padding: 15px 0;">
            <div style="font-size: 28px; font-weight: bold; color: #e6a23c;">{{ signalsCount }}</div>
            <div style="font-size: 13px; color: #666; margin-top: 4px;">外部信号</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="24">
        <el-card>
          <template #header><span>预测对比: 基线 vs 增强模型</span></template>
          <chart-panel :option="comparisonOption" height="400px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <el-card>
          <template #header><span>外部信号</span></template>
          <chart-panel :option="signalsOption" height="250px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>A/B 实验</span></template>
          <el-table :data="experiments" stripe max-height="250">
            <el-table-column prop="experiment_name" label="实验名称" min-width="120" />
            <el-table-column prop="model_a" label="模型A" width="80" />
            <el-table-column prop="model_b" label="模型B" width="80" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="winner" label="胜者" width="80" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header><span>精度趋势</span></template>
      <chart-panel :option="accuracyTrendOption" height="300px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import ChartPanel from '@/components/ChartPanel.vue'
import StoreSelector from '@/components/StoreSelector.vue'
import { ElMessage } from 'element-plus'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)
const selectedStore = ref(null)
const periods = ref(30)
const category = ref('')
const tuning = ref(false)

const comparison = ref({ baseline: [], enhanced: [] })
const signals = ref([])
const experiments = ref([])
const accuracyHistory = ref([])
const accuracyBaseline = ref('--')
const accuracyEnhanced = ref('--')
const improvement = ref(0)
const signalsCount = ref(0)

const comparisonOption = computed(() => {
  const dates = comparison.value.baseline.map(d => d.date)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['基线预测', '增强预测', '基线上界', '增强上界'] },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: [
      { name: '基线预测', type: 'line', data: comparison.value.baseline.map(d => d.forecast), lineStyle: { type: 'dashed', color: '#909399' } },
      { name: '增强预测', type: 'line', data: comparison.value.enhanced.map(d => d.forecast), lineStyle: { color: '#409eff' }, itemStyle: { color: '#409eff' } },
      { name: '基线上界', type: 'line', data: comparison.value.baseline.map(d => d.upper), lineStyle: { type: 'dotted', color: '#c0c4cc' }, symbol: 'none' },
      { name: '增强上界', type: 'line', data: comparison.value.enhanced.map(d => d.upper), lineStyle: { type: 'dotted', color: '#a0cfff' }, symbol: 'none' },
    ],
  }
})

const signalsOption = computed(() => {
  const types = [...new Set(signals.value.map(s => s.signal_type))]
  const dates = [...new Set(signals.value.map(s => s.signal_date))].sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: types },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: types.map(t => ({
      name: t, type: 'line',
      data: dates.map(d => { const item = signals.value.find(s => s.signal_date === d && s.signal_type === t); return item ? item.value : null }),
    })),
  }
})

const accuracyTrendOption = computed(() => {
  const baselineData = accuracyHistory.value.filter(a => a.model_name === 'baseline')
  const enhancedData = accuracyHistory.value.filter(a => a.model_name === 'enhanced')
  const dates = [...new Set(accuracyHistory.value.map(a => a.evaluation_date))].sort()
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['基线MAPE', '增强MAPE'] },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'MAPE (%)' },
    series: [
      { name: '基线MAPE', type: 'line', data: dates.map(d => { const item = baselineData.find(a => a.evaluation_date === d); return item ? item.mape : null }), itemStyle: { color: '#909399' } },
      { name: '增强MAPE', type: 'line', data: dates.map(d => { const item = enhancedData.find(a => a.evaluation_date === d); return item ? item.mape : null }), itemStyle: { color: '#409eff' } },
    ],
  }
})

const triggerTune = async () => {
  if (!selectedStore.value) { ElMessage.warning('请选择门店'); return }
  tuning.value = true
  try {
    const res = await api.post(`/api/demand-forecast/tune?store_id=${selectedStore.value}`)
    ElMessage.success(`调优完成: 基线MAPE ${res.data.baseline_mape}% → 增强MAPE ${res.data.enhanced_mape}%`)
    await loadData()
  } catch (e) {
    ElMessage.error('调优失败')
  } finally {
    tuning.value = false
  }
}

const loadData = async () => {
  if (!selectedStore.value && stores.value.length > 0) {
    selectedStore.value = stores.value[0].id
  }
  if (!selectedStore.value) return

  const catParam = category.value ? `&category=${category.value}` : ''
  try {
    const [compRes, sigRes, expRes, accRes] = await Promise.all([
      api.get(`/api/demand-forecast/comparison?store_id=${selectedStore.value}&periods=${periods.value}${catParam}`),
      api.get(`/api/demand-forecast/signals`),
      api.get(`/api/demand-forecast/ab-experiments`),
      api.get(`/api/demand-forecast/accuracy?store_ids=${selectedStore.value}&days=90`),
    ])
    comparison.value = compRes.data
    signals.value = sigRes.data
    signalsCount.value = sigRes.data.length
    experiments.value = expRes.data
    accuracyHistory.value = accRes.data

    const latestBaseline = accRes.data.find(a => a.model_name === 'baseline')
    const latestEnhanced = accRes.data.find(a => a.model_name === 'enhanced')
    accuracyBaseline.value = latestBaseline ? latestBaseline.mape.toFixed(1) : '--'
    accuracyEnhanced.value = latestEnhanced ? latestEnhanced.mape.toFixed(1) : '--'
    improvement.value = latestBaseline && latestEnhanced ? (latestBaseline.mape - latestEnhanced.mape).toFixed(1) : 0
  } catch (e) {
    console.error('加载预测数据失败', e)
  }
}

onMounted(async () => {
  await appStore.fetchStores()
  await loadData()
})
</script>
