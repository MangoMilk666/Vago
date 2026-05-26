import React, { useEffect, useState, useCallback } from 'react'
import Navbar from '../components/Navbar'
import { guideApi } from '../api/travel'

// ── 工具：格式化日期 ──────────────────────────────────────────────────────────
function fmtDate(str) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

// ── 攻略卡片（瀑布流样式）────────────────────────────────────────────────────
function GuideCard({ guide, isMine, onOpen, onEdit, onDelete, onLike }) {
  const [liked, setLiked] = useState(false)

  const handleLike = async (e) => {
    e.stopPropagation()
    if (liked) return
    try {
      await onLike(guide.uuid)
      setLiked(true)
    } catch (_) {}
  }

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
      onClick={() => onOpen(guide)}
      className="break-inside-avoid mb-3 bg-white rounded-2xl overflow-hidden
                 shadow-sm hover:shadow-md transition-shadow cursor-pointer group"
    >
      {/* 封面图 */}
      <div
        className={`w-full bg-gradient-to-br ${colors[colorIdx]}
                     flex items-end justify-between p-3`}
        style={{ minHeight: 120 + (guide.uuid.charCodeAt(2) % 3) * 40 }}
      >
        {guide.destination ? (
          <span className="bg-white/80 backdrop-blur-sm text-xs text-gray-700
                           px-2 py-0.5 rounded-full font-medium">
            {guide.destination}
          </span>
        ) : <span />}

        {isDraft && (
          <span className="bg-amber-400/90 backdrop-blur-sm text-xs text-white
                           px-2 py-0.5 rounded-full font-medium tracking-wide">
            草稿
          </span>
        )}
      </div>

      {/* 内容区 */}
      <div className="p-3">
        <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 leading-snug mb-2
                       group-hover:text-indigo-600 transition-colors">
          {guide.title}
        </h3>

        {/* 标签 */}
        {guide.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {guide.tags.slice(0, 3).map((tag) => (
              <span key={tag}
                className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-500">
                #{tag}
              </span>
            ))}
          </div>
        )}

        {/* 底部：作者 + 点赞 */}
        <div className="flex items-center justify-between mt-1">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                            flex items-center justify-center text-white text-xs font-semibold shrink-0">
              {guide.authorNickname?.[0] ?? '?'}
            </div>
            <span className="text-xs text-gray-500 line-clamp-1 max-w-[80px]">
              {guide.authorNickname ?? '旅行者'}
            </span>
          </div>

          <button onClick={handleLike}
            className={`flex items-center gap-0.5 text-xs transition-colors
              ${liked ? 'text-red-500' : 'text-gray-400 hover:text-red-400'}`}>
            <svg className="w-3.5 h-3.5" fill={liked ? 'currentColor' : 'none'}
              stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
            <span>{(guide.likeCount ?? 0) + (liked ? 1 : 0)}</span>
          </button>
        </div>

        {/* 我的攻略 — 编辑/删除 */}
        {isMine && (
          <div className="flex gap-1.5 mt-2 pt-2 border-t border-gray-50">
            <button onClick={(e) => { e.stopPropagation(); onEdit(guide) }}
              className="flex-1 py-1 rounded-lg text-xs text-gray-500
                         hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
              编辑
            </button>
            <button onClick={(e) => { e.stopPropagation(); onDelete(guide) }}
              className="flex-1 py-1 rounded-lg text-xs text-gray-500
                         hover:text-red-500 hover:bg-red-50 transition-colors">
              删除
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── 攻略详情 Modal ────────────────────────────────────────────────────────────
function GuideDetailModal({ guide, isMine, onClose, onEdit, onDelete }) {
  const [detail,      setDetail]      = useState(guide)
  const [liked,       setLiked]       = useState(false)
  const [likeLoading, setLikeLoading] = useState(false)
  const [fetching,    setFetching]    = useState(true)

  // 拉取完整详情（同时触发后端浏览量 +1）
  useEffect(() => {
    let alive = true
    setFetching(true)
    guideApi.detail(guide.uuid)
      .then((res) => { if (alive) setDetail(res.data) })
      .catch(() => {})
      .finally(() => { if (alive) setFetching(false) })
    return () => { alive = false }
  }, [guide.uuid])

  // 按 ESC 关闭
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleLike = async () => {
    if (liked || likeLoading) return
    setLikeLoading(true)
    try {
      await guideApi.like(detail.uuid)
      setLiked(true)
      setDetail((d) => ({ ...d, likeCount: (d.likeCount ?? 0) + 1 }))
    } catch (_) {}
    finally { setLikeLoading(false) }
  }

  const colors = [
    'from-rose-300 to-pink-400',
    'from-violet-300 to-purple-400',
    'from-sky-300 to-blue-400',
    'from-teal-300 to-emerald-400',
    'from-amber-300 to-orange-400',
  ]
  const colorIdx = detail.uuid.charCodeAt(0) % colors.length
  const isDraft   = detail.status === 0

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl
                      max-h-[90vh] flex flex-col overflow-hidden">

        {/* 封面区 */}
        <div className={`relative w-full bg-gradient-to-br ${colors[colorIdx]} shrink-0`}
             style={{ minHeight: 180 }}>
          {/* 关闭按钮 */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/30
                       backdrop-blur-sm flex items-center justify-center
                       text-white hover:bg-black/50 transition-colors z-10"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>

          {/* 目的地 + 草稿标识 */}
          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
            {detail.destination ? (
              <span className="bg-white/80 backdrop-blur-sm text-sm text-gray-700
                               px-3 py-1 rounded-full font-medium">
                {detail.destination}
              </span>
            ) : <span />}
            {isDraft && (
              <span className="bg-amber-400/90 backdrop-blur-sm text-xs text-white
                               px-2 py-0.5 rounded-full font-medium tracking-wide">
                草稿
              </span>
            )}
          </div>
        </div>

        {/* 正文区（可滚动） */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">

          {/* 作者行 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                              flex items-center justify-center text-white text-sm font-semibold shrink-0">
                {detail.authorNickname?.[0] ?? '?'}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {detail.authorNickname ?? '旅行者'}
                </p>
                <p className="text-xs text-gray-400">
                  发布于 {fmtDate(detail.createdAt)}
                  {detail.updatedAt && detail.updatedAt !== detail.createdAt
                    ? ` · 更新于 ${fmtDate(detail.updatedAt)}`
                    : ''}
                </p>
              </div>
            </div>

            {/* 统计：浏览 + 点赞 */}
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7
                       -1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                {fetching ? '…' : (detail.viewCount ?? 0)}
              </span>
              <button
                onClick={handleLike}
                disabled={liked || likeLoading}
                className={`flex items-center gap-1 transition-colors
                  ${liked ? 'text-red-500' : 'hover:text-red-400'}`}
              >
                <svg className="w-3.5 h-3.5" fill={liked ? 'currentColor' : 'none'}
                  stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682
                       a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318
                       a4.5 4.5 0 00-6.364 0z"/>
                </svg>
                {detail.likeCount ?? 0}
              </button>
            </div>
          </div>

          {/* 标题 */}
          <h2 className="text-xl font-bold text-gray-900 leading-snug">
            {detail.title}
          </h2>

          {/* 标签 */}
          {detail.tags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {detail.tags.map((tag) => (
                <span key={tag}
                  className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 font-medium">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          <hr className="border-gray-100"/>

          {/* 正文 */}
          {fetching ? (
            <div className="flex justify-center py-10">
              <div className="animate-spin w-6 h-6 border-4 border-indigo-400
                              border-t-transparent rounded-full"/>
            </div>
          ) : (
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {detail.content || '（暂无内容）'}
            </p>
          )}

          {/* 图片列表（有数据时展示） */}
          {!fetching && detail.imageKeys?.length > 0 && (
            <div className="grid grid-cols-2 gap-2 pt-2">
              {detail.imageKeys.map((key, i) => (
                <div key={i}
                  className="rounded-xl overflow-hidden bg-gray-100 aspect-video
                             flex items-center justify-center text-gray-400 text-xs">
                  {/* 当前阶段暂无 OSS 渲染；占位展示 key */}
                  <span className="px-2 truncate">{key}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 底栏：我的攻略可编辑/删除 */}
        {isMine && (
          <div className="px-6 py-4 border-t border-gray-100 flex gap-3 shrink-0">
            <button
              onClick={() => { onClose(); onEdit(detail) }}
              className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                         hover:text-indigo-600 hover:border-indigo-300 transition-colors"
            >
              编辑
            </button>
            <button
              onClick={() => { onClose(); onDelete(detail) }}
              className="flex-1 py-2 rounded-xl border border-red-200 text-sm text-red-500
                         hover:bg-red-50 transition-colors"
            >
              删除
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── 创建/编辑 Modal ──────────────────────────────────────────────────────────
function GuideModal({ guide, onClose, onSaved }) {
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
      if (isEdit) {
        await guideApi.update(guide.uuid, payload)
      } else {
        await guideApi.create(payload)
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
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">{isEdit ? '编辑攻略' : '发布攻略'}</h2>
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
              <option value={1}>公开发布</option>
              <option value={0}>保存草稿</option>
            </select>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </form>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <button type="button" onClick={onClose}
            className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                       hover:bg-gray-50 transition-colors">
            取消
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                       hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {loading ? '发布中…' : (form.status == 0 ? '保存草稿' : '发布攻略')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 主页面 ───────────────────────────────────────────────────────────────────
export default function GuidePage() {
  const [tab,        setTab]        = useState('discover') // 'discover' | 'mine'
  const [guides,     setGuides]     = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [page,       setPage]       = useState(1)
  const [total,      setTotal]      = useState(0)
  const [modal,      setModal]      = useState(null)   // null | 'create' | guide obj (edit)
  const [deleting,   setDeleting]   = useState(null)   // guide obj
  const [viewGuide,  setViewGuide]  = useState(null)   // guide obj — 详情弹窗
  const PAGE_SIZE = 20

  const loadDiscover = useCallback(async (p = 1) => {
    setLoading(true)
    setError('')
    try {
      const res = await guideApi.listPublished(p, PAGE_SIZE)
      const { records, total: t } = res.data
      setGuides(p === 1 ? (records ?? []) : (prev) => [...prev, ...(records ?? [])])
      setTotal(t ?? 0)
      setPage(p)
    } catch (err) {
      setError(err.message || '加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadMine = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await guideApi.listMine()
      setGuides(res.data ?? [])
    } catch (err) {
      setError(err.message || '加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setGuides([])
    setPage(1)
    if (tab === 'discover') loadDiscover(1)
    else loadMine()
  }, [tab])

  const hasMore = tab === 'discover' && guides.length < total

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* 顶部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">攻略广场</h1>
            <p className="text-sm text-gray-500 mt-0.5">发现好地方，分享旅行故事</p>
          </div>
          {tab === 'mine' && (
            <button onClick={() => setModal('create')}
              className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white
                         rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
              </svg>
              发布攻略
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit mb-6">
          {[['discover', '发现'], ['mine', '我的攻略']].map(([key, label]) => (
            <button key={key} onClick={() => setTab(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
                ${tab === key
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'}`}>
              {label}
            </button>
          ))}
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl
                          text-sm text-red-600 flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            {error}
          </div>
        )}

        {/* 加载中 */}
        {loading && guides.length === 0 ? (
          <div className="flex justify-center py-20">
            <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full"/>
          </div>
        ) : guides.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="text-5xl mb-4">📖</div>
            <p className="text-gray-500 mb-4">
              {tab === 'mine' ? '还没有发布过攻略' : '暂无公开攻略'}
            </p>
            {tab === 'mine' && (
              <button onClick={() => setModal('create')}
                className="px-5 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium
                           hover:bg-indigo-700 transition-colors">
                发布第一篇攻略
              </button>
            )}
          </div>
        ) : (
          <>
            {/* 瀑布流（CSS columns） */}
            <div className="columns-2 md:columns-3 lg:columns-4 gap-3">
              {guides.map((guide) => (
                <GuideCard
                  key={guide.uuid}
                  guide={guide}
                  isMine={tab === 'mine'}
                  onOpen={(g) => setViewGuide(g)}
                  onEdit={(g) => setModal(g)}
                  onDelete={(g) => setDeleting(g)}
                  onLike={guideApi.like}
                />
              ))}
            </div>

            {/* 加载更多 */}
            {hasMore && (
              <div className="flex justify-center mt-8">
                <button
                  onClick={() => loadDiscover(page + 1)}
                  disabled={loading}
                  className="px-6 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-600
                             hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-50
                             transition-colors">
                  {loading ? '加载中…' : '加载更多'}
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* 攻略详情弹窗 */}
      {viewGuide && (
        <GuideDetailModal
          guide={viewGuide}
          isMine={tab === 'mine'}
          onClose={() => setViewGuide(null)}
          onEdit={(g) => setModal(g)}
          onDelete={(g) => setDeleting(g)}
        />
      )}

      {/* 创建/编辑 Modal */}
      {modal !== null && (
        <GuideModal
          guide={modal === 'create' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null)
            if (tab === 'mine') loadMine()
            else loadDiscover(1)
          }}
        />
      )}

      {/* 删除确认 */}
      {deleting && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl p-6">
            <h3 className="font-semibold text-gray-900 mb-2">确认删除</h3>
            <p className="text-sm text-gray-500 mb-6">
              确定要删除攻略「{deleting.title}」吗？
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleting(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors">取消</button>
              <button onClick={async () => {
                  try {
                    await guideApi.delete(deleting.uuid)
                    setDeleting(null)
                    if (tab === 'mine') loadMine()
                    else loadDiscover(1)
                  } catch (err) { alert(err.message) }
                }}
                className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-medium
                           hover:bg-red-600 transition-colors">确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
