import { clearAuth, getCsrfToken } from '../stores/auth'

const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete'])

export function configureHttp(http, fallbackMessage = '网络请求失败，请稍后重试') {
  http.defaults.withCredentials = true
  http.interceptors.request.use((config) => {
    // Cookie 由浏览器自动发送；写请求另带本次会话的 CSRF Token。
    if (WRITE_METHODS.has(config.method?.toLowerCase())) {
      const csrfToken = getCsrfToken()
      if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken
    }
    return config
  })
  http.interceptors.response.use(
    (response) => response.data,
    (error) => {
      if (error.response?.status === 401) handleUnauthorized()
      return Promise.reject(new Error(error.response?.data?.message || fallbackMessage))
    },
  )
  return http
}

export function handleUnauthorized() {
  if (window.location.pathname.startsWith('/login')) return
  clearAuth()
  window.location.href = '/login'
}
