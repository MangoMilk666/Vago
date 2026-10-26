// Web 只在内存保存展示资料和 CSRF Token；认证凭证由 HttpOnly Cookie 承载。
let auth = null
let restorePromise = null
const authChannel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('vago:auth')

export class AccountStatusError extends Error {}

export function announceAuthChange() {
  // 只发送重新校验信号，不跨标签页传递用户资料或 CSRF Token。
  authChannel?.postMessage('session-changed')
}

export function subscribeAuthChanges(listener) {
  if (!authChannel) return () => {}
  authChannel.addEventListener('message', listener)
  return () => authChannel.removeEventListener('message', listener)
}

export function saveAuth({ user, csrfToken }) {
  auth = { user, csrfToken }
  localStorage.removeItem('vago_auth')
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
  window.dispatchEvent(new Event('vago:auth-changed'))
}

export function clearAuth() {
  auth = null
  localStorage.removeItem('vago_auth')
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
  window.dispatchEvent(new Event('vago:auth-changed'))
}

export function getAuth() {
  return auth
}

export function getCsrfToken() {
  return auth?.csrfToken ?? null
}

export function isLoggedIn() {
  return Boolean(auth?.user)
}

export function restoreAuth() {
  if (restorePromise) return restorePromise
  // 页面重载后必须询问服务端，不能用旧浏览器存储判断是否已登录。
  restorePromise = fetch('/api/v1/auth/session', { credentials: 'same-origin' })
    .then(async (response) => {
      if (response.status === 401) {
        clearAuth()
        return null
      }
      if (response.status === 403) {
        const body = await response.json()
        if (['ACCOUNT_BANNED', 'ACCOUNT_CANCELLING', 'ACCOUNT_INVALID'].includes(body.code)) {
          clearAuth()
          throw new AccountStatusError(body.message || '当前账号不可登录')
        }
      }
      if (!response.ok) throw new Error('暂时无法验证登录状态')
      const body = await response.json()
      saveAuth({ user: body.data.userInfo, csrfToken: body.data.csrfToken })
      return auth
    })
    .finally(() => { restorePromise = null })
  return restorePromise
}
