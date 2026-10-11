// 主窗口这边：把正在唱的歌和时间告诉桌面歌词那扇小窗（它自己没有播放器）。
// 换歌、播放暂停、拖动进度时各说一次，平时每十来秒对一下表；小窗自己按时钟往前走。
import { watch } from 'vue'
import { api } from './api.js'
import { store, saveSettings } from './store.js'
import { player, current } from './player.js'

let sentTime = 0
let sentAt = 0
let timer = null

function send() {
  if (!store.settings?.desktop_lyrics) return
  const track = current.value
  sentTime = player.time
  sentAt = performance.now()
  api.lyricsNow({
    title: track?.title || '',
    artist: track?.artist || '',
    lines: track ? player.lyrics.map((l) => [l.time, l.text || l.translation]) : [],
    plain: track ? player.plain.slice(0, 4) : [],
    playing: player.playing,
    time: player.time,
  }).catch(() => {})
}

export function startDesktopLyrics() {
  watch([() => current.value?.id, () => player.lyrics, () => player.playing, () => store.settings?.desktop_lyrics], send)
  // A jump in time that the clock cannot explain is a seek.
  watch(() => player.time, (t) => {
    if (!player.playing) return
    const expected = sentTime + (performance.now() - sentAt) / 1000
    if (Math.abs(t - expected) > 1.2) send()
  })
  timer = setInterval(() => player.playing && send(), 12000)
}

export const toggleDesktopLyrics = () => saveSettings({ desktop_lyrics: !store.settings?.desktop_lyrics })
export const toggleLyricsLock = () => saveSettings({ lyrics_locked: !store.settings?.lyrics_locked })
