<script setup>
// 压花（收藏）：一朵五瓣的堇菜花。没压时只是铅笔描的轮廓；压下去，花瓣一片片摊平、染上颜色。
import { computed, ref } from 'vue'
import { isPressed, togglePress } from '../shelf.js'

const props = defineProps({
  track: { type: Object, default: null },
  size: { type: Number, default: 18 },
})
// Violets have two upper petals, two at the sides and a broad lower one.
const PETALS = [
  { rot: -28, d: 5.4, rx: 3.1, ry: 4.6, tone: 'deep' },
  { rot: 28, d: 5.4, rx: 3.1, ry: 4.6, tone: 'deep' },
  { rot: -100, d: 5, rx: 2.8, ry: 4.2, tone: 'mid' },
  { rot: 100, d: 5, rx: 2.8, ry: 4.2, tone: 'mid' },
  { rot: 180, d: 5.6, rx: 3.6, ry: 4.9, tone: 'light' },
]
const pressed = computed(() => isPressed(props.track))
const fresh = ref(false)

function click(event) {
  if (!props.track) return
  if (!pressed.value) {
    fresh.value = true
    setTimeout(() => (fresh.value = false), 1000)
  }
  togglePress(props.track, event.currentTarget)
}
</script>

<template>
  <button class="press" :class="{ pressed, fresh }" :disabled="!track"
    :title="pressed ? '已压成花（收藏）· 点一下取出来' : '压一朵花（收藏）'" :aria-label="pressed ? '取消收藏' : '收藏'"
    :aria-pressed="pressed" :style="{ '--s': size + 12 + 'px' }" @click.stop="click">
    <svg :width="size" :height="size" viewBox="0 0 24 24" aria-hidden="true">
      <g class="flower">
        <g v-for="(p, i) in PETALS" :key="i" :transform="`rotate(${p.rot} 12 12)`">
          <ellipse class="petal" :class="p.tone" :style="{ '--i': i }" cx="12" :cy="12 - p.d" :rx="p.rx" :ry="p.ry" />
        </g>
        <path class="vein" d="M12 13.2v4.6M10.6 13l-1.2 3.4M13.4 13l1.2 3.4" />
        <circle class="heart" cx="12" cy="12" r="1.7" />
      </g>
    </svg>
  </button>
</template>

<style scoped>
.press {
  display: inline-grid;
  place-items: center;
  width: var(--s);
  height: var(--s);
  border-radius: 50%;
  color: var(--ink-faint);
  transition: color 0.2s var(--ease), background 0.2s var(--ease), transform 0.25s var(--ease);
}
.press:hover:not(:disabled) {
  color: var(--violet-ink);
  background: var(--violet-wash);
  transform: rotate(-10deg);
}
svg {
  overflow: visible;
}
.flower {
  transform-origin: 12px 12px;
  transition: transform 0.5s var(--ease);
}
.petal {
  transform-origin: 12px 12px;
  fill: transparent;
  stroke: currentColor;
  stroke-width: 1.3;
  transition: fill 0.4s var(--ease), stroke 0.4s var(--ease);
}
.vein,
.heart {
  fill: none;
  stroke: currentColor;
  stroke-width: 1;
  opacity: 0.6;
}
/* Pressed: flat, a little turned, coloured in. */
.pressed .flower {
  transform: rotate(-14deg) scale(1.02, 0.94);
}
.pressed .petal {
  stroke: color-mix(in srgb, var(--wax-b) 60%, transparent);
  stroke-width: 0.6;
}
.pressed .deep {
  fill: #5b3d93;
}
.pressed .mid {
  fill: #7d5fb8;
}
.pressed .light {
  fill: #a58bd6;
}
.pressed .vein {
  stroke: #f3e7c8;
  opacity: 0.8;
}
.pressed .heart {
  fill: #e0b54e;
  stroke: none;
  opacity: 1;
}
:root[data-theme='dark'] .pressed .deep {
  fill: #8f6fd0;
}
/* The moment of pressing: petals open out one after another and settle flat. */
.fresh .petal {
  animation: unfold 0.7s cubic-bezier(0.25, 1.4, 0.45, 1) backwards;
  animation-delay: calc(var(--i) * 0.06s);
}
.fresh .flower {
  animation: press-down 0.8s cubic-bezier(0.3, 1.5, 0.45, 1);
}
@keyframes unfold {
  from {
    opacity: 0;
    transform: scale(0.3);
  }
}
@keyframes press-down {
  0% {
    transform: scale(1.5) rotate(20deg);
  }
  55% {
    transform: scale(0.85, 0.75) rotate(-18deg);
  }
  100% {
    transform: rotate(-14deg) scale(1.02, 0.94);
  }
}
@media (prefers-reduced-motion: reduce) {
  .fresh .petal,
  .fresh .flower {
    animation: none;
  }
}
</style>
