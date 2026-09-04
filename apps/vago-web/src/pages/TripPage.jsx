import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { tripApi } from '../api/travel'

const STATUS_MAP = { 1: '未开始', 2: '进行中', 3: '已结束' }
const STATUS_COLOR = {
  1: 'bg-violet-50 text-violet-700',
  2: 'bg-emerald-50 text-emerald-700',
  3: 'bg-slate-100 text-slate-500',
}

// ── 空状态 ──────────────────────────────────────────────────────────────────
function EmptyState({ onAdd }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-5xl mb-4">✈️</div>
      <p className="text-gray-500 mb-4">还没有行程，快来创建第一条吧</p>
      <button onClick={onAdd}
        className="px-5 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium
                   hover:bg-indigo-700 transition-colors">
        创建行程
      </button>
    </div>
  )
}

// ── 行程卡片 ─────────────────────────────────────────────────────────────────
function TripCard({ trip, onEdit, onDelete, onPlan, onStart, onFinish }) {
  const ended = trip.status === 3
  const nights = trip.startDate && trip.endDate
    ? Math.max(0,
        (new Date(trip.endDate) - new Date(trip.startDate)) / 86400000
      )
    : null

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm
                    hover:shadow-md transition-shadow p-5 flex flex-col gap-3">
      {/* 顶部：标题 + 状态标签 */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-900 text-base leading-snug line-clamp-2">
          {trip.title}
        </h3>
        <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium
                          ${STATUS_COLOR[trip.status]}`}>
          {STATUS_MAP[trip.status]}
        </span>
      </div>

      {/* 目的地 */}
      {trip.destination && (
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
          </svg>
          <span className="line-clamp-1">{trip.destination}</span>
        </div>
      )}

      {/* 日期 */}
      {trip.startDate && (
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
          <span>{trip.startDate} → {trip.endDate}</span>
          {nights !== null && (
            <span className="text-gray-400 text-xs ml-1">共 {nights} 晚</span>
          )}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex gap-2 pt-1 mt-auto flex-wrap">
        <button onClick={() => onPlan(trip)}
          className="flex-1 min-w-[80px] py-1.5 rounded-xl bg-indigo-50 text-indigo-600 text-sm
                     font-medium hover:bg-indigo-100 transition-colors">
          {ended ? '查看行程' : '编辑行程安排'}
        </button>
        {!ended && <button onClick={() => onEdit(trip)}
          className="py-1.5 px-3 rounded-xl border border-gray-200 text-sm text-gray-600
                     hover:border-indigo-400 hover:text-indigo-600 transition-colors">
          编辑行程
        </button>}
        {/* 分支条件：未开始行程可开始，进行中行程可结束，历史行程仅允许查看。 */}
        {trip.status === 1 && <button onClick={() => onStart(trip)} className="py-1.5 px-3 rounded-xl bg-emerald-50 text-emerald-700 text-sm font-medium hover:bg-emerald-100 transition-colors">开始</button>}
        {trip.status === 2 && <button onClick={() => onFinish(trip)} className="py-1.5 px-3 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-colors">结束行程</button>}
        {!ended && <button onClick={() => onDelete(trip)}
          className="py-1.5 px-3 rounded-xl border border-gray-200 text-sm text-gray-600
                     hover:border-red-300 hover:text-red-500 transition-colors">
          删除
        </button>}
      </div>
    </div>
  )
}

// ── 创建/编辑 Modal ──────────────────────────────────────────────────────────
function TripModal({ trip, onClose, onSaved }) {
  const isEdit = !!trip
  const [form, setForm] = useState({
    title:      trip?.title      ?? '',
    destination: trip?.destination ?? '',
    startDate:  trip?.startDate  ?? '',
    endDate:    trip?.endDate    ?? '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) { setError('请填写行程标题'); return }
    if (!form.startDate || !form.endDate) { setError('请选择出发和返回日期'); return }
    setLoading(true); setError('')
    try {
      if (isEdit) {
        await tripApi.update(trip.uuid, form)
      } else {
        await tripApi.create(form)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-md shadow-xl">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">{isEdit ? '编辑行程' : '创建行程'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">行程标题 *</label>
            <input value={form.title} onChange={set('title')} maxLength={100}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="例：东京赏樱七日游"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">目的地</label>
            <input value={form.destination} onChange={set('destination')} maxLength={200}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="例：日本东京"/>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">出发日期 *</label>
              <input type="date" value={form.startDate} onChange={set('startDate')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"/>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">返回日期 *</label>
              <input type="date" value={form.endDate} onChange={set('endDate')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"/>
            </div>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                         hover:bg-gray-50 transition-colors">
              取消
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                         hover:bg-indigo-700 disabled:opacity-50 transition-colors">
              {loading ? '保存中…' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── 主页面 ───────────────────────────────────────────────────────────────────
export default function TripPage() {
  const navigate = useNavigate()
  const [trips,    setTrips]   = useState([])
  const [loading,  setLoading] = useState(true)
  const [tab,      setTab]     = useState('all')   // 'all' | 'history'
  const [modal,    setModal]   = useState(null)     // null | 'create' | trip对象
  const [deleting, setDeleting] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = tab === 'history'
        ? await tripApi.history()
        : await tripApi.list()
      setTrips(res.data ?? [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [tab])

  const handleDelete = async () => {
    if (!deleting) return
    try {
      await tripApi.delete(deleting.uuid)
      setDeleting(null)
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  const changeTripState = async (trip, action) => {
    try {
      // 分支条件：点击开始或结束时，分别调用后端受约束的状态转换接口。
      if (action === 'start') await tripApi.start(trip.uuid)
      else await tripApi.finish(trip.uuid)
      load()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="app-page">
      <Navbar />

      <main className="app-main">
        {/* 顶部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">我的行程</h1>
            <p className="text-sm text-gray-500 mt-0.5">记录每一段旅程</p>
          </div>
          <button onClick={() => setModal('create')}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white
                       rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
            </svg>
            创建行程
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit mb-6">
          {[['all', '全部行程'], ['history', '历史行程']].map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
                ${tab === key
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'}`}>
              {label}
            </button>
          ))}
        </div>

        {/* 内容 */}
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full"/>
          </div>
        ) : trips.length === 0 ? (
          <EmptyState onAdd={() => setModal('create')}/>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {trips.map((trip) => (
              <TripCard
                key={trip.uuid}
                trip={trip}
                onEdit={(t) => setModal(t)}
                onDelete={(t) => setDeleting(t)}
                onPlan={(t) => navigate(
                  `/trips/${t.uuid}/itinerary?type=trip&title=${encodeURIComponent(t.title)}&readonly=${t.status === 3}`
                )}
                onStart={(t) => changeTripState(t, 'start')}
                onFinish={(t) => changeTripState(t, 'finish')}
              />
            ))}
          </div>
        )}
      </main>

      {/* 创建/编辑 Modal */}
      {modal !== null && (
        <TripModal
          trip={modal === 'create' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); load() }}
        />
      )}

      {/* 删除确认 */}
      {deleting && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl p-6">
            <h3 className="font-semibold text-gray-900 mb-2">确认删除</h3>
            <p className="text-sm text-gray-500 mb-6">
              确定要删除行程「{deleting.title}」吗？此操作不可撤销。
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleting(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors">
                取消
              </button>
              <button onClick={handleDelete}
                className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-medium
                           hover:bg-red-600 transition-colors">
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
