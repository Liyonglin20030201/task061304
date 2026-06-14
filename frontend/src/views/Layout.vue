<template>
  <el-container style="min-height: 100vh;">
    <el-aside width="220px" style="background: #304156;">
      <div style="padding: 20px; color: #fff; text-align: center; font-size: 14px; font-weight: bold;">
        门店数据分析平台
      </div>
      <el-menu :default-active="$route.path" router background-color="#304156" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><DataAnalysis /></el-icon><span>数据概览</span></el-menu-item>
        <el-menu-item index="/sales"><el-icon><ShoppingCart /></el-icon><span>销售数据</span></el-menu-item>
        <el-menu-item index="/inventory"><el-icon><Box /></el-icon><span>库存管理</span></el-menu-item>
        <el-menu-item index="/members"><el-icon><User /></el-icon><span>会员管理</span></el-menu-item>
        <el-menu-item index="/analytics"><el-icon><TrendCharts /></el-icon><span>智能分析</span></el-menu-item>
        <el-menu-item index="/replenishment"><el-icon><SetUp /></el-icon><span>智能补货</span></el-menu-item>
        <el-menu-item index="/site-selection"><el-icon><MapLocation /></el-icon><span>选址分析</span></el-menu-item>
        <el-menu-item index="/marketing"><el-icon><Promotion /></el-icon><span>营销自动化</span></el-menu-item>
        <el-menu-item index="/supply-chain"><el-icon><Connection /></el-icon><span>供应链协同</span></el-menu-item>
        <el-menu-item index="/association"><el-icon><Share /></el-icon><span>商品关联分析</span></el-menu-item>
        <el-menu-item index="/space-layout"><el-icon><Grid /></el-icon><span>空间布局优化</span></el-menu-item>
        <el-menu-item index="/omnichannel"><el-icon><Monitor /></el-icon><span>全渠道整合</span></el-menu-item>
        <el-menu-item index="/store-energy"><el-icon><Lightning /></el-icon><span>能耗智能监控</span></el-menu-item>
        <el-menu-item index="/import"><el-icon><Upload /></el-icon><span>数据导入</span></el-menu-item>
        <el-menu-item index="/reports"><el-icon><Document /></el-icon><span>报表导出</span></el-menu-item>
        <el-menu-item index="/tasks"><el-icon><List /></el-icon><span>任务日志</span></el-menu-item>
        <el-sub-menu index="port">
          <template #title><el-icon><Ship /></el-icon><span>港口作业</span></template>
          <el-menu-item index="/port/energy">能耗监控</el-menu-item>
          <el-menu-item index="/port/cargo">货物追溯</el-menu-item>
          <el-menu-item index="/port/scheduling">智能排班</el-menu-item>
          <el-menu-item index="/port/analytics">数据分析</el-menu-item>
          <el-menu-item index="/port/yard-3d">3D堆场</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: space-between; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.1);">
        <store-selector />
        <div style="display: flex; align-items: center; gap: 12px;">
          <span>{{ authStore.user?.full_name || authStore.user?.username }}</span>
          <el-button text @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main style="background: #f0f2f5; padding: 20px;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import StoreSelector from '../components/StoreSelector.vue'

const router = useRouter()
const authStore = useAuthStore()

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
