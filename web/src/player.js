import { reactive, computed } from 'vue'
import { api, audioUrl, libraryCoverUrl } from './api.js'
import { parseLrc, plainLyrics, activeIndex } from './lrc.js'
import { sound } from './sound.js'
import { toast } from './store.js'

const audio = new Audio()
audio.preload = 'metadata'

function savedVolume() {
  try {
    const v = Number(localStorage.getItem('violet-volume'))
    const raw = localStorage.getItem('violet-volume')
    return raw !== null && Number.isFinite(v) && v >= 0 ? Math.min(1, v) : 0.8
  } catch {
    return 0.8
  }
}
audio.volume = savedVolume()

export const player = reactive({
  queue: [],
  index: -1,
  playing: false,
  time: 0,
  duration: 0,
  buffering: false,
  volume: audio.volume,
  muted: false,
  mode: 'order', // order | shuffle | one
  lyrics: [],
  plain: [],
  lyricsLoading: false,
  sheet: false,
})

export const current = computed(() => (player.index >= 0 ? player.queue[player.index] : null))
export const currentLine = computed(() => activeIndex(player.lyrics, player.time))
export const coverOf = (track) => (track?.has_cover ? libraryCoverUrl(track.id) : '')

sound.bindMusic(() => player.playing)

let lyricsFor = null
async function loadLyrics(track) {
  lyricsFor = track.id
  player.lyrics = []
  player.plain = []
  if (!track.has_lyrics) return
  player.lyricsLoading = true
  try {
    const { lyrics } = await api.lyrics(track.id)
    if (lyricsFor !== track.id) return
    player.lyrics = parseLrc(lyrics)
    player.plain = player.lyrics.length ? [] : plainLyrics(lyrics)
  } catch {
    /* lyrics are optional */
  } finally {
    if (lyricsFor === track.id) player.lyricsLoading = false
  }
}

let playedFor = null
// Seconds actually heard of the current track; seeking does not count.
let heard = 0
let lastTime = 0

function load(index, autoplay = true) {
  const track = player.queue[index]
  if (!track) return
  playedFor = null
  heard = 0
  lastTime = 0
  player.index = index
  player.time = 0
  player.duration = (track.duration || 0) / 1000
  audio.src = audioUrl(track.id)
  loadLyrics(track)
  if (autoplay) audio.play().catch(() => {})
  updateMediaSession(track)
}

export function playList(tracks, startIndex = 0) {
  player.queue = tracks.slice()
  load(startIndex)
}

// Songs sent back to the Recycle Bin: the player lets go of the file first (Windows will not bin an open file),
// then of their places in the queue, carrying on with the next song if the current one went.
export function release(ids) {
  const gone = new Set(ids)
  const held = current.value && gone.has(current.value.id)
  const state = { held, playing: held && player.playing, time: audio.currentTime }
  if (held) {
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
  }
  return state
}

export function forgetTracks(removed, state) {
  const gone = new Set(removed)
  const index = player.index
  const before = player.queue.slice(0, Math.max(0, index)).filter((t) => gone.has(t.id)).length
  const currentGone = index >= 0 && gone.has(player.queue[index]?.id)
  player.queue = player.queue.filter((t) => !gone.has(t.id))
  if (!player.queue.length) {
    Object.assign(player, { index: -1, playing: false, time: 0, duration: 0, lyrics: [], plain: [] })
    return
  }
  if (index < 0) return
  if (currentGone) return load(Math.min(index - before, player.queue.length - 1), state.playing)
  player.index = index - before
  if (state.held) {
    // The song could not be binned after all: pick it up again where it was.
    load(player.index, state.playing)
    audio.addEventListener('loadedmetadata', () => (audio.currentTime = state.time), { once: true })
  }
}

export function toggle() {
  if (!current.value) return
  if (audio.paused) audio.play().catch(() => {})
  else audio.pause()
}

export function next(manual = true) {
  const n = player.queue.length
  if (!n) return
  if (player.mode === 'one' && !manual) return load(player.index)
  if (player.mode === 'shuffle' && n > 1) {
    let i = player.index
    while (i === player.index) i = Math.floor(Math.random() * n)
    return load(i)
  }
  if (player.index + 1 < n) load(player.index + 1)
  else if (manual) load(0)
  else {
    player.playing = false
    audio.currentTime = 0
    audio.pause()
  }
}

export function prev() {
  if (audio.currentTime > 4) {
    audio.currentTime = 0
    return
  }
  if (player.index > 0) load(player.index - 1)
  else if (player.queue.length) load(player.queue.length - 1)
}

export function seek(seconds) {
  if (!current.value || !Number.isFinite(seconds)) return
  audio.currentTime = Math.max(0, Math.min(seconds, player.duration || seconds))
  player.time = audio.currentTime
}

export function setVolume(v) {
  audio.volume = Math.max(0, Math.min(1, v))
  audio.muted = false
  try {
    localStorage.setItem('violet-volume', String(audio.volume))
  } catch {
    /* ignore */
  }
}

export function toggleMute() {
  audio.muted = !audio.muted
}

export function cycleMode() {
  player.mode = { order: 'shuffle', shuffle: 'one', one: 'order' }[player.mode]
}

audio.addEventListener('play', () => (player.playing = true))
audio.addEventListener('pause', () => (player.playing = false))
audio.addEventListener('timeupdate', () => {
  player.time = audio.currentTime
  const step = audio.currentTime - lastTime
  lastTime = audio.currentTime
  if (step > 0 && step < 1.5 && !audio.paused) heard += step
  // Count a listen after 15 seconds really heard, so the letters and the stamp book know what you played.
  const track = current.value
  if (track && playedFor !== track.id && heard > 15) {
    playedFor = track.id
    api.played(track.id).catch(() => {})
  }
})
audio.addEventListener('durationchange', () => {
  if (Number.isFinite(audio.duration)) player.duration = audio.duration
})
audio.addEventListener('waiting', () => (player.buffering = true))
audio.addEventListener('playing', () => (player.buffering = false))
audio.addEventListener('volumechange', () => {
  player.volume = audio.volume
  player.muted = audio.muted
})
audio.addEventListener('ended', () => next(false))
audio.addEventListener('error', () => {
  if (!audio.src) return
  player.playing = false
  toast('这封信打不开：文件可能已被移动，或格式不受支持', 'error')
})

function updateMediaSession(track) {
  if (!('mediaSession' in navigator)) return
  navigator.mediaSession.metadata = new MediaMetadata({
    title: track.title,
    artist: track.artist,
    album: track.album,
    artwork: track.has_cover ? [{ src: coverOf(track), sizes: '512x512' }] : [],
  })
  navigator.mediaSession.setActionHandler('play', toggle)
  navigator.mediaSession.setActionHandler('pause', toggle)
  navigator.mediaSession.setActionHandler('nexttrack', () => next(true))
  navigator.mediaSession.setActionHandler('previoustrack', prev)
}
