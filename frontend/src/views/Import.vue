<template>
  <el-card>
    <template #header>数据导入</template>
    <el-upload
      drag
      :action="uploadUrl"
      :headers="headers"
      :data="{ data_type: dataType }"
      :on-success="handleSuccess"
      :on-error="handleError"
      :before-upload="beforeUpload"
    >
      <el-icon style="font-size: 40px; color: #c0c4cc;"><Upload /></el-icon>
      <div style="margin-top: 8px;">拖拽文件到此处，或<em>点击上传</em></div>
      <template #tip>
        <div style="color: #909399;">支持 CSV、Excel 文件，最大 200MB</div>
      </template>
    </el-upload>

    <el-form inline style="margin-top: 20px;">
      <el-form-item label="数据类型">
        <el-select v-model="dataType" size="default">
          <el-option label="销售数据" value="sales" />
          <el-option label="库存数据" value="inventory" />
          <el-option label="会员数据" value="members" />
          <el-option label="促销活动" value="promotions" />
          <el-option label="客流数据" value="traffic" />
          <el-option label="天气数据" value="weather" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-divider>导入历史</el-divider>
    <el-table :data="history" size="small">
      <el-table-column prop="file_name" label="文件名" />
      <el-table-column prop="data_type" label="类型" width="100" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_rows" label="总行数" width="80" />
      <el-table-column prop="success_rows" label="成功" width="80" />
      <el-table-column prop="error_rows" label="错误" width="80" />
      <el-table-column prop="created_at" label="时间" width="180" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const dataType = ref('sales')
const history = ref([])
const uploadUrl = '/api/imports/upload'
const headers = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'processing') return 'warning'
  return 'info'
}

function beforeUpload(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['csv', 'xlsx', 'xls'].includes(ext)) {
    ElMessage.error('仅支持 CSV 和 Excel 文件')
    return false
  }
  if (file.size > 200 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过200MB')
    return false
  }
  return true
}

function handleSuccess(res) {
  ElMessage.success('上传成功，正在后台处理')
  loadHistory()
}

function handleError() {
  ElMessage.error('上传失败')
}

async function loadHistory() {
  const { data } = await api.get('/api/imports/history')
  history.value = data
}

onMounted(loadHistory)
</script>
