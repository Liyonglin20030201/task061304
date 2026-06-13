<template>
  <el-card>
    <template #header>任务日志</template>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="file_name" label="文件名" />
      <el-table-column prop="data_type" label="类型" width="90" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_rows" label="总行数" width="80" />
      <el-table-column prop="success_rows" label="成功" width="80" />
      <el-table-column prop="error_rows" label="错误" width="80" />
      <el-table-column prop="duplicate_rows" label="重复" width="80" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button text size="small" @click="showLogs(row.id)">查看日志</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="logDialogVisible" title="任务日志" width="600px">
      <el-timeline>
        <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="log.created_at" :type="log.level === 'error' ? 'danger' : 'primary'">
          {{ log.message }}
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const tasks = ref([])
const loading = ref(false)
const logs = ref([])
const logDialogVisible = ref(false)

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'processing') return 'warning'
  return 'info'
}

async function fetchTasks() {
  loading.value = true
  try {
    const { data } = await api.get('/api/tasks')
    tasks.value = data
  } finally {
    loading.value = false
  }
}

async function showLogs(taskId) {
  const { data } = await api.get(`/api/tasks/${taskId}/logs`)
  logs.value = data
  logDialogVisible.value = true
}

onMounted(fetchTasks)
</script>
