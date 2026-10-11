<script setup>
import Nunkish from './Nunkish.vue'
defineProps({
  eyebrow: { type: String, required: true },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  script: { type: String, default: '' },
})
</script>

<template>
  <header class="page-header">
    <div class="text">
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1 class="title-cn">
        {{ title }}
        <Nunkish v-if="script" class="script" :text="script" :size="18" :weight="4.5" />
      </h1>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
    </div>
    <div class="side"><slot /></div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  margin-bottom: 22px;
  border-bottom: 1px solid var(--rule);
  position: relative;
}
.page-header::after {
  content: '❦';
  position: absolute;
  left: 50%;
  bottom: -10px;
  transform: translateX(-50%);
  padding: 0 12px;
  background: var(--paper);
  color: var(--gold);
  font-size: 15px;
  line-height: 18px;
}
.eyebrow {
  margin: 0 0 2px;
}
h1 {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 0;
  font-size: 34px;
  line-height: 1.25;
  color: var(--ink);
}
.script {
  color: var(--violet-ink);
  opacity: 0.45;
}
.subtitle {
  margin: 6px 0 0;
  color: var(--ink-soft);
  font-size: 14px;
}
.side {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
