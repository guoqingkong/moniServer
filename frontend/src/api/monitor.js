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
