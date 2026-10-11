<script setup>
// 光阴：铺在背景画上的一层光与天气。
// 白天有一道随时辰变色的斜光和光里的浮尘；夜里是烛火的微光和几点萤火。
// 回信上贴了天气邮票，窗外就跟着下雨、落雪、起风或起雾。设置里可以关掉，系统「减少动态效果」时只留静态的光。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { store, isDark } from '../store.js'
import { desk } from '../desk.js'
import { isoDate } from '../format.js'

const props = defineProps({
  strength: { type: String, default: 'full' }, // full | soft | whisper
})

const canvas = ref(null)
const flash = ref(false)
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
const moving = computed(() => store.settings?.ambient !== false && !reduced.matches)
const dark = computed(() => {
  void store.settings?.theme
  return isDark()
})

// Today's weather stamp: the one on the sheet being written wins, so choosing a stamp changes the sky at once.
const weather = computed(() => {
  const today = isoDate()
  if (desk.writing?.date === today && store.view === 'write') return desk.writing.weather || ''
  return desk.today?.reply?.weather || ''
})

const hour = ref(new Date().getHours())
const hourTimer = setInterval(() => (hour.value = new Date().getHours()), 5 * 60 * 1000)
// The colour of the light through the window, by the hour.
const tint = computed(() => {
  const h = hour.value
  if (h < 5 || h >= 21) return 'night'
  if (h < 9) return 'dawn'
  if (h < 15) return 'noon'
  if (h < 18) return 'golden'
  return 'dusk'
})
const dim = computed(() => ['overcast', 'rain', 'storm', 'fog', 'snow'].includes(weather.value))

// ------------------------------------------------------------------ particles

let ctx = null
let raf = 0
let parts = []
let width = 0
let height = 0
let last = 0
let observer = null
let nextFlash = 0

const rand = (a, b) => a + Math.random() * (b - a)

function kind() {
  const w = weather.value
  if (w === 'rain' || w === 'storm') return 'rain'
  if (w === 'snow') return 'snow'
  if (w === 'wind') return 'petal'
  if (w === 'fog') return 'fog'
  return dark.value ? 'firefly' : 'mote'
}

function spawn(type, anywhere = true) {
  // Most of the life sits on the right, where the window and the painting are; the words stay clear.
  const x = width * (type === 'fog' ? rand(-0.3, 0.9) : rand(0.38, 1.02))
  const y = anywhere ? rand(0, height) : type === 'mote' || type === 'firefly' ? height + 10 : -20
  switch (type) {
    case 'rain':
      return { type, x, y, len: rand(10, 22), speed: rand(520, 760), alpha: rand(0.12, 0.3) }
    case 'snow':
      return { type, x, y, r: rand(1, 2.8), speed: rand(18, 46), sway: rand(0, Math.PI * 2), alpha: rand(0.45, 0.9) }
    case 'petal':
      return { type, x: anywhere ? x : rand(-40, width * 0.5), y: anywhere ? y : rand(-30, height * 0.6), r: rand(3, 6),
        vx: rand(60, 120), vy: rand(10, 34), spin: rand(0, Math.PI * 2), vs: rand(-2.5, 2.5), alpha: rand(0.5, 0.85) }
    case 'fog':
      return { type, x, y: rand(height * 0.25, height), w: rand(260, 520), h: rand(60, 120), vx: rand(6, 16), alpha: rand(0.05, 0.11) }
    case 'firefly':
      return { type, x, y, r: rand(1.2, 2.4), vx: rand(-8, 8), vy: rand(-14, -4), phase: rand(0, 6.3), alpha: 0 }
    default:
      return { type: 'mote', x, y, r: rand(0.6, 1.8), vx: rand(-4, 6), vy: rand(-9, -2), phase: rand(0, 6.3), alpha: 0 }
  }
}

function population(type) {
  const scale = { full: 1, soft: 0.6, whisper: 0.35 }[props.strength] || 1
  const base = { rain: 110, snow: 70, petal: 12, fog: 5, firefly: 12, mote: 40 }[type]
  return Math.round(base * scale * Math.min(1.4, width / 1100))
}

function reset() {
  const type = kind()
  parts = Array.from({ length: population(type) }, () => spawn(type))
}

function resize() {
  const el = canvas.value
  if (!el) return
  const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
  width = el.clientWidth
  height = el.clientHeight
  el.width = Math.round(width * ratio)
  el.height = Math.round(height * ratio)
  ctx = el.getContext('2d')
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  reset()
}

function draw(now) {
  raf = requestAnimationFrame(draw)
  if (document.hidden || !ctx) return
  // About 30 frames a second is plenty for drifting dust and keeps the fan quiet.
  if (now - last < 32) return
  const dt = Math.min(0.08, (now - last) / 1000)
  last = now
  ctx.clearRect(0, 0, width, height)
  const night = dark.value
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i]
    switch (p.type) {
      case 'rain': {
        p.x -= p.speed * 0.18 * dt
        p.y += p.speed * dt
        ctx.strokeStyle = night ? `rgba(170,190,230,${p.alpha})` : `rgba(90,110,150,${p.alpha * 0.8})`
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(p.x, p.y)
        ctx.lineTo(p.x + p.len * 0.18, p.y - p.len)
        ctx.stroke()
        if (p.y > height + 20) parts[i] = spawn('rain', false)
        break
      }
      case 'snow': {
        p.sway += dt
        p.x += Math.sin(p.sway) * 12 * dt
        p.y += p.speed * dt
        ctx.fillStyle = night ? `rgba(235,235,250,${p.alpha})` : `rgba(255,255,255,${p.alpha})`
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fill()
        if (!night) {
          ctx.strokeStyle = `rgba(140,150,175,${p.alpha * 0.35})`
          ctx.stroke()
        }
        if (p.y > height + 10) parts[i] = spawn('snow', false)
        break
      }
      case 'petal': {
        p.spin += p.vs * dt
        p.x += p.vx * dt
        p.y += (p.vy + Math.sin(p.spin) * 20) * dt
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.spin)
        ctx.scale(1, Math.abs(Math.cos(p.spin * 0.7)) * 0.6 + 0.4)
        ctx.fillStyle = night ? `rgba(196,170,236,${p.alpha})` : `rgba(126,92,180,${p.alpha * 0.75})`
        ctx.beginPath()
        ctx.ellipse(0, 0, p.r, p.r * 0.55, 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
        if (p.x > width + 30 || p.y > height + 30) parts[i] = spawn('petal', false)
        break
      }
      case 'fog': {
        p.x += p.vx * dt
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.w / 2)
        const c = night ? '200,190,220' : '255,252,245'
        g.addColorStop(0, `rgba(${c},${p.alpha * (night ? 0.8 : 2.2)})`)
        g.addColorStop(1, `rgba(${c},0)`)
        ctx.fillStyle = g
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.scale(1, p.h / p.w)
        ctx.translate(-p.x, -p.y)
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.w / 2, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
        if (p.x - p.w / 2 > width) {
          parts[i] = spawn('fog')
          parts[i].x = -p.w / 2
        }
        break
      }
      default: {
        // Dust in the sunbeam, or fireflies by the lamp: both drift up and breathe in and out.
        p.phase += dt * (p.type === 'firefly' ? 1.6 : 0.9)
        p.x += (p.vx + Math.sin(p.phase * 0.7) * 6) * dt
        p.y += p.vy * dt
        const breath = (Math.sin(p.phase) + 1) / 2
        p.alpha = Math.min(1, p.alpha + dt * 0.5)
        if (p.type === 'firefly') {
          const a = p.alpha * (0.15 + breath * 0.85)
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6)
          g.addColorStop(0, `rgba(255,214,140,${a})`)
          g.addColorStop(0.3, `rgba(240,180,90,${a * 0.35})`)
          g.addColorStop(1, 'rgba(240,180,90,0)')
          ctx.fillStyle = g
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2)
          ctx.fill()
        } else {
          ctx.fillStyle = `rgba(255,246,220,${p.alpha * (0.25 + breath * 0.6)})`
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
          ctx.fill()
        }
        if (p.y < -12 || p.x > width + 12 || p.x < width * 0.25) parts[i] = spawn(p.type, false)
      }
    }
  }
  // A storm lights the room now and then.
  if (weather.value === 'storm' && now > nextFlash) {
    nextFlash = now + rand(7000, 16000)
    if (last > 1000) {
      flash.value = true
      setTimeout(() => (flash.value = false), 420)
    }
  }
}

function start() {
  stop()
  if (!moving.value) {
    ctx?.clearRect(0, 0, width, height)
    return
  }
  last = performance.now()
  nextFlash = last + rand(4000, 9000)
  raf = requestAnimationFrame(draw)
}
function stop() {
  cancelAnimationFrame(raf)
  raf = 0
}

// A new sky (weather, day or night) starts afresh; a change of strength only adds or retires a few motes,
// so the dust already drifting never jumps when moving between pages.
watch([weather, dark], () => reset())
watch(() => props.strength, () => {
  const type = kind()
  const want = population(type)
  if (parts.length > want) parts.length = want
  while (parts.length < want) parts.push(spawn(type))
})
watch(moving, start)

onMounted(() => {
  resize()
  observer = new ResizeObserver(resize)
  observer.observe(canvas.value)
  start()
})
onBeforeUnmount(() => {
  stop()
  observer?.disconnect()
  clearInterval(hourTimer)
})
</script>

<template>
  <div class="ambience" :class="[strength, tint, { dark, dim, moving, flash }]" aria-hidden="true">
    <div class="beam" />
    <div class="lamp" />
    <canvas ref="canvas" />
  </div>
</template>

<style scoped>
.ambience {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
/* The window light: a soft diagonal shaft from the upper right. */
.beam {
  position: absolute;
  top: -20%;
  right: -10%;
  width: 70%;
  height: 140%;
  transform: rotate(18deg);
  transform-origin: top right;
  background: linear-gradient(100deg, transparent 8%, var(--beam) 38%, var(--beam) 52%, transparent 82%);
  mix-blend-mode: soft-light;
  opacity: 0.9;
  filter: blur(18px);
}
.moving .beam {
  animation: sway 18s ease-in-out infinite alternate;
}
@keyframes sway {
  from {
    transform: rotate(16deg) translateX(0);
    opacity: 0.75;
  }
  to {
    transform: rotate(20deg) translateX(-40px);
    opacity: 1;
  }
}
.dawn {
  --beam: rgba(232, 238, 255, 0.85);
}
.noon {
  --beam: rgba(255, 250, 232, 0.9);
}
.golden {
  --beam: rgba(255, 214, 150, 0.95);
}
.dusk {
  --beam: rgba(240, 170, 170, 0.8);
}
.night {
  --beam: rgba(180, 170, 230, 0.35);
}
.dim .beam {
  opacity: 0.35;
  filter: blur(26px) saturate(0.4);
}
.soft .beam {
  opacity: 0.6;
}
.whisper .beam {
  opacity: 0.35;
}
/* At night the only light is the lamp on her desk, breathing like a flame. */
.lamp {
  position: absolute;
  right: 8%;
  bottom: 6%;
  width: 46vw;
  height: 46vw;
  max-width: 640px;
  max-height: 640px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 190, 110, 0.16), rgba(255, 170, 90, 0.05) 45%, transparent 70%);
  opacity: 0;
  transform: translate(30%, 30%);
  transition: opacity 1.2s var(--ease);
}
.dark .lamp {
  opacity: 1;
}
.dark .beam {
  display: none;
}
.dark.moving .lamp {
  animation: flame 5.2s infinite;
}
.whisper .lamp {
  opacity: 0.4;
}
@keyframes flame {
  0%,
  100% {
    transform: translate(30%, 30%) scale(1);
    filter: brightness(1);
  }
  18% {
    transform: translate(30%, 30%) scale(1.03);
    filter: brightness(1.12);
  }
  31% {
    transform: translate(30%, 30%) scale(0.98);
    filter: brightness(0.92);
  }
  47% {
    transform: translate(30%, 30%) scale(1.02);
    filter: brightness(1.08);
  }
  64% {
    transform: translate(30%, 30%) scale(0.99);
    filter: brightness(0.96);
  }
  80% {
    transform: translate(30%, 30%) scale(1.04);
    filter: brightness(1.15);
  }
}
.flash::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(230, 225, 255, 0.22);
  animation: lightning 0.42s ease-out;
}
@keyframes lightning {
  0% {
    opacity: 0;
  }
  15% {
    opacity: 1;
  }
  30% {
    opacity: 0.2;
  }
  45% {
    opacity: 0.8;
  }
  100% {
    opacity: 0;
  }
}
</style>
