import React, { useEffect, useState, useCallback, useRef } from 'react'
import Navbar from '../components/Navbar'
import { guideApi } from '../api/travel'
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
    0: { label: '待索引', dot: 'bg-amber-400',  cls: 'bg-amber-50 text-amber-600' },
    1: { label: '索引中', dot: 'bg-blue-400 animate-pulse', cls: 'bg-blue-50 text-blue-600' },
    2: { label: '已索引', dot: 'bg-green-400',  cls: 'bg-green-50 text-green-600' },
    3: { label: '失败',   dot: 'bg-red-400',    cls: 'bg-red-50 text-red-500' },
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

  // ESC 关闭
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
function GuideDetailModal({ guide, onClose, onEdit, onDelete }) {
  const [detail,   setDetail]   = useState(guide)
  const [fetching, setFetching] = useState(true)

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
          {/* 刷新按钮 */}
          <button
            onClick={onRefresh}
            title="刷新状态"
            className="w-7 h-7 flex items-center justify-center rounded-lg
                       text-gray-400 hover:text-indigo-500 hover:bg-indigo-50 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0
                   a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </button>
          {/* 添加按钮 */}
          <button
            onClick={onAdd}
            title="添加攻略"
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
            <GuideSidebarCard
              key={guide.uuid}
              guide={guide}
              onView={onView}
              onEdit={onEdit}
            />
          ))
        )}
      </div>

      {/* 图例 */}
      {guides.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-100 shrink-0">
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {[
              { dot: 'bg-green-400', label: '已加入 AI 知识库' },
              { dot: 'bg-blue-400 animate-pulse', label: '索引中' },
              { dot: 'bg-amber-400', label: '待索引' },
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
      {/* 颜色块 */}
      <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${colors[colorIdx]} shrink-0 mt-0.5`}/>

      {/* 内容 */}
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
            className="text-xs text-gray-300 hover:text-indigo-500 transition-colors opacity-0 group-hover:opacity-100">
            编辑
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 右侧：AI 聊天面板 ──────────────────────────────────────────────────────────

/** 单条来源引用卡片（可折叠） */
function SourceCard({ source }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="rounded-lg border border-gray-100 overflow-hidden text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2
                   text-left bg-gray-50 hover:bg-gray-100 transition-colors">
        <span className="text-gray-600 font-medium truncate flex-1 mr-2">
          📄 {source.title || source.articleId}
        </span>
        {source.score != null && (
          <span className="text-gray-400 shrink-0 mr-1">
            {Math.round(source.score * 100)}%
          </span>
        )}
        <svg
          className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>
      {expanded && (
        <div className="px-3 py-2 text-gray-500 leading-relaxed bg-white">
          {source.chunkText || '（无摘要）'}
        </div>
      )}
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

  // assistant 消息
  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-2.5 max-w-[90%]">
        {/* AI 头像 */}
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
            // 正在生成中占位
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
              <p className="text-xs text-gray-400 px-1">参考攻略：</p>
              {msg.sources.map((s, i) => <SourceCard key={i} source={s} />)}
            </div>
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
          <span>正在检索攻略库</span>
          {query && <span className="opacity-70 truncate max-w-[150px]">「{query}」</span>}
        </div>
      </div>
    </div>
  )
}

/** 对话面板 */
function ChatPanel() {
  const [messages,       setMessages]       = useState([])          // {role, content, sources?, streaming?, error?}
  const [input,          setInput]          = useState('')
  const [streaming,      setStreaming]      = useState(false)
  const [searchingQuery, setSearchingQuery] = useState(null)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // 自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, searchingQuery])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || streaming) return

    // 追加用户消息
    const historyForApi = [...messages.map((m) => ({ role: m.role, content: m.content })),
                           { role: 'user', content: text }]
    setMessages((prev) => [
      ...prev,
      { role: 'user',      content: text },
      { role: 'assistant', content: '', sources: [], streaming: true },
    ])
    setInput('')
    setStreaming(true)
    setSearchingQuery(null)

    try {
      const response = await aiApi.chatStream(historyForApi)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // 逐块读取 SSE
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (raw === '[DONE]') break

          try {
            const event = JSON.parse(raw)

            if (event.type === 'text') {
              setMessages((prev) => {
                const copy = [...prev]
                const last = { ...copy[copy.length - 1] }
                last.content = (last.content ?? '') + (event.content ?? '')
                copy[copy.length - 1] = last
                return copy
              })
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
              throw new Error(event.message || 'AI 服务错误')
            }
          } catch (parseErr) {
            // 跳过格式错误的事件
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const copy = [...prev]
        const last = { ...copy[copy.length - 1] }
        last.content  = last.content || '抱歉，AI 服务暂时不可用，请稍后重试。'
        last.error    = true
        last.streaming = false
        copy[copy.length - 1] = last
        return copy
      })
    } finally {
      // 去掉最后一条消息的 streaming 标志
      setMessages((prev) => {
        const copy = [...prev]
        const last = { ...copy[copy.length - 1] }
        last.streaming = false
        copy[copy.length - 1] = last
        return copy
      })
      setStreaming(false)
      setSearchingQuery(null)
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
          <p className="text-xs text-gray-400 mt-0.5">基于你的攻略库，为你定制行程建议</p>
        </div>
        {messages.length > 0 && (
          <button onClick={clearChat} disabled={streaming}
            className="text-xs text-gray-400 hover:text-red-400 disabled:opacity-40 transition-colors
                       flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-red-50">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5
                   4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
            清空对话
          </button>
        )}
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
              我会基于你的攻略库为你提供个性化的旅行建议，试着问我：
            </p>
            <div className="flex flex-col gap-2 w-full max-w-xs">
              {[
                '帮我规划一个 5 天的京都行程',
                '推荐清迈有哪些值得去的地方',
                '冬天去北海道需要注意什么',
              ].map((q) => (
                <button
                  key={q}
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

        {messages.map((msg, i) => <ChatMessage key={i} msg={msg} />)}

        {searchingQuery !== null && <SearchingIndicator query={searchingQuery} />}

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
            style={{ height: 'auto' }}
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
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                  d="M5 12h14M12 5l7 7-7 7"/>
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
  const [guides,   setGuides]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [modal,    setModal]    = useState(null)      // null | 'create' | guide obj (edit)
  const [viewGuide, setViewGuide] = useState(null)   // guide obj — 详情弹窗
  const [deleting,  setDeleting]  = useState(null)   // guide obj — 删除确认

  const loadGuides = useCallback(async () => {
    setLoading(true)
    try {
      const res = await guideApi.listMine()
      setGuides(res.data ?? [])
    } catch (_) {
      // 静默失败，保持现有列表
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadGuides() }, [loadGuides])

  // 自动轮询：有 PENDING(0) 或 INDEXING(1) 的攻略时，每 3 秒刷新一次状态
  useEffect(() => {
    const hasPending = guides.some((g) => g.aiStatus === 0 || g.aiStatus === 1)
    if (!hasPending) return
    const timer = setInterval(loadGuides, 3000)
    return () => clearInterval(timer)
  }, [guides, loadGuides])

  const handleDelete = async (guide) => {
    try {
      await guideApi.delete(guide.uuid)
      setDeleting(null)
      loadGuides()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* 页面主体：左右分栏 */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex gap-4 h-[calc(100vh-7.5rem)]">

          {/* ── 左侧攻略库 ────────────────────────────────────────────────── */}
          <div className="w-72 lg:w-80 shrink-0 bg-white rounded-2xl border border-gray-100
                          shadow-sm flex flex-col overflow-hidden">
            <GuideSidebar
              guides={guides}
              loading={loading}
              onRefresh={loadGuides}
              onView={(g)  => setViewGuide(g)}
              onEdit={(g)  => setModal(g)}
              onAdd={()    => setModal('create')}
            />
          </div>

          {/* ── 右侧 AI 聊天 ───────────────────────────────────────────────── */}
          <div className="flex-1 min-w-0 bg-white rounded-2xl border border-gray-100
                          shadow-sm flex flex-col overflow-hidden">
            <ChatPanel />
          </div>
        </div>
      </main>

      {/* 攻略详情弹窗 */}
      {viewGuide && (
        <GuideDetailModal
          guide={viewGuide}
          onClose={() => setViewGuide(null)}
          onEdit={(g) => { setViewGuide(null); setModal(g) }}
          onDelete={(g) => { setViewGuide(null); setDeleting(g) }}
        />
      )}

      {/* 创建/编辑 Modal */}
      {modal !== null && (
        <GuideFormModal
          guide={modal === 'create' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); loadGuides() }}
        />
      )}

      {/* 删除确认 */}
      {deleting && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl p-6">
            <h3 className="font-semibold text-gray-900 mb-2">确认删除</h3>
            <p className="text-sm text-gray-500 mb-1">
              确定要删除攻略「{deleting.title}」吗？
            </p>
            {deleting.aiStatus === 2 && (
              <p className="text-xs text-amber-500 mb-4">
                此攻略已加入 AI 知识库，删除后将同步从知识库中移除。
              </p>
            )}
            <div className="flex gap-3 mt-4">
              <button onClick={() => setDeleting(null)}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors">
                取消
              </button>
              <button onClick={() => handleDelete(deleting)}
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
