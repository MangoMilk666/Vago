import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import { isLoggedIn } from './stores/auth'

// 受保护路由：未登录跳转到 /login
function ProtectedRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      {/* 兜底重定向 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
