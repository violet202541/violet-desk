<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { player, current, currentLine, seek, coverOf } from '../player.js'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import Nunkish from './Nunkish.vue'
import EmptyState from './EmptyState.vue'

const scroller = ref(null)
let userScrollUntil = 0
const lines = computed(() => player.lyrics)
const chars = computed(() => {
  const line = lines.value[currentLine.value]
  return line ? Array.from(line.text) : []
})

function center(smooth = true) {
  const el = scroller.value?.querySelector('.line.on')
  if (!el || Date.now() < userScrollUntil) return
  scroller.value.scrollTo({ top: el.offsetTop - scroller.value.clientHeight * 0.42, behavior: smooth ? 'smooth' : 'auto' })
}

watch(currentLine, () => nextTick(center))
watch(
  () => player.sheet,
  (open) => open && nextTick(() => center(false)),
)
watch(
  () => current.value?.id,
  () => {
    userScrollUntil = 0
    nextTick(() => scroller.value?.scrollTo({ top: 0 }))
  },
)
</script>

<template>
  <Transition name="sheet">
    <section v-if="player.sheet && current" class="lyrics-sheet" @keydown.esc="player.sheet = false">
      <div class="wash" :style="{ backgroundImage: current.has_cover ? `url(${coverOf(current)})` : 'none' }" />
      <button class="icon-btn close" title="收起 (Esc)" @click="player.sheet = false"><Icon name="down" :size="22" /></button>

      <div class="layout">
        <aside class="photo">
          <div class="pasted">
            <span class="tape left" /><span class="tape right" />
            <CoverArt :src="coverOf(current)" size="100%" :seed="current.title" :radius="1" />
          </div>
          <h2 class="title-text">{{ current.title }}</h2>
          <p class="artist">{{ current.artist || '佚名' }}</p>
          <p v-if="current.album" class="album faint">《{{ current.album }}》</p>
          <Nunkish class="sig" :text="(current.artist || 'violet').replace(/[^a-z0-9 ]/gi, '') || 'violet'" :size="16" />
        </aside>

        <div ref="scroller" class="scroller" @wheel="userScrollUntil = Date.now() + 3000">
          <div v-if="lines.length" class="lines">
            <p v-for="(line, i) in lines" :key="i" class="line" :class="{ on: i === currentLine, past: i < currentLine }"
              @click="seek(line.time)">
              <span v-if="i === currentLine" :key="'typed-' + i" class="text typed">
                <span v-for="(c, j) in chars" :key="j" :style="{ animationDelay: Math.min(j * 0.035, 0.9) + 's' }">{{ c }}</span>
              </span>
              <span v-else class="text">{{ line.text || '♪' }}</span>
              <span v-if="line.translation" class="translation">{{ line.translation }}</span>
            </p>
          </div>
          <div v-else-if="player.plain.length" class="lines plain">
            <p v-for="(text, i) in player.plain" :key="i" class="line">{{ text }}</p>
          </div>
          <EmptyState v-else-if="!player.lyricsLoading" script="no words" title="这封信没有附上歌词"
            hint="下载时开启「内嵌歌词」，或在歌曲旁放一个同名 .lrc 文件。" />
        </div>
      </div>
    </section>
  </Transition>
</template>

<style scoped>
.lyrics-sheet {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: var(--paper);
  overflow: hidden;
}
.wash {
  position: absolute;
  inset: -80px;
  background-size: cover;
  background-position: center;
  filter: blur(80px) saturate(1.3);
  opacity: 0.22;
}
.close {
  position: absolute;
  top: 18px;
  right: 22px;
  z-index: 2;
}
.layout {
  position: relative;
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) 1.2fr;
  gap: 64px;
  height: 100%;
  padding: 56px 72px 0;
  max-width: 1400px;
  margin: 0 auto;
}
.photo {
  align-self: center;
  justify-self: end;
  width: min(360px, 100%);
  margin-bottom: 72px;
}
.pasted {
  position: relative;
  padding: 12px 12px 44px;
  background: var(--sheet-raised);
  box-shadow: var(--shadow-lift);
  transform: rotate(-2.2deg);
}
.tape {
  position: absolute;
  top: -12px;
  width: 86px;
  height: 26px;
  background: rgba(222, 205, 160, 0.55);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  z-index: 1;
}
.tape.left {
  left: -18px;
  transform: rotate(-32deg);
}
.tape.right {
  right: -18px;
  transform: rotate(28deg);
}
h2 {
  margin: 30px 0 4px;
  font-size: 28px;
  font-weight: 400;
  line-height: 1.3;
}
.artist {
  margin: 0;
  font-size: 16px;
  color: var(--ink-soft);
}
.album {
  margin: 2px 0 0;
  font-size: 14px;
}
.sig {
  margin-top: 16px;
  color: var(--gold);
}
.scroller {
  overflow-y: auto;
  padding: 30vh 12px 36vh 0;
  mask-image: linear-gradient(transparent, #000 18%, #000 78%, transparent);
  scrollbar-width: none;
}
.scroller::-webkit-scrollbar {
  display: none;
}
.lines {
  display: grid;
  gap: 4px;
}
.line {
  margin: 0;
  padding: 10px 14px;
  border-radius: var(--radius);
  font-size: 19px;
  line-height: 1.6;
  color: var(--ink-faint);
  cursor: pointer;
  transition: color 0.4s var(--ease), background 0.3s var(--ease);
}
.line:hover {
  background: var(--violet-wash);
}
.line.past {
  color: color-mix(in srgb, var(--ink-faint) 80%, transparent);
}
.line .text {
  display: block;
}
.line.on .text {
  font-family: var(--font-title);
  font-size: 30px;
  line-height: 1.45;
  color: var(--violet-ink);
}
.typed span {
  opacity: 0;
  animation: type 0.05s steps(1) forwards;
}
@keyframes type {
  to {
    opacity: 1;
  }
}
.translation {
  display: block;
  font-size: 15px;
  margin-top: 2px;
}
.line.on .translation {
  color: var(--ink-soft);
}
.plain .line {
  cursor: default;
  color: var(--ink-soft);
}
.sheet-enter-active,
.sheet-leave-active {
  transition: transform 0.55s var(--ease), opacity 0.4s var(--ease);
}
.sheet-enter-from,
.sheet-leave-to {
  transform: translateY(40px);
  opacity: 0;
}
</style>
