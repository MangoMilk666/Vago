import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { itineraryApi } from '../api/travel'

// ── 常量 ──────────────────────────────────────────────────────────────────────
const CATEGORY_META = [
  { label: '景点',   color: 'bg-blue-50   text-blue-600',   dot: 'bg-blue-400'   },
  { label: '餐厅',   color: 'bg-orange-50 text-orange-600', dot: 'bg-orange-400' },
  { label: '购物',   color: 'bg-pink-50   text-pink-600',   dot: 'bg-pink-400'   },
  { label: '娱乐',   color: 'bg-purple-50 text-purple-600', dot: 'bg-purple-400' },
  { label: '中转',   color: 'bg-gray-100  text-gray-500',   dot: 'bg-gray-400'   },
  { label: '其他',   color: 'bg-green-50  text-green-600',  dot: 'bg-green-400'  },
]

const TRANSPORT_OPTIONS = [
  '飞机', '高铁 / 动车', '火车', '自驾', '大巴', '地铁 / 公交', '船 / 游轮', '徒步', '其他',
]

// ── 格式化 ─────────────────────────────────────────────────────────────────────
function fmtDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
function fmtDuration(min) {
  if (!min) return ''
  return min >= 60 ? `${Math.floor(min / 60)}h${min % 60 ? `${min % 60}m` : ''}` : `${min}m`
}
const WEEKDAY = ['日', '一', '二', '三', '四', '五', '六']
function fmtWeekday(dateStr) {
  if (!dateStr) return ''
  return `周${WEEKDAY[new Date(dateStr).getDay()]}`
}

// ── 景点行（可拖拽排序暂用上移/下移按钮代替）────────────────────────────────────
function SpotRow({ spot, index, total, onEdit, onDelete, onMoveUp, onMoveDown }) {
  const meta = CATEGORY_META[spot.category ?? 0] ?? CATEGORY_META[0]
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0 group">
      {/* 序号 */}
      <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold
                      flex items-center justify-center shrink-0 mt-0.5">
        {index + 1}
      </div>

      {/* 信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm text-gray-900">{spot.name}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded-full ${meta.color}`}>
            {meta.label}
          </span>
          {spot.durationMinutes > 0 && (
            <span className="text-xs text-gray-400">{fmtDuration(spot.durationMinutes)}</span>
          )}
        </div>
        {spot.address && (
          <p className="text-xs text-gray-400 mt-0.5 truncate">{spot.address}</p>
        )}
        {spot.notes && (
          <p className="text-xs text-gray-400 italic mt-0.5 line-clamp-1">{spot.notes}</p>
        )}
      </div>

      {/* 操作（hover 显示） */}
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button onClick={onMoveUp} disabled={index === 0}
          className="p-1 rounded text-gray-300 hover:text-gray-600 disabled:opacity-20 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7"/>
          </svg>
        </button>
        <button onClick={onMoveDown} disabled={index === total - 1}
          className="p-1 rounded text-gray-300 hover:text-gray-600 disabled:opacity-20 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <button onClick={onEdit}
          className="p-1 rounded text-gray-300 hover:text-indigo-500 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0
                 012.828 0L21 6.586a2 2 0 010 2.828l-11.01 11.01A2 2 0 018.58 21H7a1 1 0
                 01-1-1v-1.586a2 2 0 01.586-1.414L17.586 5.586z"/>
          </svg>
        </button>
        <button onClick={onDelete}
          className="p-1 rounded text-gray-300 hover:text-red-400 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
  )
}

// ── 单日卡片 ──────────────────────────────────────────────────────────────────
function DayCard({ day, onSave, saving }) {
  const [open,    setOpen]    = useState(false)
  const [editing, setEditing] = useState(false)
  const [form,    setForm]    = useState(null)

  const startEdit = () => {
    setForm({
      transportation: day.transportation ?? '',
      accommodation:  day.accommodation  ?? '',
      mealBreakfast:  day.mealBreakfast  ?? '',
      mealLunch:      day.mealLunch      ?? '',
      mealDinner:     day.mealDinner     ?? '',
      budgetDay:      day.budgetDay      ?? '',
      notes:          day.notes          ?? '',
      spots: day.spots ? JSON.parse(JSON.stringify(day.spots)) : [],
    })
    setEditing(true)
    setOpen(true)
  }

  const cancelEdit = () => { setEditing(false); setForm(null) }

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  // ── 景点操作 ────────────────────────────────────────────────────────────────
  const addSpot = () => {
    setForm((f) => ({
      ...f,
      spots: [...f.spots, { name: '', address: '', category: 0,
                            durationMinutes: '', notes: '', _new: true }],
    }))
  }

  const setSpot = (idx, key, val) => {
    setForm((f) => {
      const spots = [...f.spots]
      spots[idx] = { ...spots[idx], [key]: val }
      return { ...f, spots }
    })
  }

  const removeSpot = (idx) => {
    setForm((f) => ({ ...f, spots: f.spots.filter((_, i) => i !== idx) }))
  }

  const moveSpot = (idx, dir) => {
    setForm((f) => {
      const spots = [...f.spots]
      const target = idx + dir
      if (target < 0 || target >= spots.length) return f
      ;[spots[idx], spots[target]] = [spots[target], spots[idx]]
      return { ...f, spots }
    })
  }

  const handleSave = async () => {
    const payload = {
      ...form,
      budgetDay: form.budgetDay === '' ? null : Number(form.budgetDay),
      spots: form.spots
        .filter((s) => s.name?.trim())
        .map((s, i) => ({
          name:            s.name.trim(),
          address:         s.address || null,
          category:        Number(s.category ?? 0),
          sortOrder:       i,
          durationMinutes: s.durationMinutes ? Number(s.durationMinutes) : null,
          notes:           s.notes || null,
        })),
    }
    await onSave(day.dayIndex, payload)
    setEditing(false)
    setForm(null)
  }

  // 显示填写进度
  const filledCount = [
    day.transportation, day.accommodation,
    day.mealBreakfast || day.mealLunch || day.mealDinner,
  ].filter(Boolean).length
  const hasSpots = (day.spots?.length ?? 0) > 0

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* 卡片头 */}
      <div
        className="flex items-center justify-between px-5 py-4 cursor-pointer
                   hover:bg-gray-50 transition-colors select-none"
        onClick={() => { if (!editing) setOpen((o) => !o) }}
      >
        <div className="flex items-center gap-3">
          {/* 天数徽标 */}
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
                          flex flex-col items-center justify-center text-white shrink-0">
            <span className="text-xs leading-none opacity-80">Day</span>
            <span className="text-base font-bold leading-tight">{day.dayIndex}</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900 text-sm">
                {fmtDate(day.dayDate)}（{fmtWeekday(day.dayDate)}）
              </span>
              {/* 填写进度点 */}
              <div className="flex gap-0.5">
                {[day.transportation, day.accommodation, day.mealLunch || day.mealDinner].map((v, i) => (
                  <div key={i}
                    className={`w-1.5 h-1.5 rounded-full ${v ? 'bg-indigo-400' : 'bg-gray-200'}`}/>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
              {day.transportation && (
                <span className="text-xs text-indigo-500">{day.transportation}</span>
              )}
              {day.accommodation && (
                <span className="text-xs text-gray-400 truncate max-w-[120px]">
                  {day.accommodation}
                </span>
              )}
              {hasSpots && (
                <span className="text-xs text-gray-400">{day.spots.length} 个地点</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!editing && (
            <button onClick={(e) => { e.stopPropagation(); startEdit() }}
              className="px-3 py-1 rounded-lg text-xs text-indigo-600 bg-indigo-50
                         hover:bg-indigo-100 transition-colors">
              编辑
            </button>
          )}
          <svg className={`w-4 h-4 text-gray-400 transition-transform duration-200
                          ${open ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
          </svg>
        </div>
      </div>

      {/* 展开内容 */}
      {open && (
        <div className="border-t border-gray-50">
          {!editing ? (
            // ── 只读视图 ────────────────────────────────────────────────────
            <div className="px-5 py-4 space-y-4">
              {/* 行程信息网格 */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <InfoCell icon="🚗" label="出行方式" value={day.transportation}/>
                <InfoCell icon="🏨" label="住宿"     value={day.accommodation}/>
                <InfoCell icon="☀️" label="早餐"     value={day.mealBreakfast}/>
                <InfoCell icon="🍱" label="午餐"     value={day.mealLunch}/>
                <InfoCell icon="🌙" label="晚餐"     value={day.mealDinner}/>
                {day.budgetDay != null && (
                  <InfoCell icon="💰" label="当日预算"
                    value={`¥ ${Number(day.budgetDay).toLocaleString()}`}/>
                )}
              </div>
              {/* 备注 */}
              {day.notes && (
                <p className="text-sm text-gray-500 bg-gray-50 rounded-xl px-4 py-3">
                  {day.notes}
                </p>
              )}
              {/* 景点列表 */}
              {hasSpots ? (
                <div>
                  <p className="text-xs font-medium text-gray-400 mb-2">行程地点</p>
                  <div className="space-y-0">
                    {day.spots.map((spot, idx) => {
                      const meta = CATEGORY_META[spot.category ?? 0] ?? CATEGORY_META[0]
                      return (
                        <div key={spot.uuid ?? idx}
                          className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0">
                          <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${meta.dot}`}/>
                          <div>
                            <span className="text-sm text-gray-800">{spot.name}</span>
                            {spot.address && (
                              <span className="text-xs text-gray-400 ml-2">{spot.address}</span>
                            )}
                            {spot.durationMinutes > 0 && (
                              <span className="text-xs text-gray-400 ml-2">
                                {fmtDuration(spot.durationMinutes)}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <button onClick={startEdit}
                  className="w-full py-2 border border-dashed border-gray-200 rounded-xl
                             text-xs text-gray-400 hover:border-indigo-300 hover:text-indigo-400
                             transition-colors">
                  + 添加景点
                </button>
              )}
            </div>
          ) : (
            // ── 编辑视图 ────────────────────────────────────────────────────
            <div className="px-5 py-4 space-y-4">
              {/* 出行方式 */}
              <div>
                <label className="form-label">出行方式</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {TRANSPORT_OPTIONS.map((t) => (
                    <button key={t} type="button"
                      onClick={() => setForm((f) => ({ ...f, transportation: t }))}
                      className={`px-3 py-1 rounded-full text-xs border transition-colors
                        ${form.transportation === t
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'border-gray-200 text-gray-600 hover:border-indigo-300'}`}>
                      {t}
                    </button>
                  ))}
                </div>
                <input value={form.transportation} onChange={set('transportation')}
                  className="edit-input mt-2" placeholder="或自定义填写…"/>
              </div>

              {/* 住宿 */}
              <div>
                <label className="form-label">住宿地点</label>
                <input value={form.accommodation} onChange={set('accommodation')} maxLength={300}
                  className="edit-input" placeholder="酒店名称 / 民宿 / 朋友家…"/>
              </div>

              {/* 三餐 */}
              <div className="grid grid-cols-3 gap-2">
                {[
                  ['mealBreakfast', '早餐', '早餐地点…'],
                  ['mealLunch',     '午餐', '午餐地点…'],
                  ['mealDinner',    '晚餐', '晚餐地点…'],
                ].map(([key, label, ph]) => (
                  <div key={key}>
                    <label className="form-label">{label}</label>
                    <input value={form[key]} onChange={set(key)} maxLength={200}
                      className="edit-input" placeholder={ph}/>
                  </div>
                ))}
              </div>

              {/* 预算 */}
              <div>
                <label className="form-label">当日预算（元）</label>
                <input type="number" min="0" value={form.budgetDay} onChange={set('budgetDay')}
                  className="edit-input w-40" placeholder="0"/>
              </div>

              {/* 备注 */}
              <div>
                <label className="form-label">备注 / 提醒</label>
                <textarea value={form.notes} onChange={set('notes')} rows={2} maxLength={2000}
                  className="edit-input resize-none"
                  placeholder="景点开放时间、预定提醒、注意事项…"/>
              </div>

              {/* 景点列表 */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="form-label mb-0">行程地点</label>
                  <button type="button" onClick={addSpot}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors">
                    + 添加地点
                  </button>
                </div>
                <div className="space-y-2">
                  {form.spots.map((spot, idx) => (
                    <div key={idx}
                      className="bg-gray-50 rounded-xl p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        {/* 序号 */}
                        <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-xs
                                         font-bold flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        {/* 名称 */}
                        <input value={spot.name}
                          onChange={(e) => setSpot(idx, 'name', e.target.value)} maxLength={100}
                          className="flex-1 rounded-lg border border-gray-200 px-2 py-1 text-sm
                                     focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                          placeholder="景点 / 餐厅 / 活动名称 *"/>
                        {/* 排序 */}
                        <button onClick={() => moveSpot(idx, -1)} disabled={idx === 0}
                          className="p-1 text-gray-300 hover:text-gray-600 disabled:opacity-20">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7"/>
                          </svg>
                        </button>
                        <button onClick={() => moveSpot(idx, 1)} disabled={idx === form.spots.length - 1}
                          className="p-1 text-gray-300 hover:text-gray-600 disabled:opacity-20">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                          </svg>
                        </button>
                        <button onClick={() => removeSpot(idx)}
                          className="p-1 text-gray-300 hover:text-red-400 transition-colors">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                          </svg>
                        </button>
                      </div>
                      {/* 类别 + 时长 + 地址 */}
                      <div className="flex gap-2 flex-wrap">
                        <select value={spot.category ?? 0}
                          onChange={(e) => setSpot(idx, 'category', Number(e.target.value))}
                          className="rounded-lg border border-gray-200 px-2 py-1 text-xs
                                     focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white">
                          {CATEGORY_META.map((m, i) => (
                            <option key={i} value={i}>{m.label}</option>
                          ))}
                        </select>
                        <input type="number" min="0" max="1440"
                          value={spot.durationMinutes ?? ''}
                          onChange={(e) => setSpot(idx, 'durationMinutes', e.target.value)}
                          className="w-24 rounded-lg border border-gray-200 px-2 py-1 text-xs
                                     focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                          placeholder="时长(分钟)"/>
                        <input value={spot.address ?? ''}
                          onChange={(e) => setSpot(idx, 'address', e.target.value)} maxLength={300}
                          className="flex-1 min-w-[120px] rounded-lg border border-gray-200 px-2 py-1
                                     text-xs focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                          placeholder="地址（可选）"/>
                      </div>
                      <input value={spot.notes ?? ''}
                        onChange={(e) => setSpot(idx, 'notes', e.target.value)} maxLength={500}
                        className="w-full rounded-lg border border-gray-200 px-2 py-1 text-xs
                                   focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white"
                        placeholder="备注（可选）"/>
                    </div>
                  ))}
                  {form.spots.length === 0 && (
                    <div className="text-center py-4 text-xs text-gray-400">
                      还没有行程地点，点击「添加地点」开始规划
                    </div>
                  )}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={cancelEdit}
                  className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                             hover:bg-gray-50 transition-colors">
                  取消
                </button>
                <button type="button" onClick={handleSave} disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                             hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  {saving ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 只读信息格 ─────────────────────────────────────────────────────────────────
function InfoCell({ icon, label, value }) {
  return (
    <div className="bg-gray-50 rounded-xl px-3 py-2.5">
      <div className="text-xs text-gray-400 mb-0.5">{icon} {label}</div>
      <div className="text-sm text-gray-800 font-medium truncate">
        {value || <span className="text-gray-300 font-normal">未填写</span>}
      </div>
    </div>
  )
}

// ── 主页面 ────────────────────────────────────────────────────────────────────
export default function ItineraryPage() {
  const { uuid }                  = useParams()
  const [searchParams]            = useSearchParams()
  const navigate                  = useNavigate()

  // type: 'trip' | 'plan'
  const type = searchParams.get('type') ?? 'trip'
  const title = searchParams.get('title') ?? (type === 'trip' ? '行程规划' : '计划规划')

  const [days,    setDays]    = useState([])
  const [loading, setLoading] = useState(true)
  const [saving,  setSaving]  = useState(false)
  const [error,   setError]   = useState('')
  const [toast,   setToast]   = useState('')

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(''), 2000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = type === 'trip'
        ? await itineraryApi.getTripDays(uuid)
        : await itineraryApi.getPlanDays(uuid)
      if (res.code === 200) setDays(res.data ?? [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [uuid, type])

  useEffect(() => { load() }, [load])

  const handleSaveDay = async (dayIndex, payload) => {
    setSaving(true)
    try {
      const res = type === 'trip'
        ? await itineraryApi.updateTripDay(uuid, dayIndex, payload)
        : await itineraryApi.updatePlanDay(uuid, dayIndex, payload)
      if (res.code === 200) {
        setDays((prev) =>
          prev.map((d) => d.dayIndex === dayIndex ? res.data : d)
        )
        showToast('保存成功')
      }
    } catch (err) {
      alert(err.message)
    } finally {
      setSaving(false)
    }
  }

  // 总预算汇总
  const totalBudget = days.reduce((sum, d) => sum + (Number(d.budgetDay) || 0), 0)
  const totalSpots  = days.reduce((sum, d) => sum + (d.spots?.length || 0), 0)

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        {/* 顶部 */}
        <div className="mb-6">
          <button onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700
                       transition-colors mb-3">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
            </svg>
            返回
          </button>
          <h1 className="text-xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            点击每一天展开规划，可填写出行方式、住宿、三餐和景点
          </p>
        </div>

        {/* 统计卡 */}
        {days.length > 0 && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            {[
              ['天', days.length,  '行程天数'],
              ['处', totalSpots,   '规划地点'],
              ['¥', totalBudget > 0 ? totalBudget.toLocaleString() : '—', '预算合计'],
            ].map(([unit, val, label]) => (
              <div key={label} className="bg-white rounded-2xl border border-gray-100 shadow-sm
                                         px-4 py-3 text-center">
                <div className="text-xl font-bold text-indigo-600">
                  {unit === '¥' ? `¥${val}` : `${val} ${unit}`}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* 内容 */}
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full"/>
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-400 mb-4">{error}</p>
            <button onClick={load}
              className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm hover:bg-indigo-700">
              重试
            </button>
          </div>
        ) : days.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <div className="text-5xl mb-4">📅</div>
            <p>该{type === 'trip' ? '行程' : '计划'}还未设置日期区间</p>
            <p className="text-sm mt-1">请先在{type === 'trip' ? '行程' : '计划'}页设置出发和返回日期</p>
          </div>
        ) : (
          <div className="space-y-3">
            {days.map((day) => (
              <DayCard
                key={day.uuid}
                day={day}
                onSave={handleSaveDay}
                saving={saving}
              />
            ))}
          </div>
        )}
      </main>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50
                        bg-gray-900 text-white text-sm px-4 py-2 rounded-full shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
