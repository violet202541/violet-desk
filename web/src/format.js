export function duration(ms) {
  const s = Math.max(0, Math.round((Number(ms) || 0) / 1000))
  if (!s) return '—'
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function bytes(n) {
  n = Number(n) || 0
  if (n >= 1073741824) return `${(n / 1073741824).toFixed(2)} GB`
  if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`
  if (n >= 1024) return `${Math.round(n / 1024)} KB`
  return `${n} B`
}

const DAY = 86400000
export function dayLabel(ts) {
  const date = new Date(ts * 1000)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.floor((today - new Date(date).setHours(0, 0, 0, 0)) / DAY)
  if (diff <= 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff} 天前`
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日`
}

export function timeOfDay(ts) {
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function postmarkDate(ts) {
  const d = new Date(ts * 1000)
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(2)}`
}

// ---------------------------------------------------------------- calendar dates (local time, never UTC)

const pad = (n) => String(n).padStart(2, '0')
export const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

export function isoDate(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function parseDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(iso, n) {
  const d = parseDate(iso)
  d.setDate(d.getDate() + n)
  return isoDate(d)
}

export function daysBetween(a, b) {
  return Math.round((parseDate(b) - parseDate(a)) / DAY)
}

export function weekdayOf(iso) {
  return WEEKDAYS[(parseDate(iso).getDay() + 6) % 7]
}

export function monthDay(iso) {
  const [, m, d] = iso.split('-').map(Number)
  return `${m} 月 ${d} 日`
}

export function longDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return `${y} 年 ${m} 月 ${d} 日`
}

// 今天 / 明天 / 昨天 / 周五 / 10 月 18 日
export function relativeDay(iso, today = isoDate()) {
  const diff = daysBetween(today, iso)
  if (diff === 0) return '今天'
  if (diff === 1) return '明天'
  if (diff === 2) return '后天'
  if (diff === -1) return '昨天'
  if (diff > 2 && diff < 7) return `周${weekdayOf(iso)}`
  if (diff < 0 && diff > -7) return `${-diff} 天前`
  return monthDay(iso)
}

export function hm(seconds) {
  const s = Math.max(0, Math.round(seconds || 0))
  const h = Math.floor(s / 3600)
  const m = Math.round((s % 3600) / 60)
  if (h && m) return `${h} 小时 ${m} 分`
  if (h) return `${h} 小时`
  return `${m} 分钟`
}

const CN_NUM = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']
export const cnMonth = (m) => CN_NUM[m]
export function cnDay(d) {
  if (d <= 10) return d === 10 ? '十' : CN_NUM[d]
  if (d < 20) return '十' + CN_NUM[d - 10]
  if (d % 10 === 0) return CN_NUM[d / 10] + '十'
  return CN_NUM[Math.floor(d / 10)] + '十' + CN_NUM[d % 10]
}
