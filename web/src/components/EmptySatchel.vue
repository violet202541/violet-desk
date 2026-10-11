<script setup>
// 空着的一格：墙上挂着一只空信袋。
defineProps({
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="satchel">
    <svg viewBox="0 0 120 110" width="104" height="95" aria-hidden="true">
      <g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="60" cy="8" r="3.2" />
        <path d="M60 11 L60 15" />
        <path d="M60 15 L33 46 M60 15 L87 46" />
        <path d="M30 46 Q30 42 34 42 L86 42 Q90 42 90 46 L91 94 Q91 99 86 99 L34 99 Q29 99 29 94 Z" />
        <path d="M30 46 Q60 50 90 46 L89 70 Q60 76 31 70 Z" />
        <rect x="54" y="66" width="12" height="11" rx="1.5" />
        <path d="M60 77 L60 86" />
        <path d="M38 88 Q60 92 82 88" opacity="0.4" />
      </g>
    </svg>
    <p v-if="title" class="title-cn">{{ title }}</p>
    <p v-if="hint" class="faint hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.satchel {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 26px 16px 30px;
  text-align: center;
  color: var(--ink-ghost);
}
svg {
  transform-origin: 60px 8px;
  animation: sway 5s ease-in-out infinite alternate;
}
@keyframes sway {
  from {
    transform: rotate(-2deg);
  }
  to {
    transform: rotate(2deg);
  }
}
.title-cn {
  margin: 4px 0 0;
  font-size: 16px;
  color: var(--ink-soft);
}
.hint {
  margin: 0;
  max-width: 360px;
  font-size: 13px;
  line-height: 1.7;
}
@media (prefers-reduced-motion: reduce) {
  svg {
    animation: none;
  }
}
</style>
