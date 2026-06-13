<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>销售数据</span>
        <div style="display: flex; gap: 10px;">
          <el-date-picker v-model="dateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" size="small" />
          <el-select v-model="category" placeholder="品类" clearable size="small" style="width: 120px;">
            <el-option label="全部" value="" />
            <el-option label="食品" value="食品" />
            <el-option label="饮料" value="饮料" />
            <el-option label="日用品" value="日用品" />
          </el-select>
          <el-button type="primary" size="small" @click="fetchData">查询</el-button>
        </div>
      </div>
    </template>
    <el-table :data="sales" v-loading="loading" stripe>
      <el-table-column prop="sale_date" label="日期" width="110" />
      <el-table-column prop="receipt_no" label="单号" width="130" />
      <el-table-column prop="item_name" label="商品" />
      <el-table-column prop="category" label="品类" width="80" />
      <el-table-column prop="quantity" label="数量" width="70" />
      <el-table-column prop="unit_price" label="单价" width="80" />
      <el-table-column prop="total_amount" label="金额" width="100" />
      <el-table-column prop="payment_method" label="支付方式" width="100" />
    </el-table>
    <el-pagination style="margin-top: 16px; justify-content: flex-end;" v-model:current-page="page" :page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="fetchData" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const sales = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dateRange = ref(null)
const category = ref('')

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (dateRange.value) {
      params.start_date = dateRange.value[0].toISOString().split('T')[0]
      params.end_date = dateRange.value[1].toISOString().split('T')[0]
    }
    if (category.value) params.category = category.value
    const { data } = await api.get('/api/sales', { params })
    sales.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>
