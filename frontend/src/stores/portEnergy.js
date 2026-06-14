import { defineStore } from 'pinia'
import { portEnergyApi } from '../api/port'

export const usePortEnergyStore = defineStore('portEnergy', {
  state: () => ({
    ws: null,
    connected: false,
    equipmentList: [],
    readings: {},
    historyData: [],
    costSummary: [],
    trendBuffer: {},
  }),

  actions: {
    connect() {
      const token = localStorage.getItem('token')
      if (!token) return

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${location.host}/api/port/ws/energy?token=${token}`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.connected = true
      }

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'pong') return

        this.readings[data.equipment_id] = data

        if (!this.trendBuffer[data.equipment_id]) {
          this.trendBuffer[data.equipment_id] = []
        }
        const buffer = this.trendBuffer[data.equipment_id]
        buffer.push({ time: data.timestamp, power: data.power_kw })
        if (buffer.length > 300) buffer.shift()
      }

      this.ws.onclose = () => {
        this.connected = false
        setTimeout(() => this.connect(), 3000)
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    },

    disconnect() {
      if (this.ws) {
        this.ws.close()
        this.ws = null
      }
    },

    async fetchEquipment() {
      const { data } = await portEnergyApi.getEquipment()
      this.equipmentList = data.items
    },

    async fetchHistory(params) {
      const { data } = await portEnergyApi.getEnergyHistory(params)
      this.historyData = data.items
    },

    async fetchCostSummary(params) {
      const { data } = await portEnergyApi.getCostSummary(params)
      this.costSummary = data.items
    },
  },
})
