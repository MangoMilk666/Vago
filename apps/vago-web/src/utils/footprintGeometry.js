const MAX_ACCURACY_METERS = 100
const MAX_CONTINUOUS_DISTANCE_METERS = 5000
const MAX_SPARSE_GAP_MS = 20 * 60 * 1000
const MAX_SPARSE_GAP_DISTANCE_METERS = 1000
const MAX_HARD_GAP_MS = 2 * 60 * 60 * 1000
const MAX_SPEED_METERS_PER_SECOND = 55
const MIN_RENDER_DISTANCE_METERS = 15

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)

export function isRenderableCoordinate(point) {
  return isFiniteNumber(point.latitude)
    && isFiniteNumber(point.longitude)
    && point.latitude >= -90 && point.latitude <= 90
    && point.longitude >= -180 && point.longitude <= 180
}

function distanceMeters(left, right) {
  const radians = (degrees) => degrees * Math.PI / 180
  const latitudeDelta = radians(right.latitude - left.latitude)
  const longitudeDelta = radians(right.longitude - left.longitude)
  const meanLatitude = radians((left.latitude + right.latitude) / 2)
  const x = longitudeDelta * Math.cos(meanLatitude)
  const y = latitudeDelta
  return Math.hypot(x, y) * 6371000
}

function timeMillis(point) {
  return new Date(point.occurredAt).getTime()
}

function isUsableAutomaticFix(point) {
  if (point.observationType !== 'AUTO_GPS') return true
  if (point.accuracyM == null) return true
  return isFiniteNumber(point.accuracyM) && point.accuracyM >= 0 && point.accuracyM <= MAX_ACCURACY_METERS
}

function hasValidMotion(point) {
  return point.speedMps == null || (isFiniteNumber(point.speedMps) && point.speedMps >= 0)
}

function hasExplicitBoundary(previous, next) {
  return previous.trackingSegmentUuid !== next.trackingSegmentUuid
    && (previous.trackingSegmentUuid != null || next.trackingSegmentUuid != null)
}

function isUntrustedConnection(previous, next) {
  const elapsed = timeMillis(next) - timeMillis(previous)
  const distance = distanceMeters(previous, next)
  if (!Number.isFinite(elapsed) || elapsed <= 0) return true
  if (distance > MAX_CONTINUOUS_DISTANCE_METERS || elapsed > MAX_HARD_GAP_MS) return true
  if (elapsed > MAX_SPARSE_GAP_MS && distance > MAX_SPARSE_GAP_DISTANCE_METERS) return true

  const impliedSpeed = distance / (elapsed / 1000)
  return impliedSpeed > MAX_SPEED_METERS_PER_SECOND
    || (previous.speedMps != null && previous.speedMps > MAX_SPEED_METERS_PER_SECOND)
    || (next.speedMps != null && next.speedMps > MAX_SPEED_METERS_PER_SECOND)
}

function compareObservations(left, right) {
  const timeDifference = timeMillis(left) - timeMillis(right)
  if (timeDifference !== 0) return timeDifference
  return String(left.clientEventUuid || left.uuid).localeCompare(String(right.clientEventUuid || right.uuid))
}

function routeSegmentsFromSorted(sorted) {
  const segments = []
  let current = []
  const flush = () => {
    if (current.length) segments.push(current)
    current = []
  }

  sorted.forEach((point) => {
    // 无效坐标、差定位或损坏的速度字段作为隔断，防止把隔断两侧的有效点误连起来。
    if (!isRenderableCoordinate(point) || !isUsableAutomaticFix(point) || !hasValidMotion(point)) {
      flush()
      return
    }

    const previous = current[current.length - 1]
    if (!previous) {
      current.push(point)
      return
    }

    if (hasExplicitBoundary(previous, point) || isUntrustedConnection(previous, point)) {
      flush()
      current.push(point)
      return
    }

    if (point.observationType === 'MANUAL_CHECKIN') {
      current.push(point)
      return
    }

    if (distanceMeters(previous, point) < MIN_RENDER_DISTANCE_METERS) {
      // 近距离自动 GPS 属于显示层降噪；手动打卡仍始终作为独立路线顶点保留。
      if (previous.observationType === 'AUTO_GPS') current[current.length - 1] = point
      return
    }

    current.push(point)
  })

  flush()
  return segments
}

export function buildFootprintSegments(observations) {
  return routeSegmentsFromSorted([...observations].sort(compareObservations))
}

/** 自动取景只围住可信路线点与独立有效打卡，不让弱信号漂移拉远地图。 */
export function selectFootprintViewportPoints(segments, checkins = []) {
  const pointsByKey = new Map()
  for (const point of [...segments.flat(), ...checkins]) {
    if (!isRenderableCoordinate(point)) continue
    const key = String(point.clientEventUuid || point.uuid)
    pointsByKey.set(key, point)
  }
  return [...pointsByKey.values()]
}

function turnAngleDegrees(previous, point, next, project) {
  const a = project(previous)
  const b = project(point)
  const c = project(next)
  if (!a || !b || !c) return 0
  const incoming = { x: b.x - a.x, y: b.y - a.y }
  const outgoing = { x: c.x - b.x, y: c.y - b.y }
  const incomingLength = Math.hypot(incoming.x, incoming.y)
  const outgoingLength = Math.hypot(outgoing.x, outgoing.y)
  if (!incomingLength || !outgoingLength) return 0
  const cosine = Math.max(-1, Math.min(1, (incoming.x * outgoing.x + incoming.y * outgoing.y) / (incomingLength * outgoingLength)))
  return Math.acos(cosine) * 180 / Math.PI
}

/** 根据地图投影后的屏幕距离选择 GPS 圆点；路线和手动打卡标记不受影响。 */
export function selectVisibleAutomaticPoints(segments, project, minimumSpacing = 22, turnThreshold = 35) {
  const visible = new Set()
  segments.forEach((segment) => {
    const automaticIndexes = []
    segment.forEach((point, index) => {
      if (point.observationType === 'AUTO_GPS') automaticIndexes.push(index)
    })
    let lastSelected = null

    automaticIndexes.forEach((index, automaticIndex) => {
      const point = segment[index]
      const projected = project(point)
      if (!projected) return
      const isEndpoint = automaticIndex === 0 || automaticIndex === automaticIndexes.length - 1
      const hasNeighbors = index > 0 && index < segment.length - 1
      const isTurn = hasNeighbors
        && turnAngleDegrees(segment[index - 1], point, segment[index + 1], project) >= turnThreshold
      const spaced = !lastSelected || Math.hypot(projected.x - lastSelected.x, projected.y - lastSelected.y) >= minimumSpacing

      if (isEndpoint || isTurn || spaced) {
        visible.add(point.uuid)
        lastSelected = projected
      }
    })
  })
  return visible
}
