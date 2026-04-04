import axios from 'axios'

const http = axios.create({
  baseURL: '/',
  timeout: 15000,
})

export async function fetchMonitorConfig() {
  const { data } = await http.get('/api/monitor/config')
  return data
}

export async function fetchDashboard(params) {
  const { data } = await http.get('/api/monitor/dashboard', { params })
  return data
}

export async function fetchCosDashboard(params) {
  const { data } = await http.get('/api/monitor/cos/dashboard', { params })
  return data
}

export async function fetchRecentAlerts(params) {
  const { data } = await http.get('/api/monitor/alerts/recent', { params })
  return data
}

export async function fetchMetricComparison(params) {
  const { data } = await http.get('/api/monitor/compare', { params })
  return data
}

export async function fetchMetricHistory(params) {
  const { data } = await http.get('/api/monitor/history', { params })
  return data
}

export async function fetchCollectorStatus() {
  const { data } = await http.get('/api/monitor/collector/status')
  return data
}
