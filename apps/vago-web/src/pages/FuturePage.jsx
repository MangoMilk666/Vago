import React from 'react'
import { Link } from 'react-router-dom'
import Navbar from '../components/Navbar'

const PAGE_CONFIG = {
  footprints: { eyebrow: 'TRAVEL FOOTPRINT', title: '旅行足迹', description: '足迹将由真实行程、地点与移动记录慢慢构成。' },
  memories: { eyebrow: 'TRAVEL MEMORY', title: '旅行回忆', description: '回忆会基于已确认的旅行事实生成，并始终保留你的编辑权。' },
}

// 为尚未建设数据域的产品能力保留稳定入口，避免在导航中回退到社区概念。
export default function FuturePage({ type }) {
  const page = PAGE_CONFIG[type]
  return <div className="app-page"><Navbar />
    <main className="app-main"><section className="app-surface mx-auto mt-12 max-w-2xl p-8 sm:p-10">
      <p className="text-sm font-medium text-violet-700">{page.eyebrow}</p>
      <h1 className="mt-3 text-2xl font-semibold text-slate-900">{page.title}</h1>
      <p className="mt-3 text-sm leading-6 text-slate-500">{page.description}</p>
      <Link to="/" className="app-secondary-action mt-7">返回首页</Link>
    </section></main>
  </div>
}
