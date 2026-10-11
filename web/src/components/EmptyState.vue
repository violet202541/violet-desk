<script setup>
import Nunkish from './Nunkish.vue'
defineProps({
  script: { type: String, default: 'dear' },
  title: { type: String, required: true },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="empty">
    <Nunkish class="glyphs" :text="script" :size="64" :weight="3.2" animate :speed="0.07" />
    <h3 class="title-cn">{{ title }}</h3>
    <p v-if="hint">{{ hint }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty {
  display: grid;
  justify-items: center;
  text-align: center;
  padding: 64px 24px;
  color: var(--ink-faint);
}
.glyphs {
  color: var(--violet-ink);
  opacity: 0.32;
  margin-bottom: 18px;
}
h3 {
  margin: 0 0 6px;
  font-size: 21px;
  color: var(--ink-soft);
}
p {
  margin: 0 0 16px;
  max-width: 420px;
  font-size: 14px;
}
</style>
