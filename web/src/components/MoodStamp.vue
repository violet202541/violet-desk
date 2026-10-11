<script setup>
// 心情与天气邮票：齿孔边框里一幅小小的线描，贴在回信的右上角，也印在邮戳簿里。
import { computed } from 'vue'
import { MOODS, WEATHERS } from '../stamps.js'

const props = defineProps({
  kind: { type: String, default: 'mood' }, // mood | weather
  value: { type: String, required: true },
  size: { type: Number, default: 56 },
  label: { type: Boolean, default: true },
  tilt: { type: Number, default: 0 },
})

const info = computed(() => (props.kind === 'weather' ? WEATHERS : MOODS)[props.value] || MOODS.calm)
</script>

<template>
  <span class="mood-stamp stamp-edge" :style="{ '--hue': info.hue, '--s': size + 'px', transform: `rotate(${tilt}deg)` }"
    :title="info.label">
    <span class="face">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true">
        <path v-for="(d, i) in info.d" :key="i" :d="d" />
      </svg>
      <span v-if="label" class="name">{{ info.label }}</span>
    </span>
  </span>
</template>

<style scoped>
.mood-stamp {
  --hole: calc(var(--s) / 22);
  display: inline-block;
  width: var(--s);
  height: calc(var(--s) * 1.18);
  flex: none;
  filter: drop-shadow(0 2px 3px rgba(60, 40, 20, 0.18));
}
.face {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 1px;
  width: 100%;
  height: 100%;
  color: var(--hue);
  background:
    radial-gradient(120% 90% at 30% 15%, color-mix(in srgb, var(--hue) 10%, #fffdf6), color-mix(in srgb, var(--hue) 24%, #f6efe0));
  border: 1px solid color-mix(in srgb, var(--hue) 40%, transparent);
}
svg {
  width: 62%;
  height: auto;
}
.name {
  font-family: var(--font-title);
  font-size: calc(var(--s) / 5.2);
  line-height: 1;
  letter-spacing: 0.08em;
  color: color-mix(in srgb, var(--hue) 75%, #2a2238);
}
:global(:root[data-theme='dark']) .face {
  background: radial-gradient(120% 90% at 30% 15%, color-mix(in srgb, var(--hue) 22%, #2a2534), color-mix(in srgb, var(--hue) 12%, #1c1825));
}
@media (prefers-color-scheme: dark) {
  :global(:root:not([data-theme='light'])) .face {
    background: radial-gradient(120% 90% at 30% 15%, color-mix(in srgb, var(--hue) 22%, #2a2534), color-mix(in srgb, var(--hue) 12%, #1c1825));
  }
}
</style>
