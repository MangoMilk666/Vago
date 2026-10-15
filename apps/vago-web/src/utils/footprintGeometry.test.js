import assert from 'node:assert/strict'
import test from 'node:test'
import { buildFootprintSegments, selectFootprintViewportPoints, selectVisibleAutomaticPoints } from './footprintGeometry.js'

function footprint(uuid, latitude, occurredAt, fields = {}) {
  return {
    uuid,
    clientEventUuid: uuid,
    tripUuid: 'trip-1',
    footprintType: 'AUTO_GPS',
    latitude,
    longitude: 0,
    accuracyM: 8,
    speedMps: 1.2,
    trackingSegmentUuid: null,
    occurredAt: new Date(occurredAt).toISOString(),
    ...fields,
  }
}

const at = (minute) => Date.UTC(2026, 9, 5, 8, minute)
const latitudeForMeters = (meters) => meters / 111320

test('步行路线按时间连接，连续段中的手动打卡保留为路线顶点', () => {
  const gpsA = footprint('a', latitudeForMeters(0), at(0), { trackingSegmentUuid: 'segment-a' })
  const checkin = footprint('checkin', latitudeForMeters(25), at(1), {
    footprintType: 'MANUAL_CHECKIN',
    accuracyM: null,
    speedMps: null,
    trackingSegmentUuid: 'segment-a',
  })
  const gpsB = footprint('b', latitudeForMeters(50), at(2), { trackingSegmentUuid: 'segment-a' })
  const segments = buildFootprintSegments([gpsB, checkin, gpsA])
  assert.equal(segments.length, 1)
  assert.deepEqual(segments[0].map((point) => point.uuid), ['a', 'checkin', 'b'])
})

test('显式重启段、长缺口、城市跳跃和高漂移定位都不会被直线跨接', () => {
  const start = footprint('start', 0, at(0), { trackingSegmentUuid: 'a' })
  const restarted = footprint('restart', latitudeForMeters(30), at(1), { trackingSegmentUuid: 'b' })
  const longGap = footprint('long-gap', latitudeForMeters(40), at(8 * 60), { trackingSegmentUuid: 'b' })
  const cityJump = footprint('city', 1, at(8 * 60 + 1), { trackingSegmentUuid: 'b' })
  const poorFix = footprint('poor-fix', latitudeForMeters(100), at(8 * 60 + 2), {
    accuracyM: 250,
    trackingSegmentUuid: 'b',
  })
  const afterPoorFix = footprint('after-poor-fix', latitudeForMeters(130), at(8 * 60 + 3), { trackingSegmentUuid: 'b' })
  const segments = buildFootprintSegments([start, restarted, longGap, cityJump, poorFix, afterPoorFix])
  assert.deepEqual(segments.map((segment) => segment.map((point) => point.uuid)), [
    ['start'], ['restart'], ['long-gap'], ['city'], ['after-poor-fix'],
  ])
})

test('弱信号漂移仍切断轨迹，但不参与自动取景；有效打卡仍纳入范围', () => {
  const before = footprint('before', 0, at(0), { trackingSegmentUuid: 'same' })
  const drift = footprint('drift', 1, at(1), { accuracyM: 250, trackingSegmentUuid: 'same' })
  const after = footprint('after', latitudeForMeters(100), at(2), { trackingSegmentUuid: 'same' })
  const checkin = footprint('checkin', latitudeForMeters(50), at(3), {
    footprintType: 'MANUAL_CHECKIN',
    accuracyM: null,
    speedMps: null,
    trackingSegmentUuid: 'same',
  })
  const segments = buildFootprintSegments([before, drift, after, checkin])
  const viewportPoints = selectFootprintViewportPoints(
    segments,
    [checkin, footprint('invalid-checkin', 91, at(4), { footprintType: 'MANUAL_CHECKIN' })],
  )

  assert.deepEqual(segments.map((segment) => segment.map((point) => point.uuid)), [['before'], ['after', 'checkin']])
  assert.deepEqual(viewportPoints.map((point) => point.uuid).sort(), ['after', 'before', 'checkin'])
  assert.ok(viewportPoints.every((point) => point.latitude < 1))
})

test('缺少 trackingSegmentUuid 的历史记录仍依据时间和空间连续性构建路线', () => {
  const old1 = footprint('old-1', latitudeForMeters(0), at(0))
  const old2 = footprint('old-2', latitudeForMeters(22), at(1))
  const old3 = footprint('old-3', latitudeForMeters(44), at(2))
  const segments = buildFootprintSegments([old3, old1, old2])
  assert.equal(segments.length, 1)
  assert.deepEqual(segments[0].map((point) => point.uuid), ['old-1', 'old-2', 'old-3'])
})

test('同段内设备上报的可疑高速会隔离该点两侧的路线', () => {
  const before = footprint('before', latitudeForMeters(0), at(0), { trackingSegmentUuid: 'same' })
  const suspicious = footprint('suspicious', latitudeForMeters(30), at(1), { trackingSegmentUuid: 'same', speedMps: 80 })
  const after = footprint('after', latitudeForMeters(60), at(2), { trackingSegmentUuid: 'same' })

  const segments = buildFootprintSegments([before, suspicious, after])

  assert.deepEqual(segments.map((segment) => segment.map((point) => point.uuid)), [['before'], ['suspicious'], ['after']])
})

test('15 米内自动采样只影响显示线，附近手动打卡仍被保留', () => {
  const gps1 = footprint('gps-1', latitudeForMeters(0), at(0))
  const checkin = footprint('checkin', latitudeForMeters(4), at(1), {
    footprintType: 'MANUAL_CHECKIN', accuracyM: null, speedMps: null,
  })
  const gps2 = footprint('gps-2', latitudeForMeters(8), at(2))
  const segments = buildFootprintSegments([gps1, checkin, gps2])
  assert.deepEqual(segments[0].map((point) => point.uuid), ['gps-1', 'checkin'])
})

test('缩远时减少 GPS 圆点，保留端点和显著转弯，打卡不进入 GPS 筛选结果', () => {
  const points = [
    footprint('a', latitudeForMeters(0), at(0)),
    footprint('b', latitudeForMeters(10), at(1)),
    footprint('c', latitudeForMeters(20), at(2)),
    footprint('turn', latitudeForMeters(30), at(3)),
    footprint('d', latitudeForMeters(30), at(4), { longitude: latitudeForMeters(10) }),
    footprint('checkin', latitudeForMeters(30), at(5), { longitude: latitudeForMeters(15), footprintType: 'MANUAL_CHECKIN' }),
    footprint('e', latitudeForMeters(30), at(6), { longitude: latitudeForMeters(20) }),
    footprint('end', latitudeForMeters(30), at(7), { longitude: latitudeForMeters(30) }),
  ]
  const projectAt = (scale) => (point) => ({ x: point.longitude * 111320 * scale, y: point.latitude * 111320 * scale })
  const segments = [points]
  const street = selectVisibleAutomaticPoints(segments, projectAt(2), 22)
  const world = selectVisibleAutomaticPoints(segments, projectAt(0.2), 22)
  assert.ok(street.size > world.size)
  assert.ok(street.has('a') && street.has('end') && street.has('turn'))
  assert.ok(!street.has('checkin'))
  assert.ok(world.has('a') && world.has('end'))
})
