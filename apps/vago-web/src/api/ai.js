import axios from 'axios'
import { getAuth } from '../stores/auth'

// ─── Axios 实例（非流式接口） ──────────────────────────────────────────────────
const http = axios.create({
  baseURL: '/api/v1/ai',
  timeout: 60000, // AI 生成可能较慢，超时设 60 秒
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = getAuth()?.accessToken
  if (token) config.headers['authorization'] = token
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
      window.location.href = '/login'
    }
    return Promise.reject(new Error(error.response?.data?.message || '网络请求失败，请稍后重试'))
  }
)

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
    const token = getAuth()?.accessToken
    const params = new URLSearchParams({
      usePersonalContext: String(usePersonalContext),
      useRag: String(useRag),
    })
    const response = await fetch(`/api/v1/agent/context-preview?${params}`, {
      headers: token ? { authorization: token } : {},
    })
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
    const token = getAuth()?.accessToken
    return fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { authorization: token } : {}),
      },
      body: JSON.stringify({ messages, useRag, usePersonalContext, conversationUuid }),
      ...(signal ? { signal } : {}),
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
}
