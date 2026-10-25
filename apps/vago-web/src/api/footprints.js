import axios from 'axios'
import { configureHttp } from './http'

const http = axios.create({
  baseURL: '/api/v1/footprints',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

configureHttp(http, '读取足迹失败，请稍后重试')

// 统一足迹 API 同时返回自动 GPS 与手动打卡，避免 Web 拼接两个读模型。
export const footprintApi = {
  listTripFootprints: (tripUuid) => http.get(`/trips/${tripUuid}/footprints`),
}
