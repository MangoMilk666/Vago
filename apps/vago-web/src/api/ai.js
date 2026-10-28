import axios from 'axios'
import { getCsrfToken } from '../stores/auth'
import { configureHttp, handleUnauthorized } from './http'

// ─── Axios 实例（非流式接口） ──────────────────────────────────────────────────
const http = axios.create({
  baseURL: '/api/v1/ai',
  timeout: 60000, // AI 生成可能较慢，超时设 60 秒
  headers: { 'Content-Type': 'application/json' },
})

configureHttp(http)

// ─── AI API ─────────────────────────────────────────────────────────────────

export const aiApi = {
  /**
   * 非流式对话：等待完整回答后返回。
   * @param {Array<{role: string, content: string}>} messages 完整消息历史
   */
  chat: (messages, useRag = true, usePersonalContext = false) => (
    http.post('/chat', { messages, useRag, usePersonalContext })
  ),

  /**
   * 保存 AI 生成的结构化行程为草稿计划。
   * @param {Object} planData 计划数据
   */
  saveDraft: (planData) => http.post('/plans/save-draft', planData),

  /**
   * 保存 AI 生成的结构化行程为正式行程。
   * @param {Object} planData 行程数据
   */
  saveTrip: (planData) => http.post('/plans/save-trip', planData),

  /**
   * 读取 Web Agent 本轮可用的 Personal Travel Context 摘要。
   * 返回内容不含 GPS 经纬度或模型内部 Prompt，仅用于用户核对授权范围。
   */
  contextPreview: async (usePersonalContext = true, useRag = true) => {
    const params = new URLSearchParams({
      usePersonalContext: String(usePersonalContext),
      useRag: String(useRag),
    })
    const response = await fetch(`/api/v1/agent/context-preview?${params}`, {
      credentials: 'same-origin',
    })
    if (response.status === 401) handleUnauthorized()
    const body = await response.json()
    if (!response.ok || body.code !== 200) {
      throw new Error(body.message || '读取旅行上下文失败')
    }
    return body.data
  },

  /**
   * 流式对话（SSE）：返回 fetch Response，调用方自行消费 ReadableStream。
   *
   * SSE 事件格式（每行 `data: <json>\n\n`）：
   *   {"type": "text",            "content": "..."}  — 文本 token（逐字追加）
   *   {"type": "context",         "labels":  [...]}   — 本轮读取的个人上下文类别
   *   {"type": "searching",       "query":   "..."}  — Agent 正在检索
   *   {"type": "sources",         "sources": [...]}  — 引用来源列表
   *   {"type": "extracting_plan"}                     — 文本回答完毕，正在提取结构化行程
   *   {"type": "structured_plan", "data":    {...}}  — 结构化行程数据
   *   {"type": "error",           "message": "..."}  — 生成错误
   *   [DONE]                                         — 流结束信号
   *
   * @param {Array<{role: string, content: string}>} messages 完整消息历史
   * @param {AbortSignal} [signal] 可选：用于超时/取消的 AbortSignal
   * @returns {Promise<Response>} fetch Response，body 为 SSE 流
   */
  chatStream: (
    messages,
    signal,
    useRag = true,
    usePersonalContext = false,
    conversationUuid = null,
  ) => {
    return fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken() ?? '',
      },
      credentials: 'same-origin',
      body: JSON.stringify({ messages, useRag, usePersonalContext, conversationUuid }),
      ...(signal ? { signal } : {}),
    }).then((response) => {
      if (response.status === 401) handleUnauthorized()
      return response
    })
  },

  /** 读取当前用户保存的 Agent 会话，用于左侧会话栏。 */
  conversations: () => http.get('/agent/conversations', { baseURL: '/api/v1' }),

  /** 创建一段独立对话；首条用户消息会由服务端生成摘要标题。 */
  createConversation: (payload) => http.post('/agent/conversations', payload, { baseURL: '/api/v1' }),

  /** 获取最近一页或指定游标之前的历史消息。 */
  conversationMessages: (conversationUuid, beforeUuid = null) => http.get(
    `/agent/conversations/${conversationUuid}/messages`,
    {
      baseURL: '/api/v1',
      params: beforeUuid ? { beforeUuid } : {},
    },
  ),

  /** 更新用户为会话指定的标题。 */
  updateConversation: (conversationUuid, payload) => http.patch(
    `/agent/conversations/${conversationUuid}`,
    payload,
    { baseURL: '/api/v1' },
  ),

  /** 删除一整段 Agent 会话及其已保存的消息。 */
  deleteConversation: (conversationUuid) => http.delete(
    `/agent/conversations/${conversationUuid}`,
    { baseURL: '/api/v1' },
  ),

  /** 在中国大陆查询规划地点；密钥由 FastAPI 保存并调用高德。 */
  searchPlanningPlaces: (city, query) => http.post(
    '/agent/planning/places/search',
    { countryCode: 'CN', city, query },
    { baseURL: '/api/v1' },
  ),

  /** 使用已选地点的高德坐标查询可选路线。 */
  searchPlanningRoutes: (city, mode, origin, destination) => http.post(
    '/agent/planning/routes/search',
    {
      countryCode: 'CN', city, mode,
      fromItemId: origin.id, toItemId: destination.id,
      originLatitude: origin.latitude, originLongitude: origin.longitude,
      destinationLatitude: destination.latitude, destinationLongitude: destination.longitude,
      coordinateSystem: 'GCJ-02',
      ...(origin.cityCode ? { cityCode: origin.cityCode } : {}),
    },
    { baseURL: '/api/v1' },
  ),

  /** 高德静态地图由服务端代取，不向浏览器暴露 Web 服务 Key。 */
  planningRoutePreview: (routeChoiceId) => http.post(
    '/agent/planning/routes/preview',
    { routeChoiceId },
    { baseURL: '/api/v1', responseType: 'blob' },
  ),

  /** 将已选路线和用户填写的时间保存为当前 Agent 会话的候选版本。 */
  createPlanningProposal: (conversationUuid, payload) => http.post(
    `/agent/conversations/${conversationUuid}/proposals`, payload, { baseURL: '/api/v1' },
  ),
  planningProposals: (conversationUuid) => http.get(
    `/agent/conversations/${conversationUuid}/proposals`, { baseURL: '/api/v1' },
  ),
  planningProposal: (conversationUuid, version) => http.get(
    `/agent/conversations/${conversationUuid}/proposals/versions/${version}`, { baseURL: '/api/v1' },
  ),
}
