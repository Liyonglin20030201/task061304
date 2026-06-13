<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>会员管理</span>
        <div style="display: flex; gap: 10px;">
          <el-input v-model="keyword" placeholder="搜索姓名/手机号" size="small" style="width: 180px;" clearable @clear="fetchData" />
          <el-select v-model="rfmSegment" placeholder="RFM分群" clearable size="small" style="width: 140px;" @change="fetchData">
            <el-option label="重要价值客户" value="重要价值客户" />
            <el-option label="重要保持客户" value="重要保持客户" />
            <el-option label="一般价值客户" value="一般价值客户" />
            <el-option label="流失客户" value="流失客户" />
          </el-select>
          <el-button type="primary" size="small" @click="fetchData">查询</el-button>
        </div>
      </div>
    </template>
    <el-table :data="members" v-loading="loading" stripe>
      <el-table-column prop="member_no" label="会员号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column prop="gender" label="性别" width="60" />
      <el-table-column prop="level" label="等级" width="80" />
      <el-table-column prop="total_points" label="积分" width="80" />
      <el-table-column prop="rfm_segment" label="RFM分群" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.rfm_segment || '未分群' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="register_date" label="注册日期" width="110" />
    </el-table>
    <el-pagination style="margin-top: 16px; justify-content: flex-end;" v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="fetchData" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const members = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const keyword = ref('')
const rfmSegment = ref('')

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (keyword.value) params.keyword = keyword.value
    if (rfmSegment.value) params.rfm_segment = rfmSegment.value
    const { data } = await api.get('/api/members', { params })
    members.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>
