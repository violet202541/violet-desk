// LRC 解析：同一时间戳的第二行视为翻译（网易云原文 + 译文拼接格式）。

const TIME = /\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]/g

export function parseLrc(text) {
  if (!text) return []
  const byTime = new Map()
  let offset = 0
  for (const raw of String(text).split(/\r?\n/)) {
    const offsetMatch = raw.match(/^\[offset:\s*([+-]?\d+)\]/i)
    if (offsetMatch) {
      offset = Number(offsetMatch[1]) / 1000
      continue
    }
    const stamps = [...raw.matchAll(TIME)]
    if (!stamps.length) continue
    const line = raw.replace(TIME, '').trim()
    for (const m of stamps) {
      const frac = m[3] ? Number(m[3]) / 10 ** m[3].length : 0
      const time = Math.max(0, Number(m[1]) * 60 + Number(m[2]) + frac - offset)
      const key = time.toFixed(2)
      const entry = byTime.get(key)
      if (!entry) byTime.set(key, { time, text: line, translation: '' })
      else if (line && !entry.translation && line !== entry.text) entry.translation = line
      else if (!entry.text) entry.text = line
    }
  }
  return [...byTime.values()]
    .filter((l) => l.text || l.translation)
    .sort((a, b) => a.time - b.time)
}

export function plainLyrics(text) {
  return String(text || '')
    .split(/\r?\n/)
    .map((l) => l.replace(TIME, '').trim())
    .filter((l) => l && !/^\[[a-z]+:/i.test(l))
}

export function activeIndex(lines, time) {
  let lo = 0
  let hi = lines.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (lines[mid].time <= time + 0.15) {
      found = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  return found
}
