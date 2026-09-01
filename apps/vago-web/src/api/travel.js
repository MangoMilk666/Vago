import axios from 'axios'

// ─── Axios 实例 ───────────────────────────────────────────────────────────────
const http = axios.create({
  baseURL: '/api/v1/travel',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

const knowledgeHttp = axios.create({
  baseURL: '/api/v1/knowledge',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动注入 Access Token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) config.headers['authorization'] = token
  return config
})

knowledgeHttp.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) config.headers['authorization'] = token
  return config
})

// 响应拦截器：统一处理 401 及业务错误码
http.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== 200) {
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      window.location.href = '/login'
    }
    const msg = error.response?.data?.message || '网络请求失败，请稍后重试'
    return Promise.reject(new Error(msg))
  }
)

knowledgeHttp.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== 200) {
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      window.location.href = '/login'
    }
    const msg = error.response?.data?.message || '网络请求失败，请稍后重试'
    return Promise.reject(new Error(msg))
  }
)

// ─── 行程 API ────────────────────────────────────────────────────────────────

export const tripApi = {
  list:    ()           => http.get('/trips'),
  history: ()           => http.get('/trips/history'),
  detail:  (uuid)       => http.get(`/trips/${uuid}`),
  create:  (data)       => http.post('/trips', data),
  update:  (uuid, data) => http.put(`/trips/${uuid}`, data),
  delete:  (uuid)       => http.delete(`/trips/${uuid}`),
}

// ─── 计划 API ────────────────────────────────────────────────────────────────

export const planApi = {
  list:      ()           => http.get('/plans'),
  detail:    (uuid)       => http.get(`/plans/${uuid}`),
  create:    (data)       => http.post('/plans', data),
  update:    (uuid, data) => http.put(`/plans/${uuid}`, data),
  delete:    (uuid)       => http.delete(`/plans/${uuid}`),
  /** 将计划转为正式行程 */
  convert:   (uuid)       => http.post(`/plans/${uuid}/convert`),
}

// ─── 每日行程 API ─────────────────────────────────────────────────────────────

export const itineraryApi = {
  /** 获取行程的全部每日规划 */
  getTripDays:  (tripUuid)           => http.get(`/trips/${tripUuid}/days`),
  /** 更新行程第 N 天 */
  updateTripDay: (tripUuid, dayIndex, data) =>
    http.put(`/trips/${tripUuid}/days/${dayIndex}`, data),

  /** 获取计划的全部每日规划 */
  getPlanDays:  (planUuid)           => http.get(`/plans/${planUuid}/days`),
  /** 更新计划第 N 天 */
  updatePlanDay: (planUuid, dayIndex, data) =>
    http.put(`/plans/${planUuid}/days/${dayIndex}`, data),
}

// ─── 攻略 API ────────────────────────────────────────────────────────────────

export const guideApi = {
  /** 公开攻略列表（分页，无需登录，独立路径） */
  listPublished: (page = 1, size = 20) =>
    http.get('/guides/discover', { params: { page, size } }),
  /** 我的攻略 */
  listMine:  ()           => knowledgeHttp.get('/guides/mine'),
  detail:    (uuid)       => http.get(`/guides/${uuid}`),
  mineDetail:(uuid)       => knowledgeHttp.get(`/guides/${uuid}`),
  create:    (data)       => knowledgeHttp.post('/guides', data),
  update:    (uuid, data) => knowledgeHttp.put(`/guides/${uuid}`, data),
  delete:    (uuid)       => knowledgeHttp.delete(`/guides/${uuid}`),
  like:      (uuid)       => http.post(`/guides/${uuid}/like`),
  unlike:    (uuid)       => http.delete(`/guides/${uuid}/like`),
  /** 手动触发向量化（加入 / 重试加入 AI 知识库） */
  index:     (uuid)       => knowledgeHttp.post(`/guides/${uuid}/index`),
}

// ─── 个人知识源 API ───────────────────────────────────────────────────────────
// 新 Knowledge Domain 仅管理用户自己的资料，不包含发现、点赞或收藏等社区语义。
export const knowledgeApi = {
  list: () => knowledgeHttp.get('/sources'),
  detail: (uuid) => knowledgeHttp.get(`/sources/${uuid}`),
  createText: (data) => knowledgeHttp.post('/sources', data),
  update: (uuid, data) => knowledgeHttp.put(`/sources/${uuid}`, data),
  delete: (uuid) => knowledgeHttp.delete(`/sources/${uuid}`),
  index: (uuid) => knowledgeHttp.post(`/sources/${uuid}/index`),
  uploadFile: (file, fields = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (fields.title) form.append('title', fields.title)
    if (fields.destination) form.append('destination', fields.destination)
    if (fields.tags?.length) form.append('tags', JSON.stringify(fields.tags))
    return knowledgeHttp.post('/sources/files', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// ─── 收藏夹 API ──────────────────────────────────────────────────────────────

export const collectionApi = {
  /** 获取当前用户的所有收藏夹列表 */
  list:      ()                        => http.get('/collections'),
  /** 创建收藏夹 */
  create:    (data)                    => http.post('/collections', data),
  /** 更新收藏夹（名称、描述） */
  update:    (data)                    => http.put('/collections', data),
  /** 删除收藏夹（含内部所有收藏记录） */
  delete:    (uuid)                    => http.delete(`/collections/${uuid}`),
  /** 获取某收藏夹内的攻略列表 */
  guideList: (uuid)                    => http.get(`/collections/${uuid}/items`),
  /** 查询某攻略被当前用户收藏到哪些收藏夹 */
  check:     (guideUuid)               => http.get('/collections/items/check', { params: { guideUuid } }),
  /** 收藏攻略到指定收藏夹 */
  saveInto:  (data)                    => http.post('/collections/items', data),
  /** 从收藏夹移除指定攻略 */
  removeItem:(collectionUuid, guideUuid) => http.delete(`/collections/${collectionUuid}/items/${guideUuid}`),
}
