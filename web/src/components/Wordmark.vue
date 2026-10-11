<script setup>
// 「Violet」钢笔花体：先描轮廓，再晕开墨色。
import mark from '../assets/wordmark.json'

defineProps({
  height: { type: Number, default: 96 },
  animate: { type: Boolean, default: false },
  delay: { type: Number, default: 0 },
})
const [x, y, w, h] = mark.viewBox
</script>

<template>
  <svg class="wordmark" :class="{ animate }" :viewBox="`${x} ${y} ${w} ${h}`" :height="height" :width="(height * w) / h"
    role="img" aria-label="Violet">
    <path v-for="(l, i) in mark.letters" :key="i" :d="l.d" pathLength="1"
      :style="{ animationDelay: `${delay + i * 0.26}s, ${delay + 0.5 + i * 0.26}s` }" />
  </svg>
</template>

<style scoped>
.wordmark {
  display: block;
  overflow: visible;
}
path {
  fill: var(--violet-ink);
  stroke: var(--violet-ink);
  stroke-width: 6;
  stroke-linejoin: round;
}
.animate path {
  fill-opacity: 0;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: trace 1.05s cubic-bezier(0.45, 0, 0.2, 1) forwards, ink 0.7s ease-out forwards;
}
@keyframes trace {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes ink {
  to {
    fill-opacity: 1;
  }
}
</style>
