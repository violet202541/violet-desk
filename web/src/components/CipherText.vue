<script setup>
// 泰尔西斯密写：遮信时，字迹像被水洇开一样逐行化掉，再用钢笔一笔一笔写成泰尔西斯文字；掀开时反过来。
// 两种用法：
//   独立：<CipherText :text :veiled />，自己就是那段文字；
//   覆盖：传 target（一个 textarea），叠在它上面，遮着时还能接着写，新字直接以密文出现。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { draw, escapeHtml, plan } from '../cipher.js'

const props = defineProps({
  text: { type: String, default: '' },
  veiled: { type: Boolean, default: false },
  target: { type: Object, default: null }, // a textarea to lie over
  clamp: { type: Number, default: 0 }, // show at most this many lines (the mailbox cards)
  ruled: { type: Number, default: 0 }, // on ruled paper: px above each line's bottom where the letters sit
})

const root = ref(null)
const mirror = ref(null)
const canvas = ref(null)
const probe = ref(null)
const phase = ref(props.veiled ? 'veiled' : 'plain') // plain | veiling | veiled | unveiling
const box = ref({})

const chars = computed(() => Array.from(props.text || ''))
// Every visible character gets its own span so it can be measured; newlines stay plain text.
const html = computed(() => {
  let out = ''
  for (const c of chars.value) out += c === '\n' ? '\n' : `<span>${escapeHtml(c)}</span>`
  return out + '​'
})

const NL = '\n'
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
let born = [] // per character: when its pen starts writing (ms clock); 0 = written long ago
let words = []
let boxes = []
let frame = 0
let timer = 0
let observer = null

function syncOverlay() {
  // The ink the words fade from: the colour the text is written in here (never the hidden textarea's).
  if (root.value) root.value.style.setProperty('--c', getComputedStyle(root.value).color)
  const el = props.target
  if (!el) return
  const style = getComputedStyle(el)
  box.value = {
    left: el.offsetLeft + 'px',
    top: el.offsetTop + 'px',
    width: el.offsetWidth + 'px',
    height: el.offsetHeight + 'px',
    font: style.font,
    letterSpacing: style.letterSpacing,
    padding: style.padding,
    textIndent: style.textIndent,
  }
}

function measure() {
  const el = mirror.value
  const cv = canvas.value
  if (!el || !cv) return
  const width = el.clientWidth
  const height = props.clamp ? el.clientHeight : el.scrollHeight
  const dpr = window.devicePixelRatio || 1
  cv.width = Math.ceil(width * dpr)
  cv.height = Math.ceil(height * dpr)
  cv.style.width = width + 'px'
  cv.style.height = height + 'px'
  const spans = el.children
  const style = getComputedStyle(el)
  const fontSize = parseFloat(style.fontSize) || 16
  const leading = parseFloat(style.lineHeight) || fontSize * 1.8
  boxes = []
  let span = 0
  chars.value.forEach((c, i) => {
    if (c === NL) return
    const s = spans[span++]
    if (!s) return
    if (props.clamp && s.offsetTop + s.offsetHeight > height + 1) return
    boxes.push({ x: s.offsetLeft, y: s.offsetTop, h: s.offsetHeight, char: c, index: i, el: s })
  })
  // Group the characters into the lines the browser wrapped them into.
  const tops = [...new Set(boxes.map((b) => b.y))].sort((a, b) => a - b)
  const step = Math.min(70, 760 / Math.max(1, tops.length))
  const lines = tops.map((top, n) => {
    const own = boxes.filter((b) => b.y === top)
    const lastIndex = own[own.length - 1].index
    const after = chars.value[lastIndex + 1]
    return {
      n,
      chars: own.map((b) => ({ char: b.char, index: b.index })),
      top: top + own[0].h / 2 - leading / 2,
      height: leading,
      width,
      last: after === undefined || after === NL,
    }
  })
  // The ink runs line by line, left to right; the pen follows the same way.
  const delays = []
  for (const b of boxes) {
    b.line = tops.indexOf(b.y)
    b.delay = b.line * step + (b.x / Math.max(1, width)) * 320
    delays[b.index] = b.delay
    b.el.style.setProperty('--d', Math.round(b.delay) + 'ms')
  }
  words = plan(lines, { fontSize, ruled: props.ruled })
  for (const w of words) {
    w.born = w.indexes.reduce((m, i) => Math.max(m, born[i] || 0), 0)
    w.delay = w.indexes.reduce((m, i) => Math.min(m, delays[i] ?? m), Infinity)
  }
  render()
}

function render() {
  cancelAnimationFrame(frame)
  const cv = canvas.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, cv.width, cv.height)
  if (phase.value === 'plain') return
  const fontSize = parseFloat(getComputedStyle(mirror.value).fontSize) || 16
  const busy = draw(ctx, words, {
    color: getComputedStyle(probe.value).color,
    weight: Math.min(1.15, Math.max(0.8, fontSize / 17)),
    dpr: window.devicePixelRatio || 1,
    at: performance.now(),
    born: (w) => w.born,
  })
  if (busy) frame = requestAnimationFrame(render)
}

function veil() {
  clearTimeout(timer)
  if (reduced()) {
    born = []
    phase.value = 'veiled'
    return nextTick(measure)
  }
  phase.value = 'veiling'
  nextTick(() => {
    measure()
    const start = performance.now() + 460 // the ink has begun to run before the pen comes
    born = []
    for (const b of boxes) born[b.index] = start + b.delay
    // A word starts when its first character's ink has run.
    for (const w of words) for (const i of w.indexes) born[i] = start + (w.delay === Infinity ? 0 : w.delay)
    measure()
    const last = boxes.reduce((m, b) => Math.max(m, b.delay), 0)
    timer = setTimeout(() => phase.value === 'veiling' && (phase.value = 'veiled'), last + 1400)
  })
}

function unveil() {
  clearTimeout(timer)
  if (reduced()) {
    phase.value = 'plain'
    return nextTick(render)
  }
  phase.value = 'unveiling'
  nextTick(() => {
    measure()
    const last = boxes.reduce((m, b) => Math.max(m, b.delay), 0)
    timer = setTimeout(() => {
      if (phase.value !== 'unveiling') return
      phase.value = 'plain'
      render()
    }, last + 650)
  })
}

watch(() => props.veiled, (v) => (v ? veil() : unveil()))

// Typing while veiled: the characters that just came in are written fresh, the rest stay as they were.
watch(chars, (now, before) => {
  if (phase.value !== 'plain') {
    let p = 0
    while (p < now.length && p < before.length && now[p] === before[p]) p++
    let s = 0
    while (s < now.length - p && s < before.length - p && now[now.length - 1 - s] === before[before.length - 1 - s]) s++
    const added = now.length - p - s
    const removed = before.length - p - s
    const t = performance.now()
    const fresh = Array.from({ length: added }, (_, k) => t + k * 45)
    born.splice(p, removed, ...fresh)
  }
  nextTick(() => {
    syncOverlay()
    nextTick(measure)
  })
})

// The textarea underneath shows its own text only while the page is plain.
watch(
  [phase, () => props.target],
  ([p, el], [, old]) => {
    if (old && old !== el) old.classList.remove('cipher-hidden')
    el?.classList.toggle('cipher-hidden', p !== 'plain')
  },
  { immediate: true },
)

onMounted(() => {
  syncOverlay()
  observer = new ResizeObserver(() => {
    syncOverlay()
    nextTick(measure)
  })
  observer.observe(props.target || root.value)
  document.fonts?.ready.then(() => nextTick(measure))
  nextTick(measure)
})
watch(() => props.target, (el, old) => {
  if (old) observer?.unobserve(old)
  if (el) observer?.observe(el)
  syncOverlay()
  nextTick(measure)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  clearTimeout(timer)
  observer?.disconnect()
  props.target?.classList.remove('cipher-hidden')
})
</script>

<template>
  <span ref="root" class="cipher" :class="[phase, { overlay: target, clamped: clamp }]"
    :style="target ? box : clamp ? { '--clamp': clamp } : null">
    <span ref="mirror" class="cipher-text" v-html="html" />
    <canvas ref="canvas" class="cipher-ink" aria-hidden="true" />
    <span ref="probe" class="probe" aria-hidden="true" />
  </span>
</template>

<style scoped>
/* Spans throughout, so it can sit inside a button (the mailbox cards). */
.cipher {
  position: relative;
  display: block;
}
.cipher.overlay {
  position: absolute;
  z-index: 1;
  pointer-events: none;
}
.cipher-text {
  display: block;
  overflow-wrap: break-word;
}
.overlay .cipher-text {
  white-space: pre-wrap;
  height: 100%;
  font: inherit;
  letter-spacing: inherit;
  color: transparent;
}
.clamped .cipher-text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: var(--clamp);
  overflow: hidden;
}
.cipher-ink {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  transition: opacity 0.5s var(--ease), filter 0.5s var(--ease);
}
.unveiling .cipher-ink {
  opacity: 0;
  filter: blur(3px);
}
.probe {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
  color: var(--cipher-ink, color-mix(in srgb, var(--violet) 66%, var(--ink)));
}
/* The ink runs: each character spreads and fades, line by line, left to right. */
.veiling .cipher-text :deep(span) {
  animation: bleed 0.62s ease-in var(--d, 0ms) both;
}
.veiled .cipher-text {
  color: transparent;
}
.veiled .cipher-text :deep(span) {
  color: transparent;
}
/* Lifting the veil: the words gather back out of the wash. */
.unveiling .cipher-text :deep(span) {
  animation: bleed 0.55s ease-out var(--d, 0ms) reverse both;
}
@keyframes bleed {
  0% {
    color: var(--c);
    text-shadow: 0 0 0 transparent;
  }
  45% {
    color: color-mix(in srgb, var(--c) 30%, transparent);
    text-shadow: 0 0 4px color-mix(in srgb, var(--c) 50%, transparent), 1px 1px 7px color-mix(in srgb, var(--violet-ink) 25%, transparent);
  }
  100% {
    color: transparent;
    text-shadow: 0 0 11px transparent;
  }
}
</style>

<style>
/* The textarea under a veil keeps its caret and selection but not its letters. */
.cipher-hidden {
  color: transparent !important;
  -webkit-text-fill-color: transparent;
}
</style>
