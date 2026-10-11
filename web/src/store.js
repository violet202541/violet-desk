import { reactive, computed, watch } from 'vue'
import { api, connectEvents } from './api.js'
import { sound } from './sound.js'

export const TERMINAL = new Set(['done', 'skipped', 'failed', 'cancelled'])

// Pages. The music pages share one bookmark in the sidebar and switch with index tabs.
export const MUSIC_VIEWS = ['search', 'playlist', 'library', 'shelf', 'post']
export const VIEWS = ['desk', 'commissions', 'calendar', 'mailbox', 'geese', ...MUSIC_VIEWS, 'settings', 'write']

export const STATE_LABEL = {
  queued: '待寄',
  resolving: '代笔中',
  downloading: '寄送中',
  finishing: '封缄中',
  cancelling: '撤回中',
  done: '已送达',
  skipped: '已存在',
  failed: '未送达',
  cancelled: '已撤回',
}

function catalogView(extra = {}) {
  return {
    songs: [],
    selected: new Set(),
    filter: '',
    loading: false,
    error: '',
    warnings: [],
    reqId: 0,
    abort: null,
    ...extra,
  }
}

export const store = reactive({
  ready: false,
  connected: true,
  bootError: '',
  version: '',
  settings: null,
  key: { has_key: false },
  quota: {},
  jobs: [],
  history: [],
  platforms: {},
  qualities: {},
  qualityLabels: {},
  chartCatalog: {},
  windowed: false,
  frame: { frameless: false, maximized: false },
  tray: false,
  today: '',
  view: 'desk',
  musicTab: 'search',
  keyDialog: null,
  confirmDialog: null,
  toasts: [],
  search: catalogView({ query: '', platform: 'netease', lastQuery: '', page: 0, hasMore: false, loadingMore: false }),
  playlist: catalogView({ source: '', platform: 'qq', info: null }),
  library: { tracks: [], roots: [], loading: false, loaded: false, stale: true, filter: '', sort: 'recent', mode: 'grid', error: '' },
  letters: { today: null, list: [], loaded: false, envelope: null, reading: null, filter: 'all' },
  backups: null,
})

export function go(view) {
  if (view === 'music') view = store.musicTab
  if (!VIEWS.includes(view)) return
  if (MUSIC_VIEWS.includes(view)) store.musicTab = view
  store.view = view
}

export const songKey = (song) => `${song.platform}:${song.id}`

export const activeJobs = computed(() => store.jobs.filter((job) => !TERMINAL.has(job.state)))

// ---------------------------------------------------------------- theme

const media = window.matchMedia('(prefers-color-scheme: dark)')
export function applyTheme() {
  const theme = store.settings?.theme || 'auto'
  const root = document.documentElement
  if (theme === 'auto') delete root.dataset.theme
  else root.dataset.theme = theme
  try {
    localStorage.setItem('violet-theme', theme)
  } catch {
    /* storage may be unavailable */
  }
}
export const isDark = () => {
  const theme = store.settings?.theme || 'auto'
  return theme === 'dark' || (theme === 'auto' && media.matches)
}

// ---------------------------------------------------------------- toasts

let toastId = 0
// action: optional { label, run } — e.g. 撤销 after tearing up a commission.
export function toast(text, level = 'info', timeout = 4200, action = null) {
  const id = ++toastId
  store.toasts.push({ id, text, level, action })
  if (store.toasts.length > 4) store.toasts.shift()
  setTimeout(() => dismissToast(id), timeout)
}
export function dismissToast(id) {
  const index = store.toasts.findIndex((t) => t.id === id)
  if (index >= 0) store.toasts.splice(index, 1)
}

// ---------------------------------------------------------------- boot and events

function applyState(state) {
  store.version = state.version
  store.settings = state.settings
  store.key = state.key
  store.quota = state.quota || {}
  store.jobs = state.jobs || []
  store.history = state.history || []
  store.platforms = state.platforms
  store.qualities = state.qualities
  store.qualityLabels = state.quality_labels
  store.chartCatalog = state.chart_catalog || {}
  store.windowed = state.window
  store.frame = state.frame || store.frame
  store.tray = Boolean(state.tray)
  store.today = state.today
  if (state.history_error) toast(state.history_error, 'warning', 8000)
  applyTheme()
}

function upsertJob(job) {
  const index = store.jobs.findIndex((j) => j.id === job.id)
  const previous = index >= 0 ? store.jobs[index] : null
  if (index >= 0) store.jobs[index] = job
  else store.jobs.push(job)
  const historyIndex = store.history.findIndex((r) => r.id === job.id)
  if (TERMINAL.has(job.state)) {
    if (historyIndex >= 0) store.history[historyIndex] = { ...store.history[historyIndex], ...job }
    else store.history.unshift(job)
    if (previous && !TERMINAL.has(previous.state)) {
      if (job.state === 'done') {
        store.library.stale = true
        sound.bell()
      }
    }
  } else if (historyIndex >= 0) {
    store.history.splice(historyIndex, 1)
  }
}

function onEvent({ type, data }) {
  switch (type) {
    case 'job':
      upsertJob(data)
      break
    case 'jobs':
      store.jobs = data
      break
    case 'history':
      store.history = data
      break
    case 'quota':
      store.quota = data
      break
    case 'settings':
      store.settings = data
      applyTheme()
      break
    case 'key':
      store.key = data
      break
    case 'window':
      store.frame = data
      break
    case 'notice':
      toast(data.text, data.level || 'info', 6500)
      break
    case 'reminder':
      sound.bell()
      toast(`${data.heading} · ${data.text}`, 'warning', 12000, { label: '去看看', run: () => go(data.kind === 'commission' ? 'commissions' : 'calendar') })
      for (const fn of listeners.reminder) fn(data)
      break
    case 'navigate':
      if (data.view === 'write') for (const fn of listeners.write) fn()
      else go(data.view)
      break
    case 'backup':
      store.backups = data
      break
    case 'restored':
      toast('已从备份恢复，正在重新载入…', 'success')
      setTimeout(() => window.location.reload(), 900)
      break
    case 'geese':
    case 'geese-progress':
    case 'geese-login':
      for (const fn of listeners[type] || []) fn(data)
      break
    case 'drained': {
      const c = data || {}
      const parts = [`送达 ${c.done || 0}`]
      if (c.skipped) parts.push(`已存在 ${c.skipped}`)
      if (c.failed) parts.push(`未送达 ${c.failed}`)
      if (c.cancelled) parts.push(`撤回 ${c.cancelled}`)
      toast(`这一批信件已全部处理 · ${parts.join(' · ')}`, c.failed ? 'warning' : 'success', 6000)
      break
    }
  }
}

export async function boot() {
  try {
    applyState(await api.state())
    store.ready = true
  } catch (error) {
    store.bootError = error.message
    return
  }
  connectEvents(onEvent, async (ok) => {
    const wasDown = !store.connected
    store.connected = ok
    if (ok && wasDown) {
      try {
        applyState(await api.state())
      } catch {
        /* keep the old state until the next reconnect */
      }
    }
  })
  media.addEventListener('change', applyTheme)
}

// ---------------------------------------------------------------- dialogs

export function confirm(title, text, ok = '确定') {
  return new Promise((resolve) => {
    store.confirmDialog = { title, text, ok, resolve }
  })
}

// ---------------------------------------------------------------- key gate

export function requireKey(reason) {
  if (store.key?.has_key) return Promise.resolve(true)
  return new Promise((resolve) => {
    store.keyDialog = { reason, resolve }
  })
}

// ---------------------------------------------------------------- catalog

function beginRequest(view) {
  view.abort?.abort()
  const controller = new AbortController()
  view.abort = controller
  view.reqId += 1
  view.loading = true
  view.error = ''
  return { id: view.reqId, signal: controller.signal }
}

export async function runSearch() {
  const view = store.search
  const query = view.query.trim()
  if (!query) {
    toast('写下想听的歌名、歌手或一句歌词', 'warning')
    return
  }
  if (!(await requireKey('搜索需要 ChKSz API Key'))) return
  const { id, signal } = beginRequest(view)
  try {
    const result = await api.search(query, view.platform, signal)
    if (id !== view.reqId) return
    view.songs = result.songs
    view.warnings = result.warnings || []
    view.selected = new Set()
    view.filter = ''
    view.lastQuery = query
    view.lastPlatform = view.platform
    view.page = 0
    view.hasMore = Boolean(result.has_more)
    if (view.warnings.length) toast('部分平台暂不可用：' + view.warnings.join('；'), 'warning', 7000)
  } catch (error) {
    if (error.name === 'AbortError' || id !== view.reqId) return
    view.error = error.message
    if (error.code === 'no_key') requireKey(error.message)
  } finally {
    if (id === view.reqId) view.loading = false
  }
}

export async function loadMore() {
  const view = store.search
  if (!view.hasMore || view.loadingMore || !view.lastQuery) return
  view.loadingMore = true
  const id = view.reqId
  try {
    const result = await api.search(view.lastQuery, view.lastPlatform, undefined, view.page + 1)
    if (id !== view.reqId) return
    const known = new Set(view.songs.map(songKey))
    const fresh = result.songs.filter((s) => !known.has(songKey(s)))
    view.songs.push(...fresh)
    view.page = result.page
    view.hasMore = Boolean(result.has_more) && fresh.length > 0
    if (!fresh.length) toast('没有更多新的结果了', 'info')
    if (result.warnings?.length) toast('部分平台暂不可用：' + result.warnings.join('；'), 'warning', 7000)
  } catch (error) {
    if (id === view.reqId) toast(error.message, 'error', 6000)
  } finally {
    view.loadingMore = false
  }
}

// ---------------------------------------------------------------- daily letters

// Other modules (the desk) subscribe to server events without importing each other in a circle.
const listeners = { reminder: [], write: [] }
export function on(kind, fn) {
  ;(listeners[kind] ||= []).push(fn)
}

export async function loadTodayLetter() {
  try {
    const letter = await api.todayLetter()
    store.letters.today = letter
    const index = store.letters.list.findIndex((l) => l.date === letter.date)
    if (index >= 0) store.letters.list[index] = letter
    else if (store.letters.loaded) store.letters.list.unshift(letter)
  } catch {
    /* the letter can wait until tomorrow */
  }
}

export async function loadLetters() {
  try {
    store.letters.list = (await api.letters()).letters
    store.letters.loaded = true
  } catch (error) {
    toast(error.message, 'error')
  }
}

// Open an envelope from the desk: the overlay plays the unsealing, then shows the letter.
export function openLetter(letter) {
  if (letter.opened) {
    store.letters.reading = letter
  } else {
    store.letters.envelope = letter
  }
}

export async function updateLetter(date, changes) {
  try {
    const letter = await api.updateLetter(date, changes)
    const index = store.letters.list.findIndex((l) => l.date === date)
    if (index >= 0) store.letters.list[index] = letter
    if (store.letters.today?.date === date) store.letters.today = letter
    if (store.letters.reading?.date === date) store.letters.reading = letter
    return letter
  } catch (error) {
    toast(error.message, 'error')
    return null
  }
}

export async function loadPlaylist() {
  const view = store.playlist
  const source = view.source.trim()
  if (!source) {
    toast('请粘贴歌单链接或数字 ID', 'warning')
    return
  }
  const platform = /music\.163\.com|163cn\.tv/.test(source) ? 'netease' : /qq\.com/.test(source) ? 'qq' : view.platform
  view.platform = platform
  if (platform === 'netease' && !(await requireKey('载入网易云歌单需要 API Key'))) return
  const { id, signal } = beginRequest(view)
  try {
    const result = await api.playlist(source, platform, signal)
    if (id !== view.reqId) return
    view.songs = result.songs
    view.info = { title: result.title, cover: result.cover, platform: result.platform, id: result.id }
    view.selected = new Set()
    view.filter = ''
  } catch (error) {
    if (error.name === 'AbortError' || id !== view.reqId) return
    view.error = error.message
  } finally {
    if (id === view.reqId) view.loading = false
  }
}

export async function sendLetters(songs) {
  if (!songs.length) {
    toast('先选几首想寄回来的歌', 'warning')
    return false
  }
  if (!(await requireKey('下载需要 ChKSz API Key'))) return false
  try {
    const result = await api.download(songs)
    if (result.added) {
      sound.carriage()
      toast(`已交给邮差 ${result.added} 封信${result.duplicates ? ` · ${result.duplicates} 封已在路上` : ''}`, 'success')
    } else {
      toast('这些信已经在路上了', 'info')
    }
    return true
  } catch (error) {
    toast(error.message, 'error', 6000)
    if (error.code === 'no_key') requireKey(error.message)
    return false
  }
}

// ---------------------------------------------------------------- library

export async function loadLibrary(refresh = false) {
  const lib = store.library
  if (lib.loading) return
  lib.loading = true
  lib.error = ''
  try {
    const result = await api.library(refresh || lib.stale)
    lib.tracks = result.tracks
    lib.roots = result.roots
    lib.loaded = true
    lib.stale = false
  } catch (error) {
    lib.error = error.message
  } finally {
    lib.loading = false
  }
}

// Only the changed fields travel, so two quick toggles can never overwrite each other.
export async function saveSettings(patch) {
  try {
    store.settings = await api.saveSettings(patch)
    applyTheme()
    return true
  } catch (error) {
    toast(error.message, 'error', 6000)
    return false
  }
}

watch(
  () => store.settings?.sound,
  (on) => sound.setEnabled(Boolean(on)),
)
