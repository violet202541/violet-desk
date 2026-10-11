<script setup>
// 一枚火漆：生成的蜡块图，中间用印章压出图案。图案是线描，画三遍——
// 右下错开一点的暗边、左上错开一点的亮边、本体几乎不着色——看起来就是蜡上凸起的浮雕。
import { computed } from 'vue'
import { WAX, MOTIFS } from '../stationery.js'

const props = defineProps({
  color: { type: String, default: 'violet' },
  motif: { type: String, default: 'monogram' },
  initials: { type: String, default: '' },
  size: { type: Number, default: 64 },
  pressed: { type: Boolean, default: false }, // play the stamping animation
  tilt: { type: Number, default: 0 },
})
const wax = computed(() => WAX[props.color] || WAX.violet)
const motif = computed(() => MOTIFS[props.motif] || MOTIFS.monogram)
const text = computed(() => {
  if (props.motif === 'initials') return (props.initials || 'V').slice(0, 3)
  return motif.value.text || ''
})
// Relief offsets in face units (48 across); a little larger on small seals so the light still reads.
const off = computed(() => (props.size < 48 ? 0.9 : 0.6))
const textSize = computed(() => (props.motif === 'monogram' ? 34 : text.value.length > 2 ? 15 : text.value.length === 2 ? 19 : 26))
const script = computed(() => props.motif === 'monogram')
</script>

<template>
  <span class="seal" :class="{ pressed }" :style="{ width: size + 'px', height: size + 'px', '--tilt': tilt + 'deg' }">
    <img :src="wax.url" alt="" draggable="false" />
    <svg class="face" viewBox="0 0 48 48" aria-hidden="true">
      <g v-for="layer in ['deep', 'light', 'body']" :key="layer" :class="layer"
        :transform="layer === 'deep' ? `translate(${off} ${off * 1.1})` : layer === 'light' ? `translate(${-off} ${-off * 1.1})` : ''"
        :stroke="layer === 'deep' ? wax.deep : layer === 'light' ? wax.light : 'rgba(0,0,0,0.1)'"
        :fill="text ? (layer === 'deep' ? wax.deep : layer === 'light' ? wax.light : 'rgba(0,0,0,0.12)') : 'none'">
        <template v-if="text">
          <text x="24" :y="script ? 25.5 : 24" text-anchor="middle" dominant-baseline="central" :font-size="textSize"
            :class="script ? 'script' : 'serif'" stroke-width="0.25">{{ text }}</text>
        </template>
        <path v-for="(d, i) in motif.d || []" :key="i" :d="d" />
      </g>
    </svg>
  </span>
</template>

<style scoped>
.seal {
  position: relative;
  display: inline-block;
  flex: none;
  transform: rotate(var(--tilt));
  filter: drop-shadow(0 2px 3px rgba(40, 20, 40, 0.3));
}
img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
}
.face {
  position: absolute;
  inset: 22%;
  width: 56%;
  height: 56%;
  overflow: visible;
}
g {
  stroke-width: 1.45;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.deep {
  filter: blur(0.35px);
}
.light {
  filter: blur(0.3px);
}
.script {
  font-family: 'Cormorant Garamond', serif;
  font-style: italic;
  font-weight: 500;
}
.serif {
  font-family: 'Cormorant Garamond', 'Huiwen Mincho', serif;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.pressed {
  animation: press 0.6s cubic-bezier(0.2, 1.4, 0.4, 1) both;
}
@keyframes press {
  0% {
    transform: rotate(calc(var(--tilt) - 18deg)) scale(1.8);
    opacity: 0;
  }
  60% {
    transform: rotate(calc(var(--tilt) + 3deg)) scale(0.92);
    opacity: 1;
  }
  100% {
    transform: rotate(var(--tilt));
  }
}
@media (prefers-reduced-motion: reduce) {
  .pressed {
    animation: none;
  }
}
</style>
