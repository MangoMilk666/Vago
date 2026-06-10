import axios from 'axios'

// ─── Axios 实例 ───────────────────────────────────────────────────────────────
const http = axios.create({
  baseURL: '/api/v1/user',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动注入 Access Token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers['authorization'] = token
  }
  return config
})

// 响应拦截器：统一处理错误 & 401 自动跳转
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const res = error.response?.data
    const msg = res?.message || '网络请求失败，请稍后重试'
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      window.location.href = '/login'
    }
    return Promise.reject(new Error(msg))
  }
)

// ─── API 方法 ─────────────────────────────────────────────────────────────────

/** 发送短信验证码 */
export function sendSmsCode(phone) {
  return http.post('/sms/send', { phone })
}

/** 手机号+验证码 登录 */
export function loginByPhone(phone, code) {
  return http.post('/login/phone', { phone, smsCode: code })
}

/** OAuth 登录 */
export function loginByOAuth(provider, authCode, redirectUri, deviceId) {
  return http.post('/login/oauth', { provider, authCode, redirectUri, deviceId })
}

/** 手机号+验证码 注册（需要昵称）*/
export function register(phone, code, nickname) {
  return http.post('/register', { phone, smsCode: code, nickname })
}

/** 获取当前用户信息 */
export function getProfile() {
  return http.get('/profile')
}

/**
 * 更新个人资料
 * @param {{ nickname?: string, email?: string, avatarUuid?: string }} data
 */
export function updateProfile(data) {
  return http.put('/profile', data)
}

/** 退出登录 */
export function logout() {
  const token = localStorage.getItem('accessToken')
  return http.post('/logout', null, {
    headers: token ? { authorization: token } : {},
  })
}
