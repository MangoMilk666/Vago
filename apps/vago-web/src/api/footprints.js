import axios from 'axios'

const http = axios.create({
  baseURL: '/api/v1/footprints',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) config.headers.authorization = token
  return config
})

http.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== 200) return Promise.reject(new Error(data.message || '请求失败'))
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      window.location.href = '/login'
    }
    return Promise.reject(new Error(error.response?.data?.message || '读取足迹失败，请稍后重试'))
  },
)

// 统一足迹 API 同时返回自动 GPS 与手动打卡，避免 Web 拼接两个读模型。
export const footprintApi = {
  listTripFootprints: (tripUuid) => http.get(`/trips/${tripUuid}/footprints`),
}
