<template>
  <div class="equipment-status-grid">
    <el-card v-for="item in equipment" :key="item.id" class="equip-card" :class="'status-' + getStatus(item.id)">
      <div class="equip-header">
        <span class="equip-code">{{ item.equipment_code }}</span>
        <el-tag :type="statusTagType(getStatus(item.id))" size="small">{{ statusLabel(getStatus(item.id)) }}</el-tag>
      </div>
      <div class="equip-name">{{ item.name }} ({{ item.equipment_type }})</div>
      <div class="equip-metrics">
        <div class="metric">
          <span class="metric-value">{{ getField(item.id, 'power_kw') }}</span>
          <span class="metric-label">kW</span>
        </div>
        <div class="metric">
          <span class="metric-value">{{ getField(item.id, 'voltage_v') }}</span>
          <span class="metric-label">V</span>
        </div>
        <div class="metric">
          <span class="metric-value">{{ getField(item.id, 'current_a') }}</span>
          <span class="metric-label">A</span>
        </div>
        <div class="metric">
          <span class="metric-value">{{ getCumKwh(item.id) }}</span>
          <span class="metric-label">kWh</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { usePortEnergyStore } from '../../stores/portEnergy'

const props = defineProps({
  equipment: { type: Array, default: () => [] },
})

const store = usePortEnergyStore()

function getStatus(id) {
  return store.readings[id]?.state || 'offline'
}

function getField(id, field) {
  const v = store.readings[id]?.[field]
  return v != null ? v : '--'
}

function getCumKwh(id) {
  const v = store.readings[id]?.cumulative_kwh
  return v != null ? v.toFixed(2) : '--'
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
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.equip-card { border-left: 3px solid #dcdfe6; }
.equip-card.status-lifting { border-left-color: #f56c6c; }
.equip-card.status-traversing { border-left-color: #e6a23c; }
.equip-card.status-rotating { border-left-color: #67c23a; }
.equip-card.status-idle { border-left-color: #909399; }
.equip-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.equip-code { font-weight: bold; font-size: 14px; }
.equip-name { font-size: 12px; color: #909399; margin-bottom: 12px; }
.equip-metrics { display: flex; gap: 12px; }
.metric { display: flex; flex-direction: column; align-items: center; }
.metric-value { font-size: 15px; font-weight: bold; color: #303133; }
.metric-label { font-size: 11px; color: #909399; }
</style>
