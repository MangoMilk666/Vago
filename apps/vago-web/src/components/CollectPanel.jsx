import React, { useEffect, useState, useRef } from 'react'
import { collectionApi } from '../api/travel'

/**
 * 收藏面板 — 点击攻略下方的收藏按钮时弹出
 *
 * Props:
 *   guideUuid  — 当前攻略的 UUID
 *   guideTitle — 攻略标题（显示用）
 *   onClose    — 关闭回调
 *   onCollectChange — 收藏状态变化回调 (guideUuid, isCollected) => void
 */
export default function CollectPanel({ guideUuid, guideTitle, onClose, onCollectChange }) {
  const [collections, setCollections]   = useState([])   // 全部收藏夹
  const [checked,     setChecked]       = useState(new Set()) // 已收藏的收藏夹 uuid
  const [loading,     setLoading]       = useState(true)
  const [toggling,    setToggling]      = useState(null)  // 正在切换的 uuid
  const [error,       setError]         = useState('')
  const [showNewForm, setShowNewForm]   = useState(false)
  const [editing,     setEditing]       = useState(null)  // 正在编辑的收藏夹 uuid
  const [newName,     setNewName]       = useState('')
  const [newDesc,     setNewDesc]       = useState('')
  const [saving,      setSaving]        = useState(false)
  const [toast,       setToast]         = useState(null)  // { message, type } | null

  // ── 加载数据 ──
  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [listRes, checkRes] = await Promise.all([
        collectionApi.list(),
        collectionApi.check(guideUuid),
      ])
      setCollections(listRes.data ?? [])
      setChecked(new Set((checkRes.data ?? []).map((c) => c.uuid)))
    } catch (err) {
      setError(err.message || '加载收藏夹失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [guideUuid])

  // ── ESC 关闭 ──
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // ── 切换收藏状态 ──
  const toggle = async (collectionUuid) => {
    if (toggling) return
    const name = collections.find((c) => c.uuid === collectionUuid)?.name || ''
    const wasChecked = checked.has(collectionUuid)
    setToggling(collectionUuid)
    try {
      if (wasChecked) {
        await collectionApi.removeItem(collectionUuid, guideUuid)
        setChecked((prev) => { const next = new Set(prev); next.delete(collectionUuid); return next })
        setToast({ message: `已从「${name}」中移除`, type: 'remove' })
        onCollectChange?.(guideUuid, checked.size > 1)
      } else {
        await collectionApi.saveInto({ collectionUuid, guideUuid })
        setChecked((prev) => { const next = new Set(prev); next.add(collectionUuid); return next })
        setToast({ message: `已收藏到「${name}」`, type: 'add' })
        onCollectChange?.(guideUuid, true)
      }
    } catch (err) {
      console.error('操作失败', err)
    } finally {
      setToggling(null)
      setTimeout(() => setToast(null), 2000)
    }
  }

  // ── 新建收藏夹 ──
  const handleCreate = async () => {
    if (!newName.trim()) return
    setSaving(true)
    try {
      const res = await collectionApi.create({ name: newName.trim(), description: newDesc.trim() })
      const created = res.data
      setCollections((prev) => [...prev, created])
      // 自动收藏到新创建的收藏夹
      await collectionApi.saveInto({ collectionUuid: created.uuid, guideUuid })
      setChecked((prev) => { const next = new Set(prev); next.add(created.uuid); return next })
      setToast({ message: `已收藏到「${created.name}」`, type: 'add' })
      onCollectChange?.(guideUuid, true)
      setShowNewForm(false)
      setNewName('')
      setNewDesc('')
    } catch (err) {
      alert(err.message || '创建失败')
    } finally {
      setSaving(false)
    }
  }

  // ── 编辑收藏夹 ──
  const handleUpdate = async (uuid, name, description) => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await collectionApi.update({ uuid, name, description })
      setCollections((prev) => prev.map((c) => c.uuid === uuid ? { ...c, name, description } : c))
      setEditing(null)
    } catch (err) {
      alert(err.message || '更新失败')
    } finally {
      setSaving(false)
    }
  }

  // 点击遮罩关闭
  const handleOverlay = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onClick={handleOverlay}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[80vh] flex flex-col">
        {/* ── 头部 ── */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-gray-900">收藏到收藏夹</h2>
            <p className="text-xs text-gray-400 truncate mt-0.5">{guideTitle}</p>
          </div>
          <button onClick={onClose}
            className="ml-3 text-gray-400 hover:text-gray-600 transition-colors shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* ── 列表 ── */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin w-6 h-6 border-3 border-indigo-500 border-t-transparent rounded-full"/>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-sm text-red-500 mb-3">{error}</p>
              <button onClick={load}
                className="text-sm text-indigo-600 hover:text-indigo-700 font-medium">重试</button>
            </div>
          ) : collections.length === 0 && !showNewForm ? (
            <div className="text-center py-12 text-gray-400 text-sm">
              还没有收藏夹，创建一个吧
            </div>
          ) : (
            <div className="space-y-0.5">
              {collections.map((c) =>
                editing === c.uuid ? (
                  <EditForm
                    key={c.uuid}
                    name={c.name}
                    description={c.description || ''}
                    saving={saving}
                    onSave={(name, desc) => handleUpdate(c.uuid, name, desc)}
                    onCancel={() => setEditing(null)}
                  />
                ) : (
                  <div
                    key={c.uuid}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer
                                transition-colors group
                                ${toggling === c.uuid ? 'opacity-50 pointer-events-none' : 'hover:bg-gray-50'}`}
                    onClick={() => toggle(c.uuid)}
                  >
                    {/* 勾选图标 */}
                    <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0
                                    transition-colors
                      ${checked.has(c.uuid)
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'border-gray-300'}`}>
                      {checked.has(c.uuid) && (
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7"/>
                        </svg>
                      )}
                    </div>

                    {/* 文件夹图标 */}
                    <svg className={`w-5 h-5 shrink-0 ${checked.has(c.uuid) ? 'text-indigo-500' : 'text-gray-400'}`}
                      fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
                    </svg>

                    {/* 名称 */}
                    <span className="text-sm text-gray-700 flex-1 truncate">{c.name}</span>

                    {/* 编辑按钮 */}
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditing(c.uuid) }}
                      className="p-1 rounded-lg opacity-0 group-hover:opacity-100
                                 hover:bg-gray-200 text-gray-400 hover:text-gray-600 transition-all"
                      title="编辑收藏夹"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                      </svg>
                    </button>
                  </div>
                )
              )}
            </div>
          )}

          {/* 新建收藏夹表单 */}
          {showNewForm && (
            <div className="mx-3 mt-2 p-3 rounded-xl bg-gray-50 border border-gray-100 space-y-2">
              <input
                value={newName} onChange={(e) => setNewName(e.target.value)}
                placeholder="收藏夹名称" maxLength={100} autoFocus
                className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <textarea
                value={newDesc} onChange={(e) => setNewDesc(e.target.value)}
                placeholder="描述（选填）" rows={2} maxLength={255}
                className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm resize-none
                           focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
              <div className="flex gap-2">
                <button onClick={() => { setShowNewForm(false); setNewName(''); setNewDesc('') }}
                  className="flex-1 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-500
                             hover:bg-white transition-colors">取消</button>
                <button onClick={handleCreate} disabled={saving || !newName.trim()}
                  className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium
                             hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                  {saving ? '创建中…' : '创建并收藏'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Toast 提示 ── */}
        {toast && (
          <div className={`absolute bottom-16 left-4 right-4 px-4 py-2.5 rounded-xl text-sm
                          font-medium text-center shadow-lg transition-all
            ${toast.type === 'add'
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-700 text-white'}`}>
            {toast.message}
          </div>
        )}

        {/* ── 底部 ── */}
        <div className="px-4 py-3 border-t border-gray-100 shrink-0">
          {!showNewForm && (
            <button onClick={() => setShowNewForm(true)}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl
                         border border-dashed border-gray-300 text-sm text-gray-500
                         hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50
                         transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
              </svg>
              新建收藏夹
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── 编辑收藏夹表单 ──────────────────────────────────────────────────────────────
function EditForm({ name: initialName, description: initialDesc, saving, onSave, onCancel }) {
  const [name, setName] = useState(initialName)
  const [desc, setDesc] = useState(initialDesc)
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim()) return
    onSave(name.trim(), desc.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="mx-1 my-1 p-3 rounded-xl bg-gray-50 border border-gray-100 space-y-2">
      <input ref={inputRef}
        value={name} onChange={(e) => setName(e.target.value)}
        placeholder="收藏夹名称" maxLength={100}
        className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm
                   focus:outline-none focus:ring-2 focus:ring-indigo-400"
      />
      <textarea
        value={desc} onChange={(e) => setDesc(e.target.value)}
        placeholder="描述（选填）" rows={2} maxLength={255}
        className="w-full rounded-lg border border-gray-200 px-3 py-1.5 text-sm resize-none
                   focus:outline-none focus:ring-2 focus:ring-indigo-400"
      />
      <div className="flex gap-2">
        <button type="button" onClick={onCancel}
          className="flex-1 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-500
                     hover:bg-white transition-colors">取消</button>
        <button type="submit" disabled={saving || !name.trim()}
          className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium
                     hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {saving ? '保存中…' : '保存'}
        </button>
      </div>
    </form>
  )
}
