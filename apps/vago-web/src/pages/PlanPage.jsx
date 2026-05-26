import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { planApi } from '../api/travel'

// ── 空状态 ───────────────────────────────────────────────────────────────────
function EmptyState({ onAdd }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-5xl mb-4">📋</div>
      <p className="text-gray-500 mb-4">还没有旅行计划，先把想去的地方记下来吧</p>
      <button onClick={onAdd}
        className="px-5 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium
                   hover:bg-indigo-700 transition-colors">
        创建计划
      </button>
    </div>
  )
}

// ── 计划卡片 ─────────────────────────────────────────────────────────────────
function PlanCard({ plan, onEdit, onDelete, onConvert, onPlan }) {
  const converted = plan.status === 1

  return (
    <div className={`bg-white rounded-2xl border shadow-sm hover:shadow-md transition-shadow p-5
                     flex flex-col gap-3 ${converted ? 'border-green-200' : 'border-gray-100'}`}>
      {/* 标题 */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-900 text-base leading-snug line-clamp-2">
          {plan.title}
        </h3>
        {converted && (
          <span className="shrink-0 px-2 py-0.5 rounded-full text-xs font-medium
                           bg-green-50 text-green-600">
            已转行程
          </span>
        )}
      </div>

      {/* 目的地 */}
      {plan.destination && (
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
          </svg>
          <span className="line-clamp-1">{plan.destination}</span>
        </div>
      )}

      {/* 日期 + 预算 */}
      <div className="flex flex-wrap gap-3 text-sm text-gray-500">
        {plan.startDate && (
          <span>
            {plan.startDate}{plan.endDate ? ` → ${plan.endDate}` : ''}
          </span>
        )}
        {plan.budget != null && (
          <span className="text-amber-600 font-medium">
            {plan.budgetCurrency ?? 'CNY'} {Number(plan.budget).toLocaleString()}
          </span>
        )}
      </div>

      {/* 备注 */}
      {plan.notes && (
        <p className="text-sm text-gray-400 line-clamp-2">{plan.notes}</p>
      )}

      {/* 操作 */}
      <div className="flex gap-2 pt-1 mt-auto flex-wrap">
        {plan.startDate && plan.endDate && (
          <button onClick={() => onPlan(plan)}
            className="flex-1 min-w-[80px] py-1.5 rounded-xl bg-indigo-50 text-indigo-600
                       text-sm font-medium hover:bg-indigo-100 transition-colors">
            规划行程
          </button>
        )}
        {!converted && (
          <>
            <button onClick={() => onEdit(plan)}
              className="py-1.5 px-3 rounded-xl border border-gray-200 text-sm text-gray-600
                         hover:border-indigo-400 hover:text-indigo-600 transition-colors">
              编辑
            </button>
            <button onClick={() => onConvert(plan)}
              className="py-1.5 px-3 rounded-xl bg-green-50 text-green-600 text-sm font-medium
                         hover:bg-green-100 transition-colors">
              转为行程
            </button>
          </>
        )}
        <button onClick={() => onDelete(plan)}
          className="py-1.5 px-3 rounded-xl border border-gray-200 text-sm text-gray-600
                     hover:border-red-300 hover:text-red-500 transition-colors">
          删除
        </button>
      </div>
    </div>
  )
}

// ── Modal ────────────────────────────────────────────────────────────────────
function PlanModal({ plan, onClose, onSaved }) {
  const isEdit = !!plan
  const [form, setForm] = useState({
    title:          plan?.title          ?? '',
    destination:    plan?.destination    ?? '',
    startDate:      plan?.startDate      ?? '',
    endDate:        plan?.endDate        ?? '',
    budget:         plan?.budget         ?? '',
    budgetCurrency: plan?.budgetCurrency ?? 'CNY',
    notes:          plan?.notes          ?? '',
  })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) { setError('请填写计划标题'); return }
    setLoading(true); setError('')
    const payload = {
      ...form,
      budget: form.budget === '' ? null : Number(form.budget),
      startDate: form.startDate || null,
      endDate:   form.endDate   || null,
    }
    try {
      if (isEdit) {
        await planApi.update(plan.uuid, payload)
      } else {
        await planApi.create(payload)
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
      <div className="bg-white rounded-2xl w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between sticky top-0 bg-white">
          <h2 className="font-semibold text-gray-900">{isEdit ? '编辑计划' : '创建计划'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">计划标题 *</label>
            <input value={form.title} onChange={set('title')} maxLength={100}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="例：冬天去北海道看雪"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">目标地点</label>
            <input value={form.destination} onChange={set('destination')} maxLength={200}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="例：日本北海道"/>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">出发日期</label>
              <input type="date" value={form.startDate} onChange={set('startDate')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"/>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">返回日期</label>
              <input type="date" value={form.endDate} onChange={set('endDate')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"/>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">预算</label>
              <input type="number" min="0" value={form.budget} onChange={set('budget')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"
                placeholder="0"/>
            </div>
            <div className="w-24">
              <label className="block text-sm font-medium text-gray-700 mb-1">货币</label>
              <select value={form.budgetCurrency} onChange={set('budgetCurrency')}
                className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400">
                <option>CNY</option>
                <option>USD</option>
                <option>JPY</option>
                <option>EUR</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">备注</label>
            <textarea value={form.notes} onChange={set('notes')} rows={3} maxLength={2000}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm resize-none
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="想去的景点、注意事项…"/>
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
export default function PlanPage() {
  const navigate = useNavigate()
  const [plans,    setPlans]   = useState([])
  const [loading,  setLoading] = useState(true)
  const [modal,    setModal]   = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [converting, setConverting] = useState(null)
  const [toast,    setToast]   = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await planApi.list()
      setPlans(res.data ?? [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 2500)
  }

  const handleDelete = async () => {
    if (!deleting) return
    try {
      await planApi.delete(deleting.uuid)
      setDeleting(null)
      load()
    } catch (err) { alert(err.message) }
  }

  const handleConvert = async () => {
    if (!converting) return
    try {
      await planApi.convert(converting.uuid)
      setConverting(null)
      load()
      showToast('已成功转为正式行程！')
    } catch (err) { alert(err.message) }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">旅行计划</h1>
            <p className="text-sm text-gray-500 mt-0.5">把心动的地方先记下来</p>
          </div>
          <button onClick={() => setModal('create')}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white
                       rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
            </svg>
            创建计划
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full"/>
          </div>
        ) : plans.length === 0 ? (
          <EmptyState onAdd={() => setModal('create')}/>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((plan) => (
              <PlanCard
                key={plan.uuid}
                plan={plan}
                onEdit={(p) => setModal(p)}
                onDelete={(p) => setDeleting(p)}
                onConvert={(p) => setConverting(p)}
                onPlan={(p) => navigate(
                  `/plans/${p.uuid}/itinerary?type=plan&title=${encodeURIComponent(p.title)}`
                )}
              />
            ))}
          </div>
        )}
      </main>

      {/* 创建/编辑 Modal */}
      {modal !== null && (
        <PlanModal
          plan={modal === 'create' ? null : modal}
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
              确定要删除计划「{deleting.title}」吗？
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleting(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors">取消</button>
              <button onClick={handleDelete}
                className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-medium
                           hover:bg-red-600 transition-colors">确认删除</button>
            </div>
          </div>
        </div>
      )}

      {/* 转为行程确认 */}
      {converting && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl p-6">
            <h3 className="font-semibold text-gray-900 mb-2">转为正式行程</h3>
            <p className="text-sm text-gray-500 mb-6">
              将计划「{converting.title}」转为正式行程？转换后计划将标记为已完成，行程可在<b>行程</b>页查看。
            </p>
            <div className="flex gap-3">
              <button onClick={() => setConverting(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors">取消</button>
              <button onClick={handleConvert}
                className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                           hover:bg-indigo-700 transition-colors">确认转换</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast 提示 */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50
                        bg-gray-900 text-white text-sm px-4 py-2 rounded-full shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
