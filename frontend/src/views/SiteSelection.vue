<template>
  <div class="site-selection-container">
    <div class="page-header">
      <h2>门店选址分析</h2>
      <div class="header-actions">
        <el-button @click="showImportDialog = true">导入竞品数据</el-button>
        <el-button type="primary" @click="showAddCandidate = true">添加候选地址</el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>候选地址对比雷达图</template>
          <chart-panel ref="radarChart" :option="radarOption" height="400px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>现有门店基准</template>
          <div class="benchmark-list">
            <div class="bench-item">
              <span class="bench-label">平均月营收</span>
              <span class="bench-value">¥{{ benchmark.avg_monthly_revenue?.toLocaleString() }}</span>
            </div>
            <div class="bench-item">
              <span class="bench-label">最高门店营收</span>
              <span class="bench-value">¥{{ benchmark.top_store_revenue?.toLocaleString() }}</span>
            </div>
            <div class="bench-item">
              <span class="bench-label">平均坪效</span>
              <span class="bench-value">{{ benchmark.avg_sqm_efficiency }}</span>
            </div>
            <div class="bench-item">
              <span class="bench-label">平均客流</span>
              <span class="bench-value">{{ benchmark.avg_traffic }}</span>
            </div>
            <div class="bench-item">
              <span class="bench-label">门店数量</span>
              <span class="bench-value">{{ benchmark.store_count }}</span>
            </div>
          </div>
        </el-card>

        <el-card style="margin-top: 16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>权重配置</span>
              <el-button size="small" type="primary" @click="showWeightEditor = true">新建方案</el-button>
            </div>
          </template>
          <el-radio-group v-model="selectedProfileId" size="small" style="margin-bottom:8px" @change="onProfileSelect">
            <el-radio-button v-for="p in profiles" :key="p.id" :label="p.id">{{ p.name }}</el-radio-button>
          </el-radio-group>
          <el-table :data="profiles" size="small" border>
            <el-table-column prop="name" label="方案" />
            <el-table-column prop="traffic_weight" label="客流" width="55" />
            <el-table-column prop="competition_weight" label="竞争" width="55" />
            <el-table-column prop="demographic_weight" label="人口" width="55" />
            <el-table-column prop="transport_weight" label="交通" width="55" />
            <el-table-column prop="commercial_weight" label="商业" width="55" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>候选地址评估排名</template>
      <el-table :data="evaluations" stripe border>
        <el-table-column type="index" label="排名" width="60" />
        <el-table-column prop="name" label="地址名称" width="160" />
        <el-table-column prop="city" label="城市" width="80" />
        <el-table-column prop="district" label="区域" width="100" />
        <el-table-column prop="total_score" label="总分" width="80" sortable>
          <template #default="{ row }">
            <span :class="scoreClass(row.total_score)">{{ row.total_score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="traffic_score" label="客流" width="70" />
        <el-table-column prop="competition_score" label="竞争" width="70" />
        <el-table-column prop="demographic_score" label="人口" width="70" />
        <el-table-column prop="transport_score" label="交通" width="70" />
        <el-table-column prop="commercial_score" label="商业" width="70" />
        <el-table-column prop="predicted_monthly_revenue" label="预估月营收" width="120">
          <template #default="{ row }">¥{{ row.predicted_monthly_revenue?.toLocaleString() || '-' }}</template>
        </el-table-column>
        <el-table-column prop="predicted_payback_months" label="回本(月)" width="90" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'info'" size="small">
              {{ row.status === 'evaluating' ? '评估中' : row.status === 'approved' ? '通过' : '拒绝' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="evaluateCandidate(row)">评估</el-button>
            <el-button size="small" type="success" @click="approveCandidate(row)">通过</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddCandidate" title="添加候选地址" width="550px">
      <el-form :model="newCandidate" label-width="90px">
        <el-form-item label="地址名称">
          <el-input v-model="newCandidate.name" />
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input v-model="newCandidate.address" />
        </el-form-item>
        <el-form-item label="城市">
          <el-input v-model="newCandidate.city" />
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="newCandidate.district" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="纬度">
              <el-input-number v-model="newCandidate.latitude" :precision="6" :step="0.001" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="经度">
              <el-input-number v-model="newCandidate.longitude" :precision="6" :step="0.001" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="面积(㎡)">
              <el-input-number v-model="newCandidate.area_sqm" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="月租(元)">
              <el-input-number v-model="newCandidate.monthly_rent" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showAddCandidate = false">取消</el-button>
        <el-button type="primary" @click="submitCandidate">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showImportDialog" title="导入竞品数据" width="450px">
      <el-upload drag action="" :auto-upload="false" :on-change="handleFileChange" accept=".csv,.xlsx,.xls">
        <el-icon style="font-size:40px;color:#909399"><i class="el-icon-upload"></i></el-icon>
        <div>拖拽或点击上传 CSV/Excel 文件</div>
        <template #tip>
          <div class="el-upload__tip">需包含 name 列，可选 brand, category, latitude, longitude, city, district</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="uploadCompetitors" :loading="uploading">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showWeightEditor" title="新建权重方案" width="500px">
      <el-form :model="newProfile" label-width="80px">
        <el-form-item label="方案名称">
          <el-input v-model="newProfile.name" placeholder="如：商业街优先" />
        </el-form-item>
        <el-form-item label="客流权重">
          <el-slider v-model="newProfile.traffic_weight" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item label="竞争权重">
          <el-slider v-model="newProfile.competition_weight" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item label="人口权重">
          <el-slider v-model="newProfile.demographic_weight" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item label="交通权重">
          <el-slider v-model="newProfile.transport_weight" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item label="商业权重">
          <el-slider v-model="newProfile.commercial_weight" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item>
          <span :style="{ color: weightSum !== 100 ? '#F56C6C' : '#67C23A' }">
            权重合计: {{ weightSum }}% {{ weightSum !== 100 ? '(需为100%)' : '✓' }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWeightEditor = false">取消</el-button>
        <el-button type="primary" @click="submitProfile" :disabled="weightSum !== 100">保存方案</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

const evaluations = ref([])
const profiles = ref([])
const benchmark = ref({})
const showAddCandidate = ref(false)
const showImportDialog = ref(false)
const showWeightEditor = ref(false)
const uploading = ref(false)
const uploadFile = ref(null)
const selectedProfileId = ref(null)

const newProfile = reactive({
  name: '',
  traffic_weight: 25,
  competition_weight: 20,
  demographic_weight: 20,
  transport_weight: 15,
  commercial_weight: 20,
})

const weightSum = computed(() =>
  newProfile.traffic_weight + newProfile.competition_weight +
  newProfile.demographic_weight + newProfile.transport_weight +
  newProfile.commercial_weight
)

const newCandidate = reactive({
  name: '', address: '', city: '', district: '',
  latitude: null, longitude: null, area_sqm: null, monthly_rent: null,
})

const radarOption = computed(() => {
  const items = evaluations.value.filter(e => e.total_score > 0).slice(0, 5)
  return {
    tooltip: {},
    legend: { data: items.map(i => i.name) },
    radar: {
      indicator: [
        { name: '客流', max: 100 },
        { name: '竞争优势', max: 100 },
        { name: '人口结构', max: 100 },
        { name: '交通便利', max: 100 },
        { name: '商业环境', max: 100 },
      ],
    },
    series: [{
      type: 'radar',
      data: items.map(i => ({
        name: i.name,
        value: [i.traffic_score || 0, i.competition_score || 0, i.demographic_score || 0, i.transport_score || 0, i.commercial_score || 0],
      })),
    }],
  }
})

function scoreClass(score) {
  if (score >= 75) return 'score-high'
  if (score >= 55) return 'score-mid'
  return 'score-low'
}

async function fetchCandidates() {
  try {
    const { data } = await api.get('/api/site-selection/candidates')
    const enriched = []
    for (const c of data) {
      try {
        const { data: evalData } = await api.get(`/api/site-selection/candidates/${c.id}/evaluation`)
        enriched.push({ ...c, ...evalData })
      } catch {
        enriched.push({ ...c, total_score: 0, traffic_score: 0, competition_score: 0, demographic_score: 0, transport_score: 0, commercial_score: 0 })
      }
    }
    evaluations.value = enriched.sort((a, b) => b.total_score - a.total_score)
  } catch (e) { console.error(e) }
}

async function fetchProfiles() {
  try {
    const { data } = await api.get('/api/site-selection/weight-profiles')
    profiles.value = data
    if (data.length > 0 && !selectedProfileId.value) {
      const defaultProfile = data.find(p => p.is_default) || data[0]
      selectedProfileId.value = defaultProfile.id
    }
  } catch (e) { console.error(e) }
}

function onProfileSelect(profileId) {
  selectedProfileId.value = profileId
}

async function submitProfile() {
  try {
    const payload = {
      name: newProfile.name,
      traffic_weight: newProfile.traffic_weight / 100,
      competition_weight: newProfile.competition_weight / 100,
      demographic_weight: newProfile.demographic_weight / 100,
      transport_weight: newProfile.transport_weight / 100,
      commercial_weight: newProfile.commercial_weight / 100,
    }
    await api.post('/api/site-selection/weight-profiles', payload)
    ElMessage.success('权重方案已保存')
    showWeightEditor.value = false
    fetchProfiles()
  } catch (e) { ElMessage.error('保存失败') }
}

async function fetchBenchmark() {
  try {
    const { data } = await api.get('/api/site-selection/benchmark')
    benchmark.value = data
  } catch (e) { console.error(e) }
}

async function submitCandidate() {
  try {
    await api.post('/api/site-selection/candidates', newCandidate)
    ElMessage.success('候选地址已添加')
    showAddCandidate.value = false
    fetchCandidates()
  } catch (e) { ElMessage.error('添加失败') }
}

async function evaluateCandidate(row) {
  try {
    const params = {}
    if (selectedProfileId.value) params.weight_profile_id = selectedProfileId.value
    const { data } = await api.post(`/api/site-selection/candidates/${row.id}/evaluate`, null, { params })
    ElMessage.success(`评估完成，总分: ${data.total_score}`)
    fetchCandidates()
  } catch (e) { ElMessage.error('评估失败') }
}

async function approveCandidate(row) {
  try {
    await api.put(`/api/site-selection/candidates/${row.id}`, { status: 'approved' })
    row.status = 'approved'
    ElMessage.success('已通过')
  } catch (e) { ElMessage.error('操作失败') }
}

function handleFileChange(file) {
  uploadFile.value = file.raw
}

async function uploadCompetitors() {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    const { data } = await api.post('/api/site-selection/competitors/import', formData)
    ElMessage.success(data.message)
    showImportDialog.value = false
  } catch (e) { ElMessage.error('导入失败') }
  finally { uploading.value = false }
}

onMounted(() => {
  fetchCandidates()
  fetchProfiles()
  fetchBenchmark()
})
</script>

<style scoped>
.site-selection-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-actions { display: flex; gap: 12px; }
.benchmark-list { display: flex; flex-direction: column; gap: 12px; }
.bench-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
.bench-label { color: #909399; }
.bench-value { font-weight: bold; color: #303133; }
.score-high { color: #67C23A; font-weight: bold; }
.score-mid { color: #E6A23C; font-weight: bold; }
.score-low { color: #F56C6C; font-weight: bold; }
</style>
