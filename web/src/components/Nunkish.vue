<script setup>
// 泰尔西斯文字：纯装饰，屏幕阅读器忽略。animate 时按书写顺序逐笔描出。
import { computed } from 'vue'
import { layout } from '../assets/nunkish.js'

const props = defineProps({
  text: { type: String, required: true },
  size: { type: Number, default: 22 },
  weight: { type: Number, default: 4.4 },
  animate: { type: Boolean, default: false },
  speed: { type: Number, default: 0.09 },
  delay: { type: Number, default: 0 },
  loop: { type: Boolean, default: false },
})

const data = computed(() => layout(props.text))
const strokes = computed(() => {
  let order = 0
  const items = []
  for (const g of data.value.glyphs) {
    for (const d of g.d) items.push({ type: 'path', d, x: g.x, order: order++ })
    for (const [cx, cy] of g.dots || []) items.push({ type: 'dot', cx: cx + g.x, cy, order: order++ })
  }
  return items
})
const total = computed(() => strokes.value.length * props.speed + 0.6)
const viewBox = computed(() => `-6 4 ${data.value.width + 12} 100`)
</script>

<template>
  <svg class="nunkish" :class="{ animate, loop }" :viewBox="viewBox" :height="size" :width="(size * (data.width + 12)) / 100"
    aria-hidden="true" :style="{ '--total': total + 's' }">
    <g fill="none" stroke="currentColor" :stroke-width="weight" stroke-linecap="round" stroke-linejoin="round">
      <template v-for="s in strokes" :key="s.order">
        <path v-if="s.type === 'path'" :d="s.d" :transform="`translate(${s.x} 0)`" pathLength="1"
          :style="{ animationDelay: delay + s.order * speed + 's' }" />
        <circle v-else :cx="s.cx" :cy="s.cy" :r="weight * 0.72" fill="currentColor" stroke="none"
          :style="{ animationDelay: delay + s.order * speed + 's' }" />
      </template>
    </g>
  </svg>
</template>

<style scoped>
.nunkish {
  display: block;
  overflow: visible;
}
.animate path {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: write 0.42s var(--ease) forwards;
}
.animate circle {
  opacity: 0;
  animation: dot 0.2s ease-out forwards;
}
.loop path {
  animation: write-loop var(--total) var(--ease) infinite;
}
.loop circle {
  animation: dot-loop var(--total) ease-out infinite;
}
@keyframes write {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes dot {
  to {
    opacity: 1;
  }
}
@keyframes write-loop {
  0% {
    stroke-dashoffset: 1;
    opacity: 1;
  }
  35%,
  80% {
    stroke-dashoffset: 0;
    opacity: 1;
  }
  100% {
    stroke-dashoffset: 0;
    opacity: 0;
  }
}
@keyframes dot-loop {
  0% {
    opacity: 0;
  }
  35%,
  80% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}
</style>
