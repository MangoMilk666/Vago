import React from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { logout } from '../api/user'
import { clearAuth, getAuth } from '../stores/auth'

const NAV_LINKS = [
  { to: '/',       label: '首页'   },
  { to: '/trips',  label: '行程'   },
  { to: '/plans',  label: '计划'   },
  { to: '/guides', label: '攻略'   },
  { to: '/ai',     label: 'AI 规划' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const user = getAuth()?.user

  const handleLogout = async () => {
    try { await logout() } catch (_) {}
    clearAuth()
    navigate('/login')
  }

  return (
    <header className="bg-white border-b border-gray-100 sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600
                          flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            </svg>
          </div>
          <span className="font-bold text-gray-900 text-sm hidden sm:block">叠迹 Vago</span>
        </Link>

        {/* 导航链接 */}
        <nav className="flex items-center gap-1">
          {NAV_LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                  ${active
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'}`}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* 用户区 */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                          flex items-center justify-center text-white text-xs font-semibold">
            {user?.nickname?.[0] ?? '?'}
          </div>
          <span className="hidden md:block text-sm text-gray-600 font-medium max-w-24 truncate">
            {user?.nickname ?? '旅行者'}
          </span>
          <button
            onClick={handleLogout}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
          >
            退出
          </button>
        </div>
      </div>
    </header>
  )
}
