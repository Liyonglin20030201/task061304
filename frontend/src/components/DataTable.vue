<template>
  <el-table :data="data" v-bind="$attrs" stripe>
    <slot />
  </el-table>
</template>

<script setup>
defineProps({
  data: { type: Array, default: () => [] },
})
</script>
