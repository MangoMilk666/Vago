import React from 'react'
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
import { isLoggedIn } from './stores/auth'

// 受保护路由：未登录跳转到 /login
function ProtectedRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
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
        <ProtectedRoute><FuturePage type="footprints" /></ProtectedRoute>
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
  )
}
