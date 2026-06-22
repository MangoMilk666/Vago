import React, { useEffect, useState, useCallback } from 'react'
import Navbar from '../components/Navbar'
import GuideDetailModal from '../components/GuideDetailModal'
import CollectPanel from '../components/CollectPanel'
import { guideApi } from '../api/travel'

// ── 工具：格式化日期 ──────────────────────────────────────────────────────────
function fmtDate(str) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

// ── 攻略卡片（瀑布流样式）────────────────────────────────────────────────────
function GuideCard({ guide, isMine, onOpen, onEdit, onDelete, onLike, onUnlike, onCollect, collected }) {
  const [liked, setLiked] = useState(!!guide.liked)

  const handleLike = async (e) => {
    e.stopPropagation()
    try {
      if (liked) {
        await onUnlike(guide.uuid)
        setLiked(false)
      } else {
        await onLike(guide.uuid)
        setLiked(true)
      }
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

        {/* 底部：作者 + 点赞 + 收藏 */}
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

          <div className="flex items-center gap-2">
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

            <button onClick={(e) => { e.stopPropagation(); onCollect(guide) }}
              className={`flex items-center gap-0.5 text-xs transition-colors
                ${collected ? 'text-indigo-500' : 'text-gray-400 hover:text-indigo-500'}`}>
              <svg className="w-3.5 h-3.5" fill={collected ? 'currentColor' : 'none'}
                stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
              </svg>
            </button>
          </div>
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

// ── 创建/编辑 Modal ──────────────────────────────────────────────────────────
// GuideDetailModal 已提取至 src/components/GuideDetailModal.jsx
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
  const [collecting, setCollecting]  = useState(null)   // guide obj — 收藏面板
  const [collectedSet, setCollectedSet] = useState(new Set()) // 已收藏的攻略 UUID 集合
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

  const handleCollectChange = (guideUuid, isCollected) => {
    setCollectedSet((prev) => {
      const next = new Set(prev)
      if (isCollected) next.add(guideUuid)
      else next.delete(guideUuid)
      return next
    })
  }

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
                  collected={collectedSet.has(guide.uuid)}
                  onOpen={(g) => setViewGuide(g)}
                  onEdit={(g) => setModal(g)}
                  onDelete={(g) => setDeleting(g)}
                  onLike={guideApi.like}
                  onUnlike={guideApi.unlike}
                  onCollect={(g) => setCollecting(g)}
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

      {/* 收藏面板 */}
      {collecting && (
        <CollectPanel
          guideUuid={collecting.uuid}
          guideTitle={collecting.title}
          onClose={() => setCollecting(null)}
          onCollectChange={handleCollectChange}
        />
      )}

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
