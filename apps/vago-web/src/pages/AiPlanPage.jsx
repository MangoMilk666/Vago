import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { aiApi } from '../api/ai'

// ── 工具：格式化日期 ──────────────────────────────────────────────────────────
function fmtDate(str) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

// ── aiStatus 徽章 ─────────────────────────────────────────────────────────────
function AiStatusBadge({ status, draft }) {
  if (draft) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full
                       bg-gray-100 text-gray-400 font-medium">
        草稿
      </span>
    )
  }
  const map = {
    0: { label: '待索引', dot: 'bg-amber-400',                    cls: 'bg-amber-50 text-amber-600' },
    1: { label: '索引中', dot: 'bg-blue-400 animate-pulse',       cls: 'bg-blue-50 text-blue-600' },
    2: { label: '已索引', dot: 'bg-green-400',                    cls: 'bg-green-50 text-green-600' },
    3: { label: '索引失败', dot: 'bg-red-400',                    cls: 'bg-red-50 text-red-500' },
  }
  // null / undefined — 旧数据未索引
  if (status == null) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full
                       font-medium bg-gray-50 text-gray-400">
        <span className="w-1.5 h-1.5 rounded-full shrink-0 bg-gray-300" />
        未加入知识库
      </span>
    )
  }
  const info = map[status] ?? { label: '未知', dot: 'bg-gray-300', cls: 'bg-gray-50 text-gray-400' }
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full font-medium ${info.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${info.dot}`} />
      {info.label}
    </span>
  )
}

// ── 攻略表单 Modal（创建/编辑） ────────────────────────────────────────────────
function GuideFormModal({ guide, onClose, onSaved }) {
  const isEdit = !!guide
  const [form, setForm] = useState({
    title:       guide?.title       ?? '',
    destination: guide?.destination ?? '',
    content:     guide?.content     ?? '',
    tags:        guide?.tags?.join('，') ?? '',
    status:      guide?.status      ?? 1,
  })
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim())   { setError('请填写攻略标题'); return }
    if (!form.content.trim()) { setError('请填写攻略内容'); return }
    setLoading(true); setError('')
    const tags = form.tags.split(/[，,、\s]+/).map((t) => t.trim()).filter(Boolean)
    const payload = { ...form, tags, status: Number(form.status) }
    try {
      if (isEdit) await guideApi.update(guide.uuid, payload)
      else        await guideApi.create(payload)
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
          <h2 className="font-semibold text-gray-900">{isEdit ? '编辑攻略' : '添加攻略'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">攻略标题 *</label>
            <input value={form.title} onChange={set('title')} maxLength={100}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="一句话概括你的旅行体验"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">目的地</label>
            <input value={form.destination} onChange={set('destination')} maxLength={200}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="例：京都、清迈、布达佩斯…"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">攻略内容 *</label>
            <textarea value={form.content} onChange={set('content')} rows={8}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm resize-none
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="详细描述你的旅行经历、推荐路线、避坑指南…"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">标签</label>
            <input value={form.tags} onChange={set('tags')}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="用逗号分隔，例：美食，打卡，亲子"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">发布状态</label>
            <select value={form.status} onChange={set('status')}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-indigo-400">
              <option value={1}>公开发布（自动加入 AI 攻略库）</option>
              <option value={0}>保存草稿（不加入 AI 攻略库）</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </form>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3 shrink-0">
          <button type="button" onClick={onClose}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                       hover:bg-gray-50 transition-colors">
            取消
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                       hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {loading ? '保存中…' : (Number(form.status) === 0 ? '保存草稿' : '发布并索引')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 攻略详情 Modal ─────────────────────────────────────────────────────────────
function GuideDetailModal({ guide, onClose, onEdit, onDelete, onIndexed }) {
  const [detail,      setDetail]      = useState(guide)
  const [fetching,    setFetching]    = useState(true)
  const [indexing,    setIndexing]    = useState(false)
  const [indexError,  setIndexError]  = useState('')

  useEffect(() => {
    let alive = true
    guideApi.detail(guide.uuid)
      .then((res) => { if (alive) setDetail(res.data) })
      .catch(() => {})
      .finally(() => { if (alive) setFetching(false) })
    return () => { alive = false }
  }, [guide.uuid])

  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  // 需要索引的条件：已发布 且满足以下任一：
  //   null — 旧数据从未索引
  //   0    — PENDING 卡死（Python 未启动或服务重启导致异步任务丢失）
  //   3    — 上次向量化失败
  const needsIndex = detail.status === 1 &&
    (detail.aiStatus == null || detail.aiStatus === 0 || detail.aiStatus === 3)
  const indexLabel = detail.aiStatus === 3
    ? '重试加入知识库'
    : detail.aiStatus === 0
      ? '重新触发索引'
      : '加入 AI 知识库'

  const handleIndex = async () => {
    setIndexing(true)
    setIndexError('')
    try {
      const res = await guideApi.index(detail.uuid)
      setDetail(res.data)          // aiStatus 已更新为 PENDING(0)
      onIndexed?.()                // 通知父组件刷新列表
    } catch (err) {
      setIndexError(err.message || '操作失败，请稍后重试')
    } finally {
      setIndexing(false)
    }
  }

  const colors = [
    'from-rose-300 to-pink-400',
    'from-violet-300 to-purple-400',
    'from-sky-300 to-blue-400',
    'from-teal-300 to-emerald-400',
    'from-amber-300 to-orange-400',
  ]
  const colorIdx = detail.uuid.charCodeAt(0) % colors.length

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* 封面区 */}
        <div className={`relative w-full bg-gradient-to-br ${colors[colorIdx]} shrink-0`}
             style={{ minHeight: 140 }}>
          <button onClick={onClose}
            className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/30
                       backdrop-blur-sm flex items-center justify-center
                       text-white hover:bg-black/50 transition-colors z-10">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
          <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between">
            {detail.destination
              ? <span className="bg-white/80 backdrop-blur-sm text-sm text-gray-700 px-3 py-1 rounded-full font-medium">{detail.destination}</span>
              : <span />}
            <AiStatusBadge status={detail.aiStatus} draft={detail.status === 0} />
          </div>
        </div>

        {/* 正文区 */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          <div className="flex items-start justify-between gap-2">
            <h2 className="text-xl font-bold text-gray-900 leading-snug">{detail.title}</h2>
            <p className="text-xs text-gray-400 shrink-0 mt-1">{fmtDate(detail.createdAt)}</p>
          </div>

          {detail.tags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {detail.tags.map((tag) => (
                <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 font-medium">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          {/* 加入知识库 / 重试按钮 */}
          {needsIndex && (
            <div className="flex flex-col gap-1.5">
              <button
                onClick={handleIndex}
                disabled={indexing}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                           bg-indigo-600 text-white text-sm font-medium
                           hover:bg-indigo-700 disabled:opacity-60 transition-colors">
                {indexing ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"/>
                    提交中…
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2
                           M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                    {indexLabel}
                  </>
                )}
              </button>
              {indexError && <p className="text-xs text-red-500 text-center">{indexError}</p>}
              {detail.aiStatus === 3 && !indexError && (
                <p className="text-xs text-gray-400 text-center">上次向量化失败，点击重新加入知识库</p>
              )}
            </div>
          )}

          <hr className="border-gray-100"/>

          {fetching ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin w-6 h-6 border-4 border-indigo-400 border-t-transparent rounded-full"/>
            </div>
          ) : (
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {detail.content || '（暂无内容）'}
            </p>
          )}
        </div>

        {/* 底栏 */}
        <div className="px-6 py-4 border-t border-gray-100 flex gap-3 shrink-0">
          <button onClick={() => { onClose(); onEdit(detail) }}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                       hover:text-indigo-600 hover:border-indigo-300 transition-colors">
            编辑
          </button>
          <button onClick={() => { onClose(); onDelete(detail) }}
            className="flex-1 py-2 rounded-xl border border-red-200 text-sm text-red-500
                       hover:bg-red-50 transition-colors">
            删除
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 左侧：攻略库面板 ──────────────────────────────────────────────────────────
function GuideSidebar({ guides, loading, onRefresh, onView, onEdit, onAdd }) {
  return (
    <aside className="flex flex-col h-full">
      {/* 标题 */}
      <div className="flex items-center justify-between px-4 pt-5 pb-3 shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">我的攻略库</h2>
          <p className="text-xs text-gray-400 mt-0.5">发布的攻略会自动加入 AI 知识库</p>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onRefresh} title="刷新状态"
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-gray-400 hover:text-indigo-500 hover:bg-indigo-50 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0
                   a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </button>
          <button onClick={onAdd} title="添加攻略"
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       bg-indigo-600 text-white hover:bg-indigo-700 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
            </svg>
          </button>
        </div>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-2">
        {loading && guides.length === 0 ? (
          <div className="flex justify-center pt-10">
            <div className="animate-spin w-6 h-6 border-4 border-indigo-400 border-t-transparent rounded-full"/>
          </div>
        ) : guides.length === 0 ? (
          <div className="flex flex-col items-center justify-center pt-10 text-center px-4">
            <div className="text-3xl mb-3">📖</div>
            <p className="text-xs text-gray-400 mb-3">还没有攻略，发布后 AI 可以检索你的旅行经验</p>
            <button onClick={onAdd}
              className="px-4 py-1.5 bg-indigo-600 text-white text-xs rounded-xl
                         hover:bg-indigo-700 transition-colors font-medium">
              添加第一篇攻略
            </button>
          </div>
        ) : (
          guides.map((guide) => (
            <GuideSidebarCard key={guide.uuid} guide={guide} onView={onView} onEdit={onEdit} />
          ))
        )}
      </div>

      {/* 图例 */}
      {guides.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-100 shrink-0">
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {[
              { dot: 'bg-green-400',                    label: '已加入知识库' },
              { dot: 'bg-blue-400 animate-pulse',       label: '索引中' },
              { dot: 'bg-amber-400',                    label: '待索引' },
              { dot: 'bg-red-400',                      label: '点击详情重试' },
            ].map(({ dot, label }) => (
              <span key={label} className="flex items-center gap-1 text-xs text-gray-400">
                <span className={`w-1.5 h-1.5 rounded-full ${dot}`}/>
                {label}
              </span>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}

// ── 攻略侧边栏卡片 ─────────────────────────────────────────────────────────────
function GuideSidebarCard({ guide, onView, onEdit }) {
  const colors = [
    'from-rose-300 to-pink-400',
    'from-violet-300 to-purple-400',
    'from-sky-300 to-blue-400',
    'from-teal-300 to-emerald-400',
    'from-amber-300 to-orange-400',
  ]
  const colorIdx = guide.uuid.charCodeAt(0) % colors.length
  const isDraft = guide.status === 0

  return (
    <div
      onClick={() => onView(guide)}
      className="group flex items-start gap-3 p-3 rounded-xl bg-white border border-gray-100
                 hover:border-indigo-200 hover:shadow-sm cursor-pointer transition-all"
    >
      <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${colors[colorIdx]} shrink-0 mt-0.5`}/>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 line-clamp-1 group-hover:text-indigo-600 transition-colors">
          {guide.title}
        </p>
        {guide.destination && (
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{guide.destination}</p>
        )}
        <div className="mt-1.5 flex items-center justify-between">
          <AiStatusBadge status={guide.aiStatus} draft={isDraft} />
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(guide) }}
            className="text-xs text-gray-300 hover:text-indigo-500 transition-colors
                       opacity-0 group-hover:opacity-100">
            编辑
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 右侧：AI 聊天面板 ──────────────────────────────────────────────────────────

/**
 * 单条个人资料引用卡片，可展开查看命中文本摘要。
 */
function SourceCard({ source }) {
  const [expanded, setExpanded] = useState(false)
  const sourceUuid = source.source_uuid || source.sourceUuid
  const title = source.title || sourceUuid

  return (
    <div className="rounded-lg border border-gray-100 overflow-hidden text-xs">
      <div className="flex items-center bg-gray-50">
        <div className="flex-1 flex items-center gap-1.5 px-3 py-2 min-w-0">
          <svg className="w-3 h-3 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0
                 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <span className="text-gray-600 font-medium truncate">
            {title}
          </span>
        </div>

        {/* 相似度 */}
        {source.score != null && (
          <span className="text-gray-400 shrink-0 px-1">
            {Math.round(source.score * 100)}%
          </span>
        )}

        {/* 展开/折叠摘要 */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="px-2 py-2 text-gray-400 hover:text-gray-600 shrink-0"
          title={expanded ? '收起摘要' : '展开摘要'}
        >
          <svg
            className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
      </div>

      {expanded && (
        <div className="px-3 py-2 text-gray-500 leading-relaxed bg-white border-t border-gray-100">
          {/* SSE 流式路径：Python model_dump() 输出 snake_case；非流式经 Java 映射为 camelCase */}
          {source.chunk_text || source.chunkText || '（无摘要）'}
        </div>
      )}
    </div>
  )
}

// ─── 结构化计划卡片子组件 ────────────────────────────────────────────────────────
function StructuredPlanCard({ plan }) {
  const navigate = useNavigate()
  const [savingDraft, setSavingDraft] = useState(false)
  const [savingTrip, setSavingTrip] = useState(false)
  const [savedType, setSavedType] = useState(null) // 'draft' | 'trip' | null
  const [saveError, setSaveError] = useState('')
  const [expandedDays, setExpandedDays] = useState({ 0: true }) // 默认展开第一天

  if (!plan) return null

  const toggleDay = (idx) => {
    setExpandedDays(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  const handleSaveDraft = async () => {
    setSavingDraft(true)
    setSaveError('')
    try {
      const res = await aiApi.saveDraft(plan)
      setSavedType('draft')
      const uuid = res.data?.uuid
      setTimeout(() => {
        navigate(`/plans/${uuid}/itinerary?type=plan&title=${encodeURIComponent(plan.title)}`)
      }, 800)
    } catch (err) {
      setSaveError(err.message || '保存草稿失败')
    } finally {
      setSavingDraft(false)
    }
  }

  const handleSaveTrip = async () => {
    if (!plan.start_date || !plan.end_date) return
    setSavingTrip(true)
    setSaveError('')
    try {
      const res = await aiApi.saveTrip(plan)
      setSavedType('trip')
      const uuid = res.data?.uuid
      setTimeout(() => {
        navigate(`/trips/${uuid}/itinerary?type=trip&title=${encodeURIComponent(plan.title)}`)
      }, 800)
    } catch (err) {
      setSaveError(err.message || '保存行程失败')
    } finally {
      setSavingTrip(false)
    }
  }

  const hasDates = !!(plan.start_date && plan.end_date)

  const getCategoryBadge = (cat) => {
    const map = {
      0: { label: '景点', cls: 'bg-emerald-50 text-emerald-600 border border-emerald-100' },
      1: { label: '餐厅', cls: 'bg-amber-50 text-amber-600 border border-amber-100' },
      2: { label: '购物', cls: 'bg-rose-50 text-rose-600 border border-rose-100' },
      3: { label: '娱乐', cls: 'bg-violet-50 text-violet-600 border border-violet-100' },
      4: { label: '中转', cls: 'bg-blue-50 text-blue-600 border border-blue-100' },
      5: { label: '其他', cls: 'bg-gray-50 text-gray-600 border border-gray-100' },
    }
    const info = map[cat] || map[5]
    return <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium shrink-0 ${info.cls}`}>{info.label}</span>
  }

  return (
    <div className="mt-3 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/20 to-white shadow-sm overflow-hidden transition-all duration-300 hover:shadow-md hover:border-indigo-200">
      {/* 头部信息 */}
      <div className="p-4 bg-gradient-to-r from-indigo-50/50 to-purple-50/50 border-b border-indigo-50 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-bold text-gray-900 text-base flex items-center gap-1.5">
              <span>🧭</span> {plan.title}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
              <span>📍</span> 目的地: <span className="font-medium text-gray-700">{plan.destination}</span>
            </p>
          </div>
          {plan.budget && (
            <div className="text-right shrink-0 bg-white/80 border border-indigo-50/50 px-2.5 py-1 rounded-xl">
              <span className="text-[10px] text-gray-400 block leading-none">总预算</span>
              <span className="text-sm font-extrabold text-indigo-600 leading-normal">
                {plan.budget} <span className="text-[10px] font-medium text-gray-500">{plan.budget_currency || 'CNY'}</span>
              </span>
            </div>
          )}
        </div>

        {/* 日期和天数 */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-gray-500 mt-1">
          {plan.start_date ? (
            <span className="flex items-center gap-1">
              📅 {plan.start_date} 至 {plan.end_date || '未定'}
            </span>
          ) : (
            <span className="text-amber-500 flex items-center gap-1 bg-amber-50 px-2 py-0.5 rounded-lg border border-amber-100/50 font-medium text-[11px]">
              ⚠️ 无具体出行日期，保存行程前需先存为草稿
            </span>
          )}
          <span className="flex items-center gap-1 font-medium bg-indigo-50/80 text-indigo-600 px-2 py-0.5 rounded-lg">
            🗺️ 共 {plan.days?.length || 0} 天行程
          </span>
        </div>
      </div>

      {/* 每日路线 */}
      <div className="p-4 space-y-3 max-h-[300px] overflow-y-auto border-b border-indigo-50/50">
        {plan.days?.map((day, idx) => {
          const isExpanded = !!expandedDays[idx]
          return (
            <div key={idx} className="border border-gray-100 rounded-xl bg-white/70 overflow-hidden shadow-xs">
              {/* 单日标题 */}
              <button
                onClick={() => toggleDay(idx)}
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-indigo-50/20 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="flex items-center justify-center w-5 h-5 rounded-lg bg-indigo-100 text-indigo-700 text-xs font-bold shrink-0">
                    {day.day_index || idx + 1}
                  </span>
                  <span className="text-xs font-semibold text-gray-800">
                    第 {day.day_index || idx + 1} 天行程 {day.day_date ? `(${day.day_date})` : ''}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {day.accommodation && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium max-w-[120px] truncate">
                      🏨 宿: {day.accommodation}
                    </span>
                  )}
                  <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                  </svg>
                </div>
              </button>

              {/* 单日详情 */}
              {isExpanded && (
                <div className="px-3.5 pb-3 pt-1 border-t border-gray-50 bg-white/50 space-y-2">
                  {/* 交通与餐饮 */}
                  {(day.transportation || day.meal_breakfast || day.meal_lunch || day.meal_dinner) && (
                    <div className="grid grid-cols-2 gap-1.5 text-[10px] text-gray-500 bg-gray-50/50 p-2 rounded-lg border border-gray-100/50">
                      {day.transportation && (
                        <div className="col-span-2 flex items-center gap-1">
                          🚗 <span className="font-medium text-gray-600">交通:</span> {day.transportation}
                        </div>
                      )}
                      {(day.meal_breakfast || day.meal_lunch || day.meal_dinner) && (
                        <div className="col-span-2 flex flex-wrap gap-x-3 gap-y-1 mt-0.5 border-t border-gray-100/50 pt-1">
                          {day.meal_breakfast && <span>🍳 早餐: {day.meal_breakfast}</span>}
                          {day.meal_lunch && <span>🍱 午餐: {day.meal_lunch}</span>}
                          {day.meal_dinner && <span>🍜 晚餐: {day.meal_dinner}</span>}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 景点时间轴 */}
                  {day.spots && day.spots.length > 0 ? (
                    <div className="space-y-2 relative pl-2 border-l border-indigo-50 mt-1">
                      {day.spots.map((spot, spotIdx) => (
                        <div key={spotIdx} className="relative group/spot">
                          <div className="absolute -left-[12.5px] top-[5px] w-2 h-2 rounded-full bg-indigo-400 border border-white group-hover/spot:bg-indigo-600 transition-colors"/>
                          <div className="flex flex-col gap-0.5">
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs font-semibold text-gray-800 leading-none">{spot.name}</span>
                              {getCategoryBadge(spot.category)}
                              {spot.duration_minutes && (
                                <span className="text-[10px] text-gray-400 shrink-0">⏱️ {spot.duration_minutes}分钟</span>
                              )}
                            </div>
                            {spot.address && (
                              <span className="text-[10px] text-gray-400 leading-tight">📍 {spot.address}</span>
                            )}
                            {spot.notes && (
                              <span className="text-[10px] text-gray-500 bg-indigo-50/30 px-2 py-1 rounded border border-indigo-50/10 mt-0.5 leading-normal italic">{spot.notes}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-gray-400 italic">这一天没有安排具体景点</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 操作按钮 */}
      <div className="p-4 bg-gray-50/70 border-t border-indigo-50/30 flex flex-col gap-2">
        <div className="flex gap-3">
          {/* 保存为草稿 */}
          <button
            onClick={handleSaveDraft}
            disabled={savingDraft || savingTrip || savedType !== null}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all
              ${savedType === 'draft'
                ? 'bg-green-100 text-green-600 border border-green-200 cursor-default'
                : 'bg-white text-gray-700 border border-gray-200 hover:border-indigo-300 hover:text-indigo-600 active:bg-gray-50 disabled:opacity-50'}`}
          >
            {savingDraft ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-indigo-600/50 border-t-indigo-600 rounded-full animate-spin"/>
                保存中...
              </>
            ) : savedType === 'draft' ? (
              <>💾 已保存为草稿</>
            ) : (
              <>💾 保存为草稿</>
            )}
          </button>

          {/* 保存为正式行程 */}
          <button
            onClick={handleSaveTrip}
            disabled={savingDraft || savingTrip || savedType !== null || !hasDates}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all
              ${savedType === 'trip'
                ? 'bg-green-100 text-green-600 border border-green-200 cursor-default'
                : !hasDates
                  ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed opacity-60'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 shadow-sm shadow-indigo-100'}`}
            title={!hasDates ? "需要明确的出行日期才能保存为正式行程，请先保存为草稿" : "保存为行程"}
          >
            {savingTrip ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/50 border-t-white rounded-full animate-spin"/>
                保存中...
              </>
            ) : savedType === 'trip' ? (
              <>✈️ 已保存为行程</>
            ) : (
              <>✈️ 保存为行程</>
            )}
          </button>
        </div>
        {saveError && <p className="text-[10px] text-red-500 text-center">{saveError}</p>}
      </div>
    </div>
  )
}

/** 单条消息气泡 */
function ChatMessage({ msg }) {
  const isUser = msg.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] px-4 py-2.5 rounded-2xl rounded-tr-sm
                        bg-indigo-600 text-white text-sm leading-relaxed whitespace-pre-wrap">
          {msg.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-2.5 max-w-[90%]">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600
                        flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5">
          AI
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          {/* 回答内容 */}
          {msg.content ? (
            <div className={`px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed whitespace-pre-wrap
              ${msg.error
                ? 'bg-red-50 text-red-600 border border-red-100'
                : 'bg-white border border-gray-100 text-gray-800 shadow-sm'}`}>
              {msg.content}
              {msg.streaming && (
                <span className="inline-block w-0.5 h-4 ml-0.5 bg-indigo-500 animate-pulse align-middle"/>
              )}
            </div>
          ) : msg.streaming ? (
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white border border-gray-100 shadow-sm">
              <div className="flex gap-1 items-center">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }}/>
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }}/>
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }}/>
              </div>
            </div>
          ) : null}

          {/* 引用来源 */}
          {msg.sources?.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-gray-400 px-1">参考资料：</p>
              {msg.sources.map((s, i) => (
                <SourceCard key={i} source={s} />
              ))}
            </div>
          )}

          {/* 结构化行程卡片 */}
          {msg.structuredPlan && (
            <StructuredPlanCard plan={msg.structuredPlan} />
          )}
        </div>
      </div>
    </div>
  )
}

/** 检索中提示 */
function SearchingIndicator({ query }) {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600
                        flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>
        <div className="px-4 py-2.5 rounded-2xl rounded-tl-sm bg-indigo-50 border border-indigo-100
                        text-xs text-indigo-600 flex items-center gap-1.5">
          <span>正在检索个人资料</span>
          {query && <span className="opacity-70 truncate max-w-[150px]">「{query}」</span>}
        </div>
      </div>
    </div>
  )
}

/** 结构化行程提取中提示 */
function ExtractingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600
                        flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>
        <div className="px-4 py-2.5 rounded-2xl rounded-tl-sm bg-purple-50 border border-purple-100
                        text-xs text-purple-600 flex items-center gap-1.5">
          <span>正在提取规划数据</span>
        </div>
      </div>
    </div>
  )
}

/** ─── 对话面板 ──────────────────────────────────────────────────────────────── */
function ChatPanel() {
  const [messages,       setMessages]       = useState([])
  const [input,          setInput]          = useState('')
  const [streaming,      setStreaming]      = useState(false)
  const [useRag,         setUseRag]         = useState(true)
  const [searchingQuery, setSearchingQuery] = useState(null)
  const [extractingPlan, setExtractingPlan] = useState(false)
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  const abortRef   = useRef(null)   // AbortController 引用，用于超时取消

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, searchingQuery, extractingPlan])

  // ── SSE 解析工具 ──────────────────────────────────────────────────────────

  /**
   * 从 SSE 一行 data 字段中解析出事件对象。
   *
   * Python vago-ai 通过 json.dumps(data, ensure_ascii=False) 生成 SSE 事件，
   * 正常情况下直接解析为 JSON 对象即可。
   * 此处保留双重编码兜底，以兼容未来可能发生的序列化格式变更。
   */
  const parseEventData = (raw) => {
    try {
      const parsed = JSON.parse(raw)
      // 正常情况：{ type: 'text', content: '...' }
      if (parsed && typeof parsed === 'object') return parsed
      // 双重编码兜底：parsed 是一个 JSON 字符串，需再解一次
      if (typeof parsed === 'string') {
        const inner = JSON.parse(parsed)
        if (inner && typeof inner === 'object') return inner
      }
    } catch (_) {
      // 解析失败，忽略该事件
    }
    return null
  }

  // ── 发送消息 ──────────────────────────────────────────────────────────────
  const sendMessage = async () => {
    const text = input.trim()
    if (!text || streaming) return

    // 过滤掉 content 为空或标记了 error 的历史消息，再拼入本轮用户消息。
    // 必要性：前一轮流式失败时 assistant 消息可能 content=''，若原样带入
    // 会触发 Java @NotBlank 校验报 4001；error 消息是前端提示文案，不属于对话语义。
    const historyForApi = [
      ...messages
        .filter((m) => !m.error && m.content && m.content.trim().length > 0)
        .map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: text },
    ]

    setMessages((prev) => [
      ...prev,
      { role: 'user',      content: text },
      { role: 'assistant', content: '', sources: [], streaming: true },
    ])
    setInput('')
    setStreaming(true)
    setSearchingQuery(null)
    setExtractingPlan(false)

    // 120 秒超时：旅行规划类长文回答生成时间可能超过 30 秒，适当延长防止误中断
    const controller = new AbortController()
    abortRef.current  = controller
    const timeoutId   = setTimeout(() => controller.abort(), 120000)

    try {
      const response = await aiApi.chatStream(historyForApi, controller.signal, useRag)

      if (!response.ok) {
        throw new Error(`服务响应异常（HTTP ${response.status}）`)
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer    = ''
      let streamEnd = false   // [DONE] 收到后跳出外层 while

      while (!streamEnd) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        // SSE 以 \n\n 分隔事件，按行处理
        const lines = buffer.split('\n')
        // 最后一段可能不完整，保留到下一个 chunk
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          // SSE spec allows optional space after "data:" colon.
          // Spring SseEmitter writes "data:" (no space); Python writes "data: " (with space).
          // Accept both: check for "data:" (5 chars), then trim any leading whitespace from the value.
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()

          // 流结束标记：同时退出内外层循环
          if (raw === '[DONE]') { streamEnd = true; break }

          const event = parseEventData(raw)
          if (!event) continue

          if (event.type === 'text') {
            // 逐 token 追加内容；首个文本到达时清除检索提示（兜底：
            // 当 RAG 无命中结果时 sources 事件不发送，searchingQuery 可能残留）
            setSearchingQuery(null)
            const textChunk = typeof event.content === 'string'
              ? event.content
              : Array.isArray(event.content)
                ? event.content.map((c) => (typeof c === 'string' ? c : c?.text ?? '')).join('')
                : ''
            if (textChunk) {
              setMessages((prev) => {
                const copy = [...prev]
                const last = { ...copy[copy.length - 1] }
                last.content = (last.content ?? '') + textChunk
                copy[copy.length - 1] = last
                return copy
              })
            }
          } else if (event.type === 'searching') {
            setSearchingQuery(event.query ?? '')
          } else if (event.type === 'sources') {
            setSearchingQuery(null)
            setMessages((prev) => {
              const copy = [...prev]
              const last = { ...copy[copy.length - 1] }
              last.sources = event.sources ?? []
              copy[copy.length - 1] = last
              return copy
            })
          } else if (event.type === 'error') {
            // 将 Python 端错误作为错误消息展示，不中断流（流中还会跟随 [DONE]）
            setMessages((prev) => {
              const copy = [...prev]
              const last = { ...copy[copy.length - 1] }
              last.content = event.message || 'AI 生成失败'
              last.error   = true
              copy[copy.length - 1] = last
              return copy
            })
          } else if (event.type === 'extracting_plan') {
            // 文本回答生成完毕，即将开始结构化行程提取（Plan Extraction）
            setSearchingQuery(null)
            setExtractingPlan(true)
          } else if (event.type === 'structured_plan') {
            setExtractingPlan(false)
            setMessages((prev) => {
              const copy = [...prev]
              const last = { ...copy[copy.length - 1] }
              last.structuredPlan = event.data ?? null
              copy[copy.length - 1] = last
              return copy
            })
          }
        }
      }
    } catch (err) {
      const isTimeout = err.name === 'AbortError'
      const errMsg    = isTimeout
        ? '系统繁忙，请稍后再试（请确认 AI 服务已启动）'
        : `连接失败：${err.message}`

      setMessages((prev) => {
        const copy = [...prev]
        const last = { ...copy[copy.length - 1] }
        last.content  = last.content || errMsg
        last.error    = true
        last.streaming = false
        copy[copy.length - 1] = last
        return copy
      })
    } finally {
      clearTimeout(timeoutId)
      abortRef.current = null
      // 去掉流式光标
      setMessages((prev) => {
        const copy = [...prev]
        const last = { ...copy[copy.length - 1] }
        last.streaming = false
        copy[copy.length - 1] = last
        return copy
      })
      setStreaming(false)
      setSearchingQuery(null)
      setExtractingPlan(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearChat = () => {
    if (streaming) return
    setMessages([])
    setSearchingQuery(null)
    setExtractingPlan(false)
  }

  return (
    <section className="flex flex-col h-full">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-gray-100 shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600
                             flex items-center justify-center text-white text-[10px] font-bold">
              AI
            </span>
            旅行规划助手
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">按当前问题选择通用知识或个人旅行资料</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-xs text-gray-400">
            <input type="checkbox" checked={useRag} onChange={(event) => setUseRag(event.target.checked)} disabled={streaming} />
            使用个人资料
          </label>
          {messages.length > 0 && (<button onClick={clearChat} disabled={streaming}
            className="text-xs text-gray-400 hover:text-red-400 disabled:opacity-40
                       transition-colors flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-red-50">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5
                   4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
            清空对话
          </button>)}
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-10">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600
                            flex items-center justify-center mb-4 shadow-lg shadow-indigo-200">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14
                     a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
              </svg>
            </div>
            <p className="text-gray-600 font-medium mb-2">你好！我是叠迹旅行规划助手</p>
            <p className="text-sm text-gray-400 max-w-xs leading-relaxed mb-6">
              我会根据当前问题选择通用知识或个人旅行资料，试着问我：
            </p>
            <div className="flex flex-col gap-2 w-full max-w-xs">
              {[
                '帮我规划一个 5 天的京都行程',
                '推荐清迈有哪些值得去的地方',
                '冬天去北海道需要注意什么',
              ].map((q) => (
                <button key={q}
                  onClick={() => { setInput(q); inputRef.current?.focus() }}
                  className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-600
                             text-left hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50
                             transition-colors">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}
        {searchingQuery !== null && <SearchingIndicator query={searchingQuery} />}
        {extractingPlan && <ExtractingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="px-4 pb-4 pt-3 border-t border-gray-100 shrink-0">
        <div className="flex items-end gap-2 bg-white rounded-2xl border border-gray-200
                        shadow-sm focus-within:border-indigo-400 focus-within:ring-2
                        focus-within:ring-indigo-100 transition-all px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            rows={1}
            placeholder="描述你的旅行需求，按 Enter 发送…"
            className="flex-1 text-sm text-gray-800 placeholder-gray-400 resize-none
                       focus:outline-none bg-transparent leading-relaxed py-1 min-h-[36px]
                       max-h-[120px] disabled:opacity-50"
            onInput={(e) => {
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || streaming}
            className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center
                       text-white shrink-0 self-end mb-0.5
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {streaming ? (
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"/>
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            )}
          </button>
        </div>
        <p className="text-xs text-gray-300 mt-1.5 text-center">
          AI 生成内容仅供参考，具体行程以实际情况为准
        </p>
      </div>

    </section>
  )
}

// ── 主页面 ────────────────────────────────────────────────────────────────────
export default function AiPlanPage() {
  return (
    <div className="app-page">
      <Navbar />

      <main className="app-main py-6">
        <div className="h-[calc(100vh-7.5rem)]">
          {/* AI 仅在 Agent 判断资料确有帮助时才触发可选语义检索。 */}
          <div className="h-full min-w-0 bg-white rounded-2xl border border-gray-100
                          shadow-sm flex flex-col overflow-hidden">
            <ChatPanel />
          </div>
        </div>
      </main>
    </div>
  )
}
