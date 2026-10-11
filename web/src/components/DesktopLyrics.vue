<script setup>
// 桌面歌词：一条浮在最上层的纸笺。没锁时是一张能拖动的纸，字是墨色的；
// 锁上以后纸笺隐去，只剩描了边的字浮在桌面上，鼠标可以从它身上穿过去。
// 窗口里纯 #010101 的地方会被系统抠成透明，所以这里不用半透明，深浅都用实色。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, connectEvents } from '../api.js'
import Icon from './Icon.vue'
import { fontStack, LETTER_FONTS } from '../fonts.js'

const now = ref(null) // { title, artist, lines, plain, playing, time }
const settings = ref({ lyrics_size: 32, lyrics_locked: false })
let receivedAt = performance.now()
const tick = ref(0)

function take(data) {
  now.value = data
  receivedAt = performance.now()
}

const position = computed(() => {
  tick.value // re-evaluated on every frame tick
  const n = now.value
  if (!n) return 0
  return n.time + (n.playing ? (performance.now() - receivedAt) / 1000 : 0)
})
const index = computed(() => {
  const lines = now.value?.lines || []
  let i = -1
  for (let k = 0; k < lines.length; k++) {
    if (lines[k][0] <= position.value + 0.15) i = k
    else break
  }
  return i
})
const lines = computed(() => {
  const n = now.value
  if (!n || !n.title) return ['Violet · 桌面歌词', '放一首歌，歌词会浮在这里']
  if (n.lines?.length) {
    const list = n.lines.filter((l) => l[1])
    const i = Math.max(0, index.value)
    const at = n.lines[i]?.[1] || n.lines.find((l) => l[1])?.[1] || ''
    const next = n.lines.slice(i + 1).find((l) => l[1])?.[1] || ''
    return index.value < 0 ? [`${n.title}`, list[0]?.[1] || n.artist] : [at, next]
  }
  if (n.plain?.length) return [n.plain[0], n.plain[1] || '']
  return [n.title, n.artist ? `${n.artist} · 这首歌没有歌词` : '这首歌没有歌词']
})
const size = computed(() => settings.value.lyrics_size || 32)
// The letters are written in the font and ink chosen in the stationery box.
const INK = { violet: '#3b2a5c', blueblack: '#22304d', sepia: '#5a3b26', green: '#2c4a3b', black: '#262326' }
const look = computed(() => {
  const st = settings.value.stationery || {}
  return { '--lyric-font': fontStack(st.font), '--lyric-ink': INK[st.ink] || INK.violet,
    '--lyric-scale': (LETTER_FONTS[st.font] || LETTER_FONTS.wenkai).scale }
})
const locked = computed(() => Boolean(settings.value.lyrics_locked))

const save = (patch) => api.saveSettings(patch).then((s) => (settings.value = s)).catch(() => {})
const bigger = () => save({ lyrics_size: Math.min(56, size.value + 4) })
const smaller = () => save({ lyrics_size: Math.max(20, size.value - 4) })
const lock = () => save({ lyrics_locked: true })
const close = () => save({ desktop_lyrics: false })

let frame = 0
let disconnect = null
function loop() {
  tick.value++
  frame = setTimeout(() => requestAnimationFrame(loop), 120)
}

onMounted(async () => {
  document.documentElement.classList.add('lyrics-mode')
  try {
    const data = await api.lyricsNowGet()
    if (data.now) take(data.now)
    settings.value = data.settings
  } catch {
    /* the strip waits for the first event */
  }
  disconnect = connectEvents((message) => {
    if (message.type === 'lyrics') take(message.data)
    else if (message.type === 'settings') settings.value = message.data
  })
  loop()
})
onBeforeUnmount(() => {
  clearTimeout(frame)
  disconnect?.()
})
</script>

<template>
  <div class="strip" :class="{ locked }" :style="{ '--size': `calc(${size}px * var(--lyric-scale, 1))`, ...look }">
    <div class="paper" aria-hidden="true" />
    <!-- Locked, the letters cannot fade (half-transparent pixels would darken against the cut-out colour):
         they are written in from the left instead. -->
    <Transition :name="locked ? 'wipe' : 'line'" mode="out-in">
      <p :key="lines[0]" class="now">{{ lines[0] }}</p>
    </Transition>
    <Transition :name="locked ? 'wipe' : 'line'" mode="out-in">
      <p :key="lines[1]" class="next">{{ lines[1] }}</p>
    </Transition>
    <div v-if="!locked" class="tools">
      <button title="字小一点" @click="smaller"><span class="a small">A</span></button>
      <button title="字大一点" @click="bigger"><span class="a">A</span></button>
      <button title="锁住：纸笺隐去，鼠标可以穿过歌词（在播放栏里解锁）" @click="lock"><Icon name="lock" :size="15" /></button>
      <button title="收起桌面歌词" @click="close"><Icon name="close" :size="15" /></button>
    </div>
  </div>
</template>

<style>
html.lyrics-mode,
html.lyrics-mode body {
  background: transparent !important;
  overflow: hidden;
}
html.lyrics-mode body::before,
html.lyrics-mode body::after {
  display: none !important;
}
</style>

<style scoped>
.strip {
  position: fixed;
  inset: 10px 12px;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 4px;
  padding: 10px 70px;
  font-family: var(--lyric-font, var(--font-body));
  user-select: none;
  cursor: grab;
}
/* Unlocked: a strip of cream writing paper with a deckled lower edge. */
.paper {
  position: absolute;
  inset: 0;
  background: #f6efe1;
  border: 1px solid #c9b88f;
  border-radius: 3px;
  clip-path: polygon(0 0, 100% 0, 100% 92%, 96% 100%, 88% 95%, 79% 100%, 68% 96%, 57% 100%, 46% 95%, 35% 100%,
    24% 96%, 13% 100%, 5% 95%, 0 100%);
  transition: opacity 0.3s;
}
.locked .paper {
  opacity: 0;
}
p {
  position: relative;
  margin: 0;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  text-align: center;
  line-height: 1.3;
}
.now {
  font-size: var(--size);
  color: var(--lyric-ink);
}
.next {
  font-size: calc(var(--size) * 0.56);
  color: #8a7aa6;
}
/* Locked: no paper; solid cream letters outlined in deep violet so they read on any wallpaper. */
.locked .now,
.locked .next {
  text-shadow: 0 0 1px #2a1d42, 0 0 2px #2a1d42, 0 1px 2px #2a1d42, 0 0 3px #2a1d42;
}
.locked .now {
  color: #fbf4e4;
}
.locked .next {
  color: #d8c9f0;
}
.tools {
  position: absolute;
  top: 6px;
  right: 8px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}
.strip:hover .tools {
  opacity: 1;
}
.tools button {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: #6e5a8f;
  background: #efe5cf;
  cursor: pointer;
}
.tools button:hover {
  color: #3b2a5c;
  background: #e6d8b8;
}
.a {
  font-family: var(--font-display);
  font-size: 16px;
}
.a.small {
  font-size: 12px;
}
.line-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.line-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
.line-enter-active,
.line-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.wipe-enter-from {
  clip-path: inset(-20% 100% -20% 0);
}
.wipe-enter-to {
  clip-path: inset(-20% 0 -20% 0);
}
.wipe-enter-active {
  transition: clip-path 0.45s cubic-bezier(0.3, 0.6, 0.3, 1);
}
.wipe-leave-active {
  transition: none;
}
</style>
