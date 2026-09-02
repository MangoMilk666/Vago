import React, { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { getProfile } from '../api/user'
import { getAuth } from '../stores/auth'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 先读缓存，再请求最新个人资料。
    const cached = getAuth()
    if (cached?.user) setUser(cached.user)

    getProfile()
      .then((res) => {
        if (res.code === 200) setUser(res.data)
      })
      .catch(() => navigate('/login'))
      .finally(() => setLoading(false))
  }, [navigate])

  if (loading && !user) {
    return <div className="min-h-screen bg-gray-50"><Navbar /><div className="flex h-64 items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" /></div></div>
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="relative mb-8 overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-8 text-white">
          <div className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10">
            <p className="mb-1 text-sm text-indigo-100">欢迎回来</p>
            <h1 className="mb-3 text-3xl font-bold">{user?.nickname ?? '旅行者'} 👋</h1>
            <p className="text-indigo-100">你的叠迹之旅正在继续，记录每一个精彩瞬间</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { emoji: '✈️', title: '我的行程', desc: '查看、创建和管理旅行行程', to: '/trips' },
            { emoji: '📋', title: '旅行计划', desc: '草稿计划，一键转为正式行程', to: '/plans' },
            { emoji: '📖', title: '个人知识库', desc: '整理自己的旅行资料与笔记', to: '/guides' },
            { emoji: '🗺️', title: '足迹地图', desc: '查看你走过的每一个地方', to: null },
            { emoji: '🤖', title: 'AI 行程规划', desc: '结合个人资料生成专属旅行计划', to: '/ai' },
            { emoji: '🌫️', title: '迷雾探索', desc: '解锁未曾踏足的区域', to: null },
          ].map((card) => {
            const inner = <div className="group relative cursor-pointer rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
              {!card.to && <span className="absolute right-3 top-3 text-xs font-medium text-gray-300">即将上线</span>}
              <div className="mb-3 text-3xl">{card.emoji}</div>
              <h2 className="mb-1 font-semibold text-gray-900 transition-colors group-hover:text-indigo-600">{card.title}</h2>
              <p className="text-sm text-gray-500">{card.desc}</p>
            </div>
            return card.to ? <Link key={card.title} to={card.to}>{inner}</Link> : <div key={card.title}>{inner}</div>
          })}
        </div>

        <div className="mt-8 text-center text-sm text-gray-400">足迹地图 · 迷雾探索 正在开发中，敬请期待</div>
      </main>
    </div>
  )
}
