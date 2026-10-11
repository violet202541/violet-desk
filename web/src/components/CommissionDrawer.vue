<script setup>
// 委托单：从右侧滑出的一张表格。关上时自动收好，不会丢字。
import { computed, reactive, ref, watch } from 'vue'
import { desk, saveCommission, tearCommission, completeCommission, startFocus } from '../desk.js'
import { addDays, isoDate, parseDate, relativeDay, hm, WEEKDAYS } from '../format.js'
import { trapFocus } from '../dialog.js'
import Icon from './Icon.vue'
import WaxSeal from './WaxSeal.vue'

const panel = ref(null)
const form = reactive({})
const stepText = ref('')
const saving = ref(false)
const open = computed(() => Boolean(desk.editing))
const isNew = computed(() => open.value && !desk.editing.id)

const REMIND = [
  { value: null, label: '不提醒' },
  { value: 0, label: '准时' },
  { value: 10, label: '提前 10 分' },
  { value: 30, label: '提前半小时' },
  { value: 60, label: '提前 1 小时' },
  { value: 1440, label: '提前 1 天' },
]
const REPEAT = [
  { value: '', label: '不重复' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
  { value: 'yearly', label: '每年' },
]

function load(item) {
  for (const key of Object.keys(form)) delete form[key]
  Object.assign(form, {
    title: '',
    client: desk.client || '',
    note: '',
    due_date: '',
    due_time: '',
    remind: null,
    steps: [],
    ...JSON.parse(JSON.stringify(item || {})),
  })
  form.freq = item?.repeat?.freq || ''
  form.weekdays = item?.repeat?.weekdays?.length ? [...item.repeat.weekdays] : []
  form.due_time = form.due_time || ''
  form.due_date = form.due_date || ''
  stepText.value = ''
}
watch(() => desk.editing, load, { immediate: true })

const today = isoDate()
const QUICK = computed(() => {
  const d = parseDate(today)
  const toSat = (6 - ((d.getDay() + 6) % 7) + 7) % 7 || 7
  const toMon = (7 - ((d.getDay() + 6) % 7)) % 7 || 7
  return [
    { label: '今天', value: today },
    { label: '明天', value: addDays(today, 1) },
    { label: '这个周末', value: addDays(today, toSat === 7 ? 0 : toSat) },
    { label: '下周一', value: addDays(today, toMon) },
    { label: '无期限', value: '' },
  ]
})

function payload() {
  const repeat = form.freq ? { freq: form.freq, interval: 1, weekdays: form.freq === 'weekly' ? form.weekdays : [] } : null
  const data = {
    title: form.title,
    client: form.client,
    note: form.note,
    due_date: form.due_date || null,
    due_time: form.due_date && form.due_time ? form.due_time : null,
    remind: form.due_date ? form.remind : null,
    repeat,
    steps: form.steps,
  }
  if (form.id) Object.assign(data, { id: form.id, revision: form.revision })
  return data
}

const dirty = computed(() => {
  if (!open.value) return false
  const before = desk.editing
  const now = payload()
  return ['title', 'client', 'note', 'due_date', 'due_time', 'remind'].some((k) => (now[k] ?? '') !== (before[k] ?? '')) ||
    JSON.stringify(now.steps) !== JSON.stringify(before.steps || []) ||
    JSON.stringify(now.repeat) !== JSON.stringify(before.repeat || null)
})

async function save(close = true) {
  if (!form.title.trim()) {
    if (isNew.value) desk.editing = null
    return
  }
  saving.value = true
  const after = desk.editing?._after // e.g. the school notice this commission was made from
  const item = await saveCommission(payload())
  saving.value = false
  if (item && after && !form.id) after(item)
  if (item && close) desk.editing = null
  else if (item) load(item)
}

function close() {
  if (dirty.value && form.title.trim()) save(true)
  else desk.editing = null
}

function addStep() {
  const text = stepText.value.trim()
  if (!text) return
  form.steps.push({ id: Math.random().toString(36).slice(2, 10), text, done: false })
  stepText.value = ''
}

function toggleWeekday(i) {
  const set = new Set(form.weekdays)
  set.has(i) ? set.delete(i) : set.add(i)
  form.weekdays = [...set].sort()
}

async function finish() {
  if (dirty.value) await save(false)
  await completeCommission(desk.editing, true, document.activeElement)
  desk.editing = null
}

async function focusNow() {
  if (dirty.value) await save(false)
  const item = desk.editing
  desk.editing = null
  startFocus(item)
}

trapFocus(panel, close)
</script>

<template>
  <Transition name="drawer">
    <div v-if="open" class="scrim" @mousedown.self="close">
      <aside ref="panel" class="drawer" role="dialog" aria-modal="true" aria-labelledby="commission-heading">
        <header class="head">
          <div>
            <p class="eyebrow">{{ isNew ? 'A new commission' : `Commission No.${String(form.number).padStart(3, '0')}` }}</p>
            <h2 id="commission-heading" class="title-cn">{{ isNew ? '新的委托' : '委托单' }}</h2>
          </div>
          <button class="icon-btn" title="收好并关上 (Esc)" @click="close"><Icon name="close" :size="18" /></button>
        </header>

        <label class="field-block">
          <span class="caption">委托内容</span>
          <textarea v-model="form.title" class="title-input" rows="2" maxlength="200" placeholder="要办的是什么事？"
            autofocus @keydown.enter.exact.prevent="save(true)" />
        </label>

        <label class="field-block">
          <span class="caption">委托人 · 为谁、为哪件事</span>
          <input v-model="form.client" class="field" list="violet-clients" maxlength="40" placeholder="自己、工作、毕业论文……" />
          <datalist id="violet-clients">
            <option v-for="c in desk.clients" :key="c.client" :value="c.client" />
          </datalist>
        </label>

        <div class="field-block">
          <span class="caption">期限</span>
          <div class="chips">
            <button v-for="q in QUICK" :key="q.label" class="chip" :class="{ on: form.due_date === q.value }"
              @click="form.due_date = q.value">{{ q.label }}</button>
          </div>
          <div class="when">
            <input v-model="form.due_date" class="field mono" type="date" aria-label="期限日期" />
            <input v-model="form.due_time" class="field mono" type="time" :disabled="!form.due_date" aria-label="期限时间" />
            <span v-if="form.due_date" class="faint small">{{ relativeDay(form.due_date) }}</span>
          </div>
        </div>

        <div class="field-block" :class="{ muted: !form.due_date }">
          <span class="caption"><Icon name="bell" :size="13" />提醒{{ form.due_date ? '' : '（先定一个期限）' }}</span>
          <div class="chips">
            <button v-for="r in REMIND" :key="String(r.value)" class="chip" :class="{ on: form.remind === r.value }"
              :disabled="!form.due_date" @click="form.remind = r.value">{{ r.label }}</button>
          </div>
          <p v-if="form.due_date && form.remind !== null && !form.due_time" class="faint small">没写时间时，按当天 09:00 提醒。</p>
        </div>

        <div class="field-block">
          <span class="caption"><Icon name="repeat" :size="13" />重复</span>
          <div class="chips">
            <button v-for="r in REPEAT" :key="r.value" class="chip" :class="{ on: form.freq === r.value }"
              @click="form.freq = r.value">{{ r.label }}</button>
          </div>
          <div v-if="form.freq === 'weekly'" class="weekdays">
            <button v-for="(w, i) in WEEKDAYS" :key="w" class="day" :class="{ on: form.weekdays.includes(i) }"
              :aria-pressed="form.weekdays.includes(i)" @click="toggleWeekday(i)">{{ w }}</button>
          </div>
          <p v-if="form.freq" class="faint small">办完一份，下一份会自动排好。</p>
        </div>

        <div class="field-block">
          <span class="caption">分步骤</span>
          <ul class="steps">
            <li v-for="(step, i) in form.steps" :key="step.id">
              <button class="mini-check" :class="{ on: step.done }" :aria-pressed="step.done" @click="step.done = !step.done">
                <svg viewBox="0 0 24 24"><path d="M6 12.5l4 4L18 8" /></svg>
              </button>
              <input v-model="step.text" class="field step-input" :class="{ done: step.done }" maxlength="200" />
              <button class="icon-btn" title="去掉这一步" @click="form.steps.splice(i, 1)"><Icon name="close" :size="14" /></button>
            </li>
          </ul>
          <input v-model="stepText" class="field" placeholder="＋ 添一个步骤，回车确认" maxlength="200" @keydown.enter.prevent="addStep" />
        </div>

        <label class="field-block">
          <span class="caption">附注</span>
          <textarea v-model="form.note" class="note" rows="3" placeholder="背景、链接、需要记得的细节……" />
        </label>

        <p v-if="form.focus_seconds" class="faint small">已为它代笔 {{ hm(form.focus_seconds) }}。</p>

        <footer class="foot">
          <button v-if="!isNew" class="btn small ghost danger" @click="tearCommission(desk.editing)"><Icon name="trash" :size="14" />撕掉</button>
          <span class="spacer" />
          <button v-if="!isNew && form.status !== 'done'" class="btn small" @click="focusNow"><Icon name="hourglass" :size="14" />代笔时间</button>
          <button v-if="!isNew && form.status !== 'done'" class="btn small" @click="finish"><Icon name="check" :size="14" />已送达</button>
          <button class="btn wax" :disabled="saving || !form.title.trim()" @click="save(true)">
            {{ isNew ? '接下委托' : '收好' }}
          </button>
        </footer>
        <WaxSeal class="corner-seal" :size="46"><span>V</span></WaxSeal>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.scrim {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 65;
  background: rgba(30, 22, 40, 0.18);
}
.drawer {
  position: absolute;
  top: 12px;
  right: 12px;
  bottom: 12px;
  width: min(460px, calc(100vw - 120px));
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px 28px 20px;
  overflow-y: auto;
  background:
    linear-gradient(90deg, transparent 14px, color-mix(in srgb, var(--danger) 22%, transparent) 14px 15px, transparent 15px),
    var(--sheet-raised);
  border: 1px solid var(--rule);
  border-radius: 4px;
  box-shadow: var(--shadow-lift), -30px 0 60px -40px rgba(40, 20, 60, 0.5);
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
.head p,
.head h2 {
  margin: 0;
}
.head h2 {
  font-size: 26px;
  font-weight: 400;
}
.field-block {
  display: grid;
  gap: 6px;
}
.field-block.muted .chips {
  opacity: 0.5;
}
.caption {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--ink-faint);
  letter-spacing: 0.08em;
}
.title-input,
.note {
  width: 100%;
  resize: vertical;
  border: 0;
  border-bottom: 1px solid var(--rule-strong);
  background: transparent;
  outline: none;
  padding: 2px 0 6px;
  line-height: 1.6;
}
/* User text stays in the body face: the display mincho draws some simplified characters in older forms. */
.title-input {
  font-size: 20px;
  resize: none;
}
.title-input:focus,
.note:focus {
  border-color: var(--violet-ink);
}
.note {
  font-size: 14.5px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  border-color: var(--rule);
}
.chip:disabled {
  cursor: default;
}
.when {
  display: flex;
  align-items: center;
  gap: 10px;
}
.when .field {
  height: 34px;
  font-size: 14px;
}
.weekdays {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}
.day {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--rule-strong);
  font-family: var(--font-title);
  font-size: 14px;
  color: var(--ink-soft);
}
.day.on {
  color: var(--wax-text);
  border-color: transparent;
  background: radial-gradient(120% 140% at 30% 20%, var(--wax-a), var(--wax-b));
}
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
}
.steps li {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
}
.mini-check {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1.4px solid var(--ink-faint);
  color: transparent;
}
.mini-check svg {
  width: 13px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
}
.mini-check.on {
  color: var(--wax-text);
  background: var(--violet-ink);
  border-color: var(--violet-ink);
}
.step-input {
  height: 34px;
  border-bottom-color: transparent;
}
.step-input.done {
  color: var(--ink-faint);
  text-decoration: line-through;
}
.small {
  font-size: 12.5px;
  margin: 0;
}
.foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px dashed var(--rule-strong);
}
.spacer {
  flex: 1;
}
.corner-seal {
  position: absolute;
  top: 18px;
  right: 74px;
  opacity: 0.9;
  font-size: 24px;
  pointer-events: none;
}
.drawer-enter-from,
.drawer-leave-to {
  background: transparent;
}
.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(40px);
  opacity: 0;
}
.drawer-enter-active,
.drawer-leave-active,
.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: all 0.35s var(--ease);
}
</style>
