<script setup>
// 开场（每天第一次）：水彩慢慢晕开，钢笔写下 Violet → 泰尔西斯文字副署 → 打字机译出问候。任意键或点击跳过。
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { sound } from '../sound.js'
import Wordmark from './Wordmark.vue'
import Nunkish from './Nunkish.vue'
import HeroBackdrop from './HeroBackdrop.vue'

const emit = defineEmits(['done'])
const GREETING = '「今天的信，我替你写好了。」'
const typed = ref(0)
const leaving = ref(false)
const timers = []
const later = (fn, ms) => timers.push(setTimeout(fn, ms))

function finish() {
  if (leaving.value) return
  leaving.value = true
  later(() => emit('done'), 650)
}

onMounted(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduced) {
    typed.value = GREETING.length
    later(finish, 900)
  } else {
    later(() => {
      sound.typing(GREETING.length, 0.055)
      const tick = () => {
        typed.value += 1
        if (typed.value < GREETING.length) later(tick, 55)
      }
      tick()
    }, 2350)
    later(finish, 4300)
  }
  window.addEventListener('keydown', finish, { once: true })
})
onBeforeUnmount(() => {
  timers.forEach(clearTimeout)
  window.removeEventListener('keydown', finish)
})
</script>

<template>
  <div class="intro" :class="{ leaving }" @click="finish">
    <HeroBackdrop class="intro-hero" strength="full" />
    <div class="stage">
      <Wordmark :height="150" animate :delay="0.15" />
      <Nunkish class="sig" text="violet evergarden" :size="26" animate :speed="0.045" :delay="1.45" />
      <p class="greeting title-cn">
        <span>{{ GREETING.slice(0, typed) }}</span><span class="caret" :class="{ hide: typed >= GREETING.length }" />
      </p>
    </div>
    <p class="skip faint">点击或按任意键继续</p>
  </div>
</template>

<style scoped>
.intro {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  background: var(--paper);
  cursor: pointer;
  transition: opacity 0.6s var(--ease), transform 0.6s var(--ease);
}
.intro::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(60% 50% at 50% 45%, var(--violet-wash), transparent 70%);
}
.leaving {
  opacity: 0;
  transform: scale(1.02);
  pointer-events: none;
}
.intro-hero :deep(img) {
  animation: wash 3.2s 0.2s var(--ease) both;
}
@keyframes wash {
  from {
    opacity: 0;
    filter: blur(6px) saturate(0.4);
    transform: scale(1.04);
  }
}
@media (min-width: 1081px) {
  .stage {
    margin-right: min(26vw, 340px);
  }
}
.stage {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 18px;
}
.sig {
  color: var(--gold);
}
.greeting {
  min-height: 1.6em;
  margin: 18px 0 0;
  font-size: 21px;
  letter-spacing: 0.16em;
  color: var(--ink-soft);
}
.caret {
  display: inline-block;
  width: 2px;
  height: 1.1em;
  margin-left: 3px;
  vertical-align: -0.15em;
  background: var(--violet-ink);
  animation: blink 0.8s steps(1) infinite;
}
.caret.hide {
  opacity: 0;
  animation: none;
}
.skip {
  position: absolute;
  bottom: 36px;
  font-size: 12px;
  letter-spacing: 0.2em;
  opacity: 0;
  animation: appear 0.6s 1.6s forwards;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
@keyframes appear {
  to {
    opacity: 0.8;
  }
}
</style>
