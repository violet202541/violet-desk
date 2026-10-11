// 本地服务客户端：令牌从启动地址 ?t= 读取，保存在会话内。

function readToken() {
  const fromUrl = new URLSearchParams(location.search).get('t')
  try {
    if (fromUrl) sessionStorage.setItem('violet-token', fromUrl)
    return fromUrl || sessionStorage.getItem('violet-token') || ''
  } catch {
    return fromUrl || ''
  }
}

export const token = readToken()

export class ApiError extends Error {
  constructor(message, status, code, current) {
    super(message)
    this.status = status
    this.code = code
    this.current = current
  }
}

async function request(method, path, { params, body, raw, signal } = {}) {
  const url = new URL(path, location.origin)
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, v)
  }
  let response
  try {
    response = await fetch(url, {
      method,
      signal,
      headers: {
        'X-Violet-Token': token,
        ...(raw ? { 'Content-Type': raw.type || 'application/octet-stream' } : body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: raw || (body ? JSON.stringify(body) : undefined),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('无法连接到 Violet 本地服务，请重新启动应用', 0)
  }
  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }
  if (!response.ok) {
    throw new ApiError(data?.error || `请求失败（${response.status}）`, response.status, data?.code, data?.current)
  }
  return data
}

export const api = {
  state: () => request('GET', '/api/state'),
  search: (q, platform, signal, page = 0) => request('GET', '/api/search', { params: { q, platform, page }, signal }),
  playlist: (src, platform, signal) => request('GET', '/api/playlist', { params: { src, platform }, signal }),
  saveSettings: (settings) => request('POST', '/api/settings', { body: settings }),
  setKey: (key, remember) => request('POST', '/api/key', { body: { key, remember } }),
  forgetKey: () => request('POST', '/api/key/forget', { body: {} }),
  verifyKey: () => request('POST', '/api/key/verify', { body: {} }),
  download: (songs) => request('POST', '/api/downloads', { body: { songs } }),
  cancel: (id) => request('POST', '/api/downloads/cancel', { body: { id } }),
  retry: (id) => request('POST', '/api/downloads/retry', { body: { id } }),
  retryRecord: (record) => request('POST', '/api/downloads/retry', { body: { record } }),
  clearFinished: () => request('POST', '/api/downloads/clear', { body: {} }),
  removeHistory: (ids) => request('POST', '/api/history/remove', { body: { ids } }),
  clearHistory: () => request('POST', '/api/history/clear', { body: {} }),
  library: (refresh) => request('GET', '/api/library', { params: { refresh: refresh ? 1 : undefined } }),
  lyrics: (id) => request('GET', `/api/library/${id}/lyrics`),
  references: (ids) => request('POST', '/api/library/references', { body: { ids } }),
  sendBack: (ids) => request('POST', '/api/library/delete', { body: { ids } }),
  duplicates: () => request('GET', '/api/library/duplicates'),
  lyricsNow: (data) => request('POST', '/api/lyrics/now', { body: data }),
  lyricsNowGet: () => request('GET', '/api/lyrics/now'),
  exportImage: (blob, name) => request('POST', '/api/export-image', { params: { name }, raw: blob }),
  reveal: (target) => request('POST', '/api/reveal', { body: target }),
  pickFolder: (initial) => request('POST', '/api/pick-folder', { body: { initial } }),
  window: (action, edge) => request('POST', '/api/window', { body: { action, edge } }),
  pickImage: () => request('POST', '/api/pick-image', { body: {} }),
  todayLetter: () => request('GET', '/api/letters/today'),
  letters: () => request('GET', '/api/letters'),
  updateLetter: (date, changes) => request('POST', '/api/letters/update', { body: { date, ...changes } }),
  played: (id) => request('POST', `/api/library/${id}/played`, { body: {} }),

  // the desk
  deskToday: () => request('GET', '/api/desk/today'),
  commissions: () => request('GET', '/api/commissions'),
  createCommission: (data) => request('POST', '/api/commissions', { body: data }),
  updateCommission: (id, data) => request('POST', `/api/commissions/${id}`, { body: data }),
  completeCommission: (id, done) => request('POST', `/api/commissions/${id}/complete`, { body: { done } }),
  focus: (id, seconds, started) =>
    request('POST', id ? `/api/commissions/${id}/focus` : '/api/focus', { body: { seconds, started } }),
  remove: (kind, id) => request('POST', `/api/${kind}/${id}/delete`, { body: {} }),
  restore: (kind, id) => request('POST', `/api/${kind}/${id}/restore`, { body: {} }),
  calendar: (month) => request('GET', '/api/calendar', { params: { month } }),
  day: (date) => request('GET', '/api/day', { params: { date } }),
  createAppointment: (data) => request('POST', '/api/appointments', { body: data }),
  updateAppointment: (id, data) => request('POST', `/api/appointments/${id}`, { body: data }),
  replies: () => request('GET', '/api/replies'),
  reply: (id) => request('GET', `/api/replies/${id}`),
  createReply: (data) => request('POST', '/api/replies', { body: data }),
  updateReply: (id, data) => request('POST', `/api/replies/${id}`, { body: data }),
  sealReply: (id, data) => request('POST', `/api/replies/${id}/seal`, { body: data }),
  unsealReply: (id) => request('POST', `/api/replies/${id}/unseal`, { body: {} }),
  openReply: (id) => request('POST', `/api/replies/${id}/open`, { body: {} }),
  uploadPhoto: (blob) => request('POST', '/api/photos', { raw: blob }),
  weekly: (week) => request('GET', '/api/weekly', { params: { week } }),
  sealWeek: (week, note) => request('POST', `/api/weekly/${week}/seal`, { body: { note } }),
  backups: () => request('GET', '/api/backups'),
  runBackup: () => request('POST', '/api/backups/run', { body: {} }),
  restoreBackup: (name, where) => request('POST', '/api/backups/restore', { body: { name, where } }),

  // the shelf: pressed flowers (favourites) and bundles of letters (playlists)
  shelf: () => request('GET', '/api/shelf'),
  press: (trackId, press = true, note) => request('POST', '/api/pressed', { body: { track_id: trackId, press, note } }),
  bundle: (id) => request('GET', `/api/bundles/${id}`),
  createBundle: (data) => request('POST', '/api/bundles', { body: data }),
  updateBundle: (id, data) => request('POST', `/api/bundles/${id}`, { body: data }),
  addToBundle: (id, data) => request('POST', `/api/bundles/${id}/add`, { body: data }),
  removeFromBundle: (id, letterIds) => request('POST', `/api/bundles/${id}/remove`, { body: { letter_ids: letterIds } }),
  orderBundle: (id, letterIds) => request('POST', `/api/bundles/${id}/order`, { body: { letter_ids: letterIds } }),

  // 鸿雁: school notices fetched along routes and sorted by the recipient's card
  geese: () => request('GET', '/api/geese'),
  geeseDrawer: (box, q) => request('GET', '/api/geese/drawer', { params: { box, q } }),
  geeseLetter: (id) => request('GET', `/api/geese/letters/${id}`),
  geeseUpdate: (id, data) => request('POST', `/api/geese/letters/${id}`, { body: data }),
  geeseWords: (id) => request('GET', `/api/geese/letters/${id}/words`),
  geeseTeach: (id, data) => request('POST', `/api/geese/letters/${id}/teach`, { body: data }),
  geeseCard: (card) => request('POST', '/api/geese/card', { body: card }),
  geeseTrial: (card) => request('POST', '/api/geese/trial', { body: card }),
  geeseFetch: () => request('POST', '/api/geese/fetch', { body: {} }),
  geeseRoutes: () => request('GET', '/api/geese/routes'),
  geeseRoute: (id, data) => request('POST', `/api/geese/routes/${id}`, { body: data }),
  geesePreview: (pack) => request('POST', '/api/geese/packs/preview', { body: { pack } }),
  geeseInstall: (pack, trust) => request('POST', '/api/geese/packs/install', { body: { pack, trust } }),
  geeseRemovePack: (id) => request('POST', `/api/geese/packs/${id}/remove`, { body: {} }),
  geeseLogin: (portal) => request('POST', `/api/geese/portals/${portal}/login`, { body: {} }),
  geeseLogout: (portal) => request('POST', `/api/geese/portals/${portal}/logout`, { body: {} }),
}

export const photoUrl = (name) => mediaUrl(`/api/photos/${name}`)

export function mediaUrl(path) {
  return `${path}${path.includes('?') ? '&' : '?'}t=${encodeURIComponent(token)}`
}

export const audioUrl = (id) => mediaUrl(`/api/library/${id}/audio`)
export const libraryCoverUrl = (id) => mediaUrl(`/api/library/${id}/cover`)

// Remote covers go through the local proxy so they share a cache and can be sampled for colour.
export function coverUrl(song, size = 120) {
  if (!song) return ''
  let url = song.picUrl || song.cover || ''
  if (!url && song.album_mid) url = `https://y.gtimg.cn/music/photo_new/T002R300x300M000${song.album_mid}.jpg`
  if (!url) return ''
  if (url.includes('music.126.net') && !url.includes('param=')) url += `${url.includes('?') ? '&' : '?'}param=${size}y${size}`
  return mediaUrl(`/api/img?u=${encodeURIComponent(url)}`)
}

export function connectEvents(onMessage, onStatus) {
  let source = null
  let closed = false
  const open = () => {
    if (closed) return
    source = new EventSource(mediaUrl('/api/events'))
    source.onopen = () => onStatus?.(true)
    source.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data))
      } catch {
        /* ignore malformed frames */
      }
    }
    source.onerror = () => onStatus?.(false)
  }
  open()
  return () => {
    closed = true
    source?.close()
  }
}
