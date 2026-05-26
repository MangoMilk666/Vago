// 轻量级 Auth 状态管理（无需 Redux，使用原生 localStorage + 自定义事件）

const AUTH_KEY = 'vago_auth'

export function saveAuth({ accessToken, refreshToken, user }) {
  localStorage.setItem(
    AUTH_KEY,
    JSON.stringify({ accessToken, refreshToken, user })
  )
  // 同一 tab 内通知其他组件
  window.dispatchEvent(new Event('vago:auth-changed'))
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY)
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
  window.dispatchEvent(new Event('vago:auth-changed'))
}

export function getAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY)) || null
  } catch {
    return null
  }
}

export function isLoggedIn() {
  const auth = getAuth()
  return !!auth?.accessToken
}
