<template>
  <div class="yard-3d-view">
    <div class="controls-panel">
      <el-button-group>
        <el-button size="small" @click="setView('overview')">全景</el-button>
        <el-button size="small" @click="setView('berth')">泊位</el-button>
        <el-button size="small" @click="setView('yard')">堆场</el-button>
      </el-button-group>
      <div class="legend">
        <span class="legend-item"><i class="dot" style="background:#67c23a;"></i>在场</span>
        <span class="legend-item"><i class="dot" style="background:#e6a23c;"></i>在途</span>
        <span class="legend-item"><i class="dot" style="background:#f56c6c;"></i>提取</span>
        <span class="legend-item"><i class="dot" style="background:#ff6600;"></i>吊机</span>
        <span class="legend-item"><i class="dot" style="background:#00ccff;"></i>AGV</span>
      </div>
    </div>
    <ThreeYardScene
      :containers="containers"
      :equipment="equipment"
      :readings="energyStore.readings"
      @select-container="handleSelect"
    />
    <el-dialog v-model="detailVisible" :title="selectedContainer?.container_code" width="400px">
      <el-descriptions :column="2" border v-if="selectedContainer">
        <el-descriptions-item label="箱型">{{ selectedContainer.container_type }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ selectedContainer.status }}</el-descriptions-item>
        <el-descriptions-item label="船名">{{ selectedContainer.vessel_name || '--' }}</el-descriptions-item>
        <el-descriptions-item label="航次">{{ selectedContainer.voyage_no || '--' }}</el-descriptions-item>
        <el-descriptions-item label="位置">{{ yardPosition(selectedContainer) }}</el-descriptions-item>
        <el-descriptions-item label="重量">{{ selectedContainer.weight_tons || '--' }} t</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ThreeYardScene from '../../components/port/ThreeYardScene.vue'
import { usePortEnergyStore } from '../../stores/portEnergy'
import { usePortCargoStore } from '../../stores/portCargo'
import { portEnergyApi, portCargoApi } from '../../api/port'

const energyStore = usePortEnergyStore()
const detailVisible = ref(false)
const selectedContainer = ref(null)
const containers = ref([])
const equipment = ref([])

function handleSelect(container) {
  selectedContainer.value = container
  detailVisible.value = true
}

function yardPosition(c) {
  if (c.yard_block) return `${c.yard_block}-${c.yard_bay}-${c.yard_row}-${c.yard_tier}`
  return '--'
}

function setView(preset) {
  // View presets handled by ThreeYardScene internally via exposed method
}

onMounted(async () => {
  const [eqRes, cRes] = await Promise.all([
    portEnergyApi.getEquipment(),
    portCargoApi.searchContainers({ page_size: 100 }),
  ])
  equipment.value = eqRes.data.items
  containers.value = cRes.data.items
  energyStore.connect()
})
</script>

<style scoped>
.yard-3d-view { position: relative; height: calc(100vh - 140px); }
.controls-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  display: flex;
  gap: 16px;
  align-items: center;
  background: rgba(255,255,255,0.9);
  padding: 8px 12px;
  border-radius: 4px;
}
.legend { display: flex; gap: 12px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 4px; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
</style>
