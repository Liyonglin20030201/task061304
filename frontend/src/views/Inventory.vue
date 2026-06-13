<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>库存管理</span>
        <el-date-picker v-model="snapshotDate" type="date" placeholder="快照日期" size="small" @change="fetchData" />
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="item_id" label="商品编码" width="120" />
      <el-table-column prop="item_name" label="商品名称" />
      <el-table-column prop="category" label="品类" width="80" />
      <el-table-column prop="quantity" label="库存量" width="100" />
      <el-table-column prop="unit_cost" label="成本单价" width="100" />
      <el-table-column prop="total_value" label="库存金额" width="120" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'normal' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top: 16px; justify-content: flex-end;" v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="fetchData" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const items = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const snapshotDate = ref(null)

async function fetchData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (snapshotDate.value) params.snapshot_date = snapshotDate.value.toISOString().split('T')[0]
    const { data } = await api.get('/api/inventory', { params })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>
