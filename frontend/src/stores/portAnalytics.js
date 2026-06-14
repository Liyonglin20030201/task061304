import { defineStore } from 'pinia'
import { portAnalyticsApi } from '../api/port'

export const usePortAnalyticsStore = defineStore('portAnalytics', {
  state: () => ({
    dashboard: null,
    utilization: [],
    throughput: [],
    loading: false,
  }),

  actions: {
    async fetchDashboard() {
      const { data } = await portAnalyticsApi.getDashboardMetrics()
      this.dashboard = data
    },

    async fetchUtilization(params) {
      const { data } = await portAnalyticsApi.getUtilization(params)
      this.utilization = data.items
    },

    async fetchThroughput(params) {
      const { data } = await portAnalyticsApi.getThroughput(params)
      this.throughput = data.items
    },
  },
})
