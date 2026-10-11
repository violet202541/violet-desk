<script setup>
// 翡翠胸针：金色椭圆托、一圈细珠，中间一颗切面的翡翠。别在重要的信上。
defineProps({ size: { type: Number, default: 16 } })
let seq = 0
const id = `brooch-${Math.random().toString(36).slice(2, 7)}-${seq++}`
</script>

<template>
  <svg class="brooch" :width="size" :height="size * 1.25" viewBox="0 0 24 30" aria-hidden="true">
    <defs>
      <radialGradient :id="`${id}-gem`" cx="38%" cy="32%" r="75%">
        <stop offset="0" stop-color="#c8f0dc" />
        <stop offset="0.28" stop-color="#3fae86" />
        <stop offset="0.7" stop-color="#1c6b52" />
        <stop offset="1" stop-color="#0d3b2d" />
      </radialGradient>
      <linearGradient :id="`${id}-gold`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f4dd9a" />
        <stop offset="0.5" stop-color="#c49a45" />
        <stop offset="1" stop-color="#8a6428" />
      </linearGradient>
    </defs>
    <ellipse cx="12" cy="15" rx="10.5" ry="13.4" :fill="`url(#${id}-gold)`" />
    <g fill="#f6e3ad" opacity="0.9">
      <circle v-for="k in 14" :key="k" :cx="12 + 9.3 * Math.cos((k / 14) * Math.PI * 2)" :cy="15 + 12 * Math.sin((k / 14) * Math.PI * 2)" r="0.8" />
    </g>
    <ellipse cx="12" cy="15" rx="7.4" ry="9.8" :fill="`url(#${id}-gem)`" stroke="#5e4318" stroke-width="0.6" />
    <path d="M12 5.4 L16.6 11 L16.6 19 L12 24.6 L7.4 19 L7.4 11 Z" fill="none" stroke="rgba(220,255,240,0.35)" stroke-width="0.5" />
    <path d="M9 9.5 Q10.5 7.6 12.6 7.4" fill="none" stroke="#fff" stroke-width="1.1" stroke-linecap="round" opacity="0.75" />
  </svg>
</template>

<style scoped>
.brooch {
  display: block;
  filter: drop-shadow(0 1.5px 1.5px rgba(30, 20, 5, 0.4));
}
</style>
