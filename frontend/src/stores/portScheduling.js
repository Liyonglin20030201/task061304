import { defineStore } from 'pinia'
import { portSchedulingApi } from '../api/port'

export const usePortSchedulingStore = defineStore('portScheduling', {
  state: () => ({
    personnel: [],
    shifts: [],
    schedules: [],
    violations: [],
    generating: false,
  }),

  actions: {
    async fetchPersonnel(params) {
      const { data } = await portSchedulingApi.getPersonnel(params)
      this.personnel = data.items
    },

    async fetchShifts() {
      const { data } = await portSchedulingApi.getShifts()
      this.shifts = data.items
    },

    async fetchSchedules(params) {
      const { data } = await portSchedulingApi.getSchedules(params)
      this.schedules = data.items
    },

    async generateSchedule(params) {
      this.generating = true
      try {
        const { data } = await portSchedulingApi.generateSchedule(params)
        this.violations = data.violations || []
        return data
      } finally {
        this.generating = false
      }
    },

    async fetchViolations(params) {
      const { data } = await portSchedulingApi.getConstraintViolations(params)
      this.violations = data.items
    },
  },
})
