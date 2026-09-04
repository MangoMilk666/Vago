import React, { useCallback, useEffect, useState } from 'react'
import Navbar from '../components/Navbar'
import { knowledgeApi } from '../api/travel'

const INDEX_STATUS = {
  NOT_INDEXED: '未索引', PENDING: '等待索引', INDEXING: '索引中', INDEXED: '已索引', FAILED: '索引失败',
}

function SourceModal({ source, onClose, onSaved }) {
  const [form, setForm] = useState({
    title: source?.title ?? '', destination: source?.destination ?? '',
    contentText: source?.contentText ?? '', tags: source?.tags?.join('，') ?? '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    if (!form.title.trim() || !form.contentText.trim()) {
      setError('请填写标题和知识内容')
      return
    }
    setSaving(true)
    setError('')
    const payload = {
      title: form.title.trim(), destination: form.destination.trim() || null,
      contentText: form.contentText.trim(),
      tags: form.tags.split(/[，,、\s]+/).map((tag) => tag.trim()).filter(Boolean),
    }
    try {
      // 分支条件：存在知识源时更新，否则创建新的纯文本资料。
      if (source) await knowledgeApi.update(source.uuid, payload)
      else await knowledgeApi.createText({ ...payload, sourceType: 'TEXT' })
      onSaved()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <form onSubmit={submit} className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <h2 className="font-semibold text-gray-900">{source ? '编辑知识资料' : '新建知识资料'}</h2>
        <button type="button" onClick={onClose} aria-label="关闭">×</button>
      </div>
      <div className="space-y-4 overflow-y-auto p-6">
        <input value={form.title} onChange={set('title')} maxLength={100} placeholder="资料标题" className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" />
        <input value={form.destination} onChange={set('destination')} maxLength={200} placeholder="目的地（可选）" className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" />
        <textarea value={form.contentText} onChange={set('contentText')} rows={12} placeholder="记录你的旅行经验、清单或注意事项" className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm" />
        <input value={form.tags} onChange={set('tags')} placeholder="标签，用逗号分隔" className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" />
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>
      <div className="flex gap-3 border-t border-gray-100 px-6 py-4">
        <button type="button" onClick={onClose} className="flex-1 rounded-lg border border-gray-200 py-2 text-sm">取消</button>
        <button disabled={saving} className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? '保存中…' : '保存资料'}</button>
      </div>
    </form>
  </div>
}

export default function GuidePage() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const [uploading, setUploading] = useState(false)

  const loadSources = useCallback(async () => {
    setLoading(true)
    try { const response = await knowledgeApi.list(); setSources(response.data ?? []); setError('') }
    catch (requestError) { setError(requestError.message) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { loadSources() }, [loadSources])

  const upload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    try { await knowledgeApi.uploadFile(file); await loadSources() }
    catch (requestError) { setError(requestError.message) }
    finally { setUploading(false); event.target.value = '' }
  }

  const requestIndex = async (source) => {
    try { await knowledgeApi.index(source.uuid); await loadSources() }
    catch (requestError) { setError(`索引「${source.title}」失败：${requestError.message}`) }
  }

  return <div className="app-page"><Navbar />
    <main className="app-main">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div><h1 className="text-xl font-bold text-gray-900">个人旅行知识库</h1><p className="mt-1 text-sm text-gray-500">沉淀自己的旅行资料，按需提供给 AI 作为上下文。</p></div>
        <div className="flex shrink-0 gap-2"><label className="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600">{uploading ? '导入中…' : '导入 .md/.txt'}<input type="file" accept=".md,.txt,text/plain,text/markdown" onChange={upload} disabled={uploading} className="hidden" /></label><button onClick={() => setModal('create')} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white">新建资料</button></div>
      </div>
      {error && <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>}
      {loading ? <div className="py-20 text-center text-sm text-gray-400">加载中…</div> : sources.length === 0 ? <div className="py-20 text-center text-sm text-gray-400">还没有个人旅行资料</div> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {sources.map((source) => <article key={source.uuid} className="app-surface flex min-h-44 flex-col p-4">
          <div className="flex items-start justify-between gap-3"><h2 className="font-semibold text-gray-900">{source.title}</h2><span className="shrink-0 text-xs text-gray-400">{source.sourceType === 'FILE' ? '文件' : '文本'}</span></div>
          {source.destination && <p className="mt-1 text-xs text-indigo-600">{source.destination}</p>}
          <p className="mt-3 line-clamp-3 flex-1 whitespace-pre-wrap text-sm text-gray-600">{source.contentText}</p>
          {/* 分支条件：后台索引失败时，直接展示服务端回写的原因，方便用户决定重试或关闭 RAG。 */}
          {source.indexStatus === 'FAILED' && source.indexError && <p className="mt-2 line-clamp-2 text-xs leading-5 text-red-500">索引失败：{source.indexError}</p>}
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-gray-100 pt-3"><span className="text-xs text-gray-400">{INDEX_STATUS[source.indexStatus] ?? '未知状态'}</span><div className="flex gap-2 text-xs"><button onClick={() => setModal(source)} className="text-indigo-600">编辑</button>{source.indexStatus !== 'INDEXED' && <button onClick={() => requestIndex(source)} className="text-indigo-600">索引</button>}<button onClick={async () => { if (window.confirm(`删除「${source.title}」吗？`)) { await knowledgeApi.delete(source.uuid); loadSources() } }} className="text-red-500">删除</button></div></div>
        </article>)}
      </div>}
    </main>
    {modal && <SourceModal source={modal === 'create' ? null : modal} onClose={() => setModal(null)} onSaved={() => { setModal(null); loadSources() }} />}
  </div>
}
