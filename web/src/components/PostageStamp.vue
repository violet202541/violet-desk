<script setup>
// 一枚邮票：齿孔的纸边、画面、细框、面值。旧照片 / 雕刻版两种色调用 SVG 滤镜做；
// 封缄后盖一枚圆邮戳，波浪的注销线从右边压过来。
import { computed } from 'vue'
import { stampImage, stampValue } from '../stationery.js'

const props = defineProps({
  stamp: { type: String, default: 'harbor' },
  tone: { type: String, default: 'color' },
  width: { type: Number, default: 64 },
  postmark: { type: String, default: '' }, // a date like 2026·10·11; empty for an unused stamp
  tilt: { type: Number, default: 0 },
})
let seq = 0
const uid = `st${Math.random().toString(36).slice(2, 7)}${seq++}`
const W = 100
const H = 132
const R = 3.1 // perforation hole radius
const holes = computed(() => {
  const out = []
  const step = 8.4
  for (let x = step / 2; x < W; x += step) out.push([x, 0], [x, H])
  for (let y = step / 2; y < H; y += step) out.push([0, y], [W, y])
  return out
})
const image = computed(() => stampImage(props.stamp))
const value = computed(() => (props.stamp.startsWith('photo:') ? '30' : stampValue(props.stamp)))
// Engraved: luminance only, then mapped from deep violet ink to the paper colour.
const ENGRAVE = '0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0.2126 0.7152 0.0722 0 0  0 0 0 1 0'
</script>

<template>
  <svg class="stamp" :width="width" :height="(width * H) / W" :viewBox="`0 0 ${W} ${H}`" :style="{ '--tilt': tilt + 'deg' }"
    aria-hidden="true">
    <defs>
      <mask :id="`${uid}-perf`">
        <rect :width="W" :height="H" fill="#fff" />
        <circle v-for="([x, y], i) in holes" :key="i" :cx="x" :cy="y" :r="R" fill="#000" />
      </mask>
      <clipPath :id="`${uid}-clip`"><rect x="9" y="9" :width="W - 18" :height="H - 30" /></clipPath>
      <filter :id="`${uid}-sepia`">
        <feColorMatrix type="matrix" values="0.393 0.769 0.189 0 0  0.349 0.686 0.168 0 0  0.272 0.534 0.131 0 0  0 0 0 1 0" />
        <feComponentTransfer><feFuncR type="linear" slope="0.92" intercept="0.06" /><feFuncG type="linear" slope="0.9" intercept="0.05" /></feComponentTransfer>
      </filter>
      <filter :id="`${uid}-engraved`">
        <feColorMatrix type="matrix" :values="ENGRAVE" />
        <feComponentTransfer>
          <feFuncR type="table" tableValues="0.22 0.42 0.97" />
          <feFuncG type="table" tableValues="0.14 0.32 0.93" />
          <feFuncB type="table" tableValues="0.36 0.58 0.88" />
        </feComponentTransfer>
      </filter>
    </defs>
    <g :mask="`url(#${uid}-perf)`">
      <rect :width="W" :height="H" fill="#fbf7ee" />
      <rect x="1.5" y="1.5" :width="W - 3" :height="H - 3" fill="none" stroke="rgba(120,100,80,0.18)" stroke-width="0.6" />
    </g>
    <image :href="image" x="9" y="9" :width="W - 18" :height="H - 30" preserveAspectRatio="xMidYMid slice"
      :clip-path="`url(#${uid}-clip)`" :filter="tone === 'color' ? undefined : `url(#${uid}-${tone})`" />
    <rect x="9" y="9" :width="W - 18" :height="H - 30" fill="none" stroke="rgba(60,40,70,0.35)" stroke-width="0.7" />
    <text x="11" :y="H - 9.5" class="value">{{ value }}</text>
    <text :x="W - 11" :y="H - 10" text-anchor="end" class="caption">VIOLET POST</text>

    <g v-if="postmark" class="postmark">
      <circle cx="24" cy="30" r="17" />
      <circle cx="24" cy="30" r="13.2" stroke-width="0.6" />
      <text x="24" y="27.6" text-anchor="middle" class="pm-top">LEIDEN</text>
      <text x="24" y="35.6" text-anchor="middle" class="pm-date">{{ postmark }}</text>
      <path d="M44 22c6-3 10 3 16 0s10 3 16 0 10 3 16 0 M44 30c6-3 10 3 16 0s10 3 16 0 10 3 16 0 M44 38c6-3 10 3 16 0s10 3 16 0 10 3 16 0" />
    </g>
  </svg>
</template>

<style scoped>
.stamp {
  display: block;
  flex: none;
  transform: rotate(var(--tilt));
  filter: drop-shadow(0 1.5px 2px rgba(50, 35, 20, 0.28));
  overflow: visible;
}
.value {
  font-family: 'Cormorant Garamond', serif;
  font-size: 14px;
  font-weight: 600;
  fill: #4a3474;
}
.caption {
  font-family: 'Cutive Mono', monospace;
  font-size: 6.4px;
  letter-spacing: 0.08em;
  fill: #6e5a8f;
}
.postmark {
  fill: none;
  stroke: rgba(40, 32, 60, 0.62);
  stroke-width: 1.2;
}
.postmark text {
  stroke: none;
  fill: rgba(40, 32, 60, 0.72);
  font-family: 'Cutive Mono', monospace;
}
.pm-top {
  font-size: 5.2px;
  letter-spacing: 0.1em;
}
.pm-date {
  font-size: 5.6px;
}
</style>
