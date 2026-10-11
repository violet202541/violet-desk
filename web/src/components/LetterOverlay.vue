<script setup>
// 拆信：在书桌上点了信封后，信封浮到眼前，火漆碎开、封口翻起、信纸抽出，展开阅读。
// 也用于在信箱和邮戳簿里重读旧信（直接展开信纸）。
import { computed, ref, watch } from 'vue'
import { store, updateLetter } from '../store.js'
import { sound } from '../sound.js'
import { trapFocus } from '../dialog.js'
import LetterSheet from './LetterSheet.vue'
import SealImpression from './SealImpression.vue'
import Nunkish from './Nunkish.vue'

const props = defineProps({ ready: { type: Boolean, default: true } })
const stage = ref('sealed') // sealed | opening | reading
const panel = ref(null)
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const sealed = computed(() => props.ready && store.letters.envelope)
const reading = computed(() => store.letters.reading)
const visible = computed(() => sealed.value || reading.value)
const dateText = computed(() => {
  const letter = store.letters.envelope || store.letters.reading
  if (!letter) return ''
  const [, m, d] = letter.date.split('-').map(Number)
  return `${m} 月 ${d} 日`
})

// The envelope was already chosen on the desk: let it float in, then open it.
watch(sealed, (letter) => {
  if (!letter) return
  stage.value = 'sealed'
  setTimeout(open, reduced() ? 0 : 520)
})

function open() {
  if (stage.value !== 'sealed') return
  stage.value = 'opening'
  sound.carriage()
  const letter = store.letters.envelope
  setTimeout(() => {
    store.letters.reading = letter
    store.letters.envelope = null
    stage.value = 'reading'
    updateLetter(letter.date, { opened: true })
  }, reduced() ? 0 : 1350)
}

function close() {
  store.letters.reading = null
  store.letters.envelope = null
}

trapFocus(panel, close)
</script>

<template>
  <Transition name="letter-fade">
    <div v-if="visible" class="backdrop" @mousedown.self="reading ? close() : null">
      <div v-if="sealed && !reading" class="delivery" :class="stage">
        <p class="eyebrow">A letter has arrived</p>
        <h2 class="title-cn">今日来信 · {{ dateText }}</h2>
        <button class="envelope" title="拆开这封信" @click="open">
          <span class="back" />
          <span class="paper-out"><Nunkish text="dear you" :size="18" /></span>
          <span class="front" />
          <span class="flap" />
          <span class="seal"><SealImpression color="violet" motif="monogram" :size="80" /></span>
          <span class="to title-cn">致 · 你</span>
        </button>
      </div>

      <div v-else-if="reading" ref="panel" class="reader" role="dialog" aria-modal="true" aria-label="来信">
        <button class="icon-btn close" title="收进信箱 (Esc)" @click="close">
          <svg viewBox="0 0 12 12" width="14" height="14"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke="currentColor" stroke-width="1.3" /></svg>
        </button>
        <LetterSheet :letter="reading" @close="close" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 70;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--paper) 72%, rgba(30, 20, 40, 0.5));
  backdrop-filter: blur(6px);
  overflow-y: auto;
  padding: 40px 0;
}
.delivery {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}
.delivery h2 {
  margin: 0 0 18px;
  font-weight: 400;
  font-size: 26px;
}
.eyebrow {
  margin: 0;
}
.envelope {
  position: relative;
  width: 420px;
  height: 270px;
  perspective: 900px;
  animation: float-in 1s cubic-bezier(0.2, 0.9, 0.3, 1.1) both, bob 4s 1s ease-in-out infinite;
}
.back,
.front,
.flap,
.paper-out {
  position: absolute;
  left: 0;
  right: 0;
}
.back {
  inset: 0;
  background: linear-gradient(160deg, var(--paper-deep), var(--sheet));
  border: 1px solid var(--rule-strong);
  border-radius: 6px;
  box-shadow: var(--shadow-lift);
}
/* The front pocket: everything below the V of the open flap, so the letter slides out from inside. */
.front {
  inset: 0;
  z-index: 2;
  border-radius: 6px;
  background:
    linear-gradient(to top right, transparent calc(50% - 1px), var(--rule-strong) 50%, transparent calc(50% + 1px)) left bottom / 50% 100% no-repeat,
    linear-gradient(to top left, transparent calc(50% - 1px), var(--rule-strong) 50%, transparent calc(50% + 1px)) right bottom / 50% 100% no-repeat,
    linear-gradient(160deg, var(--sheet-raised), var(--paper-deep));
  clip-path: polygon(0 0, 50% 58%, 100% 0, 100% 100%, 0 100%);
}
.flap {
  top: 0;
  height: 58%;
  background: linear-gradient(170deg, var(--sheet-raised), var(--paper-deep));
  clip-path: polygon(0 0, 100% 0, 50% 100%);
  transform-origin: top;
  filter: drop-shadow(0 2px 2px rgba(60, 40, 20, 0.15));
  transition: transform 0.7s var(--ease);
  z-index: 3;
}
.paper-out {
  left: 24px;
  right: 24px;
  top: 14px;
  height: 230px;
  display: grid;
  justify-items: center;
  padding-top: 26px;
  background: var(--sheet-raised);
  border: 1px solid var(--rule);
  color: var(--violet-ink);
  transition: transform 0.7s 0.55s var(--ease);
  z-index: 1;
}
.seal {
  position: absolute;
  left: 50%;
  top: 58%;
  transform: translate(-50%, -50%);
  z-index: 4;
  transition: transform 0.45s var(--ease), opacity 0.45s var(--ease);
}
.seal-v {
  font-size: 40px;
  transform: translate(1px, 4px);
  text-shadow: 0 -1px 0 rgba(0, 0, 0, 0.35), 0 1px 0 rgba(255, 255, 255, 0.25);
}
.to {
  position: absolute;
  right: 26px;
  bottom: 18px;
  z-index: 4;
  color: var(--ink-soft);
  font-size: 15px;
  letter-spacing: 0.3em;
}
.opening .seal {
  transform: translate(-50%, -50%) scale(1.25) rotate(-20deg);
  opacity: 0;
}
.opening .flap {
  transform: rotateX(180deg);
  z-index: 0;
  transition: transform 0.7s var(--ease), z-index 0s 0.35s;
}
.opening .paper-out {
  transform: translateY(-150px);
}
.opening .envelope {
  animation: none;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 30px;
}
.reader {
  position: relative;
  width: min(760px, calc(100vw - 80px));
  margin: auto;
  animation: unfold 0.6s var(--ease) both;
}
.close {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;
}
@keyframes float-in {
  from {
    opacity: 0;
    transform: translate(-40px, -80px) rotate(-14deg) scale(0.9);
  }
}
@keyframes bob {
  50% {
    transform: translateY(-6px) rotate(0.6deg);
  }
}
@keyframes unfold {
  from {
    opacity: 0;
    transform: translateY(40px) scaleY(0.92);
  }
}
.letter-fade-enter-active,
.letter-fade-leave-active {
  transition: opacity 0.4s var(--ease);
}
.letter-fade-enter-from,
.letter-fade-leave-to {
  opacity: 0;
}
</style>
