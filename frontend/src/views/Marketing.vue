<template>
  <div class="marketing-container">
    <div class="page-header">
      <h2>会员营销自动化</h2>
      <el-button type="primary" @click="showCreateCampaign = true">新建活动</el-button>
    </div>

    <div class="kpi-cards">
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.active_campaigns }}</div>
        <div class="kpi-label">活跃活动</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.members_reached_month }}</div>
        <div class="kpi-label">本月触达会员</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.avg_conversion_rate }}%</div>
        <div class="kpi-label">平均转化率</div>
      </el-card>
      <el-card class="kpi-card">
        <div class="kpi-value">{{ dashboardData.total_roi }}</div>
        <div class="kpi-label">ROI</div>
      </el-card>
    </div>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="10">
        <el-card>
          <template #header>会员生命周期分布</template>
          <chart-panel ref="lifecycleChart" :option="lifecycleOption" height="320px" />
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>活动效果趋势</span>
              <el-button size="small" @click="runTriggers" :loading="triggering">执行触发评估</el-button>
            </div>
          </template>
          <chart-panel ref="trendChart" :option="trendOption" height="320px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>营销活动</span>
          <el-radio-group v-model="campaignFilter" @change="fetchCampaigns" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="active">活跃</el-radio-button>
            <el-radio-button label="draft">草稿</el-radio-button>
            <el-radio-button label="paused">暂停</el-radio-button>
            <el-radio-button label="completed">已完成</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="campaigns" stripe border>
        <el-table-column prop="name" label="活动名称" width="180" />
        <el-table-column prop="campaign_type" label="类型" width="100">
          <template #default="{ row }">{{ typeLabel(row.campaign_type) }}</template>
        </el-table-column>
        <el-table-column prop="channel" label="渠道" width="80" />
        <el-table-column prop="target_segment" label="目标人群" width="120" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发送" width="80">
          <template #default="{ row }">{{ row.stats?.total_sent || 0 }}</template>
        </el-table-column>
        <el-table-column label="转化" width="80">
          <template #default="{ row }">{{ row.stats?.converted || 0 }}</template>
        </el-table-column>
        <el-table-column label="转化率" width="90">
          <template #default="{ row }">{{ row.stats?.conversion_rate || 0 }}%</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始" width="110" />
        <el-table-column prop="end_date" label="结束" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="toggleStatus(row, 'active')" v-if="row.status !== 'active'">启用</el-button>
            <el-button size="small" type="warning" @click="toggleStatus(row, 'paused')" v-if="row.status === 'active'">暂停</el-button>
            <el-button size="small" @click="executeCampaign(row)">手动触发</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreateCampaign" title="新建营销活动" width="650px">
      <el-form :model="newCampaign" label-width="100px">
        <el-form-item label="活动名称">
          <el-input v-model="newCampaign.name" placeholder="如：生日关怀-6月" />
        </el-form-item>
        <el-form-item label="活动类型">
          <el-select v-model="newCampaign.campaign_type" style="width: 100%">
            <el-option label="生日关怀" value="birthday" />
            <el-option label="流失预警" value="churn_warning" />
            <el-option label="复购激励" value="repurchase" />
            <el-option label="升级鼓励" value="upgrade" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发方式">
          <el-select v-model="newCampaign.trigger_type" style="width: 100%">
            <el-option label="自动触发" value="auto" />
            <el-option label="手动触发" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标人群">
          <el-select v-model="newCampaign.target_segment" style="width: 100%" clearable>
            <el-option label="高价值" value="high_value" />
            <el-option label="活跃" value="active" />
            <el-option label="流失风险" value="at_risk" />
            <el-option label="沉睡" value="churned" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item label="触达渠道">
          <el-select v-model="newCampaign.channel" style="width: 100%">
            <el-option label="短信" value="sms" />
            <el-option label="邮件" value="email" />
            <el-option label="推送" value="push" />
            <el-option label="微信" value="wechat" />
          </el-select>
        </el-form-item>
        <el-form-item label="消息模板">
          <el-input v-model="newCampaign.message_template" type="textarea" :rows="3" placeholder="支持变量: {member_id}, {name}" />
        </el-form-item>
        <el-form-item label="优惠类型">
          <el-select v-model="newCampaign.discount_type" clearable style="width: 100%">
            <el-option label="折扣" value="percentage" />
            <el-option label="满减" value="fixed" />
            <el-option label="积分" value="points" />
          </el-select>
        </el-form-item>
        <el-form-item label="优惠力度" v-if="newCampaign.discount_type">
          <el-input-number v-model="newCampaign.discount_value" :min="0" />
        </el-form-item>
        <el-form-item label="预算">
          <el-input-number v-model="newCampaign.budget" :min="0" :step="1000" />
        </el-form-item>
        <el-form-item label="有效期">
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
            start-placeholder="开始" end-placeholder="结束" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateCampaign = false">取消</el-button>
        <el-button type="primary" @click="submitCampaign">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import ChartPanel from '../components/ChartPanel.vue'

const campaignFilter = ref('')
const campaigns = ref([])
const showCreateCampaign = ref(false)
const triggering = ref(false)
const dateRange = ref([])
const dashboardData = ref({
  active_campaigns: 0,
  members_reached_month: 0,
  avg_conversion_rate: 0,
  total_roi: 0,
  lifecycle_distribution: [],
})

const newCampaign = reactive({
  name: '',
  campaign_type: 'birthday',
  trigger_type: 'auto',
  target_segment: 'all',
  message_template: '',
  channel: 'sms',
  discount_type: null,
  discount_value: null,
  budget: 0,
})

const lifecycleOption = computed(() => {
  const data = dashboardData.value.lifecycle_distribution || []
  const stageNames = { new: '新会员', active: '活跃', declining: '下降', at_risk: '流失风险', churned: '沉睡' }
  return {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'funnel',
      left: '10%',
      width: '80%',
      sort: 'none',
      data: data.map(d => ({
        name: stageNames[d.stage] || d.stage,
        value: d.count,
      })),
      label: { show: true, formatter: '{b}: {c}' },
    }],
  }
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] },
  yAxis: [{ type: 'value', name: '人数' }, { type: 'value', name: '%', position: 'right' }],
  legend: { data: ['触达人数', '转化率'] },
  series: [
    { name: '触达人数', type: 'bar', data: [120, 200, 150, 80, 70, 110, 130] },
    { name: '转化率', type: 'line', yAxisIndex: 1, data: [12, 15, 13, 18, 22, 14, 16] },
  ],
}))

function typeLabel(t) {
  const map = { birthday: '生日关怀', churn_warning: '流失预警', repurchase: '复购激励', upgrade: '升级鼓励', custom: '自定义' }
  return map[t] || t
}
function statusType(s) {
  const map = { active: 'success', draft: 'info', paused: 'warning', completed: '' }
  return map[s] || 'info'
}
function statusLabel(s) {
  const map = { active: '活跃', draft: '草稿', paused: '暂停', completed: '完成' }
  return map[s] || s
}

async function fetchDashboard() {
  try {
    const { data } = await api.get('/api/marketing/dashboard')
    dashboardData.value = data
  } catch (e) { console.error(e) }
}

async function fetchCampaigns() {
  try {
    const params = {}
    if (campaignFilter.value) params.status_filter = campaignFilter.value
    const { data } = await api.get('/api/marketing/campaigns', { params })
    campaigns.value = data
  } catch (e) { console.error(e) }
}

async function submitCampaign() {
  const payload = { ...newCampaign }
  if (dateRange.value?.length === 2) {
    payload.start_date = dateRange.value[0]
    payload.end_date = dateRange.value[1]
  }
  try {
    await api.post('/api/marketing/campaigns', payload)
    ElMessage.success('活动创建成功')
    showCreateCampaign.value = false
    fetchCampaigns()
  } catch (e) { ElMessage.error('创建失败') }
}

async function toggleStatus(row, newStatus) {
  try {
    await api.put(`/api/marketing/campaigns/${row.id}/status`, { status: newStatus })
    row.status = newStatus
    ElMessage.success('状态已更新')
  } catch (e) { ElMessage.error('操作失败') }
}

async function executeCampaign(row) {
  try {
    const { data } = await api.post(`/api/marketing/campaigns/${row.id}/execute`)
    ElMessage.success(data.message)
    fetchCampaigns()
  } catch (e) { ElMessage.error('执行失败') }
}

async function runTriggers() {
  triggering.value = true
  try {
    const { data } = await api.post('/api/marketing/evaluate-triggers')
    ElMessage.success(data.message)
    fetchDashboard()
  } catch (e) { ElMessage.error('评估失败') }
  finally { triggering.value = false }
}

onMounted(() => {
  fetchDashboard()
  fetchCampaigns()
})
</script>

<style scoped>
.marketing-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.kpi-cards { display: flex; gap: 16px; }
.kpi-card { flex: 1; text-align: center; }
.kpi-value { font-size: 28px; font-weight: bold; color: #303133; }
.kpi-label { font-size: 14px; color: #909399; margin-top: 4px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
