<script setup>
import Nunkish from './Nunkish.vue'
defineProps({ label: { type: String, default: '正在代笔…' }, script: { type: String, default: 'writing' } })
</script>

<template>
  <div class="loader" role="status">
    <div class="line">
      <Nunkish :text="script" :size="34" loop :speed="0.12" />
      <span class="nib" />
    </div>
    <p class="label">{{ label }}</p>
  </div>
</template>

<style scoped>
.loader {
  display: grid;
  justify-items: center;
  gap: 14px;
  padding: 56px 0;
  color: var(--violet-ink);
}
.line {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--rule-strong);
}
.nib {
  width: 2px;
  height: 22px;
  background: var(--violet-ink);
  animation: blink 0.9s steps(1) infinite;
}
.label {
  margin: 0;
  color: var(--ink-faint);
  font-size: 14px;
  letter-spacing: 0.08em;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
