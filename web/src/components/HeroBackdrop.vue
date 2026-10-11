<script setup>
// 背景立绘：书桌前写信的她，铺在页面最底层，边缘化进纸里。
// 默认是内置的水彩；设置里可以换成自选图片或关掉。assets/ 里放了 hero-night.webp 时，夜间换成它。
// 鸿雁那一页换成邮局分拣室（晨光 / 台灯与月光），不跟随自选图片。
import { computed } from 'vue'
import day from '../assets/hero-day.webp'
import postalDay from '../assets/geese-day.webp'
import postalNight from '../assets/geese-night.webp'
import { mediaUrl } from '../api.js'
import { store, isDark } from '../store.js'

const props = defineProps({
  strength: { type: String, default: 'full' }, // full | soft | whisper
  scene: { type: String, default: 'desk' }, // desk | postal
})

const night = Object.values(import.meta.glob('../assets/hero-night.webp', { eager: true, import: 'default' }))[0]
const mode = computed(() => store.settings?.portrait || 'art')
const dark = computed(() => {
  void store.settings?.theme
  return isDark()
})
const postal = computed(() => props.scene === 'postal')
const src = computed(() => {
  if (postal.value) return dark.value ? postalNight : postalDay
  if (mode.value === 'custom' && store.settings?.portrait_path) {
    return mediaUrl(`/api/portrait?v=${encodeURIComponent(store.settings.portrait_path)}`)
  }
  return dark.value && night ? night : day
})
const filtered = computed(() => !postal.value && dark.value && !(night && mode.value !== 'custom'))
</script>

<template>
  <div v-if="mode !== 'off'" class="hero" :class="[strength, scene, { dark, filtered, custom: mode === 'custom' && !postal }]" aria-hidden="true">
    <img :key="src" :src="src" alt="" draggable="false" />
  </div>
</template>

<style scoped>
.hero {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  animation: bloom 1.6s var(--ease) both;
}
img {
  position: absolute;
  right: 0;
  bottom: 0;
  /* Moving between full / soft / whisper eases the same picture instead of swapping two copies. */
  transition: opacity 0.6s var(--ease), filter 0.6s var(--ease);
  height: 100%;
  width: auto;
  min-width: 70%;
  max-width: none;
  object-fit: cover;
  object-position: right bottom;
  /* Feather every edge into the paper; the left side, where the words are, fades out completely. */
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 42%), linear-gradient(0deg, transparent 0%, #000 12%);
  -webkit-mask-composite: source-in;
  mask-image: linear-gradient(90deg, transparent 0%, #000 42%), linear-gradient(0deg, transparent 0%, #000 12%);
  mask-composite: intersect;
}
.full img {
  opacity: 0.62;
}
.soft img {
  opacity: 0.42;
  filter: saturate(0.85);
}
.whisper img {
  opacity: 0.16;
  filter: saturate(0.6);
}
/* Candlelight: without a night painting, dim the day one into a warm low glow. */
.filtered img {
  filter: brightness(0.62) saturate(0.8) sepia(0.12);
}
.filtered.full img {
  opacity: 0.5;
}
.filtered.soft img {
  opacity: 0.26;
}
.filtered.whisper img {
  opacity: 0.1;
}
/* The sorting room: its left side is already blank paper, so it may come further in and stand a little stronger. */
.postal img {
  min-width: 0;
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 30%), linear-gradient(0deg, transparent 0%, #000 16%);
  mask-image: linear-gradient(90deg, transparent 0%, #000 30%), linear-gradient(0deg, transparent 0%, #000 16%);
}
.postal.full img {
  opacity: 0.86;
}
.postal.dark.full img {
  opacity: 0.72;
}
/* A user's own picture has an opaque background; let the light theme absorb it into the paper. */
.custom:not(.dark) img {
  mix-blend-mode: multiply;
}
@keyframes bloom {
  from {
    opacity: 0;
    transform: scale(1.015);
  }
}
</style>
