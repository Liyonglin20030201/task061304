<template>
  <el-card>
    <template #header>报表导出</template>
    <el-form :model="form" label-width="100px">
      <el-form-item label="报表类型">
        <el-select v-model="form.report_type">
          <el-option label="销售汇总" value="sales_summary" />
          <el-option label="库存状态" value="inventory_status" />
          <el-option label="综合报表" value="general" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期范围">
        <el-date-picker v-model="dateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" />
      </el-form-item>
      <el-form-item label="导出格式">
        <el-radio-group v-model="form.format">
          <el-radio label="excel">Excel</el-radio>
          <el-radio label="csv">CSV</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="exportReport" :loading="loading">生成报表</el-button>
      </el-form-item>
    </el-form>

    <el-divider v-if="reportResult">导出结果</el-divider>
    <div v-if="reportResult">
      <el-alert type="success" :title="`报表已生成: ${reportResult.file_name}`" show-icon />
      <el-button type="primary" text style="margin-top: 8px;" @click="downloadReport">下载报表</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const form = ref({ report_type: 'sales_summary', format: 'excel' })
const dateRange = ref(null)
const loading = ref(false)
const reportResult = ref(null)

async function exportReport() {
  if (!dateRange.value) {
    ElMessage.warning('请选择日期范围')
    return
  }
  loading.value = true
  try {
    const { data } = await api.post('/api/reports/export', {
      report_type: form.value.report_type,
      start_date: dateRange.value[0].toISOString().split('T')[0],
      end_date: dateRange.value[1].toISOString().split('T')[0],
      format: form.value.format,
    })
    reportResult.value = data
    ElMessage.success('报表生成成功')
  } catch (e) {
    ElMessage.error('报表生成失败')
  } finally {
    loading.value = false
  }
}

function downloadReport() {
  if (reportResult.value) {
    window.open(`/api/reports/${reportResult.value.report_id}/download`, '_blank')
  }
}
</script>
