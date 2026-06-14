<template>
  <div class="equipment-status-grid">
    <el-card v-for="item in equipment" :key="item.id" class="equip-card" :class="'status-' + getStatus(item.id)">
      <div class="equip-header">
        <span class="equip-code">{{ item.equipment_code }}</span>
        <el-tag :type="statusTagType(getStatus(item.id))" size="small">{{ statusLabel(getStatus(item.id)) }}</el-tag>
      </div>
      <div class="equip-name">{{ item.name }}</div>
      <div class="equip-metrics">
        <div class="metric">
          <span class="metric-value">{{ getReading(item.id, 'power_kw') }}</span>
          <span class="metric-label">功率 kW</span>
        </div>
        <div class="metric">
          <span class="metric-value">{{ getReading(item.id, 'voltage') }}</span>
          <span class="metric-label">电压 V</span>
        </div>
        <div class="metric">
          <span class="metric-value">{{ getReading(item.id, 'current_amps') }}</span>
          <span class="metric-label">电流 A</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { usePortEnergyStore } from '../../stores/portEnergy'
import { computed } from 'vue'

const props = defineProps({
  equipment: { type: Array, default: () => [] },
})

const store = usePortEnergyStore()

function getStatus(id) {
  return store.readings[id]?.operational_state || 'offline'
}

function getReading(id, field) {
  return store.readings[id]?.[field] ?? '--'
}

function statusTagType(status) {
  const map = { idle: 'info', lifting: 'danger', traversing: 'warning', rotating: 'success', offline: '' }
  return map[status] || ''
}

function statusLabel(status) {
  const map = { idle: '空闲', lifting: '起吊', traversing: '行走', rotating: '旋转', offline: '离线' }
  return map[status] || status
}
</script>

<style scoped>
.equipment-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.equip-card {
  border-left: 3px solid #dcdfe6;
}
.equip-card.status-lifting { border-left-color: #f56c6c; }
.equip-card.status-traversing { border-left-color: #e6a23c; }
.equip-card.status-rotating { border-left-color: #67c23a; }
.equip-card.status-idle { border-left-color: #909399; }
.equip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.equip-code { font-weight: bold; font-size: 14px; }
.equip-name { font-size: 12px; color: #909399; margin-bottom: 12px; }
.equip-metrics { display: flex; gap: 16px; }
.metric { display: flex; flex-direction: column; align-items: center; }
.metric-value { font-size: 16px; font-weight: bold; color: #303133; }
.metric-label { font-size: 11px; color: #909399; }
</style>
