<template>
  <div class="scheduling-view">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>智能排班</span>
          <div class="header-actions">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 280px;" />
            <el-button type="primary" :loading="store.generating" @click="handleGenerate">生成排班</el-button>
            <el-button @click="handleRefresh">刷新</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="排班日历" name="calendar">
          <ScheduleCalendar
            v-if="dateRange"
            :schedules="store.schedules"
            :shifts="store.shifts"
            :start-date="dateRange[0]"
            :end-date="dateRange[1]"
          />
          <el-empty v-else description="请选择日期范围" />
        </el-tab-pane>

        <el-tab-pane label="人员管理" name="personnel">
          <el-table :data="store.personnel" stripe>
            <el-table-column prop="employee_code" label="工号" width="100" />
            <el-table-column prop="name" label="姓名" width="100" />
            <el-table-column prop="position" label="岗位" width="120">
              <template #default="{ row }">
                <el-tag :type="positionType(row.position)" size="small">{{ positionLabel(row.position) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="shift_preference" label="偏好" width="80">
              <template #default="{ row }">{{ prefLabel(row.shift_preference) }}</template>
            </el-table-column>
            <el-table-column prop="max_continuous_hours" label="最大连续工时" width="120" />
            <el-table-column prop="min_rest_hours" label="最少休息时间" width="120" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '在岗' : '离岗' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="约束冲突" name="violations">
          <el-alert v-if="store.violations.length === 0" title="无约束冲突" type="success" :closable="false" />
          <el-table v-else :data="store.violations" stripe>
            <el-table-column prop="schedule_date" label="日期" width="120" />
            <el-table-column prop="constraint_type" label="冲突类型" width="140">
              <template #default="{ row }">
                <el-tag type="warning" size="small">{{ constraintLabel(row.constraint_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="personnel_name" label="相关人员" width="100" />
            <el-table-column prop="resolution" label="解决方案" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usePortSchedulingStore } from '../../stores/portScheduling'
import ScheduleCalendar from '../../components/port/ScheduleCalendar.vue'

const store = usePortSchedulingStore()
const activeTab = ref('calendar')
const dateRange = ref(null)

const POSITION_MAP = { crane_operator: '吊机操作员', agv_driver: 'AGV驾驶员', yard_planner: '堆场计划员', inspector: '检验员' }
const PREF_MAP = { day: '白班', night: '夜班', flexible: '灵活' }
const CONSTRAINT_MAP = { max_hours: '超时', rest_violation: '休息不足', skill_mismatch: '技能不符', infeasible: '无可行解', no_eligible: '人员不足' }

function positionLabel(p) { return POSITION_MAP[p] || p }
function positionType(p) { return { crane_operator: 'danger', agv_driver: 'warning', yard_planner: 'success', inspector: 'info' }[p] || '' }
function prefLabel(p) { return PREF_MAP[p] || p }
function constraintLabel(c) { return CONSTRAINT_MAP[c] || c }

async function handleGenerate() {
  if (!dateRange.value) {
    ElMessage.warning('请先选择日期范围')
    return
  }
  const result = await store.generateSchedule({
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
  })
  if (result.error) {
    ElMessage.error(result.error)
  } else {
    ElMessage.success(`排班生成完成，共${result.schedules?.length || 0}条分配`)
    await handleRefresh()
  }
}

async function handleRefresh() {
  if (dateRange.value) {
    await store.fetchSchedules({ start_date: dateRange.value[0], end_date: dateRange.value[1] })
    await store.fetchViolations({ start_date: dateRange.value[0], end_date: dateRange.value[1] })
  }
}

onMounted(async () => {
  await store.fetchPersonnel({})
  await store.fetchShifts()
  const today = new Date()
  const nextWeek = new Date(today)
  nextWeek.setDate(today.getDate() + 6)
  dateRange.value = [today.toISOString().split('T')[0], nextWeek.toISOString().split('T')[0]]
  await handleRefresh()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; gap: 8px; align-items: center; }
</style>
