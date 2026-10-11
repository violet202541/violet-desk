<script setup>
// 鸿雁邮务的徽记：一封封着火漆的信，两侧展开雁翅。钢笔线条，跟随 currentColor。
defineProps({ size: { type: Number, default: 64 } })
const FEATHERS = [
  'M41 37 C31 26 17 21 3 25 C13 27 21 31 28 36',
  'M41 43 C31 35 18 34 7 39 C16 40 23 42 29 45',
  'M41 49 C33 45 22 46 13 52 C21 51 27 51 32 52',
]
</script>

<template>
  <svg class="emblem" :width="size" :height="size * 0.62" viewBox="0 0 120 74" aria-hidden="true">
    <g fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path v-for="(d, i) in FEATHERS" :key="'l' + i" :d="d" />
      <g transform="translate(120 0) scale(-1 1)">
        <path v-for="(d, i) in FEATHERS" :key="'r' + i" :d="d" />
      </g>
      <rect x="42" y="29" width="36" height="26" rx="2" />
      <path d="M42 30 L60 44 L78 30" />
      <path d="M42 55 L54 45 M78 55 L66 45" opacity="0.55" />
      <circle cx="60" cy="44" r="4.2" fill="currentColor" stroke="none" />
      <path d="M60 12 L61.6 16.4 L66 18 L61.6 19.6 L60 24 L58.4 19.6 L54 18 L58.4 16.4 Z" fill="currentColor" stroke="none" opacity="0.8" />
    </g>
  </svg>
</template>

<style scoped>
.emblem {
  display: block;
  overflow: visible;
}
</style>
