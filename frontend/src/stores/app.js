import { defineStore } from 'pinia'
import api from '../api'

export const useAppStore = defineStore('app', {
  state: () => ({
    stores: [],
    selectedStoreIds: [],
    loading: false,
  }),
  actions: {
    async fetchStores() {
      const { data } = await api.get('/api/stores')
      this.stores = data
    },
    setSelectedStores(ids) {
      this.selectedStoreIds = ids
    },
  },
})
