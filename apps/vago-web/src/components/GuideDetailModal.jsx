import React, { useEffect, useState } from 'react'
import { guideApi } from '../api/travel'

function fmtDate(str) {
  if (!str) return ''
  const d = new Date(str)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

const COVER_COLORS = [
  'from-rose-300 to-pink-400',
  'from-violet-300 to-purple-400',
  'from-sky-300 to-blue-400',
  'from-teal-300 to-emerald-400',
  'from-amber-300 to-orange-400',
]

/**
 * 攻略详情弹窗 — 小红书网页端双栏风格
 *
 * Props:
 *   guide   — 含 uuid 的攻略对象（可只含 uuid，组件内部会拉取完整数据）
 *   isMine  — 是否为当前用户自己的攻略（展示编辑/删除按钮）
 *   onClose — 关闭回调
 *   onEdit  — 编辑回调 (guide) => void
 *   onDelete— 删除回调 (guide) => void
 */
export default function GuideDetailModal({ guide, isMine, onClose, onEdit, onDelete }) {
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

  // ESC 关闭
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // 锁定 body 滚动
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

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

  const colorIdx = detail.uuid.charCodeAt(0) % COVER_COLORS.length
  const isDraft  = detail.status === 0

  return (
    // 遮罩层
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* 弹窗主体：小红书双栏 */}
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh]
                      flex overflow-hidden relative">

        {/* ── 关闭按钮 ── */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-20 w-8 h-8 rounded-full bg-black/20
                     hover:bg-black/40 backdrop-blur-sm flex items-center justify-center
                     text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>

        {/* ══ 左栏：封面 + 图片 ══════════════════════════════════════════════════ */}
        <div className="w-[45%] shrink-0 flex flex-col overflow-y-auto bg-gray-900">

          {/* 主封面 */}
          <div
            className={`w-full shrink-0 bg-gradient-to-br ${COVER_COLORS[colorIdx]}
                         flex flex-col justify-end p-4 relative`}
            style={{ minHeight: 320 }}
          >
            {/* 目的地标签 */}
            {detail.destination && (
              <span className="absolute top-4 left-4 bg-white/80 backdrop-blur-sm
                               text-sm text-gray-700 px-3 py-1 rounded-full font-medium">
                📍 {detail.destination}
              </span>
            )}
            {isDraft && (
              <span className="absolute top-4 right-12 bg-amber-400/90 backdrop-blur-sm
                               text-xs text-white px-2 py-0.5 rounded-full font-medium">
                草稿
              </span>
            )}
          </div>

          {/* 附图列表（暂无真实图片时展示占位） */}
          {!fetching && detail.imageKeys?.length > 0 && (
            <div className="flex flex-col gap-0.5 bg-gray-900">
              {detail.imageKeys.map((key, i) => (
                <div
                  key={i}
                  className="w-full bg-gray-800 flex items-center justify-center
                             aspect-video text-gray-500 text-xs"
                >
                  <span className="px-4 truncate">{key}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ══ 右栏：内容 + 互动 ══════════════════════════════════════════════════ */}
        <div className="flex-1 flex flex-col min-h-0">

          {/* 可滚动内容区 */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

            {/* 作者信息 */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                              flex items-center justify-center text-white text-sm font-semibold shrink-0">
                {detail.authorNickname?.[0] ?? '?'}
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">
                  {detail.authorNickname ?? '旅行者'}
                </p>
                <p className="text-xs text-gray-400">
                  {fmtDate(detail.createdAt)}
                  {detail.updatedAt && detail.updatedAt !== detail.createdAt
                    ? ` · 更新于 ${fmtDate(detail.updatedAt)}`
                    : ''}
                </p>
              </div>
            </div>

            <hr className="border-gray-100" />

            {/* 标题 */}
            <h2 className="text-xl font-bold text-gray-900 leading-snug">
              {detail.title}
            </h2>

            {/* 标签 */}
            {detail.tags?.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {detail.tags.map((tag) => (
                  <span key={tag}
                    className="text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-500">
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* 正文 */}
            {fetching ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin w-6 h-6 border-4 border-indigo-400
                                border-t-transparent rounded-full" />
              </div>
            ) : (
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {detail.content || '（暂无内容）'}
              </p>
            )}

            <hr className="border-gray-100" />

            {/* ── 评论区占位 ── */}
            <div>
              <p className="text-sm font-semibold text-gray-700 mb-3">
                评论
                <span className="text-xs font-normal text-gray-400 ml-2">
                  ({detail.commentCount ?? 0})
                </span>
              </p>
              <div className="rounded-xl border border-dashed border-gray-200
                              bg-gray-50 py-8 flex flex-col items-center gap-2 text-center">
                <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863
                       9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574
                       3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <p className="text-sm text-gray-400">评论功能即将上线</p>
                <p className="text-xs text-gray-300">抢先收藏这篇攻略吧</p>
              </div>
            </div>

            {/* 底部留白，防止内容被底栏遮住 */}
            <div className="h-2" />
          </div>

          {/* ── 固定底栏：统计 + 互动 + 操作 ── */}
          <div className="shrink-0 px-6 py-3 border-t border-gray-100 bg-white
                          flex items-center justify-between gap-4">

            {/* 统计 */}
            <div className="flex items-center gap-4 text-sm text-gray-400">
              {/* 浏览量 */}
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943
                       9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                {fetching ? '…' : (detail.viewCount ?? 0)}
              </span>

              {/* 点赞 */}
              <button
                onClick={handleLike}
                disabled={liked || likeLoading}
                className={`flex items-center gap-1.5 transition-colors
                  ${liked ? 'text-red-500' : 'hover:text-red-400'}`}
              >
                <svg className="w-4 h-4" fill={liked ? 'currentColor' : 'none'}
                  stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682
                       a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318
                       a4.5 4.5 0 00-6.364 0z"/>
                </svg>
                {detail.likeCount ?? 0}
              </button>

              {/* 收藏占位 */}
              <button
                disabled
                title="收藏功能即将上线"
                className="flex items-center gap-1.5 text-gray-300 cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                </svg>
                收藏
              </button>
            </div>

            {/* 编辑/删除（仅限自己的攻略） */}
            {isMine && (
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => { onClose(); onEdit?.(detail) }}
                  className="px-4 py-1.5 rounded-lg border border-gray-200 text-sm
                             text-gray-600 hover:text-indigo-600 hover:border-indigo-300
                             transition-colors"
                >
                  编辑
                </button>
                <button
                  onClick={() => { onClose(); onDelete?.(detail) }}
                  className="px-4 py-1.5 rounded-lg border border-red-200 text-sm
                             text-red-500 hover:bg-red-50 transition-colors"
                >
                  删除
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
