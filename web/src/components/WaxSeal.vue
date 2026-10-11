<script setup>
// 火漆印：不规则边缘 + 内圈压痕。tone: violet | emerald | danger | gold
defineProps({
  size: { type: Number, default: 44 },
  tone: { type: String, default: 'violet' },
  pressed: { type: Boolean, default: false },
})
const EDGE =
  'M32 3c5 0 7 3 11 4s8 0 10 4 0 7 2 10 6 6 5 11-5 6-6 10 1 8-3 11-8 1-11 3-5 6-10 6-7-4-11-6-8 0-11-3-1-7-3-11-6-5-6-10 4-7 5-11-2-7 2-10 7-2 10-4 6-4 11-4z'
</script>

<template>
  <span class="seal" :class="[tone, { pressed }]" :style="{ width: size + 'px', height: size + 'px' }">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path class="body" :d="EDGE" />
      <circle cx="32" cy="32" r="20" class="ring" />
      <ellipse cx="25" cy="21" rx="9" ry="5" class="shine" transform="rotate(-30 25 21)" />
    </svg>
    <span class="content"><slot /></span>
  </span>
</template>

<style scoped>
.seal {
  position: relative;
  display: inline-grid;
  place-items: center;
  flex: none;
  color: var(--wax-text);
  filter: drop-shadow(0 3px 4px rgba(40, 20, 60, 0.28));
}
svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.body {
  fill: var(--seal-color);
}
.ring {
  fill: none;
  stroke: rgba(0, 0, 0, 0.22);
  stroke-width: 1.4;
}
.shine {
  fill: rgba(255, 255, 255, 0.18);
}
.violet {
  --seal-color: #5b3a8c;
}
.emerald {
  --seal-color: #2c6a57;
}
.danger {
  --seal-color: #94392f;
}
.gold {
  --seal-color: #a9803a;
}
.content {
  position: relative;
  display: grid;
  place-items: center;
  font-family: var(--font-script);
  line-height: 1;
}
.pressed {
  animation: press 0.55s cubic-bezier(0.2, 1.4, 0.4, 1);
}
@keyframes press {
  0% {
    transform: scale(1.8) rotate(-18deg);
    opacity: 0;
  }
  60% {
    transform: scale(0.92) rotate(3deg);
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(0);
  }
}
</style>
