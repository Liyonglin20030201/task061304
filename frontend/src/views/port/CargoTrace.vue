<template>
  <div class="cargo-trace">
    <el-row :gutter="16" class="stats-row" v-if="store.statistics">
      <el-col :span="6"><el-statistic title="集装箱总数" :value="store.statistics.total_containers" /></el-col>
      <el-col :span="6"><el-statistic title="在途" :value="store.statistics.en_route" /></el-col>
      <el-col :span="6"><el-statistic title="在场" :value="store.statistics.stacked" /></el-col>
      <el-col :span="6"><el-statistic title="平均滞留(时)" :value="Math.round(store.statistics.avg_dwell_hours)" /></el-col>
    </el-row>

    <el-card style="margin-top: 16px;">
      <template #header>
        <div class="search-header">
          <span>货物追溯</span>
          <div class="search-controls">
            <el-input v-model="searchForm.keyword" placeholder="箱号/提单号" clearable style="width: 180px;" @keyup.enter="doSearch" />
            <el-input v-model="searchForm.vessel" placeholder="船名" clearable style="width: 140px;" />
            <el-select v-model="searchForm.status" placeholder="状态" clearable style="width: 120px;">
              <el-option label="在途" value="en_route" />
              <el-option label="到港" value="arrived" />
              <el-option label="在场" value="stacked" />
              <el-option label="提取中" value="retrieving" />
              <el-option label="已离港" value="departed" />
            </el-select>
            <el-button type="primary" @click="doSearch">搜索</el-button>
          </div>
        </div>
      </template>

      <el-table :data="store.containers" v-loading="store.loading" stripe @row-click="showTrace">
        <el-table-column prop="container_code" label="箱号" width="140" />
        <el-table-column prop="container_type" label="箱型" width="80" />
        <el-table-column prop="vessel_name" label="船名" width="140" />
        <el-table-column prop="voyage_no" label="航次" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="yard_block" label="堆场位置" width="120">
          <template #default="{ row }">
            {{ row.yard_block ? `${row.yard_block}-${row.yard_bay}-${row.yard_row}-${row.yard_tier}` : '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="arrival_time" label="到港时间" width="160">
          <template #default="{ row }">{{ formatTime(row.arrival_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showTrace(row)">追溯</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="store.total > 20"
        style="margin-top: 16px; justify-content: flex-end;"
        :current-page="searchForm.page"
        :page-size="20"
        :total="store.total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-drawer v-model="drawerVisible" :title="traceTitle" size="450px">
      <ContainerTimeline :events="store.traceEvents" />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { usePortCargoStore } from '../../stores/portCargo'
import ContainerTimeline from '../../components/port/ContainerTimeline.vue'

const store = usePortCargoStore()
const drawerVisible = ref(false)
const traceTitle = ref('')

const searchForm = reactive({
  keyword: '',
  vessel: '',
  status: '',
  page: 1,
})

const STATUS_MAP = {
  en_route: { label: '在途', type: 'info' },
  arrived: { label: '到港', type: '' },
  stacked: { label: '在场', type: 'success' },
  retrieving: { label: '提取中', type: 'warning' },
  departed: { label: '已离港', type: 'danger' },
}

function statusLabel(s) { return STATUS_MAP[s]?.label || s }
function statusType(s) { return STATUS_MAP[s]?.type || '' }
function formatTime(t) { return t ? new Date(t).toLocaleString('zh-CN') : '--' }

async function doSearch() {
  searchForm.page = 1
  await store.searchContainers(searchForm)
}

function handlePageChange(page) {
  searchForm.page = page
  store.searchContainers(searchForm)
}

async function showTrace(row) {
  traceTitle.value = `追溯: ${row.container_code}`
  await store.getTrace(row.id)
  drawerVisible.value = true
}

onMounted(async () => {
  await store.fetchStatistics()
  await doSearch()
})
</script>

<style scoped>
.stats-row { background: #fff; padding: 20px; border-radius: 4px; }
.search-header { display: flex; justify-content: space-between; align-items: center; }
.search-controls { display: flex; gap: 8px; align-items: center; }
</style>
