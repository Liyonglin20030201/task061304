<template>
  <div class="schedule-calendar">
    <div class="calendar-grid">
      <div class="calendar-header">
        <div class="header-cell time-cell">班次</div>
        <div class="header-cell" v-for="d in dateRange" :key="d">{{ formatDate(d) }}</div>
      </div>
      <div class="calendar-row" v-for="shift in shifts" :key="shift.id">
        <div class="row-label">{{ shift.shift_name }}</div>
        <div class="day-cell" v-for="d in dateRange" :key="d + '-' + shift.id">
          <el-tag
            v-for="assignment in getAssignments(d, shift.id)"
            :key="assignment.id"
            :type="tagType(assignment.position)"
            size="small"
            class="assignment-tag"
          >
            {{ assignment.personnel_name }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  schedules: { type: Array, default: () => [] },
  shifts: { type: Array, default: () => [] },
  startDate: { type: String, required: true },
  endDate: { type: String, required: true },
})

const dateRange = computed(() => {
  const dates = []
  const start = new Date(props.startDate)
  const end = new Date(props.endDate)
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    dates.push(d.toISOString().split('T')[0])
  }
  return dates
})

function formatDate(d) {
  const date = new Date(d)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function getAssignments(dateStr, shiftId) {
  return props.schedules.filter(s => s.schedule_date === dateStr && s.shift_id === shiftId)
}

function tagType(position) {
  const map = { crane_operator: 'danger', agv_driver: 'warning', yard_planner: 'success', inspector: 'info' }
  return map[position] || ''
}
</script>

<style scoped>
.calendar-grid { overflow-x: auto; }
.calendar-header { display: flex; border-bottom: 2px solid #dcdfe6; padding-bottom: 8px; margin-bottom: 8px; }
.header-cell { min-width: 100px; font-weight: bold; font-size: 13px; text-align: center; }
.time-cell { min-width: 80px; text-align: left; }
.calendar-row { display: flex; min-height: 60px; border-bottom: 1px solid #ebeef5; padding: 8px 0; }
.row-label { min-width: 80px; font-weight: 500; font-size: 13px; display: flex; align-items: center; }
.day-cell { min-width: 100px; display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; align-items: flex-start; }
.assignment-tag { margin: 1px; }
</style>
