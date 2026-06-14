import { defineStore } from 'pinia'
import { portCargoApi } from '../api/port'

export const usePortCargoStore = defineStore('portCargo', {
  state: () => ({
    containers: [],
    total: 0,
    currentContainer: null,
    traceEvents: [],
    statistics: null,
    loading: false,
  }),

  actions: {
    async searchContainers(params) {
      this.loading = true
      try {
        const { data } = await portCargoApi.searchContainers(params)
        this.containers = data.items
        this.total = data.total
      } finally {
        this.loading = false
      }
    },

    async getContainer(id) {
      const { data } = await portCargoApi.getContainer(id)
      this.currentContainer = data
    },

    async getTrace(id) {
      const { data } = await portCargoApi.getContainerTrace(id)
      this.traceEvents = data.items
    },

    async fetchStatistics() {
      const { data } = await portCargoApi.getStatistics()
      this.statistics = data
    },
  },
})
