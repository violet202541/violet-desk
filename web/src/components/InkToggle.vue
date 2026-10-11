<script setup>
defineProps({ modelValue: Boolean, label: { type: String, required: true }, hint: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <label class="toggle">
    <input type="checkbox" :checked="modelValue" @change="emit('update:modelValue', $event.target.checked)" />
    <span class="switch" aria-hidden="true"><span class="knob" /></span>
    <span class="text">
      <span class="label">{{ label }}</span>
      <span v-if="hint" class="hint">{{ hint }}</span>
    </span>
  </label>
</template>

<style scoped>
.toggle {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
  padding: 6px 0;
}
input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.switch {
  flex: none;
  position: relative;
  width: 36px;
  height: 20px;
  margin-top: 2px;
  border-radius: 999px;
  border: 1.4px solid var(--rule-strong);
  transition: all 0.25s var(--ease);
}
.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--ink-faint);
  transition: all 0.3s cubic-bezier(0.3, 1.4, 0.5, 1);
}
input:checked + .switch {
  border-color: var(--violet-ink);
  background: var(--violet-wash-strong);
}
input:checked + .switch .knob {
  left: 18px;
  background: var(--violet-ink);
}
input:focus-visible + .switch {
  outline: 2px solid var(--violet-ink);
  outline-offset: 2px;
}
.text {
  display: grid;
  line-height: 1.45;
}
.label {
  color: var(--ink);
}
.hint {
  font-size: 12.5px;
  color: var(--ink-faint);
}
</style>
