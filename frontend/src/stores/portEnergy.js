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
    lastSeq: 0,
    droppedFrames: 0,
    lastTickTs: 0,
    latencyMs: 0,
  }),

  actions: {
    connect() {
      const token = localStorage.getItem('token')
      if (!token) return
      if (this.ws && this.ws.readyState === WebSocket.OPEN) return

      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${location.host}/api/port/ws/energy?token=${token}`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.connected = true
        this.droppedFrames = 0
      }

      this.ws.onmessage = (event) => {
        const recvTs = Date.now()
        const msg = JSON.parse(event.data)
        if (msg.type === 'pong') return
        if (msg.type !== 'tick') return

        const { seq, ts, readings } = msg

        this.latencyMs = recvTs - ts
        if (this.lastSeq > 0 && seq > this.lastSeq + 1) {
          this.droppedFrames += (seq - this.lastSeq - 1)
        }
        this.lastSeq = seq
        this.lastTickTs = ts

        const newReadings = {}
        for (const r of readings) {
          newReadings[r.equipment_id] = r

          if (!this.trendBuffer[r.equipment_id]) {
            this.trendBuffer[r.equipment_id] = []
          }
          const buffer = this.trendBuffer[r.equipment_id]
          buffer.push([ts, r.power_kw])
          if (buffer.length > 300) buffer.splice(0, buffer.length - 300)
        }
        this.readings = newReadings
      }

      this.ws.onclose = () => {
        this.connected = false
        this.ws = null
        setTimeout(() => this.connect(), 2000)
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    },

    disconnect() {
      if (this.ws) {
        this.ws.close()
        this.ws = null
        this.connected = false
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
