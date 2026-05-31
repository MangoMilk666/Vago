import React, { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getProfile, updateProfile } from '../api/user'
import { getAuth, saveAuth } from '../stores/auth'
import Navbar from '../components/Navbar'

// ── 头像展示 ──────────────────────────────────────────────────────────────────

function AvatarDisplay({ url, nickname, className = 'w-24 h-24 text-3xl' }) {
  if (url) {
    return <img src={url} alt="avatar" className={`${className} rounded-full object-cover`} />
  }
  return (
    <div className={`${className} rounded-full bg-gradient-to-br from-indigo-400 to-purple-500
                     flex items-center justify-center text-white font-bold`}>
      {nickname?.[0] ?? '?'}
    </div>
  )
}

// ── 只读信息行 ────────────────────────────────────────────────────────────────

function InfoRow({ label, value, action }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-400 w-20 shrink-0">{label}</span>
      <span className="text-sm text-gray-700 flex-1">{value ?? '—'}</span>
      {action}
    </div>
  )
}

// ── 主页面 ────────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const navigate = useNavigate()
  const fileRef  = useRef(null)
  const auth     = getAuth()

  const [form, setForm] = useState({
    nickname:  auth?.user?.nickname  ?? '',
    email:     auth?.user?.email     ?? '',
    avatarUrl: auth?.user?.avatarUrl ?? '',
  })
  const [saving,  setSaving]  = useState(false)
  const [success, setSuccess] = useState(false)
  const [error,   setError]   = useState('')

  const user = auth?.user ?? {}

  // ── 头像本地预览 ────────────────────────────────────────────────────────────
  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { setError('图片不能超过 2 MB'); return }
    const reader = new FileReader()
    reader.onload = (ev) => setForm((f) => ({ ...f, avatarUrl: ev.target.result }))
    reader.readAsDataURL(file)
  }

  // ── 提交 ────────────────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess(false)
    setSaving(true)

    const payload = {}
    if (form.nickname.trim() && form.nickname !== user.nickname)   payload.nickname   = form.nickname.trim()
    if (form.email.trim()    !== (user.email ?? ''))               payload.email      = form.email.trim() || undefined
    if (form.avatarUrl       !== user.avatarUrl)                   payload.avatarUuid = form.avatarUrl

    if (Object.keys(payload).length === 0) { setSaving(false); setSuccess(true); return }

    try {
      const res         = await updateProfile(payload)
      const updatedUser = res.data
      saveAuth({ accessToken: auth.accessToken, refreshToken: auth.refreshToken, user: updatedUser })
      setForm((f) => ({
        ...f,
        nickname:  updatedUser.nickname  ?? f.nickname,
        email:     updatedUser.email     ?? f.email,
        avatarUrl: updatedUser.avatarUrl ?? f.avatarUrl,
      }))
      setSuccess(true)
    } catch (err) {
      setError(err.message || '保存失败，请稍后重试')
    } finally {
      setSaving(false)
    }
  }

  const planBadge = user.planType === 1
    ? <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">付费版</span>
    : <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">免费版</span>

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* 页头 */}
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate(-1)}
            className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 hover:text-gray-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
            </svg>
          </button>
          <h1 className="text-2xl font-bold text-gray-900">个人资料</h1>
        </div>

        {/* 双栏主体 */}
        <div className="flex gap-6 items-start">

          {/* ── 左栏：头像 + 账号只读信息 ── */}
          <div className="w-72 shrink-0 space-y-5">

            {/* 头像卡片 */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col items-center gap-4">
              <div className="relative group">
                <AvatarDisplay url={form.avatarUrl} nickname={form.nickname} />
                <div
                  onClick={() => fileRef.current?.click()}
                  className="absolute inset-0 rounded-full bg-black/40 flex items-center
                             justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                >
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07
                         4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012
                         2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/>
                  </svg>
                </div>
              </div>

              <div className="text-center">
                <p className="font-semibold text-gray-900">{form.nickname || '—'}</p>
                <p className="text-xs text-gray-400 mt-0.5">点击头像更换图片</p>
              </div>

              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="w-full py-1.5 rounded-lg border border-gray-200 text-sm text-gray-600
                           hover:bg-gray-50 transition-colors"
              >
                更换头像
              </button>
              <p className="text-xs text-gray-400 -mt-2">JPG / PNG / WebP，最大 2 MB</p>

              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            {/* 账号信息卡片 */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">账号信息</h2>
              <InfoRow label="手机号" value={user.phone}
                action={
                  <span className="text-xs text-gray-300 cursor-not-allowed" title="换绑功能开发中">
                    换绑
                  </span>
                }
              />
              <InfoRow label="套餐" value={null} action={planBadge} />
              <InfoRow
                label="攻略配额"
                value={user.articleQuota != null ? `${user.articleQuota} 篇` : null}
              />
              <InfoRow
                label="注册时间"
                value={user.createdAt ? user.createdAt.slice(0, 10) : null}
              />
            </div>
          </div>

          {/* ── 右栏：可编辑字段 ── */}
          <form onSubmit={handleSubmit} className="flex-1 space-y-5">

            {/* 基本信息 */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-5">基本信息</h2>

              <div className="space-y-5">
                {/* 昵称 */}
                <div className="grid grid-cols-[120px_1fr] items-center gap-4">
                  <label className="text-sm text-gray-500 text-right">昵称</label>
                  <input
                    type="text"
                    value={form.nickname}
                    onChange={(e) => setForm((f) => ({ ...f, nickname: e.target.value }))}
                    maxLength={20}
                    placeholder="2-20 个字符"
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full
                               focus:outline-none focus:ring-2 focus:ring-indigo-300
                               focus:border-indigo-400 transition"
                  />
                </div>

                {/* 邮箱 */}
                <div className="grid grid-cols-[120px_1fr] items-center gap-4">
                  <label className="text-sm text-gray-500 text-right">邮箱</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="选填"
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full
                               focus:outline-none focus:ring-2 focus:ring-indigo-300
                               focus:border-indigo-400 transition"
                  />
                </div>

                {/* 手机号（只读） */}
                <div className="grid grid-cols-[120px_1fr] items-center gap-4">
                  <label className="text-sm text-gray-500 text-right">手机号</label>
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      value={user.phone ?? ''}
                      disabled
                      className="border border-gray-100 rounded-lg px-3 py-2 text-sm w-full
                                 bg-gray-50 text-gray-400 cursor-not-allowed"
                    />
                    <button
                      type="button"
                      disabled
                      title="换绑功能开发中"
                      className="shrink-0 text-xs text-gray-300 cursor-not-allowed whitespace-nowrap"
                    >
                      换绑
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* 反馈 + 按钮行 */}
            <div className="flex items-center justify-between">
              <div className="text-sm">
                {error   && <span className="text-red-500">{error}</span>}
                {success && !error && <span className="text-green-600">保存成功</span>}
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => navigate(-1)}
                  className="px-5 py-2 rounded-xl border border-gray-200 text-gray-600 text-sm
                             font-medium hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium
                             hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed
                             transition-colors"
                >
                  {saving ? '保存中…' : '保存修改'}
                </button>
              </div>
            </div>

          </form>
        </div>
      </div>
    </div>
  )
}
