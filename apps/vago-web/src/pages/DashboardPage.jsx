import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { getProfile } from '../api/user'
import { getAuth } from '../stores/auth'

const ENTRIES = [
  { icon: '✈️', title: '我的行程', description: '查看、创建和管理旅行行程', to: '/trips' },
  { icon: '📋', title: '旅行计划', description: '先记下想去的地方，再慢慢完善', to: '/plans' },
  { icon: '📖', title: '个人知识库', description: '整理自己的旅行资料与笔记', to: '/guides' },
  { icon: '🤖', title: 'AI 搭子', description: '结合个人资料生成旅行计划草案', to: '/ai' },
  { icon: '🗺️', title: '旅行足迹', description: '回顾每一段真实走过的旅程', to: '/footprints' },
  { icon: '✦', title: '旅行回忆', description: '将旅途中的记录沉淀为长期回忆', to: '/memories' },
]

export default function DashboardPage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(() => getAuth()?.user ?? null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProfile()
      .then((response) => {
        if (response.code === 200) setUser(response.data)
      })
      .catch(() => navigate('/login'))
      .finally(() => setLoading(false))
  }, [navigate])

  if (loading && !user) {
    return <div className="app-page"><Navbar /><div className="flex h-64 items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" /></div></div>
  }

  return <div className="app-page"><Navbar />
    <main className="app-main max-w-6xl py-12">
      <section className="mb-8 border-b border-violet-100 pb-7">
        <p className="mb-2 text-sm font-medium text-violet-700">PERSONAL TRAVEL INTELLIGENCE</p>
        <h1 className="text-3xl font-semibold text-slate-900">你好，{user?.nickname ?? '旅行者'}</h1>
        <p className="mt-3 text-sm text-slate-500">从一条资料、一个计划或一段行程开始，留下属于自己的旅行脉络。</p>
      </section>

      {/* 首页保留简单明确的功能入口，避免堆叠过多数据面板。 */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ENTRIES.map((entry) => <Link key={entry.to} to={entry.to} className="group app-surface flex min-h-44 flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-md">
          <span className="mb-5 text-3xl" aria-hidden="true">{entry.icon}</span>
          <h2 className="text-base font-semibold text-slate-900 transition-colors group-hover:text-violet-700">{entry.title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">{entry.description}</p>
        </Link>)}
      </section>
    </main>
  </div>
}
