<script setup>
// 一只鸿雁的剪影：长颈前伸、翅膀上下扇动，脚下系着一封信（鸿雁传书）。
defineProps({
  size: { type: Number, default: 96 },
  letter: { type: Boolean, default: true },
  still: { type: Boolean, default: false },
  delay: { type: Number, default: 0 },
})
</script>

<template>
  <svg class="goose" :class="{ still }" :width="size" :height="size / 2" viewBox="0 0 120 60" aria-hidden="true"
    :style="{ '--delay': delay + 's' }">
    <g class="wing far">
      <path d="M55 30 C 55 22, 53 14, 47 7 C 54 13, 60 21, 65 30 Z" />
    </g>
    <path class="tail" d="M15 36 L 5 32.5 L 8 37 L 5 41 Z" />
    <path class="body" d="M14 36 C 24 30, 44 27, 62 30 C 72 31.5, 82 31, 94 29.5 C 99 28.5, 104 28.5, 107 30 L 114.5 31.6
      L 107 33.2 C 103 34, 98 34, 93 34.2 C 82 35, 74 38, 64 40.2 C 48 43.4, 28 42.4, 14 36 Z" />
    <ellipse class="cheek" cx="102.5" cy="32.4" rx="2.6" ry="1.3" />
    <g class="wing near">
      <path d="M45 31.5 C 43 21, 36 11, 23 4 C 30 7, 38 12, 46 17 C 50 21, 55 26, 59 31 Z" />
    </g>
    <g v-if="letter" class="mail">
      <path class="string" d="M57 41 L 58 46" />
      <rect x="51" y="45.5" width="14" height="9" rx="1" />
      <path class="flap" d="M51.4 46 L 58 50.6 L 64.6 46" />
    </g>
  </svg>
</template>

<style scoped>
.goose {
  display: block;
  overflow: visible;
  color: var(--goose-ink, var(--ink));
}
.body,
.tail,
.wing path {
  fill: currentColor;
}
.wing.far path {
  opacity: 0.55;
}
.cheek {
  fill: var(--goose-cheek, var(--paper));
  opacity: 0.85;
}
.mail rect {
  fill: var(--goose-letter, var(--sheet-raised));
  stroke: currentColor;
  stroke-width: 0.9;
}
.mail .flap,
.mail .string {
  fill: none;
  stroke: currentColor;
  stroke-width: 0.9;
}
.mail {
  transform-box: view-box;
  transform-origin: 57px 41px;
  animation: sway 1s ease-in-out infinite alternate;
  animation-delay: var(--delay);
}
.wing {
  transform-box: view-box;
  transform-origin: 52px 31px;
  animation: flap 0.52s cubic-bezier(0.45, 0, 0.55, 1) infinite alternate;
  animation-delay: var(--delay);
}
.wing.far {
  transform-origin: 58px 30px;
  animation-delay: calc(var(--delay) + 0.05s);
}
@keyframes flap {
  from {
    transform: scaleY(1);
  }
  to {
    transform: scaleY(-0.62) skewX(-8deg);
  }
}
@keyframes sway {
  from {
    transform: rotate(-6deg);
  }
  to {
    transform: rotate(7deg);
  }
}
.still .wing,
.still .mail {
  animation: none;
}
@media (prefers-reduced-motion: reduce) {
  .wing,
  .mail {
    animation: none;
  }
}
</style>
