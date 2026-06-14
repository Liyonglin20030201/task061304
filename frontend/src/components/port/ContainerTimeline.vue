<template>
  <div class="container-timeline">
    <el-timeline>
      <el-timeline-item
        v-for="event in events"
        :key="event.id"
        :timestamp="formatTime(event.event_time)"
        :type="eventColor(event.event_type)"
        :hollow="false"
        placement="top"
      >
        <el-card shadow="never" class="timeline-card">
          <div class="event-header">
            <el-tag :type="eventColor(event.event_type)" size="small">{{ eventLabel(event.event_type) }}</el-tag>
            <span class="event-location" v-if="event.location">{{ event.location }}</span>
          </div>
          <div class="event-details" v-if="event.equipment_id || event.operator_id">
            <span v-if="event.equipment_id">设备ID: {{ event.equipment_id }}</span>
            <span v-if="event.operator_id">操作员ID: {{ event.operator_id }}</span>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-if="!events.length" description="暂无追溯记录" />
  </div>
</template>

<script setup>
const props = defineProps({
  events: { type: Array, default: () => [] },
})

const EVENT_LABELS = {
  vessel_arrival: '船舶到港',
  discharge: '卸船',
  gate_in: '进闸',
  stack: '堆放',
  restack: '翻箱',
  retrieve: '提箱',
  load: '装船',
  gate_out: '出闸',
  inspection: '查验',
}

const EVENT_COLORS = {
  vessel_arrival: 'primary',
  discharge: 'success',
  gate_in: 'info',
  stack: 'success',
  restack: 'warning',
  retrieve: 'warning',
  load: 'danger',
  gate_out: 'info',
  inspection: '',
}

function eventLabel(type) {
  return EVENT_LABELS[type] || type
}

function eventColor(type) {
  return EVENT_COLORS[type] || ''
}

function formatTime(time) {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped>
.container-timeline { padding: 16px; }
.timeline-card { margin-bottom: 0; }
.event-header { display: flex; align-items: center; gap: 12px; }
.event-location { font-size: 12px; color: #909399; }
.event-details { margin-top: 8px; font-size: 12px; color: #606266; display: flex; gap: 16px; }
</style>
