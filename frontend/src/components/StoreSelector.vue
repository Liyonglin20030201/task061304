<template>
  <el-select
    v-model="selectedStores"
    multiple
    collapse-tags
    collapse-tags-tooltip
    placeholder="选择门店"
    size="small"
    style="width: 280px;"
    @change="handleChange"
  >
    <el-option v-for="store in stores" :key="store.id" :label="store.name" :value="store.id" />
  </el-select>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()
const stores = computed(() => appStore.stores)
const selectedStores = ref([])

onMounted(() => {
  appStore.fetchStores()
})

function handleChange(val) {
  appStore.setSelectedStores(val)
}
</script>
