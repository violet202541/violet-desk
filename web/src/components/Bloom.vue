<script setup>
// 一朵压平的堇菜花（静态）。hue 让每朵颜色略有不同：有的偏蓝紫，有的偏粉。
defineProps({
  size: { type: Number, default: 40 },
  hue: { type: Number, default: 0 },
  turn: { type: Number, default: -12 },
})
const PETALS = [
  { rot: -28, d: 5.4, rx: 3.1, ry: 4.6, c: '#5b3d93' },
  { rot: 28, d: 5.4, rx: 3.1, ry: 4.6, c: '#5b3d93' },
  { rot: -100, d: 5, rx: 2.8, ry: 4.2, c: '#7d5fb8' },
  { rot: 100, d: 5, rx: 2.8, ry: 4.2, c: '#7d5fb8' },
  { rot: 180, d: 5.6, rx: 3.6, ry: 4.9, c: '#a58bd6' },
]
</script>

<template>
  <svg class="bloom" :width="size" :height="size" viewBox="0 0 24 24" aria-hidden="true"
    :style="{ filter: `hue-rotate(${hue}deg) saturate(0.85)`, transform: `rotate(${turn}deg)` }">
    <path d="M12 17 C 12.5 20, 14 22, 16.5 23.5" class="stem" />
    <g v-for="(p, i) in PETALS" :key="i" :transform="`rotate(${p.rot} 12 12)`">
      <ellipse cx="12" :cy="12 - p.d" :rx="p.rx" :ry="p.ry" :fill="p.c" opacity="0.92" />
    </g>
    <path d="M12 13.2v4M10.6 13l-1 3M13.4 13l1 3" stroke="#f3e7c8" stroke-width="0.7" fill="none" opacity="0.8" />
    <circle cx="12" cy="12" r="1.6" fill="#e0b54e" />
  </svg>
</template>

<style scoped>
.bloom {
  overflow: visible;
}
.stem {
  fill: none;
  stroke: #6f8a55;
  stroke-width: 1.1;
  stroke-linecap: round;
}
</style>
