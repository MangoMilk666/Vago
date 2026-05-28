import React, { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getProfile, logout } from '../api/user'
import { clearAuth, getAuth } from '../stores/auth'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 先读缓存，再请求最新
    const cached = getAuth()
    if (cached?.user) setUser(cached.user)

    getProfile()
      .then((res) => {
        if (res.code === 200) setUser(res.data)
      })
      .catch(() => navigate('/login'))
      .finally(() => setLoading(false))
  }, [navigate])

  const handleLogout = async () => {
    try { await logout() } catch (_) {}
    clearAuth()
    navigate('/login')
  }

  if (loading && !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
                            flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243
                     a8 8 0 1111.314 0z" />
              </svg>
            </div>
            <span className="font-bold text-gray-900">叠迹 Vago</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                            flex items-center justify-center text-white text-sm font-semibold">
              {user?.nickname?.[0] ?? '?'}
            </div>
            <span className="hidden sm:block text-sm text-gray-700 font-medium">
              {user?.nickname ?? '旅行者'}
            </span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-red-500 transition-colors px-2 py-1"
            >
              退出
            </button>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-5xl mx-auto px-6 py-12">
        {/* 欢迎横幅 */}
        <div className="rounded-3xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500
                        p-8 text-white mb-8 relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-48 h-48 bg-white/10 rounded-full blur-2xl" />
          <div className="relative z-10">
            <p className="text-indigo-100 text-sm mb-1">欢迎回来</p>
            <h1 className="text-3xl font-bold mb-3">
              {user?.nickname ?? '旅行者'} 👋
            </h1>
            <p className="text-indigo-100">
              你的叠迹之旅正在继续，记录每一个精彩瞬间
            </p>
          </div>
        </div>

        {/* 功能卡片网格 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { emoji: '✈️', title: '我的行程', desc: '查看、创建和管理旅行行程', to: '/trips' },
            { emoji: '📋', title: '旅行计划', desc: '草稿计划，一键转为正式行程', to: '/plans' },
            { emoji: '📖', title: '攻略广场', desc: '浏览和分享旅游攻略帖', to: '/guides' },
            { emoji: '🗺️', title: '足迹地图', desc: '查看你走过的每一个地方', to: null },
            { emoji: '🤖', title: 'AI 行程规划', desc: '基于攻略库智能生成专属旅行计划', to: '/ai' },
            { emoji: '🌫️', title: '迷雾探索', desc: '解锁未曾踏足的区域', to: null },
          ].map((card) => {
            const inner = (
              <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm
                              hover:shadow-md hover:-translate-y-0.5 transition-all duration-200
                              cursor-pointer group relative">
                {!card.to && (
                  <span className="absolute top-3 right-3 text-xs text-gray-300 font-medium">
                    即将上线
                  </span>
                )}
                <div className="text-3xl mb-3">{card.emoji}</div>
                <h3 className="font-semibold text-gray-900 mb-1 group-hover:text-indigo-600
                               transition-colors">
                  {card.title}
                </h3>
                <p className="text-sm text-gray-500">{card.desc}</p>
              </div>
            )
            return card.to
              ? <Link key={card.title} to={card.to}>{inner}</Link>
              : <div key={card.title}>{inner}</div>
          })}
        </div>

        <div className="mt-8 text-center text-sm text-gray-400">
          足迹地图 · 迷雾探索 正在开发中，敬请期待
        </div>
      </main>
    </div>
  )
}
