import axios from 'axios'
import { configureHttp } from './http'

// ─── Axios 实例 ───────────────────────────────────────────────────────────────
const http = axios.create({
  baseURL: '/api/v1/user',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

configureHttp(http)

// ─── API 方法 ─────────────────────────────────────────────────────────────────

/** 发送短信验证码 */
export function sendSmsCode(phone) {
  return http.post('/sms/send', { phone })
}

/** 手机号+验证码 登录 */
export function loginByPhone(phone, code) {
  return http.post('/login/phone', { phone, smsCode: code, clientType: 'web' })
}

/** OAuth 登录 */
export function loginByOAuth(provider, authCode, redirectUri, deviceId) {
  return http.post('/login/oauth', { provider, authCode, redirectUri, deviceId, clientType: 'web' })
}

/** 手机号+验证码 注册（需要昵称）*/
export function register(phone, code, nickname) {
  return http.post('/register', { phone, smsCode: code, nickname, clientType: 'web' })
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
  return http.post('/logout')
}
