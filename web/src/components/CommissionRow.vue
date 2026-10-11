<script setup>
// 一份委托：火漆圈勾选，完成时盖上「已送达」邮戳。点标题打开委托单。
import { computed, ref } from 'vue'
import { desk, completeCommission, startFocus, postponeCommission } from '../desk.js'
import { relativeDay, isoDate, hm, addDays, parseDate } from '../format.js'
import Icon from './Icon.vue'

const props = defineProps({
  item: { type: Object, required: true },
  compact: { type: Boolean, default: false },
  postpone: { type: Boolean, default: false },
})
const stamping = ref(false)
const root = ref(null)
const done = computed(() => props.item.status === 'done')
const today = isoDate()
const overdue = computed(() => !done.value && props.item.due_date && props.item.due_date < today)
const due = computed(() => {
  const c = props.item
  if (!c.due_date) return ''
  return `${relativeDay(c.due_date, today)}${c.due_time ? ' ' + c.due_time : ''}`
})
const steps = computed(() => {
  const s = props.item.steps || []
  return s.length ? `${s.filter((x) => x.done).length}/${s.length}` : ''
})
const REPEAT = { daily: '每天', weekly: '每周', monthly: '每月', yearly: '每年' }

// Put off: to tomorrow (or the day after, if it is already due tomorrow) or to next Monday.
const putting = ref(false)
const later = computed(() => {
  const tomorrow = addDays(today, 1)
  const first = props.item.due_date === tomorrow ? { label: '后天', on: addDays(today, 2) } : { label: '明天', on: tomorrow }
  const monday = addDays(today, 7 - ((parseDate(today).getDay() + 6) % 7))
  return [first, { label: '下周一', on: monday }].filter((o, i, all) => o.on !== props.item.due_date && (i === 0 || o.on !== all[0].on))
})
function putOff(on) {
  putting.value = false
  postponeCommission(props.item, on)
}

async function toggle() {
  if (done.value) return completeCommission(props.item, false)
  stamping.value = true
  setTimeout(() => {
    completeCommission(props.item, true, root.value)
    stamping.value = false
  }, 650)
}
</script>

<template>
  <div ref="root" class="row" :class="{ done, overdue, compact, stamping }">
    <button class="check" :aria-label="done ? `撤回「${item.title}」的送达` : `完成「${item.title}」`"
      :aria-pressed="done" @click="toggle">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12.5l4 4L18 8" /></svg>
    </button>
    <button class="body" @click="desk.editing = item">
      <span class="title">{{ item.title }}</span>
      <span class="meta">
        <span v-if="!compact" class="no mono">No.{{ String(item.number).padStart(3, '0') }}</span>
        <span v-if="due" class="due" :class="{ late: overdue }"><Icon name="clock" :size="12" />{{ overdue ? '逾期 · ' : '' }}{{ due }}</span>
        <span v-if="item.client" class="client"><Icon name="user" :size="12" />{{ item.client }}</span>
        <span v-if="steps" class="steps mono">{{ steps }}</span>
        <span v-if="item.repeat" class="repeat"><Icon name="repeat" :size="12" />{{ REPEAT[item.repeat.freq] }}</span>
        <span v-if="item.remind !== null && item.remind !== undefined && !done" class="bell"><Icon name="bell" :size="12" /></span>
        <span v-if="item.focus_seconds && !compact" class="focus"><Icon name="hourglass" :size="12" />{{ hm(item.focus_seconds) }}</span>
      </span>
    </button>
    <span v-if="!done" class="tools">
      <span v-if="postpone && putting" class="later" @mouseleave="putting = false">
        <button v-for="o in later" :key="o.on" class="chip tiny" @click="putOff(o.on)">{{ o.label }}</button>
      </span>
      <button v-else-if="postpone" class="icon-btn quill" title="推到明天或下周" @click="putting = true">
        <Icon name="future" :size="16" />
      </button>
      <button class="icon-btn quill" title="代笔时间：专心做这一件" @click="startFocus(item)">
        <Icon name="hourglass" :size="16" />
      </button>
    </span>
    <span v-if="done || stamping" class="postmark" aria-hidden="true">
      <span class="pm-ring">
        <span class="pm-top">VIOLET POST</span>
        <span class="pm-mid title-cn">已送达</span>
      </span>
    </span>
  </div>
</template>

<style scoped>
.row {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 9px 10px 9px 6px;
  border-radius: var(--radius);
  transition: background 0.2s var(--ease);
}
.row:hover {
  background: var(--violet-wash);
}
.check {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1.5px solid var(--ink-faint);
  color: transparent;
  transition: all 0.25s var(--ease);
}
.check svg {
  width: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.check:hover {
  border-color: var(--violet-ink);
  color: var(--violet-ink);
}
.done .check,
.stamping .check {
  border-color: transparent;
  color: var(--wax-text);
  background: radial-gradient(120% 140% at 30% 20%, var(--wax-a), var(--wax-b));
}
.body {
  display: grid;
  gap: 2px;
  min-width: 0;
  text-align: left;
}
.title {
  font-size: 15.5px;
  line-height: 1.45;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.done .title {
  color: var(--ink-faint);
  text-decoration: line-through;
  text-decoration-color: color-mix(in srgb, var(--violet-ink) 55%, transparent);
}
.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--ink-faint);
}
.meta > span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.meta :deep(svg) {
  flex: none;
}
.no {
  letter-spacing: 0.04em;
}
.late {
  color: var(--danger);
}
.client {
  color: var(--violet-ink);
}
.quill {
  width: 30px;
  height: 30px;
  opacity: 0;
}
.row:hover .quill,
.quill:focus-visible {
  opacity: 1;
}
.tools {
  display: flex;
  align-items: center;
  gap: 2px;
}
.later {
  display: flex;
  gap: 4px;
  animation: later-in 0.2s var(--ease);
}
.chip.tiny {
  height: 26px;
  padding: 0 10px;
  font-size: 12.5px;
}
@keyframes later-in {
  from {
    opacity: 0;
    transform: translateX(6px);
  }
}
.compact {
  padding: 7px 8px 7px 4px;
}
.compact .title {
  font-size: 15px;
}
/* The postmark that lands when a commission is delivered. */
.postmark {
  position: absolute;
  right: 44px;
  top: 50%;
  pointer-events: none;
  transform: translateY(-50%) rotate(-14deg);
}
.pm-ring {
  display: grid;
  place-items: center;
  width: 64px;
  height: 40px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  color: color-mix(in srgb, var(--violet-ink) 55%, transparent);
  line-height: 1;
  opacity: 0.75;
}
.pm-top {
  font-family: var(--font-mono);
  font-size: 6.5px;
  letter-spacing: 0.1em;
}
.pm-mid {
  font-size: 12px;
  letter-spacing: 0.2em;
}
.compact .postmark {
  right: 8px;
}
.stamping .postmark {
  animation: slam 0.55s cubic-bezier(0.2, 1.4, 0.4, 1) both;
}
.done:not(.stamping) .postmark {
  opacity: 0.55;
}
@keyframes slam {
  0% {
    transform: translateY(-50%) rotate(-30deg) scale(2.2);
    opacity: 0;
  }
  60% {
    transform: translateY(-50%) rotate(-12deg) scale(0.92);
    opacity: 1;
  }
  100% {
    transform: translateY(-50%) rotate(-14deg) scale(1);
  }
}
</style>
