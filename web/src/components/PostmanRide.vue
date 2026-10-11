<script setup>
// 鸿雁出门取信时，邮差骑着车从页面这一头骑到那一头。钢笔线条的剪影，车轮会转。
defineProps({
  label: { type: String, default: '' },
})
const SPOKES = [0, 45, 90, 135]
</script>

<template>
  <div class="ride" role="status">
    <div class="road" aria-hidden="true">
      <svg class="rider" viewBox="0 0 124 84" width="96" height="65">
        <g fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <g v-for="cx in [26, 94]" :key="cx" class="wheel" :style="{ transformOrigin: `${cx}px 62px` }">
            <circle :cx="cx" cy="62" r="16" />
            <path v-for="a in SPOKES" :key="a" :d="`M${cx} 62 l${(15 * Math.cos((a * Math.PI) / 180)).toFixed(2)} ${(15 * Math.sin((a * Math.PI) / 180)).toFixed(2)} M${cx} 62 l${(-15 * Math.cos((a * Math.PI) / 180)).toFixed(2)} ${(-15 * Math.sin((a * Math.PI) / 180)).toFixed(2)}`"
              stroke-width="0.8" opacity="0.6" />
          </g>
          <!-- frame -->
          <path d="M26 62 L52 62 L80 37 L46 37 L26 62 M46 33 L52 62 M80 37 L94 62 M80 37 L78 29 L88 27" />
          <path d="M42 33 L51 33" stroke-width="3" />
          <!-- the parcel rack over the front wheel, a bundle of letters on it -->
          <path d="M84 33 L102 33 L100 41 L86 41 Z" />
          <path d="M87 30 L99 30 M88 27.5 L97 27.5" stroke-width="1.4" />
          <!-- rider -->
          <g class="body">
            <path d="M47 32 C52 24 56 18 61 15" />
            <path d="M60 17 C68 20 76 24 85 27" />
            <path d="M47 32 L60 44 L53 60" />
            <path d="M47 33 L55 47 L49 62" opacity="0.55" />
            <circle cx="64" cy="9" r="5" />
            <path d="M57 6.5 L71 5.5 M59 5.5 C60 1 68 0.5 69.5 4.8" />
            <!-- the satchel on its strap -->
            <path d="M61 15 L44 37" stroke-width="1.4" />
            <path d="M37 36 L48 36 L49 48 L38 49 Z" />
            <path d="M37 36 L48 36 L47 41 L38 41 Z" stroke-width="1.4" />
          </g>
        </g>
      </svg>
    </div>
    <p class="label mono">{{ label }}</p>
  </div>
</template>

<style scoped>
.ride {
  display: grid;
  gap: 2px;
}
.road {
  position: relative;
  height: 66px;
  overflow: hidden;
  color: var(--ink-soft);
  background: linear-gradient(transparent 63px, color-mix(in srgb, var(--ink) 18%, transparent) 63px 64px, transparent 64px);
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}
.rider {
  position: absolute;
  left: 0;
  bottom: 0;
  opacity: 0.78;
  animation: ride 7s linear infinite;
}
@keyframes ride {
  from {
    transform: translateX(-110px);
  }
  to {
    transform: translateX(calc(100cqw + 20px));
  }
}
.road {
  container-type: inline-size;
}
.wheel {
  animation: turn 0.9s linear infinite;
}
@keyframes turn {
  to {
    transform: rotate(360deg);
  }
}
.body {
  animation: bob 0.45s ease-in-out infinite alternate;
}
@keyframes bob {
  to {
    transform: translateY(0.8px);
  }
}
.label {
  margin: 0;
  text-align: center;
  font-size: 12.5px;
  color: var(--ink-faint);
  letter-spacing: 0.04em;
}
@media (prefers-reduced-motion: reduce) {
  .rider {
    left: 40%;
    animation: none;
  }
  .wheel,
  .body {
    animation: none;
  }
}
</style>
