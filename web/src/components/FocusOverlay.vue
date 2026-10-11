<script setup>
// 代笔时间：专心做一份委托。打字机的纸卷随时间慢慢上移，写满一页泰尔西斯文字。
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { store, loadLibrary } from '../store.js'
import { desk, endFocus } from '../desk.js'
import { player, playList, toggle } from '../player.js'
import { sound } from '../sound.js'
import { trapFocus } from '../dialog.js'
import Nunkish from './Nunkish.vue'
import Icon from './Icon.vue'

const box = ref(null)
const now = ref(Date.now())
const paused = ref(false)
const elapsedBefore = ref(0) // seconds banked before the latest resume
const resumedAt = ref(0)
const target = ref(25 * 60)
const rang = ref(false)
const music = ref(false)
let tick = null

const focus = computed(() => desk.focus)
const elapsed = computed(() => elapsedBefore.value + (paused.value ? 0 : (now.value - resumedAt.value) / 1000))
const remaining = computed(() => Math.max(0, target.value - elapsed.value))
const progress = computed(() => (target.value ? Math.min(1, elapsed.value / target.value) : Math.min(1, elapsed.value / 3600)))
const clock = computed(() => {
  const s = Math.round(target.value ? remaining.value : elapsed.value)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})
const LINES = ['dear', 'i want to know', 'what i love you means', 'letters travel far', 'every word arrives',
  'auto memory doll', 'thank you', 'a quiet afternoon', 'ink and paper', 'violet evergarden', 'i will write it down',
  'someone is waiting', 'carefully', 'one more line', 'the post office', 'almost there']
const shown = computed(() => Math.floor(progress.value * LINES.length))
const DURATIONS = [{ label: '25 分', value: 25 * 60 }, { label: '45 分', value: 45 * 60 }, { label: '60 分', value: 60 * 60 },
  { label: '不计时', value: 0 }]

watch(focus, (f) => {
  clearInterval(tick)
  if (!f) return
  target.value = f.target ?? 25 * 60
  elapsedBefore.value = 0
  resumedAt.value = Date.now()
  paused.value = false
  rang.value = false
  music.value = false
  tick = setInterval(() => {
    now.value = Date.now()
    if (target.value && !rang.value && remaining.value <= 0) {
      rang.value = true
      sound.bell()
    }
  }, 500)
}, { immediate: true })

function pause() {
  if (paused.value) {
    resumedAt.value = Date.now()
    paused.value = false
  } else {
    elapsedBefore.value = elapsed.value
    paused.value = true
  }
}

function extend(minutes) {
  target.value = Math.ceil(elapsed.value) + minutes * 60
  rang.value = false
}

async function toggleMusic() {
  music.value = !music.value
  if (!music.value) {
    if (player.playing) toggle()
    return
  }
  if (player.playing) return
  if (!store.library.loaded) await loadLibrary()
  const tracks = store.library.tracks
  if (!tracks.length) return
  player.mode = 'shuffle'
  playList(tracks, Math.floor(Math.random() * tracks.length))
}

function finish(complete) {
  clearInterval(tick)
  endFocus(elapsed.value, { complete })
}

function abandon() {
  clearInterval(tick)
  desk.focus = null
}

trapFocus(box, () => finish(false))
onBeforeUnmount(() => clearInterval(tick))
</script>

<template>
  <Transition name="focus-fade">
    <div v-if="focus" ref="box" class="focus" role="dialog" aria-modal="true" aria-label="代笔时间">
      <div class="lamp" aria-hidden="true" />
      <p class="eyebrow">Ghostwriting time · 代笔时间</p>
      <h2 class="title-text">{{ focus.commission ? `「${focus.commission.title}」` : '专心做一件事' }}</h2>
      <p v-if="focus.commission?.client" class="faint">委托人：{{ focus.commission.client }}</p>

      <div class="machine" aria-hidden="true">
        <div class="platen">
          <div class="sheet" :style="{ transform: `translateY(${-progress * 62}%)` }">
            <p class="sheet-title mono">COMMISSION No.{{ String(focus.commission?.number || 0).padStart(3, '0') }}</p>
            <Nunkish v-for="(line, i) in LINES.slice(0, shown + 1)" :key="i" :text="line" :size="15" :weight="4"
              :animate="i === shown" :speed="0.12" class="line" />
          </div>
        </div>
        <div class="roller" />
        <div class="keys"><span v-for="n in 11" :key="n" /></div>
      </div>

      <p class="clock mono" :class="{ done: rang }" role="timer">{{ rang ? '时间到' : clock }}</p>
      <div class="durations">
        <button v-for="d in DURATIONS" :key="d.value" class="chip" :class="{ on: target === d.value }"
          @click="target = d.value; rang = false">{{ d.label }}</button>
      </div>

      <div class="controls">
        <template v-if="rang">
          <button class="btn" @click="extend(5)">再写 5 分钟</button>
          <button v-if="focus.commission" class="btn wax" @click="finish(true)"><Icon name="check" :size="15" />完成并送达</button>
          <button class="btn" @click="finish(false)">先到这里</button>
        </template>
        <template v-else>
          <button class="btn" @click="pause"><Icon :name="paused ? 'play' : 'pause'" :size="15" />{{ paused ? '继续' : '歇一下' }}</button>
          <button class="btn" :class="{ on: music }" title="从书信匣随机放歌" @click="toggleMusic"><Icon name="music" :size="15" />伴奏</button>
          <button v-if="focus.commission" class="btn wax" @click="finish(true)"><Icon name="check" :size="15" />完成并送达</button>
          <button class="btn" @click="finish(false)">结束，记下时间</button>
        </template>
      </div>
      <button class="abandon faint" @click="abandon">不记录，直接离开</button>
    </div>
  </Transition>
</template>

<style scoped>
.focus {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 75;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 8px;
  text-align: center;
  background: radial-gradient(70% 60% at 50% 30%, color-mix(in srgb, var(--paper) 92%, var(--gold)), var(--paper) 70%);
  overflow-y: auto;
}
.lamp {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(40% 35% at 50% 18%, rgba(255, 220, 150, 0.18), transparent 70%);
}
.eyebrow,
h2,
p {
  margin: 0;
}
h2 {
  font-weight: 400;
  font-size: 26px;
  max-width: 70vw;
}
.machine {
  position: relative;
  width: 360px;
  margin: 18px 0 6px;
}
.platen {
  height: 190px;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(transparent, #000 25%);
  mask-image: linear-gradient(transparent, #000 25%);
}
.sheet {
  width: 260px;
  min-height: 420px;
  margin: 40px auto 0;
  padding: 18px 22px;
  display: grid;
  align-content: start;
  justify-items: start;
  gap: 8px;
  color: var(--violet-ink);
  background: var(--sheet-raised);
  box-shadow: var(--shadow-sheet);
  transition: transform 1s linear;
}
.sheet-title {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--ink-faint);
}
.roller {
  height: 22px;
  margin: 0 10px;
  border-radius: 11px;
  background: linear-gradient(#3a3344, #15121b 60%, #2c2735);
  box-shadow: 0 4px 10px -4px rgba(0, 0, 0, 0.6);
}
.keys {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 10px 26px 12px;
  margin: 0 24px;
  border-radius: 0 0 18px 18px;
  background: linear-gradient(#2c2733, #1c1822);
}
.keys span {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 35%, #f6efe0, #c9bfae);
  box-shadow: 0 2px 0 #0d0b10;
}
.clock {
  font-size: 54px;
  letter-spacing: 0.06em;
  color: var(--ink);
}
.clock.done {
  font-family: var(--font-title);
  color: var(--violet-ink);
  font-size: 40px;
  padding: 7px 0;
}
.durations,
.controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}
.controls {
  margin-top: 10px;
}
.btn.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.abandon {
  margin-top: 12px;
  font-size: 12.5px;
  text-decoration: underline;
}
.focus-fade-enter-active,
.focus-fade-leave-active {
  transition: opacity 0.5s var(--ease);
}
.focus-fade-enter-from,
.focus-fade-leave-to {
  opacity: 0;
}
</style>
