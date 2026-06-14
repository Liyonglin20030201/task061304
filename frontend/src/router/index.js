import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    redirect: '/dashboard',
    component: () => import('../views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'sales', name: 'Sales', component: () => import('../views/Sales.vue') },
      { path: 'inventory', name: 'Inventory', component: () => import('../views/Inventory.vue') },
      { path: 'members', name: 'Members', component: () => import('../views/Members.vue') },
      { path: 'analytics', name: 'Analytics', component: () => import('../views/Analytics.vue') },
      { path: 'replenishment', name: 'Replenishment', component: () => import('../views/Replenishment.vue') },
      { path: 'site-selection', name: 'SiteSelection', component: () => import('../views/SiteSelection.vue') },
      { path: 'marketing', name: 'Marketing', component: () => import('../views/Marketing.vue') },
      { path: 'supply-chain', name: 'SupplyChain', component: () => import('../views/SupplyChain.vue') },
      { path: 'association', name: 'Association', component: () => import('../views/Association.vue') },
      { path: 'space-layout', name: 'SpaceLayout', component: () => import('../views/SpaceLayout.vue') },
      { path: 'omnichannel', name: 'Omnichannel', component: () => import('../views/Omnichannel.vue') },
      { path: 'store-energy', name: 'StoreEnergy', component: () => import('../views/StoreEnergy.vue') },
      { path: 'import', name: 'Import', component: () => import('../views/Import.vue') },
      { path: 'reports', name: 'Reports', component: () => import('../views/Reports.vue') },
      { path: 'tasks', name: 'TaskLogs', component: () => import('../views/TaskLogs.vue') },
      { path: 'port/energy', name: 'PortEnergy', component: () => import('../views/port/EnergyDashboard.vue') },
      { path: 'port/cargo', name: 'PortCargo', component: () => import('../views/port/CargoTrace.vue') },
      { path: 'port/scheduling', name: 'PortScheduling', component: () => import('../views/port/Scheduling.vue') },
      { path: 'port/analytics', name: 'PortAnalytics', component: () => import('../views/port/PortAnalytics.vue') },
      { path: 'port/yard-3d', name: 'PortYard3D', component: () => import('../views/port/YardView3D.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth !== false && !authStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
