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
  chat: (messages) => http.post('/chat', { messages }),

  /**
   * 流式对话（SSE）：返回 fetch Response，调用方自行消费 ReadableStream。
   *
   * SSE 事件格式（每行 `data: <json>\n\n`）：
   *   {"type": "text",      "content": "..."}  — 文本 token（逐字追加）
   *   {"type": "searching", "query":   "..."}  — Agent 正在检索
   *   {"type": "sources",   "sources": [...]}  — 引用来源列表
   *   {"type": "error",     "message": "..."}  — 生成错误
   *   [DONE]                                   — 流结束信号
   *
   * @param {Array<{role: string, content: string}>} messages 完整消息历史
   * @param {AbortSignal} [signal] 可选：用于超时/取消的 AbortSignal
   * @returns {Promise<Response>} fetch Response，body 为 SSE 流
   */
  chatStream: (messages, signal) => {
    const token = getAuth()?.accessToken
    return fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { authorization: token } : {}),
      },
      body: JSON.stringify({ messages }),
      ...(signal ? { signal } : {}),
    })
  },
}
