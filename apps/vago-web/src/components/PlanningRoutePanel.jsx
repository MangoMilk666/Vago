import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { aiApi } from '../api/ai'

const MODES = [
  { value: 'walking', label: '步行' },
  { value: 'driving', label: '驾车' },
  { value: 'transit', label: '公交' },
]

function PlaceField({ title, city, value, onChange, selected, onSelect }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const search = async (event) => {
    event.preventDefault()
    setError('')
    setResults([])
    if (!city.trim() || !value.trim()) {
      setError('请先填写城市和地点名称')
      return
    }
    setLoading(true)
    try {
      const response = await aiApi.searchPlanningPlaces(city.trim(), value.trim())
      setResults(response.data ?? [])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
      <label className="block text-xs font-semibold text-slate-700" htmlFor={`planning-${title}`}>{title}</label>
      <form onSubmit={search} className="flex gap-2">
        <input id={`planning-${title}`} value={value} onChange={(event) => {
          onChange(event.target.value)
          setResults([])
        }} placeholder="搜索地点名称" className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-violet-500" />
        <button type="submit" disabled={loading} className="rounded-lg border border-violet-200 px-3 text-xs font-medium text-violet-700 hover:bg-violet-50 disabled:opacity-50">
          {loading ? '搜索中' : '搜索'}
        </button>
      </form>
      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
      {results.length > 0 && (
        <div className="max-h-36 space-y-1 overflow-y-auto" aria-label={`${title}搜索结果`}>
          {results.map((place) => (
            <button key={place.id} type="button" onClick={() => {
              onSelect(place)
              setResults([])
            }} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-violet-50">
              <span className="block truncate text-xs font-medium text-slate-800">{place.name}</span>
              <span className="block truncate text-[11px] text-slate-400">{place.address || '高德地点'}</span>
            </button>
          ))}
        </div>
      )}
      {!loading && !error && value.trim() && results.length === 0 && !selected && (
        <p className="text-[11px] text-slate-400">输入地点后点击搜索，从结果中选择。</p>
      )}
      {selected && <p className="rounded-lg bg-violet-50 px-2 py-1.5 text-xs text-violet-700">已选：{selected.name}</p>}
    </section>
  )
}

export default function PlanningRoutePanel({ onClose, previewTarget }) {
  const [city, setCity] = useState('')
  const [originQuery, setOriginQuery] = useState('')
  const [destinationQuery, setDestinationQuery] = useState('')
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  const [mode, setMode] = useState('walking')
  const [routes, setRoutes] = useState([])
  const [selectedRoute, setSelectedRoute] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [showPreview, setShowPreview] = useState(false)
  const previewUrlRef = useRef('')
  const previewRequestRef = useRef(0)

  useEffect(() => () => {
    previewRequestRef.current += 1
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
  }, [])

  const clearPreview = () => {
    previewRequestRef.current += 1
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    previewUrlRef.current = ''
    setPreviewUrl('')
    setPreviewError('')
    setPreviewLoading(false)
    setShowPreview(false)
  }

  const clearRoute = () => {
    clearPreview()
    setRoutes([])
    setSelectedRoute(null)
    setError('')
  }

  const searchRoutes = async () => {
    if (!origin || !destination) return
    setLoading(true)
    clearRoute()
    try {
      const response = await aiApi.searchPlanningRoutes(city.trim(), mode, origin, destination)
      setRoutes(response.data ?? [])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const selectRoute = async (route) => {
    clearPreview()
    setSelectedRoute(route)
    setShowPreview(true)
    if (!route.previewAvailable) {
      setPreviewError('这条路线暂时没有完整的地图预览')
      return
    }
    const requestId = previewRequestRef.current
    setPreviewLoading(true)
    try {
      const image = await aiApi.planningRoutePreview(route.routeChoiceId)
      // 如果用户已切换路线或关闭面板，丢弃先前返回的图片。
      if (requestId !== previewRequestRef.current) return
      const url = URL.createObjectURL(image)
      previewUrlRef.current = url
      setPreviewUrl(url)
    } catch (requestError) {
      if (requestId === previewRequestRef.current) setPreviewError(requestError.message)
    } finally {
      if (requestId === previewRequestRef.current) setPreviewLoading(false)
    }
  }

  return (
    <>
    <aside aria-label="地点与路线规划" className="absolute inset-y-0 right-0 z-20 flex w-full flex-col border-l border-slate-200 bg-slate-50 shadow-xl sm:max-w-[440px] lg:static lg:h-full lg:w-[420px] lg:shrink-0 lg:shadow-none">
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-white px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">地点与路线</h3>
          <p className="mt-1 text-xs text-slate-500">查询中国大陆地点，比较不同出行方式</p>
        </div>
        <button type="button" onClick={onClose} aria-label="关闭地点与路线面板" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeWidth="2" strokeLinecap="round" d="M6 6l12 12M18 6 6 18" /></svg>
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div>
          <label htmlFor="planning-city" className="mb-1.5 block text-xs font-semibold text-slate-700">城市</label>
          <input id="planning-city" value={city} onChange={(event) => {
            setCity(event.target.value)
            setOrigin(null)
            setDestination(null)
            clearRoute()
          }} placeholder="例如：上海" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-violet-500" />
        </div>
        <PlaceField key={`origin-${city}`} title="起点" city={city} value={originQuery} onChange={(value) => {
          setOriginQuery(value)
          setOrigin(null)
          clearRoute()
        }} selected={origin} onSelect={(place) => {
          setOrigin(place)
          setOriginQuery(place.name)
          clearRoute()
        }} />
        <PlaceField key={`destination-${city}`} title="终点" city={city} value={destinationQuery} onChange={(value) => {
          setDestinationQuery(value)
          setDestination(null)
          clearRoute()
        }} selected={destination} onSelect={(place) => {
          setDestination(place)
          setDestinationQuery(place.name)
          clearRoute()
        }} />
        <div>
          <p className="mb-2 text-xs font-semibold text-slate-700">出行方式</p>
          <div className="grid grid-cols-3 gap-2">
            {MODES.map((option) => (
              <button key={option.value} type="button" onClick={() => {
                setMode(option.value)
                clearRoute()
              }} className={`rounded-lg border px-2 py-2 text-xs font-medium transition ${mode === option.value ? 'border-violet-500 bg-violet-50 text-violet-700' : 'border-slate-200 bg-white text-slate-600 hover:border-violet-200'}`} aria-pressed={mode === option.value}>
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <button type="button" onClick={searchRoutes} disabled={!origin || !destination || loading} className="w-full rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-40">
          {loading ? '正在查询路线…' : '查看路线候选'}
        </button>
        {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-600">{error}</p>}
        {routes.length > 0 && (
          <section className="space-y-2" aria-label="路线候选">
            <h4 className="text-xs font-semibold text-slate-700">路线候选 · {routes.length} 条</h4>
            {routes.map((route, index) => (
              <button key={route.routeChoiceId} type="button" onClick={() => selectRoute(route)} className={`w-full rounded-xl border bg-white p-3 text-left transition ${selectedRoute?.routeChoiceId === route.routeChoiceId ? 'border-violet-500 ring-1 ring-violet-200' : 'border-slate-200 hover:border-violet-300'}`} aria-pressed={selectedRoute?.routeChoiceId === route.routeChoiceId}>
                <span className="flex items-center justify-between gap-2 text-xs font-medium text-slate-800"><span>{route.summary || `路线 ${index + 1}`}</span><span>{route.routeDurationMinutes} 分钟</span></span>
                <span className="mt-1 block text-[11px] text-slate-400">高德地图 · {route.distanceMeters ? `${Math.round(Number(route.distanceMeters))} 米 · ` : ''}查询结果十分钟内有效</span>
              </button>
            ))}
          </section>
        )}
      </div>
    </aside>
    {previewTarget && selectedRoute && showPreview && createPortal(
      // 预览挂在中央聊天区，关闭右侧面板时随面板一起卸载。
      <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-900/25 p-4 sm:p-6" aria-label="所选路线地图预览">
        <section className="flex max-h-full w-full max-w-[900px] flex-col overflow-hidden rounded-2xl border border-violet-100 bg-white shadow-2xl" role="dialog" aria-label="路线地图预览">
          <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-4 py-3 sm:px-5">
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-slate-900">路线地图预览</h4>
              <p className="mt-0.5 truncate text-xs text-slate-500">{origin?.name} → {destination?.name} · {selectedRoute.routeDurationMinutes} 分钟</p>
            </div>
            <button type="button" onClick={() => setShowPreview(false)} aria-label="收起路线地图预览" className="shrink-0 rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path strokeWidth="2" strokeLinecap="round" d="M6 6l12 12M18 6 6 18" /></svg>
            </button>
          </div>
          <div className="min-h-0 overflow-y-auto bg-slate-50">
            {previewLoading && <p className="p-5 text-sm text-slate-500">正在加载地图…</p>}
            {previewError && <p role="alert" className="p-5 text-sm text-red-600">{previewError}</p>}
            {previewUrl && <img src={previewUrl} alt={`${origin?.name}至${destination?.name}的高德路线预览`} className="block w-full" />}
          </div>
          <p className="px-4 py-2.5 text-xs text-slate-500 sm:px-5">高德地图 · 此路线仅供比较，尚未写入候选计划。</p>
        </section>
      </div>,
      previewTarget,
    )}
    </>
  )
}
