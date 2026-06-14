import api from './index'

export const portEnergyApi = {
  getEquipment: () => api.get('/port/energy/equipment'),
  getEquipmentDetail: (id) => api.get(`/port/energy/equipment/${id}`),
  getEnergyHistory: (params) => api.get('/port/energy/history', { params }),
  getCostSummary: (params) => api.get('/port/energy/cost-summary', { params }),
  getPeakAnalysis: (params) => api.get('/port/energy/peak-analysis', { params }),
}

export const portCargoApi = {
  searchContainers: (params) => api.get('/port/cargo/containers', { params }),
  getContainer: (id) => api.get(`/port/cargo/containers/${id}`),
  createContainer: (data) => api.post('/port/cargo/containers', data),
  getContainerTrace: (id) => api.get(`/port/cargo/containers/${id}/trace`),
  addEvent: (containerId, data) => api.post(`/port/cargo/containers/${containerId}/events`, data),
  getStatistics: (params) => api.get('/port/cargo/statistics', { params }),
}

export const portSchedulingApi = {
  getPersonnel: (params) => api.get('/port/scheduling/personnel', { params }),
  createPersonnel: (data) => api.post('/port/scheduling/personnel', data),
  updatePersonnel: (id, data) => api.put(`/port/scheduling/personnel/${id}`, data),
  getShifts: () => api.get('/port/scheduling/shifts'),
  createShift: (data) => api.post('/port/scheduling/shifts', data),
  generateSchedule: (data) => api.post('/port/scheduling/generate', data),
  getSchedules: (params) => api.get('/port/scheduling/schedules', { params }),
  overrideSchedule: (id, data) => api.put(`/port/scheduling/schedules/${id}`, data),
  getConstraintViolations: (params) => api.get('/port/scheduling/violations', { params }),
  getTaskLoad: () => api.get('/port/scheduling/task-load'),
}

export const portAnalyticsApi = {
  getDashboardMetrics: (params) => api.get('/port/analytics/dashboard', { params }),
  getUtilization: (params) => api.get('/port/analytics/utilization', { params }),
  getThroughput: (params) => api.get('/port/analytics/throughput', { params }),
  generateReport: (data) => api.post('/port/analytics/reports', data),
  getReportTemplates: () => api.get('/port/analytics/templates'),
}
