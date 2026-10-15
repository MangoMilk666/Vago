import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import Navbar from '../components/Navbar'
import { footprintApi } from '../api/footprints'
import { tripApi } from '../api/travel'
import { buildFootprintSegments, isRenderableCoordinate, selectFootprintViewportPoints, selectVisibleAutomaticPoints } from '../utils/footprintGeometry'

const STATUS = {
  1: { label: '未开始', className: 'bg-violet-100 text-violet-700' },
  2: { label: '进行中', className: 'bg-emerald-100 text-emerald-700' },
  3: { label: '已结束', className: 'bg-slate-200 text-slate-600' },
}
const DEFAULT_CENTER = [20, 0]

function formatDate(value) {
  if (!value) return '未设置日期'
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function formatTime(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function MapViewport({ points }) {
  const map = useMap()

  useEffect(() => {
    // 如果当前 Trip 没有足迹点位，保留世界视角，避免地图跳到无意义的零坐标。
    if (!points.length) {
      map.setView(DEFAULT_CENTER, 2)
      return
    }
    const bounds = points.map((point) => [point.latitude, point.longitude])
    map.fitBounds(bounds, { padding: [56, 56], maxZoom: 15 })
  }, [map, points])

  return null
}

function TripList({ trips, selectedUuid, onSelect }) {
  if (!trips.length) {
    return <div className="px-4 py-10 text-center text-sm leading-6 text-slate-500">还没有行程。创建行程并记录足迹后，会在这里显示。</div>
  }

  return (
    <div className="space-y-2 px-3 pb-4">
      {trips.map((trip) => {
        const status = STATUS[trip.status] ?? STATUS[1]
        const selected = trip.uuid === selectedUuid
        return (
          <button
            key={trip.uuid}
            type="button"
            onClick={() => onSelect(trip.uuid)}
            className={`w-full border px-3 py-3 text-left transition-colors ${selected
              ? 'border-violet-300 bg-violet-50 shadow-sm'
              : 'border-transparent bg-white hover:border-violet-100 hover:bg-violet-50/50'}`}
            style={{ borderRadius: 8 }}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="min-w-0 truncate text-sm font-semibold text-slate-800">{trip.title}</p>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${status.className}`}>{status.label}</span>
            </div>
            <p className="mt-1 truncate text-xs text-slate-500">{trip.destination || '未设置目的地'}</p>
            <p className="mt-1 text-[11px] text-slate-400">{formatDate(trip.startDate)} - {formatDate(trip.endDate)}</p>
          </button>
        )
      })}
    </div>
  )
}

function FootprintLayers({ segments, checkins, showGpsPoints }) {
  const map = useMap()
  const [viewportRevision, setViewportRevision] = useState(0)

  useMapEvents({
    zoomend: () => setViewportRevision((value) => value + 1),
    moveend: () => setViewportRevision((value) => value + 1),
    resize: () => setViewportRevision((value) => value + 1),
  })

  const visiblePointUuids = useMemo(() => {
    if (!showGpsPoints) return new Set()
    return selectVisibleAutomaticPoints(
      segments,
      (point) => {
        const projected = map.latLngToLayerPoint([point.latitude, point.longitude])
        return { x: projected.x, y: projected.y }
      },
    )
  }, [map, segments, showGpsPoints, viewportRevision])

  return (
    <>
      {segments.filter((segment) => segment.length > 1).map((segment, index) => {
        const positions = segment.map((item) => [item.latitude, item.longitude])
        const key = `${segment[0].trackingSegmentUuid || segment[0].uuid}-${index}`
        return (
          <React.Fragment key={key}>
            <Polyline
              positions={positions}
              pathOptions={{ color: '#5856d6', weight: 9, opacity: 0.2, lineCap: 'round', lineJoin: 'round', interactive: false }}
              smoothFactor={1}
            />
            <Polyline
              positions={positions}
              pathOptions={{ color: '#5856d6', weight: 4, opacity: 0.92, lineCap: 'round', lineJoin: 'round', interactive: false }}
              smoothFactor={1}
            />
          </React.Fragment>
        )
      })}

      {showGpsPoints && segments.flat().filter((point) => visiblePointUuids.has(point.uuid)).map((point) => (
        <CircleMarker
          key={point.uuid}
          center={[point.latitude, point.longitude]}
          radius={3.5}
          pathOptions={{ color: '#ffffff', fillColor: '#5856d6', fillOpacity: 1, weight: 1.25 }}
        >
          <Popup><FootprintPopup point={point} /></Popup>
        </CircleMarker>
      ))}

      {checkins.map((point) => (
        <CircleMarker
          key={point.uuid}
          center={[point.latitude, point.longitude]}
          radius={6.5}
          pathOptions={{ color: '#ffffff', fillColor: '#e75b7b', fillOpacity: 1, weight: 2.5 }}
        >
          <Popup><FootprintPopup point={point} /></Popup>
        </CircleMarker>
      ))}
    </>
  )
}

function FootprintMap({ footprints, showGpsPoints }) {
  const checkins = useMemo(
    () => footprints.filter((item) => item.footprintType === 'MANUAL_CHECKIN' && isRenderableCoordinate(item)),
    [footprints],
  )
  const segments = useMemo(() => buildFootprintSegments(footprints), [footprints])
  const viewportPoints = useMemo(() => selectFootprintViewportPoints(segments, checkins), [segments, checkins])

  return (
    <MapContainer center={DEFAULT_CENTER} zoom={2} className="h-full w-full" zoomControl={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapViewport points={viewportPoints} />

      <FootprintLayers segments={segments} checkins={checkins} showGpsPoints={showGpsPoints} />
    </MapContainer>
  )
}

function FootprintPopup({ point }) {
  const checkin = point.footprintType === 'MANUAL_CHECKIN'
  return (
    <div className="min-w-40 font-sans text-sm text-slate-700">
      <p className="font-semibold">{checkin ? point.locationName || '未命名打卡' : 'GPS 采样点'}</p>
      <p className="mt-1 text-xs text-slate-500">{formatDate(point.occurredAt)} {formatTime(point.occurredAt)}</p>
      {checkin && point.note && <p className="mt-2 text-xs leading-5 text-slate-600">{point.note}</p>}
      {!checkin && point.accuracyM != null && <p className="mt-1 text-xs text-slate-500">定位精度约 {Math.round(point.accuracyM)} m</p>}
    </div>
  )
}

export default function FootprintPage() {
  const [trips, setTrips] = useState([])
  const [selectedTripUuid, setSelectedTripUuid] = useState(null)
  const [footprints, setFootprints] = useState([])
  const [loadingTrips, setLoadingTrips] = useState(true)
  const [loadingMap, setLoadingMap] = useState(false)
  const [error, setError] = useState('')
  const [showGpsPoints, setShowGpsPoints] = useState(true)

  useEffect(() => {
    let active = true
    const loadTrips = async () => {
      setLoadingTrips(true)
      setError('')
      try {
        const response = await tripApi.list()
        if (!active) return
        const nextTrips = response.data ?? []
        setTrips(nextTrips)
        // 如果存在进行中行程，优先作为地图的初始上下文；否则读取最新一条行程。
        setSelectedTripUuid((current) => current || nextTrips.find((trip) => trip.status === 2)?.uuid || nextTrips[0]?.uuid || null)
      } catch (requestError) {
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoadingTrips(false)
      }
    }
    loadTrips()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!selectedTripUuid) {
      setFootprints([])
      return undefined
    }
    let active = true
    const loadFootprints = async () => {
      setLoadingMap(true)
      setError('')
      try {
        const response = await footprintApi.listTripFootprints(selectedTripUuid)
        if (active) setFootprints(response.data ?? [])
      } catch (requestError) {
        if (active) setFootprints([])
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoadingMap(false)
      }
    }
    loadFootprints()
    return () => { active = false }
  }, [selectedTripUuid])

  const selectedTrip = trips.find((trip) => trip.uuid === selectedTripUuid)
  const automaticCount = footprints.filter((item) => item.footprintType === 'AUTO_GPS').length
  const checkinCount = footprints.filter((item) => item.footprintType === 'MANUAL_CHECKIN').length

  return (
    <div className="app-page min-h-screen">
      <Navbar />
      <main className="h-[calc(100vh-4rem)] min-h-[640px] w-full p-3 sm:p-5">
        <section className="grid h-full overflow-hidden border border-violet-100 bg-white shadow-sm lg:grid-cols-[300px_minmax(0,1fr)]" style={{ borderRadius: 8 }}>
          <aside className="flex min-h-0 flex-col border-b border-violet-100 bg-slate-50/70 lg:border-b-0 lg:border-r">
            <div className="border-b border-violet-100 px-5 py-5">
              <p className="text-[11px] font-semibold tracking-[0.12em] text-violet-600">TRAVEL FOOTPRINT</p>
              <h1 className="mt-1 text-lg font-semibold text-slate-900">旅行足迹</h1>
              <p className="mt-1 text-xs leading-5 text-slate-500">按行程查看真实轨迹与主动打卡。</p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto pt-3">
              {loadingTrips ? <p className="px-5 py-5 text-sm text-slate-500">正在读取行程...</p> : <TripList trips={trips} selectedUuid={selectedTripUuid} onSelect={setSelectedTripUuid} />}
            </div>
          </aside>

          <section className="relative min-h-[460px] overflow-hidden bg-slate-100">
            <FootprintMap footprints={footprints} showGpsPoints={showGpsPoints} />
            <div className="absolute left-4 top-4 z-[500] max-w-[calc(100%-2rem)] border border-white/80 bg-white/95 px-4 py-3 shadow-lg backdrop-blur" style={{ borderRadius: 8 }}>
              <div className="flex items-start gap-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{selectedTrip?.title || '选择一个行程'}</p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">{selectedTrip?.destination || '当前用户的旅行空间记录'}</p>
                </div>
                {selectedTrip && <Link to={`/trips/${selectedTrip.uuid}/itinerary?type=trip&title=${encodeURIComponent(selectedTrip.title)}`} className="shrink-0 text-xs font-medium text-violet-700 hover:text-violet-900">查看日程</Link>}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
                <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-violet-500" />轨迹 {automaticCount}</span>
                <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-500" />打卡 {checkinCount}</span>
                <label className="inline-flex cursor-pointer items-center gap-1.5 text-slate-600">
                  <input type="checkbox" checked={showGpsPoints} onChange={(event) => setShowGpsPoints(event.target.checked)} className="h-3.5 w-3.5 accent-violet-600" />
                  显示 GPS 点
                </label>
              </div>
            </div>

            {loadingMap && <div className="absolute inset-0 z-[600] flex items-center justify-center bg-white/50 backdrop-blur-[1px]"><div className="rounded-md bg-white px-3 py-2 text-sm text-slate-600 shadow-sm">正在绘制足迹...</div></div>}
            {!loadingMap && selectedTrip && !footprints.length && !error && <div className="absolute inset-0 z-[500] flex items-center justify-center px-6 text-center"><div className="bg-white/90 px-5 py-4 text-sm leading-6 text-slate-500 shadow-sm" style={{ borderRadius: 8 }}>这个行程还没有已同步的足迹或打卡记录。</div></div>}
            {error && <div className="absolute bottom-4 left-4 right-4 z-[600] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-sm" style={{ borderRadius: 8 }}>{error}</div>}
          </section>
        </section>
      </main>
    </div>
  )
}
