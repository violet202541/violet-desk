<script setup>
// 「速达」橡皮戳：暗红印泥，边缘微微晕开、着墨不匀，斜盖在急件上。
const props = defineProps({
  size: { type: Number, default: 64 }, // width in px
  tilt: { type: Number, default: -12 },
  label: { type: String, default: '速达' },
})
let seq = 0
const id = `express-${Math.random().toString(36).slice(2, 8)}-${seq++}`
</script>

<template>
  <svg class="express" :width="size" :height="size * 0.56" viewBox="0 0 120 67" :style="{ transform: `rotate(${tilt}deg)` }"
    role="img" :aria-label="label">
    <defs>
      <!-- Uneven ink: the stamp bites the paper harder in some places than others. -->
      <filter :id="id" x="-5%" y="-5%" width="110%" height="110%">
        <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" seed="7" result="grain" />
        <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -3.2 2.65" result="holes" />
        <feComposite in="SourceGraphic" in2="holes" operator="in" result="inked" />
        <feTurbulence type="turbulence" baseFrequency="0.04" numOctaves="1" seed="3" result="warp" />
        <feDisplacementMap in="inked" in2="warp" scale="0.9" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </defs>
    <g :filter="`url(#${id})`" fill="none" stroke="currentColor">
      <rect x="4" y="4" width="112" height="59" rx="7" stroke-width="3.4" />
      <rect x="10" y="10" width="100" height="47" rx="4" stroke-width="1.3" />
      <text x="63" y="38" text-anchor="middle" fill="currentColor" stroke="none" class="cn">{{ label }}</text>
      <text x="62" y="51.5" text-anchor="middle" fill="currentColor" stroke="none" class="en">EXPRESS</text>
      <path d="M16 44 H32 M88 44 H104" stroke-width="1.1" />
    </g>
  </svg>
</template>

<style scoped>
.express {
  display: block;
  color: var(--stamp-red, #a8392f);
  opacity: 0.86;
  overflow: visible;
  pointer-events: none;
}
:root[data-theme='dark'] .express {
  --stamp-red: #e0796c;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) .express {
    --stamp-red: #e0796c;
  }
}
.cn {
  font-family: var(--font-title);
  font-size: 23px;
  font-weight: 700;
  letter-spacing: 0.32em;
}
.en {
  font-family: var(--font-display);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.42em;
}
</style>
