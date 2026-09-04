import React, { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { logout } from '../api/user'
import { clearAuth, getAuth } from '../stores/auth'

const NAV_LINKS = [
  { to: '/', label: '首页' },
  { to: '/guides', label: '知识库' },
  { to: '/ai', label: 'AI 搭子' },
  { to: '/plans', label: '计划' },
  { to: '/trips', label: '行程' },
  { to: '/footprints', label: '足迹' },
  { to: '/memories', label: '回忆' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()

  // 监听 auth 变化（用户在 ProfilePage 保存后触发 vago:auth-changed），实时刷新 Navbar 头像/昵称
  const [user, setUser] = useState(() => getAuth()?.user)
  useEffect(() => {
    const refresh = () => setUser(getAuth()?.user)
    window.addEventListener('vago:auth-changed', refresh)
    return () => window.removeEventListener('vago:auth-changed', refresh)
  }, [])

  const handleLogout = async () => {
    try { await logout() } catch (_) {}
    clearAuth()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-40 border-b border-violet-100 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 shadow-sm shadow-violet-200">
            <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            </svg>
          </div>
          <span className="hidden text-sm font-semibold tracking-wide text-slate-900 sm:block">叠迹 Vago</span>
        </Link>

        {/* 导航链接 */}
        <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto whitespace-nowrap px-1 [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          {NAV_LINKS.map(({ to, label }) => {
            const active = pathname === to || (to !== '/' && pathname.startsWith(to))
            return (
              <Link
                key={to}
                to={to}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-colors
                  ${active
                    ? 'bg-violet-100 text-violet-800'
                    : 'text-slate-500 hover:bg-violet-50 hover:text-violet-700'}`}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* 用户区 */}
        <div className="flex shrink-0 items-center gap-2">
          {/* 点击头像 / 昵称跳转个人资料页 */}
          <Link to="/profile" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {user?.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt="avatar"
                className="h-7 w-7 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-500 text-xs font-semibold text-white">
                {user?.nickname?.[0] ?? '?'}
              </div>
            )}
            <span className="hidden max-w-24 truncate text-sm font-medium text-slate-600 md:block">
              {user?.nickname ?? '旅行者'}
            </span>
          </Link>
          <button
            onClick={handleLogout}
            className="px-2 py-1 text-xs text-slate-400 transition-colors hover:text-red-500"
          >
            退出
          </button>
        </div>
      </div>
    </header>
  )
}
