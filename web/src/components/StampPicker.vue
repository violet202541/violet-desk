<script setup>
// 邮票式单选：选中的那枚盖上邮戳并微微抬起。
defineProps({
  options: { type: Array, required: true }, // [{ value, label, sub }]
  modelValue: { type: String, required: true },
  compact: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const TILT = [-2, 1.5, -1, 2]
</script>

<template>
  <div class="stamps" :class="{ compact }" role="radiogroup">
    <button v-for="(o, i) in options" :key="o.value" type="button" class="stamp" :class="[o.value, { on: modelValue === o.value }]"
      role="radio" :aria-checked="modelValue === o.value" :style="{ '--tilt': TILT[i % 4] + 'deg' }"
      @click="emit('update:modelValue', o.value)">
      <span class="paper stamp-edge">
        <span class="inner">
          <span class="label title-cn">{{ o.label }}</span>
          <span v-if="!compact && o.sub" class="sub">{{ o.sub }}</span>
        </span>
      </span>
      <svg v-if="modelValue === o.value" class="postmark" viewBox="0 0 80 40" aria-hidden="true">
        <circle cx="22" cy="20" r="15" />
        <path d="M40 12q8-4 16 0t16 0M40 20q8-4 16 0t16 0M40 28q8-4 16 0t16 0" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.stamps {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.stamp {
  position: relative;
  transform: rotate(var(--tilt));
  transition: transform 0.3s var(--ease), filter 0.3s var(--ease);
  filter: drop-shadow(0 1px 1px rgba(60, 40, 20, 0.12));
}
.stamp:hover {
  transform: rotate(0) translateY(-2px);
}
.stamp.on {
  transform: rotate(0) translateY(-3px);
  filter: drop-shadow(0 6px 8px rgba(60, 40, 20, 0.2));
}
.paper {
  display: block;
  padding: 5px;
  background: var(--sheet-raised);
}
.inner {
  display: grid;
  place-items: center;
  align-content: center;
  min-width: 82px;
  height: 58px;
  padding: 0 12px;
  border: 1px solid var(--stamp-ink);
  color: var(--stamp-ink);
  background: color-mix(in srgb, var(--stamp-ink) 7%, transparent);
  transition: background 0.3s var(--ease);
}
.on .inner {
  background: color-mix(in srgb, var(--stamp-ink) 15%, transparent);
}
.label {
  font-size: 17px;
  line-height: 1.15;
}
.sub {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 11.5px;
  opacity: 0.8;
  letter-spacing: 0.06em;
}
.netease {
  --stamp-ink: var(--p-netease);
}
.qq {
  --stamp-ink: var(--p-qq);
}
.kugou {
  --stamp-ink: var(--p-kugou);
}
.all {
  --stamp-ink: var(--violet-ink);
}
.postmark {
  position: absolute;
  right: -18px;
  top: -10px;
  width: 64px;
  height: 32px;
  fill: none;
  stroke: var(--ink);
  stroke-opacity: 0.45;
  stroke-width: 1.3;
  pointer-events: none;
  animation: stampin 0.35s cubic-bezier(0.2, 1.4, 0.4, 1);
}
.compact .inner {
  min-width: 64px;
  height: 36px;
}
.compact .label {
  font-size: 15px;
}
.compact .postmark {
  width: 48px;
  height: 24px;
  right: -14px;
  top: -9px;
}
@keyframes stampin {
  from {
    transform: scale(1.6);
    opacity: 0;
  }
}
</style>
