<script setup>
import { computed, ref } from 'vue'
import { player, current, toggle, next, prev, seek, setVolume, toggleMute, cycleMode, coverOf, currentLine } from '../player.js'
import { clock } from '../format.js'
import { go } from '../store.js'
import { clipToReply } from '../desk.js'
import { openMenu } from '../shelf.js'
import { store } from '../store.js'
import { toggleDesktopLyrics, toggleLyricsLock } from '../desktopLyrics.js'
import PressFlower from './PressFlower.vue'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import Nunkish from './Nunkish.vue'

const bar = ref(null)
const hover = ref(null)
const dragging = ref(false)
const pct = computed(() => (player.duration ? (player.time / player.duration) * 100 : 0))
const line = computed(() => {
  const l = player.lyrics[currentLine.value]
  return l ? l.text : ''
})
const MODE = { order: ['repeat', '顺序播放'], shuffle: ['shuffle', '随机播放'], one: ['one', '单曲循环'] }

function ratio(event) {
  const rect = bar.value.getBoundingClientRect()
  return Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
}
function onDown(event) {
  if (!current.value) return
  dragging.value = true
  seek(ratio(event) * player.duration)
  const move = (e) => seek(ratio(e) * player.duration)
  const up = () => {
    dragging.value = false
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}
function onBarKey(event) {
  if (!current.value) return
  const steps = { ArrowLeft: -5, ArrowRight: 5, ArrowDown: -5, ArrowUp: 5, PageDown: -30, PageUp: 30 }
  if (event.key in steps) seek(player.time + steps[event.key])
  else if (event.key === 'Home') seek(0)
  else if (event.key === 'End') seek(player.duration - 1)
  else return
  event.preventDefault()
  event.stopPropagation()
}
function onVolume(event) {
  setVolume(Number(event.target.value))
}
</script>

<template>
  <footer class="player" :class="{ idle: !current }">
    <div class="now">
      <button class="cover-btn" :disabled="!current" title="展开歌词" @click="player.sheet = true">
        <CoverArt :src="coverOf(current)" :size="50" :seed="current?.title || 'violet'" :radius="3" />
      </button>
      <div v-if="current" class="meta">
        <span class="title title-text ellipsis">{{ current.title }}</span>
        <span class="sub ellipsis">{{ line || current.artist || '佚名' }}</span>
      </div>
      <div v-else class="meta idle-meta">
        <Nunkish text="silence" :size="15" :weight="4.4" />
        <span class="sub">在书信匣里选一首歌来聆听</span>
      </div>
      <span v-if="current" class="keep">
        <PressFlower :track="current" :size="16" />
        <button class="clip" title="夹进信札（加入歌单）" @click="openMenu([current], $event)"><Icon name="bundle" :size="15" /></button>
        <button class="clip" title="把这首歌夹进今天的回信" @click="clipToReply(current, $event.currentTarget)">
          <Icon name="envelope" :size="15" />
        </button>
      </span>
    </div>

    <div class="center">
      <div class="controls">
        <button class="icon-btn small" :title="MODE[player.mode][1]" :class="{ on: player.mode !== 'order' }" @click="cycleMode">
          <Icon :name="MODE[player.mode][0]" :size="17" />
        </button>
        <button class="icon-btn" :disabled="!current" title="上一首" @click="prev"><Icon name="prev" :size="19" /></button>
        <button class="play" :disabled="!current" :title="player.playing ? '暂停 (Space)' : '播放 (Space)'" @click="toggle">
          <Icon :name="player.playing ? 'pause' : 'play'" :size="20" />
        </button>
        <button class="icon-btn" :disabled="!current" title="下一首" @click="next(true)"><Icon name="next" :size="19" /></button>
        <button class="icon-btn small" :disabled="!current" :class="{ on: player.sheet }" title="歌词" @click="player.sheet = !player.sheet">
          <Icon name="lyrics" :size="17" />
        </button>
      </div>
      <div class="timeline">
        <span class="mono t">{{ clock(player.time) }}</span>
        <div ref="bar" class="bar" :class="{ dragging }" role="slider" :tabindex="current ? 0 : -1" aria-label="播放进度"
          :aria-valuemin="0" :aria-valuemax="Math.round(player.duration)" :aria-valuenow="Math.round(player.time)"
          :aria-valuetext="`${clock(player.time)} / ${clock(player.duration)}`" :aria-disabled="!current"
          @pointerdown="onDown" @pointermove="hover = ratio($event)" @pointerleave="hover = null" @keydown="onBarKey">
          <span class="fill" :style="{ width: pct + '%' }"><span class="nib" /></span>
          <span v-if="hover !== null && current" class="peek mono" :style="{ left: hover * 100 + '%' }">{{ clock(hover * player.duration) }}</span>
        </div>
        <span class="mono t">{{ clock(player.duration) }}</span>
      </div>
    </div>

    <div class="right">
      <button class="icon-btn small" :title="player.muted ? '取消静音' : '静音'" @click="toggleMute">
        <Icon :name="player.muted || player.volume === 0 ? 'mute' : 'volume'" :size="18" />
      </button>
      <input class="volume" type="range" min="0" max="1" step="0.01" :value="player.muted ? 0 : player.volume"
        :style="{ '--v': (player.muted ? 0 : player.volume) * 100 + '%' }" aria-label="音量" @input="onVolume" />
      <span v-if="store.windowed" class="desk-lyrics">
        <button class="icon-btn small" :class="{ on: store.settings?.desktop_lyrics }"
          :title="store.settings?.desktop_lyrics ? '收起桌面歌词' : '桌面歌词：一条浮在最上层的纸笺'" @click="toggleDesktopLyrics">
          <span class="ci title-cn">词</span>
        </button>
        <button v-if="store.settings?.desktop_lyrics && store.settings?.lyrics_locked" class="icon-btn small on"
          title="解锁桌面歌词，就能拖动它了" @click="toggleLyricsLock"><Icon name="unlock" :size="16" /></button>
      </span>
      <button class="icon-btn small" title="书信匣（本地曲库）" @click="go('library')"><Icon name="box" :size="17" /></button>
    </div>
  </footer>
</template>

<style scoped>
.player {
  position: relative;
  z-index: 6;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(360px, 1.4fr) minmax(220px, 1fr);
  align-items: center;
  gap: 24px;
  height: var(--player);
  padding: 0 24px 0 18px;
  background: var(--sheet);
  border-top: 1px solid var(--rule);
  box-shadow: 0 -10px 30px -24px rgba(50, 30, 20, 0.5);
}
.now {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.cover-btn {
  border-radius: 3px;
  box-shadow: var(--shadow-sheet);
  transition: transform 0.25s var(--ease);
}
.cover-btn:hover:not(:disabled) {
  transform: translateY(-2px);
}
.meta {
  display: grid;
  min-width: 0;
  line-height: 1.4;
}
.title {
  font-size: 16px;
}
.sub {
  font-size: 12.5px;
  color: var(--ink-faint);
}
.idle-meta {
  color: var(--violet-ink);
  gap: 4px;
}
.center {
  display: grid;
  gap: 2px;
}
.controls {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
}
.icon-btn.small {
  width: 32px;
  height: 32px;
}
.icon-btn.on {
  color: var(--violet-ink);
}
.play {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  color: var(--wax-text);
  background: radial-gradient(120% 140% at 30% 20%, var(--wax-a), var(--wax-b));
  box-shadow: 0 6px 14px -8px rgba(63, 36, 104, 0.9);
  transition: transform 0.2s var(--ease);
}
.play:hover:not(:disabled) {
  transform: scale(1.06);
}
.play:disabled {
  opacity: 0.4;
}
.timeline {
  display: grid;
  grid-template-columns: 42px 1fr 42px;
  align-items: center;
  gap: 10px;
}
.t {
  font-size: 11.5px;
  color: var(--ink-faint);
  text-align: center;
}
.bar:focus-visible {
  outline-offset: 4px;
}
.bar {
  position: relative;
  height: 14px;
  cursor: pointer;
  touch-action: none;
}
.bar::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 6.5px;
  height: 1px;
  background: var(--rule-strong);
}
.fill {
  position: absolute;
  left: 0;
  top: 6px;
  height: 2px;
  background: var(--violet-ink);
  border-radius: 2px;
}
.nib {
  position: absolute;
  right: -5px;
  top: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg) scale(0);
  background: var(--violet-ink);
  transition: transform 0.2s var(--ease);
}
.bar:hover .nib,
.bar.dragging .nib {
  transform: rotate(-45deg) scale(1);
}
.peek {
  position: absolute;
  bottom: 16px;
  transform: translateX(-50%);
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 3px;
  background: var(--ink);
  color: var(--paper);
  pointer-events: none;
}
.desk-lyrics {
  display: inline-flex;
}
.ci {
  font-size: 15px;
  line-height: 1;
}
.right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
}
.volume {
  -webkit-appearance: none;
  appearance: none;
  width: 96px;
  height: 14px;
  background: transparent;
  cursor: pointer;
}
.volume::-webkit-slider-runnable-track {
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--violet-ink) var(--v), var(--rule-strong) var(--v));
}
.volume::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 10px;
  height: 10px;
  margin-top: -4px;
  border-radius: 50%;
  background: var(--violet-ink);
}
.clip {
  flex: none;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: var(--ink-faint);
  opacity: 0;
  transition: opacity 0.2s var(--ease), color 0.2s var(--ease), transform 0.25s var(--ease);
}
.keep {
  flex: none;
  display: flex;
  align-items: center;
}
.now:hover .clip,
.clip:focus-visible,
.now:hover .keep :deep(.press),
.keep :deep(.press.pressed),
.keep :deep(.press:focus-visible) {
  opacity: 1;
}
.keep :deep(.press) {
  opacity: 0;
  transition: opacity 0.2s var(--ease);
}
.clip:hover {
  color: var(--violet-ink);
  background: var(--violet-wash);
  transform: rotate(-8deg) scale(1.08);
}
</style>
