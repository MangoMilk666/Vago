import React, { useEffect, useRef, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage    from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import TripPage       from './pages/TripPage'
import PlanPage       from './pages/PlanPage'
import GuidePage      from './pages/GuidePage'
import ItineraryPage  from './pages/ItineraryPage'
import AiPlanPage     from './pages/AiPlanPage'
import ProfilePage    from './pages/ProfilePage'
import FuturePage     from './pages/FuturePage'
import FootprintPage  from './pages/FootprintPage'
import { AccountStatusError, getAuth, isLoggedIn, restoreAuth, subscribeAuthChanges } from './stores/auth'

// 受保护路由：未登录跳转到 /login
function ProtectedRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  const [sessionState, setSessionState] = useState('loading')
  const [accountMessage, setAccountMessage] = useState('')
  const revalidateRef = useRef(null)

  useEffect(() => {
    let active = true
    let validating = false
    let pendingValidation = false
    let canPreserveRoute = false

    const validateSession = async () => {
      if (validating) {
        pendingValidation = true
        return
      }
      validating = true
      const previousUserUuid = getAuth()?.user?.uuid ?? null
      // 首屏尚无页面可保留；之后的校验只遮住页面，不卸载表单和编辑器。
      setSessionState(canPreserveRoute ? 'checking' : 'loading')
      try {
        const current = await restoreAuth()
        if (!active) return
        const currentUserUuid = current?.user?.uuid ?? null
        // 如果共享 Cookie 指向另一个账号，整页重新载入，丢弃旧账号的页面数据。
        if (previousUserUuid && previousUserUuid !== currentUserUuid) {
          pendingValidation = false
          window.location.replace(currentUserUuid ? '/' : '/login')
          return
        }
        if (!previousUserUuid && currentUserUuid && window.location.pathname === '/login') {
          pendingValidation = false
          window.location.replace('/')
          return
        }
        canPreserveRoute = true
        setSessionState('ready')
      } catch (error) {
        if (!active) return
        if (error instanceof AccountStatusError) {
          canPreserveRoute = false
          pendingValidation = false
          setAccountMessage(error.message)
          setSessionState('blocked')
        } else {
          setSessionState(canPreserveRoute ? 'checking-error' : 'error')
        }
      } finally {
        validating = false
        // 如果校验期间另一标签页改了 Cookie，再读取一次最终会话状态。
        if (active && pendingValidation) {
          pendingValidation = false
          validateSession()
        }
      }
    }

    const recheckVisibleSession = () => {
      if (document.visibilityState === 'visible') validateSession()
    }
    revalidateRef.current = validateSession
    validateSession()
    const unsubscribe = subscribeAuthChanges(recheckVisibleSession)
    document.addEventListener('visibilitychange', recheckVisibleSession)
    window.addEventListener('focus', recheckVisibleSession)
    return () => {
      active = false
      revalidateRef.current = null
      unsubscribe()
      document.removeEventListener('visibilitychange', recheckVisibleSession)
      window.removeEventListener('focus', recheckVisibleSession)
    }
  }, [])

  if (sessionState === 'loading') return <div role="status">正在验证登录状态…</div>
  if (sessionState === 'blocked') return (
    <div role="alert">
      <p>{accountMessage}</p>
      <button onClick={() => window.location.assign('/login')}>返回登录页</button>
    </div>
  )
  if (sessionState === 'error') return (
    <div role="alert">暂时无法验证登录状态。<button onClick={() => window.location.reload()}>重试</button></div>
  )

  const checking = sessionState === 'checking' || sessionState === 'checking-error'
  return (
    <>
      <div aria-hidden={checking} inert={checking ? '' : undefined}
        style={checking ? { visibility: 'hidden', pointerEvents: 'none' } : undefined}>
        <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/" element={
        <ProtectedRoute><DashboardPage /></ProtectedRoute>
      } />
      <Route path="/trips" element={
        <ProtectedRoute><TripPage /></ProtectedRoute>
      } />
      <Route path="/plans" element={
        <ProtectedRoute><PlanPage /></ProtectedRoute>
      } />
      <Route path="/guides" element={
        <ProtectedRoute><GuidePage /></ProtectedRoute>
      } />
      <Route path="/ai" element={
        <ProtectedRoute><AiPlanPage /></ProtectedRoute>
      } />
      <Route path="/profile" element={
        <ProtectedRoute><ProfilePage /></ProtectedRoute>
      } />
      <Route path="/footprints" element={
        <ProtectedRoute><FootprintPage /></ProtectedRoute>
      } />
      <Route path="/memories" element={
        <ProtectedRoute><FuturePage type="memories" /></ProtectedRoute>
      } />
      {/* 每日行程规划：/trips/:uuid/itinerary?type=trip&title=xxx */}
      <Route path="/trips/:uuid/itinerary" element={
        <ProtectedRoute><ItineraryPage /></ProtectedRoute>
      } />
      <Route path="/plans/:uuid/itinerary" element={
        <ProtectedRoute><ItineraryPage /></ProtectedRoute>
      } />

      {/* 兜底重定向 */}
      <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {checking && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-white" role="status">
          {sessionState === 'checking-error' ? (
            <div role="alert">
              暂时无法验证登录状态。
              <button onClick={() => revalidateRef.current?.()}>重试</button>
            </div>
          ) : '正在验证登录状态…'}
        </div>
      )}
    </>
  )
}
